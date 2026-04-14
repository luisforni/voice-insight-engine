FROM python:3.11-slim

# System deps for whisper + ffmpeg
RUN apt-get update && apt-get install -y \
    ffmpeg \
    git \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt .
# setuptools>=71 removes pkg_resources which openai-whisper's legacy setup.py requires.
# Pin to <71, install whisper without build isolation, then install the rest.
RUN pip install --no-cache-dir "setuptools<71" wheel && \
    pip install --no-cache-dir --no-build-isolation openai-whisper==20240930 && \
    pip install --no-cache-dir -r requirements.txt

# Pre-download whisper base model at build time
RUN python -c "import whisper; whisper.load_model('base')"

COPY . .

EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--reload"]
