"""Module for interacting with AlphaESS via MCP using stdio protocol."""

import atexit
import json
import subprocess
import uuid
from pathlib import Path
from typing import Any, Dict, Optional

import structlog

logger = structlog.get_logger()

class MCPClient:
    """MCP client that communicates with FastMCP server over stdio."""
    
    def __init__(self, mcp_config_path: str = "mcp.json"):
        self.mcp_config_path = Path(mcp_config_path)
        self.server_process: Optional[subprocess.Popen] = None
        self.tools: list = []
        self._load_config()
        
    def _load_config(self):
        """Load MCP server configuration."""
        if not self.mcp_config_path.exists():
            raise FileNotFoundError(f"MCP config file not found: {self.mcp_config_path}")
            
        with open(self.mcp_config_path) as f:
            self.config = json.load(f)
            
        if "alpha-ess-mcp" not in self.config.get("mcpServers", {}):
            raise ValueError("alpha-ess-mcp server not found in mcp.json")
            
        self.server_config = self.config["mcpServers"]["alpha-ess-mcp"]
        
    def start_server(self):
        """Start the MCP server if not already running."""
        if self.server_process and self.server_process.poll() is None:
            logger.info("MCP server is already running")
            return
            
        logger.info("Starting MCP server...")
        
        # Build command from config
        command = [self.server_config["command"]] + self.server_config["args"]
        env = self.server_config.get("env", {})
        
        # Start the server process with stdio pipes
        self.server_process = subprocess.Popen(
            command,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            env={**subprocess.os.environ, **env},
            text=True,
            bufsize=0  # Unbuffered
        )
        
        # Register cleanup function
        atexit.register(self.stop_server)
        
        # Initialize the MCP session
        self._initialize_session()
        logger.info("MCP server is ready")
        
    def _initialize_session(self):
        """Initialize MCP session with handshake."""
        # Send initialize request
        init_request = {
            "jsonrpc": "2.0",
            "id": str(uuid.uuid4()),
            "method": "initialize",
            "params": {
                "protocolVersion": "2024-11-05",
                "capabilities": {
                    "tools": {}
                },
                "clientInfo": {
                    "name": "pi-power-butler",
                    "version": "1.0.0"
                }
            }
        }
        
        response = self._send_request(init_request)
        if not response.get("result"):
            raise RuntimeError(f"Failed to initialize MCP session: {response}")

        # Store server-provided tools
        self.tools = response.get("result", {}).get("capabilities", {}).get("tools", [])
        logger.info(f"MCP server provided {len(self.tools)} tools.")
            
        # Send initialized notification
        initialized_notification = {
            "jsonrpc": "2.0",
            "method": "notifications/initialized"
        }
        
        self._send_notification(initialized_notification)
        
    def _send_request(self, request: Dict[str, Any]) -> Dict[str, Any]:
        """Send a JSON-RPC request and wait for response."""
        if not self.server_process:
            raise RuntimeError("MCP server not started")
            
        # Send request
        request_json = json.dumps(request) + "\n"
        self.server_process.stdin.write(request_json)
        self.server_process.stdin.flush()
        
        # Read response
        response_line = self.server_process.stdout.readline()
        if not response_line:
            raise RuntimeError("No response from MCP server")
            
        return json.loads(response_line.strip())
        
    def _send_notification(self, notification: Dict[str, Any]):
        """Send a JSON-RPC notification (no response expected)."""
        if not self.server_process:
            raise RuntimeError("MCP server not started")
            
        notification_json = json.dumps(notification) + "\n"
        self.server_process.stdin.write(notification_json)
        self.server_process.stdin.flush()
        
    def call_tool(self, tool_name: str, arguments: Dict[str, Any]) -> Dict[str, Any]:
        """Call an MCP tool."""
        if not self.server_process:
            self.start_server()
            
        # Remove mcp_alpha-ess-mcp_ prefix if present
        clean_tool_name = tool_name
        if tool_name.startswith("mcp_alpha-ess-mcp_"):
            clean_tool_name = tool_name[len("mcp_alpha-ess-mcp_"):]
        
        request = {
            "jsonrpc": "2.0",
            "id": str(uuid.uuid4()),
            "method": "tools/call",
            "params": {
                "name": clean_tool_name,
                "arguments": arguments
            }
        }
        
        try:
            response = self._send_request(request)
            
            if "error" in response:
                raise RuntimeError(f"MCP tool error: {response['error']}")
                
            result = response.get("result", {})
            return result.get("content", [{}])[0] if result.get("content") else {}
            
        except Exception as e:
            logger.error(f"MCP tool call failed: {e}")
            raise RuntimeError(f"MCP tool call failed: {e}") from e
        
    def stop_server(self):
        """Stop the MCP server."""
        if self.server_process:
            logger.info("Stopping MCP server...")
            self.server_process.terminate()
            try:
                self.server_process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                logger.warning("MCP server didn't stop gracefully, killing...")
                self.server_process.kill()
            self.server_process = None
            
    def is_running(self) -> bool:
        """Check if the server is running."""
        return self.server_process is not None and self.server_process.poll() is None


# Global client instance
_mcp_client: Optional[MCPClient] = None

def get_mcp_client() -> MCPClient:
    """Get or create the global MCP client."""
    global _mcp_client
    if _mcp_client is None:
        _mcp_client = MCPClient()
    return _mcp_client


def get_mcp_tools() -> list:
    """Get the list of tools from the MCP client."""
    client = get_mcp_client()
    if not client.is_running():
        client.start_server()
    return client.tools


def execute_mcp_tool(name: str, parameters: dict) -> dict:
    """Execute an MCP tool call against the AlphaESS server.

    Args:
        name: The name of the MCP tool (e.g., 'mcp_alpha-ess-mcp_get_last_power_data').
        parameters: Dictionary of parameters for the tool.

    Returns:
        The JSON response from the server.
    """
    client = get_mcp_client()
    return client.call_tool(name, parameters)
