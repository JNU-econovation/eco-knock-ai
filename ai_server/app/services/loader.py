from pathlib import Path


def load_document(file_path: str) -> str:
    path = Path(file_path)

    if not path.exists():
        raise FileNotFoundError(f"file not found: {file_path}")

    if path.suffix.lower() != ".md":
        raise ValueError(f"unsupported file type: {path.suffix} (only .md allowed)")

    return path.read_text(encoding="utf-8").strip()
