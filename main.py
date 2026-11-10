import os

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from dotenv import load_dotenv
from supabase import create_client

load_dotenv()

# 로컬에선 .env를 읽고, Railway에선 Variables가 이미 들어 있음
SUPABASE_URL = os.environ["SUPABASE_URL"]
SUPABASE_SECRET_KEY = os.environ["SUPABASE_SECRET_KEY"]
# 로컬 프론트 테스트용 origin은 기본 허용, 배포 도메인은 FRONT_ORIGINS에 추가
FRONT_ORIGINS = ["http://localhost:3000", "http://127.0.0.1:3000"] + [
    o.strip() for o in os.getenv("FRONT_ORIGINS", "").split(",") if o.strip()
]

sb = create_client(SUPABASE_URL, SUPABASE_SECRET_KEY)

app = FastAPI(title="my-api")

app.add_middleware(
    CORSMiddleware,
    allow_origins=FRONT_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class Note(BaseModel):
    content: str


@app.get("/health")
def health():
    return {"status": "ok"}

@app.get("v")
def health2():
    return {"s":"100", "t":"200"}


@app.get("/health/db")
def health_db():
    """Supabase 연결 확인 (notes 테이블 조회)"""
    try:
        sb.table("notes").select("id").limit(1).execute()
        return {"status": "ok", "supabase": "connected"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Supabase error: {e}")


@app.get("/notes")
def list_notes():
    try:
        res = sb.table("notes").select("*").order("id", desc=True).limit(50).execute()
        return res.data
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/notes", status_code=201)
def create_note(note: Note):
    try:
        res = sb.table("notes").insert({"content": note.content}).execute()
        return res.data[0]
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
