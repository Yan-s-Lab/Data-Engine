from fastapi import FastAPI
from contextlib import asynccontextmanager
# from scripts import init_db
from .api import collections, samples
from libs.core_db.db import Base, engine,init_db  # 路径按你实际改



@asynccontextmanager
async def lifespan(app: FastAPI):
    # 🚀 这里相当于 startup
    print("🚀Initializing database...😄")
    init_db()
    yield   # ---- 应用运行中 ----

    # 🧹 这里相当于 shutdown
    print("Application shutdown.")


# 创建了 FastAPI 实例
app = FastAPI(title="Collection Gateway(hhhh)",lifespan=lifespan)

# 把 app/api/collections.py等里定义的路由挂进来，FastAPI自动把所有路由生成 Swagger 文档：http://localhost:8001/docs
app.include_router(collections.router)
app.include_router(samples.router)
