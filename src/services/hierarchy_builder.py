from typing import List
import re
from ..models.data_models import HeadingCandidate, OutlineEntry, DocumentOutline

class HierarchyBuilder:
    def __init__(self, config_manager):
        pass

    def build_outline(self, headings: List[HeadingCandidate], document_title: str) -> DocumentOutline:
        headings.sort(key=lambda h: (h.page, h.text_block.position.y0))
        
        title_norm = self._normalize(document_title)
        
        outline = []
        last_h1, last_h2 = False, False

        for heading in headings:
            if title_norm and self._normalize(heading.text) == title_norm:
                continue
            
            level = heading.level
            
            if level == "H1":
                last_h1, last_h2 = True, False
            elif level == "H2":
                if not last_h1: level = "H1"; last_h1 = True
                last_h2 = True
            elif level == "H3":
                if not last_h1: level = "H1"; last_h1 = True
                if not last_h2: level = "H2"; last_h2 = True
            
            outline.append(OutlineEntry(level, heading.text, heading.page))
        
        return DocumentOutline(title=document_title, outline=outline)

    def _normalize(self, text: str) -> str:
        return re.sub(r'[^a-z0-9]', '', text.lower()) if text else ""
