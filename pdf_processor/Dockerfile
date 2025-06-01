FROM python:3.12-slim

# Instala dependências do sistema
RUN apt-get update && apt-get install -y \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# Instala o Poetry
RUN pip install poetry

# Configura o Poetry para não criar ambientes virtuais
RUN poetry config virtualenvs.create false

# Define o diretório de trabalho
WORKDIR /app

# Copia os arquivos de dependências
COPY pyproject.toml poetry.lock ./

# Instala as dependências
RUN poetry install --without dev --no-interaction --no-ansi --no-root

# Copia o código da aplicação
COPY src/ ./src/

# Expõe a porta 8080 para o Cloud Run
EXPOSE 8080

# Define a variável de ambiente PORT
ENV PORT=8080

# Comando para executar a aplicação
CMD ["python", "src/main.py"] 