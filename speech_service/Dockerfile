FROM python:3.11-slim
WORKDIR /app
RUN apt-get update && apt-get install -y --no-install-recommends libsndfile1 libgomp1 ffmpeg && rm -rf /var/lib/apt/lists/*
COPY requirements.txt requirements.txt
COPY speech_service/requirements.txt speech_service/requirements.txt
COPY scripts/install_voice.sh scripts/install_voice.sh
RUN sh scripts/install_voice.sh
COPY speech_service speech_service
COPY smriti_core smriti_core
COPY scripts/download_models.py scripts/download_models.py
COPY scripts/download_regional_voices.py scripts/download_regional_voices.py
ENV SMRITI_MODEL_DIR=/models SMRITI_AUDIO_CACHE=/audio-cache HF_HOME=/models/.hf
RUN useradd --create-home --uid 10001 smriti && mkdir /models /audio-cache && chown -R smriti:smriti /models /audio-cache /app
USER smriti
EXPOSE 8000
# One process shares model memory and the bounded inference queue.
CMD ["python", "-m", "uvicorn", "speech_service.app:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "1", "--ws-max-size", "100000", "--no-access-log"]
