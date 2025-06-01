# PDF Chunks Extractor Service

Este serviço é responsável por extrair chunks de texto dos PDFs processados, utilizando o LangChain para fazer a divisão inteligente do texto com overlap.

## Funcionalidades

- Consome mensagens do tópico `pdf_baixado`
- Utiliza o LangChain para dividir o texto em chunks de 1000 caracteres com overlap de 200
- Publica os chunks no tópico `pdf_chunks`
- Tratamento de erros com publicação em tópico de erro

## Variáveis de Ambiente

O serviço requer as seguintes variáveis de ambiente:

```env
# Kafka
KAFKA_BOOTSTRAP_SERVERS=
KAFKA_API_KEY=
KAFKA_API_SECRET=
KAFKA_CONSUMER_GROUP=extrair-chunks-pdf-group

# Schema Registry
SCHEMA_REGISTRY_URL=
SCHEMA_REGISTRY_API_KEY=
SCHEMA_REGISTRY_API_SECRET=

# Google Gemini
GOOGLE_API_KEY=
```

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
    },
    {
      "doc": "Índice do chunk no documento",
      "name": "chunk_index",
      "type": "int"
    },
    {
      "doc": "Total de chunks no documento",
      "name": "total_chunks",
      "type": "int"
    }
  ],
  "name": "pdf_chunk",
  "namespace": "co.techrom.poc_rag",
  "type": "record"
}
```

## Desenvolvimento

1. Instale as dependências:
```bash
poetry install
```

2. Execute o serviço:
```bash
poetry run python main.py
```

## Docker

1. Build da imagem:
```bash
docker build -t extrair-chunks-pdf .
```

2. Execute o container:
```bash
docker run -p 8080:8080 --env-file .env extrair-chunks-pdf
``` 