import os
from typing import List
from pymilvus import connections, Collection
import logging
from dotenv import load_dotenv
from shared import KafkaConfig, KafkaTopics
from confluent_kafka.serialization import SerializationContext, MessageField

class DocumentRetriever:
    def __init__(self):
        self.logger = logging.getLogger(__name__)
        self.logger.info("Initializing DocumentRetriever...")
        load_dotenv()
        
        # Kafka configuration
        self.kafka_config = KafkaConfig()
        self.perguntas_topic = "perguntas_embeddings"
        self.documentos_topic = "documentos_selecionados"
        
        # Milvus configuration
        self.milvus_uri = os.getenv("MILVUS_URI")
        self.milvus_token = os.getenv("MILVUS_TOKEN")
        self.collection_name = os.getenv("MILVUS_COLLECTION", "pdf_embeddings")
        
        self.logger.debug(f"Milvus URI: {self.milvus_uri}")
        self.logger.debug(f"Milvus collection: {self.collection_name}")
        
        # Initialize components
        self._init_kafka_components()
        self._init_milvus()
        self.logger.info("DocumentRetriever initialized successfully")
        
    def _init_kafka_components(self):
        """Initialize Kafka components using shared configuration."""
        self.logger.info("Initializing Kafka components...")
        try:
            # Initialize Schema Registry
            self.schema_registry = self.kafka_config.create_schema_registry()
            
            # Initialize consumer
            self.consumer = self.kafka_config.create_consumer()
            self.consumer.subscribe([self.perguntas_topic])
            
            # Initialize producer
            self.producer = self.kafka_config.create_producer()
            
            # Initialize serializers/deserializers
            self.perguntas_deserializer = self.kafka_config.create_avro_deserializer(
                self.schema_registry,
                self.perguntas_topic
            )
            self.documentos_serializer = self.kafka_config.create_avro_serializer(
                self.schema_registry,
                self.documentos_topic
            )
            
            self.logger.info("Kafka components initialized successfully")
        except Exception as e:
            self.logger.error(f"Failed to initialize Kafka components: {str(e)}")
            raise
        
    def _init_milvus(self):
        """Initialize Milvus connection and collection."""
        self.logger.info("Initializing Milvus connection...")
        try:
            connections.connect(
                alias="default",
                uri=self.milvus_uri,
                token=self.milvus_token
            )
            self.collection = Collection(self.collection_name)
            self.logger.info(f"Connected to Milvus collection: {self.collection_name}")
        except Exception as e:
            self.logger.error(f"Failed to initialize Milvus connection: {str(e)}")
            raise
        
    def _get_similar_documents(self, query_embedding: List[float], k: int = 5) -> List[str]:
        """Retrieve k most similar documents from Milvus."""
        self.logger.info(f"Searching for similar documents using embedding vector")
        try:
            # TODO: Implement vector search logic here
            # This is a placeholder - you'll need to implement the actual vector search
            # based on your specific Milvus collection configuration
            results = self.collection.search(
                data=[query_embedding],  # Using the provided embedding vector
                anns_field="embedding",  # Using the correct field name from MilvusSink
                param={"metric_type": "L2", "params": {"nprobe": 10}},
                limit=k,
                output_fields=["text"]  # Adjust based on your collection schema
            )
            
            # Extract document texts from results
            documents = []
            for hits in results:
                for hit in hits:
                    documents.append(hit.entity.get('text'))
            
            self.logger.info(f"Found {len(documents)} similar documents")
            return documents
            
        except Exception as e:
            self.logger.error(f"Error retrieving similar documents: {str(e)}")
            return []
            
    def process_message(self, msg):
        """Process a single message from Kafka."""
        try:
            if msg is None:
                self.logger.debug("Received empty message, skipping...")
                return
                
            if msg.error():
                self.logger.error(f"Consumer error: {msg.error()}")
                return
                
            # Deserialize message
            self.logger.info(f"Received message from topic {msg.topic()}, partition {msg.partition()}, offset {msg.offset()}")
            perguntas_data = self.perguntas_deserializer(
                msg.value(),
                SerializationContext(msg.topic(), MessageField.VALUE)
            )
            self.logger.debug(f"Processing message for session: {perguntas_data['session_id']}")
            
            # Get similar documents
            documents = self._get_similar_documents(perguntas_data['embedding'])
            self.logger.info(f"Found {len(documents) if documents else 0} similar documents")
            
            # Prepare output message
            output_data = {
                'session_id': perguntas_data['session_id'],
                'pergunta': perguntas_data['pergunta'],
                'documentos': None if not documents else [doc if doc else None for doc in documents]
            }
            self.logger.info(f"Prepared output message: {output_data}")
            
            # Serialize and send message
            self.logger.info(f"Attempting to serialize message for topic {self.documentos_topic}")
            try:
                serialized_data = self.documentos_serializer(
                    output_data,
                    SerializationContext(self.documentos_topic, MessageField.VALUE)
                )
                self.logger.info("Message serialized successfully")
                
                self.logger.info(f"Attempting to produce message to topic {self.documentos_topic}")
                self.producer.produce(
                    topic=self.documentos_topic,
                    value=serialized_data,
                    callback=self.delivery_report
                )
                self.logger.info("Message produced successfully")
                
                # Poll to handle delivery reports
                self.producer.poll(0)
                
                self.logger.info("Flushing producer...")
                self.producer.flush()
                self.logger.info("Producer flushed successfully")
                
                self.logger.info(f"Response sent successfully for session: {perguntas_data['session_id']}")
            except Exception as e:
                self.logger.error(f"Error during message serialization/production: {str(e)}", exc_info=True)
                raise
            
        except Exception as e:
            self.logger.error(f"Error processing message: {str(e)}", exc_info=True)
            
    def delivery_report(self, err, msg):
        """Callback for message delivery reports"""
        if err is not None:
            self.logger.error(f"Message delivery failed: {err}")
        else:
            self.logger.info(f"Message delivered to {msg.topic()} [{msg.partition()}]")
            
    def run(self):
        """Main processing loop."""
        self.logger.info("Starting DocumentRetriever main loop...")
        try:
            while True:
                msg = self.consumer.poll(1.0)
                if msg is None:
                    continue
                if msg.error():
                    self.logger.error(f"Consumer error: {msg.error()}")
                    continue
                    
                self.process_message(msg)
                
        except KeyboardInterrupt:
            self.logger.info("Received shutdown signal. Shutting down DocumentRetriever...")
        except Exception as e:
            self.logger.error(f"Unexpected error in main loop: {str(e)}")
            raise
        finally:
            self.logger.info("Cleaning up resources...")
            self.consumer.close()
            self.producer.flush()
            connections.disconnect("default")
            self.logger.info("DocumentRetriever shutdown completed") 