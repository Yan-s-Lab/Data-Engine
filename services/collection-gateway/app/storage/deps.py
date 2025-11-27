# 依赖注入（DB session）
from contextlib import contextmanager
from libs.core_db.session import SessionLocal


@contextmanager
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
