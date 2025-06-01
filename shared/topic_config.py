"""
Configurações dos tópicos Kafka utilizados no pipeline de processamento de PDFs.
"""

class KafkaTopics:
    """Configuração dos tópicos Kafka utilizados no pipeline."""
    
    # Tópicos principais
    PDF_DOWNLOAD = "pdf_download"  # Tópico para buscar PDFs a serem baixados
    PDF_BAIXADO = "pdf_baixado"  # Tópico para textos extraídos dos PDFs
    PDF_CHUNKS = "pdf_chunks"      # Tópico para chunks dos textos
    PDF_ERRORS = "pdf_errors"      # Tópico para mensagens de erro

    @classmethod
    def get_pdf_processor_topics(cls) -> dict:
        """Retorna os tópicos utilizados pelo PDFProcessor."""
        return {
            "input": cls.PDF_DOWNLOAD,
            "output": cls.PDF_BAIXADO,
            "error": cls.PDF_ERRORS
        }

    @classmethod
    def get_chunks_processor_topics(cls) -> dict:
        """Retorna os tópicos utilizados pelo ChunksProcessor."""
        return {
            "input": cls.PDF_BAIXADO,
            "output": cls.PDF_CHUNKS,
            "error": cls.PDF_ERRORS
        } 