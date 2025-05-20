# ─── BUILDER STAGE ────────────────────────────────────
FROM python:3.10-slim AS builder

# 1) Build tools + ADB tools
RUN apt-get update && apt-get install -y \
      build-essential \
      libpq-dev \
      adb \
      netcat-openbsd \
      ewf-tools \
    --no-install-recommends && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# 2) Python deps into /install
COPY requirements.txt .
RUN pip install --prefix=/install --no-cache-dir -r requirements.txt

# 3) Copy only your Django code—node_modules & via are now truly ignored
COPY manage.py manage.py
COPY core/     core/
COPY apps/     apps/

# ─── FINAL (runtime) STAGE ────────────────────────────
FROM python:3.10-slim

# 4) Runtime tools only
RUN apt-get update && apt-get install -y \
      adb \
      netcat-openbsd \
      ewf-tools \
    --no-install-recommends && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# 5) Bring in Python packages
COPY --from=builder /install /usr/local

# 6) Ensure console‐scripts (gunicorn etc.) are on PATH
ENV PATH="/usr/local/bin:${PATH}"

# 7) Copy your app
COPY manage.py manage.py
COPY core/     core/
COPY apps/     apps/

# 8) Entrypoint + server
COPY entrypoint.sh .
RUN chmod +x entrypoint.sh

EXPOSE 8000
ENTRYPOINT ["./entrypoint.sh"]
CMD ["gunicorn", "--bind", "0.0.0.0:8000", "core.wsgi:application"]
