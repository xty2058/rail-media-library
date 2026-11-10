FROM python:3.12-slim-bookworm
RUN apt-get update && apt-get install -y --no-install-recommends ffmpeg ca-certificates && rm -rf /var/lib/apt/lists/*
WORKDIR /app
COPY *.py ./
COPY dist/ ./dist/
ENV PYTHONUNBUFFERED=1 MEDIA_TEAM=1 MEDIA_DATA=/var/data
CMD ["python", "-B", "server.py"]
