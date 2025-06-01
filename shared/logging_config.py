"""
Configuração do sistema de logs usando loguru.
"""
import sys
from loguru import logger

def setup_logging():
    """
    Configura o sistema de logs usando loguru.
    Configura o formato, nível e saída dos logs.
    """
    # Remove o handler padrão
    logger.remove()

    # Adiciona o handler para stdout com formato personalizado
    logger.add(
        sys.stdout,
        format="<green>{time:YYYY-MM-DD HH:mm:ss.SSS}</green> | <level>{level: <8}</level> | <cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> - <level>{message}</level>",
        level="INFO",
        colorize=True
    )

    # Adiciona o handler para arquivo com formato detalhado
    logger.add(
        "logs/app.log",
        rotation="500 MB",  # Rotaciona o arquivo quando atingir 500MB
        retention="10 days",  # Mantém os logs por 10 dias
        compression="zip",  # Comprime os arquivos antigos
        format="{time:YYYY-MM-DD HH:mm:ss.SSS} | {level: <8} | {name}:{function}:{line} - {message}",
        level="DEBUG",
        encoding="utf-8"
    )

    # Adiciona o handler para arquivo de erros
    logger.add(
        "logs/error.log",
        rotation="100 MB",
        retention="30 days",
        compression="zip",
        format="{time:YYYY-MM-DD HH:mm:ss.SSS} | {level: <8} | {name}:{function}:{line} - {message}",
        level="ERROR",
        encoding="utf-8"
    )

    return logger 