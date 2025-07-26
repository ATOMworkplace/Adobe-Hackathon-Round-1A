from typing import List
import re
from ..models.data_models import HeadingCandidate, OutlineEntry, DocumentOutline

class HierarchyBuilder:
    def __init__(self, config_manager):
        pass

    def build_outline(self, headings: List[HeadingCandidate], document_title: str) -> DocumentOutline:
        headings.sort(key=lambda h: (h.page, h.text_block.position.y0))
        
        outline_entries = []
        last_h1 = False
        for heading in headings:
            level = heading.level
            
            if level == "H1":
                last_h1 = True
            elif level == "H2":
                if not last_h1: level = "H1"
            elif level == "H3":
                if not last_h1: level = "H1"

            outline_entries.append(OutlineEntry(level, heading.text, heading.page))
            
        return DocumentOutline(title=document_title, outline=outline_entries)