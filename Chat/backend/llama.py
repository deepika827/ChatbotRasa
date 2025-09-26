from time import time
from flask import Flask, jsonify, request
import requests
import json
import os
from dotenv import load_dotenv
from googletrans import Translator

from mcp.client import MCPClient

mcp_client = MCPClient()


app = Flask(__name__)

# Load environment variables
load_dotenv()

OLLAMA_URL = os.getenv("OLLAMA_URL", "http://127.0.0.1:11434/api/generate")
# MCP_SERVICE_URL = os.getenv("MCP_SERVICE_URL", "http://localhost:8000")


def query_mongodb_via_mcp_service(collection: str, filter: dict = None, limit: int = 10):
    """
    Query a MongoDB collection via the MCP.
    Fetches all docs (limit 10).
    """
    try:
        response = mcp_client.query(
            database="mcp_database",
            collection=collection,
            method="find",
            params={"filter": {}, "limit": 10}
        )
        return response
    except Exception as e:
        return {"success": False, "error": f"Failed to query MCP service: {str(e)}"}

def get_conversation_history(username=None, search_text=None):
    """
    Get conversation history from the MCPClient.
    """
    try:
        query_filter = {}
        if username:
            query_filter["username"] = username
        if search_text:
            query_filter["text"] = {"$regex": search_text, "$options": "i"}

        response = mcp_client.query(
            database="mcp_database",
            collection="mcp_collection",
            method="find",
            params={"filter": query_filter, "limit": 20}
        )
        return response
    except Exception as e:
        return {"error": f"Failed to query conversation history via MCPClient: {str(e)}"}
    
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

def get_pdf_text(filename="BankingLaw.pdf"):
    """
    Fetch the extracted text of the uploaded PDF from MCP.
    """
    try:
        response = mcp_client.query(
            database="mcp_database",
            collection="pdf_texts",
            method="find_one",
            params={"filter": {"filename": filename}}
        )
        if not response or "result" not in response:
            print("No text found in database for the given file.")
            return None

        pdf_text = response["result"].get("text")
        if isinstance(pdf_text, list):
            return " ".join(pdf_text)
        return str(pdf_text)
    except Exception as e:
        print(f"Error fetching PDF text via MCP: {str(e)}")
        return None


def translation(text, src='ne', dest='en'):
    translator = Translator()
    result = translator.translate(text, src=src, dest=dest)
    return result.text

      
@app.route("/chat", methods=["POST"])
def chat():
    """
    Chat endpoint: takes user message, queries MCP collections,
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

    # Step 1: Query relevant collections via MCP
    employees_data = query_mongodb_via_mcp_service("employees")
    conversations_data = get_conversation_history() if "conversation" in user_message.lower() else query_mongodb_via_mcp_service("mcp_collection")

    # Step 2: Check relevance (same logic as before)
    has_relevant_data, analysis = analyze_database_relevance(user_message, employees_data, conversations_data)

    if not has_relevant_data:
        return jsonify({
            "success": True,
            "content": f"I don't have information about that in my database. {analysis}. Would you like to talk to a live agent?",
            "suggest_handoff": True,
            "reason": analysis,
            "query_type": "no_data_available"
        })


    # Step : Build enhanced Llama prompt


    prompt = f"""
            You are a professional database assistant. Answer questions directly and factually using only the provided data.

User question: "{user_message}"

Employee Database:
{json.dumps(employees_data, indent=2)}

Chat History Database:
{json.dumps(conversations_data, indent=2)}

PDF CONTENT (BankingLaw.pdf):
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
        if any(ind.lower() in answer.lower() for ind in no_data_indicators):
            return jsonify({
                "success": True,
                "content": "I apologize, I don't have information about that. Would you like to talk to a live agent?",
                "suggest_handoff": True,
                "reason": "Llama could not find relevant data",
                "query_type": "no_relevant_data"
            })

        return jsonify({
            "success": True,
            "content": answer.strip(),
            "query_type": "conversation_history" if "conversation" in user_message.lower() else "general",
            "db_raw": {
                "employees": employees_data,
                "conversations": conversations_data
            }
        })
    except Exception as e:
        return jsonify({"error": f"Ollama request failed: {str(e)}"}), 500


if __name__ == "__main__":
    app.run(debug=True, port=5002)