#!/usr/bin/env python3
"""
PDF Outline Extractor - Adobe Hackathon Round 1A
Main application entry point for batch processing PDFs.
"""

import os
import sys
import json
import time
import logging
from pathlib import Path
from typing import List

# Add src to Python path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

from src.config import ConfigManager
from src.services.pdf_processor import PDFProcessor
from src.services.text_extractor import TextExtractor
from src.services.heading_classifier import HeadingClassifier
from src.services.title_detector import TitleDetector
from src.services.hierarchy_builder import HierarchyBuilder
from src.services.json_generator import JSONGenerator
from src.utils.logging_config import setup_logging
from src.utils.performance_monitor import PerformanceMonitor
from src.exceptions import PDFProcessingError


def discover_pdf_files(input_directory: str) -> List[str]:
    """Discover all PDF files in the input directory.
    
    Args:
        input_directory: Path to input directory
        
    Returns:
        List of PDF file paths
    """
    pdf_files = []
    input_path = Path(input_directory)
    
    if not input_path.exists():
        logging.error(f"Input directory does not exist: {input_directory}")
        return pdf_files
    
    # Use a set to avoid duplicates and check both extensions
    pdf_files_set = set()
    
    for file_path in input_path.glob("*.pdf"):
        if file_path.is_file():
            pdf_files_set.add(str(file_path))
    
    # Also check for .PDF extension
    for file_path in input_path.glob("*.PDF"):
        if file_path.is_file():
            pdf_files_set.add(str(file_path))
    
    return sorted(list(pdf_files_set))


def create_output_path(input_path: str, output_directory: str) -> str:
    """Create output JSON file path from input PDF path.
    
    Args:
        input_path: Path to input PDF file
        output_directory: Output directory path
        
    Returns:
        Path to output JSON file
    """
    input_file = Path(input_path)
    output_file = Path(output_directory) / f"{input_file.stem}.json"
    return str(output_file)


def process_single_file(
    pdf_processor: PDFProcessor,
    text_extractor: TextExtractor,
    heading_classifier: HeadingClassifier,
    title_detector: TitleDetector,
    hierarchy_builder: HierarchyBuilder,
    json_generator: JSONGenerator,
    performance_monitor: PerformanceMonitor,
    input_path: str,
    output_path: str,
    logger: logging.Logger
) -> bool:
    """Process a single PDF file through the complete pipeline.
    
    Args:
        pdf_processor: PDFProcessor instance
        text_extractor: TextExtractor instance
        heading_classifier: HeadingClassifier instance
        title_detector: TitleDetector instance
        hierarchy_builder: HierarchyBuilder instance
        json_generator: JSONGenerator instance
        input_path: Path to input PDF
        output_path: Path to output JSON
        logger: Logger instance
        
    Returns:
        True if processing succeeded
    """
    try:
        logger.info(f"Processing: {input_path}")
        start_time = time.time()
        
        # Monitor performance throughout processing
        def monitored_processing():
            # Step 1: Open the PDF and process each page
            import fitz  # PyMuPDF
            doc = fitz.open(input_path)
            
            all_text_blocks = []
            for page in doc:
                page_blocks = text_extractor.extract_blocks(page)
                all_text_blocks.extend(page_blocks)
            
            doc.close()

            if not all_text_blocks:
                logger.warning(f"No text blocks extracted from {input_path}")
                # Create minimal output for empty documents
                output_data = {
                    "title": f"Empty Document - {Path(input_path).stem}",
                    "outline": []
                }
                json_generator.save_to_file(output_data, output_path)
                return True
            
            text_blocks = all_text_blocks
            logger.info(f"Extracted {len(text_blocks)} text blocks")
            
            # Check memory usage after text extraction
            if not performance_monitor.check_memory_usage():
                performance_monitor.trigger_cleanup()
            
            # Step 2: Classify headings
            heading_candidates = heading_classifier.classify_text_blocks(text_blocks)
            logger.info(f"Found {len(heading_candidates)} heading candidates")
            
            # Step 3: Detect document title
            document_title = title_detector.detect_title(text_blocks, heading_candidates)
            logger.info(f"Detected title: {document_title[:50]}...")
            
            # Step 4: Build hierarchical outline
            document_outline = hierarchy_builder.build_outline(heading_candidates, document_title)
            logger.info(f"Built outline with {len(document_outline.outline)} entries")
            
            # Step 5: Generate and save JSON output
            json_generator.generate_and_save(document_outline, output_path)
            
            return True
        
        # Execute with performance monitoring
        metrics = performance_monitor.monitor_processing(monitored_processing)
        
        if not metrics.success:
            raise Exception(metrics.error_message or "Processing failed")
        
        # Log performance metrics
        logger.info(f"Successfully processed {input_path} in {metrics.processing_time:.2f}s -> {output_path}")
        logger.debug(f"Memory usage: {metrics.memory_usage_mb:.1f}MB (peak: {metrics.memory_peak_mb:.1f}MB)")
        
        return True
        

        
    except Exception as e:
        logger.error(f"Error processing {input_path}: {str(e)}")
        
        # Create error output
        try:
            error_output = {
                "title": f"Error Processing - {Path(input_path).stem}",
                "outline": []
            }
            json_generator.save_to_file(error_output, output_path)
        except:
            pass  # If we can't even save error output, just continue
        
        return False


def main():
    """Main application entry point."""
    # Set up logging
    logger = setup_logging("INFO")
    logger.info("Starting PDF Outline Extractor")
    
    try:
        # Load configuration
        config_manager = ConfigManager()
        processing_config = config_manager.get_processing_config()
        
        # Override directories for local testing
        if os.path.exists("./input"):
            processing_config.input_directory = "./input"
        
        # Always use local output directory for local testing
        processing_config.output_directory = "./output"
        
        logger.info(f"Input directory: {processing_config.input_directory}")
        logger.info(f"Output directory: {processing_config.output_directory}")
        
        # Create output directory if it doesn't exist
        os.makedirs(processing_config.output_directory, exist_ok=True)
        
        # Discover PDF files
        pdf_files = discover_pdf_files(processing_config.input_directory)
        
        if not pdf_files:
            logger.warning(f"No PDF files found in {processing_config.input_directory}")
            return 0
        
        logger.info(f"Found {len(pdf_files)} PDF files to process")
        
        # Initialize processing components
        classification_config = config_manager.get_classification_config()
        performance_monitor = PerformanceMonitor(
            max_memory_gb=processing_config.max_memory_gb,
            max_time_seconds=processing_config.max_processing_time_seconds
        )
        
        pdf_processor = PDFProcessor(processing_config)
        text_extractor = TextExtractor()
        heading_classifier = HeadingClassifier(classification_config)
        title_detector = TitleDetector(classification_config)
        hierarchy_builder = HierarchyBuilder(classification_config)
        json_generator = JSONGenerator()
        
        # Process each file
        successful_count = 0
        failed_count = 0
        
        for pdf_file in pdf_files:
            output_file = create_output_path(pdf_file, processing_config.output_directory)
            
            if process_single_file(
                pdf_processor, text_extractor, heading_classifier,
                title_detector, hierarchy_builder, json_generator,
                performance_monitor, pdf_file, output_file, logger
            ):
                successful_count += 1
            else:
                failed_count += 1
        
        # Log summary
        logger.info(f"Processing complete: {successful_count} successful, {failed_count} failed")
        
        return 0 if failed_count == 0 else 1
        
    except Exception as e:
        logger.error(f"Application error: {str(e)}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
