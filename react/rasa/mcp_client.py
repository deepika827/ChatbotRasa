import asyncio
import websockets
import json
import os
from typing import Dict, Any, Optional

class MCPClient:
    def __init__(self, server_url: str, api_key: str = None, api_secret: str = None):
        self.server_url = server_url
        self.api_key = api_key
        self.api_secret = api_secret
        self.websocket = None
        self.request_id = 1

    async def connect(self):
        """Connect to the MCP server"""
        try:
            # Try different authentication methods
            headers = {}
            if self.api_key and self.api_secret:
                headers['Authorization'] = f'Bearer {self.api_key}:{self.api_secret}'

            self.websocket = await websockets.connect(
                self.server_url,
                extra_headers=headers
            )
            print("✅ Connected to MCP server")
            return True
        except Exception as e:
            print(f"❌ Failed to connect to MCP server: {e}")
            return False

    async def disconnect(self):
        """Disconnect from the MCP server"""
        if self.websocket:
            await self.websocket.close()
            self.websocket = None

    async def query(self, method: str, params: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Send a query to the MCP server"""
        if not self.websocket:
            print("❌ Not connected to MCP server")
            return None

        try:
            request = {
                "jsonrpc": "2.0",
                "id": self.request_id,
                "method": method,
                "params": params
            }

            self.request_id += 1

            await self.websocket.send(json.dumps(request))
            print(f"📤 Sent: {json.dumps(request, indent=2)}")

            response = await self.websocket.recv()
            result = json.loads(response)
            print(f"📥 Received: {json.dumps(result, indent=2)}")

            return result

        except Exception as e:
            print(f"❌ Query failed: {e}")
            return None

# Example usage
async def test_mcp_connection():
    client = MCPClient(
        server_url="ws://localhost:3000",
        api_key="mdb_sa_id_68baeeb922d3970b63bba9e7",
        api_secret="mdb_sa_sk_VneO3QlphelgmBIm4oULVYiZOx5lo8ObPFpVHNQF"
    )

    if await client.connect():
        # Test find query
        result = await client.query("find", {
            "database": "mcp_database",
            "collection": "employees",
            "filter": {},
            "limit": 5
        })

        if result:
            print("✅ Query successful!")
            print(f"Result: {result}")
        else:
            print("❌ Query failed")

        await client.disconnect()
    else:
        print("❌ Could not connect to MCP server")

if __name__ == "__main__":
    asyncio.run(test_mcp_connection())
