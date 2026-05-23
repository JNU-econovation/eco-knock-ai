import re
import time
from pathlib import Path
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup

BASE_URL = "https://jnu-econovation.github.io"
CATEGORIES_URL = f"{BASE_URL}/categories.html"
DATA_DIR = Path(__file__).resolve().parents[2] / "data"

CATEGORY_FILE_MAP = {
    "SUMMER/WINTER_DEV": "blog_dev.md",
    "ECONO_NEWS": "blog_news.md",
}
DEFAULT_FILE = "blog_etc.md"


def _get_soup(url: str) -> BeautifulSoup:
    resp = requests.get(url, timeout=10)
    resp.raise_for_status()
    resp.encoding = resp.apparent_encoding
    return BeautifulSoup(resp.text, "html.parser")


def _collect_post_links() -> list[dict]:
    # ul.page-segments-list 안에 h2.segment-name과 li가 혼합된 구조

    soup = _get_soup(CATEGORIES_URL)
    posts = []

    container = soup.select_one("ul.page-segments-list")
    if not container:
        return posts

    current_category = "기타"
    for child in container.children:
        if child.name == "h2":
            current_category = child.get_text(strip=True)
        elif child.name == "li":
            a_tag = child.select_one("a.post-link")
            if a_tag:
                href = a_tag["href"]
                full_url = urljoin(BASE_URL, href)
                if urlparse(full_url).netloc == urlparse(BASE_URL).netloc:
                    posts.append({"url": full_url, "category": current_category})

    return posts


def _date_from_url(url: str) -> str:
    m = re.search(r"/(\d{4})/(\d{2})/(\d{2})/", url)
    return f"{m.group(1)}-{m.group(2)}-{m.group(3)}" if m else ""


def _parse_post(url: str) -> dict | None:
    try:
        soup = _get_soup(url)
    except requests.RequestException:
        return None

    content_tag = soup.select_one(".post-content")
    if not content_tag:
        return None

    title_tag = content_tag.find("h1") or content_tag.find("h2")
    title = title_tag.get_text(strip=True) if title_tag else "제목 없음"

    if title_tag:
        title_tag.decompose()

    body = content_tag.get_text(separator="\n", strip=True)
    date = _date_from_url(url)

    return {"title": title, "date": date, "body": body}


def _determine_output_file(category: str) -> str:
    for key, filename in CATEGORY_FILE_MAP.items():
        if key in category.upper():
            return filename
    return DEFAULT_FILE


def _format_post(post_meta: dict, post_data: dict) -> str:
    lines = [
        f"## {post_data['title']}",
        f"날짜: {post_data['date']}",
        post_data["body"],
        "",
        "---",
        "",
    ]
    return "\n".join(lines)


def crawl_blog() -> dict[str, int]:
    DATA_DIR.mkdir(parents=True, exist_ok=True)

    print("글 링크 수집 중...")
    posts_meta = _collect_post_links()
    print(f"총 {len(posts_meta)}개 링크 수집 완료")

    file_buffers: dict[str, list[str]] = {}

    for i, meta in enumerate(posts_meta, 1):
        print(f"[{i}/{len(posts_meta)}] {meta['url']}")
        post_data = _parse_post(meta["url"])

        if post_data:
            filename = _determine_output_file(meta["category"])
            file_buffers.setdefault(filename, [])
            file_buffers[filename].append(_format_post(meta, post_data))

        time.sleep(1)

    counts: dict[str, int] = {}
    for filename, chunks in file_buffers.items():
        output_path = DATA_DIR / filename
        output_path.write_text("\n".join(chunks), encoding="utf-8")
        counts[filename] = len(chunks)
        print(f"저장 완료: {output_path} ({len(chunks)}개 글)")

    print(f"크롤링 완료. 총 {sum(counts.values())}개 글 저장.")
    return counts


if __name__ == "__main__":
    crawl_blog()
