import os
from typing import List
from pymilvus import connections, Collection
import logging
from dotenv import load_dotenv
from shared import KafkaConfig, KafkaTopics

class DocumentRetriever:
    def __init__(self):
        self.logger = logging.getLogger(__name__)
        self.logger.info("Initializing DocumentRetriever...")
        load_dotenv()
        
        # Kafka configuration
        self.kafka_config = KafkaConfig()
        self.perguntas_topic = "perguntas"
        self.documentos_topic = "documentos_selecionados"
        
        # Milvus configuration
        self.milvus_uri = os.getenv("MILVUS_URI")
        self.milvus_token = os.getenv("MILVUS_TOKEN")
        self.collection_name = os.getenv("MILVUS_COLLECTION_NAME")
        
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
        
    def _get_similar_documents(self, query_text: str, k: int = 5) -> List[str]:
        """Retrieve k most similar documents from Milvus."""
        self.logger.debug(f"Searching for similar documents to query: {query_text}")
        try:
            # TODO: Implement vector search logic here
            # This is a placeholder - you'll need to implement the actual vector search
            # based on your specific Milvus collection configuration
            results = self.collection.search(
                data=[query_text],  # This needs to be properly vectorized
                anns_field="vector",  # Adjust based on your collection schema
                param={"metric_type": "L2", "params": {"nprobe": 10}},
                limit=k,
                output_fields=["text"]  # Adjust based on your collection schema
            )
            
            # Extract document texts from results
            documents = []
            for hits in results:
                for hit in hits:
                    documents.append(hit.entity.get('text'))
            
            self.logger.debug(f"Found {len(documents)} similar documents")
            return documents
            
        except Exception as e:
            self.logger.error(f"Error retrieving similar documents: {str(e)}")
            return []
            
    def process_message(self, msg):
        """Process a single message from Kafka."""
        try:
            # Deserialize message
            self.logger.debug("Deserializing message")
            perguntas_data = self.perguntas_deserializer(msg.value())
            self.logger.debug(f"Processing message for session: {perguntas_data['session_id']}")
            
            # Get similar documents
            documents = self._get_similar_documents(perguntas_data['pergunta'])
            
            # Prepare output message
            output_data = {
                'session_id': perguntas_data['session_id'],
                'pergunta': perguntas_data['pergunta'],
                'documentos': documents if documents else None
            }
            
            # Serialize and send message
            self.logger.debug(f"Sending response for session: {perguntas_data['session_id']}")
            serialized_data = self.documentos_serializer(output_data)
            self.producer.produce(
                topic=self.documentos_topic,
                value=serialized_data
            )
            self.producer.flush()
            self.logger.debug(f"Response sent successfully for session: {perguntas_data['session_id']}")
            
        except Exception as e:
            self.logger.error(f"Error processing message: {str(e)}")
            
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