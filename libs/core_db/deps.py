# libs/core_db/deps.py FastAPI 依赖（get_db）
from collections.abc import Generator
from .db import SessionLocal

# 给 FastAPI 依赖注入用的（如果你还没有）
def get_session():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()