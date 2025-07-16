# mcp_calendar_client.py
import asyncio
import json
import logging
from typing import Dict, Any, Optional
from datetime import datetime, timedelta
from mcp import ClientSession
from mcp.client.stdio import stdio_client

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class CalendarMCPClient:
    """MCP Client for Google Calendar operations"""
    
    def __init__(self, server_command: str = "npx", server_args: list = None):
        self.server_command = server_command
        self.server_args = server_args or ["-y", "@cocal/google-calendar-mcp"]
        self.session = None
        self.tools = {}
    
    async def __aenter__(self):
        """Async context manager entry"""
        try:
            # Create stdio client connection to MCP server
            self.stdio_client = stdio_client(self.server_command, self.server_args)
            self.read, self.write = await self.stdio_client.__aenter__()
            
            # Create client session
            self.session_context = ClientSession(self.read, self.write)
            self.session = await self.session_context.__aenter__()
            
            # Initialize connection and discover tools
            await self.session.initialize()
            await self._discover_tools()
            
            logger.info("Successfully connected to Google Calendar MCP server")
            return self
            
        except Exception as e:
            logger.error(f"Failed to connect to MCP server: {e}")
            raise
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit"""
        if hasattr(self, 'session_context'):
            await self.session_context.__aexit__(exc_type, exc_val, exc_tb)
        if hasattr(self, 'stdio_client'):
            await self.stdio_client.__aexit__(exc_type, exc_val, exc_tb)
    
    async def _discover_tools(self):
        """Discover available tools from the MCP server"""
        try:
            tools_response = await self.session.list_tools()
            self.tools = {tool.name: tool for tool in tools_response.tools}
            logger.info(f"Discovered tools: {list(self.tools.keys())}")
        except Exception as e:
            logger.error(f"Failed to discover tools: {e}")
            raise
    
    def get_available_tools(self) -> Dict[str, Any]:
        """Return available tools for Claude"""
        claude_tools = []
        
        for tool_name, tool in self.tools.items():
            claude_tool = {
                "name": tool_name,
                "description": tool.description,
                "input_schema": tool.inputSchema
            }
            claude_tools.append(claude_tool)
        
        return claude_tools
    
    async def execute_tool(self, tool_name: str, arguments: Dict[str, Any]) -> Dict[str, Any]:
        """Execute a tool via the MCP server"""
        if tool_name not in self.tools:
            raise ValueError(f"Tool '{tool_name}' not available. Available tools: {list(self.tools.keys())}")
        
        try:
            result = await self.session.call_tool(tool_name, arguments)
            return {
                "success": True,
                "content": result.content,
                "tool_name": tool_name
            }
        except Exception as e:
            logger.error(f"Tool execution failed for {tool_name}: {e}")
            return {
                "success": False,
                "error": str(e),
                "tool_name": tool_name
            }
    
    async def create_calendar_event(self, summary: str, start_time: str, end_time: str, 
                                  description: str = None, attendees: list = None) -> Dict[str, Any]:
        """Convenience method to create calendar event"""
        args = {
            "summary": summary,
            "start": {
                "dateTime": start_time,
                "timeZone": "America/New_York"
            },
            "end": {
                "dateTime": end_time,  
                "timeZone": "America/New_York"
            }
        }
        
        if description:
            args["description"] = description
        if attendees:
            args["attendees"] = [{"email": email} for email in attendees]
        
        return await self.execute_tool("create_calendar_event", args)
    
    async def list_events(self, time_min: str = None, time_max: str = None, 
                         max_results: int = 10) -> Dict[str, Any]:
        """Convenience method to list calendar events"""
        args = {"maxResults": max_results}
        
        if time_min:
            args["timeMin"] = time_min
        if time_max:
            args["timeMax"] = time_max
        
        return await self.execute_tool("list_calendar_events", args)

# Example usage and testing
async def test_mcp_client():
    """Test the MCP client functionality"""
    async with CalendarMCPClient() as client:
        # Test tool discovery
        tools = client.get_available_tools()
        print("Available tools:")
        for tool in tools:
            print(f"- {tool['name']}: {tool['description']}")
        
        # Test creating an event
        tomorrow = datetime.now() + timedelta(days=1)
        start_time = tomorrow.replace(hour=14, minute=0, second=0, microsecond=0).isoformat()
        end_time = tomorrow.replace(hour=15, minute=0, second=0, microsecond=0).isoformat()
        
        result = await client.create_calendar_event(
            summary="Test Meeting via MCP",
            start_time=start_time,
            end_time=end_time,
            description="Created via MCP client"
        )
        
        print(f"Event creation result: {result}")
        
        # Test listing events
        events_result = await client.list_events(max_results=5)
        print(f"Recent events: {events_result}")

if __name__ == "__main__":
    asyncio.run(test_mcp_client())