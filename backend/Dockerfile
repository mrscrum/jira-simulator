FROM python:3.12-slim

WORKDIR /app

# Copy dependency spec first for layer caching
COPY pyproject.toml .
RUN pip install --no-cache-dir -e "." 2>/dev/null || true

# Copy application code
COPY . .

# Re-install now that code is present (editable mode needs the package)
RUN pip install --no-cache-dir -e "."

EXPOSE 8000

COPY entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh

CMD ["/entrypoint.sh"]
