import pytest
import tempfile
import shutil
from unittest.mock import Mock, patch, MagicMock
from pathlib import Path
import sys
import os

# Add the parent directory to the path so we can import modules
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from config import Config
from rag_system import RAGSystem
from vector_store import VectorStore
from ai_generator import AIGenerator
from document_processor import DocumentProcessor
from session_manager import SessionManager
from search_tools import CourseSearchTool, CourseOutlineTool

@pytest.fixture
def mock_config():
    """Create a mock configuration for testing"""
    config = Mock(spec=Config)
    config.ANTHROPIC_API_KEY = "test-api-key"
    config.ANTHROPIC_MODEL = "claude-sonnet-4-20250514"
    config.EMBEDDING_MODEL = "all-MiniLM-L6-v2"
    config.CHROMA_DB_PATH = ":memory:"
    config.CHUNK_SIZE = 800
    config.CHUNK_OVERLAP = 100
    config.MAX_SEARCH_RESULTS = 5
    return config

@pytest.fixture
def temp_directory():
    """Create a temporary directory for testing"""
    temp_dir = tempfile.mkdtemp()
    yield temp_dir
    shutil.rmtree(temp_dir)

@pytest.fixture
def mock_anthropic_client():
    """Create a mock Anthropic client"""
    with patch('anthropic.Anthropic') as mock_anthropic:
        mock_client = Mock()
        mock_anthropic.return_value = mock_client
        
        # Mock the messages.create method
        mock_response = Mock()
        mock_response.content = [Mock()]
        mock_response.content[0].text = "Test AI response"
        mock_response.content[0].type = "text"
        mock_client.messages.create.return_value = mock_response
        
        yield mock_client

@pytest.fixture
def mock_vector_store():
    """Create a mock vector store"""
    vector_store = Mock()
    
    # Mock search results
    from vector_store import SearchResults
    mock_results = SearchResults(
        documents=['This is test content about machine learning.'],
        metadata=[{
            'course_title': 'ML Course',
            'lesson_number': 1,
            'chunk_index': 0
        }],
        distances=[0.05],
        lesson_links={'ML Course|1': 'http://example.com/lesson1'}
    )
    vector_store.search_content.return_value = mock_results
    vector_store.search_courses.return_value = [
        {
            'title': 'ML Course',
            'instructor': 'Test Instructor',
            'course_link': 'http://example.com/ml-course',
            'lesson_count': 5,
            'lessons_json': [
                {'lesson_number': 1, 'lesson_title': 'Introduction', 'lesson_link': 'http://example.com/lesson1'}
            ]
        }
    ]
    vector_store.get_course_analytics.return_value = {
        'total_courses': 1,
        'course_titles': ['ML Course']
    }
    
    return vector_store

@pytest.fixture
def mock_ai_generator(mock_anthropic_client):
    """Create a mock AI generator"""
    with patch('ai_generator.anthropic.Anthropic'):
        ai_gen = Mock(spec=AIGenerator)
        ai_gen.generate_with_tools.return_value = (
            "This is a test response about machine learning.",
            [{"text": "Test source content", "link": "http://example.com/source"}]
        )
        return ai_gen

@pytest.fixture
def mock_session_manager():
    """Create a mock session manager"""
    session_manager = Mock(spec=SessionManager)
    session_manager.create_session.return_value = "test-session-123"
    session_manager.add_message.return_value = None
    session_manager.get_history.return_value = []
    return session_manager

@pytest.fixture
def mock_rag_system(mock_config, mock_vector_store, mock_ai_generator, mock_session_manager):
    """Create a mock RAG system with all dependencies mocked"""
    with patch('rag_system.VectorStore'), \
         patch('rag_system.AIGenerator'), \
         patch('rag_system.SessionManager'), \
         patch('rag_system.DocumentProcessor'):
        
        rag = Mock(spec=RAGSystem)
        rag.vector_store = mock_vector_store
        rag.ai_generator = mock_ai_generator
        rag.session_manager = mock_session_manager
        
        rag.query.return_value = (
            "This is a test response about machine learning.",
            [{"text": "Test source content", "link": "http://example.com/source"}]
        )
        rag.get_course_analytics.return_value = {
            'total_courses': 1,
            'course_titles': ['ML Course']
        }
        rag.add_course_folder.return_value = (1, 5)
        
        return rag

@pytest.fixture
def sample_course_data():
    """Sample course data for testing"""
    return {
        'course_title': 'Machine Learning Basics',
        'instructor': 'Dr. Test',
        'course_link': 'http://example.com/ml-basics',
        'lessons': [
            {
                'lesson_number': 1,
                'lesson_title': 'Introduction to ML',
                'lesson_link': 'http://example.com/lesson1',
                'content': 'This is the introduction to machine learning...'
            },
            {
                'lesson_number': 2,
                'lesson_title': 'Supervised Learning',
                'lesson_link': 'http://example.com/lesson2',
                'content': 'Supervised learning is a type of machine learning...'
            }
        ]
    }

@pytest.fixture
def sample_documents(temp_directory):
    """Create sample documents in a temporary directory"""
    docs_dir = Path(temp_directory) / "docs"
    docs_dir.mkdir()
    
    course_dir = docs_dir / "ml-course"
    course_dir.mkdir()
    
    # Create a sample JSON file
    import json
    course_data = {
        "course_title": "Machine Learning Basics",
        "instructor": "Dr. Test",
        "course_link": "http://example.com/ml-basics",
        "lessons": [
            {
                "lesson_number": 1,
                "lesson_title": "Introduction",
                "lesson_link": "http://example.com/lesson1",
                "content": "This is test content about machine learning fundamentals."
            }
        ]
    }
    
    with open(course_dir / "course.json", "w") as f:
        json.dump(course_data, f)
    
    return str(docs_dir)

@pytest.fixture
def api_test_client():
    """Create a test client for API testing that avoids static file mounting issues"""
    from fastapi import FastAPI
    from fastapi.testclient import TestClient
    
    # Create a minimal app for testing without static file mounting
    test_app = FastAPI(title="Test RAG System")
    
    # We'll add the API routes in the actual test file
    return TestClient(test_app)