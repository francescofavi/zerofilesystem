#!/usr/bin/env bash

set -e

echo "zeroos - Complete Setup"
echo "=========================================="
echo ""

if ! command -v uv &> /dev/null; then
    echo "Installing uv..."
    curl -LsSf https://astral.sh/uv/install.sh | sh
    export PATH="$HOME/.cargo/bin:$PATH"
    echo "+ uv installed"
else
    echo "+ uv found ($(uv --version))"
fi

echo ""
echo "Removing old virtual environment..."
rm -rf .venv
echo "+ Old venv removed"

echo ""
echo "Creating fresh virtual environment..."
uv venv
echo "+ Virtual environment created"

echo ""
echo "Installing dependencies..."
uv sync

if [ $? -ne 0 ]; then
    echo "X Failed to install dependencies"
    exit 1
fi

echo ""
echo "Installing pre-commit hooks..."
if uv run pre-commit install 2>/dev/null; then
    echo "+ Pre-commit hooks installed"
else
    echo "! Warning: Failed to install pre-commit hooks"
    echo "  You can install them later with: uv run pre-commit install"
fi

echo ""
echo "=========================================="
echo "+ Setup complete!"
echo "=========================================="
echo ""
