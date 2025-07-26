"""Heading classification service using multi-factor analysis."""

import re
import math
from typing import List, Dict, Tuple, Optional
import logging

from ..models.data_models import TextBlock, HeadingCandidate
from ..config import ClassificationConfig
from ..services.font_analyzer import FontAnalyzer
from ..utils.validation import UnicodeHandler


class HeadingClassifier:
    """Multi-factor heading classification system."""
    
    def __init__(self, classification_config: ClassificationConfig):
        """Initialize heading classifier.
        
        Args:
            classification_config: Configuration for classification parameters
        """
        self.config = classification_config
        self.font_analyzer = FontAnalyzer(classification_config)
        self.unicode_handler = UnicodeHandler()
        self.logger = logging.getLogger(__name__)
    
    def classify_text_blocks(self, blocks: List[TextBlock]) -> List[HeadingCandidate]:
        """Classify text blocks to identify potential headings.
        
        Args:
            blocks: List of text blocks to classify
            
        Returns:
            List of heading candidates with confidence scores
        """
        if not blocks:
            return []
        
        self.logger.info(f"Classifying {len(blocks)} text blocks for headings")
        
        # Analyze font relationships across all blocks
        font_analysis = self.font_analyzer.analyze_font_relationships(blocks)
        
        # Create document context for classification
        document_context = self._create_document_context(blocks, font_analysis)
        
        # Classify each block with adaptive thresholds
        heading_candidates = []
        potential_fragments = []  # Store low-confidence candidates that might be fragments
        
        for block in blocks:
            confidence_score = self.calculate_heading_score(block, document_context)
            
            # Create classification factors breakdown
            factors = self._calculate_classification_factors(block, document_context)
            
            # Determine if this could be a fragment of a larger heading
            is_potential_fragment = self._is_potential_fragment(block, factors)
            
            # Use adaptive threshold based on fragment potential
            threshold = (self.config.fragment_merge_threshold if is_potential_fragment 
                        else self.config.heading_confidence_threshold)
            
            if confidence_score >= threshold:
                # Create temporary candidate for level determination
                temp_candidate = HeadingCandidate(
                    text_block=block,
                    confidence_score=confidence_score,
                    classification_factors=factors
                )
                
                # Determine heading level
                suggested_level = self.determine_heading_level(temp_candidate, document_context)
                
                candidate = HeadingCandidate(
                    text_block=block,
                    confidence_score=confidence_score,
                    classification_factors=factors,
                    suggested_level=suggested_level
                )
                
                if is_potential_fragment:
                    potential_fragments.append(candidate)
                else:
                    heading_candidates.append(candidate)
        
        # Merge potential fragments with main candidates
        heading_candidates.extend(potential_fragments)
        
        # Post-process to merge potential heading fragments
        heading_candidates = self._merge_heading_fragments(heading_candidates)
        
        # Additional post-processing: merge same-line candidates with identical formatting
        heading_candidates = self._merge_same_line_candidates(heading_candidates)
        
        # Sort by confidence score (highest first)
        heading_candidates.sort(key=lambda x: x.confidence_score, reverse=True)
        
        self.logger.info(f"Found {len(heading_candidates)} heading candidates")
        return heading_candidates
    
    def calculate_heading_score(self, block: TextBlock, context: Dict[str, any]) -> float:
        """Calculate comprehensive heading score for a text block.
        
        Args:
            block: Text block to score
            context: Document context information
            
        Returns:
            Confidence score between 0.0 and 1.0
        """
        # Font-based scoring
        font_score = self._calculate_font_score(block, context)
        
        # Position-based scoring
        position_score = self._calculate_position_score(block, context)
        
        # Whitespace pattern scoring
        whitespace_score = self._calculate_whitespace_score(block, context)
        
        # Text pattern scoring
        text_score = self._calculate_text_pattern_score(block)
        
        # Length-based scoring
        length_score = self._calculate_length_score(block)
        
        # Combine scores with configured weights
        total_score = (
            font_score * self.config.font_size_weight +
            position_score * self.config.position_weight +
            whitespace_score * self.config.whitespace_weight +
            text_score * self.config.text_length_weight +
            length_score * 0.1  # Small weight for length
        )
        
        return min(total_score, 1.0)
    
    def determine_heading_level(self, candidate: HeadingCandidate, hierarchy_context: Dict[str, any]) -> str:
        """Determine the appropriate heading level for a candidate using a scoring system."""
        block = candidate.text_block
        factors = candidate.classification_factors
        
        h1_score, h2_score, h3_score = 0.0, 0.0, 0.0

        # Base score from confidence
        base_score = candidate.confidence_score
        h1_score += base_score
        h2_score += base_score
        h3_score += base_score

        # Font size contribution
        font_rank = factors.get('relative_size_rank', 10)
        if font_rank == 0:
            h1_score += 0.6
        elif font_rank == 1:
            h2_score += 0.5
            h1_score += 0.2
        elif font_rank == 2:
            h3_score += 0.5
            h2_score += 0.2
        else:
            h3_score += 0.2

        # Position on page
        if block.page_number == 0 and block.position.y1 > 700:
            h1_score += 0.4 # Stronger bonus for being at the top of the first page

        # Text patterns
        text_lower = block.text.lower()
        if any(word in text_lower for word in ['introduction', 'conclusion', 'abstract']):
            h1_score += 0.2
            h2_score -= 0.1
        if re.match(r'^\d+\.\d+', text_lower): # e.g., 1.1, 2.3
            h2_score += 0.3
            h3_score += 0.2
            h1_score -= 0.3
        elif re.match(r'^\d+\.', text_lower): # e.g., 1., 2.
            h1_score += 0.15
            h2_score += 0.15

        # Penalize "Page X of Y" and other common footer/header text
        if re.search(r'^\s*page\s*\d+\s*(of\s*\d+)?\s*$', text_lower, re.IGNORECASE):
            h1_score -= 2.0
            h2_score -= 2.0
            h3_score -= 2.0
        
        # Determine best level
        scores = {"H1": h1_score, "H2": h2_score, "H3": h3_score}
        
        # If all scores are low, it's likely not a heading of any importance
        if max(scores.values()) < self.config.heading_confidence_threshold:
            return "Body"

        return max(scores, key=scores.get)
    
    def _create_document_context(self, blocks: List[TextBlock], font_analysis: Dict[str, any]) -> Dict[str, any]:
        """Create document context for classification.
        
        Args:
            blocks: All text blocks in document
            font_analysis: Font analysis results
            
        Returns:
            Document context dictionary
        """
        # Calculate page statistics
        pages = set(block.page_number for block in blocks)
        
        # Calculate position statistics
        y_positions = [block.position.y1 for block in blocks]
        x_positions = [block.position.x0 for block in blocks]
        
        return {
            'font_analysis': font_analysis,
            'total_blocks': len(blocks),
            'total_pages': len(pages),
            'page_range': (min(pages), max(pages)) if pages else (1, 1),
            'y_position_range': (min(y_positions), max(y_positions)) if y_positions else (0, 0),
            'x_position_range': (min(x_positions), max(x_positions)) if x_positions else (0, 0),
            'blocks_by_page': self._group_blocks_by_page(blocks)
        }
    
    def _group_blocks_by_page(self, blocks: List[TextBlock]) -> Dict[int, List[TextBlock]]:
        """Group text blocks by page number.
        
        Args:
            blocks: List of text blocks
            
        Returns:
            Dictionary mapping page numbers to lists of blocks
        """
        blocks_by_page = {}
        for block in blocks:
            if block.page_number not in blocks_by_page:
                blocks_by_page[block.page_number] = []
            blocks_by_page[block.page_number].append(block)
        
        return blocks_by_page
    
    def _calculate_font_score(self, block: TextBlock, context: Dict[str, any]) -> float:
        """Calculate font-based heading score."""
        return self.font_analyzer.calculate_font_score(block, context.get('font_analysis', {}))
    
    def _calculate_position_score(self, block: TextBlock, context: Dict[str, any]) -> float:
        """Calculate position-based heading score.
        
        Args:
            block: Text block to score
            context: Document context
            
        Returns:
            Position score between 0.0 and 1.0
        """
        score = 0.0
        
        # Y-position scoring (higher on page = higher score)
        y_range = context.get('y_position_range', (0, 0))
        if y_range[1] > y_range[0]:
            y_ratio = (block.position.y1 - y_range[0]) / (y_range[1] - y_range[0])
            score += y_ratio * 0.3
        
        # Left alignment bonus (headings often start at left margin)
        x_range = context.get('x_position_range', (0, 0))
        if x_range[1] > x_range[0]:
            # Bonus for being close to left margin
            left_margin_distance = (block.position.x0 - x_range[0]) / (x_range[1] - x_range[0])
            if left_margin_distance < 0.1:  # Within 10% of left margin
                score += 0.2
        
        # First page bonus
        if block.page_number == 0:
            score += 0.1
        
        return min(score, 1.0)
    
    def _calculate_whitespace_score(self, block: TextBlock, context: Dict[str, any]) -> float:
        """Calculate whitespace pattern score.
        
        Args:
            block: Text block to score
            context: Document context
            
        Returns:
            Whitespace score between 0.0 and 1.0
        """
        score = 0.0
        
        # Get blocks on the same page
        page_blocks = context.get('blocks_by_page', {}).get(block.page_number, [])
        
        if len(page_blocks) > 1:
            # Sort blocks by vertical position (top to bottom)
            sorted_blocks = sorted(page_blocks, key=lambda b: b.position.y1, reverse=True)
            
            # Find current block index
            try:
                current_index = next(i for i, b in enumerate(sorted_blocks) if b == block)
                
                # Check spacing above and below
                if current_index > 0:
                    above_block = sorted_blocks[current_index - 1]
                    space_above = above_block.position.y0 - block.position.y1
                    if space_above > 10:  # Significant space above
                        score += 0.3
                
                if current_index < len(sorted_blocks) - 1:
                    below_block = sorted_blocks[current_index + 1]
                    space_below = block.position.y0 - below_block.position.y1
                    if space_below > 10:  # Significant space below
                        score += 0.3
                        
            except StopIteration:
                pass
        
        return min(score, 1.0)
    
    def _calculate_text_pattern_score(self, block: TextBlock) -> float:
        """Calculate text pattern-based score.
        
        Args:
            block: Text block to score
            
        Returns:
            Text pattern score between 0.0 and 1.0
        """
        text = block.text.strip()
        score = 0.0
        
        # Filter out common PDF artifacts first
        import re
        # Remove extra spaces and check against artifact patterns
        normalized_text = re.sub(r'\s+', ' ', text).strip()
        artifact_patterns = ['( )', '( - )', '( - - )', '(-)', '[]', '{}', '...', '..', '.', '( )', '()', '( - )', '(-)', '( -- )', '(--)', '( --- )', '(---)']
        if normalized_text in artifact_patterns:
            return 0.0
        
        # Also check with regex patterns for more flexible matching
        artifact_regex_patterns = [
            r'^\(\s*\)$',  # Empty parentheses with optional spaces
            r'^\(\s*-+\s*\)$',  # Parentheses with dashes
            r'^\[\s*\]$',  # Empty square brackets
            r'^\{\s*\}$',  # Empty curly brackets
            r'^\.+$',  # Only dots
            r'^-+$',  # Only dashes
        ]
        
        for pattern in artifact_regex_patterns:
            if re.match(pattern, text):
                return 0.0
        
        # Filter out meaningless fragments
        if len(text) <= 2:
            # Very short text - only allow if it's a meaningful short heading
            # Use Unicode-aware checking for letters and digits
            import unicodedata
            if any(unicodedata.category(c).startswith('L') for c in text) and text.isupper():  # Like "A", "I", etc.
                score += 0.1
            elif text.isdigit():  # Like "1", "2", etc.
                score += 0.1
            else:
                return 0.0  # Reject single characters, symbols, fragments
        
        # Reject pure symbol fragments - use Unicode-aware checking
        import unicodedata
        has_meaningful_chars = any(c.isalnum() or unicodedata.category(c).startswith('L') for c in text)
        if not has_meaningful_chars:
            return 0.0
        
        # Check for multiple sentences (likely body text)
        sentence_count = text.count('。') + text.count('.') + text.count('!') + text.count('?')
        if sentence_count > 1:
            return 0.0  # Multiple sentences = body text, not heading
        
        # Length-based scoring - be more strict with very long text
        if len(text) > 150:
            # Very long text is likely body text
            if len(text) > 200:
                return 0.0  # Definitely body text
            score -= 0.3  # Penalize long text
        elif self.config.min_heading_length <= len(text) <= 100:
            score += 0.3
        elif len(text) <= self.config.max_heading_length:
            # Gradually decrease score for longer text
            score += 0.2
        
        # Capitalization patterns
        if text.isupper():
            score += 0.2  # All caps might be a heading
        elif text.istitle():
            score += 0.3  # Title case is common for headings
        elif text[0].isupper() if text else False:
            score += 0.1  # At least starts with capital
        
        # Punctuation patterns
        if not text.endswith('.'):
            score += 0.2  # Headings typically don't end with periods
        
        # Number patterns (e.g., "1. Introduction", "Chapter 2")
        if re.match(r'^\d+\.?\s+', text) or re.match(r'^Chapter\s+\d+', text, re.IGNORECASE):
            score += 0.3
        
        # Common heading words
        heading_words = ['introduction', 'conclusion', 'abstract', 'summary', 'chapter', 'section', 'appendix']
        text_lower = text.lower()
        if any(word in text_lower for word in heading_words):
            score += 0.2
        
        # Bonus for complete words vs fragments
        word_count = len(text.split())
        if word_count >= 2:  # Multi-word headings are more likely to be real
            score += 0.1
        
        # Penalty for text that looks like body content
        if len(text) > 100:  # Long text is less likely to be a heading
            # Check for sentence-like patterns
            has_articles = any(word.lower() in ['the', 'a', 'an', 'and', 'or', 'but', 'in', 'on', 'at', 'to', 'for', 'of', 'with'] 
                             for word in text.split()[:10])  # Check first 10 words
            if has_articles:
                score -= 0.3  # Strong penalty for body text patterns
        
        return min(score, 1.0)
    
    def _calculate_length_score(self, block: TextBlock) -> float:
        """Calculate length-based score (shorter text more likely to be headings).
        
        Args:
            block: Text block to score
            
        Returns:
            Length score between 0.0 and 1.0
        """
        text_length = len(block.text.strip())
        
        if text_length == 0:
            return 0.0
        
        # Optimal heading length range
        if self.config.min_heading_length <= text_length <= 50:
            return 1.0
        elif text_length <= self.config.max_heading_length:
            # Gradually decrease score for longer text
            return max(0.0, 1.0 - (text_length - 50) / (self.config.max_heading_length - 50))
        else:
            return 0.0
    
    def _calculate_classification_factors(self, block: TextBlock, context: Dict[str, any]) -> Dict[str, float]:
        """Calculate detailed classification factors for debugging.
        
        Args:
            block: Text block being classified
            context: Document context
            
        Returns:
            Dictionary with individual factor scores
        """
        return {
            'font_score': self._calculate_font_score(block, context),
            'position_score': self._calculate_position_score(block, context),
            'whitespace_score': self._calculate_whitespace_score(block, context),
            'text_pattern_score': self._calculate_text_pattern_score(block),
            'length_score': self._calculate_length_score(block),
            'font_size': block.font_metadata.size,
            'relative_size_rank': block.font_metadata.relative_size_rank,
            'is_bold': block.styling.is_bold,
            'text_length': len(block.text.strip())
        }
    
    def _merge_heading_fragments(self, candidates: List[HeadingCandidate]) -> List[HeadingCandidate]:
        """Merge heading candidates that appear to be fragments of the same heading.
        
        Args:
            candidates: List of heading candidates
            
        Returns:
            List of candidates with fragments merged
        """
        if not candidates:
            return candidates
        
        # Sort by page and position for processing
        sorted_candidates = sorted(candidates, key=lambda c: (
            c.text_block.page_number,
            c.text_block.position.y1,  # Top to bottom
            c.text_block.position.x0   # Left to right
        ))
        
        merged_candidates = []
        i = 0
        
        while i < len(sorted_candidates):
            current = sorted_candidates[i]
            merge_group = [current]
            
            # Look for candidates to merge with current
            j = i + 1
            while j < len(sorted_candidates):
                next_candidate = sorted_candidates[j]
                
                if self._should_merge_heading_candidates(current, next_candidate):
                    merge_group.append(next_candidate)
                    j += 1
                else:
                    break
            
            # Merge the group if it has multiple candidates
            if len(merge_group) > 1:
                merged_candidate = self._merge_candidate_group(merge_group)
                merged_candidates.append(merged_candidate)
            else:
                merged_candidates.append(current)
            
            i = j if j > i + 1 else i + 1
        
        return merged_candidates
    
    def _should_merge_heading_candidates(self, candidate1: HeadingCandidate, candidate2: HeadingCandidate) -> bool:
        """Determine if two heading candidates should be merged.
        
        Args:
            candidate1: First candidate
            candidate2: Second candidate
            
        Returns:
            True if candidates should be merged
        """
        block1 = candidate1.text_block
        block2 = candidate2.text_block
        
        # Must be on same page
        if block1.page_number != block2.page_number:
            return False
        
        # Must have similar font characteristics
        same_font = (
            block1.font_metadata.family == block2.font_metadata.family and
            abs(block1.font_metadata.size - block2.font_metadata.size) < 1.0 and
            block1.font_metadata.weight == block2.font_metadata.weight
        )
        
        if not same_font:
            return False
        
        # Must be horizontally close (same line or very close)
        horizontal_gap = block2.position.x0 - block1.position.x1
        if horizontal_gap > 50:  # More than 50 points apart
            return False
        
        # Must be vertically aligned (same line)
        vertical_center1 = (block1.position.y0 + block1.position.y1) / 2
        vertical_center2 = (block2.position.y0 + block2.position.y1) / 2
        vertical_tolerance = max(block1.position.height, block2.position.height) * 0.3
        
        if abs(vertical_center1 - vertical_center2) > vertical_tolerance:
            return False
        
        # At least one should be a short fragment (likely part of a larger heading)
        text1_short = len(block1.text.strip()) <= 5
        text2_short = len(block2.text.strip()) <= 5
        
        return text1_short or text2_short
    
    def _merge_candidate_group(self, candidates: List[HeadingCandidate]) -> HeadingCandidate:
        """Merge a group of heading candidates into a single candidate.
        
        Args:
            candidates: List of candidates to merge
            
        Returns:
            Single merged candidate
        """
        if len(candidates) == 1:
            return candidates[0]
        
        # Sort by horizontal position
        candidates.sort(key=lambda c: c.text_block.position.x0)
        
        # Combine text with appropriate spacing
        combined_text_parts = []
        for i, candidate in enumerate(candidates):
            text = candidate.text_block.text.strip()
            if text:
                if i > 0:
                    # Add space between fragments
                    prev_candidate = candidates[i-1]
                    gap = candidate.text_block.position.x0 - prev_candidate.text_block.position.x1
                    if gap > 5:  # Add space for significant gaps
                        combined_text_parts.append(" ")
                combined_text_parts.append(text)
        
        combined_text = "".join(combined_text_parts)
        
        # Use the first candidate as base and update its text
        base_candidate = candidates[0]
        base_candidate.text_block.text = combined_text
        
        # Update bounding box to encompass all fragments
        min_x0 = min(c.text_block.position.x0 for c in candidates)
        min_y0 = min(c.text_block.position.y0 for c in candidates)
        max_x1 = max(c.text_block.position.x1 for c in candidates)
        max_y1 = max(c.text_block.position.y1 for c in candidates)
        
        base_candidate.text_block.position.x0 = min_x0
        base_candidate.text_block.position.y0 = min_y0
        base_candidate.text_block.position.x1 = max_x1
        base_candidate.text_block.position.y1 = max_y1
        base_candidate.text_block.position.width = max_x1 - min_x0
        base_candidate.text_block.position.height = max_y1 - min_y0
        
        # Use the highest confidence score
        base_candidate.confidence_score = max(c.confidence_score for c in candidates)
        
        return base_candidate
    
    def _merge_same_line_candidates(self, candidates: List[HeadingCandidate]) -> List[HeadingCandidate]:
        """Merge heading candidates that are on the same line with identical formatting.
        
        Args:
            candidates: List of heading candidates
            
        Returns:
            List of candidates with same-line fragments merged
        """
        if not candidates:
            return candidates
        
        # Sort by page and position
        sorted_candidates = sorted(candidates, key=lambda c: (
            c.text_block.page_number,
            c.text_block.position.y1,  # Top to bottom
            c.text_block.position.x0   # Left to right
        ))
        
        merged_candidates = []
        i = 0
        
        while i < len(sorted_candidates):
            current = sorted_candidates[i]
            same_line_group = [current]
            
            # Look for candidates on the same line with identical formatting
            j = i + 1
            while j < len(sorted_candidates):
                next_candidate = sorted_candidates[j]
                
                if self._are_same_line_candidates(current, next_candidate):
                    same_line_group.append(next_candidate)
                    j += 1
                else:
                    break
            
            # Merge the group if it has multiple candidates
            if len(same_line_group) > 1:
                merged_candidate = self._merge_same_line_group(same_line_group)
                merged_candidates.append(merged_candidate)
            else:
                merged_candidates.append(current)
            
            i = j if j > i + 1 else i + 1
        
        return merged_candidates
    
    def _are_same_line_candidates(self, candidate1: HeadingCandidate, candidate2: HeadingCandidate) -> bool:
        """Check if two candidates are on the same line with identical formatting.
        
        Args:
            candidate1: First candidate
            candidate2: Second candidate
            
        Returns:
            True if candidates should be merged
        """
        block1 = candidate1.text_block
        block2 = candidate2.text_block
        
        # Must be on same page
        if block1.page_number != block2.page_number:
            return False
        
        # Must have identical font characteristics
        identical_font = (
            block1.font_metadata.family == block2.font_metadata.family and
            abs(block1.font_metadata.size - block2.font_metadata.size) < 0.1 and
            block1.font_metadata.weight == block2.font_metadata.weight and
            block1.font_metadata.style == block2.font_metadata.style
        )
        
        if not identical_font:
            return False
        
        # Must be on the same line (very strict)
        avg_line_height = (block1.position.height + block2.position.height) / 2
        vertical_diff = abs(block1.position.y1 - block2.position.y1)
        same_line = vertical_diff < avg_line_height * 0.1
        
        if not same_line:
            return False
        
        # Must be horizontally adjacent (reasonable gap)
        horizontal_gap = block2.position.x0 - block1.position.x1
        reasonable_gap = -10 <= horizontal_gap <= 100  # Allow small overlap or reasonable gap
        
        return reasonable_gap
    
    def _merge_same_line_group(self, candidates: List[HeadingCandidate]) -> HeadingCandidate:
        """Merge a group of same-line candidates into a single candidate.
        
        Args:
            candidates: List of candidates to merge
            
        Returns:
            Single merged candidate
        """
        if len(candidates) == 1:
            return candidates[0]
        
        # Sort by horizontal position
        candidates.sort(key=lambda c: c.text_block.position.x0)
        
        # Combine text with appropriate spacing
        combined_text_parts = []
        for i, candidate in enumerate(candidates):
            text = candidate.text_block.text.strip()
            if text:
                if i > 0:
                    # Add space between fragments - always add space for readability
                    combined_text_parts.append(" ")
                combined_text_parts.append(text)
        
        combined_text = "".join(combined_text_parts)
        
        # Use the first candidate as base and update its text
        base_candidate = candidates[0]
        base_candidate.text_block.text = combined_text
        
        # Update bounding box to encompass all fragments
        min_x0 = min(c.text_block.position.x0 for c in candidates)
        min_y0 = min(c.text_block.position.y0 for c in candidates)
        max_x1 = max(c.text_block.position.x1 for c in candidates)
        max_y1 = max(c.text_block.position.y1 for c in candidates)
        
        base_candidate.text_block.position.x0 = min_x0
        base_candidate.text_block.position.y0 = min_y0
        base_candidate.text_block.position.x1 = max_x1
        base_candidate.text_block.position.y1 = max_y1
        base_candidate.text_block.position.width = max_x1 - min_x0
        base_candidate.text_block.position.height = max_y1 - min_y0
        
        # Use the highest confidence score
        base_candidate.confidence_score = max(c.confidence_score for c in candidates)
        
        return base_candidate    

    def _is_potential_fragment(self, block: TextBlock, factors: Dict[str, float]) -> bool:
        """Determine if a text block is potentially a fragment of a larger heading.
        
        Args:
            block: Text block to analyze
            factors: Classification factors
            
        Returns:
            True if this could be a fragment
        """
        text = block.text.strip()
        
        # Short text with good font characteristics might be a fragment
        is_short = len(text) <= 15
        has_good_font = factors.get('font_score', 0) > 0.15
        has_good_position = factors.get('position_score', 0) > 0.05
        
        # Text that looks like it could be part of a larger heading
        looks_like_fragment = (
            is_short and 
            has_good_font and 
            (has_good_position or factors.get('whitespace_score', 0) > 0.1)
        )
        
        # Also consider text that has heading-like font size but low overall score
        large_font_low_score = (
            factors.get('font_size', 0) > 15 and  # Reasonably large font
            factors.get('relative_size_rank', 10) <= 3 and  # Top 3 font sizes
            0.2 <= factors.get('font_score', 0) < 0.4  # Good font score but not excellent
        )
        
        return looks_like_fragment or large_font_low_score
