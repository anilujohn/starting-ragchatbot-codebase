#!/bin/bash

# Code formatting script for the RAG chatbot application
# Automatically formats code using Black and fixes issues with Ruff

set -e

echo "🎨 Formatting code..."

# Check if we're in the right directory
if [ ! -f "pyproject.toml" ]; then
    echo "Error: pyproject.toml not found. Please run this script from the project root."
    exit 1
fi

echo ""
echo "📝 Formatting with Black..."
uv run black backend/ *.py

echo ""
echo "🔧 Auto-fixing with Ruff..."
uv run ruff check backend/ *.py --fix

echo ""
echo "✅ Code formatting complete!"