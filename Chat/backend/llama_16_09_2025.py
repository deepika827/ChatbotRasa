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

def analyze_database_relevance(user_message, employees_data, conversations_data):
    """
    Analyze if the database contains relevant information for the user's query.
    Returns: (has_relevant_data: bool, analysis: str)
    """
    user_lower = user_message.lower()
    
    # Check if there's any data at all
    has_employee_data = (employees_data.get("success") and 
                        employees_data.get("data", {}).get("result") and 
                        len(employees_data["data"]["result"]) > 0)
    
    has_conversation_data = (conversations_data.get("success") and 
                           ((conversations_data.get("conversations") and len(conversations_data["conversations"]) > 0) or
                            (conversations_data.get("data", {}).get("result") and len(conversations_data["data"]["result"]) > 0)))
    
    # If no data at all, definitely no relevance
    if not has_employee_data and not has_conversation_data:
        return False, "No data available in the database"
    
    # Define common business/employee keywords
    business_keywords = [
        "employee", "staff", "worker", "team", "department", "manager", "role", 
        "position", "job", "work", "office", "company", "organization", "salary",
        "name", "contact", "phone", "email", "address", "hire", "employment"
    ]
    
    # Check if query seems to be about business/employee information
    is_business_query = any(keyword in user_lower for keyword in business_keywords)
    
    if is_business_query and not has_employee_data:
        return False, "Query seems to be about employees/business but no employee data available"
    
    # For conversation queries, check if we have conversation data
    if detect_conversation_query(user_message) and not has_conversation_data:
        return False, "Query about conversation history but no conversation data available"
    
    # If we have some data, let Llama try to answer
    return True, "Database contains some relevant data"

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

    # Step 3: Check if database has relevant information
    has_relevant_data, analysis = analyze_database_relevance(user_message, employees_data, conversations_data)
    
    # If no relevant data found, suggest human agent
    if not has_relevant_data:
        return jsonify({
            "success": True,
            "content": f"I don't have information about that in my database. {analysis}. Would you like to talk to a live agent who can help you better?",
            "suggest_handoff": True,  # Signal that handoff should be suggested
            "reason": analysis,
            "query_type": "no_data_available"
        })

    # Step 4: Build enhanced Llama prompt
    if is_conversation_query:
        prompt = f"""
You are a database query assistant for conversation history. You can ONLY answer using data from the provided databases.

User question: "{user_message}"

CONVERSATION HISTORY DATABASE:
{json.dumps(conversations_data, indent=2)}

EMPLOYEE DATABASE:
{json.dumps(employees_data, indent=2)}

CRITICAL RULES:
1. You can ONLY use information from these two databases above
2. Do NOT use external knowledge or general information
3. If the databases do not contain the exact information requested, you MUST respond with exactly: "NO_RELEVANT_DATA_FOUND"
4. Do NOT provide helpful suggestions or general advice
5. ONLY search the conversation history and employee data provided

Examples:
- Question about past conversations in the database → Answer using conversation data
- Question about employees mentioned in conversations → Use both databases
- Question about topics not in the conversation history → Respond: "NO_RELEVANT_DATA_FOUND"
"""
    else:
        prompt = f"""
You are a database query assistant. You can ONLY answer using data from the provided databases.

User question: "{user_message}"

Employee Database:
{json.dumps(employees_data, indent=2)}

Chat History Database:
{json.dumps(conversations_data, indent=2)}

CRITICAL RULES:
1. You can ONLY use information from these two databases above
2. Do NOT use external knowledge, general information, or suggestions
3. If the databases do not contain the exact information requested, you MUST respond with exactly: "NO_RELEVANT_DATA_FOUND"
4. Do NOT provide helpful suggestions, external resources, or general advice
5. Do NOT say "I recommend checking..." or "you can find this information..."
6. ONLY use the database content provided above

Examples:
- Question about employees in the database → Answer using employee data
- Question about conversations in the database → Answer using chat history  
- Question about weather, politics, cooking, etc. → Respond: "NO_RELEVANT_DATA_FOUND"
- Question about people not in employee database → Respond: "NO_RELEVANT_DATA_FOUND"
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

        # Check if Llama couldn't find relevant data (multiple detection methods)
        no_data_indicators = [
            "NO_RELEVANT_DATA_FOUND",
            "do not have any information about",
            "does not contain information about",
            "database does not include",
            "not included in the database",
            "database only contains information about employees",
            "checking a reliable news source",
            "official government website",
            "I suggest checking",
            "I recommend"
        ]
        
        # Check if any indicator of insufficient data is present
        answer_lower = answer.lower()
        has_insufficient_data = any(indicator.lower() in answer_lower for indicator in no_data_indicators)
        
        print(f"🔍 DEBUG: answer_lower = {answer_lower[:100]}...")
        print(f"🔍 DEBUG: has_insufficient_data = {has_insufficient_data}")
        
        if has_insufficient_data or "NO_RELEVANT_DATA_FOUND" in answer:
            print("🎯 TRIGGERING HANDOFF SUGGESTION!")
            return jsonify({
                "success": True,
                "content": "I don't have specific information about that in my database. Would you like to talk to a live agent who can help you with more detailed information?",
                "suggest_handoff": True,
                "reason": "Llama could not find relevant data in database",
                "query_type": "no_relevant_data"
            })

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
