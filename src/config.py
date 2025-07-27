from dataclasses import dataclass

@dataclass
class ProcessingConfig:
    input_directory: str = "/app/input"
    output_directory: str = "/app/output"
    header_footer_margin: int = 50

@dataclass
class ClassificationConfig:
    min_heading_length: int = 3
    max_heading_words: int = 30
    title_max_words: int = 30
    heading_confidence_threshold: float = 0.55
    
    w_font_size: float = 0.40
    w_style: float = 0.25
    w_pattern: float = 0.35

class ConfigManager:
    def __init__(self):
        self.processing_config = ProcessingConfig()
        self.classification_config = ClassificationConfig()
    
    def get_processing_config(self) -> ProcessingConfig:
        return self.processing_config
    
    def get_classification_config(self) -> ClassificationConfig:
        return self.classification_config