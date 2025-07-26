"""Core data models for PDF outline extraction."""

from dataclasses import dataclass
from typing import List, Optional, Dict, Any
from datetime import datetime


@dataclass
class PositionInfo:
    """Information about text positioning in PDF."""
    x0: float  # Left coordinate
    y0: float  # Bottom coordinate
    x1: float  # Right coordinate
    y1: float  # Top coordinate
    width: float
    height: float


@dataclass
class StyleInfo:
    """Information about text styling."""
    is_bold: bool = False
    is_italic: bool = False
    is_underlined: bool = False
    color: Optional[str] = None


@dataclass
class FontMetadata:
    """Font metadata information."""
    size: float
    family: str
    weight: str  # normal, bold
    style: str   # normal, italic
    relative_size_rank: int = 0  # ranking within document (0 = largest)
    
    def __post_init__(self):
        """Normalize font metadata after initialization."""
        self.weight = self.weight.lower() if self.weight else "normal"
        self.style = self.style.lower() if self.style else "normal"
        self.family = self.family or "unknown"


@dataclass
class TextBlock:
    """A block of text extracted from PDF with metadata."""
    text: str
    page_number: int
    font_metadata: FontMetadata
    position: PositionInfo
    styling: StyleInfo
    
    def __post_init__(self):
        """Clean and validate text block after initialization."""
        self.text = self.text.strip() if self.text else ""
    
    @property
    def is_likely_heading(self) -> bool:
        """Quick heuristic to check if this might be a heading."""
        if not self.text or len(self.text) > 200:
            return False
        
        # Check for heading-like characteristics
        has_large_font = self.font_metadata.relative_size_rank <= 3
        is_short = len(self.text) < 100
        is_bold = self.styling.is_bold or "bold" in self.font_metadata.weight
        
        return has_large_font and (is_short or is_bold)


@dataclass
class HeadingCandidate:
    """A candidate heading with classification information."""
    text_block: TextBlock
    confidence_score: float
    classification_factors: Dict[str, float]
    suggested_level: Optional[str] = None  # H1, H2, H3
    
    @property
    def text(self) -> str:
        """Get the text content."""
        return self.text_block.text
    
    @property
    def page(self) -> int:
        """Get the page number."""
        return self.text_block.page_number


@dataclass
class OutlineEntry:
    """An entry in the document outline."""
    level: str  # H1, H2, H3
    text: str
    page: int
    confidence_score: float = 1.0
    
    def __post_init__(self):
        """Validate outline entry after initialization."""
        if self.level not in ["H1", "H2", "H3"]:
            raise ValueError(f"Invalid heading level: {self.level}")
        
        if not self.text or not self.text.strip():
            raise ValueError("Outline entry text cannot be empty")
        
        if self.page < 0:
            raise ValueError("Page number must be non-negative")
        
        self.text = self.text.strip()
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "level": self.level,
            "text": self.text,
            "page": self.page
        }


@dataclass
class ProcessingMetadata:
    """Metadata about the processing operation."""
    processing_time_seconds: float
    total_pages: int
    total_text_blocks: int
    headings_found: int
    confidence_scores: List[float]
    timestamp: datetime
    
    @property
    def average_confidence(self) -> float:
        """Calculate average confidence score."""
        if not self.confidence_scores:
            return 0.0
        return sum(self.confidence_scores) / len(self.confidence_scores)


@dataclass
class DocumentOutline:
    """Complete document outline with title and hierarchical structure."""
    title: str
    outline: List[OutlineEntry]
    processing_metadata: Optional[ProcessingMetadata] = None
    
    def __post_init__(self):
        """Validate document outline after initialization."""
        if not self.title or not self.title.strip():
            self.title = "Untitled Document"
        else:
            self.title = self.title.strip()
        
        # Ensure outline is sorted by page number
        self.outline.sort(key=lambda entry: entry.page)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "title": self.title,
            "outline": [entry.to_dict() for entry in self.outline]
        }
    
    def get_entries_by_level(self, level: str) -> List[OutlineEntry]:
        """Get all entries of a specific level."""
        return [entry for entry in self.outline if entry.level == level]
    
    def get_entries_on_page(self, page: int) -> List[OutlineEntry]:
        """Get all entries on a specific page."""
        return [entry for entry in self.outline if entry.page == page]


@dataclass
class ProcessingResult:
    """Result of processing a single PDF file."""
    success: bool
    document_outline: Optional[DocumentOutline] = None
    error_message: Optional[str] = None
    processing_metadata: Optional[ProcessingMetadata] = None
    
    @property
    def has_outline(self) -> bool:
        """Check if processing produced an outline."""
        return self.success and self.document_outline is not None
    
    @property
    def outline_count(self) -> int:
        """Get the number of outline entries."""
        if not self.has_outline:
            return 0
        return len(self.document_outline.outline)