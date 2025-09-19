from flask import Flask, jsonify, request
import requests
import json
import os
from dotenv import load_dotenv
from pymongo import MongoClient
from googletrans import Translator
from googletrans import LANGUAGES

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

def get_pdf_text():
    """
    Fetch the extracted text of the uploaded PDF from the database.
    """
    try:
        client = MongoClient("mongodb://localhost:27017/")
        db = client["mcp_database"]
        doc = db["pdf_texts"].find_one({"filename": "MunaMadan.pdf"})
        return doc["text"] if doc and "text" in doc else ""
    except Exception as e:
        print(f"Error fetching PDF text: {str(e)}")
        return ""

def translation(text, src='ne', dest='en'):
    translator = Translator()
    result = translator.translate(text, src=src, dest=dest)
    return result.text

      
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

    # Fetch PDF text (limit to first 3000 chars for context window)
    pdf_text = get_pdf_text()
    pdf_context = pdf_text[:3000] if pdf_text else None

    # Translate PDF context to English
    if pdf_context:
        pdf_context = translation(pdf_context, src='ne', dest='en')


    # Check for greetings first
    greeting_keywords = [
        "hi", "hello", "hey", "good morning", "good afternoon", "good evening",
        "greetings", "howdy", "hiya", "what's up", "sup"
    ]
    
    user_lower = user_message.lower().strip()
    is_greeting = any(greeting in user_lower for greeting in greeting_keywords) or user_lower in ["hi", "hello", "hey"]
    
    if is_greeting:
        return jsonify({
            "success": True,
            "content": "Hello! How can I assist you today?",
            "query_type": "greeting"
        })

    # Step 1: Check if this is a conversation history query
    is_conversation_query = detect_conversation_query(user_message)
    
    # Step 2: Query relevant collections
    employees_data = query_mongodb_via_mcp_service("employees")
    # pdf_files_data = query_mongodb_via_mcp_service("fs.files")
    
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
You are a professional database assistant. Answer questions directly and factually using only the provided data.

User question: "{user_message}"


CONVERSATION HISTORY DATABASE:
{json.dumps(conversations_data, indent=2)}

EMPLOYEE DATABASE:
{json.dumps(employees_data, indent=2)}

PDF CONTENT (MunaMadan.pdf):
{pdf_context if pdf_context else '[No PDF content available]'}


INSTRUCTIONS:
1. Answer the question directly and factually using ONLY the data provided above
2. Do NOT make assumptions about what the user wants to do
3. Do NOT include raw database entries, IDs, or technical details in your response
4. Be professional and concise
5. If no relevant data exists, respond with exactly: "NO_RELEVANT_DATA_FOUND"
6. Do NOT use external knowledge - only the provided databases
7. Do NOT add unnecessary conversational elements or assumptions

Example good responses:
- "The HR Manager is Alice Johnson."
- "John Smith works in the Engineering department as a Software Developer."
- "There are 3 employees in the Marketing department: Sarah, Mike, and Lisa."
- "According to the PDF, ... (summarize relevant PDF info)"
"""
    else:
        prompt = f"""
You are a professional database assistant. Answer questions directly and factually using only the provided data.

User question: "{user_message}"

Employee Database:
{json.dumps(employees_data, indent=2)}

Chat History Database:
{json.dumps(conversations_data, indent=2)}

PDF CONTENT (MunaMadan.pdf):
{pdf_context if pdf_context else '[No PDF content available]'}

INSTRUCTIONS:
1. Answer the question directly and factually using ONLY the data provided above
2. Do NOT make assumptions about what the user wants to do
3. Do NOT include raw database entries, IDs, or technical details in your response
4. Be professional and concise
5. For questions about employees/company that have no data: respond with exactly "NO_RELEVANT_DATA_FOUND"
6. For questions about anything unrelated to employees/company: respond with exactly "NO_RELEVANT_DATA_FOUND"
7. Do NOT use external knowledge - only the provided databases
8. Do NOT provide suggestions about external sources or websites
9. Do NOT add unnecessary conversational elements or assumptions

CRITICAL: If the user asks about presidents, politics, weather, cooking, shopping, flights, or any general knowledge questions, you MUST respond with exactly: "NO_RELEVANT_DATA_FOUND" - do not explain or elaborate.

Example good responses:
- "The HR Manager is Alice Johnson."
- "John Smith works in the Engineering department as a Software Developer."
- "There are 3 employees in the Marketing department: Sarah, Mike, and Lisa."

Example irrelevant questions that should return "NO_RELEVANT_DATA_FOUND":
- Flight booking, travel reservations
- Weather information
- Cooking recipes
- Shopping recommendations
- General knowledge questions
- Technical support for non-company systems
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
            "don't have any information about",
            "do not have any relevant data",
            "don't have any relevant data",
            "does not contain information about",
            "database does not include",
            "not included in the database",
            "database only contains information about employees",
            "checking a reliable news source",
            "official government website",
            "I suggest checking",
            "I recommend",
            "I'm not able to",
            "I cannot",
            "I can't",
            "not able to",
            "unable to",
            "don't have the ability",
            "outside of my capabilities",
            "beyond my scope",
            "no relevant data",
            "no information about",
            "not in my database",
            "not available in my database"
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
                "content": "I apologize, but I don't have information about that in my database. Would you like to talk to a live agent who can help you with more detailed information?",
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
