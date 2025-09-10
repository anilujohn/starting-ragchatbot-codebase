#!/bin/bash

# Quality check script for the RAG chatbot application
# Runs code formatting and linting checks

set -e

echo "🔍 Running code quality checks..."

# Check if we're in the right directory
if [ ! -f "pyproject.toml" ]; then
    echo "Error: pyproject.toml not found. Please run this script from the project root."
    exit 1
fi

echo ""
echo "📝 Checking code formatting with Black..."
uv run black backend/ *.py --check --diff

echo ""
echo "🔍 Running Ruff linter..."
uv run ruff check backend/ *.py

echo ""
echo "✅ All quality checks passed!"