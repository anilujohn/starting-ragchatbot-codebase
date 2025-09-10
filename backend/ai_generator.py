import anthropic
from typing import List, Optional, Dict, Any, Tuple
from dataclasses import dataclass

@dataclass
class ConversationState:
    """Manages state across multiple rounds of tool calling"""
    messages: List[Dict[str, Any]]
    system_prompt: str
    round_count: int
    max_rounds: int
    tools: Optional[List]
    tool_manager: Optional[Any]
    base_params: Dict[str, Any]

class AIGenerator:
    """Handles interactions with Anthropic's Claude API for generating responses"""
    
    # Static system prompt to avoid rebuilding on each call
    SYSTEM_PROMPT = """ You are an AI assistant specialized in course materials and educational content with access to comprehensive search tools for course information.

Available Tools:
- **search_course_content**: Search within course materials for specific content, concepts, or technical details
- **get_course_outline**: Get complete course outlines including title, course link, and all lessons with numbers and titles

Tool Usage Guidelines:
- Use search_course_content for questions about specific course content, educational materials, AND technical implementation details
- Use get_course_outline for questions about course structure, lesson lists, or complete course overviews
- **Multi-round tool usage**: You can make tool calls across up to 2 rounds to gather comprehensive information
- Use multiple tool calls to:
  - Gather complementary information from different tools
  - Search for specific details after getting general context
  - Cross-reference information from multiple sources
- Example: Search for course outline first, then search specific lessons for details
- Stop making tool calls when you have sufficient information to answer
- Synthesize tool results into accurate, fact-based responses
- If tools yield no results, state this clearly without offering alternatives

Response Protocol:
- **General knowledge questions**: Answer using existing knowledge without using tools
- **Course-specific content questions**: Use search_course_content first, then answer
- **Course outline/structure questions**: Use get_course_outline first, then answer
- **Technical implementation questions**: Use search_course_content for relevant documentation or code examples
- **No meta-commentary**:
 - Provide direct answers only — no reasoning process, tool explanations, or question-type analysis
 - Do not mention "based on the search results" or "using the outline tool"

For course outline responses, always include:
- Course title
- Course link (if available)
- Complete lesson list with numbers and titles

All responses must be:
1. **Brief, Concise and focused** - Get to the point quickly
2. **Educational** - Maintain instructional value
3. **Clear** - Use accessible language
4. **Example-supported** - Include relevant examples when they aid understanding
Provide only the direct answer to what was asked.
"""
    
    def __init__(self, api_key: str, model: str):
        self.client = anthropic.Anthropic(api_key=api_key)
        self.model = model
        
        # Pre-build base API parameters
        self.base_params = {
            "model": self.model,
            "temperature": 0,
            "max_tokens": 800
        }
    
    def generate_response_with_rounds(self, query: str,
                                    conversation_history: Optional[str] = None,
                                    tools: Optional[List] = None,
                                    tool_manager=None,
                                    max_rounds: int = 2) -> str:
        """
        Generate AI response with support for multiple rounds of tool calling.
        
        Args:
            query: The user's question or request
            conversation_history: Previous messages for context
            tools: Available tools the AI can use
            tool_manager: Manager to execute tools
            max_rounds: Maximum number of tool calling rounds (default 2)
            
        Returns:
            Generated response as string
        """
        
        # Build system content efficiently
        system_content = (
            f"{self.SYSTEM_PROMPT}\n\nPrevious conversation:\n{conversation_history}"
            if conversation_history 
            else self.SYSTEM_PROMPT
        )
        
        # Initialize conversation state
        state = ConversationState(
            messages=[{"role": "user", "content": query}],
            system_prompt=system_content,
            round_count=0,
            max_rounds=max_rounds,
            tools=tools,
            tool_manager=tool_manager,
            base_params={
                **self.base_params,
                "system": system_content
            }
        )
        
        # Execute rounds until termination condition met
        while state.round_count < state.max_rounds:
            response, should_continue, termination_reason = self._execute_single_round(state)
            
            if not should_continue:
                return response
                
            state.round_count += 1
        
        # If we've exhausted all rounds, make a final call without tools
        final_params = {
            **state.base_params,
            "messages": state.messages
        }
        final_response = self.client.messages.create(**final_params)
        return final_response.content[0].text
    
    def _execute_single_round(self, state: ConversationState) -> Tuple[str, bool, Optional[str]]:
        """
        Execute a single round of conversation with tool support.
        
        Args:
            state: Current conversation state
            
        Returns:
            Tuple of (response_text, should_continue, termination_reason)
        """
        # Prepare API call parameters
        api_params = {
            **state.base_params,
            "messages": state.messages
        }
        
        # Add tools if available and not final round
        if state.tools and state.tool_manager:
            api_params["tools"] = state.tools
            api_params["tool_choice"] = {"type": "auto"}
        
        # Make API call to Claude
        try:
            response = self.client.messages.create(**api_params)
        except Exception as e:
            return f"Error generating response: {str(e)}", False, "api_error"
        
        # Check if Claude wants to use tools
        if response.stop_reason == "tool_use" and state.tool_manager:
            # Execute tools and add results to conversation
            tool_success = self._execute_tools_and_update_state(response, state)
            if not tool_success:
                return "Tool execution failed", False, "tool_error"
            
            # Check if we should continue for another round
            should_continue, reason = self._should_continue_rounds(state)
            if not should_continue:
                # Make final call without tools
                final_params = {
                    **state.base_params,
                    "messages": state.messages
                }
                final_response = self.client.messages.create(**final_params)
                return final_response.content[0].text, False, reason
            
            return "", True, None  # Continue to next round
        
        # No tool use - return response directly
        return response.content[0].text, False, "no_tool_use"
    
    def _execute_tools_and_update_state(self, response, state: ConversationState) -> bool:
        """
        Execute tools from response and update conversation state.
        
        Args:
            response: Claude's response containing tool calls
            state: Conversation state to update
            
        Returns:
            True if all tools executed successfully, False otherwise
        """
        # Add AI's tool use response to conversation
        state.messages.append({"role": "assistant", "content": response.content})
        
        # Execute all tool calls and collect results
        tool_results = []
        for content_block in response.content:
            if content_block.type == "tool_use":
                try:
                    tool_result = state.tool_manager.execute_tool(
                        content_block.name, 
                        **content_block.input
                    )
                    
                    tool_results.append({
                        "type": "tool_result",
                        "tool_use_id": content_block.id,
                        "content": tool_result
                    })
                except Exception as e:
                    # Add error result but continue
                    tool_results.append({
                        "type": "tool_result",
                        "tool_use_id": content_block.id,
                        "content": f"Tool execution failed: {str(e)}",
                        "is_error": True
                    })
                    return False
        
        # Add tool results to conversation
        if tool_results:
            state.messages.append({"role": "user", "content": tool_results})
        
        return True
    
    def _should_continue_rounds(self, state: ConversationState) -> Tuple[bool, Optional[str]]:
        """
        Determine if we should continue to another round of tool calling.
        
        Args:
            state: Current conversation state
            
        Returns:
            Tuple of (should_continue, termination_reason)
        """
        # Check if we've reached max rounds
        if state.round_count >= state.max_rounds - 1:  # -1 because we increment after this check
            return False, "max_rounds_reached"
        
        # Check if tools are available
        if not state.tools or not state.tool_manager:
            return False, "no_tools_available"
        
        # Continue by default - let Claude decide if it needs more tools
        return True, None
    
    def generate_response(self, query: str,
                         conversation_history: Optional[str] = None,
                         tools: Optional[List] = None,
                         tool_manager=None) -> str:
        """
        Generate AI response with optional tool usage and conversation context.
        Updated to support multi-round tool calling.
        
        Args:
            query: The user's question or request
            conversation_history: Previous messages for context
            tools: Available tools the AI can use
            tool_manager: Manager to execute tools
            
        Returns:
            Generated response as string
        """
        # Delegate to multi-round handler
        return self.generate_response_with_rounds(
            query=query,
            conversation_history=conversation_history,
            tools=tools,
            tool_manager=tool_manager,
            max_rounds=2
        )
    
    def _handle_tool_execution(self, initial_response, base_params: Dict[str, Any], tool_manager):
        """
        Handle execution of tool calls and get follow-up response.
        
        Args:
            initial_response: The response containing tool use requests
            base_params: Base API parameters
            tool_manager: Manager to execute tools
            
        Returns:
            Final response text after tool execution
        """
        # Start with existing messages
        messages = base_params["messages"].copy()
        
        # Add AI's tool use response
        messages.append({"role": "assistant", "content": initial_response.content})
        
        # Execute all tool calls and collect results
        tool_results = []
        for content_block in initial_response.content:
            if content_block.type == "tool_use":
                tool_result = tool_manager.execute_tool(
                    content_block.name, 
                    **content_block.input
                )
                
                tool_results.append({
                    "type": "tool_result",
                    "tool_use_id": content_block.id,
                    "content": tool_result
                })
        
        # Add tool results as single message
        if tool_results:
            messages.append({"role": "user", "content": tool_results})
        
        # Prepare final API call without tools
        final_params = {
            **self.base_params,
            "messages": messages,
            "system": base_params["system"]
        }
        
        # Get final response
        final_response = self.client.messages.create(**final_params)
        return final_response.content[0].text