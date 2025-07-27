import json
import logging
import os
import re

from ..models.data_models import DocumentOutline
from ..exceptions import JSONGenerationError

class JSONGenerator:
    def __init__(self):
        self.logger = logging.getLogger(__name__)

    def generate_and_save(self, outline: DocumentOutline, file_path: str):
        try:
            output_data = outline.to_dict()
            self._clean_output(output_data)
            self.save_to_file(output_data, file_path)
        except Exception as e:
            raise JSONGenerationError(f"Failed during JSON generation/saving: {e}")

    def _clean_text(self, text: str) -> str:
        return re.sub(r'\s+', ' ', text).strip()

    def _clean_output(self, data):
        data["title"] = self._clean_text(data.get("title", ""))
        cleaned_outline = []
        for entry in data.get("outline", []):
            cleaned_text = self._clean_text(entry.get("text", ""))
            if cleaned_text:
                entry["text"] = cleaned_text + " "
                cleaned_outline.append(entry)
        data["outline"] = cleaned_outline

    def save_to_file(self, data, file_path: str):
        try:
            os.makedirs(os.path.dirname(file_path), exist_ok=True)
            with open(file_path, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=4, ensure_ascii=False)
        except Exception as e:
            raise JSONGenerationError(f"Failed to save JSON to {file_path}: {e}")
