import logging
import os
import re

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from dotenv import load_dotenv
from supabase import create_client

load_dotenv()

# 로컬에선 .env를 읽고, Railway에선 Variables가 이미 들어 있음
SUPABASE_URL = os.environ["SUPABASE_URL"]
SUPABASE_SECRET_KEY = os.environ["SUPABASE_SECRET_KEY"]
# Railway에서 실행 중이면 RAILWAY_ENVIRONMENT 가 자동으로 들어 있음 → 운영(prod)
IS_PROD = bool(os.getenv("RAILWAY_ENVIRONMENT"))

# [보안] CORS: 허용할 프론트 주소는 환경변수 FRONT_ORIGINS 로만 지정 (쉼표로 구분)
#   예) https://my-shop.vercel.app   ← 끝에 / 붙이지 않기
FRONT_ORIGINS = [
    o.strip().rstrip("/") for o in os.getenv("FRONT_ORIGINS", "").split(",") if o.strip()
]
if not IS_PROD:  # 내 컴퓨터에서 테스트할 때만 localhost 허용 (운영에서는 불가)
    FRONT_ORIGINS += ["http://localhost:3000", "http://127.0.0.1:3000"]

sb = create_client(SUPABASE_URL, SUPABASE_SECRET_KEY)

# [보안] 운영에서는 API 설명서(/docs)를 숨김 (필요하면 ENABLE_DOCS=1 변수 추가)
SHOW_DOCS = (not IS_PROD) or os.getenv("ENABLE_DOCS") == "1"
app = FastAPI(
    title="my-api",
    docs_url="/docs" if SHOW_DOCS else None,
    redoc_url=None,
    openapi_url="/openapi.json" if SHOW_DOCS else None,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=FRONT_ORIGINS,
    allow_credentials=False,  # 쿠키를 쓰지 않으므로 끔
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
    allow_headers=["Content-Type"],
)


class Note(BaseModel):
    content: str


@app.get("/health")
def health():
    return {"status": "ok"}

@app.get("/v")
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


# ───────────────────────── 장바구니 (cart) ─────────────────────────
# 로그인 없이 쓰는 데모라서, 브라우저가 만든 임의의 cart_id(UUID)로 장바구니를 구분함
logger = logging.getLogger("my-api")
CART_ID_RE = re.compile(r"^[A-Za-z0-9-]{16,64}$")


class AddItem(BaseModel):
    product_id: int = Field(gt=0)
    quantity: int = Field(default=1, ge=1, le=99)


class SetQty(BaseModel):
    quantity: int = Field(ge=0, le=99)  # 0 이면 삭제


def valid_cart(cart_id: str) -> str:
    if not CART_ID_RE.match(cart_id):
        raise HTTPException(status_code=400, detail="invalid cart id")
    return cart_id


def server_error(e: Exception):
    # [보안] 내부 오류 내용은 로그에만 남기고, 사용자에게는 일반 메시지만 전달
    logger.exception("cart error: %s", e)
    raise HTTPException(status_code=500, detail="서버 오류가 발생했어요")


def load_cart(cart_id: str):
    res = (
        sb.table("cart_items")
        .select("quantity, products(id, name, price, emoji)")
        .eq("cart_id", cart_id)
        .order("id")
        .execute()
    )
    items = []
    for r in res.data:
        p = r["products"]
        items.append(
            {
                "product_id": p["id"],
                "name": p["name"],
                "price": p["price"],
                "emoji": p["emoji"],
                "quantity": r["quantity"],
                "subtotal": p["price"] * r["quantity"],
            }
        )
    return {
        "items": items,
        "count": sum(i["quantity"] for i in items),
        "total": sum(i["subtotal"] for i in items),
    }


@app.get("/products")
def list_products():
    try:
        res = sb.table("products").select("*").order("id").execute()
        return res.data
    except Exception as e:
        server_error(e)


@app.get("/cart/{cart_id}")
def get_cart(cart_id: str):
    valid_cart(cart_id)
    try:
        return load_cart(cart_id)
    except Exception as e:
        server_error(e)


@app.post("/cart/{cart_id}/items")
def add_to_cart(cart_id: str, body: AddItem):
    valid_cart(cart_id)
    try:
        prod = sb.table("products").select("id").eq("id", body.product_id).execute()
        if not prod.data:
            raise HTTPException(status_code=404, detail="상품을 찾을 수 없어요")
        cur = (
            sb.table("cart_items")
            .select("quantity")
            .eq("cart_id", cart_id)
            .eq("product_id", body.product_id)
            .execute()
        )
        if cur.data:
            new_q = min(99, cur.data[0]["quantity"] + body.quantity)
            (
                sb.table("cart_items")
                .update({"quantity": new_q})
                .eq("cart_id", cart_id)
                .eq("product_id", body.product_id)
                .execute()
            )
        else:
            sb.table("cart_items").insert(
                {"cart_id": cart_id, "product_id": body.product_id, "quantity": body.quantity}
            ).execute()
        return load_cart(cart_id)
    except HTTPException:
        raise
    except Exception as e:
        server_error(e)


@app.put("/cart/{cart_id}/items/{product_id}")
def set_quantity(cart_id: str, product_id: int, body: SetQty):
    valid_cart(cart_id)
    try:
        t = sb.table("cart_items")
        if body.quantity == 0:
            t.delete().eq("cart_id", cart_id).eq("product_id", product_id).execute()
        else:
            (
                t.update({"quantity": body.quantity})
                .eq("cart_id", cart_id)
                .eq("product_id", product_id)
                .execute()
            )
        return load_cart(cart_id)
    except Exception as e:
        server_error(e)


@app.delete("/cart/{cart_id}/items/{product_id}")
def remove_item(cart_id: str, product_id: int):
    valid_cart(cart_id)
    try:
        (
            sb.table("cart_items")
            .delete()
            .eq("cart_id", cart_id)
            .eq("product_id", product_id)
            .execute()
        )
        return load_cart(cart_id)
    except Exception as e:
        server_error(e)


@app.delete("/cart/{cart_id}")
def clear_cart(cart_id: str):
    valid_cart(cart_id)
    try:
        sb.table("cart_items").delete().eq("cart_id", cart_id).execute()
        return load_cart(cart_id)
    except Exception as e:
        server_error(e)
