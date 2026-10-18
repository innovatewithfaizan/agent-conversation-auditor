# The auditor API (FastAPI) for live audits with the visitor's own key.
# Works on Hugging Face Spaces (Docker, port 7860) and Render (sets $PORT).
FROM python:3.11-slim

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY auditor ./auditor
COPY policy ./policy
COPY data/benchmark ./data/benchmark
COPY results ./results

# No API keys are baked in or read from the environment: visitors send their own.
ENV AUDITOR_CORS_ORIGINS="https://innovatewithfaizan.github.io"
EXPOSE 7860
CMD ["sh", "-c", "uvicorn auditor.api:app --host 0.0.0.0 --port ${PORT:-7860}"]
