import os
import threading
from dotenv import load_dotenv

# Carrega as variáveis de ambiente
load_dotenv()

from shared import setup_logging
from pdf_processor.pdf_processor.pdf_processor import PDFProcessor
from extrair_chunks_pdf.extrair_chunks_pdf.chunks_processor import ChunksProcessor

def run_pdf_processor():
    """Executa o processador de PDFs"""
    processor = PDFProcessor()
    processor.run()

def run_chunks_processor():
    """Executa o processador de chunks"""
    processor = ChunksProcessor()
    processor.run()

def main():
    # Configura o logging
    logger = setup_logging()
    logger.info("Iniciando aplicação...")

    # Cria o diretório de logs se não existir
    os.makedirs("logs", exist_ok=True)

    # Inicia os processadores em threads separadas
    pdf_thread = threading.Thread(target=run_pdf_processor, name="PDFProcessor")
    chunks_thread = threading.Thread(target=run_chunks_processor, name="ChunksProcessor")

    try:
        logger.info("Iniciando processadores...")
        pdf_thread.start()
        chunks_thread.start()

        # Aguarda as threads terminarem
        pdf_thread.join()
        chunks_thread.join()

    except KeyboardInterrupt:
        logger.info("Encerrando aplicação...")
    except Exception as e:
        logger.error(f"Erro ao executar aplicação: {str(e)}")
        raise

if __name__ == "__main__":
    main() 