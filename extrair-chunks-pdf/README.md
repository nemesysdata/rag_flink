# PDF Chunks Extractor Service

Este serviço é responsável por extrair chunks de texto dos PDFs processados, utilizando o Gemini para fazer a divisão inteligente do texto com overlap.

## Funcionalidades

- Consome mensagens do tópico `pdf_baixado`
- Utiliza o Gemini para dividir o texto em chunks com overlap de 1024 caracteres
- Publica os chunks no tópico `pdf_chunks`
- Tratamento de erros com publicação em tópico de erro

## Variáveis de Ambiente

O serviço requer as seguintes variáveis de ambiente:

```env
KAFKA_BOOTSTRAP_SERVERS=
KAFKA_API_KEY=
KAFKA_API_SECRET=
KAFKA_INPUT_TOPIC=pdf_baixado
KAFKA_OUTPUT_TOPIC=pdf_chunks
KAFKA_ERROR_TOPIC=pdf_chunks_error
KAFKA_CONSUMER_GROUP=extrair-chunks-pdf-group
SCHEMA_REGISTRY_URL=
SCHEMA_REGISTRY_API_KEY=
SCHEMA_REGISTRY_API_SECRET=
GOOGLE_API_KEY=
```

## Build e Execução

### Local

1. Instale o Poetry (se ainda não tiver):
```bash
curl -sSL https://install.python-poetry.org | python3 -
```

2. Instale as dependências:
```bash
poetry install
```

3. Configure as variáveis de ambiente

4. Execute o serviço:
```bash
poetry run python src/main.py
```

### Docker

1. Build da imagem:
```bash
docker build -t extrair-chunks-pdf .
```

2. Execute o container:
```bash
docker run -p 8080:8080 --env-file .env extrair-chunks-pdf
```

## Endpoints

- `GET /health`: Endpoint de health check

## Schemas

### Input (pdf_baixado)
```json
{
  "doc": "PDF completo que foi baixado",
  "fields": [
    {
      "doc": "ID do documento HASH 256 calculado a partir da URL",
      "name": "id",
      "type": "string"
    },
    {
      "doc": "URL de onde o documento foi baixado",
      "name": "url",
      "type": "string"
    },
    {
      "doc": "O texto extraído do documento",
      "name": "text",
      "type": "string"
    }
  ],
  "name": "pdf_completo",
  "namespace": "co.techrom.poc_rag",
  "type": "record"
}
```

### Output (pdf_chunks)
```json
{
  "doc": "Chunks do pdf",
  "fields": [
    {
      "doc": "UUID gerado para o registro",
      "name": "chunk_id",
      "type": "string"
    },
    {
      "doc": "O id do pdf lido no tópico anterior",
      "name": "pdf_id",
      "type": "string"
    },
    {
      "doc": "O texto do chunk que foi extraido do topico",
      "name": "chunk_text",
      "type": "string"
    }
  ],
  "name": "pdf_chunk",
  "namespace": "co.techrom.poc_rag",
  "type": "record"
}
``` 