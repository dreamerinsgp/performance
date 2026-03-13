FROM python:3.11-slim

# sshpass for one-time SSH key setup (optional, when user provides password)
RUN apt-get update && apt-get install -y --no-install-recommends sshpass openssh-client \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY backend/ ./backend/
COPY frontend/ ./frontend/
COPY config/ ./config/
COPY scripts/ ./scripts/
COPY perftest/ ./perftest/
COPY requirements.txt .

RUN pip install --no-cache-dir -r requirements.txt

EXPOSE 8000

CMD ["uvicorn", "backend.main:app", "--host", "0.0.0.0", "--port", "8000"]
