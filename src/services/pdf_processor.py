"""PDF processing service for outline extraction."""

import fitz  # PyMuPDF
import gc
import time
from typing import List, Optional
import logging
from pathlib import Path

from ..models.data_models import TextBlock, ProcessingResult, DocumentOutline, ProcessingMetadata
from ..config import ProcessingConfig
from ..exceptions import PDFParsingError, PerformanceError, FileSystemError
from ..utils.validation import validate_processing_input


class PDFProcessor:
    """Main PDF processing class for extracting text and metadata."""
    
    def __init__(self, config: ProcessingConfig):
        """Initialize PDF processor with configuration.
        
        Args:
            config: Processing configuration
        """
        self.config = config
        self.logger = logging.getLogger(__name__)
        
    def process_file(self, input_path: str, output_path: str) -> ProcessingResult:
        """Process a single PDF file and extract outline.
        
        Args:
            input_path: Path to input PDF file
            output_path: Path for output JSON file
            
        Returns:
            ProcessingResult with success status and outline data
        """
        start_time = time.time()
        
        try:
            # Validate input file
            validate_processing_input(input_path)
            
            self.logger.info(f"Starting processing of {input_path}")
            
            # Extract text with metadata
            text_blocks = self.extract_text_with_metadata(input_path)
            
            if not text_blocks:
                return ProcessingResult(
                    success=False,
                    error_message="No text blocks extracted from PDF"
                )
            
            # Check processing time constraint
            elapsed_time = time.time() - start_time
            if elapsed_time > self.config.max_processing_time_seconds:
                raise PerformanceError(f"Processing exceeded time limit: {elapsed_time:.2f}s")
            
            self.logger.info(f"Extracted {len(text_blocks)} text blocks from {len(set(block.page_number for block in text_blocks))} pages")
            
            # Create processing metadata
            processing_metadata = ProcessingMetadata(
                processing_time_seconds=elapsed_time,
                total_pages=len(set(block.page_number for block in text_blocks)),
                total_text_blocks=len(text_blocks),
                headings_found=0,  # Will be updated by classification
                confidence_scores=[],
                timestamp=time.time()
            )
            
            return ProcessingResult(
                success=True,
                processing_metadata=processing_metadata
            )
            
        except Exception as e:
            elapsed_time = time.time() - start_time
            error_msg = f"Error processing {input_path}: {str(e)}"
            self.logger.error(error_msg)
            
            return ProcessingResult(
                success=False,
                error_message=error_msg,
                processing_metadata=ProcessingMetadata(
                    processing_time_seconds=elapsed_time,
                    total_pages=0,
                    total_text_blocks=0,
                    headings_found=0,
                    confidence_scores=[],
                    timestamp=time.time()
                )
            )
    
    def extract_text_with_metadata(self, pdf_path: str) -> List[TextBlock]:
        """Extract text blocks with comprehensive metadata from PDF.
        
        Args:
            pdf_path: Path to PDF file
            
        Returns:
            List of TextBlock objects with metadata
            
        Raises:
            PDFParsingError: If PDF cannot be parsed
        """
        text_blocks = []
        pdf_document = None
        
        try:
            # Open PDF document
            pdf_document = fitz.open(pdf_path)
            
            if pdf_document.is_encrypted:
                raise PDFParsingError("PDF is encrypted and cannot be processed")
            
            if pdf_document.page_count == 0:
                raise PDFParsingError("PDF has no pages")
            
            # Process each page
            for page_num in range(pdf_document.page_count):
                try:
                    page = pdf_document[page_num]
                    page_blocks = self._extract_page_text_blocks(page, page_num)
                    text_blocks.extend(page_blocks)
                    
                except Exception as e:
                    self.logger.warning(f"Error processing page {page_num}: {str(e)}")
                    continue
            
            return text_blocks
            
        except fitz.FileDataError as e:
            raise PDFParsingError(f"Invalid PDF file format: {str(e)}")
        except fitz.FileNotFoundError as e:
            raise PDFParsingError(f"PDF file not found: {str(e)}")
        except Exception as e:
            raise PDFParsingError(f"Unexpected error parsing PDF: {str(e)}")
        finally:
            # Clean up resources
            if pdf_document:
                pdf_document.close()
            gc.collect()  # Force garbage collection for memory management
    
    def _extract_page_text_blocks(self, page, page_number: int) -> List[TextBlock]:
        """Extract text blocks from a single page.
        
        Args:
            page: PyMuPDF page object
            page_number: Page number (1-indexed)
            
        Returns:
            List of TextBlock objects from the page
        """
        from ..models.data_models import FontMetadata, PositionInfo, StyleInfo
        
        text_blocks = []
        
        try:
            # Get text blocks with detailed information
            blocks = page.get_text("dict")
            
            for block in blocks.get("blocks", []):
                if "lines" not in block:
                    continue  # Skip non-text blocks (images, etc.)
                
                for line in block["lines"]:
                    for span in line["spans"]:
                        text = span.get("text", "").strip()
                        if not text:
                            continue
                        
                        # Extract font metadata
                        font_metadata = FontMetadata(
                            size=span.get("size", 12.0),
                            family=span.get("font", "unknown"),
                            weight="bold" if span.get("flags", 0) & 2**4 else "normal",
                            style="italic" if span.get("flags", 0) & 2**1 else "normal"
                        )
                        
                        # Extract position information
                        bbox = span.get("bbox", [0, 0, 0, 0])
                        position = PositionInfo(
                            x0=bbox[0],
                            y0=bbox[1],
                            x1=bbox[2],
                            y1=bbox[3],
                            width=bbox[2] - bbox[0],
                            height=bbox[3] - bbox[1]
                        )
                        
                        # Extract styling information
                        flags = span.get("flags", 0)
                        styling = StyleInfo(
                            is_bold=bool(flags & 2**4),
                            is_italic=bool(flags & 2**1),
                            is_underlined=bool(flags & 2**0),
                            color=span.get("color")
                        )
                        
                        # Create text block
                        text_block = TextBlock(
                            text=text,
                            page_number=page_number,
                            font_metadata=font_metadata,
                            position=position,
                            styling=styling
                        )
                        
                        text_blocks.append(text_block)
        
        except Exception as e:
            self.logger.warning(f"Error extracting text from page {page_number}: {str(e)}")
        
        return text_blocks
    
    def handle_processing_errors(self, error: Exception) -> None:
        """Handle processing errors with appropriate logging and recovery.
        
        Args:
            error: Exception that occurred during processing
        """
        if isinstance(error, PDFParsingError):
            self.logger.error(f"PDF parsing error: {str(error)}")
        elif isinstance(error, PerformanceError):
            self.logger.error(f"Performance constraint violated: {str(error)}")
        elif isinstance(error, FileSystemError):
            self.logger.error(f"File system error: {str(error)}")
        else:
            self.logger.error(f"Unexpected error: {str(error)}")
    
    def get_memory_usage(self) -> dict:
        """Get current memory usage statistics.
        
        Returns:
            Dictionary with memory usage information
        """
        import psutil
        import os
        
        process = psutil.Process(os.getpid())
        memory_info = process.memory_info()
        
        return {
            "rss_mb": memory_info.rss / 1024 / 1024,  # Resident Set Size
            "vms_mb": memory_info.vms / 1024 / 1024,  # Virtual Memory Size
            "percent": process.memory_percent()
        }