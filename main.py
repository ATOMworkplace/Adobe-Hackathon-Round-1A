#!/usr/bin/env python3
import os
import sys
from pathlib import Path
import logging

sys.path.insert(0, os.path.join(os.path.dirname(__file__)))

from src.config import ConfigManager
from src.services.pdf_processor import PDFProcessor
from src.services.heading_classifier import HeadingClassifier
from src.services.title_detector import TitleDetector
from src.services.hierarchy_builder import HierarchyBuilder
from src.services.json_generator import JSONGenerator
from src.services.toc_extractor import TOCExtractor  # <-- NEW!
from src.utils.logging_config import setup_logging

def discover_pdf_files(input_directory):
    pdf_files = []
    input_path = Path(input_directory)
    if not input_path.exists() or not input_path.is_dir():
        logging.error(f"Input directory does not exist or is not a directory: {input_directory}")
        return pdf_files
    for file_path in input_path.rglob('*.pdf'):
        if file_path.is_file():
            pdf_files.append(str(file_path))
    return sorted(pdf_files)

def create_output_path(input_path, output_directory):
    input_file = Path(input_path)
    return str(Path(output_directory) / f"{input_file.stem}.json")

def process_single_file(
    pdf_processor,
    heading_classifier,
    title_detector,
    hierarchy_builder,
    json_generator,
    toc_extractor,
    input_path,
    output_path,
    logger
):
    try:
        logger.info(f"Processing: {input_path}")

        text_blocks = pdf_processor.process_pdf(input_path)

        if not text_blocks:
            logger.warning(f"No text blocks extracted from {input_path}")
            json_generator.save_to_file(
                {"title": "", "outline": []},
                output_path
            )
            return True

        # Try TOC extraction first
        toc_headings = toc_extractor.extract_toc_headings(text_blocks)
        if toc_headings:
            heading_candidates = toc_headings
        else:
            heading_candidates = heading_classifier.classify_blocks(text_blocks)

        document_title = title_detector.detect_title(heading_candidates, text_blocks)
        document_outline = hierarchy_builder.build_outline(heading_candidates, document_title)

        json_generator.generate_and_save(document_outline, output_path)

        logger.info(f"Successfully processed {input_path} -> {output_path}")
        return True

    except Exception as e:
        logger.error(f"Error processing {input_path}: {str(e)}", exc_info=True)
        try:
            json_generator.save_to_file(
                {"title": f"Error Processing - {Path(input_path).stem}", "outline": []},
                output_path
            )
        except Exception as json_err:
            logger.error(f"Could not even save error JSON for {input_path}: {json_err}")
        return False

def main():
    logger = setup_logging("INFO")
    logger.info("Starting PDF Outline Extractor")
    try:
        config = ConfigManager()
        proc_cfg = config.get_processing_config()

        if os.path.exists("./input") and os.path.isdir("./input"):
             proc_cfg.input_directory = "./input"

        if os.path.exists("./output") and os.path.isdir("./output"):
            proc_cfg.output_directory = "./output"

        os.makedirs(proc_cfg.input_directory, exist_ok=True)
        os.makedirs(proc_cfg.output_directory, exist_ok=True)

        pdf_files = discover_pdf_files(proc_cfg.input_directory)
        if not pdf_files:
            logger.warning(f"No PDF files found in configured input directory: {proc_cfg.input_directory}")
            return 0

        pdf_proc = PDFProcessor(config)
        head_clf = HeadingClassifier(config)
        title_det = TitleDetector(config)
        hierarchy = HierarchyBuilder(config)
        json_gen = JSONGenerator()
        toc_extractor = TOCExtractor(config)  # <-- NEW!

        success_count = 0
        for pdf_path in pdf_files:
            output_path = create_output_path(pdf_path, proc_cfg.output_directory)
            if process_single_file(
                pdf_proc, head_clf,
                title_det, hierarchy, json_gen,
                toc_extractor,  # <-- NEW!
                pdf_path, output_path, logger
            ):
                success_count += 1
        logger.info(f"Completed: {success_count}/{len(pdf_files)} processed successfully.")
        return 0

    except Exception as e:
        logger.error(f"A fatal error occurred in the main process: {str(e)}", exc_info=True)
        return 1

if __name__ == '__main__':
    sys.exit(main())
