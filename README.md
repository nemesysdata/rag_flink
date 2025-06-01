# RAG Flink

Projeto de processamento de documentos PDF usando Apache Kafka e Google Cloud Run.

## Estrutura do Projeto

```
rag_flink/
├── pdf_processor/          # Serviço de processamento de PDFs
│   ├── main.py            # Ponto de entrada do serviço
│   ├── pdf_processor.py   # Lógica de processamento
│   └── schemas/           # Schemas Avro
├── extrair_chunks_pdf/    # Serviço de extração de chunks
│   ├── main.py           # Ponto de entrada do serviço
│   └── chunks_processor.py # Lógica de processamento
├── shared/                # Módulos compartilhados
│   ├── kafka_config.py    # Configuração do Kafka
│   ├── topic_config.py    # Configuração dos tópicos
│   └── logging_config.py  # Configuração de logs
├── scripts/               # Scripts utilitários
├── main.py               # Ponto de entrada principal
└── pyproject.toml        # Dependências do projeto
```

## Serviços

### PDF Processor

Serviço responsável por:
- Monitorar o tópico `pdf_download` para URLs de PDFs
- Fazer download dos PDFs
- Extrair o texto dos documentos
- Publicar o conteúdo no tópico `pdf_baixado`

### Chunks Processor

Serviço responsável por:
- Monitorar o tópico `pdf_baixado` para textos extraídos
- Dividir o texto em chunks de 1000 caracteres com overlap de 200
- Publicar os chunks no tópico `pdf_chunks`

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
   ```

2. **Tópicos Kafka**:
   - `pdf_download`: URLs de PDFs para processamento
   - `pdf_baixado`: Textos extraídos dos PDFs
   - `pdf_chunks`: Chunks de texto processados
   - `pdf_errors`: Mensagens de erro

#### Desenvolvimento Local

1. Instalar dependências:
   ```bash
   poetry install
   ```

2. Executar os serviços:
   ```bash
   poetry run python main.py
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