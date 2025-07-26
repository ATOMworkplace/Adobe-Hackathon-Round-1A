"""Validation utilities for PDF outline extractor."""

import json
import re
from typing import Dict, Any, List, Optional
import unicodedata

from ..exceptions import ValidationError


class JSONSchemaValidator:
    """Validates JSON output against the required schema."""
    
    REQUIRED_SCHEMA = {
        "type": "object",
        "required": ["title", "outline"],
        "properties": {
            "title": {"type": "string"},
            "outline": {
                "type": "array",
                "items": {
                    "type": "object",
                    "required": ["level", "text", "page"],
                    "properties": {
                        "level": {"type": "string", "enum": ["H1", "H2", "H3"]},
                        "text": {"type": "string"},
                        "page": {"type": "integer", "minimum": 1}
                    }
                }
            }
        }
    }
    
    @staticmethod
    def validate_json_output(data: Dict[str, Any]) -> bool:
        """Validate JSON output against required schema.
        
        Args:
            data: Dictionary to validate
            
        Returns:
            True if valid
            
        Raises:
            ValidationError: If validation fails
        """
        try:
            # Check required top-level fields
            if not isinstance(data, dict):
                raise ValidationError("Output must be a dictionary")
            
            if "title" not in data:
                raise ValidationError("Missing required field: title")
            
            if "outline" not in data:
                raise ValidationError("Missing required field: outline")
            
            # Validate title
            if not isinstance(data["title"], str):
                raise ValidationError("Title must be a string")
            
            if not data["title"].strip():
                raise ValidationError("Title cannot be empty")
            
            # Validate outline
            if not isinstance(data["outline"], list):
                raise ValidationError("Outline must be a list")
            
            for i, entry in enumerate(data["outline"]):
                JSONSchemaValidator._validate_outline_entry(entry, i)
            
            return True
            
        except Exception as e:
            if isinstance(e, ValidationError):
                raise
            raise ValidationError(f"Validation error: {str(e)}")
    
    @staticmethod
    def _validate_outline_entry(entry: Dict[str, Any], index: int) -> None:
        """Validate a single outline entry."""
        if not isinstance(entry, dict):
            raise ValidationError(f"Outline entry {index} must be a dictionary")
        
        # Check required fields
        required_fields = ["level", "text", "page"]
        for field in required_fields:
            if field not in entry:
                raise ValidationError(f"Outline entry {index} missing required field: {field}")
        
        # Validate level
        if entry["level"] not in ["H1", "H2", "H3"]:
            raise ValidationError(f"Outline entry {index} has invalid level: {entry['level']}")
        
        # Validate text
        if not isinstance(entry["text"], str):
            raise ValidationError(f"Outline entry {index} text must be a string")
        
        if not entry["text"].strip():
            raise ValidationError(f"Outline entry {index} text cannot be empty")
        
        # Validate page
        if not isinstance(entry["page"], int):
            raise ValidationError(f"Outline entry {index} page must be an integer")
        
        if entry["page"] < 0:
            raise ValidationError(f"Outline entry {index} page must be non-negative")


