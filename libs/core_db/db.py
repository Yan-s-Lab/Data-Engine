# libs/core_db/db.py 统一的 Engine / Session / Base
import os
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base

# 可以统一用同一个环境变量名，默认走 compose 里的 postgres
SQLALCHEMY_DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "postgresql+psycopg2://dataengine:dataengine@postgres:5432/dataengine",
)

engine = create_engine(
    SQLALCHEMY_DATABASE_URL,
    future=True,
    pool_pre_ping=True,
)

SessionLocal = sessionmaker(
    autocommit=False,
    autoflush=False,
    bind=engine,
)

Base = declarative_base()


# ⭐ 关键：初始化数据库（建表）
def init_db() -> None:
    # 这里一定要 import 进来，才能把 models 注册到 Base 上
    from libs.core_db.models import collection, sample  # noqa: F401

    # 如果你还有别的 models 文件，也一并 import：
    # from libs.core_db.models import xxx

    Base.metadata.create_all(bind=engine)