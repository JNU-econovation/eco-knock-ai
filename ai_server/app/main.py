import os
from pathlib import Path
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse
from app.routes.chat import router as chat_router
from app.routes.documents import router as documents_router
from app.routes.slack import router as slack_router

app = FastAPI(title="club ai server")

_origins_env = os.getenv("ALLOWED_ORIGINS", "*")
origins = [o.strip() for o in _origins_env.split(",")] if _origins_env != "*" else ["*"]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(documents_router)
app.include_router(chat_router)
app.include_router(slack_router)

@app.get("/")
def root():
    return {"message": "club ai server is running"}

@app.get("/health")
def health_check():
    return {"status": "ok"}

@app.get("/api-spec", response_class=HTMLResponse)
async def api_spec():
    html_path = Path(__file__).parent / "static" / "api-docs.html"
    return HTMLResponse(content=html_path.read_text(encoding="utf-8"))