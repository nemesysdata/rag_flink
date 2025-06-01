import os
import logging
import uuid
from typing import Dict, Any
from confluent_kafka import Consumer, Producer
from confluent_kafka.schema_registry import SchemaRegistryClient
from confluent_kafka.schema_registry.avro import AvroSerializer, AvroDeserializer
from confluent_kafka.serialization import StringSerializer, SerializationContext, MessageField

logger = logging.getLogger(__name__)

class KafkaConfig:
    def __init__(self):
        # Configurações do Kafka
        self.bootstrap_servers = os.getenv('KAFKA_BOOTSTRAP_SERVERS')
        self.api_key = os.getenv('KAFKA_API_KEY')
        self.api_secret = os.getenv('KAFKA_API_SECRET')
        self.consumer_group = os.getenv('KAFKA_CONSUMER_GROUP')

        # Configurações do Schema Registry
        self.schema_registry_url = os.getenv('SCHEMA_REGISTRY_URL')
        self.schema_registry_key = os.getenv('SCHEMA_REGISTRY_API_KEY')
        self.schema_registry_secret = os.getenv('SCHEMA_REGISTRY_API_SECRET')

        # Validação das configurações
        self._validate_config()

    def _validate_config(self):
        """Valida as configurações necessárias"""
        if not all([self.bootstrap_servers, self.api_key, self.api_secret, self.consumer_group]):
            missing = [k for k, v in {
                'KAFKA_BOOTSTRAP_SERVERS': self.bootstrap_servers,
                'KAFKA_API_KEY': self.api_key,
                'KAFKA_API_SECRET': self.api_secret,
                'KAFKA_CONSUMER_GROUP': self.consumer_group
            }.items() if not v]
            raise ValueError(f"Configurações Kafka faltando: {', '.join(missing)}")

        if not all([self.schema_registry_url, self.schema_registry_key, self.schema_registry_secret]):
            missing = [k for k, v in {
                'SCHEMA_REGISTRY_URL': self.schema_registry_url,
                'SCHEMA_REGISTRY_API_KEY': self.schema_registry_key,
                'SCHEMA_REGISTRY_API_SECRET': self.schema_registry_secret
            }.items() if not v]
            raise ValueError(f"Configurações Schema Registry faltando: {', '.join(missing)}")

    def get_kafka_config(self) -> Dict[str, Any]:
        """Retorna a configuração do Kafka com credenciais."""
        return {
            'bootstrap.servers': self.bootstrap_servers,
            'security.protocol': 'SASL_SSL',
            'sasl.mechanisms': 'PLAIN',
            'sasl.username': self.api_key,
            'sasl.password': self.api_secret,
            'group.id': self.consumer_group,
            'auto.offset.reset': os.getenv('KAFKA_AUTO_OFFSET_RESET', 'latest'),
            'enable.auto.commit': False,
            'client.id': f'kafka-client-{uuid.uuid4()}',
            'debug': 'all'
        }

    def get_consumer_config(self) -> Dict[str, Any]:
        """Retorna a configuração do consumer"""
        return {
            'bootstrap.servers': self.bootstrap_servers,
            'security.protocol': 'SASL_SSL',
            'sasl.mechanisms': 'PLAIN',
            'sasl.username': self.api_key,
            'sasl.password': self.api_secret,
            'group.id': self.consumer_group,
            'auto.offset.reset': os.getenv('KAFKA_AUTO_OFFSET_RESET', 'latest'),
            'enable.auto.commit': True,
            'auto.commit.interval.ms': 5000,  # Commit a cada 5 segundos
            'client.id': f'kafka-client-{uuid.uuid4()}',
            'heartbeat.interval.ms': 3000,  # Envia heartbeat a cada 3 segundos
            'session.timeout.ms': 10000  # Timeout de 10 segundos
        }

    def get_producer_config(self) -> Dict[str, Any]:
        """Retorna a configuração do producer"""
        return {
            'bootstrap.servers': self.bootstrap_servers,
            'security.protocol': 'SASL_SSL',
            'sasl.mechanisms': 'PLAIN',
            'sasl.username': self.api_key,
            'sasl.password': self.api_secret,
            'queue.buffering.max.messages': 100000,
            'queue.buffering.max.ms': 100,
            'batch.num.messages': 10000
        }

    def get_schema_registry_config(self) -> Dict[str, Any]:
        """Retorna a configuração do Schema Registry"""
        return {
            'url': self.schema_registry_url,
            'basic.auth.user.info': f"{self.schema_registry_key}:{self.schema_registry_secret}"
        }

    def create_consumer(self) -> Consumer:
        """Cria e retorna um consumer Kafka"""
        logger.debug("Inicializando Consumer Kafka...")
        consumer = Consumer(self.get_consumer_config())
        logger.info("Consumer Kafka inicializado")
        return consumer

    def create_producer(self) -> Producer:
        """Cria e retorna um producer Kafka"""
        logger.debug("Inicializando Producer Kafka...")
        producer = Producer(self.get_producer_config())
        logger.info("Producer Kafka inicializado")
        return producer

    def create_schema_registry(self) -> SchemaRegistryClient:
        """Cria e retorna um cliente do Schema Registry"""
        logger.debug("Inicializando Schema Registry...")
        schema_registry = SchemaRegistryClient(self.get_schema_registry_config())
        logger.info("Schema Registry inicializado")
        return schema_registry

    def create_avro_serializer(self, schema_registry: SchemaRegistryClient, topic: str) -> AvroSerializer:
        """Cria e retorna um serializer Avro"""
        logger.debug(f"Inicializando serializer Avro para tópico {topic}...")
        schema = schema_registry.get_latest_version(f"{topic}-value").schema
        serializer = AvroSerializer(schema_registry, schema)
        logger.info(f"Serializer Avro inicializado para tópico {topic}")
        return serializer

    def create_avro_deserializer(self, schema_registry: SchemaRegistryClient, topic: str) -> AvroDeserializer:
        """Cria e retorna um deserializer Avro"""
        logger.debug(f"Inicializando deserializer Avro para tópico {topic}...")
        schema = schema_registry.get_latest_version(f"{topic}-value").schema
        deserializer = AvroDeserializer(schema_registry, schema)
        logger.info(f"Deserializer Avro inicializado para tópico {topic}")
        return deserializer

    def create_string_serializer(self) -> StringSerializer:
        """Cria e retorna um serializer de string"""
        logger.debug("Inicializando serializer de string...")
        serializer = StringSerializer('utf_8')
        logger.info("Serializer de string inicializado")
        return serializer 