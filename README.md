# PDF Outline Extractor

A production-ready PDF outline extraction system designed for Adobe's "Connecting the Dots" Hackathon Round 1A. This system extracts structured outlines from PDF documents, identifying titles and hierarchical headings (H1, H2, H3) with corresponding page numbers, and outputs results in JSON format.

## Features

- **High-Performance Processing**: Processes 50-page PDFs within 10 seconds
- **Multi-Factor Heading Classification**: Uses font size, weight, positioning, whitespace patterns, and text analysis
- **Intelligent Title Detection**: Identifies document titles using font size, positioning, and placement heuristics
- **Hierarchical Structure Building**: Constructs logical H1/H2/H3 hierarchy with conflict resolution
- **Multilingual Support**: Handles Unicode content including Japanese and other non-English languages
- **Docker Containerization**: AMD64-compatible container for offline batch processing
- **Robust Error Handling**: Graceful handling of malformed PDFs and edge cases

## Architecture

The system uses a modular pipeline architecture:

1. **PDF Processing**: PyMuPDF-based text extraction with comprehensive metadata
2. **Font Analysis**: Statistical analysis of font characteristics across the document
3. **Heading Classification**: Multi-factor scoring system for heading identification
4. **Title Detection**: Specialized algorithms for document title identification
5. **Hierarchy Building**: Intelligent level assignment with conflict resolution
6. **JSON Generation**: Schema-compliant output with validation

## Technical Specifications

- **Platform**: AMD64 CPU architecture (no GPU dependencies)
- **Performance**: Maximum 10 seconds for 50-page PDFs
- **Memory**: Optimized for 16GB RAM limit
- **Model Size**: Under 200MB total (no external models required)
- **Network**: Complete offline operation
- **Output Format**: JSON with exact schema compliance

## Installation

### Local Development

### Docker Deployment

```bash
# Build the container
docker build --platform linux/amd64 -t pdf-outline-extractor .

# Run with input/output volumes
docker run --rm \
  -v $(pwd)/input:/app/input \
  -v $(pwd)/output:/app/output \
  --network none \
  pdf-outline-extractor
```

## Usage

### Input/Output Structure

- **Input**: PDF files in `/app/input` directory (or `./input` for local testing)
- **Output**: JSON files in `/app/output` directory (or `./output` for local testing)

### JSON Output Schema

```json
{
  "title": "Document Title",
  "outline": [
    {"level": "H1", "text": "Main Section", "page": 1},
    {"level": "H2", "text": "Subsection", "page": 2},
    {"level": "H3", "text": "Sub-subsection", "page": 3}
  ]
}
```

## Algorithm Details

### Heading Classification

The system uses a weighted multi-factor approach:

- **Font Size Analysis (40%)**: Relative font size relationships within the document
- **Font Weight & Styling (20%)**: Bold, italic, and other styling indicators
- **Position Analysis (20%)**: Vertical positioning and left alignment patterns
- **Whitespace Patterns (10%)**: Spacing above and below text blocks
- **Text Patterns (10%)**: Length, capitalization, and linguistic patterns

### Title Detection

Three-stage title detection strategy:

1. **Heading-Based**: Look for high-confidence H1 headings on first page
2. **Font Analysis**: Identify largest font text with title characteristics
3. **Placement Analysis**: Find title-like text in top 20% of first page

### Hierarchy Building

Intelligent level assignment process:

1. **Font Grouping**: Group headings by similar font characteristics
2. **Statistical Ranking**: Rank groups by size and confidence
3. **Context Resolution**: Resolve hierarchy conflicts and level skipping
4. **Sequential Validation**: Ensure logical heading progression

## Performance Optimizations

- **Streaming Processing**: Memory-efficient handling of large documents
- **Font Caching**: Cached font metadata analysis
- **Early Termination**: Skip processing for clearly non-heading text
- **Garbage Collection**: Aggressive memory cleanup for batch processing

## Testing

```bash
# Run basic functionality tests
python test_basic.py

# Test with sample PDFs (place PDFs in ./input directory)
python main.py
```

## Configuration

Key configuration parameters in `src/config.py`:

- `max_processing_time_seconds`: Processing timeout (default: 10s)
- `heading_confidence_threshold`: Minimum confidence for headings (default: 0.6)
- `title_confidence_threshold`: Minimum confidence for titles (default: 0.8)
- Font analysis weights and hierarchy thresholds

## Error Handling

The system handles various error conditions:

- **Corrupted PDFs**: Graceful failure with error logging
- **Encrypted PDFs**: Skip with appropriate warning
- **Memory Issues**: Streaming processing for large files
- **Performance Timeouts**: Partial results with timeout handling
- **Unicode Issues**: Robust Unicode normalization and fallback

## Multilingual Support

- **Unicode Normalization**: NFC normalization for consistent processing
- **Language Detection**: Character-based language hints (Japanese, Latin, Cyrillic)
- **Cultural Patterns**: Adaptation for different formatting conventions
- **Encoding Handling**: UTF-8 throughout with fallback strategies

## Known Limitations

- Maximum 50 pages per document (hackathon constraint)
- Heading levels limited to H1, H2, H3
- Complex multi-column layouts may affect accuracy
- Heavily stylized documents may require manual tuning
- No support for encrypted or password-protected PDFs

## Dependencies

- **PyMuPDF (fitz)**: PDF processing and text extraction
- **psutil**: Memory and performance monitoring
- **Python 3.9+**: Core runtime environment

## License

This project is developed for Adobe's Hackathon Round 1A competition.

## Development Notes

The codebase is designed for extensibility in Round 1B with:

- Modular architecture for easy component replacement
- Comprehensive logging and monitoring
- Configurable parameters for different document types
- Clean separation between processing stages
- Extensive error handling and recovery mechanisms
