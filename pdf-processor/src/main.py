import os
import json
import hashlib
import logging
import multiprocessing
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
    port = int(os.getenv('PORT', 8000))
    uvicorn.run(app, host="0.0.0.0", port=port)

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

        # Inicialização lazy
        self._schema_registry = None
        self._consumer = None
        self._producer = None
        self._input_deserializer = None
        self._pdf_completo_serializer = None
        self._string_serializer = None

    @property
    def schema_registry(self):
        if self._schema_registry is None:
            self._schema_registry = SchemaRegistryClient({
                'url': self.schema_registry_url,
                'basic.auth.user.info': f"{self.schema_registry_key}:{self.schema_registry_secret}"
            })
        return self._schema_registry

    @property
    def consumer(self):
        if self._consumer is None:
            self._consumer = Consumer({
                'bootstrap.servers': self.bootstrap_servers,
                'security.protocol': 'SASL_SSL',
                'sasl.mechanisms': 'PLAIN',
                'sasl.username': self.api_key,
                'sasl.password': self.api_secret,
                'group.id': self.consumer_group,
                'auto.offset.reset': 'earliest',
                'enable.auto.commit': 'false'
            })
            self._consumer.subscribe([self.input_topic])
        return self._consumer

    @property
    def producer(self):
        if self._producer is None:
            self._producer = Producer({
                'bootstrap.servers': self.bootstrap_servers,
                'security.protocol': 'SASL_SSL',
                'sasl.mechanisms': 'PLAIN',
                'sasl.username': self.api_key,
                'sasl.password': self.api_secret,
                'queue.buffering.max.messages': 100000,
                'queue.buffering.max.ms': 100,
                'batch.num.messages': 10000
            })
        return self._producer

    @property
    def input_deserializer(self):
        if self._input_deserializer is None:
            input_schema = self.schema_registry.get_latest_version(f"{self.input_topic}-value").schema
            self._input_deserializer = AvroDeserializer(self.schema_registry, input_schema)
        return self._input_deserializer

    @property
    def pdf_completo_serializer(self):
        if self._pdf_completo_serializer is None:
            pdf_completo_schema = self.schema_registry.get_latest_version("pdf_baixado-value").schema
            self._pdf_completo_serializer = AvroSerializer(self.schema_registry, pdf_completo_schema)
        return self._pdf_completo_serializer

    @property
    def string_serializer(self):
        if self._string_serializer is None:
            self._string_serializer = StringSerializer('utf_8')
        return self._string_serializer

    def download_pdf(self, url: str) -> bytes:
        """Download do PDF da URL fornecida"""
        try:
            response = requests.get(url, timeout=10)
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
                    logger.debug(f"Fim da partição {msg.partition()}")
                else:
                    logger.error(f"Erro ao receber mensagem: {msg.error()}")
                return

            # Deserializa a mensagem
            try:
                value = self.input_deserializer(msg.value(), SerializationContext(msg.topic(), MessageField.VALUE))
                logger.debug(f"Mensagem recebida: {value}")
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
            logger.debug(f"ID do documento gerado: {doc_id}")

            # Prepara a mensagem para o tópico pdf_baixado
            pdf_completo_msg = {
                'id': doc_id,
                'url': url,
                'text': text
            }

            # Flag para controlar se a mensagem foi enviada com sucesso
            message_sent = False

            # Envia para o tópico pdf_baixado usando o ID como chave
            try:
                self.producer.produce(
                    topic='pdf_baixado',
                    key=doc_id.encode('utf-8'),
                    value=self.pdf_completo_serializer(
                        pdf_completo_msg,
                        SerializationContext('pdf_baixado', MessageField.VALUE)
                    ),
                    on_delivery=self.delivery_report
                )
                
                # Aguarda a confirmação do envio com timeout reduzido
                self.producer.poll(0.1)
                message_sent = True
                logger.debug(f"Mensagem enviada para pdf_baixado com ID: {doc_id}")
            except Exception as e:
                logger.error(f"Erro ao enviar mensagem para pdf_baixado: {str(e)}")
                # Envia mensagem de erro
                error_msg = {
                    'error': str(e),
                    'url': url,
                    'timestamp': int(time.time() * 1000)
                }
                try:
                    self.producer.produce(
                        topic=self.error_topic,
                        value=self.string_serializer(json.dumps(error_msg)),
                        on_delivery=self.delivery_report
                    )
                    self.producer.poll(0.1)
                except Exception as error_e:
                    logger.error(f"Erro ao enviar mensagem de erro: {str(error_e)}")

            # Só faz o commit se a mensagem foi enviada com sucesso
            if message_sent:
                self.consumer.commit(msg)
                logger.debug(f"Commit realizado para mensagem com ID: {doc_id}")
            else:
                logger.warning(f"Não foi possível fazer o commit da mensagem com ID: {doc_id}")

        except Exception as e:
            logger.error(f"Erro ao processar mensagem: {str(e)}")
            # Envia mensagem de erro
            error_msg = {
                'error': str(e),
                'url': url if 'url' in locals() else 'unknown',
                'timestamp': int(time.time() * 1000)
            }
            try:
                self.producer.produce(
                    topic=self.error_topic,
                    value=self.string_serializer(json.dumps(error_msg)),
                    on_delivery=self.delivery_report
                )
                self.producer.poll(0.1)
            except Exception as error_e:
                logger.error(f"Erro ao enviar mensagem de erro: {str(error_e)}")

    def delivery_report(self, err, msg):
        """Callback para relatório de entrega de mensagens"""
        if err is not None:
            logger.error(f"Falha ao entregar mensagem: {err}")
        else:
            logger.debug(f"Mensagem entregue: {msg.topic()} [{msg.partition()}]")

    def run(self):
        """Executa o processador de PDFs"""
        logger.info("Iniciando processador de PDFs...")
        try:
            while True:
                msg = self.consumer.poll(0.1)  # Reduzido timeout do poll
                if msg is None:
                    continue
                if msg.error():
                    if msg.error().code() == KafkaError._PARTITION_EOF:
                        logger.debug(f"Fim da partição {msg.partition()}")
                    else:
                        logger.error(f"Erro ao receber mensagem: {msg.error()}")
                else:
                    self.process_message(msg)
        except KeyboardInterrupt:
            logger.info("Encerrando processador de PDFs...")
        finally:
            if self._consumer:
                self.consumer.close()
            if self._producer:
                self.producer.flush(timeout=1.0)

def run_processor():
    """Função para executar o processador em um processo separado"""
    processor = PDFProcessor()
    processor.run()

if __name__ == "__main__":
    # Inicia o FastAPI em um processo separado
    api_process = multiprocessing.Process(target=run_api)
    api_process.daemon = True
    api_process.start()

    # Inicia o processador de PDFs no processo principal
    run_processor() 