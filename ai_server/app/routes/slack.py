import hashlib
import hmac
import json
import os
import re
import time
from datetime import datetime
from pathlib import Path
from urllib.parse import parse_qs

from fastapi import APIRouter, BackgroundTasks, HTTPException, Request
from fastapi.responses import JSONResponse, PlainTextResponse

from app.services.chunker import chunk_markdown_text
from app.services.retriever import retriever

router = APIRouter(tags=["slack"])

SLACK_SIGNING_SECRET = os.getenv("SLACK_SIGNING_SECRET", "")
SIGNATURE_TOLERANCE_SECONDS = 60 * 5

DATA_DIR = Path(__file__).resolve().parents[2] / "data"
SLACK_NOTICES_FILE = DATA_DIR / "slack_notices.md"
SLACK_NOTICES_SOURCE = "data/slack_notices.md"


def _verify_slack_signature(body: bytes, timestamp: str, signature: str) -> bool:
    if not timestamp or not signature:
        return False

    try:
        if abs(time.time() - float(timestamp)) > SIGNATURE_TOLERANCE_SECONDS:
            return False
    except ValueError:
        return False

    basestring = f"v0:{timestamp}:{body.decode('utf-8')}"
    expected = "v0=" + hmac.new(
        SLACK_SIGNING_SECRET.encode(), basestring.encode(), hashlib.sha256
    ).hexdigest()

    return hmac.compare_digest(expected, signature)


def _parse_body(raw_body: bytes, content_type: str) -> dict:
    try:
        if "application/json" in content_type:
            return json.loads(raw_body)
        parsed = parse_qs(raw_body.decode())
        return {k: v[0] for k, v in parsed.items()}
    except Exception:
        return {}


def _reindex_notice(text: str, ts: str) -> None:
    try:
        posted_at = datetime.fromtimestamp(float(ts)).strftime("%Y-%m-%d")
    except ValueError:
        posted_at = ts

    first_line = text.strip().splitlines()[0][:50]
    chunk_text = f"## 슬랙 공지 ({posted_at}) - {first_line}\n{text}"
    chunks = chunk_markdown_text(text=chunk_text, source=SLACK_NOTICES_SOURCE)
    retriever.add_chunks(chunks, extra_metadata={"slack_ts": ts})


def _append_notice_and_index(text: str, ts: str) -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    with open(SLACK_NOTICES_FILE, "a", encoding="utf-8") as f:
        f.write(f"\n## 공지 ({ts})\n{text}\n")

    try:
        _reindex_notice(text, ts)
    except Exception as e:
        print(f"슬랙 공지 인덱싱 실패: {e}")


def _update_notice_and_reindex(text: str, ts: str) -> None:
    if not SLACK_NOTICES_FILE.exists():
        print(f"슬랙 공지 수정 실패: {ts} - slack_notices.md 없음")
        return

    content = SLACK_NOTICES_FILE.read_text(encoding="utf-8")
    header = f"## 공지 ({ts})"
    pattern = re.compile(re.escape(header) + r"\n.*?(?=\n## |\Z)", re.DOTALL)

    new_content, count = pattern.subn(lambda m: f"{header}\n{text}\n", content, count=1)
    if count == 0:
        print(f"슬랙 공지 수정 실패: {ts}에 해당하는 공지를 찾을 수 없음")
        return

    SLACK_NOTICES_FILE.write_text(new_content, encoding="utf-8")

    try:
        retriever.delete_chunks({"$and": [{"source": SLACK_NOTICES_SOURCE}, {"slack_ts": ts}]})
        _reindex_notice(text, ts)
    except Exception as e:
        print(f"슬랙 공지 재인덱싱 실패: {e}")


@router.post("/slack/events")
async def slack_events(request: Request, background_tasks: BackgroundTasks):
    raw_body = await request.body()

    timestamp = request.headers.get("X-Slack-Request-Timestamp", "")
    signature = request.headers.get("X-Slack-Signature", "")

    if SLACK_SIGNING_SECRET and not _verify_slack_signature(raw_body, timestamp, signature):
        raise HTTPException(status_code=403, detail="invalid slack signature")

    body = _parse_body(raw_body, request.headers.get("content-type", ""))

    if body.get("type") == "url_verification":
        return PlainTextResponse(content=body.get("challenge", ""))

    if request.headers.get("X-Slack-Retry-Num"):
        return JSONResponse({"ok": True})

    event = body.get("event", {})

    if event.get("type") == "message":
        subtype = event.get("subtype")

        if subtype is None and not event.get("bot_id"):
            text = event.get("text", "").strip()
            ts = event.get("ts", "")
            if text:
                background_tasks.add_task(_append_notice_and_index, text, ts)
        elif subtype == "message_changed":
            new_message = event.get("message", {})
            if not new_message.get("bot_id"):
                text = new_message.get("text", "").strip()
                ts = new_message.get("ts", "")
                if text:
                    background_tasks.add_task(_update_notice_and_reindex, text, ts)

    return JSONResponse({"ok": True})