class UnicodeHandler:
    """Handles Unicode text processing for multilingual support."""
    
    @staticmethod
    def normalize_text(text: str) -> str:
        """Normalize Unicode text for consistent processing.
        
        Args:
            text: Input text
            
        Returns:
            Normalized text
        """
        if not text:
            return ""
        
        # Normalize Unicode to NFC form
        normalized = unicodedata.normalize('NFC', text)
        
        # Remove control characters but keep line breaks
        cleaned = ''.join(char for char in normalized 
                         if unicodedata.category(char) != 'Cc' or char in '\n\r\t')
        
        return cleaned.strip()
    
    @staticmethod
    def clean_extracted_text(text: str) -> str:
        """Clean text extracted from PDF, removing common artifacts.
        
        Args:
            text: Raw extracted text
            
        Returns:
            Cleaned text
        """
        if not text:
            return ""
        
        # First normalize Unicode
        cleaned = UnicodeHandler.normalize_text(text)
        
        # Remove common PDF extraction artifacts
        artifacts_patterns = [
            r'\(\s*\)',  # Empty parentheses with optional spaces
            r'\(\s*-\s*-\s*\)',  # Parentheses with dashes
            r'\(\s*-+\s*\)',  # Parentheses with multiple dashes
            r'\[\s*\]',  # Empty square brackets
            r'\{\s*\}',  # Empty curly brackets
            r'^\s*[-•·]\s*',  # Leading bullet points
            r'\s+$',  # Trailing whitespace
            r'^\s+',  # Leading whitespace
        ]
        
        for pattern in artifacts_patterns:
            cleaned = re.sub(pattern, '', cleaned)
        
        # Normalize multiple spaces to single space
        cleaned = re.sub(r'\s{2,}', ' ', cleaned)
        
        # Remove standalone punctuation that might be artifacts
        if cleaned.strip() in ['()', '( )', '(-)', '( - )', '( - - )', '[]', '{}', '-', '•', '·']:
            return ""
        
        return cleaned.strip()
    
    @staticmethod
    def is_valid_unicode(text: str) -> bool:
        """Check if text contains valid Unicode characters.
        
        Args:
            text: Text to validate
            
        Returns:
            True if valid Unicode
        """
        try:
            text.encode('utf-8').decode('utf-8')
            return True
        except UnicodeError:
            return False
    
    @staticmethod
    def detect_language_hints(text: str) -> Dict[str, float]:
        """Detect language hints from text characteristics.
        
        Args:
            text: Text to analyze
            
        Returns:
            Dictionary with language hints and confidence scores
        """
        hints = {}
        
        if not text:
            return hints
        
        # Japanese character detection
        japanese_chars = sum(1 for char in text if '\u3040' <= char <= '\u309F' or  # Hiragana
                           '\u30A0' <= char <= '\u30FF' or  # Katakana
                           '\u4E00' <= char <= '\u9FAF')    # Kanji
        
        if japanese_chars > 0:
            hints['japanese'] = japanese_chars / len(text)
        
        # Latin script detection
        latin_chars = sum(1 for char in text if '\u0000' <= char <= '\u007F' or  # Basic Latin
                         '\u0080' <= char <= '\u00FF')    # Latin-1 Supplement
        
        if latin_chars > 0:
            hints['latin'] = latin_chars / len(text)
        
        # Cyrillic detection
        cyrillic_chars = sum(1 for char in text if '\u0400' <= char <= '\u04FF')
        
        if cyrillic_chars > 0:
            hints['cyrillic'] = cyrillic_chars / len(text)
        
        return hints


class DataModelValidator:
    """Validates data model instances."""
    
    @staticmethod
    def validate_font_size(size: float) -> bool:
        """Validate font size is reasonable.
        
        Args:
            size: Font size to validate
            
        Returns:
            True if valid
        """
        return 1.0 <= size <= 200.0
    
    @staticmethod
    def validate_page_number(page: int) -> bool:
        """Validate page number is positive.
        
        Args:
            page: Page number to validate
            
        Returns:
            True if valid
        """
        return isinstance(page, int) and page >= 1
    
    @staticmethod
    def validate_heading_text(text: str) -> bool:
        """Validate heading text is reasonable.
        
        Args:
            text: Heading text to validate
            
        Returns:
            True if valid
        """
        if not text or not isinstance(text, str):
            return False
        
        text = text.strip()
        
        # Check length constraints
        if len(text) < 1 or len(text) > 500:
            return False
        
        # Check for reasonable content (not just whitespace or special chars)
        # Use Unicode-aware character checking
        meaningful_chars = sum(1 for char in text if char.isalnum() or unicodedata.category(char).startswith('L'))
        if meaningful_chars < 1:
            return False
        
        return True
    
    @staticmethod
    def validate_confidence_score(score: float) -> bool:
        """Validate confidence score is in valid range.
        
        Args:
            score: Confidence score to validate
            
        Returns:
            True if valid
        """
        return isinstance(score, (int, float)) and 0.0 <= score <= 1.0


def validate_processing_input(file_path: str) -> bool:
    """Validate input file for processing.
    
    Args:
        file_path: Path to file to validate
        
    Returns:
        True if valid for processing
        
    Raises:
        ValidationError: If validation fails
    """
    import os
    
    if not file_path:
        raise ValidationError("File path cannot be empty")
    
    if not os.path.exists(file_path):
        raise ValidationError(f"File does not exist: {file_path}")
    
    if not os.path.isfile(file_path):
        raise ValidationError(f"Path is not a file: {file_path}")
    
    # Check file extension
    if not file_path.lower().endswith('.pdf'):
        raise ValidationError(f"File must be a PDF: {file_path}")
    
    # Check file size (reasonable limit for processing)
    file_size = os.path.getsize(file_path)
    max_size = 100 * 1024 * 1024  # 100MB limit
    
    if file_size > max_size:
        raise ValidationError(f"File too large: {file_size} bytes (max: {max_size})")
    
    return True