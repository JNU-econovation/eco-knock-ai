from typing import List, Dict


def split_long_text(text: str, max_length: int = 500) -> List[str]:
    if len(text) <= max_length:
        return [text]

    parts = []
    current = ""

    sentences = text.replace(". ", ".\n").splitlines()

    for sentence in sentences:
        sentence = sentence.strip()
        if not sentence:
            continue

        if len(current) + len(sentence) + 1 <= max_length:
            current = f"{current} {sentence}".strip()
        else:
            if current:
                parts.append(current)
            current = sentence

    if current:
        parts.append(current)

    return parts


def chunk_markdown_text(
    text: str,
    source: str,
    min_length: int = 20,
    max_length: int = 500
) -> List[Dict]:
    lines = text.splitlines()

    sections = []
    current_title_parts = []
    current_content = []

    for line in lines:
        stripped = line.strip()

        if not stripped:
            continue

        if stripped.startswith("#"):
            if current_content:
                full_title = " > ".join(current_title_parts) if current_title_parts else "untitled"
                sections.append(
                    {
                        "title": full_title,
                        "content": " ".join(current_content).strip()
                    }
                )
                current_content = []

            level = len(stripped) - len(stripped.lstrip("#"))
            title_text = stripped.lstrip("#").strip()

            if level == 1:
                current_title_parts = [title_text]
            elif level == 2:
                current_title_parts = current_title_parts[:1] + [title_text]
            elif level >= 3:
                base = current_title_parts[:2]
                current_title_parts = base + [title_text]

        else:
            current_content.append(stripped)

    if current_content:
        full_title = " > ".join(current_title_parts) if current_title_parts else "untitled"
        sections.append(
            {
                "title": full_title,
                "content": " ".join(current_content).strip()
            }
        )

    chunks = []
    chunk_id = 0

    for section in sections:
        title = section["title"]
        content = section["content"]

        if len(content) < min_length:
            continue

        split_parts = split_long_text(content, max_length=max_length)

        for idx, part in enumerate(split_parts):
            part = part.strip()
            if len(part) < min_length:
                continue

            chunk_title = title if len(split_parts) == 1 else f"{title} ({idx + 1})"

            chunks.append(
                {
                    "chunk_id": chunk_id,
                    "title": chunk_title,
                    "text": part,
                    "source": source,
                }
            )
            chunk_id += 1

    return chunks


def chunk_text( 
    text: str,
    source: str,
    min_length: int = 20,
    max_length: int = 500
) -> List[Dict]:
    return chunk_markdown_text(
        text=text,
        source=source,
        min_length=min_length,
        max_length=max_length,
    )