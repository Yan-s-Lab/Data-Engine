FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /workspace

COPY requirements.txt /tmp/requirements.txt
RUN pip install --no-cache-dir -r /tmp/requirements.txt

COPY deploy/pipeline/pipeline_entrypoint.sh /usr/local/bin/pipeline_entrypoint.sh

RUN chmod +x /usr/local/bin/pipeline_entrypoint.sh

ENTRYPOINT ["/usr/local/bin/pipeline_entrypoint.sh"]
