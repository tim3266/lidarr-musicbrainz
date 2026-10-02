#!/bin/sh
set -e

CONFIG="${MB_SEED_CONFIG:-/app/examples/justin-bieber-journals-expanded.yaml}"
OUT="${MB_SEED_HTML:-/output/mb-seed.html}"
mkdir -p "$(dirname "$OUT")"

ARGS="-c ${CONFIG} --html ${OUT}"

if [ "${MB_SEED_SUBMIT:-false}" = "true" ]; then
  ARGS="${ARGS} --submit --print-url"
fi

# shellcheck disable=SC2086
mb-seed-release ${ARGS}

if [ -n "${MB_SEED_SERVE_PORT:-}" ]; then
  echo "Serving ${OUT} and /output on port ${MB_SEED_SERVE_PORT}"
  exec python -m http.server "${MB_SEED_SERVE_PORT}" --directory /output
fi

echo "Done. HTML: ${OUT}"
