from flask import Flask, request, jsonify
from flask_cors import CORS
import json
import os
from pymongo import MongoClient
from bson import ObjectId

app = Flask(__name__)
CORS(app)

# Direct MongoDB connection
# For Docker MongoDB:
# client = MongoClient("mongodb://mongodb:27017/")

# For MongoDB Atlas (replace with your Atlas connection string):
# client = MongoClient("your_atlas_connection_string_here")

# For local MongoDB (if running outside Docker):
client = MongoClient("mongodb://localhost:27017/")
db = client["mcp_database"]

def serialize_mongo_doc(doc):
    """Convert MongoDB document to JSON serializable format"""
    if isinstance(doc, dict):
        for key, value in doc.items():
            if isinstance(value, ObjectId):
                doc[key] = str(value)
            elif isinstance(value, dict):
                doc[key] = serialize_mongo_doc(value)
            elif isinstance(value, list):
                doc[key] = [serialize_mongo_doc(item) if isinstance(item, dict) else item for item in value]
    return doc

@app.route('/mcp/query', methods=['POST'])
def mcp_query():
    """Endpoint to query MongoDB directly"""
    try:
        data = request.get_json()
        method = data.get('method', 'find')
        params = data.get('params', {})
        
        collection_name = params.get('collection', 'employees')
        database_name = params.get('database', 'mcp_database')
        
        # Use the specified database
        target_db = client[database_name]
        collection = target_db[collection_name]
        
        if method == 'find':
            filter_query = params.get('filter', {})
            limit = params.get('limit', 20)
            
            cursor = collection.find(filter_query).limit(limit)
            results = [serialize_mongo_doc(doc) for doc in cursor]
            
            return jsonify({
                "success": True, 
                "data": {"result": results}
            })
            
        elif method == 'insertMany':
            documents = params.get('documents', [])
            result = collection.insert_many(documents)
            
            return jsonify({
                "success": True,
                "data": {
                    "acknowledged": result.acknowledged,
                    "inserted_count": len(result.inserted_ids)
                }
            })
        
        else:
            return jsonify({"success": False, "error": f"Unsupported method: {method}"}), 400
    
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500

@app.route('/mcp/employees', methods=['GET'])
def get_employees():
    """Get all employees from MongoDB"""
    try:
        collection = db["employees"]
        cursor = collection.find({}).limit(20)
        employees = [serialize_mongo_doc(doc) for doc in cursor]
        
        return jsonify({"success": True, "employees": employees})
    
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500

@app.route('/mcp/conversations', methods=['GET'])
def get_conversations():
    """Get conversation history from MongoDB"""
    try:
        collection = db["mcp_collection"]
        
        # Get query parameters
        username = request.args.get('username')
        limit = int(request.args.get('limit', 50))
        
        # Build query
        query = {}
        if username:
            query['username'] = username
            
        # Find conversations, sorted by timestamp (newest first)
        cursor = collection.find(query).sort("timestamp", -1).limit(limit)
        conversations = [serialize_mongo_doc(doc) for doc in cursor]
        
        # Convert timestamp to string for JSON serialization
        for conv in conversations:
            if 'timestamp' in conv:
                conv['timestamp'] = conv['timestamp'].isoformat()
        
        return jsonify({
            "success": True,
            "conversations": conversations,
            "count": len(conversations)
        })
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500

@app.route('/mcp/conversations/search', methods=['POST'])
def search_conversations():
    """Search conversation history"""
    try:
        data = request.get_json()
        search_text = data.get('search_text', '')
        username = data.get('username')
        limit = int(data.get('limit', 20))
        
        collection = db["mcp_collection"]
        
        # Build search query
        query = {}
        if username:
            query['username'] = username
            
        if search_text:
            query['text'] = {"$regex": search_text, "$options": "i"}  # Case-insensitive search
        
        # Find matching conversations
        cursor = collection.find(query).sort("timestamp", -1).limit(limit)
        conversations = [serialize_mongo_doc(doc) for doc in cursor]
        
        # Convert timestamp to string for JSON serialization
        for conv in conversations:
            if 'timestamp' in conv:
                conv['timestamp'] = conv['timestamp'].isoformat()
        
        return jsonify({
            "success": True,
            "conversations": conversations,
            "count": len(conversations),
            "search_text": search_text
        })
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500

@app.route('/health', methods=['GET'])
def health_check():
    """Health check endpoint"""
    try:
        # Test MongoDB connection
        client.admin.command('ping')
        return jsonify({"status": "healthy", "service": "MCP Service", "mongodb": "connected"})
    except Exception as e:
        return jsonify({"status": "unhealthy", "service": "MCP Service", "error": str(e)}), 500

if __name__ == '__main__':
    print("🚀 Starting MCP Service on port 5003...")
    print("📡 Connecting to MongoDB at mongodb://mongodb:27017/")
    app.run(host='0.0.0.0', port=5003, debug=True)
