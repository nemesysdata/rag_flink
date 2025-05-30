import os
import requests
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Configurações
CLUSTER_ID = "lkc-roq6wp"  # ID do cluster Kafka
CONSUMER_GROUP = "pdf-processor-group-test"
TOPIC = "pdf_download"
API_KEY = os.getenv('KAFKA_API_KEY')
API_SECRET = os.getenv('KAFKA_API_SECRET')

# URL base da API REST
BASE_URL = f"https://pkc-619z3.us-east1.gcp.confluent.cloud/kafka/v3/clusters/{CLUSTER_ID}"

# Headers para autenticação
headers = {
    'Content-Type': 'application/json',
    'Authorization': f'Basic {API_KEY}:{API_SECRET}'
}

def reset_consumer_group_offsets():
    # Endpoint para resetar offsets
    url = f"{BASE_URL}/consumer-groups/{CONSUMER_GROUP}/offsets"
    
    # Dados para resetar para o início
    data = {
        "topic": TOPIC,
        "offset": 0,
        "partition": 0
    }
    
    try:
        # Fazer a requisição
        response = requests.post(url, headers=headers, json=data)
        
        # Verificar a resposta
        if response.status_code == 200:
            print("Offsets resetados com sucesso!")
            print(response.json())
        else:
            print(f"Erro ao resetar offsets: {response.status_code}")
            print(response.text)
            
    except Exception as e:
        print(f"Erro ao fazer a requisição: {str(e)}")

if __name__ == "__main__":
    reset_consumer_group_offsets() 