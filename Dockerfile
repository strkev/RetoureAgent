FROM python:3.11-slim

# Umgebungsvariablen setzen: kein Bytecode, direkte Konsolenausgabe, höherer Pip-Timeout
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_DEFAULT_TIMEOUT=1000

WORKDIR /app

# CPU-Version von PyTorch vorinstallieren:
RUN pip install --no-cache-dir torch --index-url https://download.pytorch.org/whl/cpu

# Abhängigkeiten installieren
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Anwendungsquellcode kopieren
COPY . .

# Port für FastAPI/Uvicorn freigeben
EXPOSE 8000

# Server auf 0.0.0.0 starten
CMD ["uvicorn", "server:app", "--host", "0.0.0.0", "--port", "8000"]
