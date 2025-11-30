# services/collection-gateway/Dockerfile
FROM python:3.11-slim

# cd /app
WORKDIR /app


RUN apt-get update && apt-get install -y curl \
    && rm -rf /var/lib/apt/lists/*


# 安装依赖（用仓库根目录的 requirements.txt）
COPY requirements.txt ./requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

# 拷贝 collection-gateway 的 FastAPI 应用代码
COPY services/collection-gateway/app ./app

# 让 Python 能找到挂进来的 libs （后面在 docker-compose 里会挂载）
ENV PYTHONPATH=/app:/app/libs 
# 这样 from libs.core_db.session import get_session 这种就不会报错

# 启动 FastAPI
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
