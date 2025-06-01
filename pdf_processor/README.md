# PDF Processor Service

Este serviço é responsável por baixar PDFs a partir de URLs e extrair seu conteúdo textual.

## Funcionalidades

- Consome mensagens do tópico `pdf_download`
- Faz download dos PDFs das URLs recebidas
- Extrai o texto dos documentos usando PyPDF2
- Publica o conteúdo no tópico `pdf_baixado`
- Tratamento de erros com publicação em tópico de erro

## Variáveis de Ambiente

O serviço requer as seguintes variáveis de ambiente:

```env
# Kafka
KAFKA_BOOTSTRAP_SERVERS=
KAFKA_API_KEY=
KAFKA_API_SECRET=
KAFKA_CONSUMER_GROUP=pdf-processor-group

# Schema Registry
SCHEMA_REGISTRY_URL=
SCHEMA_REGISTRY_API_KEY=
SCHEMA_REGISTRY_API_SECRET=
```

## Schemas

### Input (pdf_download)
```json
{
  "doc": "URL do PDF para download",
  "fields": [
    {
      "doc": "URL do documento PDF",
      "name": "url",
      "type": "string"
    }
  ],
  "name": "pdf_download",
  "namespace": "co.techrom.poc_rag",
  "type": "record"
}
```

### Output (pdf_baixado)
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
docker build -t pdf-processor .
```

2. Execute o container:
```bash
docker run -p 8080:8080 --env-file .env pdf-processor
``` 