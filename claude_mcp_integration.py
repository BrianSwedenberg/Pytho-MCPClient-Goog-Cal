# claude_mcp_integration.py
import asyncio
import json
import os
from datetime import datetime
from anthropic import Anthropic
from mcp_calendar_client import CalendarMCPClient

class ClaudeMCPIntegration:
    """Integration between Claude API and MCP Calendar Client"""
    
    def __init__(self, anthropic_api_key: str):
        self.client = Anthropic(api_key=anthropic_api_key)
        self.mcp_client = None
    
    async def initialize_mcp(self):
        """Initialize the MCP client connection"""
        self.mcp_client = CalendarMCPClient()
        await self.mcp_client.__aenter__()
    
    async def cleanup_mcp(self):
        """Cleanup MCP client connection"""
        if self.mcp_client:
            await self.mcp_client.__aexit__(None, None, None)
    
    def _format_tools_for_claude(self, mcp_tools: list) -> list:
        """Convert MCP tools to Claude API format"""
        claude_tools = []
        
        for tool in mcp_tools:
            claude_tool = {
                "name": tool["name"],
                "description": tool["description"],
                "input_schema": tool["input_schema"]
            }
            claude_tools.append(claude_tool)
        
        return claude_tools
    
    async def process_request(self, user_message: str) -> dict:
        """Process user request through Claude with MCP tools"""
        try:
            # Get available MCP tools
            mcp_tools = self.mcp_client.get_available_tools()
            claude_tools = self._format_tools_for_claude(mcp_tools)
            
            # Create system message that explains the calendar capabilities
            system_message = """You are an AI assistant with access to Google Calendar through MCP tools. 
            You can help users create, list, update, and manage calendar events. 
            
            When users ask for calendar operations:
            1. Use the appropriate MCP tool
            2. Format dates/times properly (ISO 8601 format)
            3. Provide clear confirmation of what was done
            
            Available calendar operations include creating events, listing events, updating events, etc."""
            
            # Make request to Claude
            response = self.client.messages.create(
                model="claude-3-5-sonnet-20241022",
                max_tokens=1000,
                system=system_message,
                tools=claude_tools,
                messages=[
                    {
                        "role": "user",
                        "content": user_message
                    }
                ]
            )
            
            # Process Claude's response
            result = await self._handle_claude_response(response)
            return result
            
        except Exception as e:
            return {
                "success": False,
                "error": f"Failed to process request: {str(e)}",
                "response": None
            }
    
    async def _handle_claude_response(self, response) -> dict:
        """Handle Claude's response and execute any tool calls"""
        results = []
        
        for content_block in response.content:
            if content_block.type == "text":
                results.append({
                    "type": "text",
                    "content": content_block.text
                })
            
            elif content_block.type == "tool_use":
                tool_name = content_block.name
                tool_input = content_block.input
                tool_id = content_block.id
                
                print(f"Claude wants to use tool: {tool_name}")
                print(f"Tool input: {tool_input}")
                
                # Execute the tool via MCP
                tool_result = await self.mcp_client.execute_tool(tool_name, tool_input)
                
                results.append({
                    "type": "tool_execution",
                    "tool_name": tool_name,
                    "tool_id": tool_id,
                    "input": tool_input,
                    "result": tool_result
                })
                
                # If there was a tool call, we need to send the result back to Claude
                # for a complete response
                follow_up_response = self.client.messages.create(
                    model="claude-3-5-sonnet-20241022",
                    max_tokens=1000,
                    messages=[
                        {
                            "role": "user",
                            "content": "Previous request"  # This would be the original request
                        },
                        {
                            "role": "assistant", 
                            "content": response.content
                        },
                        {
                            "role": "user",
                            "content": [
                                {
                                    "type": "tool_result",
                                    "tool_use_id": tool_id,
                                    "content": json.dumps(tool_result)
                                }
                            ]
                        }
                    ]
                )
                
                # Add Claude's final response
                for follow_up_block in follow_up_response.content:
                    if follow_up_block.type == "text":
                        results.append({
                            "type": "final_response",
                            "content": follow_up_block.text
                        })
        
        return {
            "success": True,
            "results": results,
            "raw_response": response
        }

# Main application class
class CalendarAssistant:
    """Main application for calendar operations via Claude + MCP"""
    
    def __init__(self, anthropic_api_key: str):
        self.integration = ClaudeMCPIntegration(anthropic_api_key)
    
    async def start(self):
        """Initialize the assistant"""
        await self.integration.initialize_mcp()
        print("Calendar Assistant initialized successfully!")
        print("Available commands:")
        print("- 'Create a meeting tomorrow at 2pm'")
        print("- 'List my events for this week'") 
        print("- 'Schedule a call with John on Friday at 10am'")
        print("- Type 'quit' to exit")
    
    async def stop(self):
        """Cleanup resources"""
        await self.integration.cleanup_mcp()
    
    async def process_command(self, command: str) -> dict:
        """Process a user command"""
        if command.lower() in ['quit', 'exit']:
            return {"action": "quit"}
        
        result = await self.integration.process_request(command)
        return result
    
    async def interactive_mode(self):
        """Run in interactive mode"""
        await self.start()
        
        try:
            while True:
                user_input = input("\nWhat would you like to do with your calendar? ")
                
                if user_input.lower() in ['quit', 'exit']:
                    break
                
                print("Processing request...")
                result = await self.process_command(user_input)
                
                if result.get("success"):
                    print("\n--- Response ---")
                    for item in result.get("results", []):
                        if item["type"] == "text":
                            print(f"Claude: {item['content']}")
                        elif item["type"] == "tool_execution":
                            print(f"Executed: {item['tool_name']}")
                            if item["result"]["success"]:
                                print("✅ Success!")
                            else:
                                print(f"❌ Error: {item['result'].get('error')}")
                        elif item["type"] == "final_response":
                            print(f"Claude: {item['content']}")
                else:
                    print(f"❌ Error: {result.get('error')}")
        
        finally:
            await self.stop()
            print("Goodbye!")

# Example usage functions
async def example_api_call():
    """Example of using the system programmatically"""
    api_key = os.getenv("ANTHROPIC_API_KEY")
    if not api_key:
        print("Please set ANTHROPIC_API_KEY environment variable")
        return
    
    assistant = CalendarAssistant(api_key)
    await assistant.start()
    
    try:
        # Example request
        result = await assistant.process_command(
            "Create a team standup meeting tomorrow at 9am for 30 minutes"
        )
        
        print("Result:", json.dumps(result, indent=2, default=str))
        
    finally:
        await assistant.stop()

async def run_interactive():
    """Run the interactive assistant"""
    api_key = os.getenv("ANTHROPIC_API_KEY")
    if not api_key:
        print("Please set ANTHROPIC_API_KEY environment variable")
        return
    
    assistant = CalendarAssistant(api_key)
    await assistant.interactive_mode()

if __name__ == "__main__":
    # Run interactive mode by default
    asyncio.run(run_interactive())
    
    # Or run a single API call example:
    # asyncio.run(example_api_call())