#!/usr/bin/env bash
set -euo pipefail

project_dir="$(cd "$(dirname "$0")/.." && pwd)"
cd "$project_dir"
python3 -m PyInstaller \
  --noconfirm \
  --clean \
  --onefile \
  --name transcriptseek-service \
  --paths src \
  src/transcriptseek/ipc.py

echo "Sidecar built at $project_dir/dist/transcriptseek-service"
