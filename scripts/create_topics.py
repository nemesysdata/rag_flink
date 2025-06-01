from confluent_kafka.admin import AdminClient, NewTopic
from loguru import logger
import os
from dotenv import load_dotenv

load_dotenv()

def create_kafka_topics():
    """Cria os tópicos necessários no Kafka."""
    # Configuração do AdminClient
    config = {
        'bootstrap.servers': os.getenv('KAFKA_BOOTSTRAP_SERVERS'),
        'security.protocol': 'SASL_SSL',
        'sasl.mechanisms': 'PLAIN',
        'sasl.username': os.getenv('KAFKA_API_KEY'),
        'sasl.password': os.getenv('KAFKA_API_SECRET')
    }

    # Lista de tópicos a serem criados
    topics = [
        NewTopic('pdf_download', num_partitions=3, replication_factor=3),
        NewTopic('pdf_baixado', num_partitions=3, replication_factor=3),
        NewTopic('pdf_chunks', num_partitions=3, replication_factor=3),
        NewTopic('pdf_errors', num_partitions=3, replication_factor=3)
    ]

    try:
        # Cria o AdminClient
        admin_client = AdminClient(config)
        
        # Cria os tópicos
        result = admin_client.create_topics(topics)
        
        # Aguarda a conclusão da criação dos tópicos
        for topic, future in result.items():
            try:
                future.result()  # Aguarda a conclusão
                logger.info(f"Tópico {topic} criado com sucesso")
            except Exception as e:
                logger.error(f"Erro ao criar tópico {topic}: {str(e)}")
                
    except Exception as e:
        logger.error(f"Erro ao conectar ao Kafka: {str(e)}")
        raise

if __name__ == "__main__":
    create_kafka_topics() 