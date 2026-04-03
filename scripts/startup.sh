#!/bin/bash
# Render startup script
# Runs before uvicorn starts

set -e

echo "=== Startup: fetching private assets ==="

# Clone private assets repo if token is available
if [ -n "$GITHUB_ASSETS_TOKEN" ] && [ -n "$GITHUB_ASSETS_REPO" ]; then
    echo "Cloning private assets..."

    # Clean up any existing clone
    rm -rf /tmp/private-assets

    git clone \
        https://${GITHUB_ASSETS_TOKEN}@github.com/${GITHUB_ASSETS_REPO}.git \
        /tmp/private-assets \
        --depth 1 \
        --quiet

    # Copy images correctly
    mkdir -p assets/overrides
    cp -r /tmp/private-assets/overrides/* assets/overrides/ 2>/dev/null || true

    # Clean up clone
    rm -rf /tmp/private-assets

    echo "Private assets loaded successfully"
else
    echo "No GITHUB_ASSETS_TOKEN set — skipping private assets"
fi

echo "=== Starting uvicorn ==="
exec uvicorn api.main:app --host 0.0.0.0 --port $PORT