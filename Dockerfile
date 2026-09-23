FROM python:3.13-slim

# Imposta variabili d'ambiente Python
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

# Installazione pacchetti di sistema di base
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    ca-certificates \
    && rm -rf /var/lib/apt/lists/*

# Installazione delle dipendenze Python
COPY requirements.txt /app/
RUN pip install --no-cache-dir -r requirements.txt

# Copia del codice dell'applicazione
COPY . /app/

# Correzione terminatori di riga (CRLF -> LF per Windows) e permessi per entrypoint
RUN sed -i 's/\r$//' /app/entrypoint.sh && chmod +x /app/entrypoint.sh

EXPOSE 8000

ENTRYPOINT ["/app/entrypoint.sh"]
CMD ["python", "manage.py", "runserver", "0.0.0.0:8000"]

