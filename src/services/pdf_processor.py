import fitz
import logging
from typing import List
from ..config import ConfigManager
from ..services.text_extractor import TextExtractor
from ..exceptions import PDFParsingError
from ..models.data_models import TextBlock

class PDFProcessor:
    def __init__(self, config_manager: ConfigManager):
        self.text_extractor = TextExtractor(config_manager)
        self.logger = logging.getLogger(__name__)

    def process_pdf(self, pdf_path: str) -> List[TextBlock]:
        try:
            doc = fitz.open(pdf_path)
        except Exception as e:
            raise PDFParsingError(f"Failed to open or parse PDF {pdf_path}: {e}")

        if doc.is_encrypted:
            self.logger.error(f"PDF is encrypted: {pdf_path}")
            doc.close()
            return []
        
        all_blocks = self.text_extractor.extract_clean_blocks(doc)
        doc.close()
        return all_blocks