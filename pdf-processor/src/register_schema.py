import os
import json
from dotenv import load_dotenv
from confluent_kafka.schema_registry import SchemaRegistryClient

# Carrega variáveis de ambiente
load_dotenv()

def register_schema():
    # Configurações do Schema Registry
    schema_registry_url = os.getenv('SCHEMA_REGISTRY_URL')
    schema_registry_key = os.getenv('SCHEMA_REGISTRY_API_KEY')
    schema_registry_secret = os.getenv('SCHEMA_REGISTRY_API_SECRET')

    # Configuração do Schema Registry
    schema_registry = SchemaRegistryClient({
        'url': schema_registry_url,
        'basic.auth.user.info': f"{schema_registry_key}:{schema_registry_secret}"
    })

    # Lê o schema do arquivo
    with open('src/schemas/pdf_completo.avsc', 'r') as f:
        schema_str = f.read()

    # Registra o schema
    try:
        schema = schema_registry.register_schema(
            subject_name="pdf_baixado-value",
            schema=schema_str,
            schema_type="AVRO"
        )
        print(f"Schema registrado com sucesso! ID: {schema.schema_id}")
    except Exception as e:
        print(f"Erro ao registrar schema: {str(e)}")

if __name__ == "__main__":
    register_schema() 