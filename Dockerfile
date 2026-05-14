FROM python:3.12-slim

RUN apt-get update && apt-get install -y --no-install-recommends \
    ffmpeg \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Pre-download rembg model for faster startup
RUN python -c "from rembg import new_session; new_session('u2netp')"

COPY . .

EXPOSE 7860

CMD ["python", "main.py"]
