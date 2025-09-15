from flask import Flask, jsonify, request
import json
from dotenv import load_dotenv
import os
import requests
from pymongo import MongoClient
import datetime

app = Flask(__name__)

# Load environment variables
load_dotenv()
ollama_url = os.getenv("OLLAMA_URL")

# MongoDB setup with mock data
try:

    MONGODB_ATLAS_CLIENT_ID = os.getenv('MDB_MCP_API_CLIENT_ID')
    MONGODB_ATLAS_CLIENT_SECRET = os.getenv('MDB_MCP_API_CLIENT_SECRET')
    
    # Connect using MCP server
    client = MongoClient(
        "mongodb://localhost:27017/",
        authSource='admin',
        username=MONGODB_ATLAS_CLIENT_ID,
        password=MONGODB_ATLAS_CLIENT_SECRET)
        
    client = MongoClient("mongodb://localhost:27017/")
    db = client["employees"]

    # Initialize collections with mock data
    def init_mock_data():
        # Clear existing data
        db.employees.drop()
        db.messages.drop()
        db.company_info.drop()
        
        # Sample employees
        employees = [
            {"name": "Alice Johnson", "department": "HR", "position": "HR Manager", "email": "alice@company.com"},
            {"name": "Bob Smith", "department": "Engineering", "position": "Senior Developer", "email": "bob@company.com"},
            {"name": "Carol Davis", "department": "Engineering", "position": "DevOps Engineer", "email": "carol@company.com"},
            {"name": "David Wilson", "department": "HR", "position": "Recruiter", "email": "david@company.com"}
        ]
        db.employees.insert_many(employees)
        
        # # Sample messages
        # messages = [
        #     {"username": "user1", "sender": "user", "text": "Hello", "timestamp": datetime.datetime.now()},
        #     {"username": "user1", "sender": "bot", "text": "Hi there!", "timestamp": datetime.datetime.now()}
        # ]
        # db.messages.insert_many(messages)
        
        # # Company info
        # company_info = [
        #     {"type": "policy", "title": "Work from Home", "content": "Employees can work from home up to 3 days per week"},
        #     {"type": "benefit", "title": "Health Insurance", "content": "Full health coverage including dental and vision"},
        #     {"type": "contact", "title": "IT Support", "content": "Email: it-support@company.com, Phone: 555-0123"}
        # ]
        # db.company_info.insert_many(company_info)
        print("✅ Mock data initialized")

    # Initialize mock data on startup
    init_mock_data()
except Exception as e:
    print(f"❌ MongoDB connection failed: {str(e)}")
    db = None


def query_database(user_message):
    """Query MongoDB based on user intent with improved pattern matching"""
    try:
        user_message_lower = user_message.lower()
        
        # First check for specific employee names in the database
        all_employees = list(db.employees.find({}, {"_id": 0}))
        for employee in all_employees:
            if employee["name"].lower() in user_message_lower:
                # Return just this employee's data
                return {
                    "type": "employees",
                    "data": [employee],
                    "context": {
                        "query_type": "specific_employee",
                        "employee_name": employee["name"],
                        "total_results": 1
                    }
                }
        
        # If no specific employee found, check for department queries
        employee_patterns = [
            "employee", "staff", "who", "works", "people", "team", "department",
            "working", "employed", "members", "personnel", "workforce", "role"
        ]
        
        department_patterns = {
            "hr": ["hr", "human resources", "hiring", "recruitment", "personnel"],
            "engineering": ["engineering", "dev", "development", "technical", "software"]
        }
        
        # Employee queries with improved pattern matching
        if any(pattern in user_message_lower for pattern in employee_patterns):
            query = {}
            
            # Department specific queries
            for dept, patterns in department_patterns.items():
                if any(pattern in user_message_lower for pattern in patterns):
                    query["department"] = dept.upper()
                    break
            
            # Position specific queries
            if "manager" in user_message_lower:
                query["position"] = {"$regex": "Manager", "$options": "i"}
            
            results = list(db.employees.find(query, {"_id": 0}))
            context = {
                "query_type": "employee",
                "department": query.get("department", "any"),
                "position": query.get("position", "any"),
                "total_results": len(results)
            }
            return {"type": "employees", "data": results, "context": context}
        
        # Company info queries
        elif any(word in user_message_lower for word in ["policy", "benefit", "contact", "company", "info", "information"]):
            results = list(db.company_info.find({}, {"_id": 0}))
            return {"type": "company_info", "data": results}
        
        else:
            return {"type": "no_match", "data": None}
            
    except Exception as e:
        return {"type": "error", "data": f"Database query failed: {str(e)}"}

