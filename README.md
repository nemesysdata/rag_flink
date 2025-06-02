# RAG Flink

Projeto de processamento de documentos PDF usando Apache Kafka e Google Cloud Run.

## Estrutura do Projeto

```
rag_flink/
├── pdf_processor/          # Serviço de processamento de PDFs
│   ├── pdf_processor/     # Módulo do processador
│   │   ├── __init__.py
│   │   ├── pdf_processor.py # Lógica de processamento
│   │   └── pdf_processor_main.py # Ponto de entrada
│   │   └── schemas/       # Schemas Avro
├── extrair_chunks_pdf/    # Serviço de extração de chunks
│   ├── extrair_chunks_pdf/ # Módulo do processador
│   │   ├── __init__.py
│   │   └── chunks_processor.py # Lógica de processamento e ponto de entrada
│   │   └── schemas/       # Schemas Avro
├── milvus_sink/          # Serviço de persistência no Milvus
│   ├── milvus_sink/      # Módulo do sink
│   │   ├── __init__.py
│   │   └── milvus_sink.py # Lógica de persistência
├── shared/                # Módulos compartilhados
│   ├── __init__.py
│   ├── kafka_config.py    # Configuração do Kafka
│   ├── topic_config.py    # Configuração dos tópicos
│   └── logging_config.py  # Configuração de logs
├── scripts/               # Scripts utilitários
│   ├── create_topics.py # Script para criar tópicos
│   └── setup_env.py # Script para configurar ambiente
├── main.py               # Ponto de entrada principal
├── api_server.py         # Servidor FastAPI centralizado
└── pyproject.toml        # Dependências do projeto
```

## Serviços

### PDF Processor

Serviço responsável por:
- Monitorar o tópico `pdf_download` para URLs de PDFs
- Fazer download dos PDFs
- Extrair o texto dos documentos
- Publicar o conteúdo no tópico `pdf_baixado`

#### Schemas do PDF Processor

##### Input (pdf_download)
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

##### Output (pdf_baixado)
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

### Chunks Processor

Serviço responsável por:
- Monitorar o tópico `pdf_baixado` para textos extraídos
- Dividir o texto em chunks de 1000 caracteres com overlap de 200
- Publicar os chunks no tópico `pdf_chunks`

#### Schemas do Chunks Processor

##### Input (pdf_baixado)
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

##### Output (pdf_chunks)
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

### Milvus Sink

Serviço responsável por:
- Monitorar o tópico `pdf_embedding` para embeddings gerados
- Persistir os embeddings no Milvus Cloud (Zilliz)
- Manter a coleção indexada para busca por similaridade

#### Estrutura da Coleção no Milvus

A coleção `pdf_embeddings` possui os seguintes campos:
- `id`: ID auto-incrementado (chave primária)
- `pdf_id`: ID do documento PDF
- `chunk_id`: ID do chunk
- `text`: Texto do chunk
- `embedding`: Vetor de embedding (1536 dimensões)

A coleção é indexada usando IVF_FLAT para busca por similaridade.

### API Server

Servidor FastAPI centralizado responsável por:
- Endpoints de health check para todos os serviços
- Monitoramento do sistema
- Documentação OpenAPI

#### Tecnologias Utilizadas
- Python 3.12
- Apache Kafka
- Confluent Schema Registry
- PyPDF2
- LangChain
- Google Gemini
- Poetry (gerenciamento de dependências)
- Docker
- Google Cloud Run
- FastAPI
- Milvus Cloud (Zilliz)

#### Configuração

1. **Variáveis de Ambiente**:
   ```env
   # Kafka
   KAFKA_BOOTSTRAP_SERVERS=
   KAFKA_API_KEY=
   KAFKA_API_SECRET=
   KAFKA_CONSUMER_GROUP=
   
   # Schema Registry
   SCHEMA_REGISTRY_URL=
   SCHEMA_REGISTRY_API_KEY=
   SCHEMA_REGISTRY_API_SECRET=
   
   # Google Gemini
   GOOGLE_API_KEY=

   # Milvus Cloud (Zilliz)
   MILVUS_URI=your-instance-endpoint.zillizcloud.com
   MILVUS_TOKEN=your-api-key
   MILVUS_COLLECTION=pdf_embeddings
   MILVUS_DIM=1536
   ```

2. **Tópicos Kafka**:
   - `pdf_download`: URLs de PDFs para processamento
   - `pdf_baixado`: Textos extraídos dos PDFs
   - `pdf_chunks`: Chunks de texto processados
   - `pdf_errors`: Mensagens de erro
   - `pdf_embedding`: Embeddings gerados dos chunks

#### Desenvolvimento Local

1. Instalar dependências:
   ```bash
   poetry install
   ```

2. Executar a aplicação (todos os serviços):
   ```bash
   poetry run python main.py
   ```

   A aplicação irá iniciar:
   - O processador de PDFs
   - O processador de chunks
   - O servidor FastAPI na porta 8080

   Para executar serviços individualmente:
   ```bash
   # Apenas o processador de PDFs
   poetry run python pdf_processor/pdf_processor/pdf_processor_main.py

   # Apenas o processador de chunks
   poetry run python extrair_chunks_pdf/extrair_chunks_pdf/chunks_processor.py
   ```

#### Deploy

O serviço é automaticamente deployado no Google Cloud Run através do Cloud Build quando há mudanças na branch main.

## Contribuição

1. Faça um fork do projeto
2. Crie uma branch para sua feature (`git checkout -b feature/nova-feature`)
3. Commit suas mudanças (`git commit -m 'Adiciona nova feature'`)
4. Push para a branch (`git push origin feature/nova-feature`)
5. Abra um Pull Request

## Licença

Este projeto está sob a licença MIT. Veja o arquivo [LICENSE](LICENSE) para mais detalhes.