import requests
import json
from typing import Dict, Any, Optional

class MCPHTTPClient:
    def __init__(self, base_url: str = "http://localhost:5003"):
        self.base_url = base_url.rstrip('/')
        self.session = requests.Session()

    def test_connection(self) -> bool:
        """Test if the MCP service is running"""
        try:
            response = self.session.get(f"{self.base_url}/health", timeout=5)
            if response.status_code == 200:
                result = response.json()
                print(f"✅ MCP Service is healthy: {result}")
                return True
            else:
                print(f"❌ MCP Service returned status {response.status_code}: {response.text}")
                return False
        except requests.exceptions.RequestException as e:
            print(f"❌ Failed to connect to MCP service: {e}")
            return False

    def query_mongodb(self, method: str, params: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Query MongoDB through the MCP service"""
        try:
            payload = {
                "method": method,
                "params": params
            }
            
            response = self.session.post(
                f"{self.base_url}/mcp/query",
                json=payload,
                timeout=10
            )
            
            print(f"📤 Request: {json.dumps(payload, indent=2)}")
            print(f"📥 Response Status: {response.status_code}")
            
            if response.status_code == 200:
                result = response.json()
                print(f"📥 Response: {json.dumps(result, indent=2)}")
                return result
            else:
                print(f"❌ Request failed with status {response.status_code}: {response.text}")
                return None
                
        except requests.exceptions.RequestException as e:
            print(f"❌ Query failed: {e}")
            return None

    def get_employees(self) -> Optional[Dict[str, Any]]:
        """Get employees directly"""
        try:
            response = self.session.get(f"{self.base_url}/mcp/employees", timeout=10)
            
            if response.status_code == 200:
                result = response.json()
                print(f"📥 Employees: {json.dumps(result, indent=2)}")
                return result
            else:
                print(f"❌ Failed to get employees: {response.status_code} - {response.text}")
                return None
                
        except requests.exceptions.RequestException as e:
            print(f"❌ Failed to get employees: {e}")
            return None

    def get_conversations(self, username: str = None, limit: int = 10) -> Optional[Dict[str, Any]]:
        """Get conversation history"""
        try:
            params = {"limit": limit}
            if username:
                params["username"] = username
                
            response = self.session.get(
                f"{self.base_url}/mcp/conversations",
                params=params,
                timeout=10
            )
            
            if response.status_code == 200:
                result = response.json()
                print(f"📥 Conversations: {json.dumps(result, indent=2)}")
                return result
            else:
                print(f"❌ Failed to get conversations: {response.status_code} - {response.text}")
                return None
                
        except requests.exceptions.RequestException as e:
            print(f"❌ Failed to get conversations: {e}")
            return None

def test_mcp_setup():
    """Test the complete MCP setup"""
    print("🧪 Testing MongoDB MCP Setup...")
    print("=" * 50)
    
    client = MCPHTTPClient()
    
    # 1. Test service health
    print("\n1. Testing MCP Service Health...")
    if not client.test_connection():
        print("❌ MCP Service is not running. Please start the service first.")
        return False
    
    # 2. Test MongoDB query through MCP
    print("\n2. Testing MongoDB Query...")
    result = client.query_mongodb("find", {
        "database": "mcp_database",
        "collection": "employees",
        "filter": {},
        "limit": 5
    })
    
    if result and result.get("success"):
        print("✅ MongoDB query successful!")
        print(f"Found {len(result.get('data', {}).get('result', []))} records")
    else:
        print("❌ MongoDB query failed")
    
    # 3. Test employees endpoint
    print("\n3. Testing Employees Endpoint...")
    employees = client.get_employees()
    
    if employees and employees.get("success"):
        print("✅ Employees endpoint working!")
        print(f"Found {len(employees.get('employees', []))} employees")
    else:
        print("❌ Employees endpoint failed")
    
    # 4. Test conversations endpoint
    print("\n4. Testing Conversations Endpoint...")
    conversations = client.get_conversations(limit=5)
    
    if conversations and conversations.get("success"):
        print("✅ Conversations endpoint working!")
        print(f"Found {conversations.get('count', 0)} conversations")
    else:
        print("❌ Conversations endpoint failed")
    
    print("\n" + "=" * 50)
    print("🏁 MCP Setup Test Complete!")
    return True

if __name__ == "__main__":
    test_mcp_setup()