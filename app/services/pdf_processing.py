import io
import re

import fitz
import pytesseract
from PIL import Image
from pydantic import BaseModel
import os
import tempfile
import logging
import nest_asyncio
from llama_parse import LlamaParse

from app.core.config import settings

logger = logging.getLogger(__name__)

# Apply nest_asyncio to allow LlamaParse to run inside our existing event loop
nest_asyncio.apply()


class ExtractionResult(BaseModel):
    success: bool
    raw_text: str | None = None
    cleaned_text: str | None = None
    page_count: int | None = None
    error: str | None = None
    message: str | None = None

def clean_text(text: str) -> str:
    """
    Strips extracted text of obvious noise (excessive whitespace, repeated headers/footers if trivially detectable).
    Kept conservative as per requirements.
    """
    # Replace 3 or more newlines with double newline
    text = re.sub(r'\n{3,}', '\n\n', text)
    # Replace 2 or more spaces/tabs with a single space
    text = re.sub(r'[ \t]{2,}', ' ', text)
    return text.strip()

async def extract_text(file_bytes: bytes, file_name: str) -> ExtractionResult:
    """
    Primary: Attempts to extract text using LlamaParse (supports PDF and PPTX).
    Fallback: Uses PyMuPDF (and Tesseract OCR) if LlamaParse fails or is unconfigured.
    """
    # ── Primary: LlamaParse ──────────────────────────────────────────────────
    if settings.LLAMA_CLOUD_API_KEY and settings.LLAMA_CLOUD_API_KEY != "llx-placeholder":
        try:
            logger.info("Attempting extraction with LlamaParse...")
            parser = LlamaParse(
                api_key=settings.LLAMA_CLOUD_API_KEY,
                result_type="markdown",
                use_vendor_multimodal_model=True,
                vendor_multimodal_model_name="openai-gpt4o",
                verbose=False
            )
            
            # LlamaParse needs a file on disk
            _, ext = os.path.splitext(file_name)
            # Ensure extension is valid for LlamaParse (e.g., .pdf, .pptx)
            if not ext:
                ext = ".pdf"
                
            with tempfile.NamedTemporaryFile(delete=False, suffix=ext) as tmp:
                tmp.write(file_bytes)
                tmp_path = tmp.name
                
            try:
                documents = await parser.aload_data(tmp_path)
                if documents:
                    raw_text = "\n\n".join([doc.text for doc in documents])
                    cleaned = clean_text(raw_text)
                    if len(cleaned) >= 50:
                        logger.info("LlamaParse extraction successful.")
                        return ExtractionResult(
                            success=True,
                            raw_text=raw_text,
                            cleaned_text=cleaned,
                            page_count=len(documents) # Approximate based on returned nodes
                        )
            finally:
                if os.path.exists(tmp_path):
                    os.remove(tmp_path)
        except Exception as e:
            logger.error(f"LlamaParse extraction failed: {e}. Falling back to PyMuPDF...")

    # ── Fallback: PyMuPDF / OCR ──────────────────────────────────────────────
    logger.info("Using PyMuPDF/OCR fallback for extraction...")
    try:
        doc = fitz.Document(stream=file_bytes, filetype="pdf")
    except Exception:
        return ExtractionResult(
            success=False,
            error="corrupted_pdf",
            message="The uploaded file could not be parsed. Please re-upload a valid PDF."
        )

    page_count = len(doc)

    if page_count == 0:
        return ExtractionResult(
            success=False,
            error="empty_pdf",
            message="No readable text was found in this document."
        )

    raw_text_parts = []
    for page in doc:
        raw_text_parts.append(page.get_text("text"))

    raw_text = "\n\n".join(raw_text_parts)
    cleaned = clean_text(raw_text)

    # If standard extraction gets enough text, return success
    if len(cleaned) >= 200:
        return ExtractionResult(
            success=True,
            raw_text=raw_text,
            cleaned_text=cleaned,
            page_count=page_count
        )

    # Text extraction returned near-empty content from a page-having PDF.
    # Attempt one fallback OCR pass.
    ocr_text_parts = []
    ocr_failed = False
    try:
        for page in doc:
            # Render page to image (avoids need for pdf2image/poppler)
            pix = page.get_pixmap(dpi=150)
            img_bytes = pix.tobytes("png")
            img = Image.open(io.BytesIO(img_bytes))

            # Perform OCR (requires Tesseract installed on system)
            text = pytesseract.image_to_string(img)
            ocr_text_parts.append(text)

        raw_ocr_text = "\n\n".join(ocr_text_parts)
        cleaned_ocr = clean_text(raw_ocr_text)

        if len(cleaned_ocr) >= 200:
            return ExtractionResult(
                success=True,
                raw_text=raw_ocr_text,
                cleaned_text=cleaned_ocr,
                page_count=page_count
            )

    except Exception:
        # Tesseract likely not installed or failed during execution
        ocr_failed = True

    # If we fall through to here, either OCR was attempted and failed to clear the threshold,
    # or the OCR process itself threw an exception (e.g. Tesseract missing).

    # If the original cleaned text was completely empty and OCR also failed/empty, we can return empty_pdf.
    # Otherwise, we return extraction_failed as per requirements.
    if len(cleaned) == 0 and ocr_failed:
        return ExtractionResult(
            success=False,
            error="empty_pdf",
            message="No readable text was found in this document."
        )
    else:
        return ExtractionResult(
            success=False,
            error="extraction_failed",
            message="Text extraction failed after retry."
        )

def chunk_text(cleaned_text: str) -> list[str]:
    """
    Splits cleaned_text into chunks of approximately 500-1000 tokens each.
    Uses word count * 1.3 as a token estimate.
    Splits on paragraph/sentence boundaries where possible.
    Ensures chunks reconstruct back to the original text.
    Returns at least 1 chunk even for short documents.
    """
    if not cleaned_text:
        return [cleaned_text] if cleaned_text else []

    # Target ~750 words per chunk (approx 975 tokens)
    max_words = 750

    chunks = []
    current_chunk_parts = []
    current_word_count = 0

    # Split by paragraph boundaries, keeping the delimiter for reconstruction
    paragraphs = re.split(r'(\n\n+)', cleaned_text)

    def add_current_chunk():
        nonlocal current_chunk_parts, current_word_count, chunks
        if current_chunk_parts:
            # Reconstruct the chunk and strip trailing paragraph breaks so chunks don't end with huge whitespace
            # Actually, the prompt says "reconstructs back to approximately the original cleaned_text"
            # It's safest to just join exactly.
            chunks.append("".join(current_chunk_parts))
            current_chunk_parts = []
            current_word_count = 0

    for part in paragraphs:
        if not part.strip():
            # It's a delimiter (newlines)
            current_chunk_parts.append(part)
            continue

        part_words = len(part.split())

        # If adding this paragraph exceeds max words and we already have content
        if current_word_count + part_words > max_words and current_word_count > 0:
            add_current_chunk()

        # If the paragraph ITSELF is larger than max_words, we need to split it by sentences
        if part_words > max_words:
            # Split by sentence boundaries, keeping the delimiter in the list
            sentences = re.split(r'([.!?](?:\s+|$))', part)

            for s_part in sentences:
                s_words = len(s_part.split())
                if current_word_count + s_words > max_words and current_word_count > 0:
                    add_current_chunk()
                current_chunk_parts.append(s_part)
                current_word_count += s_words
        else:
            current_chunk_parts.append(part)
            current_word_count += part_words

    if current_chunk_parts:
        add_current_chunk()

    # If chunks is empty but cleaned_text wasn't, return it as one chunk
    if not chunks:
        return [cleaned_text]

    return chunks
