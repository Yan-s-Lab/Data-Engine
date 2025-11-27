from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from datetime import datetime

from libs.core_db import models
from libs.core_schemas.collections import CollectionRunCreate, CollectionRun
from ..deps import get_db

router = APIRouter(prefix="/collections", tags=["collections"])


@router.post("/", response_model=CollectionRun)
def create_collection(
    payload: CollectionRunCreate, db: Session = Depends(get_db)
):
    obj = models.CollectionRun(
        name=payload.name,
        description=payload.description,
        source_type=payload.source_type,
        created_at=datetime.utcnow(),
    )
    db.add(obj)
    db.commit()
    db.refresh(obj)
    return CollectionRun(
        id=obj.id,
        name=obj.name,
        description=obj.description,
        source_type=obj.source_type,
        created_at=obj.created_at,
    )
