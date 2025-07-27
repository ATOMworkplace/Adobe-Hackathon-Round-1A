import statistics
import re
from typing import List
from ..config import ConfigManager
from ..models.data_models import TextBlock, HeadingCandidate

class HeadingClassifier:
    def __init__(self, config_manager: ConfigManager):
        self.config = config_manager.get_classification_config()

    def classify_blocks(self, blocks: List[TextBlock]) -> List[HeadingCandidate]:
        if not blocks:
            return []

        # Step 1: Detect TOC pages
        toc_pages = set()
        for b in blocks:
            t = b.text.strip()
            if re.search(r'\.{3,}\s*\d+\s*$', t):
                toc_pages.add(b.page_number)
            elif "table of contents" in t.lower():
                toc_pages.add(b.page_number)

        # Step 2: Detect Revision History pages
        revision_pages = set(
            b.page_number for b in blocks if b.text.strip().lower() == "revision history"
        )

        # Median size calculation (content only)
        content_blocks = [
            b for b in blocks
            if b.page_number not in toc_pages and b.page_number not in revision_pages and b.page_number > 0
        ]
        font_sizes = [b.font_metadata.size for b in content_blocks if len(b.text.split()) < 50]
        median_size = statistics.median(font_sizes) if font_sizes else 10.0

        candidates = []
        for block in content_blocks:
            txt = block.text.strip()

            # Ignore obvious pseudo-headings (version lines, page numbers, ToC lines)
            if re.match(r'^\d+(\.\d+)?\s+\d{1,2}\s+[A-Z]{3,}\s+\d{4}', txt):
                continue
            if re.search(r'\.{3,}\s*\d+\s*$', txt):  # dot leaders + page num
                continue
            if re.fullmatch(r'page \d+|\d+', txt, re.I):
                continue
            if len(txt) < 2:
                continue

            level = self._get_heading_level(block, median_size)
            if level in ("H1", "H2"):
                candidates.append(HeadingCandidate(text_block=block, level=level))

        return candidates

    def _get_heading_level(self, block: TextBlock, median_size: float) -> str:
        txt = block.text.strip()
        font_size = block.font_metadata.size
        is_bold = block.font_metadata.is_bold
        word_count = len(txt.split())

        if not txt or word_count > self.config.max_heading_words:
            return "Body"

        size_ratio = font_size / median_size if median_size > 0 else 1.0

        # Numbered pattern (e.g. 1. Introduction)
        if re.match(r'^\d+\.\s', txt):
            return "H1"
        if re.match(r'^\d+\.\d+\s', txt):
            return "H2"
        # Unnumbered but matches common main headings
        main_headings = {"revision history", "table of contents", "acknowledgements", "references"}
        if txt.lower() in main_headings and size_ratio > 1.1:
            return "H1"
        if is_bold and size_ratio > 1.1:
            return "H2"
        if size_ratio > 1.3:
            return "H1"
        return "Body"
