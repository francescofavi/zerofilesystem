#!/usr/bin/env bash
set -e

echo "zeroos - Run Tests & Examples"
echo "=========================================="
echo ""

# Run tests first
echo "--- Running Tests ---"
echo ""
uv run pytest -v
echo ""

# Run all examples
EXAMPLES_DIR="examples"
FAILED=0

for example in "$EXAMPLES_DIR"/[0-9]*.py; do
    name=$(basename "$example")
    echo "=========================================="
    echo "Running: $name"
    echo "=========================================="
    echo ""
    if uv run python "$example"; then
        echo ""
        echo "[OK] $name"
    else
        echo ""
        echo "[FAIL] $name"
        FAILED=$((FAILED + 1))
    fi
    echo ""
done

echo "=========================================="
if [ "$FAILED" -eq 0 ]; then
    echo "[OK] All tests and examples passed!"
else
    echo "[FAIL] $FAILED example(s) failed"
fi
echo "=========================================="
