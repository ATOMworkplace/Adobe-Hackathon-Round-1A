"""Configuration management for PDF outline extractor."""

from dataclasses import dataclass
from typing import Dict, Any
import os


@dataclass
class ProcessingConfig:
    """Configuration for PDF processing parameters."""
    max_processing_time_seconds: int = 10
    max_memory_gb: int = 16
    max_cpus: int = 8
    input_directory: str = "/app/input"
    output_directory: str = "/app/output"
    
    # Font analysis thresholds
    min_font_size_threshold: float = 8.0
    max_font_size_threshold: float = 72.0
    
    # Heading classification parameters
    heading_confidence_threshold: float = 0.6
    title_confidence_threshold: float = 0.8
    
    # Performance optimization
    enable_caching: bool = True
    batch_size: int = 1  # Process one file at a time for memory efficiency


@dataclass
class ClassificationConfig:
    """Configuration for heading classification algorithms."""
    # Font size analysis weights
    font_size_weight: float = 0.4
    font_weight_importance: float = 0.2
    position_weight: float = 0.2
    whitespace_weight: float = 0.1
    text_length_weight: float = 0.1
    
    # Hierarchy level thresholds
    h1_min_relative_size: float = 0.8  # Relative to largest font
    h2_min_relative_size: float = 0.6
    h3_min_relative_size: float = 0.4
    
    # Text pattern analysis
    max_heading_length: int = 200
    min_heading_length: int = 3
    
    # Confidence thresholds - adaptive based on document context
    heading_confidence_threshold: float = 0.3  # Base threshold
    title_confidence_threshold: float = 0.5
    title_consensus_threshold: float = 0.9  # Threshold for consensus boosting
    
    # Fragment merging thresholds
    fragment_merge_threshold: float = 0.2  # Lower threshold for fragments that can be merged
    same_line_bonus: float = 0.15  # Bonus for same-line text fragments


class ConfigManager:
    """Manages application configuration."""
    
    def __init__(self):
        self.processing_config = ProcessingConfig()
        self.classification_config = ClassificationConfig()
        self._load_environment_overrides()
    
    def _load_environment_overrides(self):
        """Load configuration overrides from environment variables."""
        # Processing config overrides
        if os.getenv('MAX_PROCESSING_TIME'):
            self.processing_config.max_processing_time_seconds = int(os.getenv('MAX_PROCESSING_TIME'))
        
        if os.getenv('INPUT_DIR'):
            self.processing_config.input_directory = os.getenv('INPUT_DIR')
            
        if os.getenv('OUTPUT_DIR'):
            self.processing_config.output_directory = os.getenv('OUTPUT_DIR')
        
        # Classification config overrides
        if os.getenv('HEADING_CONFIDENCE_THRESHOLD'):
            self.classification_config.heading_confidence_threshold = float(os.getenv('HEADING_CONFIDENCE_THRESHOLD'))
    
    def get_processing_config(self) -> ProcessingConfig:
        """Get processing configuration."""
        return self.processing_config
    
    def get_classification_config(self) -> ClassificationConfig:
        """Get classification configuration."""
        return self.classification_config
