#!/usr/bin/env python3
"""Live system tests to reproduce actual server errors"""

import unittest
import sys
import os
from unittest.mock import patch
import tempfile
import shutil

# Add the parent directory to the path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from config import config
from rag_system import RAGSystem
from vector_store import VectorStore


class TestLiveSystemIssues(unittest.TestCase):
    """Test actual system configuration issues"""

    def test_max_results_zero_breaks_search(self):
        """Test that MAX_RESULTS=0 causes search to fail"""
        # Create a minimal vector store with the problematic config
        temp_dir = tempfile.mkdtemp()

        try:
            vector_store = VectorStore(
                chroma_path=temp_dir,
                embedding_model="all-MiniLM-L6-v2",
                max_results=0,  # This is the issue
            )

            # Try to search - this should return no results even if data exists
            results = vector_store.search("test query")

            # With MAX_RESULTS=0, we expect no results regardless of content
            self.assertTrue(
                results.is_empty() or results.error,
                "Search should fail or return empty with MAX_RESULTS=0",
            )

        finally:
            shutil.rmtree(temp_dir)

    def test_config_values(self):
        """Test current configuration values that might cause issues"""
        print(f"\n=== CONFIGURATION ANALYSIS ===")
        print(f"MAX_RESULTS: {config.MAX_RESULTS}")
        print(f"ANTHROPIC_API_KEY set: {'Yes' if config.ANTHROPIC_API_KEY else 'No'}")
        print(f"ANTHROPIC_MODEL: {config.ANTHROPIC_MODEL}")
        print(f"EMBEDDING_MODEL: {config.EMBEDDING_MODEL}")
        print(f"CHROMA_PATH: {config.CHROMA_PATH}")
        print(f"CHUNK_SIZE: {config.CHUNK_SIZE}")
        print(f"CHUNK_OVERLAP: {config.CHUNK_OVERLAP}")
        print(f"MAX_HISTORY: {config.MAX_HISTORY}")

        # Test the critical issue
        self.assertGreater(
            config.MAX_RESULTS,
            0,
            "CRITICAL: MAX_RESULTS=0 will cause all searches to return no results",
        )

    def test_rag_system_with_real_config(self):
        """Test RAG system initialization with real config"""
        # This test will likely fail due to config issues
        try:
            rag_system = RAGSystem(config)

            # Try a simple query that should work
            result, sources = rag_system.query("Hello")

            print(f"\nQuery result: {result}")
            print(f"Sources: {sources}")

        except Exception as e:
            self.fail(f"RAG system failed with real config: {e}")

    def test_vector_store_with_real_config(self):
        """Test vector store directly with real config"""
        vector_store = VectorStore(
            config.CHROMA_PATH, config.EMBEDDING_MODEL, config.MAX_RESULTS
        )

        # Try to get existing courses
        course_count = vector_store.get_course_count()
        print(f"\nCourse count in vector store: {course_count}")

        if course_count > 0:
            # Try a search with the problematic MAX_RESULTS=0
            results = vector_store.search("MCP")
            print(
                f"Search results with MAX_RESULTS=0: {len(results.documents)} documents"
            )
            print(f"Search error: {results.error}")

            # This should demonstrate the problem
            if config.MAX_RESULTS == 0:
                self.assertTrue(
                    results.is_empty(),
                    "With MAX_RESULTS=0, search should return empty even with valid data",
                )


if __name__ == "__main__":
    unittest.main(verbosity=2)
