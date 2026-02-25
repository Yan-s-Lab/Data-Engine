FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /workspace

COPY requirements.txt /tmp/requirements.txt
RUN pip install --no-cache-dir -r /tmp/requirements.txt

COPY . /workspace

RUN chmod +x /workspace/deploy/pipeline/pipeline_entrypoint.sh \
    && chmod +x /workspace/pipelines/run_managed_pipeline.py

ENTRYPOINT ["/workspace/deploy/pipeline/pipeline_entrypoint.sh"]
