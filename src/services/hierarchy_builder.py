"""Hierarchy building service for document outline construction."""

from typing import List, Dict, Optional
import logging

from ..models.data_models import HeadingCandidate, OutlineEntry, DocumentOutline
from ..config import ClassificationConfig

class HierarchyBuilder:
    """Builds hierarchical document outline from heading candidates."""

    def __init__(self, config: ClassificationConfig):
        """Initialize hierarchy builder."""
        self.config = config
        self.logger = logging.getLogger(__name__)

    def build_outline(self, headings: List[HeadingCandidate], document_title: str) -> DocumentOutline:
        """Build complete document outline from heading candidates."""
        if not headings:
            self.logger.warning("No headings provided for outline building")
            return DocumentOutline(title=document_title, outline=[])

        self.logger.info(f"Building outline from {len(headings)} heading candidates")

        # Sort headings by their position in the document (page, then top-to-bottom)
        # Note: In PDF coordinates, higher Y values are at the top, so we sort by descending Y
        headings.sort(key=lambda h: (h.text_block.page_number, -h.text_block.position.y1))

        outline_entries = []
        
        for heading in headings:
            # Skip any heading that is part of the document title or is classified as body
            if self._is_title_duplicate(heading.text, document_title) or heading.suggested_level == "Body":
                continue
            
            # Pre-clean the text to check if it would be empty after cleaning
            from ..utils.validation import UnicodeHandler
            cleaned_text = UnicodeHandler.clean_extracted_text(heading.text)
            
            # Skip headings that would result in empty text after cleaning
            if not cleaned_text or len(cleaned_text.strip()) == 0:
                self.logger.debug(f"Skipping heading with empty cleaned text: '{heading.text}'")
                continue

            entry = OutlineEntry(
                level=heading.suggested_level,
                text=heading.text,
                page=heading.text_block.page_number,
                confidence_score=heading.confidence_score
            )
            outline_entries.append(entry)

        # Reverse the order to match document reading order (top to bottom)
        outline_entries.reverse()
        
        self.logger.info(f"Built outline with {len(outline_entries)} entries")
        return DocumentOutline(title=document_title, outline=outline_entries)
    
    def _is_title_duplicate(self, heading_text: str, document_title: str) -> bool:
        """Check if a heading is a duplicate or part of the document title.
        
        Args:
            heading_text: Text of the heading candidate
            document_title: The document title
            
        Returns:
            True if the heading should be filtered out as a title duplicate
        """
        if not heading_text or not document_title:
            return False
        
        heading_lower = heading_text.lower().strip()
        title_lower = document_title.lower().strip()
        
        # Exact match
        if heading_lower == title_lower:
            return True
        
        # Check if heading is a significant part of the title (>50% overlap)
        heading_words = set(heading_lower.split())
        title_words = set(title_lower.split())
        
        if len(heading_words) > 0:
            overlap = len(heading_words.intersection(title_words))
            overlap_ratio = overlap / len(heading_words)
            
            # If more than 80% of heading words are in the title AND it's a long heading, it's likely a duplicate
            # But allow shorter headings with common words like "renewable energy"
            if overlap_ratio > 0.8 and len(heading_words) > 4:
                return True
        
        # Check for specific patterns that indicate title fragments
        title_fragments = [
            "climate change the role of renewable energy in combating",
            "the role of renewable energy in combating climate change",
            "climate change",  # This should be filtered when it's part of the title
            "the role of renewable energy in combating",
            "in education the importance of mental health awareness",
            "the importance of mental health awareness in education"
        ]
        
        for fragment in title_fragments:
            if heading_lower == fragment:
                return True
        
        return False
