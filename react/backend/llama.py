from flask import Flask, jsonify, request
import requests
import json
import os
from dotenv import load_dotenv

app = Flask(__name__)

# Load environment variables
load_dotenv()

OLLAMA_URL = os.getenv("OLLAMA_URL", "http://127.0.0.1:11434/api/generate")
MCP_SERVICE_URL = os.getenv("MCP_SERVICE_URL", "http://localhost:5003")

def query_mongodb_via_mcp_service(collection: str):
    """
    Query a MongoDB collection via the MCP service.
    Fetches all docs (limit 10).
    """
    try:
        response = requests.post(f"{MCP_SERVICE_URL}/mcp/query", json={
            "method": "find",
            "params": {
                "database": "mcp_database",
                "collection": collection,
                "filter": {},
                "limit": 10
            }
        })
        response.raise_for_status()
        return response.json()
    except Exception as e:
        return {"error": f"Failed to query MCP service: {str(e)}"}

def get_conversation_history(username=None, search_text=None):
    """
    Get conversation history from the MCP service.
    """
    try:
        if search_text:
            # Search conversations
            response = requests.post(f"{MCP_SERVICE_URL}/mcp/conversations/search", json={
                "search_text": search_text,
                "username": username,
                "limit": 20
            })
        else:
            # Get all conversations
            params = {"limit": 50}
            if username:
                params["username"] = username
            response = requests.get(f"{MCP_SERVICE_URL}/mcp/conversations", params=params)
        
        response.raise_for_status()
        return response.json()
    except Exception as e:
        return {"error": f"Failed to query conversation history: {str(e)}"}

def detect_conversation_query(user_message):
    """
    Detect if the user is asking about conversation history.
    """
    conversation_keywords = [
        "conversation", "chat", "previous", "history", "talked", "discussed", 
        "asked", "said", "mentioned", "conversation history", "chat history",
        "what did", "who asked", "when did", "before", "earlier"
    ]
    
    user_lower = user_message.lower()
    return any(keyword in user_lower for keyword in conversation_keywords)

@app.route("/chat", methods=["POST"])
def chat():
    """
    Chat endpoint: takes user message, queries both collections,
    and enriches with Llama.
    """
    user_input = request.json
    if not user_input or "message" not in user_input:
        return jsonify({"error": "Missing message in request"}), 400

    user_message = user_input["message"]

    # Step 1: Check if this is a conversation history query
    is_conversation_query = detect_conversation_query(user_message)
    
    # Step 2: Query relevant collections
    employees_data = query_mongodb_via_mcp_service("employees")
    
    if is_conversation_query:
        # Get conversation history
        conversations_data = get_conversation_history()
    else:
        # Get general mcp_collection data
        conversations_data = query_mongodb_via_mcp_service("mcp_collection")

    # Step 3: Build enhanced Llama prompt
    if is_conversation_query:
        prompt = f"""
You are an AI assistant that can answer questions about conversation history and company data.

User question: "{user_message}"

CONVERSATION HISTORY DATABASE:
{json.dumps(conversations_data, indent=2)}

EMPLOYEE DATABASE:
{json.dumps(employees_data, indent=2)}

Instructions:
- The user is asking about conversation history
- Use the CONVERSATION HISTORY DATABASE to answer questions about previous conversations
- Look for patterns like: who asked what, when conversations happened, what topics were discussed
- If the user asks about specific people or topics from conversations, search through the conversation data
- Be specific about timestamps, usernames, and conversation content when available
- If the conversation history is empty or does not contain relevant information, say so clearly
- Answer in a professional and helpful manner
"""
    else:
        prompt = f"""
You are an AI assistant that answers user questions using company data.

User question: "{user_message}"

IMPORTANT: Use the following database information to answer the user question:

Employee Database:
{json.dumps(employees_data, indent=2)}

Chat History Database:
{json.dumps(conversations_data, indent=2)}

Instructions:
- If the user asks about employees, use the Employee Database above
- Use ONLY the information provided in the databases above
- If the database contains relevant information, use it to answer the question
- Be specific and include names, roles, and departments when available
- If no relevant data is found, say so clearly
- Answer in a professional and helpful manner
"""

    llama_payload = {
        "model": "llama3.2",
        "prompt": prompt,
        "stream": False,
        "options": {"temperature": 0.7}
    }

    try:
        response = requests.post(OLLAMA_URL, json=llama_payload)
        response.raise_for_status()
        llama_data = response.json()
        answer = llama_data.get("response", "Sorry, I could not generate a response.")

        return jsonify({
            "success": True,
            "content": answer.strip(),
            "query_type": "conversation_history" if is_conversation_query else "general",
            "db_raw": {
                "employees": employees_data,
                "conversations": conversations_data
            }
        })
    except Exception as e:
        return jsonify({"error": f"Ollama request failed: {str(e)}"}), 500

if __name__ == "__main__":
    app.run(debug=True, port=5002)
