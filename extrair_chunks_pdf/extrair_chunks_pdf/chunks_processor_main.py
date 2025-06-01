import os
import json
import logging
import uuid
import threading
from typing import Dict, Any, List
from dotenv import load_dotenv
from confluent_kafka import Consumer, Producer, KafkaError
from confluent_kafka.schema_registry import SchemaRegistryClient
from confluent_kafka.schema_registry.avro import AvroSerializer, AvroDeserializer
from confluent_kafka.serialization import StringSerializer, SerializationContext, MessageField
from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain_google_genai import ChatGoogleGenerativeAI

from shared import KafkaConfig, setup_logging

# Configuração de logging
setup_logging()
logger = logging.getLogger(__name__)

# Carrega variáveis de ambiente
load_dotenv()

class ChunksProcessor:
    """Processador de chunks que divide textos em partes menores.
    
    Esta classe é responsável por:
    - Consumir textos do tópico Kafka
    - Dividir em chunks usando LangChain
    - Publicar os chunks em outro tópico
    """

    def __init__(self):
        """Inicializa o processador com configurações do Kafka e LangChain."""
        self.kafka_config = {
            'bootstrap.servers': os.getenv('KAFKA_BOOTSTRAP_SERVERS'),
            'security.protocol': 'SASL_SSL',
            'sasl.mechanisms': 'PLAIN',
            'sasl.username': os.getenv('KAFKA_API_KEY'),
            'sasl.password': os.getenv('KAFKA_API_SECRET'),
            'group.id': os.getenv('KAFKA_CONSUMER_GROUP', 'extrair-chunks-pdf-group'),
            'auto.offset.reset': 'earliest'
        }

        self.schema_registry_config = {
            'url': os.getenv('SCHEMA_REGISTRY_URL'),
            'basic.auth.user.info': f"{os.getenv('SCHEMA_REGISTRY_API_KEY')}:{os.getenv('SCHEMA_REGISTRY_API_SECRET')}"
        }

        self.schema_registry_client = SchemaRegistryClient(self.schema_registry_config)
        self.setup_serializers()
        self.setup_langchain()

    def setup_serializers(self) -> None:
        """Configura os serializadores Avro para os tópicos de entrada e saída."""
        # Serializador para o tópico de entrada (pdf_baixado)
        self.input_serializer = AvroDeserializer(
            self.schema_registry_client,
            "co.techrom.poc_rag.pdf_completo"
        )

        # Serializador para o tópico de saída (pdf_chunks)
        self.output_serializer = AvroSerializer(
            self.schema_registry_client,
            "co.techrom.poc_rag.pdf_chunk"
        )

    def setup_langchain(self) -> None:
        """Configura os componentes do LangChain para divisão de texto."""
        self.text_splitter = RecursiveCharacterTextSplitter(
            chunk_size=1000,
            chunk_overlap=200,
            length_function=len,
            is_separator_regex=False
        )

        self.llm = ChatGoogleGenerativeAI(
            model="gemini-pro",
            google_api_key=os.getenv('GOOGLE_API_KEY'),
            temperature=0.7
        )

    def split_text(self, text: str) -> List[str]:
        """Divide um texto em chunks menores.
        
        Args:
            text: Texto a ser dividido em chunks.
            
        Returns:
            List[str]: Lista de chunks de texto.
        """
        return self.text_splitter.split_text(text)

    def process_message(self, msg: Any) -> None:
        """Processa uma mensagem do Kafka contendo texto para dividir em chunks.
        
        Args:
            msg: Mensagem do Kafka com o texto a ser processado.
            
        Raises:
            Exception: Se houver erro no processamento da mensagem.
        """
        try:
            # Deserializa a mensagem
            value = self.input_serializer(msg.value(), SerializationContext(msg.topic(), MessageField.VALUE))
            
            if value is None:
                return

            pdf_id = value.get('id')
            text = value.get('text')
            
            if not pdf_id or not text:
                logger.warning("ID ou texto não encontrados na mensagem")
                return

            # Divide o texto em chunks
            chunks = self.split_text(text)
            total_chunks = len(chunks)

            # Publica cada chunk
            producer = Producer(self.kafka_config)
            
            for index, chunk_text in enumerate(chunks):
                chunk_id = str(uuid.uuid4())
                
                # Prepara a mensagem de saída
                output_message = {
                    'chunk_id': chunk_id,
                    'pdf_id': pdf_id,
                    'chunk_text': chunk_text,
                    'chunk_index': index,
                    'total_chunks': total_chunks
                }

                # Serializa e publica a mensagem
                serialized_value = self.output_serializer(
                    output_message,
                    SerializationContext("pdf_chunks", MessageField.VALUE)
                )

                producer.produce(
                    topic="pdf_chunks",
                    value=serialized_value,
                    callback=self.delivery_report
                )

            producer.flush()
            logger.info(f"PDF {pdf_id} dividido em {total_chunks} chunks")

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
            consumer.subscribe(["pdf_baixado"])

            logger.info("Iniciando processador de chunks...")
            
            while True:
                msg = consumer.poll(1.0)
                if msg is None:
                    continue
                if msg.error():
                    logger.error(f"Erro do consumidor: {msg.error()}")
                    continue
                    
                self.process_message(msg)

        except KeyboardInterrupt:
            logger.info("Encerrando processador de chunks...")
        except Exception as e:
            logger.error(f"Erro fatal no processador: {str(e)}")
            raise
        finally:
            if 'consumer' in locals():
                consumer.close()

def run_processor():
    """Inicia o processador de chunks em um processo separado."""
    try:
        logger.info("Iniciando thread do processador Kafka...")
        processor = ChunksProcessor()
        logger.info("ChunksProcessor inicializado com sucesso")
        processor.run()
    except Exception as e:
        logger.error(f"Erro fatal na thread do processador Kafka: {str(e)}", exc_info=True)
        raise

if __name__ == "__main__":
    run_processor() 