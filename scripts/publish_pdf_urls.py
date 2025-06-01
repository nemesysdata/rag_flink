import os
import uuid
from dotenv import load_dotenv
from confluent_kafka import Producer
from confluent_kafka.schema_registry import SchemaRegistryClient
from confluent_kafka.schema_registry.avro import AvroSerializer
from confluent_kafka.serialization import SerializationContext, MessageField
from loguru import logger

# URLs dos PDFs
PDF_URLS = [
    "https://www.gov.br/saude/pt-br/assuntos/pcdt/a/artrite-psoriaca.pdf/@@download/file",
    "https://www.gov.br/saude/pt-br/assuntos/pcdt/a/anemia-deficiencia-de-ferro/@@download/file",
    "https://www.gov.br/saude/pt-br/assuntos/pcdt/a/artrite-reativa/@@download/file",
    "https://www.gov.br/saude/pt-br/assuntos/pcdt/i/isotretinoina-no-tratamento-da-acne-grave/@@download/file"
]

def delivery_report(err, msg):
    """Callback para relatório de entrega de mensagens"""
    if err is not None:
        logger.error(f"Falha na entrega da mensagem: {err}")
    else:
        logger.info(f"Mensagem entregue: {msg.topic()} [{msg.partition()}]")

def main():
    # Carrega variáveis de ambiente
    load_dotenv()
    
    # Configuração do Kafka
    kafka_config = {
        'bootstrap.servers': os.getenv('KAFKA_BOOTSTRAP_SERVERS'),
        'security.protocol': 'SASL_SSL',
        'sasl.mechanisms': 'PLAIN',
        'sasl.username': os.getenv('KAFKA_API_KEY'),
        'sasl.password': os.getenv('KAFKA_API_SECRET')
    }
    
    # Configuração do Schema Registry
    schema_registry_config = {
        'url': os.getenv('SCHEMA_REGISTRY_URL'),
        'basic.auth.user.info': f"{os.getenv('SCHEMA_REGISTRY_API_KEY')}:{os.getenv('SCHEMA_REGISTRY_API_SECRET')}"
    }
    
    # Inicializa o Schema Registry
    schema_registry = SchemaRegistryClient(schema_registry_config)
    
    # Schema do pdf_download como string JSON
    schema_str = '''
    {
      "type": "record",
      "namespace": "co.techrom.poc_rag",
      "name": "pdf_download",
      "doc": "URL do PDF para download",
      "fields": [
        {
          "name": "url",
          "type": "string",
          "doc": "URL do documento PDF"
        }
      ]
    }
    '''
    
    # Cria o serializer Avro para o tópico pdf_download
    serializer = AvroSerializer(
        schema_registry,
        schema_str
    )
    
    # Inicializa o producer
    producer = Producer(kafka_config)
    
    # Publica cada URL
    for url in PDF_URLS:
        # Gera um UUID v4 para a key
        key = str(uuid.uuid4())
        
        # Prepara a mensagem
        message = {
            'url': url
        }
        
        # Serializa e publica a mensagem
        producer.produce(
            topic='pdf_download',
            key=key.encode('utf-8'),
            value=serializer(
                message,
                SerializationContext('pdf_download', MessageField.VALUE)
            ),
            callback=delivery_report
        )
        
        logger.info(f"URL publicada: {url}")
    
    # Aguarda todas as mensagens serem entregues
    producer.flush()
    logger.info("Todas as mensagens foram publicadas")

if __name__ == "__main__":
    main() 