"""JSON output generation service for PDF outline extraction."""

import json
from typing import Dict, Any, List
import logging

from ..models.data_models import DocumentOutline, OutlineEntry
from ..utils.validation import JSONSchemaValidator, UnicodeHandler
from ..exceptions import JSONGenerationError, ValidationError


class JSONGenerator:
    """Generates JSON output according to the required schema."""
    
    def __init__(self):
        """Initialize JSON generator."""
        self.logger = logging.getLogger(__name__)
        self.unicode_handler = UnicodeHandler()
        self.validator = JSONSchemaValidator()
    
    def generate_output(self, outline: DocumentOutline) -> Dict[str, Any]:
        """Generate JSON output from document outline.
        
        Args:
            outline: DocumentOutline object
            
        Returns:
            Dictionary ready for JSON serialization
            
        Raises:
            JSONGenerationError: If output generation fails
        """
        try:
            self.logger.info(f"Generating JSON output for outline with {len(outline.outline)} entries")
            
            # Create the base output structure
            output = {
                "title": self._clean_title(outline.title),
                "outline": []
            }
            
            # Process each outline entry
            for entry in outline.outline:
                formatted_entry = self.format_outline_entry(entry)
                output["outline"].append(formatted_entry)
            
            # Validate the output
            if not self.validate_output_schema(output):
                raise JSONGenerationError("Generated output failed schema validation")
            
            self.logger.info("JSON output generated successfully")
            return output
            
        except Exception as e:
            if isinstance(e, JSONGenerationError):
                raise
            raise JSONGenerationError(f"Failed to generate JSON output: {str(e)}")
    
    def format_outline_entry(self, entry: OutlineEntry) -> Dict[str, Any]:
        """Format a single outline entry for JSON output.
        
        Args:
            entry: OutlineEntry object
            
        Returns:
            Dictionary with formatted entry data
            
        Raises:
            JSONGenerationError: If entry formatting fails
        """
        try:
            # Clean and normalize the text
            cleaned_text = self._clean_text(entry.text)
            
            # Validate the entry data
            if not cleaned_text:
                raise JSONGenerationError(f"Empty text in outline entry on page {entry.page}")
            
            if entry.level not in ["H1", "H2", "H3"]:
                raise JSONGenerationError(f"Invalid heading level: {entry.level}")
            
            if entry.page < 0:
                raise JSONGenerationError(f"Invalid page number: {entry.page}")
            
            return {
                "level": entry.level,
                "text": cleaned_text,
                "page": entry.page
            }
            
        except Exception as e:
            if isinstance(e, JSONGenerationError):
                raise
            raise JSONGenerationError(f"Failed to format outline entry: {str(e)}")
    
    def validate_output_schema(self, output: Dict[str, Any]) -> bool:
        """Validate output against the required JSON schema.
        
        Args:
            output: Dictionary to validate
            
        Returns:
            True if valid
            
        Raises:
            JSONGenerationError: If validation fails
        """
        try:
            return self.validator.validate_json_output(output)
        except ValidationError as e:
            raise JSONGenerationError(f"Schema validation failed: {str(e)}")
    
    def _clean_title(self, title: str) -> str:
        """Clean and normalize the document title.
        
        Args:
            title: Raw title string
            
        Returns:
            Cleaned title string
        """
        if not title:
            return "Untitled Document"
        
        # Use enhanced text cleaning
        cleaned = self.unicode_handler.clean_extracted_text(title)
        
        # Limit length
        if len(cleaned) > 200:
            cleaned = cleaned[:200].strip()
            # Try to break at word boundary
            if ' ' in cleaned:
                cleaned = cleaned.rsplit(' ', 1)[0]
        
        # Ensure we have a valid title
        if not cleaned or len(cleaned.strip()) == 0:
            return "Untitled Document"
        
        return cleaned.strip()
    
    def _clean_text(self, text: str) -> str:
        """Clean and normalize outline entry text.
        
        Args:
            text: Raw text string
            
        Returns:
            Cleaned text string
        """
        if not text:
            return ""
        
        # Use enhanced text cleaning
        cleaned = self.unicode_handler.clean_extracted_text(text)
        
        # Additional artifact removal specific to outline entries
        cleaned = self._remove_text_artifacts(cleaned)
        
        # Limit length for outline entries
        if len(cleaned) > 500:
            cleaned = cleaned[:500].strip()
            # Try to break at word boundary
            if ' ' in cleaned:
                cleaned = cleaned.rsplit(' ', 1)[0]
        
        return cleaned.strip()
    
    def _remove_text_artifacts(self, text: str) -> str:
        """Remove common text artifacts from PDF extraction.
        
        Args:
            text: Text to clean
            
        Returns:
            Cleaned text
        """
        # Remove common PDF artifacts
        artifacts = [
            '\uf0b7',  # Bullet point character
            '\uf0a7',  # Another bullet character
            '\uf020',  # Space character
            '\uf0d8',  # Arrow character
        ]
        
        for artifact in artifacts:
            text = text.replace(artifact, '')
        
        # Remove multiple consecutive dots (often from TOC)
        import re
        text = re.sub(r'\.{3,}', '', text)
        
        # Remove tab characters and normalize spaces
        text = re.sub(r'\t+', ' ', text)
        text = re.sub(r' {2,}', ' ', text)
        
        return text.strip()
    
    def save_to_file(self, output: Dict[str, Any], file_path: str) -> None:
        """Save JSON output to file.
        
        Args:
            output: JSON output dictionary
            file_path: Path to save the file
            
        Raises:
            JSONGenerationError: If file saving fails
        """
        try:
            self.logger.info(f"Saving JSON output to {file_path}")
            
            # Ensure output directory exists
            import os
            os.makedirs(os.path.dirname(file_path), exist_ok=True)
            
            # Write JSON file with proper encoding
            with open(file_path, 'w', encoding='utf-8') as f:
                json.dump(output, f, indent=2, ensure_ascii=False)
            
            self.logger.info(f"JSON output saved successfully to {file_path}")
            
        except Exception as e:
            raise JSONGenerationError(f"Failed to save JSON to {file_path}: {str(e)}")
    
    def generate_and_save(self, outline: DocumentOutline, file_path: str) -> Dict[str, Any]:
        """Generate JSON output and save to file in one operation.
        
        Args:
            outline: DocumentOutline object
            file_path: Path to save the JSON file
            
        Returns:
            Generated JSON output dictionary
            
        Raises:
            JSONGenerationError: If generation or saving fails
        """
        output = self.generate_output(outline)
        self.save_to_file(output, file_path)
        return output
    
    def get_output_statistics(self, output: Dict[str, Any]) -> Dict[str, Any]:
        """Get statistics about the generated JSON output.
        
        Args:
            output: Generated JSON output
            
        Returns:
            Dictionary with output statistics
        """
        if not output or 'outline' not in output:
            return {'valid': False}
        
        outline_entries = output['outline']
        
        if not outline_entries:
            return {
                'valid': True,
                'title_length': len(output.get('title', '')),
                'total_entries': 0,
                'level_counts': {'H1': 0, 'H2': 0, 'H3': 0}
            }
        
        level_counts = {'H1': 0, 'H2': 0, 'H3': 0}
        text_lengths = []
        pages = []
        
        for entry in outline_entries:
            level = entry.get('level', '')
            if level in level_counts:
                level_counts[level] += 1
            
            text = entry.get('text', '')
            text_lengths.append(len(text))
            
            page = entry.get('page', 0)
            pages.append(page)
        
        return {
            'valid': True,
            'title_length': len(output.get('title', '')),
            'total_entries': len(outline_entries),
            'level_counts': level_counts,
            'avg_text_length': sum(text_lengths) / len(text_lengths) if text_lengths else 0,
            'min_text_length': min(text_lengths) if text_lengths else 0,
            'max_text_length': max(text_lengths) if text_lengths else 0,
            'page_range': (min(pages), max(pages)) if pages else (0, 0),
            'unique_pages': len(set(pages)) if pages else 0
        }