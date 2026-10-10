FROM python:3.12-slim
ENV PYTHONUNBUFFERED=1 TZ=Asia/Shanghai
WORKDIR /app
RUN apt-get update && apt-get install -y --no-install-recommends tzdata ca-certificates \
    && rm -rf /var/lib/apt/lists/*
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .
# 非 root 运行（更安全）
RUN useradd -r -s /usr/sbin/nologin app && chown -R app:app /app
USER app
EXPOSE 5000
CMD ["python", "api/app.py"]
