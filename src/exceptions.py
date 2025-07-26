"""Custom exceptions for PDF outline extractor."""


class PDFProcessingError(Exception):
    """Base exception for PDF processing errors."""
    pass


class PDFParsingError(PDFProcessingError):
    """Raised when PDF file cannot be parsed."""
    pass


class TextExtractionError(PDFProcessingError):
    """Raised when text extraction fails."""
    pass


class HeadingClassificationError(PDFProcessingError):
    """Raised when heading classification fails."""
    pass


class HierarchyBuildingError(PDFProcessingError):
    """Raised when hierarchy building fails."""
    pass


class JSONGenerationError(PDFProcessingError):
    """Raised when JSON output generation fails."""
    pass


class ValidationError(PDFProcessingError):
    """Raised when data validation fails."""
    pass


class PerformanceError(PDFProcessingError):
    """Raised when performance constraints are violated."""
    pass


class FileSystemError(PDFProcessingError):
    """Raised when file system operations fail."""
    pass