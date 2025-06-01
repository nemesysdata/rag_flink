import os
import json
import uuid
import time
from typing import Dict, Any, List
from confluent_kafka import KafkaError
from confluent_kafka.serialization import SerializationContext, MessageField
from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain_google_genai import ChatGoogleGenerativeAI
from loguru import logger

from shared import KafkaConfig, KafkaTopics

class ChunksProcessor:
    def __init__(self):
        # Configurações do Kafka
        self.kafka_config = KafkaConfig()
        self.topics = KafkaTopics.get_chunks_processor_topics()

        # Configuração do LangChain e Gemini
        self.setup_langchain()
        
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
            self._consumer.subscribe([self.topics["input"]])
            logger.info(f"Consumer Kafka inicializado e inscrito no tópico {self.topics['input']}")
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
                self.schema_registry, self.topics["input"]
            )
        return self._input_deserializer

    @property
    def pdf_chunk_serializer(self):
        if self._pdf_chunk_serializer is None:
            self._pdf_chunk_serializer = self.kafka_config.create_avro_serializer(
                self.schema_registry, self.topics["output"]
            )
        return self._pdf_chunk_serializer

    @property
    def string_serializer(self):
        if self._string_serializer is None:
            self._string_serializer = self.kafka_config.create_string_serializer()
        return self._string_serializer

    def setup_langchain(self) -> None:
        """Configura os componentes do LangChain para divisão de texto."""
        self.text_splitter = RecursiveCharacterTextSplitter(
            chunk_size=int(os.getenv('CHUNK_SIZE', '4096')),
            chunk_overlap=int(os.getenv('CHUNK_OVERLAP', '1024')),
            length_function=len,
            is_separator_regex=False
        )

        self.llm = ChatGoogleGenerativeAI(
            model="gemini-pro",
            google_api_key=os.getenv('GOOGLE_API_KEY'),
            temperature=0.7
        )

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

    def process_message(self, msg):
        """Processa uma mensagem recebida do Kafka."""
        try:
            if msg is None:
                logger.warning("Mensagem vazia recebida")
                return
                
            if msg.error():
                error = msg.error()
                logger.error(f"Erro na mensagem Kafka: {error}")
                logger.error(f"Detalhes do erro: código={error.code()}, nome={error.name()}, descrição={error.str()}")
                return

            logger.info(f"Processando mensagem do tópico {msg.topic()}, partição {msg.partition()}, offset {msg.offset()}")
            
            # Deserializa a mensagem usando o Schema Registry
            try:
                value = self.input_deserializer(msg.value(), SerializationContext(msg.topic(), MessageField.VALUE))
                logger.info(f"Conteúdo da mensagem: {json.dumps({k: v if k != 'text' else '[...texto omitido...]' for k, v in value.items()}, indent=2)}")
            except Exception as e:
                logger.error(f"Erro ao deserializar mensagem: {str(e)}")
                return

            # Processa o texto
            try:
                text = value.get('text')
                url = value.get('url')
                doc_id = value.get('id')
                
                if not text:
                    logger.error(f"Texto não encontrado na mensagem para URL: {url}")
                    return

                logger.info(f"Iniciando processamento de chunks para documento ID: {doc_id}, URL: {url}")
                chunks = self.split_text_into_chunks(text)
                
                if chunks:
                    logger.info(f"Texto dividido em {len(chunks)} chunks para documento ID: {doc_id}")
                    # Envia para o próximo tópico usando o serializer Avro
                    for i, chunk_text in enumerate(chunks):
                        chunk_message = {
                            'chunk_id': str(uuid.uuid4()),
                            'pdf_id': doc_id,
                            'chunk_text': chunk_text,
                            'chunk_index': i,
                            'total_chunks': len(chunks)
                        }
                        
                        self.producer.produce(
                            self.topics["output"],
                            key=chunk_message['chunk_id'].encode('utf-8'),
                            value=self.pdf_chunk_serializer(
                                chunk_message,
                                SerializationContext(self.topics["output"], MessageField.VALUE)
                            ),
                            callback=self.delivery_report
                        )
                        self.producer.poll(0)
                    
                    logger.info(f"Mensagens enviadas para o tópico {self.topics['output']}: {len(chunks)} chunks do documento ID: {doc_id}")
                else:
                    logger.error(f"Falha ao dividir texto em chunks para documento ID: {doc_id}")
                    
                # Commit do offset após processamento bem-sucedido
                self.consumer.commit(msg)
                logger.info(f"Offset {msg.offset()} commitado com sucesso")
                
            except Exception as e:
                logger.error(f"Erro ao processar chunks para documento ID {doc_id}: {str(e)}")
                # Envia erro para o tópico de erros usando o serializer de string
                self.producer.produce(
                    self.topics["error"],
                    self.string_serializer(json.dumps({
                        'doc_id': doc_id,
                        'url': url,
                        'error': str(e)
                    })),
                    callback=self.delivery_report
                )
                self.producer.poll(0)
                logger.info(f"Erro enviado para o tópico {self.topics['error']}: documento ID: {doc_id}")

        except Exception as e:
            logger.error(f"Erro ao processar mensagem: {str(e)}")
            logger.error(f"Detalhes da mensagem: tópico={msg.topic()}, partição={msg.partition()}, offset={msg.offset()}")

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
                try:
                    msg = self.consumer.poll(1.0)
                    if msg is None:
                        continue
                    self.process_message(msg)
                    self.producer.poll(0)
                except Exception as e:
                    logger.error(f"Erro ao processar mensagem: {str(e)}")
                    # Tenta reconectar ao Kafka
                    try:
                        self.consumer.close()
                        self._consumer = None
                        logger.info("Tentando reconectar ao Kafka...")
                        time.sleep(5)  # Espera 5 segundos antes de tentar novamente
                    except Exception as reconnect_error:
                        logger.error(f"Erro ao tentar reconectar: {str(reconnect_error)}")
                        time.sleep(10)  # Espera mais tempo se falhar
        except KeyboardInterrupt:
            logger.info("Encerrando processador de chunks...")
        finally:
            logger.info("Fechando conexões...")
            try:
                self.consumer.close()
                self.producer.flush()
                logger.info("Conexões fechadas com sucesso")
            except Exception as e:
                logger.error(f"Erro ao fechar conexões: {str(e)}") 