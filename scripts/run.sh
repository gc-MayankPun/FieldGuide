
#!/usr/bin/env bash

set -e

# Always run from the project root
cd "$(dirname "$0")/.."

VENV=".venv"
HASH_FILE="$VENV/.requirements_hash"

echo "Starting FieldGuide..."

# Create virtual environment if missing
if [ ! -d "$VENV" ]; then
    echo "Creating virtual environment..."
    python -m venv "$VENV"
fi

# Activate virtual environment
source "$VENV/bin/activate"

# Install or update dependencies only when requirements change
if [ -f requirements.txt ]; then
    CURRENT_HASH=$(sha256sum requirements.txt | cut -d ' ' -f 1)
    OLD_HASH=$(cat "$HASH_FILE" 2>/dev/null || true)

    if [ "$CURRENT_HASH" != "$OLD_HASH" ]; then
        echo "Installing/updating dependencies..."
        python -m pip install -r requirements.txt
        echo "$CURRENT_HASH" > "$HASH_FILE"
    fi
fi

echo "Launching FieldGuide..."

# Pass user arguments, defaulting to --start
if [ "$#" -eq 0 ]; then
    set -- --start
fi

exec python -m fieldguide "$@"
