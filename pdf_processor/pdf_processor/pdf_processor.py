import os
import json
import hashlib
from typing import Dict, Any
from confluent_kafka import KafkaError
from confluent_kafka.serialization import SerializationContext, MessageField
import requests
from io import BytesIO
from PyPDF2 import PdfReader
from loguru import logger
import time

from shared import KafkaConfig, KafkaTopics

class PDFProcessor:
    def __init__(self):
        # Configurações do Kafka
        self.kafka_config = KafkaConfig()
        self.topics = KafkaTopics.get_pdf_processor_topics()
        
        # Inicialização lazy
        self._schema_registry = None
        self._consumer = None
        self._producer = None
        self._input_deserializer = None
        self._pdf_completo_serializer = None
        self._string_serializer = None

    @property
    def schema_registry(self):
        if self._schema_registry is None:
            self._schema_registry = self.kafka_config.create_schema_registry()
        return self._schema_registry

    @property
    def consumer(self):
        if self._consumer is None:
            self._consumer = self.kafka_config.create_consumer()
            self._consumer.subscribe([self.topics["input"]])
            logger.info(f"Consumer Kafka inicializado e inscrito no tópico {self.topics['input']}")
        return self._consumer

    @property
    def producer(self):
        if self._producer is None:
            self._producer = self.kafka_config.create_producer()
        return self._producer

    @property
    def input_deserializer(self):
        if self._input_deserializer is None:
            self._input_deserializer = self.kafka_config.create_avro_deserializer(
                self.schema_registry, self.topics["input"]
            )
        return self._input_deserializer

    @property
    def pdf_completo_serializer(self):
        if self._pdf_completo_serializer is None:
            self._pdf_completo_serializer = self.kafka_config.create_avro_serializer(
                self.schema_registry, self.topics["output"]
            )
        return self._pdf_completo_serializer

    @property
    def string_serializer(self):
        if self._string_serializer is None:
            self._string_serializer = self.kafka_config.create_string_serializer()
        return self._string_serializer

    def download_pdf(self, url: str) -> bytes:
        """Download do PDF da URL fornecida"""
        try:
            response = requests.get(url, timeout=10)
            response.raise_for_status()
            return response.content
        except Exception as e:
            logger.error(f"Erro ao baixar PDF de {url}: {str(e)}")
            raise

    def extract_text_from_pdf(self, pdf_content: bytes) -> str:
        """Extrai o texto do conteúdo do PDF"""
        try:
            pdf_file = BytesIO(pdf_content)
            pdf_reader = PdfReader(pdf_file)
            text = ""
            for page in pdf_reader.pages:
                text += page.extract_text() + "\n"
            return text
        except Exception as e:
            logger.error(f"Erro ao extrair texto do PDF: {str(e)}")
            raise

    def generate_document_id(self, url: str) -> str:
        """Gera um ID único para o documento baseado na URL"""
        return hashlib.sha256(url.encode()).hexdigest()

    def process_message(self, msg):
        """Processa uma mensagem recebida do Kafka."""
        try:
            if msg is None:
                logger.warning("Mensagem vazia recebida")
                return
                
            if msg.error():
                error = msg.error()
                logger.error(f"Erro na mensagem Kafka: {error}")
                logger.error(f"Detalhes do erro: código={error.code()}, nome={error.name()}, descrição={error.str()}")
                # Obtém o group_id da configuração
                group_id = self.kafka_config.get_kafka_config().get('group.id', 'unknown')
                client_id = self.kafka_config.get_kafka_config().get('client.id', 'unknown')
                logger.error(f"Configurações atuais: group.id={group_id}, client.id={client_id}")
                return

            logger.info(f"Processando mensagem do tópico {msg.topic()}, partição {msg.partition()}, offset {msg.offset()}")
            
            # Deserializa a mensagem usando o Schema Registry
            try:
                value = self.input_deserializer(msg.value(), SerializationContext(msg.topic(), MessageField.VALUE))
                logger.info(f"Conteúdo da mensagem: {json.dumps(value, indent=2)}")
            except Exception as e:
                logger.error(f"Erro ao deserializar mensagem: {str(e)}")
                return

            # Processa o PDF
            try:
                pdf_url = value.get('url')
                if not pdf_url:
                    logger.error("URL do PDF não encontrada na mensagem")
                    return

                logger.info(f"Iniciando download do PDF: {pdf_url}")
                pdf_content = self.download_pdf(pdf_url)
                
                if pdf_content:
                    logger.info(f"PDF baixado com sucesso: {pdf_url}")
                    text = self.extract_text_from_pdf(pdf_content)
                    
                    if text:
                        logger.info(f"Texto extraído com sucesso do PDF: {pdf_url}")
                        # Envia para o próximo tópico usando o serializer Avro
                        doc_id = self.generate_document_id(pdf_url)
                        logger.info(f"ID gerado para o documento: {doc_id}")
                        self.producer.produce(
                            self.topics["output"],
                            key=doc_id.encode('utf-8'),
                            value=self.pdf_completo_serializer({
                                'id': doc_id,
                                'url': pdf_url,
                                'text': text
                            }, SerializationContext(self.topics["output"], MessageField.VALUE)),
                            callback=self.delivery_report
                        )
                        self.producer.poll(0)
                        logger.info(f"Mensagem enviada para o tópico {self.topics['output']}: {pdf_url}")
                        
                        # Commit do offset após processamento bem-sucedido
                        self.consumer.commit(msg)
                        logger.info(f"Offset {msg.offset()} commitado com sucesso")
                    else:
                        logger.error(f"Falha ao extrair texto do PDF: {pdf_url}")
                else:
                    logger.error(f"Falha ao baixar PDF: {pdf_url}")
                    
            except Exception as e:
                logger.error(f"Erro ao processar PDF {pdf_url}: {str(e)}")
                # Envia erro para o tópico de erros usando o serializer de string
                self.producer.produce(
                    self.topics["error"],
                    self.string_serializer(json.dumps({
                        'url': pdf_url,
                        'error': str(e)
                    })),
                    callback=self.delivery_report
                )
                self.producer.poll(0)
                logger.info(f"Erro enviado para o tópico {self.topics['error']}: {pdf_url}")

        except Exception as e:
            logger.error(f"Erro ao processar mensagem: {str(e)}")
            logger.error(f"Detalhes da mensagem: tópico={msg.topic()}, partição={msg.partition()}, offset={msg.offset()}")

    def delivery_report(self, err, msg):
        """Callback para relatório de entrega de mensagens"""
        if err is not None:
            logger.error(f"Falha na entrega da mensagem: {err}")
        else:
            logger.debug(f"Mensagem entregue: {msg.topic()} [{msg.partition()}]")

    def run(self):
        """Executa o processador de PDFs"""
        logger.info("Iniciando processador de PDFs...")
        try:
            while True:
                try:
                    msg = self.consumer.poll(1.0)
                    if msg is None:
                        continue
                    self.process_message(msg)
                    self.producer.poll(0)
                except Exception as e:
                    logger.error(f"Erro ao processar mensagem: {str(e)}")
                    # Tenta reconectar ao Kafka
                    try:
                        self.consumer.close()
                        self._consumer = None
                        logger.info("Tentando reconectar ao Kafka...")
                        time.sleep(5)  # Espera 5 segundos antes de tentar novamente
                    except Exception as reconnect_error:
                        logger.error(f"Erro ao tentar reconectar: {str(reconnect_error)}")
                        time.sleep(10)  # Espera mais tempo se falhar
        except KeyboardInterrupt:
            logger.info("Encerrando processador de PDFs...")
        finally:
            logger.info("Fechando conexões...")
            try:
                self.consumer.close()
                self.producer.flush()
                logger.info("Conexões fechadas com sucesso")
            except Exception as e:
                logger.error(f"Erro ao fechar conexões: {str(e)}") 