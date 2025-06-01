import os
from dotenv import load_dotenv
from loguru import logger

def check_environment():
    """Verifica e configura as variáveis de ambiente necessárias."""
    # Carrega variáveis do .env se existir
    load_dotenv()
    
    # Lista de variáveis necessárias
    required_vars = {
        'KAFKA_BOOTSTRAP_SERVERS': 'Servidor Kafka',
        'KAFKA_API_KEY': 'API Key do Kafka',
        'KAFKA_API_SECRET': 'API Secret do Kafka',
        'KAFKA_CONSUMER_GROUP': 'Grupo de consumidores',
        'SCHEMA_REGISTRY_URL': 'URL do Schema Registry',
        'SCHEMA_REGISTRY_API_KEY': 'API Key do Schema Registry',
        'SCHEMA_REGISTRY_API_SECRET': 'API Secret do Schema Registry',
        'GOOGLE_API_KEY': 'API Key do Google'
    }
    
    # Verifica cada variável
    missing_vars = []
    for var, description in required_vars.items():
        if not os.getenv(var):
            missing_vars.append(f"{var} ({description})")
    
    if missing_vars:
        logger.error("Variáveis de ambiente faltando:")
        for var in missing_vars:
            logger.error(f"- {var}")
        return False
    
    logger.info("Todas as variáveis de ambiente estão configuradas!")
    return True

if __name__ == "__main__":
    check_environment() 