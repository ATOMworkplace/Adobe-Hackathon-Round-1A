"""Font analysis utilities for heading classification."""

from typing import List, Dict, Tuple, Set
from collections import defaultdict, Counter
import statistics
import logging

from ..models.data_models import TextBlock, FontMetadata
from ..config import ClassificationConfig


class FontAnalyzer:
    """Analyzes font characteristics for heading classification."""
    
    def __init__(self, config: ClassificationConfig):
        """Initialize font analyzer with configuration.
        
        Args:
            config: Classification configuration
        """
        self.config = config
        self.logger = logging.getLogger(__name__)
    
    def analyze_font_relationships(self, text_blocks: List[TextBlock]) -> Dict[str, any]:
        """Analyze font relationships across all text blocks.
        
        Args:
            text_blocks: List of text blocks to analyze
            
        Returns:
            Dictionary with font analysis results
        """
        if not text_blocks:
            return {}
        
        # Extract font sizes and calculate statistics
        font_sizes = [block.font_metadata.size for block in text_blocks]
        size_stats = self._calculate_size_statistics(font_sizes)
        
        # Analyze font families and weights
        font_families = self._analyze_font_families(text_blocks)
        font_weights = self._analyze_font_weights(text_blocks)
        
        # Calculate relative size rankings
        size_rankings = self._calculate_relative_rankings(text_blocks)
        
        # Identify potential heading fonts
        heading_fonts = self._identify_heading_fonts(text_blocks, size_stats)
        
        return {
            'size_statistics': size_stats,
            'font_families': font_families,
            'font_weights': font_weights,
            'size_rankings': size_rankings,
            'heading_fonts': heading_fonts,
            'total_blocks': len(text_blocks)
        }
    
    def _calculate_size_statistics(self, font_sizes: List[float]) -> Dict[str, float]:
        """Calculate statistical measures for font sizes.
        
        Args:
            font_sizes: List of font sizes
            
        Returns:
            Dictionary with size statistics
        """
        if not font_sizes:
            return {}
        
        return {
            'min_size': min(font_sizes),
            'max_size': max(font_sizes),
            'mean_size': statistics.mean(font_sizes),
            'median_size': statistics.median(font_sizes),
            'std_dev': statistics.stdev(font_sizes) if len(font_sizes) > 1 else 0.0,
            'unique_sizes': len(set(font_sizes))
        }
    
    def _analyze_font_families(self, text_blocks: List[TextBlock]) -> Dict[str, any]:
        """Analyze font family distribution.
        
        Args:
            text_blocks: List of text blocks
            
        Returns:
            Dictionary with font family analysis
        """
        family_counter = Counter(block.font_metadata.family for block in text_blocks)
        total_blocks = len(text_blocks)
        
        family_stats = {}
        for family, count in family_counter.items():
            family_stats[family] = {
                'count': count,
                'percentage': (count / total_blocks) * 100,
                'sizes': list(set(block.font_metadata.size 
                                for block in text_blocks 
                                if block.font_metadata.family == family))
            }
        
        return {
            'families': family_stats,
            'most_common': family_counter.most_common(3),
            'unique_families': len(family_counter)
        }
    
    def _analyze_font_weights(self, text_blocks: List[TextBlock]) -> Dict[str, any]:
        """Analyze font weight distribution.
        
        Args:
            text_blocks: List of text blocks
            
        Returns:
            Dictionary with font weight analysis
        """
        weight_counter = Counter(block.font_metadata.weight for block in text_blocks)
        total_blocks = len(text_blocks)
        
        weight_stats = {}
        for weight, count in weight_counter.items():
            weight_stats[weight] = {
                'count': count,
                'percentage': (count / total_blocks) * 100,
                'avg_size': statistics.mean([block.font_metadata.size 
                                           for block in text_blocks 
                                           if block.font_metadata.weight == weight])
            }
        
        return {
            'weights': weight_stats,
            'bold_percentage': weight_stats.get('bold', {}).get('percentage', 0),
            'normal_percentage': weight_stats.get('normal', {}).get('percentage', 0)
        }
    
    def _calculate_relative_rankings(self, text_blocks: List[TextBlock]) -> Dict[float, int]:
        """Calculate relative size rankings for all font sizes.
        
        Args:
            text_blocks: List of text blocks
            
        Returns:
            Dictionary mapping font sizes to their relative rankings
        """
        # Get unique font sizes and sort in descending order
        unique_sizes = sorted(set(block.font_metadata.size for block in text_blocks), reverse=True)
        
        # Create size to rank mapping (0 = largest)
        size_to_rank = {size: rank for rank, size in enumerate(unique_sizes)}
        
        # Update text blocks with relative rankings
        for block in text_blocks:
            block.font_metadata.relative_size_rank = size_to_rank[block.font_metadata.size]
        
        return size_to_rank
    
    def _identify_heading_fonts(self, text_blocks: List[TextBlock], size_stats: Dict[str, float]) -> Dict[str, any]:
        """Identify fonts that are likely used for headings.
        
        Args:
            text_blocks: List of text blocks
            size_stats: Font size statistics
            
        Returns:
            Dictionary with heading font analysis
        """
        if not size_stats:
            return {}
        
        max_size = size_stats['max_size']
        mean_size = size_stats['mean_size']
        
        # Define thresholds for heading identification
        large_size_threshold = mean_size + (max_size - mean_size) * 0.3
        medium_size_threshold = mean_size + (max_size - mean_size) * 0.1
        
        heading_candidates = {
            'large_fonts': [],  # Potential H1
            'medium_fonts': [], # Potential H2
            'small_fonts': []   # Potential H3
        }
        
        for block in text_blocks:
            size = block.font_metadata.size
            
            # Skip very long text (unlikely to be headings)
            if len(block.text) > self.config.max_heading_length:
                continue
            
            # Skip very short text (unless it's bold)
            if len(block.text) < self.config.min_heading_length and not block.styling.is_bold:
                continue
            
            if size >= large_size_threshold:
                heading_candidates['large_fonts'].append(block)
            elif size >= medium_size_threshold:
                heading_candidates['medium_fonts'].append(block)
            elif block.styling.is_bold or block.font_metadata.weight == 'bold':
                heading_candidates['small_fonts'].append(block)
        
        return {
            'candidates': heading_candidates,
            'thresholds': {
                'large_size_threshold': large_size_threshold,
                'medium_size_threshold': medium_size_threshold
            },
            'total_candidates': sum(len(candidates) for candidates in heading_candidates.values())
        }
    
    def calculate_font_score(self, block: TextBlock, font_analysis: Dict[str, any]) -> float:
        """Calculate a font-based score for heading likelihood.
        
        Args:
            block: Text block to score
            font_analysis: Results from analyze_font_relationships
            
        Returns:
            Font score between 0.0 and 1.0
        """
        if not font_analysis or 'size_statistics' not in font_analysis:
            return 0.0
        
        score = 0.0
        size_stats = font_analysis['size_statistics']
        
        # Size-based scoring (40% weight)
        if size_stats['max_size'] > size_stats['min_size']:
            size_ratio = (block.font_metadata.size - size_stats['min_size']) / (size_stats['max_size'] - size_stats['min_size'])
            score += size_ratio * self.config.font_size_weight
        
        # Weight-based scoring (20% weight)
        if block.styling.is_bold or block.font_metadata.weight == 'bold':
            score += self.config.font_weight_importance
        
        # Relative ranking bonus
        if block.font_metadata.relative_size_rank <= 2:  # Top 3 sizes
            score += 0.1
        
        # Family consistency bonus
        font_families = font_analysis.get('font_families', {})
        if font_families and 'families' in font_families:
            family_info = font_families['families'].get(block.font_metadata.family, {})
            if family_info.get('percentage', 0) < 50:  # Less common fonts might be headings
                score += 0.05
        
        return min(score, 1.0)  # Cap at 1.0
    
    def get_heading_level_suggestion(self, block: TextBlock, font_analysis: Dict[str, any]) -> str:
        """Suggest a heading level based on font characteristics.
        
        Args:
            block: Text block to analyze
            font_analysis: Results from analyze_font_relationships
            
        Returns:
            Suggested heading level (H1, H2, or H3)
        """
        if not font_analysis or 'size_statistics' not in font_analysis:
            return "H3"
        
        size_stats = font_analysis['size_statistics']
        max_size = size_stats['max_size']
        
        # Calculate relative size
        if max_size > 0:
            relative_size = block.font_metadata.size / max_size
        else:
            relative_size = 0.5
        
        # Determine level based on relative size and configuration thresholds
        if relative_size >= self.config.h1_min_relative_size:
            return "H1"
        elif relative_size >= self.config.h2_min_relative_size:
            return "H2"
        else:
            return "H3"