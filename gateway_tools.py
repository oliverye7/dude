import asyncio
import json
from typing import Dict, Any, List
import httpx


class MCPGatewayTools:
    """
    Simple MCP Gateway tool access
    Reference https://github.com/oliverye7/mcp-gateway for details on how to use the MCP Gateway.
    """

    def __init__(self, gateway_url: str = "http://localhost:8080"):
        self.gateway_url = gateway_url
        self.session_id = None

    async def create_session(self):
        """Create gateway session"""
        async with httpx.AsyncClient() as client:
            response = await client.post(f"{self.gateway_url}/sessions/create")
            result = response.json()
            if result.get("success"):
                self.session_id = result["session_id"]
                return f"Created gateway session: {self.session_id}"
            else:
                return f"Failed to create session: {result}"

    async def search_tools(self, query: str) -> str:
        """Search for tools"""
        if not self.session_id:
            return "No gateway session - call create_session first"

        async with httpx.AsyncClient(timeout=30.0) as client:
            headers = {"X-Session-ID": self.session_id}
            response = await client.post(
                f"{self.gateway_url}/mcp/search",
                json={"query": query},
                headers=headers
            )
            result = response.json()

            if "result" in result:
                if isinstance(result["result"], list):
                    tools = result["result"]
                else:
                    tools = []

                if tools:
                    # Return the full tool specifications as JSON string
                    # The gateway returns complete tool specs with descriptions and input schemas
                    return json.dumps(tools)
                else:
                    return f"No tools found for query: {query}"
            else:
                return f"Search failed: {result}"

    async def execute_tool(self, tool_name: str, **args) -> str:
        """Execute a tool"""
        if not self.session_id:
            return "No gateway session - call create_session first"

        async with httpx.AsyncClient() as client:
            headers = {"X-Session-ID": self.session_id}
            response = await client.post(
                f"{self.gateway_url}/mcp/execute",
                json={"tool_name": tool_name, "args": args},
                headers=headers,
                timeout=60.0
            )
            result = response.json()

            if "result" in result:
                if isinstance(result["result"], str):
                    try:
                        parsed = json.loads(result["result"])
                        return str(parsed.get("content", parsed))
                    except json.JSONDecodeError:
                        return result["result"]
                else:
                    return str(result["result"])
            else:
                return f"Tool execution failed: {result}"

    async def list_tools(self) -> str:
        """List all available tools"""
        if not self.session_id:
            return "No gateway session - call create_session first"

        async with httpx.AsyncClient() as client:
            headers = {"X-Session-ID": self.session_id}
            response = await client.get(
                f"{self.gateway_url}/mcp/tools",
                headers=headers
            )
            result = response.json()
            tools = result.get("tools", [])

            if tools:
                tool_list = []
                for tool in tools:
                    name = tool.get("name", "Unknown")
                    desc = tool.get("description", "No description")
                    tool_list.append(f"- {name}: {desc}")
                return f"Available tools ({len(tools)}):\n" + "\n".join(tool_list)
            else:
                return "No tools available"
