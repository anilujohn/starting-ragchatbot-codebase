import unittest
import sys
import os
from unittest.mock import Mock, patch, MagicMock

# Add the parent directory to the path so we can import modules
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from search_tools import CourseSearchTool
from vector_store import VectorStore, SearchResults

class TestCourseSearchTool(unittest.TestCase):
    
    def setUp(self):
        """Set up test fixtures"""
        self.mock_vector_store = Mock(spec=VectorStore)
        self.search_tool = CourseSearchTool(self.mock_vector_store)
    
    def test_tool_definition(self):
        """Test that tool definition is properly formatted"""
        definition = self.search_tool.get_tool_definition()
        
        self.assertEqual(definition["name"], "search_course_content")
        self.assertIn("description", definition)
        self.assertIn("input_schema", definition)
        
        # Check required parameters
        required_params = definition["input_schema"]["required"]
        self.assertEqual(required_params, ["query"])
        
        # Check optional parameters exist
        properties = definition["input_schema"]["properties"]
        self.assertIn("query", properties)
        self.assertIn("course_name", properties)
        self.assertIn("lesson_number", properties)
    
    def test_execute_with_valid_results(self):
        """Test execute method with successful search results"""
        # Mock search results
        mock_results = SearchResults(
            documents=["Sample course content about MCP"],
            metadata=[{"course_title": "MCP Course", "lesson_number": 1}],
            distances=[0.5],
            lesson_links={"MCP Course|1": "http://example.com/lesson1"}
        )
        self.mock_vector_store.search.return_value = mock_results
        
        result = self.search_tool.execute("What is MCP?")
        
        # Check that search was called correctly
        self.mock_vector_store.search.assert_called_once_with(
            query="What is MCP?",
            course_name=None,
            lesson_number=None
        )
        
        # Check result format
        self.assertIn("MCP Course", result)
        self.assertIn("Sample course content about MCP", result)
        self.assertIn("Lesson 1", result)
    
    def test_execute_with_course_filter(self):
        """Test execute method with course name filter"""
        mock_results = SearchResults(
            documents=["Filtered content"],
            metadata=[{"course_title": "Specific Course", "lesson_number": 2}],
            distances=[0.3]
        )
        self.mock_vector_store.search.return_value = mock_results
        
        result = self.search_tool.execute("test query", course_name="Specific Course")
        
        self.mock_vector_store.search.assert_called_once_with(
            query="test query",
            course_name="Specific Course",
            lesson_number=None
        )
        self.assertIn("Specific Course", result)
    
    def test_execute_with_lesson_filter(self):
        """Test execute method with lesson number filter"""
        mock_results = SearchResults(
            documents=["Lesson specific content"],
            metadata=[{"course_title": "Test Course", "lesson_number": 3}],
            distances=[0.2]
        )
        self.mock_vector_store.search.return_value = mock_results
        
        result = self.search_tool.execute("test query", lesson_number=3)
        
        self.mock_vector_store.search.assert_called_once_with(
            query="test query",
            course_name=None,
            lesson_number=3
        )
        self.assertIn("Lesson 3", result)
    
    def test_execute_with_empty_results(self):
        """Test execute method when search returns no results"""
        mock_results = SearchResults(
            documents=[],
            metadata=[],
            distances=[]
        )
        self.mock_vector_store.search.return_value = mock_results
        
        result = self.search_tool.execute("nonexistent query")
        
        self.assertIn("No relevant content found", result)
    
    def test_execute_with_search_error(self):
        """Test execute method when search returns an error"""
        mock_results = SearchResults(
            documents=[],
            metadata=[],
            distances=[],
            error="Vector store connection failed"
        )
        self.mock_vector_store.search.return_value = mock_results
        
        result = self.search_tool.execute("test query")
        
        self.assertEqual(result, "Vector store connection failed")
    
    def test_execute_with_course_and_lesson_filter(self):
        """Test execute method with both course and lesson filters"""
        mock_results = SearchResults(
            documents=["Very specific content"],
            metadata=[{"course_title": "Target Course", "lesson_number": 5}],
            distances=[0.1]
        )
        self.mock_vector_store.search.return_value = mock_results
        
        result = self.search_tool.execute(
            "specific query", 
            course_name="Target Course", 
            lesson_number=5
        )
        
        self.mock_vector_store.search.assert_called_once_with(
            query="specific query",
            course_name="Target Course",
            lesson_number=5
        )
        self.assertIn("Target Course", result)
        self.assertIn("Lesson 5", result)
    
    def test_sources_tracking(self):
        """Test that sources are properly tracked for UI display"""
        mock_results = SearchResults(
            documents=["Content 1", "Content 2"],
            metadata=[
                {"course_title": "Course A", "lesson_number": 1},
                {"course_title": "Course B", "lesson_number": 2}
            ],
            distances=[0.3, 0.4],
            lesson_links={"Course A|1": "http://link1.com", "Course B|2": "http://link2.com"}
        )
        self.mock_vector_store.search.return_value = mock_results
        
        result = self.search_tool.execute("test query")
        
        # Check that sources are stored
        self.assertEqual(len(self.search_tool.last_sources), 2)
        
        # Check source structure
        source1 = self.search_tool.last_sources[0]
        self.assertEqual(source1["text"], "Course A - Lesson 1")
        self.assertEqual(source1["link"], "http://link1.com")
        
        source2 = self.search_tool.last_sources[1]
        self.assertEqual(source2["text"], "Course B - Lesson 2")
        self.assertEqual(source2["link"], "http://link2.com")
    
    def test_sources_without_lesson_links(self):
        """Test sources tracking when lesson links are not available"""
        mock_results = SearchResults(
            documents=["Content without links"],
            metadata=[{"course_title": "Course C", "lesson_number": 3}],
            distances=[0.5]
        )
        self.mock_vector_store.search.return_value = mock_results
        
        result = self.search_tool.execute("test query")
        
        self.assertEqual(len(self.search_tool.last_sources), 1)
        source = self.search_tool.last_sources[0]
        self.assertEqual(source["text"], "Course C - Lesson 3")
        self.assertIsNone(source["link"])

if __name__ == '__main__':
    unittest.main()