@app.route('/chat', methods=['POST'])
def chat():
    try:
        user_input = request.json
        if not user_input or "message" not in user_input:
            return jsonify({"error": "Missing 'message' in request"}), 400

        user_message = user_input['message']
        
        # Query database first
        db_response = query_database(user_message)
        
        # Create enhanced prompt for Llama with better context and instructions
        if db_response["type"] != "no_match" and db_response["data"]:
            context = db_response.get("context", {})
            prompt = f"""
You are an AI assistant that helps employees find information about the company and its people.

User question: "{user_message}"

Database results: {json.dumps(db_response["data"], indent=2)}

Instructions:
1. Provide a clear and concise response
2. Focus only on directly answering the question
3. Use natural, conversational language
4. Keep responses brief and to the point

Format your response as JSON:
{{
    "content": "your direct answer here"
}}

Important:
- Don't include introductory phrases like "Here are" or "I found"
- Don't add suggestions or follow-up questions
- Keep the response focused and concise
"""
        else:
            prompt = f"""
You are an AI assistant for a company. The user asked: "{user_message}"

While this doesn't match our database queries directly, provide a helpful response that:
1. Acknowledges their question
2. Explains what kind of information you can help with
3. Suggests relevant alternative questions they might want to ask

Format your response as JSON:
{{
    "type": "general_response",
    "content": "your helpful response here",
    "suggestions": ["suggested question 1", "suggested question 2"],
    "confidence": "medium"
}}

Keep the tone professional and helpful.
"""

        # Query Ollama
        llama_payload = {
            "model": "llama3.2",
            "prompt": prompt,
            "stream": False,
            "options": {
                "temperature": 0.7
            }
        }

        response = requests.post(ollama_url, json=llama_payload)
        if response.status_code != 200:
            return jsonify({"error": "Ollama API request failed", "status_code": response.status_code}), 500

        llama_data = response.json()
        llama_output = llama_data.get('response', '')

        # Try to parse JSON response from Llama
        try:
            # Clean up the response and extract JSON
            if '```json' in llama_output:
                llama_output = llama_output.split('```json')[1].split('```')[0]
            elif '```' in llama_output:
                llama_output = llama_output.split('```')[1].split('```')[0]
            
            parsed_response = json.loads(llama_output.strip())
            
            # Format the content based on database results
            if db_response["type"] == "employees" and db_response["data"]:
                # Find specific employee if name is mentioned
                employee_name = None
                user_message_lower = user_message.lower()
                for emp in db_response["data"]:
                    if emp["name"].lower() in user_message_lower:
                        employee_name = emp["name"]
                        content = f"{emp['name']} works as a {emp['position']} in the {emp['department']} department."
                        break
                
                # If no specific employee found, list all employees
                if not employee_name:
                    employees = db_response["data"]
                    content = "Here are the details:\n"
                    for emp in employees:
                        content += f"• {emp['name']} - {emp['position']}\n"
            else:
                # If it's a parsed response, extract just the content
                try:
                    if isinstance(parsed_response, str):
                        # Try to parse JSON string
                        parsed_json = json.loads(parsed_response)
                        content = parsed_json.get("content", "I'm here to help!")
                    else:
                        content = parsed_response.get("content", "I'm here to help!")
                except json.JSONDecodeError:
                    content = "I'm here to help!"

            # Simplified response with just the essential content
            response_data = {
                "success": True,
                "content": content.strip()  # Clean up any extra whitespace
            }
            
            return jsonify(response_data)
            
        except json.JSONDecodeError:
            # If JSON parsing fails, return the raw response
            return jsonify({
                "success": True,
                "response": llama_output,
                "type": "general_response",
                "db_data": db_response["data"] if db_response["type"] != "no_match" else None
            })

    except Exception as e:
        return jsonify({"error": f"Server error: {str(e)}"}), 500

if __name__ == "__main__":
    app.run(debug=True, port=5002)