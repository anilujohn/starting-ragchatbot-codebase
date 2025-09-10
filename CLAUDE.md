# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

This is a Retrieval-Augmented Generation (RAG) system for course materials that uses ChromaDB for vector storage, Anthropic's Claude for AI generation, and provides a web interface for interaction.

## Architecture

The application follows a modular Python backend with FastAPI:

- **Backend (`/backend/`)**: Python FastAPI application
  - `app.py`: Main FastAPI application with API endpoints
  - `rag_system.py`: Core RAG orchestrator combining all components
  - `vector_store.py`: ChromaDB vector database operations
  - `document_processor.py`: Document parsing and chunking
  - `ai_generator.py`: Anthropic Claude integration with tool support
  - `search_tools.py`: Tool-based search functionality for AI agent
  - `session_manager.py`: Conversation history management
  - `models.py`: Pydantic models for data structures
  - `config.py`: Configuration management with environment variables

- **Frontend (`/frontend/`)**: Static HTML/CSS/JavaScript web interface

## Development Commands

### Environment Setup
```bash
# Install dependencies
uv sync

# Create .env file with required variables
ANTHROPIC_API_KEY=your_key_here
```

### Running the Application
```bash
# Quick start (recommended)
chmod +x run.sh
./run.sh

# Manual start
cd backend && uv run uvicorn app:app --reload --port 8000
```

### Development Server
- Web Interface: `http://localhost:8000`
- API Documentation: `http://localhost:8000/docs`

### Code Quality
```bash
# Format code automatically
./scripts/format_code.sh

# Check code quality (formatting and linting)
./scripts/quality_check.sh

# Manual commands
uv run black backend/ *.py        # Format with Black
uv run ruff check backend/ *.py   # Lint with Ruff
uv run ruff check backend/ *.py --fix  # Auto-fix Ruff issues
```

## Key Configuration

- **Python Version**: 3.13+
- **Package Manager**: `uv` (not pip/poetry)
- **API Model**: Uses Claude Sonnet 4 (`claude-sonnet-4-20250514`)
- **Vector Store**: ChromaDB with `all-MiniLM-L6-v2` embeddings
- **Document Processing**: 800 character chunks with 100 character overlap
- **Code Quality**: Black formatter + Ruff linter with 88-character line length

## Important Implementation Details

- The system uses tool-based RAG where Claude has access to a `CourseSearchTool` for semantic search
- Documents are automatically loaded from `/docs` folder on startup
- Session management maintains conversation context (2 message history)
- CORS is configured for development with wildcard origins
- Static files are served with no-cache headers for development
- The vector database has two collections:
course_catalog:
stores course titles for name resolution
metadata for each course: title, instructor, course_link, lesson_count, lessons_json (list of lessons: lesson_number, lesson_title, lesson_link)
course_content:
stores text chunks for semantic search
metadata for each chunk: course_title, lesson_number, chunk_index