#!/bin/sh
set -e

MODE="${MB_RUN_MODE:-server}"
OUTPUT="${MB_OUTPUT_DIR:-/output}"
CONFIG="${MB_CONFIG_DIR:-/config}"
mkdir -p "$OUTPUT"

if [ "$MODE" = "once" ]; then
  CONFIG_FILE="${MB_SEED_CONFIG:-/app/examples/justin-bieber-journals-expanded.yaml}"
  OUT="${MB_SEED_HTML:-$OUTPUT/mb-seed.html}"
  ARGS="-c ${CONFIG_FILE} --html ${OUT}"
  if [ "${MB_SEED_SUBMIT:-false}" = "true" ]; then
    ARGS="${ARGS} --submit --print-url"
  fi
  # shellcheck disable=SC2086
  mb-seed-release ${ARGS}
  echo "Done. HTML: ${OUT}"
  exit 0
fi

export MB_OUTPUT_DIR="$OUTPUT"
export MB_CONFIG_DIR="$CONFIG"
exec mb-seed-release serve
