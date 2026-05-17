"""Extracts text from uploaded PDF files using pdfplumber."""
import pdfplumber
from typing import Tuple


class PDFExtractionError(Exception):
    pass


def extract_text_from_pdf(file_path: str) -> Tuple[str, int]:
    """
    Extract raw text from a PDF file.
    Returns (full_text, page_count).
    Raises PDFExtractionError on any failure.
    """
    try:
        full_text_parts = []
        with pdfplumber.open(file_path) as pdf:
            page_count = len(pdf.pages)
            if page_count == 0:
                raise PDFExtractionError("PDF has no pages.")

            for i, page in enumerate(pdf.pages):
                text = page.extract_text()
                if text:
                    full_text_parts.append(f"--- PAGE {i + 1} ---\n{text.strip()}")

        if not full_text_parts:
            raise PDFExtractionError(
                "No text could be extracted. The PDF may be image-only or scanned."
            )

        return "\n\n".join(full_text_parts), page_count

    except PDFExtractionError:
        raise
    except Exception as e:
        raise PDFExtractionError(f"Failed to extract PDF text: {str(e)}") from e