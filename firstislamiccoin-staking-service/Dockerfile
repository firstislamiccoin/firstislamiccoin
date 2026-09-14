# FirstIslamicCoin mobile/web gateway (firstislamiccoin-staking-service) image.

FROM python:3.12-slim

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    && rm -rf /var/lib/apt/lists/* \
    && useradd --create-home --shell /bin/bash fic-gateway

WORKDIR /app
COPY requirements.txt /app/
RUN pip install --no-cache-dir -r requirements.txt
COPY . /app/

USER fic-gateway
VOLUME ["/app/data"]
EXPOSE 8080

ENV GATEWAY_DB_PATH=/app/data/gateway.db

# gunicorn, not app.py's own __main__ dev server -- see gateway.service's
# comment for why.
ENTRYPOINT ["gunicorn", "--workers", "4", "--bind", "0.0.0.0:8080", "--access-logfile", "-", "app:app"]
