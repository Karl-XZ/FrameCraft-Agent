FROM python:3.11-slim

RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        ffmpeg curl \
        fonts-noto-cjk fonts-noto-cjk-extra fonts-noto-color-emoji \
    && fc-cache -f \
    && rm -rf /var/lib/apt/lists/*

# Node 22 (HyperFrames CLI 需要 Node>=22)
RUN curl -fsSL https://deb.nodesource.com/setup_22.x | bash - \
    && apt-get install -y nodejs \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY backend/requirements.txt /app/backend/requirements.txt
RUN pip install --no-cache-dir -r /app/backend/requirements.txt
COPY vendor/VectCutAPI/requirements.txt /app/vendor/VectCutAPI/requirements.txt
RUN pip install --no-cache-dir -r /app/vendor/VectCutAPI/requirements.txt || true

COPY package.json /app/package.json
RUN npm install --omit=dev || true

COPY backend /app/backend
COPY config /app/config
COPY resources /app/resources

ENV PYTHONUNBUFFERED=1
WORKDIR /app/backend
EXPOSE 8000
CMD ["python", "-m", "uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
