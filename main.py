import os
import threading
from dotenv import load_dotenv
import uvicorn

# Carrega as variáveis de ambiente
load_dotenv()

from shared import setup_logging
from pdf_processor.pdf_processor.pdf_processor import PDFProcessor
from extrair_chunks_pdf.extrair_chunks_pdf.chunks_processor import ChunksProcessor
from api_server import app

def run_pdf_processor() -> None:
    """Inicia o processador de PDFs em uma thread separada.
    
    O processador monitora o tópico 'pdf_download' para URLs de PDFs,
    faz o download e extrai o texto dos documentos.
    """
    processor = PDFProcessor()
    processor.run()

def run_chunks_processor() -> None:
    """Inicia o processador de chunks em uma thread separada.
    
    O processador monitora o tópico 'pdf_baixado' para textos extraídos,
    divide em chunks e publica no tópico 'pdf_chunks'.
    """
    processor = ChunksProcessor()
    processor.run()

def run_fastapi() -> None:
    """Inicia o servidor FastAPI em uma thread separada.
    
    O servidor fornece endpoints de health check e monitoramento
    para todos os serviços da aplicação.
    """
    uvicorn.run(
        app,
        host="0.0.0.0",
        port=8080,
        log_level="info"
    )

def main() -> None:
    """Função principal que inicializa e coordena todos os serviços.
    
    Inicia três threads separadas:
    - Processador de PDFs
    - Processador de chunks
    - Servidor FastAPI
    
    Gerencia o ciclo de vida das threads e tratamento de exceções.
    """
    # Configura o logging
    logger = setup_logging()
    logger.info("Iniciando aplicação...")

    # Cria o diretório de logs se não existir
    os.makedirs("logs", exist_ok=True)

    # Inicia os processadores em threads separadas
    pdf_thread = threading.Thread(target=run_pdf_processor, name="PDFProcessor")
    chunks_thread = threading.Thread(target=run_chunks_processor, name="ChunksProcessor")
    api_thread = threading.Thread(target=run_fastapi, name="FastAPI")

    try:
        logger.info("Iniciando processadores e API...")
        pdf_thread.start()
        chunks_thread.start()
        api_thread.start()

        # Aguarda as threads terminarem
        pdf_thread.join()
        chunks_thread.join()
        api_thread.join()

    except KeyboardInterrupt:
        logger.info("Encerrando aplicação...")
    except Exception as e:
        logger.error(f"Erro ao executar aplicação: {str(e)}")
        raise

if __name__ == "__main__":
    main() 