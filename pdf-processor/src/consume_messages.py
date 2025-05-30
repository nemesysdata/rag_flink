import os
from confluent_kafka import Consumer
from dotenv import load_dotenv
import json

# Load environment variables
load_dotenv()

# Configuração do Consumer
consumer_conf = {
    'bootstrap.servers': os.getenv('KAFKA_BOOTSTRAP_SERVERS'),
    'security.protocol': 'SASL_SSL',
    'sasl.mechanisms': 'PLAIN',
    'sasl.username': os.getenv('KAFKA_API_KEY'),
    'sasl.password': os.getenv('KAFKA_API_SECRET'),
    'group.id': 'test-consumer-group',
    'auto.offset.reset': 'earliest',
    'enable.auto.commit': 'false'
}

# Criar instância do Consumer
consumer = Consumer(consumer_conf)

# Inscrever no tópico
consumer.subscribe(['pdf_download'])

print("Starting consumer...")
print(f"Consumer group: {consumer_conf['group.id']}")
print(f"Topic: pdf_download")

try:
    while True:
        msg = consumer.poll(1.0)
        
        if msg is None:
            print("No message received")
            continue
        
        if msg.error():
            print(f"Consumer error: {msg.error()}")
            continue
        
        print(f"\nReceived message at partition {msg.partition()}, offset {msg.offset()}")
        print(f"Message value: {msg.value().decode('utf-8')}")
        
        # Commit da mensagem
        consumer.commit(msg)
        
except KeyboardInterrupt:
    print("\nStopping consumer...")
finally:
    consumer.close() 