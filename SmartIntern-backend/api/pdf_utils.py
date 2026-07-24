import pypdf
import io
import os
from fastapi import UploadFile


async def extract_text_from_pdf(file: UploadFile) -> str:
    """
    Extracts text from an uploaded PDF or DOCX file.
    Detects file type by extension and routes to the correct parser.
    """
    filename = file.filename or ""
    ext = os.path.splitext(filename)[1].lower()

    try:
        content = await file.read()

        if ext == ".pdf":
            return _extract_from_pdf_bytes(content)
        elif ext in (".docx",):
            return _extract_from_docx_bytes(content)
        elif ext in (".doc",):
            # .doc is legacy binary format — extract what we can as raw text
            return _extract_raw_text(content)
        else:
            # Fallback: try PDF first, then raw
            try:
                return _extract_from_pdf_bytes(content)
            except Exception:
                return _extract_raw_text(content)

    except Exception as e:
        print(f"Error extracting text from file '{filename}': {e}")
        return ""
    finally:
        # Always reset cursor
        try:
            await file.seek(0)
        except Exception:
            pass


def _extract_from_pdf_bytes(content: bytes) -> str:
    """Extract text from PDF bytes using pypdf."""
    pdf_reader = pypdf.PdfReader(io.BytesIO(content))
    pages_text = []
    for page in pdf_reader.pages:
        page_text = page.extract_text()
        if page_text:
            pages_text.append(page_text)
    return "\n".join(pages_text).strip()


def _extract_from_docx_bytes(content: bytes) -> str:
    """Extract text from DOCX bytes using python-docx."""
    try:
        import docx  # python-docx
        doc = docx.Document(io.BytesIO(content))
        paragraphs = [p.text for p in doc.paragraphs if p.text.strip()]
        return "\n".join(paragraphs).strip()
    except ImportError:
        print("python-docx not installed. Run: pip install python-docx")
        return _extract_raw_text(content)
    except Exception as e:
        print(f"DOCX extraction error: {e}")
        return _extract_raw_text(content)


def _extract_raw_text(content: bytes) -> str:
    """Last-resort: decode bytes as UTF-8 ignoring errors."""
    try:
        return content.decode("utf-8", errors="ignore").strip()
    except Exception:
        return ""
