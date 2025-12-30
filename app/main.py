# app/main.py
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.services import init_db
from app.api.routes import router as api_router


app = FastAPI(title="Anamnesis API", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # for dev; tighten in prod
    allow_methods=["*"],
    allow_headers=["*"],
    allow_credentials=True,
)


@app.on_event("startup")
def on_startup() -> None:
    init_db()


@app.get("/")
def root():
    return {"message": "Anamnesis API is running"}


app.include_router(api_router, prefix="/api")
