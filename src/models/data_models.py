from dataclasses import dataclass
from typing import List, Dict, Any

@dataclass
class PositionInfo:
    x0: float; y0: float; x1: float; y1: float

@dataclass
class FontMetadata:
    size: float; family: str; weight: str; style: str; is_bold: bool

@dataclass
class TextBlock:
    text: str; page_number: int; font_metadata: FontMetadata; position: PositionInfo

@dataclass
class HeadingCandidate:
    text_block: TextBlock; level: str
    
    @property
    def text(self) -> str: return self.text_block.text
    @property
    def page(self) -> int: return self.text_block.page_number

@dataclass
class OutlineEntry:
    level: str; text: str; page: int
    def to_dict(self) -> Dict[str, Any]: return {"level": self.level, "text": self.text, "page": self.page}

@dataclass
class DocumentOutline:
    title: str; outline: List[OutlineEntry]
    def to_dict(self) -> Dict[str, Any]: return {"title": self.title, "outline": [e.to_dict() for e in self.outline]}