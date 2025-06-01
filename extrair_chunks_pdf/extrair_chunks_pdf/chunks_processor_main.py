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

def run_processor():
    """Executa o processador de chunks em um processo separado"""
    try:
        logger.info("Iniciando thread do processador Kafka...")
        processor = ChunksProcessor()
        logger.info("ChunksProcessor inicializado com sucesso")
        processor.run()
    except Exception as e:
        logger.error(f"Erro fatal na thread do processador Kafka: {str(e)}", exc_info=True)
        raise

class ChunksProcessor:
    def __init__(self):
        logger.info("Inicializando ChunksProcessor...")
        
        # Configurações do Kafka
        self.kafka_config = KafkaConfig()
        self.input_topic = os.getenv('KAFKA_INPUT_TOPIC')
        self.output_topic = os.getenv('KAFKA_OUTPUT_TOPIC')
        self.error_topic = os.getenv('KAFKA_ERROR_TOPIC')

        # Validação das configurações
        if not all([self.input_topic, self.output_topic, self.error_topic]):
            missing = [k for k, v in {
                'KAFKA_INPUT_TOPIC': self.input_topic,
                'KAFKA_OUTPUT_TOPIC': self.output_topic,
                'KAFKA_ERROR_TOPIC': self.error_topic
            }.items() if not v]
            raise ValueError(f"Configurações Kafka faltando: {', '.join(missing)}")

        logger.info(f"Configurações Kafka carregadas - Input Topic: {self.input_topic}, Output Topic: {self.output_topic}")

        # Configuração do LangChain e Gemini
        self.llm = ChatGoogleGenerativeAI(
            model="gemini-pro",
            google_api_key=os.getenv('GOOGLE_API_KEY'),
            temperature=0
        )
        
        # Configuração do Text Splitter
        self.text_splitter = RecursiveCharacterTextSplitter(
            chunk_size=1000,  # Tamanho padrão do chunk
            chunk_overlap=200,  # Overlap reduzido para ser menor que o chunk_size
            length_function=len,
            is_separator_regex=False
        )
        
        logger.info("Modelo Gemini e Text Splitter configurados")

        # Inicialização lazy
        self._schema_registry = None
        self._consumer = None
        self._producer = None
        self._input_deserializer = None
        self._pdf_chunk_serializer = None
        self._string_serializer = None

    @property
    def schema_registry(self):
        if self._schema_registry is None:
            self._schema_registry = self.kafka_config.create_schema_registry()
        return self._schema_registry

    @property
    def consumer(self):
        if self._consumer is None:
            self._consumer = self.kafka_config.create_consumer()
            self._consumer.subscribe([self.input_topic])
            logger.info(f"Consumer Kafka inicializado e inscrito no tópico {self.input_topic}")
        return self._consumer

    @property
    def producer(self):
        if self._producer is None:
            self._producer = self.kafka_config.create_producer()
        return self._producer

    @property
    def input_deserializer(self):
        if self._input_deserializer is None:
            self._input_deserializer = self.kafka_config.create_avro_deserializer(
                self.schema_registry, self.input_topic
            )
        return self._input_deserializer

    @property
    def pdf_chunk_serializer(self):
        if self._pdf_chunk_serializer is None:
            self._pdf_chunk_serializer = self.kafka_config.create_avro_serializer(
                self.schema_registry, "pdf_chunks"
            )
        return self._pdf_chunk_serializer

    @property
    def string_serializer(self):
        if self._string_serializer is None:
            self._string_serializer = self.kafka_config.create_string_serializer()
        return self._string_serializer

    def split_text_into_chunks(self, text: str) -> List[str]:
        """Divide o texto em chunks usando o LangChain"""
        try:
            logger.info(f"Iniciando divisão do texto em chunks. Tamanho do texto: {len(text)} caracteres")
            
            # Usa o LangChain para dividir o texto
            chunks = self.text_splitter.split_text(text)
            
            logger.info(f"Texto dividido em {len(chunks)} chunks com sucesso")
            for i, chunk in enumerate(chunks, 1):
                logger.debug(f"Chunk {i}: {len(chunk)} caracteres")
            
            return chunks
        except Exception as e:
            logger.error(f"Erro ao dividir texto em chunks: {str(e)}")
            raise

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
                logger.info(f"Nova mensagem recebida do tópico {msg.topic()}")
                logger.debug(f"Conteúdo da mensagem: {value}")
            except Exception as e:
                logger.error(f"Erro ao deserializar mensagem: {str(e)}")
                return

            if not value or 'id' not in value or 'text' not in value:
                logger.error("Mensagem inválida: id ou text não encontrados")
                return

            pdf_id = value['id']
            text = value['text']
            logger.info(f"Iniciando processamento do PDF ID: {pdf_id}")

            # Divide o texto em chunks
            chunks = self.split_text_into_chunks(text)
            logger.info(f"PDF ID {pdf_id}: Texto dividido em {len(chunks)} chunks")

            # Processa cada chunk
            chunks_processados = 0
            for chunk_text in chunks:
                chunk_id = str(uuid.uuid4())
                
                # Cria a mensagem para o tópico de chunks
                chunk_message = {
                    'chunk_id': chunk_id,
                    'pdf_id': pdf_id,
                    'chunk_text': chunk_text
                }

                # Serializa e envia a mensagem
                try:
                    self.producer.produce(
                        topic=self.output_topic,
                        key=chunk_id,
                        value=self.pdf_chunk_serializer(
                            chunk_message,
                            SerializationContext(self.output_topic, MessageField.VALUE)
                        ),
                        on_delivery=self.delivery_report
                    )
                    chunks_processados += 1
                    logger.debug(f"Chunk {chunk_id} enviado com sucesso")
                except Exception as e:
                    logger.error(f"Erro ao enviar chunk {chunk_id}: {str(e)}")
                    # Envia para o tópico de erro
                    error_message = {
                        'error': str(e),
                        'original_message': chunk_message
                    }
                    self.producer.produce(
                        topic=self.error_topic,
                        value=self.string_serializer(json.dumps(error_message)),
                        on_delivery=self.delivery_report
                    )

            # Commit da mensagem original
            self.consumer.commit(msg)
            logger.info(f"PDF ID {pdf_id}: Processamento concluído. {chunks_processados} chunks processados com sucesso")

        except Exception as e:
            logger.error(f"Erro ao processar mensagem: {str(e)}")
            # Envia para o tópico de erro
            error_message = {
                'error': str(e),
                'original_message': value
            }
            self.producer.produce(
                topic=self.error_topic,
                value=self.string_serializer(json.dumps(error_message)),
                on_delivery=self.delivery_report
            )

    def delivery_report(self, err, msg):
        """Callback para relatório de entrega de mensagens"""
        if err is not None:
            logger.error(f"Falha na entrega da mensagem: {err}")
        else:
            logger.debug(f"Mensagem entregue: {msg.topic()} [{msg.partition()}]")

    def run(self):
        """Executa o processador de chunks"""
        logger.info("Iniciando processador de chunks...")
        try:
            while True:
                msg = self.consumer.poll(1.0)
                if msg is None:
                    continue
                self.process_message(msg)
                self.producer.poll(0)
        except KeyboardInterrupt:
            logger.info("Encerrando processador de chunks...")
        finally:
            logger.info("Fechando conexões...")
            self.consumer.close()
            self.producer.flush()
            logger.info("Conexões fechadas")

if __name__ == "__main__":
    # Inicia o processador Kafka em uma thread separada
    kafka_thread = threading.Thread(target=run_processor, daemon=True)
    kafka_thread.start() 