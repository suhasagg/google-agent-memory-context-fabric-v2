FROM python:3.12-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PIP_NO_CACHE_DIR=1
WORKDIR /app
COPY pyproject.toml README.md ./
COPY src/ ./src/
RUN python -m pip install --no-cache-dir '.[server]' \
    && groupadd --gid 10001 fabric \
    && useradd --uid 10001 --gid 10001 --home-dir /home/fabric --create-home fabric \
    && install -d -o 10001 -g 10001 -m 0700 /home/fabric/data
USER 10001:10001
ENV FABRIC_DB=/home/fabric/data/memory.sqlite
EXPOSE 8000
CMD ["uvicorn","context_fabric.api:app","--host","0.0.0.0","--port","8000","--workers","1"]
