"""Comprehensive error handling for PDF outline extraction."""

import logging
from typing import Dict, Any, Optional, Callable
from enum import Enum
from dataclasses import dataclass

from ..exceptions import (
    PDFProcessingError, PDFParsingError, TextExtractionError,
    HeadingClassificationError, JSONGenerationError, PerformanceError
)


class RecoveryAction(Enum):
    """Recovery actions for different error types."""
    SKIP_FILE = "skip_file"
    USE_FALLBACK = "use_fallback"
    MINIMAL_OUTPUT = "minimal_output"
    PARTIAL_RESULTS = "partial_results"
    RETRY = "retry"
    ABORT = "abort"


@dataclass
class ErrorContext:
    """Context information for error handling."""
    operation: str
    file_path: Optional[str] = None
    stage: Optional[str] = None
    additional_info: Optional[Dict[str, Any]] = None


class ErrorHandler:
    """Comprehensive error handling system for PDF processing."""
    
    def __init__(self):
        """Initialize error handler."""
        self.logger = logging.getLogger(__name__)
        self.error_counts = {
            'pdf_parsing': 0,
            'text_extraction': 0,
            'classification': 0,
            'json_generation': 0,
            'performance': 0,
            'unknown': 0
        }
    
    def handle_error(self, error: Exception, context: ErrorContext) -> RecoveryAction:
        """Handle an error and determine recovery action.
        
        Args:
            error: Exception that occurred
            context: Context information about the error
            
        Returns:
            RecoveryAction to take
        """
        error_type = type(error).__name__
        self.logger.error(f"Error in {context.operation}: {error_type} - {str(error)}")
        
        # Log context information
        if context.file_path:
            self.logger.error(f"File: {context.file_path}")
        if context.stage:
            self.logger.error(f"Stage: {context.stage}")
        if context.additional_info:
            self.logger.error(f"Additional info: {context.additional_info}")
        
        # Determine recovery action based on error type
        if isinstance(error, PDFParsingError):
            return self.handle_pdf_parsing_error(error, context)
        elif isinstance(error, TextExtractionError):
            return self.handle_text_extraction_error(error, context)
        elif isinstance(error, HeadingClassificationError):
            return self.handle_classification_error(error, context)
        elif isinstance(error, JSONGenerationError):
            return self.handle_json_generation_error(error, context)
        elif isinstance(error, PerformanceError):
            return self.handle_performance_error(error, context)
        else:
            return self.handle_unknown_error(error, context)
    
    def handle_pdf_parsing_error(self, error: PDFParsingError, context: ErrorContext) -> RecoveryAction:
        """Handle PDF parsing errors.
        
        Args:
            error: PDF parsing error
            context: Error context
            
        Returns:
            Recovery action
        """
        self.error_counts['pdf_parsing'] += 1
        
        # Check if file is corrupted or encrypted
        error_msg = str(error).lower()
        if 'encrypted' in error_msg:
            self.logger.error("PDF is encrypted - skipping file")
            return RecoveryAction.SKIP_FILE
        elif 'corrupted' in error_msg or 'invalid' in error_msg:
            self.logger.error("PDF is corrupted - skipping file")
            return RecoveryAction.SKIP_FILE
        else:
            self.logger.error("PDF parsing failed - skipping file")
            return RecoveryAction.SKIP_FILE
    
    def handle_text_extraction_error(self, error: TextExtractionError, context: ErrorContext) -> RecoveryAction:
        """Handle text extraction errors.
        
        Args:
            error: Text extraction error
            context: Error context
            
        Returns:
            Recovery action
        """
        self.error_counts['text_extraction'] += 1
        
        # Try fallback extraction method
        self.logger.warning("Text extraction failed, attempting fallback method")
        return RecoveryAction.USE_FALLBACK
    
    def handle_classification_error(self, error: HeadingClassificationError, context: ErrorContext) -> RecoveryAction:
        """Handle heading classification errors.
        
        Args:
            error: Classification error
            context: Error context
            
        Returns:
            Recovery action
        """
        self.error_counts['classification'] += 1
        
        # Generate minimal outline with basic font-size classification
        self.logger.warning("Heading classification failed, generating minimal outline")
        return RecoveryAction.MINIMAL_OUTPUT
    
    def handle_json_generation_error(self, error: JSONGenerationError, context: ErrorContext) -> RecoveryAction:
        """Handle JSON generation errors.
        
        Args:
            error: JSON generation error
            context: Error context
            
        Returns:
            Recovery action
        """
        self.error_counts['json_generation'] += 1
        
        # Try to generate minimal valid JSON
        self.logger.warning("JSON generation failed, creating minimal output")
        return RecoveryAction.MINIMAL_OUTPUT
    
    def handle_performance_error(self, error: PerformanceError, context: ErrorContext) -> RecoveryAction:
        """Handle performance constraint errors.
        
        Args:
            error: Performance error
            context: Error context
            
        Returns:
            Recovery action
        """
        self.error_counts['performance'] += 1
        
        error_msg = str(error).lower()
        if 'timeout' in error_msg:
            self.logger.error("Processing timeout - returning partial results")
            return RecoveryAction.PARTIAL_RESULTS
        elif 'memory' in error_msg:
            self.logger.error("Memory limit exceeded - attempting cleanup and retry")
            return RecoveryAction.RETRY
        else:
            self.logger.error("Performance constraint violated - returning partial results")
            return RecoveryAction.PARTIAL_RESULTS
    
    def handle_unknown_error(self, error: Exception, context: ErrorContext) -> RecoveryAction:
        """Handle unknown errors.
        
        Args:
            error: Unknown error
            context: Error context
            
        Returns:
            Recovery action
        """
        self.error_counts['unknown'] += 1
        
        # Log full traceback for debugging
        self.logger.exception(f"Unknown error in {context.operation}: {str(error)}")
        
        # Try to continue with minimal output
        return RecoveryAction.MINIMAL_OUTPUT
    
    def create_fallback_output(self, file_path: str, error_message: str) -> Dict[str, Any]:
        """Create fallback JSON output for failed processing.
        
        Args:
            file_path: Path to the PDF file
            error_message: Error message to include
            
        Returns:
            Minimal JSON output
        """
        from pathlib import Path
        
        filename = Path(file_path).stem
        
        return {
            "title": f"Error Processing - {filename}",
            "outline": []
        }
    
    def create_minimal_outline(self, text_blocks: list, title: str = None) -> Dict[str, Any]:
        """Create minimal outline using basic font-size analysis.
        
        Args:
            text_blocks: List of text blocks
            title: Document title (optional)
            
        Returns:
            Minimal outline structure
        """
        if not text_blocks:
            return {
                "title": title or "Empty Document",
                "outline": []
            }
        
        # Simple font-size based classification
        outline_entries = []
        
        # Find largest font size
        max_font_size = max(block.font_metadata.size for block in text_blocks)
        
        for block in text_blocks:
            # Only include text that's significantly larger than average
            if block.font_metadata.size >= max_font_size * 0.8:
                # Simple level assignment based on relative size
                if block.font_metadata.size >= max_font_size * 0.9:
                    level = "H1"
                elif block.font_metadata.size >= max_font_size * 0.8:
                    level = "H2"
                else:
                    level = "H3"
                
                # Basic text cleaning
                text = block.text.strip()
                if len(text) > 3 and len(text) < 200:  # Reasonable heading length
                    outline_entries.append({
                        "level": level,
                        "text": text,
                        "page": block.page_number
                    })
        
        # Limit to reasonable number of entries
        outline_entries = outline_entries[:20]
        
        return {
            "title": title or (outline_entries[0]["text"] if outline_entries else "Untitled Document"),
            "outline": outline_entries
        }
    
    def get_error_summary(self) -> Dict[str, Any]:
        """Get summary of errors encountered.
        
        Returns:
            Dictionary with error statistics
        """
        total_errors = sum(self.error_counts.values())
        
        return {
            'total_errors': total_errors,
            'error_breakdown': self.error_counts.copy(),
            'most_common_error': max(self.error_counts, key=self.error_counts.get) if total_errors > 0 else None
        }
    
    def reset_error_counts(self) -> None:
        """Reset error counters."""
        for key in self.error_counts:
            self.error_counts[key] = 0
    
    def with_error_handling(self, operation_name: str, file_path: str = None):
        """Decorator for automatic error handling.
        
        Args:
            operation_name: Name of the operation
            file_path: File path being processed (optional)
            
        Returns:
            Decorator function
        """
        def decorator(func: Callable):
            def wrapper(*args, **kwargs):
                context = ErrorContext(
                    operation=operation_name,
                    file_path=file_path
                )
                
                try:
                    return func(*args, **kwargs)
                except Exception as e:
                    recovery_action = self.handle_error(e, context)
                    
                    # Handle recovery action
                    if recovery_action == RecoveryAction.SKIP_FILE:
                        return None
                    elif recovery_action == RecoveryAction.USE_FALLBACK:
                        # Caller should implement fallback logic
                        raise e
                    elif recovery_action == RecoveryAction.MINIMAL_OUTPUT:
                        # Return minimal output if possible
                        if file_path:
                            return self.create_fallback_output(file_path, str(e))
                        else:
                            return None
                    else:
                        raise e
            
            return wrapper
        return decorator