FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

COPY backend/requirements_py3.12.txt /tmp/req.txt
RUN pip install --no-cache-dir -r /tmp/req.txt

COPY . /app

# Strip CRLF that may sneak in when the repo is checked out on Windows —
# Linux `env` chokes on `bash\r` in shebangs.
RUN sed -i 's/\r$//' /app/start.sh && chmod +x /app/start.sh

# Port baked in for EXPOSE only; the actual bind port is read from $PORT
# at runtime (see start.sh).
EXPOSE 9419

CMD ["./start.sh", "prod"]
