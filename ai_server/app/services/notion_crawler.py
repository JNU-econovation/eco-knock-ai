import argparse
import os
import time
from pathlib import Path

import requests
from dotenv import load_dotenv

load_dotenv()

NOTION_API_URL = "https://api.notion.com/v1"
NOTION_VERSION = "2022-06-28"
REQUEST_TIMEOUT = 30
MAX_RETRIES = 3
RETRY_DELAY = 2
REQUEST_DELAY = 1.0
MAX_DEPTH = 6
NON_NESTING_TYPES = {"column_list", "column"}
DATA_DIR = Path(__file__).resolve().parents[2] / "data"

WEEKLY_PAGE_IDS = [
    "1a830b4e-356c-8064-979d-e6134d50583d",  # 멘토링
    "13e30b4e-356c-8033-96e3-f252d6d322c8",  # Econovation
]

MONTHLY_PAGE_IDS = [
    "1be30b4e-356c-801d-9da4-ea0abc4cf701",  # Contributors
    "25730b4e-356c-8003-abf9-e21b6ee66f40",  # 동아리방 대청소
    "19f30b4e-356c-80c5-8416-e2aad3c7785c",  # 알림아리
    "25330b4e-356c-806e-baf9-f39c0de10ec2",  # 여름 야유회
]

TEXT_BLOCK_TYPES = {
    "paragraph",
    "heading_1",
    "heading_2",
    "heading_3",
    "heading_4",
    "bulleted_list_item",
    "to_do",
    "quote",
    "toggle",
    "callout",
    "code",
    "equation",
}

def _headers() -> dict:
    token = os.getenv("NOTION_TOKEN")
    if not token:
        raise RuntimeError("NOTION_TOKEN 환경변수가 설정되지 않았습니다.")
    return {
        "Authorization": f"Bearer {token}",
        "Notion-Version": NOTION_VERSION,
        "Content-Type": "application/json",
    }


def _rich_text_to_plain(rich_text: list[dict]) -> str:
    return "".join(t.get("plain_text", "") for t in rich_text)


def _request_json(method: str, url: str, **kwargs) -> dict | None:
    for attempt in range(1, MAX_RETRIES + 1):
        try:
            resp = requests.request(method, url, headers=_headers(), timeout=REQUEST_TIMEOUT, **kwargs)

            if resp.status_code == 400:
                print(f"400 Bad Request, 건너뜀: {url}")
                return None
            if resp.status_code == 404:
                print(f"404 Not Found, 건너뜀: {url}")
                return None

            resp.raise_for_status()
            return resp.json()
        except requests.exceptions.RequestException as e:
            if attempt == MAX_RETRIES:
                print(f"요청 실패, 건너뜀: {url} ({e})")
                return None
            print(f"요청 실패, {RETRY_DELAY}초 후 재시도 ({attempt}/{MAX_RETRIES}): {url} ({e})")
            time.sleep(RETRY_DELAY)

    return None


def _get_page_title(page_id: str) -> str:
    data = _request_json("GET", f"{NOTION_API_URL}/pages/{page_id}")
    if not data:
        return "제목 없음"

    properties = data.get("properties", {})
    for prop in properties.values():
        if prop.get("type") == "title":
            return _rich_text_to_plain(prop.get("title", [])) or "제목 없음"

    return "제목 없음"


def _get_block_children(block_id: str) -> list[dict]:
    blocks = []
    url = f"{NOTION_API_URL}/blocks/{block_id}/children"
    params = {"page_size": 100}

    while True:
        data = _request_json("GET", url, params=params)
        if data is None:
            break
        blocks.extend(data.get("results", []))

        if not data.get("has_more"):
            break
        params["start_cursor"] = data["next_cursor"]
        time.sleep(REQUEST_DELAY)

    return blocks


def _get_database_rows(database_id: str) -> list[dict]:
    data = _request_json(
        "POST",
        f"{NOTION_API_URL}/databases/{database_id}/query",
        json={"page_size": 100},
    )
    return data.get("results", []) if data else []


def _get_row_title(row: dict) -> str:
    properties = row.get("properties", {})
    for prop in properties.values():
        if prop.get("type") == "title":
            return _rich_text_to_plain(prop.get("title", [])) or "제목 없음"
    return "제목 없음"


def _property_to_text(name: str, prop: dict) -> str | None:
    ptype = prop.get("type")

    if ptype == "rich_text":
        text = _rich_text_to_plain(prop.get("rich_text", []))
        return f"{name}: {text}" if text else None
    if ptype == "date":
        date = prop.get("date")
        if not date or not date.get("start"):
            return None
        value = date["start"]
        if date.get("end"):
            value = f"{value} ~ {date['end']}"
        return f"{name}: {value}"
    if ptype == "select":
        select = prop.get("select")
        return f"{name}: {select['name']}" if select else None
    if ptype == "multi_select":
        options = prop.get("multi_select", [])
        return f"{name}: {', '.join(o['name'] for o in options)}" if options else None
    if ptype == "status":
        status = prop.get("status")
        return f"{name}: {status['name']}" if status else None
    if ptype == "checkbox":
        return f"{name}: {'O' if prop.get('checkbox') else 'X'}"
    if ptype == "number":
        number = prop.get("number")
        return f"{name}: {number}" if number is not None else None
    if ptype == "people":
        names = [p.get("name") for p in prop.get("people", []) if p.get("name")]
        return f"{name}: {', '.join(names)}" if names else None

    return None


