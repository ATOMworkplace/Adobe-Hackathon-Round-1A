"""Text extraction service with advanced metadata capture."""

import fitz
import re
from typing import List, Dict, Tuple, Optional
import logging
from collections import defaultdict

from ..models.data_models import TextBlock, FontMetadata, PositionInfo, StyleInfo
from ..exceptions import TextExtractionError
from ..utils.validation import UnicodeHandler


class TextExtractor:
    """Advanced text extraction with positioning and font metadata."""
    
    def __init__(self):
        """Initialize text extractor."""
        self.logger = logging.getLogger(__name__)
        self.unicode_handler = UnicodeHandler()
        
    def extract_blocks(self, page) -> List[TextBlock]:
        """Extract text blocks from a PDF page with comprehensive metadata.
        
        Args:
            page: PyMuPDF page object
            
        Returns:
            List of TextBlock objects with detailed metadata
        """
        try:
            text_blocks = []
            page_number = page.number  # Keep 0-indexed
            
            # Get text with detailed formatting information
            text_dict = page.get_text("dict")
            
            # Collect ALL spans from ALL blocks on the page first
            all_page_spans = []
            
            for block in text_dict.get("blocks", []):
                if "lines" not in block:
                    continue  # Skip image blocks
                
                # Extract all spans from this block
                for line in block.get("lines", []):
                    for span in line.get("spans", []):
                        text = span.get("text", "").strip()
                        if not text:
                            continue
                        
                        # Normalize Unicode text
                        text = self.unicode_handler.normalize_text(text)
                        if not text:
                            continue
                        
                        # Extract font metadata
                        font_metadata = self.get_font_metadata(span)
                        
                        # Extract position information
                        position = self.calculate_positioning(span)
                        
                        # Extract styling information
                        styling = self._extract_styling(span)
                        
                        text_block = TextBlock(
                            text=text,
                            page_number=page_number,
                            font_metadata=font_metadata,
                            position=position,
                            styling=styling
                        )
                        
                        all_page_spans.append(text_block)
            
            # Now group all spans from the entire page into logical blocks
            if all_page_spans:
                # Sort spans by position (top to bottom, left to right)
                all_page_spans.sort(key=lambda span: (
                    -span.position.y1,  # Top to bottom (negative for descending)
                    span.position.x0    # Left to right
                ))
                
                # Group spans into logical text blocks
                text_blocks = self._group_spans_into_blocks(all_page_spans)
            
            # Post-process to merge related text spans and calculate relative font sizes
            text_blocks = self._post_process_blocks(text_blocks)
            
            return text_blocks
            
        except Exception as e:
            raise TextExtractionError(f"Failed to extract text blocks: {str(e)}")
    

    
    def get_font_metadata(self, span: dict) -> FontMetadata:
        """Extract comprehensive font metadata from a text span.
        
        Args:
            span: Text span dictionary from PyMuPDF
            
        Returns:
            FontMetadata object
        """
        size = span.get("size", 12.0)
        font_name = span.get("font", "unknown")
        flags = span.get("flags", 0)
        
        # Determine font weight
        weight = "bold" if flags & 2**4 else "normal"
        
        # Determine font style
        style = "italic" if flags & 2**1 else "normal"
        
        # Clean up font family name
        family = self._normalize_font_family(font_name)
        
        return FontMetadata(
            size=size,
            family=family,
            weight=weight,
            style=style,
            relative_size_rank=0  # Will be calculated later
        )
    
    def calculate_positioning(self, span: dict) -> PositionInfo:
        """Calculate detailed positioning information for a text span.
        
        Args:
            span: Text span dictionary from PyMuPDF
            
        Returns:
            PositionInfo object with positioning details
        """
        bbox = span.get("bbox", [0, 0, 0, 0])
        
        return PositionInfo(
            x0=bbox[0],
            y0=bbox[1],
            x1=bbox[2],
            y1=bbox[3],
            width=bbox[2] - bbox[0],
            height=bbox[3] - bbox[1]
        )
    
    def _extract_styling(self, span: dict) -> StyleInfo:
        """Extract styling information from a text span.
        
        Args:
            span: Text span dictionary from PyMuPDF
            
        Returns:
            StyleInfo object
        """
        flags = span.get("flags", 0)
        
        return StyleInfo(
            is_bold=bool(flags & 2**4),
            is_italic=bool(flags & 2**1),
            is_underlined=bool(flags & 2**0),
            color=span.get("color")
        )
    
    def _normalize_font_family(self, font_name: str) -> str:
        """Normalize font family name for consistent comparison.
        
        Args:
            font_name: Raw font name from PDF
            
        Returns:
            Normalized font family name
        """
        if not font_name:
            return "unknown"
        
        # Remove common prefixes and suffixes
        font_name = re.sub(r'^[A-Z]{6}\+', '', font_name)  # Remove subset prefix
        font_name = re.sub(r'[,-].*', '', font_name)      # Remove style suffixes
        
        # Normalize common font names
        font_mapping = {
            'times': 'Times',
            'arial': 'Arial',
            'helvetica': 'Helvetica',
            'courier': 'Courier',
            'calibri': 'Calibri'
        }
        
        font_lower = font_name.lower()
        for key, value in font_mapping.items():
            if key in font_lower:
                return value
        
        return font_name
    
    def _merge_related_spans(self, spans: List[TextBlock]) -> List[TextBlock]:
        """Merge text spans that belong to the same logical text unit.
        
        Args:
            spans: List of TextBlock objects from the same line
            
        Returns:
            List of merged TextBlock objects
        """
        if not spans:
            return []
        
        merged = []
        current_group = [spans[0]]
        
        for i in range(1, len(spans)):
            current_span = spans[i]
            previous_span = current_group[-1]
            
            # Check if spans should be merged
            if self._should_merge_spans(previous_span, current_span):
                current_group.append(current_span)
            else:
                # Merge current group and start new group
                if current_group:
                    merged_span = self._merge_span_group(current_group)
                    merged.append(merged_span)
                current_group = [current_span]
        
        # Merge final group
        if current_group:
            merged_span = self._merge_span_group(current_group)
            merged.append(merged_span)
        
        return merged
    
    def _should_merge_spans(self, span1: TextBlock, span2: TextBlock) -> bool:
        """Determine if two spans should be merged into one text block.
        
        Args:
            span1: First text span
            span2: Second text span
            
        Returns:
            True if spans should be merged
        """
        # Same font characteristics (more lenient for size differences)
        same_font = (
            span1.font_metadata.family == span2.font_metadata.family and
            abs(span1.font_metadata.size - span2.font_metadata.size) < 1.0 and  # Increased tolerance
            span1.font_metadata.weight == span2.font_metadata.weight and
            span1.font_metadata.style == span2.font_metadata.style
        )
        
        # Close horizontal positioning (same line) - more generous gap allowance
        horizontal_gap = span2.position.x0 - span1.position.x1
        
        # Calculate average character width for better gap assessment
        avg_char_width = max(span1.position.width / max(len(span1.text), 1), 
                           span2.position.width / max(len(span2.text), 1))
        
        # Allow gaps up to 2 character widths or 30 points, whichever is larger
        max_allowed_gap = max(avg_char_width * 2, 30)
        reasonable_gap = horizontal_gap < max_allowed_gap
        
        # Similar vertical positioning (more lenient)
        vertical_center1 = (span1.position.y0 + span1.position.y1) / 2
        vertical_center2 = (span2.position.y0 + span2.position.y1) / 2
        vertical_tolerance = max(span1.position.height, span2.position.height) * 0.5
        
        vertical_overlap = abs(vertical_center1 - vertical_center2) < vertical_tolerance
        
        # Special case: if both spans are very short (likely fragments), be more aggressive about merging
        both_short = len(span1.text.strip()) <= 3 and len(span2.text.strip()) <= 3
        if both_short and same_font and horizontal_gap < 50:  # More generous for short fragments
            return True
        
        return same_font and reasonable_gap and vertical_overlap
    
    def _merge_span_group(self, spans: List[TextBlock]) -> TextBlock:
        """Merge a group of related spans into a single TextBlock.
        
        Args:
            spans: List of TextBlock objects to merge
            
        Returns:
            Single merged TextBlock
        """
        if len(spans) == 1:
            return spans[0]
        
        # Sort spans by position for proper text reconstruction
        spans.sort(key=lambda span: (
            -span.position.y1,  # Top to bottom
            span.position.x0    # Left to right
        ))
        
        # Combine text with appropriate spacing
        texts = []
        for i, span in enumerate(spans):
            if i > 0:
                prev_span = spans[i-1]
                
                # Check if this is a line break or horizontal continuation
                vertical_diff = abs(prev_span.position.y1 - span.position.y1)
                horizontal_gap = span.position.x0 - prev_span.position.x1
                avg_line_height = (prev_span.position.height + span.position.height) / 2
                
                # Determine if spans are on the same line
                same_line = vertical_diff < avg_line_height * 0.1
                
                if same_line:
                    # Same line: add space if there's a horizontal gap
                    if horizontal_gap > 1:  # Any gap larger than 1 point gets a space
                        texts.append(" ")
                else:
                    # Different lines: add space unless previous text ends with hyphen
                    prev_text = prev_span.text.strip()
                    if prev_text and prev_text.endswith('-'):
                        # Hyphenated word continuation - no space
                        pass
                    else:
                        # Normal line break - add space
                        texts.append(" ")
            
            texts.append(span.text)
        
        combined_text = "".join(texts).strip()
        
        # Calculate combined bounding box
        min_x0 = min(span.position.x0 for span in spans)
        min_y0 = min(span.position.y0 for span in spans)
        max_x1 = max(span.position.x1 for span in spans)
        max_y1 = max(span.position.y1 for span in spans)
        
        combined_position = PositionInfo(
            x0=min_x0,
            y0=min_y0,
            x1=max_x1,
            y1=max_y1,
            width=max_x1 - min_x0,
            height=max_y1 - min_y0
        )
        
        # Use font metadata from the first span (they should be similar)
        return TextBlock(
            text=combined_text,
            page_number=spans[0].page_number,
            font_metadata=spans[0].font_metadata,
            position=combined_position,
            styling=spans[0].styling
        )
    
    def _post_process_blocks(self, text_blocks: List[TextBlock]) -> List[TextBlock]:
        """Post-process text blocks to calculate relative font sizes and clean up.
        
        Args:
            text_blocks: List of TextBlock objects
            
        Returns:
            Post-processed list of TextBlock objects
        """
        if not text_blocks:
            return text_blocks
        
        # Calculate relative font size rankings
        font_sizes = [block.font_metadata.size for block in text_blocks]
        unique_sizes = sorted(set(font_sizes), reverse=True)
        
        # Create size to rank mapping
        size_to_rank = {size: rank for rank, size in enumerate(unique_sizes)}
        
        # Update relative size ranks
        for block in text_blocks:
            block.font_metadata.relative_size_rank = size_to_rank[block.font_metadata.size]
        
        # Filter out very short or invalid text blocks
        filtered_blocks = []
        for block in text_blocks:
            if len(block.text.strip()) >= 1 and self.unicode_handler.is_valid_unicode(block.text):
                filtered_blocks.append(block)
        
        return filtered_blocks
    
    def _group_spans_into_blocks(self, spans: List[TextBlock]) -> List[TextBlock]:
        """Group spans into logical text blocks (paragraphs, headings).
        
        Args:
            spans: List of sorted text spans
            
        Returns:
            List of grouped text blocks
        """
        if not spans:
            return []
        
        grouped_blocks = []
        current_group = [spans[0]]
        
        for i in range(1, len(spans)):
            current_span = spans[i]
            previous_span = current_group[-1]
            
            # Check if current span should be part of the same logical block
            if self._should_group_spans(previous_span, current_span):
                current_group.append(current_span)
            else:
                # Finalize current group and start new one
                if current_group:
                    merged_block = self._merge_span_group(current_group)
                    grouped_blocks.append(merged_block)
                current_group = [current_span]
        
        # Don't forget the last group
        if current_group:
            merged_block = self._merge_span_group(current_group)
            grouped_blocks.append(merged_block)
        
        return grouped_blocks
    
    def _should_group_spans(self, span1: TextBlock, span2: TextBlock) -> bool:
        """Determine if two spans should be grouped into the same logical text block.
        
        Args:
            span1: First text span (earlier in reading order)
            span2: Second text span (later in reading order)
            
        Returns:
            True if spans should be grouped together
        """
        # Must have identical font characteristics for grouping
        identical_font = (
            span1.font_metadata.family == span2.font_metadata.family and
            abs(span1.font_metadata.size - span2.font_metadata.size) < 0.1 and  # Very strict size matching
            span1.font_metadata.weight == span2.font_metadata.weight and
            span1.font_metadata.style == span2.font_metadata.style
        )
        
        if not identical_font:
            return False
        
        # Calculate line height for reference
        avg_line_height = (span1.position.height + span2.position.height) / 2
        
        # Case 1: Same line merging (highest priority)
        vertical_diff = abs(span1.position.y1 - span2.position.y1)
        same_line = vertical_diff < avg_line_height * 0.1  # Very strict same-line detection
        
        if same_line:
            # Check if span2 comes after span1 horizontally
            horizontal_gap = span2.position.x0 - span1.position.x1
            
            # Allow reasonable gaps for same-line text (up to 100 points for wide spacing)
            reasonable_gap = -10 <= horizontal_gap <= 100  # Allow small overlap or reasonable gap
            
            return reasonable_gap
        
        # Case 2: Multi-line continuation (lower priority)
        # Check if span2 is on the next line and continues the text flow
        vertical_gap = span1.position.y0 - span2.position.y1  # Gap between bottom of span1 and top of span2
        
        # Must be reasonable line spacing
        reasonable_line_spacing = 0 < vertical_gap <= avg_line_height * 1.8
        
        # Must be roughly left-aligned (paragraph continuation)
        left_alignment_tolerance = 30  # Points
        left_aligned = abs(span1.position.x0 - span2.position.x0) <= left_alignment_tolerance
        
        # Additional check: span2 should start near the left margin (not indented significantly)
        # This helps distinguish paragraph continuation from new sections
        reasonable_left_position = span2.position.x0 <= span1.position.x0 + left_alignment_tolerance
        
        return reasonable_line_spacing and left_aligned and reasonable_left_position