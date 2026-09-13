# FirstIslamicCoin block explorer backend image. Stateless -- no volume
# needed. The frontend (index.html/app.js/style.css) is plain static files;
# serve them separately (see README.md) or add an nginx stage in front of
# this if bundling both behind one container is preferred.

FROM python:3.12-slim

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    && rm -rf /var/lib/apt/lists/* \
    && useradd --create-home --shell /bin/bash fic-explorer

WORKDIR /app
COPY requirements.txt /app/
RUN pip install --no-cache-dir -r requirements.txt
COPY app.py rpc.py /app/

USER fic-explorer
EXPOSE 8081

ENTRYPOINT ["gunicorn", "--workers", "4", "--bind", "0.0.0.0:8081", "--access-logfile", "-", "app:app"]
