from abc import ABC, abstractmethod
from typing import List

class OCRClient(ABC):
    @abstractmethod
    def extract_text_from_image(self, image_path: str) -> str:

    @abstractmethod
    def extract_text_from_pdf(self, pdf_path: str) -> str: