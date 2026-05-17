from pathlib import Path
import fitz


def load_pdf_text(file_path: str) -> str:
    doc = fitz.open(file_path)
    pages = []

    for page in doc:
        text = page.get_text("text")
        if text:
            pages.append(text.strip())

    doc.close()
    return "\n\n".join(pages)


def load_text_file(file_path: str) -> str:
    return Path(file_path).read_text(encoding="utf-8").strip()


def load_document(file_path: str) -> str:
    path = Path(file_path)

    if not path.exists():
        raise FileNotFoundError(f"file not found: {file_path}")

    suffix = path.suffix.lower()

    if suffix == ".pdf":
        return load_pdf_text(file_path)

    if suffix in [".md", ".txt"]:
        return load_text_file(file_path)

    raise ValueError(f"unsupported file type: {suffix}")