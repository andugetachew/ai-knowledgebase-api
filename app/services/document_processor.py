import io
import csv
from pathlib import Path


def extract_text_from_pdf(content: bytes) -> str:
    import fitz  # pymupdf
    doc = fitz.open(stream=content, filetype="pdf")
    text = ""
    for page in doc:
        text += page.get_text()
    doc.close()
    return text.strip()


def extract_text_from_docx(content: bytes) -> str:
    from docx import Document
    doc = Document(io.BytesIO(content))
    return "\n".join([para.text for para in doc.paragraphs if para.text.strip()])


def extract_text_from_csv(content: bytes) -> str:
    text = content.decode("utf-8", errors="ignore")
    reader = csv.reader(io.StringIO(text))
    rows = []
    for row in reader:
        rows.append(" | ".join(row))
    return "\n".join(rows)


def extract_text_from_txt(content: bytes) -> str:
    return content.decode("utf-8", errors="ignore")


async def extract_text_from_url(url: str) -> str:
    import httpx
    from bs4 import BeautifulSoup
    async with httpx.AsyncClient(timeout=15) as client:
        response = await client.get(url)
        response.raise_for_status()
    soup = BeautifulSoup(response.text, "html.parser")
    for tag in soup(["script", "style", "nav", "footer", "header"]):
        tag.decompose()
    return soup.get_text(separator="\n", strip=True)


def extract_text(content: bytes, content_type: str) -> str:
    """Route to correct extractor based on content type."""
    if content_type == "application/pdf":
        return extract_text_from_pdf(content)
    elif content_type in (
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        "application/msword",
    ):
        return extract_text_from_docx(content)
    elif content_type == "text/csv":
        return extract_text_from_csv(content)
    else:
        return extract_text_from_txt(content)