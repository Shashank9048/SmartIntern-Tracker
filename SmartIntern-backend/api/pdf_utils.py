import pypdf
from fastapi import UploadFile
import io

async def extract_text_from_pdf(file: UploadFile) -> str:
    """
    Extracts text from an uploaded PDF file using pypdf.
    """
    try:
        # Read the file content into memory
        content = await file.read()
        
        # Create a PDF reader object
        pdf_reader = pypdf.PdfReader(io.BytesIO(content))
        
        text = ""
        # Iterate through all pages and extract text
        for page in pdf_reader.pages:
            text += page.extract_text() + "\n"
            
        # Reset file cursor for potential future use (good practice)
        await file.seek(0)
        
        return text.strip()
    except Exception as e:
        print(f"Error extracting PDF text: {e}")
        return ""
