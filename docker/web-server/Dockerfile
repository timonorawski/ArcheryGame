# YAMS Web Dev Server with Pygbag Build
FROM python:3.11-slim

WORKDIR /app

# Install build dependencies
RUN pip install --no-cache-dir \
    aiohttp \
    aiohttp-cors \
    pygbag \
    pygame-ce \
    pyyaml

# Create build output directory (writable)
RUN mkdir -p /build/web

# Copy the entrypoint and server scripts
COPY docker/web-server/entrypoint.sh /entrypoint.sh
COPY docker/web-server/server.py /server.py
RUN chmod +x /entrypoint.sh

EXPOSE 8000

ENTRYPOINT ["/entrypoint.sh"]
