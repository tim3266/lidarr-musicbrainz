FROM python:3.12-slim

WORKDIR /app

COPY pyproject.toml README.md ./
COPY src ./src
COPY examples ./examples
COPY deploy/omv/entrypoint.sh /entrypoint.sh

RUN pip install --no-cache-dir . \
    && chmod +x /entrypoint.sh

ENV MB_SEED_HTML=/output/mb-seed.html
ENV MB_SEED_CONFIG=/app/examples/justin-bieber-journals-expanded.yaml

VOLUME ["/output"]

ENTRYPOINT ["/entrypoint.sh"]
