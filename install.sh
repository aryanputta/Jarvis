#!/bin/bash
set -euo pipefail

PYTHON_BIN="${PYTHON_BIN:-python3.12}"
VENV_DIR="${VENV_DIR:-.venv312}"

if ! command -v "$PYTHON_BIN" >/dev/null 2>&1; then
  echo "Expected $PYTHON_BIN but it was not found."
  echo "Install Python 3.12 first, then rerun this script."
  exit 1
fi

if command -v brew >/dev/null 2>&1; then
  if ! brew list portaudio >/dev/null 2>&1; then
    brew install portaudio
  fi
else
  echo "Homebrew not found. Install portaudio manually if PyAudio fails to build."
fi

"$PYTHON_BIN" -m venv "$VENV_DIR"
"$VENV_DIR/bin/pip" install --upgrade pip
"$VENV_DIR/bin/pip" install -r requirements.txt

cat <<EOF

Setup complete.

Activate the environment:
  source $VENV_DIR/bin/activate

Run Jarvis:
  $VENV_DIR/bin/python -m app.core.video_pipeline
EOF
