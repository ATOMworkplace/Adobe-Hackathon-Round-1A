import re
from typing import List, Optional
from ..models.data_models import TextBlock, HeadingCandidate

class TOCExtractor:
    def __init__(self, config_manager):
        self.config = config_manager.get_classification_config()

    def extract_toc_headings(self, blocks: List[TextBlock]) -> Optional[List[HeadingCandidate]]:
        # Find the page containing "Table of Contents"
        toc_page = None
        for block in blocks:
            if "table of contents" in block.text.strip().lower():
                toc_page = block.page_number
                break
        if toc_page is None:
            return None  # No TOC found

        toc_headings = []
        for block in blocks:
            if block.page_number in (toc_page, toc_page + 1):
                txt = block.text.strip()
                # Match e.g. "2.3 Learning Objectives .......... 7"
                m = re.match(r'^((?:[0-9]+[.])+\s*)?(.+?)\.{3,}\s*(\d+)$', txt)
                if m:
                    heading_txt = m.group(2).strip()
                    page_num = int(m.group(3))
                    level = self.detect_level(m.group(1))
                    toc_headings.append(HeadingCandidate(
                        text_block=block, level=level, page=page_num
                    ))
                else:
                    # For cases like "Revision History .......... 3"
                    m2 = re.match(r'^(.+?)\.{3,}\s*(\d+)$', txt)
                    if m2:
                        heading_txt = m2.group(1).strip()
                        page_num = int(m2.group(2))
                        level = "H1"
                        toc_headings.append(HeadingCandidate(
                            text_block=block, level=level, page=page_num
                        ))
        if toc_headings:
            # Deduplicate by heading text
            seen = set()
            result = []
            for h in toc_headings:
                if h.text_block.text not in seen:
                    result.append(h)
                    seen.add(h.text_block.text)
            return result
        return None

    def detect_level(self, numpart):
        if numpart is None:
            return "H1"
        # Count dots: "2.3" = H2, "1." = H1
        if numpart.count('.') > 1:
            return "H2"
        if numpart.count('.') == 1:
            return "H2"
        return "H1"
