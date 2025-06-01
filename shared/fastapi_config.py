import logging
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

logger = logging.getLogger(__name__)

def create_app(title: str = "Service") -> FastAPI:
    """Cria e configura uma aplicação FastAPI"""
    logger.info(f"Criando aplicação FastAPI: {title}")
    
    app = FastAPI(
        title=title,
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

    # Endpoint de health check
    @app.get("/health")
    async def health_check():
        return {"status": "healthy"}

    logger.info("Aplicação FastAPI configurada com sucesso")
    return app 