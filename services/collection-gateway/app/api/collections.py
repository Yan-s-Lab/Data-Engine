from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from datetime import datetime

from libs.core_db.models import CollectionRun
from libs.core_schemas.collection import CollectionRunCreate, CollectionRunOut
from libs.core_db.deps import get_session

router = APIRouter(prefix="/collections", tags=["collections"])


@router.post("/", response_model=CollectionRunOut)
def create_collection(
    payload: CollectionRunCreate, db: Session = Depends(get_session)
):

    # ✅ 1. 用 SQLAlchemy ORM 模型创建对象
    obj = CollectionRun(
        name=payload.name,
        description=payload.description,
        source_type=payload.source_type,
        created_at=datetime.now(),
        meta=payload.meta,

    )

    # ✅ 2. 持久化到数据库
    db.add(obj)
    db.commit()
    db.refresh(obj)

    # ✅ 3. 返回 Pydantic 响应模型（两种方式二选一）
    
    # 方式 A：直接手动构造（你现在就是这样做的）,需要类型处理
    # return CollectionRunOut(
    #     id=obj.id,
    #     name=obj.name,
    #     description=obj.description,
    #     source_type= obj.source_type,
    #     created_at=obj.created_at,
    # )
    # 方式 B（推荐）：让 FastAPI 自动从 ORM 转 Pydantic
    # 前提：CollectionRun 里配置了 orm_mode / from_attributes，也不用重复写这么多变量了
    return obj
