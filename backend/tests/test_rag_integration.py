import unittest
import sys
import os
from unittest.mock import Mock, patch, MagicMock
import tempfile
import shutil

# Add the parent directory to the path so we can import modules
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from rag_system import RAGSystem
from config import Config
from search_tools import ToolManager, CourseSearchTool, CourseOutlineTool
import anthropic


class TestRAGIntegration(unittest.TestCase):

    def setUp(self):
        """Set up test fixtures"""
        # Create a test config
        self.test_config = Config()
        self.test_config.ANTHROPIC_API_KEY = "test_key"
        self.test_config.MAX_RESULTS = 5  # Fix the config issue
        self.test_config.CHROMA_PATH = tempfile.mkdtemp()  # Use temp directory

    def tearDown(self):
        """Clean up test fixtures"""
        if os.path.exists(self.test_config.CHROMA_PATH):
            shutil.rmtree(self.test_config.CHROMA_PATH)

    @patch("rag_system.AIGenerator")
    @patch("rag_system.VectorStore")
    @patch("rag_system.DocumentProcessor")
    @patch("rag_system.SessionManager")
    def test_rag_system_initialization(
        self, mock_session, mock_doc_proc, mock_vector_store, mock_ai_gen
    ):
        """Test RAGSystem initialization"""
        rag_system = RAGSystem(self.test_config)

        # Verify components were initialized
        mock_doc_proc.assert_called_once_with(
            self.test_config.CHUNK_SIZE, self.test_config.CHUNK_OVERLAP
        )
        mock_vector_store.assert_called_once_with(
            self.test_config.CHROMA_PATH,
            self.test_config.EMBEDDING_MODEL,
            self.test_config.MAX_RESULTS,
        )
        mock_ai_gen.assert_called_once_with(
            self.test_config.ANTHROPIC_API_KEY, self.test_config.ANTHROPIC_MODEL
        )
        mock_session.assert_called_once_with(self.test_config.MAX_HISTORY)

        # Verify tools are registered
        self.assertIsInstance(rag_system.tool_manager, ToolManager)
        self.assertIsInstance(rag_system.search_tool, CourseSearchTool)
        self.assertIsInstance(rag_system.outline_tool, CourseOutlineTool)

    @patch("rag_system.AIGenerator")
    @patch("rag_system.VectorStore")
    @patch("rag_system.DocumentProcessor")
    @patch("rag_system.SessionManager")
    def test_query_without_session(
        self, mock_session, mock_doc_proc, mock_vector_store, mock_ai_gen
    ):
        """Test query processing without session context"""
        # Mock AI generator response
        mock_ai_instance = Mock()
        mock_ai_instance.generate_response.return_value = "AI response about MCP"
        mock_ai_gen.return_value = mock_ai_instance

        # Mock tool manager
        mock_tool_manager = Mock()
        mock_tool_manager.get_last_sources.return_value = [
            {"text": "MCP Course - Lesson 1", "link": "http://test.com"}
        ]

        rag_system = RAGSystem(self.test_config)
        rag_system.tool_manager = mock_tool_manager

        result, sources = rag_system.query("What is MCP?")

        # Verify AI generator was called correctly
        mock_ai_instance.generate_response.assert_called_once()
        call_args = mock_ai_instance.generate_response.call_args[1]

        self.assertIn("query", call_args)
        self.assertEqual(call_args["conversation_history"], None)
        self.assertIn("tools", call_args)
        self.assertIn("tool_manager", call_args)

        # Check query format
        query_text = call_args["query"]
        self.assertIn("What is MCP?", query_text)

        # Verify results
        self.assertEqual(result, "AI response about MCP")
        self.assertEqual(len(sources), 1)
        self.assertEqual(sources[0]["text"], "MCP Course - Lesson 1")

    @patch("rag_system.AIGenerator")
    @patch("rag_system.VectorStore")
    @patch("rag_system.DocumentProcessor")
    @patch("rag_system.SessionManager")
    def test_query_with_session(
        self, mock_session, mock_doc_proc, mock_vector_store, mock_ai_gen
    ):
        """Test query processing with session context"""
        # Mock session manager
        mock_session_instance = Mock()
        mock_session_instance.get_conversation_history.return_value = (
            "Previous conversation history"
        )
        mock_session.return_value = mock_session_instance

        # Mock AI generator
        mock_ai_instance = Mock()
        mock_ai_instance.generate_response.return_value = "Follow-up response"
        mock_ai_gen.return_value = mock_ai_instance

        # Mock tool manager
        mock_tool_manager = Mock()
        mock_tool_manager.get_last_sources.return_value = []

        rag_system = RAGSystem(self.test_config)
        rag_system.tool_manager = mock_tool_manager

        result, sources = rag_system.query("Tell me more", session_id="session123")

        # Verify session history was retrieved and used
        mock_session_instance.get_conversation_history.assert_called_once_with(
            "session123"
        )

        call_args = mock_ai_instance.generate_response.call_args[1]
        self.assertEqual(
            call_args["conversation_history"], "Previous conversation history"
        )

        # Verify session was updated
        mock_session_instance.add_exchange.assert_called_once_with(
            "session123", "Tell me more", "Follow-up response"
        )

    @patch("rag_system.AIGenerator")
    @patch("rag_system.VectorStore")
    @patch("rag_system.DocumentProcessor")
    @patch("rag_system.SessionManager")
    def test_tool_manager_integration(
        self, mock_session, mock_doc_proc, mock_vector_store, mock_ai_gen
    ):
        """Test that tool manager is properly integrated with AI generator"""
        mock_ai_instance = Mock()
        mock_ai_instance.generate_response.return_value = "Tool-based response"
        mock_ai_gen.return_value = mock_ai_instance

        rag_system = RAGSystem(self.test_config)

        result, sources = rag_system.query("What is the MCP course outline?")

        # Verify tool definitions were passed to AI generator
        call_args = mock_ai_instance.generate_response.call_args[1]
        tools = call_args["tools"]
        tool_manager = call_args["tool_manager"]

        self.assertIsNotNone(tools)
        self.assertIs(tool_manager, rag_system.tool_manager)

        # Verify tools include both search and outline tools
        tool_names = [tool["name"] for tool in tools]
        self.assertIn("search_course_content", tool_names)
        self.assertIn("get_course_outline", tool_names)

    @patch("rag_system.AIGenerator")
    @patch("rag_system.VectorStore")
    @patch("rag_system.DocumentProcessor")
    @patch("rag_system.SessionManager")
    def test_sources_handling(
        self, mock_session, mock_doc_proc, mock_vector_store, mock_ai_gen
    ):
        """Test that sources are properly retrieved and reset"""
        mock_ai_instance = Mock()
        mock_ai_instance.generate_response.return_value = "Response with sources"
        mock_ai_gen.return_value = mock_ai_instance

        # Mock tool manager with sources
        mock_tool_manager = Mock()
        test_sources = [
            {"text": "Course A - Lesson 1", "link": "http://link1.com"},
            {"text": "Course B - Lesson 2", "link": "http://link2.com"},
        ]
        mock_tool_manager.get_last_sources.return_value = test_sources

        rag_system = RAGSystem(self.test_config)
        rag_system.tool_manager = mock_tool_manager

        result, sources = rag_system.query("Test query")

        # Verify sources were retrieved and reset
        mock_tool_manager.get_last_sources.assert_called_once()
        mock_tool_manager.reset_sources.assert_called_once()

        self.assertEqual(sources, test_sources)

    @patch("rag_system.AIGenerator")
    @patch("rag_system.VectorStore")
    @patch("rag_system.DocumentProcessor")
    @patch("rag_system.SessionManager")
    def test_error_handling_in_query(
        self, mock_session, mock_doc_proc, mock_vector_store, mock_ai_gen
    ):
        """Test error handling in query processing"""
        # Mock AI generator that raises an exception
        mock_ai_instance = Mock()
        mock_ai_instance.generate_response.side_effect = Exception("API error")
        mock_ai_gen.return_value = mock_ai_instance

        rag_system = RAGSystem(self.test_config)

        # Query should handle the exception gracefully
        with self.assertRaises(Exception):
            rag_system.query("Test query")

    @patch("rag_system.AIGenerator")
    @patch("rag_system.VectorStore")
    @patch("rag_system.DocumentProcessor")
    @patch("rag_system.SessionManager")
    def test_get_course_analytics(
        self, mock_session, mock_doc_proc, mock_vector_store, mock_ai_gen
    ):
        """Test course analytics functionality"""
        mock_vector_instance = Mock()
        mock_vector_instance.get_course_count.return_value = 4
        mock_vector_instance.get_existing_course_titles.return_value = [
            "MCP Course",
            "Retrieval Course",
            "Compression Course",
            "Computer Use Course",
        ]
        mock_vector_store.return_value = mock_vector_instance

        rag_system = RAGSystem(self.test_config)

        analytics = rag_system.get_course_analytics()

        expected = {
            "total_courses": 4,
            "course_titles": [
                "MCP Course",
                "Retrieval Course",
                "Compression Course",
                "Computer Use Course",
            ],
        }

        self.assertEqual(analytics, expected)


class TestRAGSystemRealConfiguration(unittest.TestCase):
    """Test RAG system with real configuration to identify config issues"""

    def test_config_max_results_issue(self):
        """Test that identifies the MAX_RESULTS=0 configuration issue"""
        from config import config

        # This test should fail and reveal the config issue
        self.assertGreater(
            config.MAX_RESULTS,
            0,
            "MAX_RESULTS is 0, which will cause search to return no results",
        )

    def test_config_anthropic_key_present(self):
        """Test that Anthropic API key is configured"""
        from config import config

        self.assertTrue(config.ANTHROPIC_API_KEY, "ANTHROPIC_API_KEY is not configured")
        self.assertNotEqual(config.ANTHROPIC_API_KEY, "", "ANTHROPIC_API_KEY is empty")

    def test_config_chroma_path_exists(self):
        """Test that ChromaDB path is accessible"""
        from config import config

        # Directory might not exist yet, but parent should be writable
        parent_dir = os.path.dirname(os.path.abspath(config.CHROMA_PATH))
        self.assertTrue(
            os.path.exists(parent_dir),
            f"Parent directory for ChromaDB path does not exist: {parent_dir}",
        )


if __name__ == "__main__":
    unittest.main()
