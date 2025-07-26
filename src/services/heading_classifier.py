import statistics
import re
from typing import List, Dict, Tuple

from ..config import ConfigManager
from ..models.data_models import TextBlock, HeadingCandidate

class HeadingClassifier:
    def __init__(self, config_manager: ConfigManager):
        self.config = config_manager.get_classification_config()

    def classify_blocks(self, blocks: List[TextBlock]) -> List[HeadingCandidate]:
        if not blocks: return []
        
        font_sizes = [b.font_metadata.size for b in blocks if len(b.text.split()) < 50]
        median_size = statistics.median(font_sizes) if font_sizes else 10.0
        
        candidates = []
        for block in blocks:
            if block.page_number == 0: continue
            level = self._get_heading_level(block, median_size)
            if level != "Body":
                candidates.append(HeadingCandidate(text_block=block, level=level))
        return candidates

    def _get_heading_level(self, block: TextBlock, median_size: float) -> str:
        text = block.text.strip()
        font_size = block.font_metadata.size
        is_bold = block.font_metadata.is_bold
        word_count = len(text.split())

        if not text or word_count > self.config.max_heading_words:
            return "Body"

        size_ratio = font_size / median_size if median_size > 0 else 1.0

        numbered_h2 = re.match(r'^\d\.\d\s', text)
        numbered_h1 = re.match(r'^\d\.\s', text)
        
        if numbered_h2: return "H2"
        if numbered_h1: return "H1"

        un_numbered_h1 = {"revision history", "table of contents", "acknowledgements", "references"}
        if text.lower() in un_numbered_h1 and size_ratio > 1.2:
            return "H1"
        
        if is_bold and size_ratio > 1.2:
            return "H2"
            
        return "Body"