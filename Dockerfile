FROM python:3.12-slim

WORKDIR /app

COPY pyproject.toml README.md ./
COPY src ./src
COPY examples ./examples
COPY plugin-demo ./plugin-demo
COPY deploy/omv/entrypoint.sh /entrypoint.sh

RUN pip install --no-cache-dir . \
    && chmod +x /entrypoint.sh

ENV MB_OUTPUT_DIR=/output
ENV MB_CONFIG_DIR=/config
ENV MB_RUN_MODE=server

VOLUME ["/output"]

ENTRYPOINT ["/entrypoint.sh"]
