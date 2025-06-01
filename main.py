import os
import logging
import multiprocessing
from dotenv import load_dotenv
from pdf_processor.pdf_processor.pdf_processor import PDFProcessor
from extrair_chunks_pdf.extrair_chunks_pdf.chunks_processor import ChunksProcessor
from api_server import app
import uvicorn
from shared import setup_logging

# Configuração de logging
logger = setup_logging()

# Carrega variáveis de ambiente
load_dotenv()

def run_api():
    """Executa o servidor FastAPI."""
    uvicorn.run(app, host="0.0.0.0", port=8080)

def run_pdf_processor():
    """Executa o processador de PDFs."""
    processor = PDFProcessor()
    processor.run()

def run_chunks_processor():
    """Executa o processador de chunks."""
    processor = ChunksProcessor()
    processor.run()

def main():
    """Função principal que inicia todos os processos."""
    try:
        logger.info("Iniciando aplicação...")
        
        # Cria os processos
        api_process = multiprocessing.Process(target=run_api)
        pdf_process = multiprocessing.Process(target=run_pdf_processor)
        chunks_process = multiprocessing.Process(target=run_chunks_processor)
        
        # Inicia os processos
        logger.info("Iniciando processadores e API...")
        api_process.start()
        pdf_process.start()
        chunks_process.start()
        
        # Aguarda os processos
        api_process.join()
        pdf_process.join()
        chunks_process.join()
        
    except KeyboardInterrupt:
        logger.info("Encerrando aplicação...")
    except Exception as e:
        logger.error(f"Erro fatal na aplicação: {str(e)}", exc_info=True)
        raise

if __name__ == "__main__":
    main() 