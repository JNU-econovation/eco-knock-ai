from fastapi import APIRouter, Request
from fastapi.responses import PlainTextResponse

router = APIRouter(tags=["slack"])

@router.post("/slack/events")
async def slack_events(request: Request):
    body = await request.json()

    if body.get("type") == "url_verification":
        return PlainTextResponse(body["challenge"])

    return {"ok": True}
