FROM python:3.12-slim

WORKDIR /app

# Instala o Poetry
RUN pip install poetry

# Configura o Poetry para não criar um ambiente virtual
RUN poetry config virtualenvs.create false

# Copia os arquivos de configuração do Poetry
COPY pyproject.toml poetry.lock* ./

# Instala as dependências
RUN poetry install --no-dev --no-interaction --no-ansi

# Copia o código fonte
COPY src/ .

CMD ["python", "main.py"] 