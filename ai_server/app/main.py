from fastapi import FastAPI
from app.routes.chat import router as chat_router
from app.routes.documents import router as documents_router

app = FastAPI(title="club ai server")

app.include_router(documents_router)
app.include_router(chat_router)

@app.get("/")
def root():
    return {"message": "club ai server is running"}

@app.get("/health")
def health_check():
    return {"status": "ok"}