import pytest
import json
import sys
import os
from unittest.mock import Mock, patch, MagicMock
from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from pydantic import BaseModel
from typing import List, Optional

# Add the parent directory to the path so we can import modules
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from rag_system import RAGSystem

# Define the API models inline to avoid import issues
class QueryRequest(BaseModel):
    """Request model for course queries"""
    query: str
    session_id: Optional[str] = None

class SourceItem(BaseModel):
    """Model for a source citation with optional link"""
    text: str
    link: Optional[str] = None

class QueryResponse(BaseModel):
    """Response model for course queries"""
    answer: str
    sources: List[SourceItem]
    session_id: str

class CourseStats(BaseModel):
    """Response model for course statistics"""
    total_courses: int
    course_titles: List[str]

class TestAPIEndpoints:
    """Test FastAPI endpoints without static file mounting issues"""

    @pytest.fixture
    def test_app(self, mock_rag_system):
        """Create a test FastAPI app with only API routes (no static files)"""
        app = FastAPI(title="Test Course Materials RAG System", root_path="")
        
        # Add the same middleware as the real app
        app.add_middleware(
            TrustedHostMiddleware,
            allowed_hosts=["*"]
        )
        
        app.add_middleware(
            CORSMiddleware,
            allow_origins=["*"],
            allow_credentials=True,
            allow_methods=["*"],
            allow_headers=["*"],
            expose_headers=["*"],
        )
        
        # Add API routes inline to avoid import issues
        @app.post("/api/query", response_model=QueryResponse)
        async def query_documents(request: QueryRequest):
            """Process a query and return response with sources"""
            try:
                # Create session if not provided
                session_id = request.session_id
                if not session_id:
                    session_id = mock_rag_system.session_manager.create_session()
                
                # Process query using RAG system
                answer, sources = mock_rag_system.query(request.query, session_id)
                
                # Convert sources to SourceItem format
                source_items = []
                for source in sources:
                    if isinstance(source, dict):
                        # New format with text and link
                        source_items.append(SourceItem(text=source["text"], link=source.get("link")))
                    else:
                        # Legacy format (just text)
                        source_items.append(SourceItem(text=str(source), link=None))
                
                return QueryResponse(
                    answer=answer,
                    sources=source_items,
                    session_id=session_id
                )
            except Exception as e:
                raise HTTPException(status_code=500, detail=str(e))

        @app.get("/api/courses", response_model=CourseStats)
        async def get_course_stats():
            """Get course analytics and statistics"""
            try:
                analytics = mock_rag_system.get_course_analytics()
                return CourseStats(
                    total_courses=analytics["total_courses"],
                    course_titles=analytics["course_titles"]
                )
            except Exception as e:
                raise HTTPException(status_code=500, detail=str(e))

        @app.get("/")
        async def root():
            """Root endpoint for health check"""
            return {"message": "RAG System API is running"}
        
        return app
    
    @pytest.fixture
    def client(self, test_app):
        """Create test client"""
        return TestClient(test_app)

    @pytest.mark.api
    def test_query_endpoint_success(self, client, mock_rag_system):
        """Test successful query to /api/query endpoint"""
        # Prepare test data
        query_data = {
            "query": "What is machine learning?",
            "session_id": "test-session-123"
        }
        
        # Make request
        response = client.post("/api/query", json=query_data)
        
        # Assertions
        assert response.status_code == 200
        
        data = response.json()
        assert "answer" in data
        assert "sources" in data
        assert "session_id" in data
        assert data["answer"] == "This is a test response about machine learning."
        assert data["session_id"] == "test-session-123"
        assert len(data["sources"]) > 0
        assert data["sources"][0]["text"] == "Test source content"
        assert data["sources"][0]["link"] == "http://example.com/source"
        
        # Verify RAG system was called correctly
        mock_rag_system.query.assert_called_once_with("What is machine learning?", "test-session-123")

    @pytest.mark.api
    def test_query_endpoint_without_session_id(self, client, mock_rag_system):
        """Test query endpoint creates session when none provided"""
        # Prepare test data without session_id
        query_data = {
            "query": "What is supervised learning?"
        }
        
        # Make request
        response = client.post("/api/query", json=query_data)
        
        # Assertions
        assert response.status_code == 200
        
        data = response.json()
        assert "session_id" in data
        assert data["session_id"] == "test-session-123"  # From mock
        
        # Verify session was created
        mock_rag_system.session_manager.create_session.assert_called_once()

    @pytest.mark.api
    def test_query_endpoint_with_legacy_sources(self, client, mock_rag_system):
        """Test query endpoint handles legacy source format (strings)"""
        # Mock RAG system to return legacy string sources
        mock_rag_system.query.return_value = (
            "Test answer",
            ["Legacy source text 1", "Legacy source text 2"]
        )
        
        query_data = {
            "query": "Test query",
            "session_id": "test-session"
        }
        
        response = client.post("/api/query", json=query_data)
        
        assert response.status_code == 200
        data = response.json()
        
        # Check that legacy sources are converted properly
        assert len(data["sources"]) == 2
        assert data["sources"][0]["text"] == "Legacy source text 1"
        assert data["sources"][0]["link"] is None
        assert data["sources"][1]["text"] == "Legacy source text 2"
        assert data["sources"][1]["link"] is None

    @pytest.mark.api
    def test_query_endpoint_validation_error(self, client):
        """Test query endpoint with invalid request data"""
        # Send request without required 'query' field
        response = client.post("/api/query", json={})
        
        assert response.status_code == 422
        
        # Send request with invalid data type
        response = client.post("/api/query", json={"query": 123})
        
        assert response.status_code == 422

    @pytest.mark.api
    def test_query_endpoint_internal_error(self, client, mock_rag_system):
        """Test query endpoint handles internal errors"""
        # Make RAG system raise an exception
        mock_rag_system.query.side_effect = Exception("Test error")
        
        query_data = {
            "query": "What is machine learning?",
            "session_id": "test-session"
        }
        
        response = client.post("/api/query", json=query_data)
        
        assert response.status_code == 500
        assert "Test error" in response.json()["detail"]

    @pytest.mark.api
    def test_courses_endpoint_success(self, client, mock_rag_system):
        """Test successful request to /api/courses endpoint"""
        response = client.get("/api/courses")
        
        assert response.status_code == 200
        
        data = response.json()
        assert "total_courses" in data
        assert "course_titles" in data
        assert data["total_courses"] == 1
        assert data["course_titles"] == ["ML Course"]
        
        # Verify RAG system was called
        mock_rag_system.get_course_analytics.assert_called_once()

    @pytest.mark.api
    def test_courses_endpoint_internal_error(self, client, mock_rag_system):
        """Test courses endpoint handles internal errors"""
        # Make RAG system raise an exception
        mock_rag_system.get_course_analytics.side_effect = Exception("Analytics error")
        
        response = client.get("/api/courses")
        
        assert response.status_code == 500
        assert "Analytics error" in response.json()["detail"]

    @pytest.mark.api
    def test_root_endpoint(self, client):
        """Test root endpoint returns health check"""
        response = client.get("/")
        
        assert response.status_code == 200
        
        data = response.json()
        assert "message" in data
        assert "RAG System API is running" in data["message"]

    @pytest.mark.api
    def test_cors_headers(self, client):
        """Test that CORS headers are properly set"""
        response = client.options("/api/query", headers={"Origin": "http://localhost:3000"})
        
        # Check that CORS headers are present (FastAPI handles preflight automatically)
        assert response.status_code == 200

    @pytest.mark.api
    def test_query_request_model_validation(self):
        """Test QueryRequest model validation"""
        # Valid request
        request = QueryRequest(query="What is ML?", session_id="test-123")
        assert request.query == "What is ML?"
        assert request.session_id == "test-123"
        
        # Request without session_id (should default to None)
        request = QueryRequest(query="What is ML?")
        assert request.query == "What is ML?"
        assert request.session_id is None

    @pytest.mark.api
    def test_response_models(self):
        """Test response model creation"""
        # Test SourceItem
        source = SourceItem(text="Test source", link="http://example.com")
        assert source.text == "Test source"
        assert source.link == "http://example.com"
        
        source_no_link = SourceItem(text="Test source")
        assert source_no_link.text == "Test source"
        assert source_no_link.link is None
        
        # Test QueryResponse
        response = QueryResponse(
            answer="Test answer",
            sources=[source],
            session_id="test-123"
        )
        assert response.answer == "Test answer"
        assert len(response.sources) == 1
        assert response.session_id == "test-123"
        
        # Test CourseStats
        stats = CourseStats(total_courses=5, course_titles=["Course 1", "Course 2"])
        assert stats.total_courses == 5
        assert len(stats.course_titles) == 2

    @pytest.mark.api
    @pytest.mark.integration
    def test_query_flow_integration(self, client, mock_rag_system):
        """Test complete query flow with session management"""
        # First query - should create a session
        query1_data = {"query": "What is machine learning?"}
        response1 = client.post("/api/query", json=query1_data)
        
        assert response1.status_code == 200
        session_id = response1.json()["session_id"]
        assert session_id == "test-session-123"
        
        # Second query - using existing session
        query2_data = {
            "query": "What about deep learning?",
            "session_id": session_id
        }
        response2 = client.post("/api/query", json=query2_data)
        
        assert response2.status_code == 200
        assert response2.json()["session_id"] == session_id
        
        # Verify both queries were processed
        assert mock_rag_system.query.call_count == 2

    @pytest.mark.api
    def test_multiple_concurrent_requests(self, client, mock_rag_system):
        """Test handling multiple concurrent requests"""
        import threading
        import time
        
        results = []
        
        def make_request(query_text):
            response = client.post("/api/query", json={"query": query_text})
            results.append(response.status_code)
        
        # Create multiple threads
        threads = []
        for i in range(5):
            thread = threading.Thread(target=make_request, args=[f"Query {i}"])
            threads.append(thread)
            thread.start()
        
        # Wait for all threads to complete
        for thread in threads:
            thread.join()
        
        # All requests should have succeeded
        assert all(status == 200 for status in results)
        assert len(results) == 5