import subprocess
import sys
import os
from loguru import logger
import time
import signal
import psutil

def run_service(service_name, command):
    """Executa um serviço e retorna o processo."""
    logger.info(f"Iniciando serviço {service_name}...")
    process = subprocess.Popen(
        command,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        universal_newlines=True,
        shell=True
    )
    return process

def monitor_process(process, service_name):
    """Monitora a saída do processo."""
    while True:
        output = process.stdout.readline()
        if output == '' and process.poll() is not None:
            break
        if output:
            logger.info(f"[{service_name}] {output.strip()}")
    
    error = process.stderr.read()
    if error:
        logger.error(f"[{service_name}] Erro: {error}")

def cleanup(processes):
    """Limpa os processos em execução."""
    logger.info("Encerrando serviços...")
    for process in processes:
        try:
            parent = psutil.Process(process.pid)
            children = parent.children(recursive=True)
            for child in children:
                child.terminate()
            parent.terminate()
        except:
            pass

def main():
    # Diretório raiz do projeto
    root_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    
    # Comandos para executar os serviços
    pdf_processor_cmd = f"cd {root_dir}/pdf-processor && python src/main.py"
    chunks_processor_cmd = f"cd {root_dir}/extrair-chunks-pdf && python src/main.py"
    
    # Lista para armazenar os processos
    processes = []
    
    try:
        # Inicia os serviços
        pdf_process = run_service("PDF Processor", pdf_processor_cmd)
        processes.append(pdf_process)
        
        # Aguarda um pouco antes de iniciar o próximo serviço
        time.sleep(5)
        
        chunks_process = run_service("Chunks Processor", chunks_processor_cmd)
        processes.append(chunks_process)
        
        # Monitora os processos
        for process in processes:
            monitor_process(process, "PDF Processor" if process == pdf_process else "Chunks Processor")
            
    except KeyboardInterrupt:
        logger.info("Interrompendo serviços...")
    finally:
        cleanup(processes)

if __name__ == "__main__":
    main() 