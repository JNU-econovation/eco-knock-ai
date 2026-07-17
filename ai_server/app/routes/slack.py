import hashlib
import hmac
import json
import os
import time
from urllib.parse import parse_qs

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import JSONResponse, PlainTextResponse

router = APIRouter(tags=["slack"])

SLACK_SIGNING_SECRET = os.getenv("SLACK_SIGNING_SECRET", "")
SIGNATURE_TOLERANCE_SECONDS = 60 * 5


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


@router.post("/slack/events")
async def slack_events(request: Request):
    raw_body = await request.body()

    timestamp = request.headers.get("X-Slack-Request-Timestamp", "")
    signature = request.headers.get("X-Slack-Signature", "")

    if SLACK_SIGNING_SECRET and not _verify_slack_signature(raw_body, timestamp, signature):
        raise HTTPException(status_code=403, detail="invalid slack signature")

    body = _parse_body(raw_body, request.headers.get("content-type", ""))

    if body.get("type") == "url_verification":
        return PlainTextResponse(content=body.get("challenge", ""))

    return JSONResponse({"ok": True})
