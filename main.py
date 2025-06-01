import os
import logging
import multiprocessing
import signal
import time
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
    processes = []
    
    def signal_handler(signum, frame):
        """Manipulador de sinal para encerramento graceful."""
        logger.info("Sinal de encerramento recebido. Aguardando processos...")
        
        # Aguarda um tempo limitado para os processos encerrarem
        for process in processes:
            if process.is_alive():
                process.terminate()
        
        # Aguarda até 5 segundos para os processos encerrarem
        for process in processes:
            process.join(timeout=5)
            if process.is_alive():
                logger.warning(f"Processo {process.name} não encerrou. Forçando encerramento...")
                process.kill()
        
        logger.info("Aplicação encerrada.")
        os._exit(0)
    
    try:
        # Registra o manipulador de sinal
        signal.signal(signal.SIGINT, signal_handler)
        signal.signal(signal.SIGTERM, signal_handler)
        
        logger.info("Iniciando aplicação...")
        
        # Cria os processos
        api_process = multiprocessing.Process(target=run_api, name="FastAPI")
        pdf_process = multiprocessing.Process(target=run_pdf_processor, name="PDFProcessor")
        chunks_process = multiprocessing.Process(target=run_chunks_processor, name="ChunksProcessor")
        
        # Adiciona os processos à lista
        processes.extend([api_process, pdf_process, chunks_process])
        
        # Inicia os processos
        logger.info("Iniciando processadores e API...")
        for process in processes:
            process.start()
        
        # Aguarda os processos
        for process in processes:
            process.join()
            
    except Exception as e:
        logger.error(f"Erro fatal na aplicação: {str(e)}", exc_info=True)
        raise

if __name__ == "__main__":
    main() 