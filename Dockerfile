FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

# rsync + openssh-client are required by the one-click install feature when
# pushing skills to a remote (ssh-typed) target. Local-typed targets work
# without these but installing them keeps the container a faithful
# prod-shaped sandbox.
RUN apt-get update \
    && apt-get install -y --no-install-recommends rsync openssh-client \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY backend/requirements_py3.12.txt /tmp/req.txt
RUN pip install --no-cache-dir -r /tmp/req.txt

COPY . /app

# Strip CRLF that may sneak in when the repo is checked out on Windows —
# Linux `env` chokes on `bash\r` in shebangs.
RUN sed -i 's/\r$//' /app/backend/start.sh && chmod +x /app/backend/start.sh

# Port baked in for EXPOSE only; the actual bind port is read from $PORT
# at runtime (see backend/start.sh).
EXPOSE 9419

CMD ["./backend/start.sh", "prod"]
