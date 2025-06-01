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

# Configuração de logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Carrega variáveis de ambiente
load_dotenv()

class PDFProcessor:
    """Processador de PDFs que monitora URLs e extrai texto dos documentos.
    
    Esta classe é responsável por:
    - Consumir URLs de PDFs do tópico Kafka
    - Fazer download dos documentos
    - Extrair o texto usando PyPDF2
    - Publicar o conteúdo extraído em outro tópico
    """

    def __init__(self):
        """Inicializa o processador com configurações do Kafka e Schema Registry."""
        self.kafka_config = {
            'bootstrap.servers': os.getenv('KAFKA_BOOTSTRAP_SERVERS'),
            'security.protocol': 'SASL_SSL',
            'sasl.mechanisms': 'PLAIN',
            'sasl.username': os.getenv('KAFKA_API_KEY'),
            'sasl.password': os.getenv('KAFKA_API_SECRET'),
            'group.id': os.getenv('KAFKA_CONSUMER_GROUP', 'pdf-processor-group'),
            'auto.offset.reset': 'earliest'
        }

        self.schema_registry_config = {
            'url': os.getenv('SCHEMA_REGISTRY_URL'),
            'basic.auth.user.info': f"{os.getenv('SCHEMA_REGISTRY_API_KEY')}:{os.getenv('SCHEMA_REGISTRY_API_SECRET')}"
        }

        self.schema_registry_client = SchemaRegistryClient(self.schema_registry_config)
        self.setup_serializers()

    def setup_serializers(self) -> None:
        """Configura os serializadores Avro para os tópicos de entrada e saída."""
        # Serializador para o tópico de entrada (pdf_download)
        self.input_serializer = AvroDeserializer(
            self.schema_registry_client,
            "co.techrom.poc_rag.pdf_download"
        )

        # Serializador para o tópico de saída (pdf_baixado)
        self.output_serializer = AvroSerializer(
            self.schema_registry_client,
            "co.techrom.poc_rag.pdf_completo"
        )

    def download_pdf(self, url: str) -> bytes:
        """Faz download de um PDF a partir de uma URL.
        
        Args:
            url: URL do documento PDF para download.
            
        Returns:
            bytes: Conteúdo do PDF em bytes.
            
        Raises:
            Exception: Se houver erro no download ou o conteúdo não for um PDF válido.
        """
        try:
            response = requests.get(url, timeout=30)
            response.raise_for_status()
            
            # Verifica se o conteúdo é um PDF
            if not response.headers.get('content-type', '').lower().startswith('application/pdf'):
                raise Exception("O conteúdo não é um PDF válido")
                
            return response.content
        except Exception as e:
            logger.error(f"Erro ao baixar PDF de {url}: {str(e)}")
            raise

    def extract_text(self, pdf_content: bytes) -> str:
        """Extrai o texto de um documento PDF.
        
        Args:
            pdf_content: Conteúdo do PDF em bytes.
            
        Returns:
            str: Texto extraído do PDF.
            
        Raises:
            Exception: Se houver erro na extração do texto.
        """
        try:
            pdf_file = BytesIO(pdf_content)
            pdf_reader = PdfReader(pdf_file)
            text = ""
            
            for page in pdf_reader.pages:
                text += page.extract_text() + "\n"
                
            return text.strip()
        except Exception as e:
            logger.error(f"Erro ao extrair texto do PDF: {str(e)}")
            raise

    def process_message(self, msg: Any) -> None:
        """Processa uma mensagem do Kafka contendo URL de PDF.
        
        Args:
            msg: Mensagem do Kafka com a URL do PDF.
            
        Raises:
            Exception: Se houver erro no processamento da mensagem.
        """
        try:
            # Deserializa a mensagem
            value = self.input_serializer(msg.value(), SerializationContext(msg.topic(), MessageField.VALUE))
            
            if value is None:
                return

            url = value.get('url')
            if not url:
                logger.warning("URL não encontrada na mensagem")
                return

            # Gera ID único para o documento
            doc_id = hashlib.sha256(url.encode()).hexdigest()
            
            # Faz download e extrai o texto
            pdf_content = self.download_pdf(url)
            text = self.extract_text(pdf_content)

            # Prepara a mensagem de saída
            output_message = {
                'id': doc_id,
                'url': url,
                'text': text
            }

            # Serializa e publica a mensagem
            serialized_value = self.output_serializer(
                output_message,
                SerializationContext("pdf_baixado", MessageField.VALUE)
            )

            # Publica no tópico de saída
            producer = Producer(self.kafka_config)
            producer.produce(
                topic="pdf_baixado",
                value=serialized_value,
                callback=self.delivery_report
            )
            producer.flush()

            logger.info(f"PDF processado com sucesso: {url}")

        except Exception as e:
            logger.error(f"Erro ao processar mensagem: {str(e)}")
            raise

    def delivery_report(self, err: KafkaError, msg: Any) -> None:
        """Callback para relatório de entrega de mensagens.
        
        Args:
            err: Erro ocorrido durante a entrega, se houver.
            msg: Mensagem que foi entregue.
        """
        if err is not None:
            logger.error(f"Erro na entrega da mensagem: {err}")
        else:
            logger.debug(f"Mensagem entregue: {msg.topic()} [{msg.partition()}]")

    def run(self) -> None:
        """Inicia o processador e começa a consumir mensagens do Kafka."""
        try:
            consumer = Consumer(self.kafka_config)
            consumer.subscribe(["pdf_download"])

            logger.info("Iniciando processador de PDFs...")
            
            while True:
                msg = consumer.poll(1.0)
                if msg is None:
                    continue
                if msg.error():
                    logger.error(f"Erro do consumidor: {msg.error()}")
                    continue
                    
                self.process_message(msg)

        except KeyboardInterrupt:
            logger.info("Encerrando processador de PDFs...")
        except Exception as e:
            logger.error(f"Erro fatal no processador: {str(e)}")
            raise
        finally:
            if 'consumer' in locals():
                consumer.close()

def run_processor():
    """Inicia o processador de PDFs em um processo separado."""
    processor = PDFProcessor()
    processor.run()

if __name__ == "__main__":
    run_processor() 