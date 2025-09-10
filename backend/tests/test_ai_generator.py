import unittest
import sys
import os
from unittest.mock import Mock, patch, MagicMock

# Add the parent directory to the path so we can import modules
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from ai_generator import AIGenerator
import anthropic


class TestAIGenerator(unittest.TestCase):

    def setUp(self):
        """Set up test fixtures"""
        self.api_key = "test_api_key"
        self.model = "claude-sonnet-4-20250514"

    @patch("ai_generator.anthropic.Anthropic")
    def test_init(self, mock_anthropic):
        """Test AIGenerator initialization"""
        generator = AIGenerator(self.api_key, self.model)

        mock_anthropic.assert_called_once_with(api_key=self.api_key)
        self.assertEqual(generator.model, self.model)
        self.assertIn("model", generator.base_params)
        self.assertIn("temperature", generator.base_params)
        self.assertIn("max_tokens", generator.base_params)

    @patch("ai_generator.anthropic.Anthropic")
    def test_generate_response_without_tools(self, mock_anthropic):
        """Test response generation without tools"""
        mock_client = Mock()
        mock_response = Mock()
        mock_response.content = [Mock(text="Test response")]
        mock_response.stop_reason = "end_turn"
        mock_client.messages.create.return_value = mock_response
        mock_anthropic.return_value = mock_client

        generator = AIGenerator(self.api_key, self.model)
        result = generator.generate_response("What is AI?")

        self.assertEqual(result, "Test response")
        mock_client.messages.create.assert_called_once()

        # Check that the call was made with correct parameters
        call_args = mock_client.messages.create.call_args[1]
        self.assertIn("messages", call_args)
        self.assertIn("system", call_args)
        self.assertEqual(len(call_args["messages"]), 1)
        self.assertEqual(call_args["messages"][0]["role"], "user")
        self.assertEqual(call_args["messages"][0]["content"], "What is AI?")

    @patch("ai_generator.anthropic.Anthropic")
    def test_generate_response_with_conversation_history(self, mock_anthropic):
        """Test response generation with conversation history"""
        mock_client = Mock()
        mock_response = Mock()
        mock_response.content = [Mock(text="Response with history")]
        mock_response.stop_reason = "end_turn"
        mock_client.messages.create.return_value = mock_response
        mock_anthropic.return_value = mock_response

        generator = AIGenerator(self.api_key, self.model)
        generator.client = mock_client

        history = "Previous: What is MCP?\nAssistant: MCP is a protocol..."
        result = generator.generate_response(
            "Tell me more", conversation_history=history
        )

        # Check that system prompt includes history
        call_args = mock_client.messages.create.call_args[1]
        self.assertIn(history, call_args["system"])

    @patch("ai_generator.anthropic.Anthropic")
    def test_generate_response_with_tools_no_tool_use(self, mock_anthropic):
        """Test response generation with tools available but not used"""
        mock_client = Mock()
        mock_response = Mock()
        mock_response.content = [Mock(text="Direct response")]
        mock_response.stop_reason = "end_turn"
        mock_client.messages.create.return_value = mock_response
        mock_anthropic.return_value = mock_client

        generator = AIGenerator(self.api_key, self.model)

        tools = [{"name": "search_course_content", "description": "Search tool"}]
        tool_manager = Mock()

        result = generator.generate_response(
            "What is 2+2?", tools=tools, tool_manager=tool_manager
        )

        self.assertEqual(result, "Direct response")

        # Check that tools were included in the API call
        call_args = mock_client.messages.create.call_args[1]
        self.assertIn("tools", call_args)
        self.assertEqual(call_args["tools"], tools)
        self.assertIn("tool_choice", call_args)

    @patch("ai_generator.anthropic.Anthropic")
    def test_generate_response_with_tool_use(self, mock_anthropic):
        """Test response generation when tool use is required"""
        mock_client = Mock()

        # First response with tool use
        mock_tool_block = Mock()
        mock_tool_block.type = "tool_use"
        mock_tool_block.name = "search_course_content"
        mock_tool_block.id = "tool_123"
        mock_tool_block.input = {"query": "What is MCP?"}

        mock_initial_response = Mock()
        mock_initial_response.content = [mock_tool_block]
        mock_initial_response.stop_reason = "tool_use"

        # Final response after tool execution
        mock_final_response = Mock()
        mock_final_response.content = [Mock(text="Based on the search, MCP is...")]

        mock_client.messages.create.side_effect = [
            mock_initial_response,
            mock_final_response,
        ]
        mock_anthropic.return_value = mock_client

        generator = AIGenerator(self.api_key, self.model)

        # Mock tool manager
        tool_manager = Mock()
        tool_manager.execute_tool.return_value = "MCP is a protocol for AI systems"

        tools = [{"name": "search_course_content", "description": "Search tool"}]

        result = generator.generate_response(
            "What is MCP?", tools=tools, tool_manager=tool_manager
        )

        self.assertEqual(result, "Based on the search, MCP is...")

        # Verify tool was executed
        tool_manager.execute_tool.assert_called_once_with(
            "search_course_content", query="What is MCP?"
        )

        # Verify two API calls were made
        self.assertEqual(mock_client.messages.create.call_count, 2)

    @patch("ai_generator.anthropic.Anthropic")
    def test_handle_tool_execution_multiple_tools(self, mock_anthropic):
        """Test handling multiple tool calls in a single response"""
        mock_client = Mock()

        # Mock tool blocks
        tool_block_1 = Mock()
        tool_block_1.type = "tool_use"
        tool_block_1.name = "search_course_content"
        tool_block_1.id = "tool_1"
        tool_block_1.input = {"query": "search 1"}

        tool_block_2 = Mock()
        tool_block_2.type = "tool_use"
        tool_block_2.name = "get_course_outline"
        tool_block_2.id = "tool_2"
        tool_block_2.input = {"course_name": "MCP"}

        mock_initial_response = Mock()
        mock_initial_response.content = [tool_block_1, tool_block_2]
        mock_initial_response.stop_reason = "tool_use"

        mock_final_response = Mock()
        mock_final_response.content = [Mock(text="Combined tool results")]

        mock_client.messages.create.side_effect = [
            mock_initial_response,
            mock_final_response,
        ]
        mock_anthropic.return_value = mock_client

        generator = AIGenerator(self.api_key, self.model)

        # Mock tool manager
        tool_manager = Mock()
        tool_manager.execute_tool.side_effect = ["Search result", "Outline result"]

        tools = [
            {"name": "search_course_content", "description": "Search tool"},
            {"name": "get_course_outline", "description": "Outline tool"},
        ]

        result = generator.generate_response(
            "Complex query", tools=tools, tool_manager=tool_manager
        )

        self.assertEqual(result, "Combined tool results")

        # Verify both tools were executed
        self.assertEqual(tool_manager.execute_tool.call_count, 2)
        tool_manager.execute_tool.assert_any_call(
            "search_course_content", query="search 1"
        )
        tool_manager.execute_tool.assert_any_call(
            "get_course_outline", course_name="MCP"
        )

    @patch("ai_generator.anthropic.Anthropic")
    def test_system_prompt_content(self, mock_anthropic):
        """Test that system prompt contains expected content"""
        mock_client = Mock()
        mock_response = Mock()
        mock_response.content = [Mock(text="Test")]
        mock_response.stop_reason = "end_turn"
        mock_client.messages.create.return_value = mock_response
        mock_anthropic.return_value = mock_client

        generator = AIGenerator(self.api_key, self.model)
        generator.generate_response("test query")

        call_args = mock_client.messages.create.call_args[1]
        system_prompt = call_args["system"]

        # Check key components of the system prompt
        self.assertIn("search_course_content", system_prompt)
        self.assertIn("get_course_outline", system_prompt)
        self.assertIn("Tool Usage Guidelines", system_prompt)
        self.assertIn("Multi-round tool usage", system_prompt)
        self.assertIn("up to 2 rounds", system_prompt)
        self.assertIn("course outline responses", system_prompt)

    @patch("ai_generator.anthropic.Anthropic")
    def test_tool_execution_error_handling(self, mock_anthropic):
        """Test error handling during tool execution"""
        mock_client = Mock()

        # Mock tool use response
        mock_tool_block = Mock()
        mock_tool_block.type = "tool_use"
        mock_tool_block.name = "search_course_content"
        mock_tool_block.id = "tool_123"
        mock_tool_block.input = {"query": "test"}

        mock_initial_response = Mock()
        mock_initial_response.content = [mock_tool_block]
        mock_initial_response.stop_reason = "tool_use"

        mock_final_response = Mock()
        mock_final_response.content = [Mock(text="Error handled response")]

        mock_client.messages.create.side_effect = [
            mock_initial_response,
            mock_final_response,
        ]
        mock_anthropic.return_value = mock_client

        generator = AIGenerator(self.api_key, self.model)

        # Mock tool manager that raises an exception
        tool_manager = Mock()
        tool_manager.execute_tool.return_value = "Tool execution failed"

        result = generator.generate_response(
            "test query",
            tools=[{"name": "search_course_content"}],
            tool_manager=tool_manager,
        )

        self.assertEqual(result, "Error handled response")

    @patch("ai_generator.anthropic.Anthropic")
    def test_multi_round_tool_calling(self, mock_anthropic):
        """Test multi-round tool calling functionality"""
        mock_client = Mock()

        # Round 1: Get course outline
        mock_tool_block_1 = Mock()
        mock_tool_block_1.type = "tool_use"
        mock_tool_block_1.name = "get_course_outline"
        mock_tool_block_1.id = "tool_1"
        mock_tool_block_1.input = {"course_name": "MCP"}

        mock_response_1 = Mock()
        mock_response_1.content = [mock_tool_block_1]
        mock_response_1.stop_reason = "tool_use"

        # Round 2: Search for content based on outline
        mock_tool_block_2 = Mock()
        mock_tool_block_2.type = "tool_use"
        mock_tool_block_2.name = "search_course_content"
        mock_tool_block_2.id = "tool_2"
        mock_tool_block_2.input = {"query": "lesson 1 details"}

        mock_response_2 = Mock()
        mock_response_2.content = [mock_tool_block_2]
        mock_response_2.stop_reason = "tool_use"

        # Final response
        mock_final_response = Mock()
        mock_final_response.content = [
            Mock(text="Combined information from outline and search")
        ]
        mock_final_response.stop_reason = "end_turn"

        mock_client.messages.create.side_effect = [
            mock_response_1,  # First round
            mock_response_2,  # Second round
            mock_final_response,  # Final response
        ]
        mock_anthropic.return_value = mock_client

        generator = AIGenerator(self.api_key, self.model)

        # Mock tool manager
        tool_manager = Mock()
        tool_manager.execute_tool.side_effect = [
            "Course outline: Lesson 1: Introduction",  # First tool result
            "Lesson 1 details: MCP overview",  # Second tool result
        ]

        tools = [
            {"name": "get_course_outline", "description": "Outline tool"},
            {"name": "search_course_content", "description": "Search tool"},
        ]

        result = generator.generate_response(
            "Get the outline for MCP course and then search for details about lesson 1",
            tools=tools,
            tool_manager=tool_manager,
        )

        self.assertEqual(result, "Combined information from outline and search")

        # Verify both tools were executed in sequence
        self.assertEqual(tool_manager.execute_tool.call_count, 2)
        tool_manager.execute_tool.assert_any_call(
            "get_course_outline", course_name="MCP"
        )
        tool_manager.execute_tool.assert_any_call(
            "search_course_content", query="lesson 1 details"
        )

        # Verify 3 API calls were made (2 rounds + final response)
        self.assertEqual(mock_client.messages.create.call_count, 3)

    @patch("ai_generator.anthropic.Anthropic")
    def test_early_termination_no_tool_use(self, mock_anthropic):
        """Test that multi-round terminates early when Claude doesn't use tools"""
        mock_client = Mock()

        # First call: no tool use
        mock_response = Mock()
        mock_response.content = [Mock(text="Direct answer without tools")]
        mock_response.stop_reason = "end_turn"

        mock_client.messages.create.return_value = mock_response
        mock_anthropic.return_value = mock_client

        generator = AIGenerator(self.api_key, self.model)

        tool_manager = Mock()
        tools = [{"name": "search_course_content", "description": "Search tool"}]

        result = generator.generate_response(
            "What is 2+2?", tools=tools, tool_manager=tool_manager
        )

        self.assertEqual(result, "Direct answer without tools")

        # Should only make one API call
        self.assertEqual(mock_client.messages.create.call_count, 1)

        # Tool manager should not be called
        tool_manager.execute_tool.assert_not_called()

    @patch("ai_generator.anthropic.Anthropic")
    def test_max_rounds_termination(self, mock_anthropic):
        """Test that multi-round terminates after max rounds (2)"""
        mock_client = Mock()

        # Round 1: Tool use
        mock_tool_block_1 = Mock()
        mock_tool_block_1.type = "tool_use"
        mock_tool_block_1.name = "search_course_content"
        mock_tool_block_1.id = "tool_1"
        mock_tool_block_1.input = {"query": "first search"}

        mock_response_1 = Mock()
        mock_response_1.content = [mock_tool_block_1]
        mock_response_1.stop_reason = "tool_use"

        # Round 2: Tool use (should be last round)
        mock_tool_block_2 = Mock()
        mock_tool_block_2.type = "tool_use"
        mock_tool_block_2.name = "get_course_outline"
        mock_tool_block_2.id = "tool_2"
        mock_tool_block_2.input = {"course_name": "test"}

        mock_response_2 = Mock()
        mock_response_2.content = [mock_tool_block_2]
        mock_response_2.stop_reason = "tool_use"

        # Final response without tools
        mock_final_response = Mock()
        mock_final_response.content = [Mock(text="Final response after 2 rounds")]
        mock_final_response.stop_reason = "end_turn"

        mock_client.messages.create.side_effect = [
            mock_response_1,  # Round 1
            mock_response_2,  # Round 2
            mock_final_response,  # Final call without tools
        ]
        mock_anthropic.return_value = mock_client

        generator = AIGenerator(self.api_key, self.model)

        tool_manager = Mock()
        tool_manager.execute_tool.side_effect = ["Result 1", "Result 2"]

        tools = [
            {"name": "search_course_content", "description": "Search tool"},
            {"name": "get_course_outline", "description": "Outline tool"},
        ]

        result = generator.generate_response(
            "Complex query requiring multiple searches",
            tools=tools,
            tool_manager=tool_manager,
        )

        self.assertEqual(result, "Final response after 2 rounds")

        # Should execute exactly 2 tools (max rounds)
        self.assertEqual(tool_manager.execute_tool.call_count, 2)

        # Should make exactly 3 API calls (2 rounds + 1 final)
        self.assertEqual(mock_client.messages.create.call_count, 3)

    @patch("ai_generator.anthropic.Anthropic")
    def test_tool_execution_failure_in_round(self, mock_anthropic):
        """Test that tool execution failure terminates multi-round sequence"""
        mock_client = Mock()

        # First round: tool use that will fail
        mock_tool_block = Mock()
        mock_tool_block.type = "tool_use"
        mock_tool_block.name = "search_course_content"
        mock_tool_block.id = "tool_1"
        mock_tool_block.input = {"query": "test"}

        mock_response = Mock()
        mock_response.content = [mock_tool_block]
        mock_response.stop_reason = "tool_use"

        mock_client.messages.create.return_value = mock_response
        mock_anthropic.return_value = mock_client

        generator = AIGenerator(self.api_key, self.model)

        # Mock tool manager that raises an exception
        tool_manager = Mock()
        tool_manager.execute_tool.side_effect = Exception("Tool failed")

        tools = [{"name": "search_course_content", "description": "Search tool"}]

        result = generator.generate_response(
            "test query", tools=tools, tool_manager=tool_manager
        )

        self.assertEqual(result, "Tool execution failed")

        # Should only make one API call before failure
        self.assertEqual(mock_client.messages.create.call_count, 1)

        # Tool should be called once and fail
        self.assertEqual(tool_manager.execute_tool.call_count, 1)


if __name__ == "__main__":
    unittest.main()
