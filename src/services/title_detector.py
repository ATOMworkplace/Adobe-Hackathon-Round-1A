from typing import List
from ..models.data_models import TextBlock, HeadingCandidate

class TitleDetector:
    def __init__(self, config_manager):
        pass

    def detect_title(self, candidates, all_blocks):
        # Allow largest text block(s) from page 0 and 1
        first_blocks = [b for b in all_blocks if b.page_number in (0, 1)]
        if not first_blocks:
            return ""
        first_blocks.sort(key=lambda b: b.font_metadata.size, reverse=True)
        max_size = first_blocks[0].font_metadata.size

        # Include all large-font lines (handles "Overview Foundation Level Extensions" as two lines)
        titles = [
            b.text.strip() for b in first_blocks
            if abs(b.font_metadata.size - max_size) < 1.0 and len(b.text.strip()) > 5
        ]
        return "  ".join(titles) if titles else first_blocks[0].text.strip()
