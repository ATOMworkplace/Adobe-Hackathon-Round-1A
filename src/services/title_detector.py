from typing import List
from ..models.data_models import TextBlock, HeadingCandidate

class TitleDetector:
    def __init__(self, config_manager):
        pass

    def detect_title(self, candidates: List[HeadingCandidate], all_blocks: List[TextBlock]) -> str:
        first_page_blocks = [b for b in all_blocks if b.page_number == 0]
        if not first_page_blocks: 
            return ""
        
        first_page_blocks.sort(key=lambda b: b.font_metadata.size, reverse=True)
        
        if not first_page_blocks:
            return ""
        
        max_size = first_page_blocks[0].font_metadata.size
        
        title_blocks = [b for b in first_page_blocks if abs(b.font_metadata.size - max_size) < 1.0]
        
        title_blocks.sort(key=lambda b: (b.position.y0, b.position.x0))
        
        return " ".join(b.text.strip() for b in title_blocks)