def _row_properties_to_lines(row: dict) -> list[str]:
    lines = []
    for name, prop in row.get("properties", {}).items():
        if prop.get("type") == "title":
            continue
        text = _property_to_text(name, prop)
        if text:
            lines.append(text)
    return lines


def _block_to_text(block: dict) -> str | None:
    block_type = block.get("type")
    if block_type not in TEXT_BLOCK_TYPES:
        return None

    content = block.get(block_type, {})

    if block_type == "equation":
        expression = content.get("expression", "")
        return expression or None

    text = _rich_text_to_plain(content.get("rich_text", []))
    if not text:
        return None

    if block_type == "heading_1":
        return f"## {text}"
    if block_type == "heading_2":
        return f"### {text}"
    if block_type == "heading_3":
        return f"#### {text}"
    if block_type == "heading_4":
        return f"##### {text}"
    if block_type == "bulleted_list_item":
        return f"- {text}"
    if block_type == "to_do":
        checked = content.get("checked", False)
        return f"- [{'x' if checked else ' '}] {text}"
    if block_type == "quote":
        return f"> {text}"
    if block_type == "toggle":
        return f"- {text}"
    if block_type == "callout":
        icon = content.get("icon") or {}
        emoji = icon.get("emoji") if icon.get("type") == "emoji" else "📢"
        return f"[{emoji}] {text}"

    return text


def _crawl_blocks(block_id: str, lines: list[str], depth: int = 0) -> None:
    if depth >= MAX_DEPTH:
        return

    blocks = _get_block_children(block_id)
    time.sleep(REQUEST_DELAY)

    counter = 0
    for block in blocks:
        block_type = block.get("type")

        if block_type == "numbered_list_item":
            counter += 1
            text = _rich_text_to_plain(block.get("numbered_list_item", {}).get("rich_text", []))
            if text:
                lines.append(f"{counter}. {text}")
            if block.get("has_children"):
                _crawl_blocks(block["id"], lines, depth + 1)
            continue

        counter = 0

        if block_type == "child_page":
            lines.append(_crawl_page(block["id"], depth + 1))
            continue

        if block_type == "child_database":
            title = block.get("child_database", {}).get("title", "제목 없음")
            lines.append(f"## {title}")
            rows = _get_database_rows(block["id"])
            time.sleep(REQUEST_DELAY)
            for row in rows:
                lines.append(f"## {_get_row_title(row)}")
                lines.extend(_row_properties_to_lines(row))
                _crawl_blocks(row["id"], lines, depth + 1)
            continue

        if block_type == "table_row":
            cells = block.get("table_row", {}).get("cells", [])
            texts = [_rich_text_to_plain(cell) for cell in cells]
            if any(texts):
                lines.append(f"| {' | '.join(texts)} |")
            continue

        if block_type == "synced_block":
            synced_from = block.get("synced_block", {}).get("synced_from")
            target_id = synced_from["block_id"] if synced_from else block["id"]
            _crawl_blocks(target_id, lines, depth + 1)
            continue

        text = _block_to_text(block)
        if text:
            lines.append(text)

        if block.get("has_children"):
            next_depth = depth if block_type in NON_NESTING_TYPES else depth + 1
            _crawl_blocks(block["id"], lines, next_depth)


def _crawl_page(page_id: str, depth: int = 0) -> str:
    title = _get_page_title(page_id)
    time.sleep(REQUEST_DELAY)

    lines = [f"## {title}"]
    _crawl_blocks(page_id, lines, depth)
    lines.append("")
    lines.append("---")
    lines.append("")

    return "\n".join(lines)


def _slugify_title(title: str) -> str:
    return title.strip().lower().replace(" ", "_").replace("/", "_")


def crawl_notion(page_ids: list[str]) -> int:
    DATA_DIR.mkdir(parents=True, exist_ok=True)

    total_start = time.monotonic()

    for i, page_id in enumerate(page_ids, 1):
        print(f"[{i}/{len(page_ids)}] {page_id}")
        page_start = time.monotonic()

        title = _get_page_title(page_id)
        time.sleep(REQUEST_DELAY)

        lines = [f"## {title}"]
        _crawl_blocks(page_id, lines)

        output_path = DATA_DIR / f"notion_{_slugify_title(title)}.md"
        output_path.write_text("\n".join(lines), encoding="utf-8")

        page_elapsed = time.monotonic() - page_start
        print(f"저장 완료: {output_path} ({page_elapsed:.1f}초)")

    total_elapsed = time.monotonic() - total_start
    print(f"크롤링 완료. 총 {len(page_ids)}개 페이지 저장. 총 소요시간: {total_elapsed:.1f}초 ({total_elapsed / 60:.1f}분)")
    return len(page_ids)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--group", choices=["weekly", "monthly"], default=None)
    args = parser.parse_args()

    if args.group == "weekly":
        target_page_ids = WEEKLY_PAGE_IDS
    elif args.group == "monthly":
        target_page_ids = MONTHLY_PAGE_IDS
    else:
        target_page_ids = WEEKLY_PAGE_IDS + MONTHLY_PAGE_IDS

    crawl_notion(target_page_ids)
