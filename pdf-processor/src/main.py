import os
import json
import hashlib
import logging
import threading
from typing import Dict, Any
from dotenv import load_dotenv
from confluent_kafka import Consumer, Producer, KafkaError
from confluent_kafka.schema_registry import SchemaRegistryClient
from confluent_kafka.schema_registry.avro import AvroSerializer, AvroDeserializer
from confluent_kafka.serialization import StringSerializer, SerializationContext, MessageField
import requests
from io import BytesIO
from PyPDF2 import PdfReader
import time
from fastapi import FastAPI
import uvicorn

# Configuração de logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Carrega variáveis de ambiente
load_dotenv()

# Inicializa o FastAPI
app = FastAPI(title="PDF Processor Service")

@app.get("/health")
async def health_check():
    return {"status": "healthy"}

def run_api():
    uvicorn.run(app, host="0.0.0.0", port=5000)

class PDFProcessor:
    def __init__(self):
        # Configurações do Kafka
        self.bootstrap_servers = os.getenv('KAFKA_BOOTSTRAP_SERVERS')
        self.api_key = os.getenv('KAFKA_API_KEY')
        self.api_secret = os.getenv('KAFKA_API_SECRET')
        self.input_topic = os.getenv('KAFKA_INPUT_TOPIC')
        self.output_topic = os.getenv('KAFKA_OUTPUT_TOPIC')
        self.error_topic = os.getenv('KAFKA_ERROR_TOPIC')
        self.consumer_group = os.getenv('KAFKA_CONSUMER_GROUP')

        # Configurações do Schema Registry
        self.schema_registry_url = os.getenv('SCHEMA_REGISTRY_URL')
        self.schema_registry_key = os.getenv('SCHEMA_REGISTRY_API_KEY')
        self.schema_registry_secret = os.getenv('SCHEMA_REGISTRY_API_SECRET')

        # Configuração do Schema Registry
        self.schema_registry = SchemaRegistryClient({
            'url': self.schema_registry_url,
            'basic.auth.user.info': f"{self.schema_registry_key}:{self.schema_registry_secret}"
        })

        # Configuração do Consumer
        self.consumer = Consumer({
            'bootstrap.servers': self.bootstrap_servers,
            'security.protocol': 'SASL_SSL',
            'sasl.mechanisms': 'PLAIN',
            'sasl.username': self.api_key,
            'sasl.password': self.api_secret,
            'group.id': self.consumer_group,
            'auto.offset.reset': 'earliest',
            'enable.auto.commit': 'false'
        })

        # Configuração do Producer
        self.producer = Producer({
            'bootstrap.servers': self.bootstrap_servers,
            'security.protocol': 'SASL_SSL',
            'sasl.mechanisms': 'PLAIN',
            'sasl.username': self.api_key,
            'sasl.password': self.api_secret
        })

        # Configuração dos serializadores/deserializadores
        self.string_serializer = StringSerializer('utf_8')
        
        # Carrega os schemas
        self.input_schema = self.schema_registry.get_latest_version(f"{self.input_topic}-value").schema
        self.pdf_completo_schema = self.schema_registry.get_latest_version("pdf_baixado-value").schema

        # Configura os deserializadores
        self.input_deserializer = AvroDeserializer(self.schema_registry, self.input_schema)

        # Configura os serializadores
        self.pdf_completo_serializer = AvroSerializer(self.schema_registry, self.pdf_completo_schema)

        # Inscreve no tópico de entrada
        self.consumer.subscribe([self.input_topic])

    def download_pdf(self, url: str) -> bytes:
        """Download do PDF da URL fornecida"""
        try:
            response = requests.get(url)
            response.raise_for_status()
            return response.content
        except Exception as e:
            logger.error(f"Erro ao baixar PDF de {url}: {str(e)}")
            raise

    def extract_text_from_pdf(self, pdf_content: bytes) -> str:
        """Extrai o texto do conteúdo do PDF"""
        try:
            pdf_file = BytesIO(pdf_content)
            pdf_reader = PdfReader(pdf_file)
            text = ""
            for page in pdf_reader.pages:
                text += page.extract_text() + "\n"
            return text
        except Exception as e:
            logger.error(f"Erro ao extrair texto do PDF: {str(e)}")
            raise

    def generate_document_id(self, url: str) -> str:
        """Gera um ID único para o documento baseado na URL"""
        return hashlib.sha256(url.encode()).hexdigest()

    def process_message(self, msg) -> None:
        """Processa uma mensagem do Kafka"""
        try:
            if msg is None:
                return

            if msg.error():
                if msg.error().code() == KafkaError._PARTITION_EOF:
                    logger.info(f"Fim da partição {msg.partition()}")
                else:
                    logger.error(f"Erro ao receber mensagem: {msg.error()}")
                return

            # Deserializa a mensagem
            try:
                value = self.input_deserializer(msg.value(), SerializationContext(msg.topic(), MessageField.VALUE))
                logger.info(f"Mensagem recebida: {value}")
            except Exception as e:
                logger.error(f"Erro ao deserializar mensagem: {str(e)}")
                return

            if not value or 'url' not in value:
                logger.error("Mensagem inválida: URL não encontrada")
                return

            url = value['url']
            logger.info(f"Processando PDF da URL: {url}")

            # Download do PDF
            pdf_content = self.download_pdf(url)
            
            # Extrai o texto
            text = self.extract_text_from_pdf(pdf_content)
            
            # Gera o ID do documento (HASH 256 da URL)
            doc_id = self.generate_document_id(url)
            logger.info(f"ID do documento gerado: {doc_id}")

            # Prepara a mensagem para o tópico pdf_baixado
            pdf_completo_msg = {
                'id': doc_id,
                'url': url,
                'text': text
            }

            # Envia para o tópico pdf_baixado usando o ID como chave
            try:
                self.producer.produce(
                    topic='pdf_baixado',
                    key=doc_id.encode('utf-8'),  # Usa o ID como chave da mensagem
                    value=self.pdf_completo_serializer(
                        pdf_completo_msg,
                        SerializationContext('pdf_baixado', MessageField.VALUE)
                    ),
                    on_delivery=self.delivery_report
                )
                self.producer.poll(0)
                logger.info(f"Mensagem enviada para pdf_baixado com ID: {doc_id}")
            except Exception as e:
                logger.error(f"Erro ao enviar mensagem para pdf_baixado: {str(e)}")
                # Envia mensagem de erro
                error_msg = {
                    'error': str(e),
                    'url': url,
                    'timestamp': int(time.time() * 1000)
                }
                self.producer.produce(
                    topic=self.error_topic,
                    value=self.string_serializer(json.dumps(error_msg)),
                    on_delivery=self.delivery_report
                )
                self.producer.poll(0)

            # Commit da mensagem
            self.consumer.commit(msg)

        except Exception as e:
            logger.error(f"Erro ao processar mensagem: {str(e)}")
            # Envia mensagem de erro
            error_msg = {
                'error': str(e),
                'url': url if 'url' in locals() else 'unknown',
                'timestamp': int(time.time() * 1000)
            }
            self.producer.produce(
                topic=self.error_topic,
                value=self.string_serializer(json.dumps(error_msg)),
                on_delivery=self.delivery_report
            )
            self.producer.poll(0)

    def delivery_report(self, err, msg):
        """Callback para relatório de entrega de mensagens"""
        if err is not None:
            logger.error(f"Falha ao entregar mensagem: {err}")
        else:
            logger.info(f"Mensagem entregue: {msg.topic()} [{msg.partition()}]")

    def run(self):
        """Executa o processador de PDFs"""
        logger.info("Iniciando processador de PDFs...")
        try:
            while True:
                msg = self.consumer.poll(1.0)
                if msg is None:
                    continue
                if msg.error():
                    if msg.error().code() == KafkaError._PARTITION_EOF:
                        logger.info(f"Fim da partição {msg.partition()}")
                    else:
                        logger.error(f"Erro ao receber mensagem: {msg.error()}")
                else:
                    self.process_message(msg)
        except KeyboardInterrupt:
            logger.info("Encerrando processador de PDFs...")
        finally:
            self.consumer.close()
            self.producer.flush()

if __name__ == "__main__":
    # Inicia o FastAPI em uma thread separada
    api_thread = threading.Thread(target=run_api)
    api_thread.daemon = True
    api_thread.start()

    # Inicia o processador de PDFs
    processor = PDFProcessor()
    processor.run() 