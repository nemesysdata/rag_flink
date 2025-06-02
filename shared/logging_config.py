"""
Configuração do sistema de logs usando loguru.
"""
import logging
import sys
from dotenv import load_dotenv

load_dotenv()

def setup_logging():
    """Configura o logging da aplicação"""
    logging.basicConfig(
        level=logging.INFO,  # Alterado de DEBUG para INFO
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[
            logging.StreamHandler(sys.stdout)
        ]
    )
    logging.info("Logging configurado com sucesso")
    
    return logging.getLogger(__name__) 