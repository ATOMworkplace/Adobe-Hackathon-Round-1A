import fitz
import re
from typing import List, Tuple
from collections import defaultdict

from ..models.data_models import TextBlock, FontMetadata, PositionInfo
from ..config import ConfigManager

class TextExtractor:
    def __init__(self, config_manager: ConfigManager):
        self.proc_cfg = config_manager.get_processing_config()

    def _normalize_font(self, font_name: str) -> Tuple[str, str, str, bool]:
        if not isinstance(font_name, str): font_name = "Unknown"
        lower = font_name.lower()
        is_bold = "bold" in lower or "black" in lower
        weight = "bold" if is_bold else "normal"
        style = "italic" if "italic" in lower or "oblique" in lower else "normal"
        family = re.sub(r'-(bold|italic|oblique|regular|medium|black)', '', font_name, flags=re.IGNORECASE).split(',')[0]
        return family, weight, style, is_bold

    def extract_clean_blocks(self, doc: fitz.Document) -> List[TextBlock]:
        raw_spans = []
        for page_num, page in enumerate(doc):
            blocks_data = page.get_text("dict", flags=~fitz.TEXT_PRESERVE_IMAGES)["blocks"]
            for b in blocks_data:
                if b.get('type') == 0:
                    for l in b.get("lines", []):
                        for s in l.get("spans", []):
                            text = s['text'].strip()
                            if not text: continue
                            bbox = s['bbox']
                            family, weight, style, is_bold = self._normalize_font(s['font'])
                            raw_spans.append(TextBlock(
                                text=text, page_number=page_num,
                                font_metadata=FontMetadata(s['size'], family, weight, style, is_bold),
                                position=PositionInfo(bbox[0], bbox[1], bbox[2], bbox[3])
                            ))
        
        filtered_spans = self._filter_spans(raw_spans, len(doc))
        clean_blocks = self._reconstruct_blocks_from_spans(filtered_spans)
        return clean_blocks

    def _filter_spans(self, spans: List[TextBlock], page_count: int) -> List[TextBlock]:
        toc_pages = self._find_toc_pages(spans)
        
        hf_texts = defaultdict(list)
        if page_count > 2:
            for span in spans:
                if span.page_number > 0 and span.page_number not in toc_pages:
                    if span.position.y0 < self.proc_cfg.header_footer_margin or span.position.y1 > (792 - self.proc_cfg.header_footer_margin):
                        hf_texts[span.text.lower()].append(span.page_number)
        
        common_hf_texts = {text for text, pages in hf_texts.items() if len(set(pages)) > page_count / 3}

        final_spans = []
        for span in spans:
            if span.page_number in toc_pages: continue
            if span.text.lower() in common_hf_texts: continue
            if re.fullmatch(r'page \d+|\d+', span.text, re.I): continue
            final_spans.append(span)
        
        return final_spans

    def _find_toc_pages(self, spans: List[TextBlock]) -> set:
        toc_pages = set()
        page_toc_counts = defaultdict(int)
        for span in spans:
            if re.search(r'(\.|\s){4,}\s*\d+$', span.text):
                page_toc_counts[span.page_number] += 1
        
        for page, count in page_toc_counts.items():
            if count > 3:
                toc_pages.add(page)
        return toc_pages

    def _reconstruct_blocks_from_spans(self, spans: List[TextBlock]) -> List[TextBlock]:
        if not spans: return []
        
        lines = defaultdict(list)
        for span in sorted(spans, key=lambda s: (s.page_number, s.position.y0, s.position.x0)):
            lines[(span.page_number, round(span.position.y0 / 5))].append(span)

        blocks = []
        for line_spans in sorted(lines.values(), key=lambda s: (s[0].page_number, s[0].position.y0)):
            text = " ".join(s.text for s in line_spans)
            pos = PositionInfo(
                x0=min(s.position.x0 for s in line_spans), y0=min(s.position.y0 for s in line_spans),
                x1=max(s.position.x1 for s in line_spans), y1=max(s.position.y1 for s in line_spans)
            )
            blocks.append(TextBlock(text, line_spans[0].page_number, line_spans[0].font_metadata, pos))
        return blocks