"""
Milvus Sink Service
"""
import os
import json
import time
import logging
import uuid
from typing import Dict, Any
from pymilvus import connections, Collection, FieldSchema, CollectionSchema, DataType, utility
from confluent_kafka.serialization import SerializationContext, MessageField
from shared.kafka_config import KafkaConfig
from shared.logging_config import setup_logging

setup_logging()
logger = logging.getLogger(__name__)

class MilvusSink:
    """Serviço para persistir embeddings no Milvus"""
    
    def __init__(self):
        """Inicializa o serviço MilvusSink"""
        self.kafka_config = KafkaConfig()
        self.consumer = self.kafka_config.create_consumer()
        self.producer = self.kafka_config.create_producer()
        
        # Configuração do Schema Registry
        self.schema_registry = self.kafka_config.create_schema_registry()
        self.input_deserializer = self.kafka_config.create_avro_deserializer(
            self.schema_registry, "pdf_embedding"
        )
        
        # Inscreve no tópico de embeddings
        self.consumer.subscribe(["pdf_embedding"])
        logger.info("Consumer Kafka inicializado e inscrito no tópico pdf_embedding")
        
        # Configurações do Milvus
        self.uri = os.getenv("MILVUS_URI")
        self.token = os.getenv("MILVUS_TOKEN")
        self.collection_name = os.getenv("MILVUS_COLLECTION", "pdf_embeddings")
        self.dim = int(os.getenv("MILVUS_DIM", "1536"))
        
        # Conecta ao Milvus
        self._connect_milvus()
        
        # Cria ou obtém a coleção
        self._setup_collection()
    
    def _connect_milvus(self):
        """Conecta ao Milvus Cloud"""
        try:
            connections.connect(
                alias="default",
                uri=self.uri,
                token=self.token,
                secure=True  # Habilita conexão segura para Zilliz Cloud
            )
            logger.info("Conectado ao Milvus Cloud com sucesso")
        except Exception as e:
            logger.error(f"Erro ao conectar ao Milvus: {str(e)}")
            raise
    
    def _setup_collection(self):
        """Configura a coleção no Milvus"""
        try:
            if utility.has_collection(self.collection_name):
                self.collection = Collection(self.collection_name)
                logger.info(f"Coleção {self.collection_name} já existe")
            else:
                # Define o schema da coleção
                fields = [
                    FieldSchema(name="id", dtype=DataType.INT64, is_primary=True, auto_id=True),
                    FieldSchema(name="chunk_id", dtype=DataType.VARCHAR, max_length=100),
                    FieldSchema(name="text", dtype=DataType.VARCHAR, max_length=65535),
                    FieldSchema(name="embedding", dtype=DataType.FLOAT_VECTOR, dim=self.dim)
                ]
                schema = CollectionSchema(fields=fields, description="PDF Embeddings Collection")
                
                # Cria a coleção
                self.collection = Collection(name=self.collection_name, schema=schema)
                
                # Cria índice para busca por similaridade
                index_params = {
                    "metric_type": "L2",
                    "index_type": "IVF_FLAT",
                    "params": {"nlist": 1024}
                }
                self.collection.create_index(field_name="embedding", index_params=index_params)
                logger.info(f"Coleção {self.collection_name} criada com sucesso")
        except Exception as e:
            logger.error(f"Erro ao configurar coleção: {str(e)}")
            raise
    
    def process_message(self, msg):
        """Processa uma mensagem do Kafka"""
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
                logger.info("Mensagem deserializada com sucesso")
            except Exception as e:
                logger.error(f"Erro ao deserializar mensagem: {str(e)}")
                return
            
            # Extrai os dados
            chunk_text = value.get("chunk_text")
            embedding = value.get("embedding")
            
            if not chunk_text:
                logger.error("Campo chunk_text não encontrado na mensagem")
                return
                
            if not embedding:
                logger.error("Campo embedding não encontrado na mensagem")
                return
            
            # Prepara os dados para inserção
            chunk_id = str(uuid.uuid4())
            data = {
                "chunk_id": chunk_id,
                "text": chunk_text,
                "embedding": embedding
            }
            
            # Insere no Milvus
            self.collection.insert([data])
            logger.info(f"Embedding persistido com sucesso: Chunk ID {chunk_id}")
            
            # Commit do offset após processamento bem-sucedido
            self.consumer.commit(msg)
            logger.info(f"Offset {msg.offset()} commitado com sucesso")
            
        except Exception as e:
            logger.error(f"Erro ao processar mensagem: {str(e)}")
    
    def run(self):
        """Executa o serviço"""
        logger.info("Iniciando MilvusSink...")
        try:
            while True:
                try:
                    msg = self.consumer.poll(1.0)
                    if msg is None:
                        continue
                    self.process_message(msg)
                except Exception as e:
                    logger.error(f"Erro ao processar mensagem: {str(e)}")
                    # Tenta reconectar ao Milvus
                    try:
                        self._connect_milvus()
                        self._setup_collection()
                        logger.info("Reconectado ao Milvus com sucesso")
                    except Exception as reconnect_error:
                        logger.error(f"Erro ao reconectar: {str(reconnect_error)}")
                        time.sleep(5)  # Espera 5 segundos antes de tentar novamente
        except KeyboardInterrupt:
            logger.info("Encerrando MilvusSink...")
        finally:
            logger.info("Fechando conexões...")
            try:
                self.consumer.close()
                self.producer.flush()
                connections.disconnect("default")
                logger.info("Conexões fechadas com sucesso")
            except Exception as e:
                logger.error(f"Erro ao fechar conexões: {str(e)}") 