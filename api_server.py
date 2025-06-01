import logging
from fastapi import FastAPI, Response
from fastapi.middleware.cors import CORSMiddleware
from shared import setup_logging

# Configuração de logging
logger = setup_logging()

# Inicializa o FastAPI
app = FastAPI(
    title="RAG Flink API",
    description="API para monitoramento e health check dos serviços de processamento de PDFs",
    version="1.0.0"
)

# Configuração de CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/health")
async def health_check():
    return {"healthy": "ok"}

@app.get("/")
async def root() -> dict:
    """Endpoint raiz que retorna informações básicas da API.
    
    Returns:
        dict: Dicionário com informações da API.
    """
    return {
        "message": "RAG Flink API",
        "version": "1.0.0",
        "status": "online"
    } 