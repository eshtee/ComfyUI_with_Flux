#!/bin/bash
set -euo pipefail

WORKSPACE=/workspace

if [[ "${1:-}" != "--yes" ]]; then
  echo "This will DELETE ALL DATA in $WORKSPACE except this script."
  echo "Usage: $0 --yes"
  exit 1
fi

# Safety: don't delete the script itself
SCRIPT_NAME=$(basename "$0")

cd "$WORKSPACE"
for item in * .[^.]*; do
  if [[ "$item" != "$SCRIPT_NAME" && "$item" != "." && "$item" != ".." ]]; then
    echo "Deleting $item..."
    rm -rf "$item"
  fi

done

echo "Workspace reset complete." 