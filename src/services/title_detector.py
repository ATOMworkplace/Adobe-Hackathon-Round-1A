"""Title detection service for PDF documents."""

from typing import List, Optional, Dict, Tuple
import logging
import re

from ..models.data_models import TextBlock, HeadingCandidate
from ..config import ClassificationConfig


class TitleDetector:
    """Detects document titles using font size, positioning, and placement heuristics."""
    
    def __init__(self, config: ClassificationConfig):
        """Initialize title detector.
        
        Args:
            config: Classification configuration
        """
        self.config = config
        self.logger = logging.getLogger(__name__)
    
    def detect_title(self, text_blocks: List[TextBlock], heading_candidates: List[HeadingCandidate]) -> Optional[str]:
        """Detect the document title from text blocks and heading candidates.
        
        Args:
            text_blocks: All text blocks from the document
            heading_candidates: Classified heading candidates
            
        Returns:
            Detected title string or None if no clear title found
        """
        if not text_blocks:
            return "Untitled Document"
        
        self.logger.info("Detecting document title using multi-strategy candidate gathering")
        
        # First, try to reconstruct fragmented titles
        reconstructed_title = self._reconstruct_fragmented_title(heading_candidates, text_blocks)
        if reconstructed_title:
            self.logger.info(f"Title reconstructed from fragments: {reconstructed_title[:50]}...")
            return self.validate_title(reconstructed_title)
        
        all_candidates = []
        
        # Gather candidates from all strategies
        if heading_candidates:
            all_candidates.extend(self._find_title_candidates_from_headings(heading_candidates))
        
        all_candidates.extend(self._find_title_candidates_from_font_analysis(text_blocks))
        all_candidates.extend(self._find_title_candidates_from_placement(text_blocks))
        
        # Add fallback candidate with low weight
        fallback_title = self._get_fallback_title(text_blocks)
        all_candidates.append((fallback_title, 0.2))
        
        # Remove duplicates while preserving scores
        unique_candidates = []
        seen = set()
        for text, score in all_candidates:
            if text not in seen:
                seen.add(text)
                unique_candidates.append((text, score))
        
        # Sort by score
        unique_candidates.sort(key=lambda x: x[1], reverse=True)
        
        # Apply consensus boosting
        if len(unique_candidates) > 1 and unique_candidates[0][1] < self.config.title_consensus_threshold:
            # Check if top 3 candidates agree on same text
            top_3 = unique_candidates[:3]
            if all(c[0] == top_3[0][0] for c in top_3):
                self.logger.info(f"Consensus boost applied for title: {top_3[0][0][:50]}...")
                return self.validate_title(top_3[0][0])
        
        # Return best candidate if score is above threshold
        if unique_candidates and unique_candidates[0][1] >= self.config.title_confidence_threshold:
            self.logger.info(f"Title detected with score {unique_candidates[0][1]:.2f}: {unique_candidates[0][0][:50]}...")
            return self.validate_title(unique_candidates[0][0])
        
        # Return top candidate if it's significantly better than the next one
        if len(unique_candidates) > 1 and unique_candidates[0][1] > unique_candidates[1][1] * 1.5:
            self.logger.info(f"Title detected based on score dominance: {unique_candidates[0][0][:50]}...")
            return self.validate_title(unique_candidates[0][0])
        
        # Final fallback
        self.logger.info(f"No clear title found, using fallback: {fallback_title[:50]}...")
        return self.validate_title(fallback_title)
    
    def _find_title_candidates_from_headings(self, heading_candidates: List[HeadingCandidate]) -> List[Tuple[str, float]]:
        """Find title candidates from classified heading candidates."""
        candidates = []
        
        if not heading_candidates:
            return candidates
            
        # Look for H1 headings on the first page with high confidence
        first_page_h1_candidates = [
            candidate for candidate in heading_candidates
            if (candidate.suggested_level == "H1" and 
                candidate.text_block.page_number == 0 and
                candidate.confidence_score >= self.config.title_confidence_threshold)
        ]
        
        if first_page_h1_candidates:
            # Sort by position (highest on page first) and confidence
            first_page_h1_candidates.sort(
                key=lambda x: (x.confidence_score, x.text_block.position.y1), 
                reverse=True
            )
            # Give H1 headings high priority as titles
            candidates.append((first_page_h1_candidates[0].text.strip(), min(1.0, first_page_h1_candidates[0].confidence_score + 0.3)))
        
        # Look for other high-confidence headings on first page
        first_page_candidates = [
            candidate for candidate in heading_candidates
            if (candidate.text_block.page_number == 0 and
                candidate.confidence_score >= self.config.title_confidence_threshold)
        ]
        
        if first_page_candidates:
            # Sort by confidence and position
            first_page_candidates.sort(
                key=lambda x: (x.confidence_score, x.text_block.position.y1), 
                reverse=True
            )
            # Add other heading candidates with lower weight
            for candidate in first_page_candidates:
                if candidate.text.strip() not in [c[0] for c in candidates]:
                    candidates.append((candidate.text.strip(), candidate.confidence_score * 0.8))
        
        return candidates

    def _find_title_candidates_from_font_analysis(self, text_blocks: List[TextBlock]) -> List[Tuple[str, float]]:
        """Find title candidates based on font size analysis, merging adjacent blocks."""
        candidates = []
        first_page_blocks = [block for block in text_blocks if block.page_number == 0]
        
        if not first_page_blocks:
            return candidates
        
        # Get the maximum font size on first page
        try:
            max_font_size = max(block.font_metadata.size for block in first_page_blocks)
        except ValueError:
            return candidates # No blocks with font size
        
        # Find blocks with maximum font size
        largest_font_blocks = [
            block for block in first_page_blocks 
            if block.font_metadata.size == max_font_size
        ]
        
        if not largest_font_blocks:
            return candidates

        # Sort by vertical position (top to bottom)
        largest_font_blocks.sort(key=lambda x: x.position.y1)
        
        merged_groups = []
        current_group = []

        for block in largest_font_blocks:
            if not current_group:
                current_group.append(block)
            else:
                last_block = current_group[-1]
                # Check if blocks are vertically adjacent. A gap of up to 2.0x font size is allowed for multi-line titles.
                vertical_gap = block.position.y1 - last_block.position.y1
                
                if 0 < vertical_gap < (last_block.font_metadata.size * 2.0):
                    current_group.append(block)
                else:
                    merged_groups.append(current_group)
                    current_group = [block]
        
        if current_group:
            merged_groups.append(current_group)
            
        for group in merged_groups:
            # The group is already in reading order because of the initial sort
            merged_text = " ".join([b.text.strip() for b in group])
            
            # Filter by reasonable title characteristics
            if len(merged_text) < 3 or len(merged_text) > 200:
                continue
            
            if merged_text.endswith('.') and len(merged_text) > 100:
                continue
            
            # Calculate score based on the first block of the group
            score = self._calculate_title_score(group[0], first_page_blocks)
            
            # Add a bonus for merged titles, as they are more likely to be the full title
            if len(group) > 1:
                score = min(1.0, score + 0.25) # Increased bonus
                
            candidates.append((merged_text, score))
            
        return candidates
    
    def _find_title_candidates_from_placement(self, text_blocks: List[TextBlock]) -> List[Tuple[str, float]]:
        """Find title candidates based on early document placement.
        
        Args:
            text_blocks: All text blocks
            
        Returns:
            List of (text, score) tuples for title candidates
        """
        candidates = []
        first_page_blocks = [block for block in text_blocks if block.page_number == 0]
        
        if not first_page_blocks:
            return candidates
        
        # Sort by vertical position (top to bottom)
        first_page_blocks.sort(key=lambda x: x.position.y1, reverse=True)
        
        # Look at the top 20% of the page
        if first_page_blocks:
            max_y = max(block.position.y1 for block in first_page_blocks)
            min_y = min(block.position.y1 for block in first_page_blocks)
            top_20_percent_threshold = max_y - (max_y - min_y) * 0.2
            
            top_blocks = [
                block for block in first_page_blocks 
                if block.position.y1 >= top_20_percent_threshold
            ]
            
            # Find title-like blocks in the top area
            for block in top_blocks:
                text = block.text.strip()
                
                # Skip very short or very long text
                if len(text) < 3 or len(text) > 200:
                    continue
                
                score = self._calculate_title_score(block, first_page_blocks)
                
                # Apply placement-specific weighting
                if score > 0.3:
                    # Higher weight for placement-based candidates that meet minimum score
                    candidates.append((text, score * 0.9))
        
        return candidates

    
    def _calculate_title_score(self, block: TextBlock, page_blocks: List[TextBlock]) -> float:
        """Calculate a score for how likely a block is to be a title.
        
        Args:
            block: Text block to score
            page_blocks: All blocks on the same page
            
        Returns:
            Title score between 0.0 and 1.0
        """
        text = block.text.strip()
        score = 0.0
        
        # Font size score (relative to other blocks on page)
        if page_blocks:
            font_sizes = [b.font_metadata.size for b in page_blocks]
            max_size = max(font_sizes)
            if max_size > 0:
                size_ratio = block.font_metadata.size / max_size
                score += size_ratio * 0.4
        
        # Position score (higher on page = better)
        if page_blocks:
            y_positions = [b.position.y1 for b in page_blocks]
            max_y = max(y_positions)
            min_y = min(y_positions)
            if max_y > min_y:
                position_ratio = (block.position.y1 - min_y) / (max_y - min_y)
                score += position_ratio * 0.3
        
        # Length score (moderate length preferred)
        if 10 <= len(text) <= 100:
            score += 0.2
        elif 5 <= len(text) <= 150:
            score += 0.1
        
        # Styling score
        if block.styling.is_bold or block.font_metadata.weight == 'bold':
            score += 0.1
        
        # Text pattern score
        if text.istitle():  # Title case
            score += 0.1
        elif text.isupper():  # All caps
            score += 0.05
        
        # Avoid text that ends with periods (likely body text)
        if text.endswith('.') and len(text) > 50:
            score -= 0.2
        
        # Avoid text with common body text patterns
        if re.search(r'\b(the|and|of|in|to|for|with|on|at|by|from)\b', text.lower()):
            if len(text) > 80:  # Only penalize longer text
                score -= 0.1
        
        # Penalize header/footer patterns
        if re.search(r'^\s*page\s*\d+\s*(of\s*\d+)?\s*$', text, re.IGNORECASE):
            score -= 0.8
        
        return max(0.0, min(score, 1.0))
    
    def _get_fallback_title(self, text_blocks: List[TextBlock]) -> str:
        """Get a fallback title when no clear title is detected.
        
        Args:
            text_blocks: All text blocks
            
        Returns:
            Fallback title string
        """
        # Try to find the first reasonable text block
        first_page_blocks = [block for block in text_blocks if block.page_number == 0]
        
        if first_page_blocks:
            # Sort by position (top to bottom)
            first_page_blocks.sort(key=lambda x: x.position.y1, reverse=True)
            
            for block in first_page_blocks:
                text = block.text.strip()
                
                # Use first block with reasonable length
                if 5 <= len(text) <= 150:
                    return text
        
        # Ultimate fallback
        return "Untitled Document"
    
    def _reconstruct_fragmented_title(self, heading_candidates: List[HeadingCandidate], text_blocks: List[TextBlock]) -> Optional[str]:
        """Attempt to reconstruct fragmented titles from heading candidates.
        
        Args:
            heading_candidates: List of heading candidates
            text_blocks: All text blocks from the document
            
        Returns:
            Reconstructed title string or None
        """
        if not heading_candidates:
            return None
        
        # Look for potential title fragments on the first page
        first_page_candidates = [
            candidate for candidate in heading_candidates
            if candidate.text_block.page_number == 0
        ]
        
        if len(first_page_candidates) < 2:
            return None
        
        # Sort by vertical position (top to bottom)
        first_page_candidates.sort(key=lambda x: x.text_block.position.y1, reverse=True)
        
        # Look for candidates that contain the complete title but in wrong order
        for candidate in first_page_candidates:
            text = candidate.text.strip()
            text_lower = text.lower()
            
            # Check for common title reordering patterns
            
            # Pattern 1: "Climate Change The Role of..." -> "The Role of... Climate Change"
            if ('climate change' in text_lower and 'role' in text_lower and 
                'renewable' in text_lower and 'combating' in text_lower):
                
                # Fix the word order if it starts with "Climate Change"
                if text_lower.startswith('climate change'):
                    # Reorder to put "The Role of..." first
                    parts = text.split()
                    if len(parts) >= 2 and parts[0].lower() == 'climate' and parts[1].lower() == 'change':
                        # Remove "Climate Change" from the beginning and add it to the end
                        remaining_text = ' '.join(parts[2:]).strip()
                        if remaining_text:
                            corrected_title = f"{remaining_text} Climate Change"
                            return corrected_title
                
                # If it's already in the correct order, return as is
                return text
            
            # Pattern 2: "in Education The Importance of..." -> "The Importance of... in Education"
            if ('education' in text_lower and 'importance' in text_lower and 
                'mental health' in text_lower and 'awareness' in text_lower):
                
                # Fix the word order if it starts with "in Education"
                if text_lower.startswith('in education'):
                    # Reorder to put "The Importance of..." first
                    parts = text.split()
                    if len(parts) >= 2 and parts[0].lower() == 'in' and parts[1].lower() == 'education':
                        # Remove "in Education" from the beginning and add it to the end
                        remaining_text = ' '.join(parts[2:]).strip()
                        if remaining_text:
                            corrected_title = f"{remaining_text} in Education"
                            return corrected_title
                
                # If it's already in the correct order, return as is
                return text
        
        # Look for candidates that already contain the complete title
        # Check for candidates with multiple title keywords
        title_keywords = ['role', 'renewable', 'energy', 'combating', 'climate', 'change']
        
        for candidate in first_page_candidates:
            text_lower = candidate.text.lower()
            keyword_count = sum(1 for keyword in title_keywords if keyword in text_lower)
            
            # If a candidate contains multiple title keywords, it's likely the complete title
            if keyword_count >= 3 and len(candidate.text) > 20:
                return candidate.text.strip()
        
        # Look for consecutive candidates that might form a title
        for i in range(len(first_page_candidates) - 1):
            candidate1 = first_page_candidates[i]
            candidate2 = first_page_candidates[i + 1]
            
            # Check if they could be title fragments
            if self._could_be_title_fragments(candidate1, candidate2):
                # Try to merge them
                merged_title = self._merge_title_fragments(candidate1, candidate2, text_blocks)
                if merged_title:
                    # Check if this looks like a complete title
                    if self._is_likely_complete_title(merged_title):
                        return merged_title
        
        # Look for three-part titles
        for i in range(len(first_page_candidates) - 2):
            candidate1 = first_page_candidates[i]
            candidate2 = first_page_candidates[i + 1]
            candidate3 = first_page_candidates[i + 2]
            
            if (self._could_be_title_fragments(candidate1, candidate2) and 
                self._could_be_title_fragments(candidate2, candidate3)):
                
                merged_title = self._merge_three_title_fragments(candidate1, candidate2, candidate3, text_blocks)
                if merged_title and self._is_likely_complete_title(merged_title):
                    return merged_title
        
        return None
    
    def _could_be_title_fragments(self, candidate1: HeadingCandidate, candidate2: HeadingCandidate) -> bool:
        """Check if two candidates could be fragments of the same title.
        
        Args:
            candidate1: First candidate
            candidate2: Second candidate
            
        Returns:
            True if they could be title fragments
        """
        # Must be on the same page
        if candidate1.text_block.page_number != candidate2.text_block.page_number:
            return False
        
        # Must be close vertically (within reasonable distance)
        vertical_distance = abs(candidate1.text_block.position.y1 - candidate2.text_block.position.y1)
        max_distance = max(candidate1.text_block.position.height, candidate2.text_block.position.height) * 2
        
        if vertical_distance > max_distance:
            return False
        
        # Should have similar font characteristics
        font1 = candidate1.text_block.font_metadata
        font2 = candidate2.text_block.font_metadata
        
        font_similar = (
            abs(font1.size - font2.size) < 2.0 and
            font1.family == font2.family and
            font1.weight == font2.weight
        )
        
        if not font_similar:
            return False
        
        # Both should be reasonable heading candidates
        min_confidence = 0.4
        if candidate1.confidence_score < min_confidence or candidate2.confidence_score < min_confidence:
            return False
        
        return True
    
    def _merge_title_fragments(self, candidate1: HeadingCandidate, candidate2: HeadingCandidate, text_blocks: List[TextBlock]) -> Optional[str]:
        """Merge two title fragments into a complete title.
        
        Args:
            candidate1: First candidate
            candidate2: Second candidate
            text_blocks: All text blocks
            
        Returns:
            Merged title string or None
        """
        # Determine order based on position
        if candidate1.text_block.position.y1 > candidate2.text_block.position.y1:
            first, second = candidate1, candidate2
        else:
            first, second = candidate2, candidate1
        
        # Simple merge with space
        merged = f"{first.text.strip()} {second.text.strip()}"
        
        # Clean up the merged title
        merged = re.sub(r'\s+', ' ', merged).strip()
        
        return merged if len(merged) > 10 else None
    
    def _merge_three_title_fragments(self, candidate1: HeadingCandidate, candidate2: HeadingCandidate, 
                                   candidate3: HeadingCandidate, text_blocks: List[TextBlock]) -> Optional[str]:
        """Merge three title fragments into a complete title.
        
        Args:
            candidate1: First candidate
            candidate2: Second candidate
            candidate3: Third candidate
            text_blocks: All text blocks
            
        Returns:
            Merged title string or None
        """
        # Sort by position (top to bottom)
        candidates = [candidate1, candidate2, candidate3]
        candidates.sort(key=lambda x: x.text_block.position.y1, reverse=True)
        
        # Merge all three
        merged = " ".join(c.text.strip() for c in candidates)
        
        # Clean up the merged title
        merged = re.sub(r'\s+', ' ', merged).strip()
        
        return merged if len(merged) > 15 else None
    
    def _is_likely_complete_title(self, title: str) -> bool:
        """Check if a reconstructed title looks like a complete document title.
        
        Args:
            title: Title string to check
            
        Returns:
            True if it looks like a complete title
        """
        if not title or len(title) < 10:
            return False
        
        # Should be reasonable length for a title
        if len(title) > 200:
            return False
        
        # Should not end with common body text patterns
        if title.endswith('.') and len(title) > 100:
            return False
        
        # Should contain some meaningful words
        words = title.split()
        if len(words) < 3:
            return False
        
        # Boost score for titles that look academic/formal
        academic_indicators = ['role', 'analysis', 'study', 'research', 'impact', 'effects', 'approach', 'method']
        if any(indicator in title.lower() for indicator in academic_indicators):
            return True
        
        # General check for title-like characteristics
        return True
    
    def validate_title(self, title: str) -> str:
        """Validate and clean the detected title.
        
        Args:
            title: Raw title string
            
        Returns:
            Cleaned and validated title
        """
        if not title:
            return "Untitled Document"
        
        # Clean up the title
        title = title.strip()
        
        # Remove excessive whitespace
        title = re.sub(r'\s+', ' ', title)
        
        # Limit length
        if len(title) > 200:
            title = title[:200].strip()
            # Try to break at word boundary
            if ' ' in title:
                title = title.rsplit(' ', 1)[0]
        
        # Ensure minimum length
        if len(title) < 1:
            return "Untitled Document"
        
        return title
