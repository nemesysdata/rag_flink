# RAG Flink

Projeto de processamento de documentos PDF usando Apache Kafka e Google Cloud Run.

## Estrutura do Projeto

```
rag_flink/
├── pdf-processor/           # Serviço de processamento de PDFs
│   ├── src/                # Código fonte
│   ├── Dockerfile         # Configuração do container
│   ├── pyproject.toml     # Dependências Python
│   └── .env              # Variáveis de ambiente
└── cloudbuild.yaml        # Configuração do Cloud Build
```

## Serviços

### PDF Processor

Serviço responsável por:
- Monitorar um tópico Kafka para URLs de PDFs
- Fazer download dos PDFs
- Extrair o texto dos documentos
- Publicar o conteúdo em um novo tópico Kafka

#### Tecnologias Utilizadas
- Python 3.12
- Apache Kafka
- Confluent Schema Registry
- PyPDF2
- Poetry (gerenciamento de dependências)
- Docker
- Google Cloud Run

#### Configuração

1. **Variáveis de Ambiente**:
   ```env
   KAFKA_BOOTSTRAP_SERVERS=
   KAFKA_API_KEY=
   KAFKA_API_SECRET=
   KAFKA_INPUT_TOPIC=
   KAFKA_OUTPUT_TOPIC=
   KAFKA_ERROR_TOPIC=
   KAFKA_CONSUMER_GROUP=
   SCHEMA_REGISTRY_URL=
   SCHEMA_REGISTRY_API_KEY=
   SCHEMA_REGISTRY_API_SECRET=
   ```

2. **Schemas Avro**:
   - `pdf_completo.avsc`: Schema para o conteúdo extraído dos PDFs

#### Desenvolvimento Local

1. Instalar dependências:
   ```bash
   cd pdf-processor
   poetry install
   ```

2. Executar o serviço:
   ```bash
   poetry run python src/main.py
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