import logging
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

logger = logging.getLogger(__name__)

# Cria a aplicação FastAPI
app = FastAPI(
    title="PDF Processing Pipeline",
    description="API para monitoramento do pipeline de processamento de PDFs",
    version="1.0.0",
    docs_url=None,  # Desabilita Swagger UI
    redoc_url=None  # Desabilita ReDoc
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
    """Endpoint de health check"""
    return {"status": "healthy"}

@app.get("/")
async def root():
    """Endpoint raiz"""
    return {
        "name": "PDF Processing Pipeline",
        "version": "1.0.0",
        "status": "running"
    } 