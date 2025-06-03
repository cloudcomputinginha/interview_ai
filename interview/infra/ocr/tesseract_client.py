import pytesseract
from pdf2image import convert_from_path
from PIL import Image
import os
import tempfile
from interview.domain.ocr.ocr_client import OCRClient

class TesseractOCRClient(OCRClient):
    def __init__(self, lang: str = "kor+eng"):
        self.lang = lang

    def extract_text_from_image(self, image_path: str) -> str:
        try:
            image = Image.open(image_path)
            text = pytesseract.image_to_string(image, lang=self.lang)
            return text.strip()
        except FileNotFoundError:
            raise FileNotFoundError(f"Image file not found: {image_path}")
        except Exception as e:
            raise RuntimeError(f"Failed to extract text from image: {str(e)}")

    def extract_text_from_pdf(self, pdf_path: str) -> str:
        try:
            with tempfile.TemporaryDirectory() as tmpdir:
                images = convert_from_path(pdf_path, output_folder=tmpdir)
                texts = [pytesseract.image_to_string(img, lang=self.lang) for img in images]
                return "\n".join(t.strip() for t in texts)
        except FileNotFoundError:
            raise FileNotFoundError(f"PDF file not found: {pdf_path}")
        except Exception as e:
            raise RuntimeError(f"Failed to extract text from PDF: {str(e)}")


# 예시 사용
if __name__ == "__main__":
    ocr = TesseractOCRClient()

    # 이미지에서 추출
    image_text = ocr.extract_text_from_image("sample_korean_image.png")
    print("Image OCR Result:\n", image_text)

    # PDF에서 추출
    pdf_text = ocr.extract_text_from_pdf("sample_korean_document.pdf")
    print("PDF OCR Result:\n", pdf_text)
