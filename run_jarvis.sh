#!/bin/bash
set -euo pipefail

VENV_DIR="${VENV_DIR:-.venv312}"
ENV_FILE="${ENV_FILE:-.env.local}"
export MPLCONFIGDIR="${MPLCONFIGDIR:-/tmp/jarvis-mpl}"
mkdir -p "$MPLCONFIGDIR"

if [ -f "$ENV_FILE" ]; then
  FILE_MODE="$(stat -f '%Lp' "$ENV_FILE" 2>/dev/null || true)"
  if [ -n "$FILE_MODE" ] && [ "$FILE_MODE" != "600" ]; then
    echo "Warning: $ENV_FILE permissions are $FILE_MODE. Run: chmod 600 $ENV_FILE"
  fi
  set -a
  source "$ENV_FILE"
  set +a
fi

if [ ! -x "$VENV_DIR/bin/python" ]; then
  echo "Missing $VENV_DIR."
  echo "Run ./install.sh first."
  exit 1
fi

exec "$VENV_DIR/bin/python" -m app.core.video_pipeline
