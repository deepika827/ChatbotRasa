import datetime
import time
from flask import Flask, request, jsonify
import requests
from flask_socketio import SocketIO, send, join_room, leave_room, emit
from flask_cors import CORS
from mcp.client import MCPClient



mcp_client = MCPClient()

handoff_pairs = {}
RASA_API_URL = "http://localhost:5005/webhooks/rest/webhook"

app= Flask(__name__)

socketio = SocketIO(app, cors_allowed_origins="*", async_mode="eventlet",ping_interval=30,  
    ping_timeout=120  ) ## allow react frontend
CORS(app)

def store_message_mcp(username, sender, text):
    """Store a chat message using MCP service"""
    try:
        mcp_client.query(
            database="mcp_database",
            collection="mcp_collection",
            method="insert_one",
            params={
                "document": {
                    "username": username,
                    "sender": "user",
                    "text": text,
                    "timestamp": datetime.datetime.utcnow()
                }
            }
        )
        print("✅ User message stored via MCP")
    except Exception as e:
        print("Error storing message via MCP:", e)

# def get_conversation_history_mcp(username=None, limit=50):
#     """Fetch conversation history via MCP service"""
#     payload = {
#         "method": "find",
#         "params": {
#             "database": "mcp_database",
#             "collection": "mcp_collection",
#             "filter": {"username": username} if username else {},
#             "limit": limit
#         }
#     }
#     try:
#         response = requests.post(f"{MCP_SERVICE_URL}/mcp/query", json=payload)
#         response.raise_for_status()
#         return response.json().get("result", [])
#     except Exception as e:
#         print(f"Error fetching conversation via MCP: {e}")
#         return []
    
# --- Socket handlers ---

# CSR room nam
CSR_ROOM = "csr_room_all"

@socketio.on("connect")
def handle_connect():
    print("🔌 A client connected *******************************")
    print(f"Async mode: {socketio.async_mode}")
    print('Socket ID:', request.sid)

@socketio.on("disconnect")
def handle_disconnect():
    print("❌ A client disconnected")

@socketio.on('user_room')
def user_room(data):
    username = data['username']
    user_room_name = f"user_{username}"
    join_room(user_room_name)
    send(f"{username} has entered the user room.", to=user_room_name)

@socketio.on('csr_room')
def csr_room(data):
    csr = data['username']
    join_room(CSR_ROOM)
    send(f'{csr} has entered the room.', to=CSR_ROOM)

@socketio.on('csr_join')
def csr_join(data):
    csr_name = data['csr_id']
    username = data['user']  # User they want to join
    
    # Register handoff pair
    handoff_pairs[username] = csr_name   # Map user to CSR "user1" -> "csr1"

    # Create completely separate rooms
    csr_room = f"csr_{csr_name}_{username}"  # CSR's dedicated room for this conversation
    user_room = f"user_{username}"           # User's dedicated room
    
    # CSR joins only their dedicated room (NOT the user's room)
    join_room(csr_room)
    
    # Notify user that CSR joined (in user's room only)
    emit("bot_response", {"sender": "system", "text": f"CSR {csr_name} has joined the chat. You are now talking to a human agent."}, room=user_room)
    
    # Notify CSR about successful join (in CSR's room only)
    emit("message", {"sender": "system", "text": f"You have joined {username}'s chat. You can now assist them."}, room=csr_room)
    
    print(f"✅ CSR {csr_name} joined separate room: {csr_room}")
    print(f"✅ User {username} room: {user_room}")
    print(f"✅ Handoff pair created: {username} <-> {csr_name}")

@socketio.on("resume_conversation")
def handle_resume(data):
    username = data.get("username")
    sender_id = data.get("sender_id")
    if not sender_id or not username:
        print("Missing sender_id or username!")
        return

    try: 
        # First, unpause the conversation directly with events API
        unpause_payload = [{"event": "resume"}]
        requests.post(
            f"http://localhost:5005/conversations/{sender_id}/tracker/events",
            json=unpause_payload,
            headers={"Content-Type": "application/json"}
        )
        
        # Then send the resume message to trigger intent
        response = requests.post(
            "http://localhost:5005/webhooks/rest/webhook",
            json={"sender": sender_id, "message": "resume"},
            headers={"Content-Type": "application/json"}
        )
        
        print("Response from Rasa:", response.status_code, response.json())
        
        # Send response to user's room only
        user_room = f"user_{username}"
        emit("bot_response", {"sender": "bot", "text": "Conversation resumed with bot ✅ You are no longer connected to a human agent."}, room=user_room)

        # Clean up handoff pair and notify CSR
        if username in handoff_pairs:
            csr = handoff_pairs[username]
            csr_room = f"csr_{csr}_{username}"
            
            # Notify CSR that user has resumed with bot (in CSR's room only)
            emit("message", {"sender": "system", "text": f"User {username} has resumed conversation with bot. Handoff session ended."}, room=csr_room)
            
            # Remove handoff mapping
            del handoff_pairs[username]
            print(f"✅ Handoff ended: {username} <-> {csr}")
            print(f"✅ Separate rooms cleaned up: {user_room} | {csr_room}")

    except Exception as e:
        print("Error resuming conversation:", e)
        user_room = f"user_{username}"
        emit("bot_response", {"sender": "bot", "text": "Error resuming conversation."}, room=user_room)

@socketio.on("message")
def handle_message(data):
    print("Message from react **********************", data)
    user_text = data.get("text", "")
    sender_id = data.get("sender_id")
    username = data.get("username", "user")

    print("Extracted text:", user_text)
    print("Sender:", sender_id)   
    print("username:", username)  

    # Store user message via MCP
    store_message_mcp(username, "user", user_text)

    # --- Handle CSR/user handoff ---
    # 1. If CSR sends message → relay ONLY to user's room
    if username in handoff_pairs.values():
        # Find which user is mapped to this CSR
        user = next((u for u, c in handoff_pairs.items() if c == username), None)
        if user:
            user_room = f"user_{user}"
            
            # Send CSR message ONLY to user's room (CSR won't see their own message duplicated)
            emit("bot_response", {"sender": f"CSR {username}", "text": user_text}, room=user_room)
            store_message_mcp(user, f"CSR_{username}", user_text)
            print("✅ User message stored in MongoDB")
            print(f"✅ CSR {username} → User {user} room ({user_room}): {user_text}")
        return

    # 2. If User is in handoff → relay ONLY to CSR's room (no bot response)
    if username in handoff_pairs:
        csr = handoff_pairs[username]
        csr_room = f"csr_{csr}_{username}"
        
        # Send user message ONLY to CSR's dedicated room
        emit("message", {"sender": username, "text": user_text}, room=csr_room)
        store_message_mcp(username, f"User_{username}", user_text)
        print("✅ User message stored in MongoDB")
        print(f"✅ User {username} → CSR {csr} room ({csr_room}): {user_text}")
        return
    


    # 3. Check for human handoff keywords first, then check for Rasa intents, then try Llama, fallback to Rasa
    
    # Keywords that should trigger human handoff
    handoff_keywords = [
        "human", "agent", "person", "support", "help", "talk to human", 
        "speak to human", "connect me", "transfer", "live agent", "real person"
    ]
    
    # Check if user is requesting human handoff
    user_text_lower = user_text.lower()
    is_handoff_request = any(keyword in user_text_lower for keyword in handoff_keywords)
    
    # Check for Rasa intents (messages starting with /)
    is_rasa_intent = user_text.startswith("/")
    
    start_time = time.time()
    print(f"Time taken for request")

   

    if is_handoff_request:
        print("🔄 Human handoff request detected, triggering handoff directly")
        # Directly trigger handoff without relying on Rasa NLU
        bot_message = [
            {
                "text": "Connecting you to a human agent... Type 'resume' to continue with the bot.",
                "json_message": {"handoff": True, "user": sender_id}
            }
        ]
        print("Direct handoff response:", bot_message)
    elif is_rasa_intent:
        print(f"🎯 Rasa intent detected: {user_text}, sending directly to Rasa")
        try:
            # Send directly to Rasa for intent processing
            rasa_response = requests.post(RASA_API_URL, json={"sender": sender_id, "message": user_text})
            if rasa_response.status_code == 200:
                bot_message = rasa_response.json()
                print("Rasa intent response:", bot_message)
            else:
                raise ConnectionError(f"Rasa server returned status code: {rasa_response.status_code}")
        except Exception as rasa_error:
            print(f"Error with Rasa service: {str(rasa_error)}")
            emit("bot_response", {"sender": "bot", "text": "I'm having trouble processing your request. Please try again later."}, room=username)
            return
    else:
        # For non-handoff requests, try Llama first, then fallback to Rasa
        try:
            # First try Llama
            llama_response = requests.post('http://localhost:5002/chat', json={"message": user_text})
            if llama_response.status_code == 200:
                llama_data = llama_response.json()
                if llama_data.get('success') and 'content' in llama_data:
                    llama_content = llama_data['content']
                    
                    # Check if Llama suggests handoff due to insufficient data
                    if llama_data.get('suggest_handoff'):
                        print("🔄 Llama suggests handoff - no relevant data found, falling back to Rasa")
                        # Fall back to Rasa to trigger action_default_fallback with buttons
                        raise ValueError("Llama suggests handoff, triggering Rasa fallback for proper buttons")
                    else:
                        # Additional check: detect if Llama response indicates no database info
                        no_data_phrases = [
                            "do not have any information about",
                            "don't have any information about",
                            "do not have any relevant data",
                            "don't have any relevant data",
                            "unable to find any information about", 
                            "does not contain information about",
                            "does not contain any information",
                            "I recommend checking",
                            "I suggest checking",
                            "official government website",
                            "reliable news source",
                            "checking a reliable",
                            "database does not include",
                            "not included in the database",
                            "appears to be random text",
                            "does not contain any information that can be searched",
                            "no connection to employees",
                            "I apologize, but",
                            "provide more context",
                            "clarify what you are trying to ask",
                            "no relevant data",
                            "no information about"
                        ]
                        
                        llama_lower = llama_content.lower()
                        has_no_data_response = any(phrase in llama_lower for phrase in no_data_phrases)
                        
                        if has_no_data_response:
                            print("🔄 Backend detected no-data/gibberish response, falling back to Rasa")
                            # Fall back to Rasa for proper fallback handling with buttons
                            raise ValueError("Llama gave unhelpful response, triggering Rasa fallback")
                        else:
                            bot_message = [{"text": llama_content}]
                            print("Llama response:", bot_message)
                else:
                    raise ValueError("Invalid Llama response format")
            else:
                raise ConnectionError(f"Llama server returned status code: {llama_response.status_code}")
                
        except (ValueError, ConnectionError, requests.RequestException) as e:
            print(f"Error with Llama service, falling back to Rasa: {str(e)}")
            try:
                # Fallback to Rasa
                rasa_response = requests.post(RASA_API_URL, json={"sender": sender_id, "message": user_text})
                if rasa_response.status_code == 200:
                    bot_message = rasa_response.json()
                    print("Fallback Rasa response:", bot_message)
                else:
                    raise ConnectionError(f"Rasa server returned status code: {rasa_response.status_code}")
            except Exception as rasa_error:
                print(f"Error with Rasa service: {str(rasa_error)}")
                emit("bot_response", {"sender": "bot", "text": "I'm having trouble processing your request. Please try again later."}, room=username)
                return
        except Exception as e:
            print(f"Unexpected error in message handling: {str(e)}")
            emit("bot_response", {"sender": "bot", "text": "An unexpected error occurred. Please try again later."}, room=username)
            return

    end_time = time.time()  # Record end time
    duration = end_time - start_time
    print(f"Time taken for request: {duration:.3f} seconds")

    if bot_message:
            combined_texts = []
            buttons = []
            handoff_required = False

            for msg in bot_message:
                if "text" in msg:
                    combined_texts.append(msg["text"])
                if "buttons" in msg:
                    buttons.extend(msg["buttons"])
                # Check for handoff in both custom and json_message fields
                if ("custom" in msg and msg['custom'].get("handoff")) or ("json_message" in msg and msg['json_message'].get("handoff")):
                    handoff_required = True

            bot_reply = {"sender": "bot", "text": " ".join(combined_texts)}
            if buttons:
                bot_reply["buttons"] = buttons
            
            # Send to user's specific room (only when NOT in handoff)
            user_room = f"user_{username}"
            emit("bot_response", bot_reply, room=user_room)
            print(f"✅ Bot response sent to {user_room}")

             # --- Store BOT message in MongoDB ---
            store_message_mcp(username, f"Bot_{username}", " ".join(combined_texts))
            print("✅ Bot message stored in MongoDB")

            # Notify CSR if human handoff is needed
            if handoff_required:
                print("🚨 Human handoff required - notifying CSR room")
                emit("join_request",
                    {"username": username, "msg": "A human agent is required. Click join to assist."},
                    room=CSR_ROOM, include_self=False)






@app.route("/")
def index():
    return "Chatbot server is running"



if __name__ == '__main__':
    socketio.run(app,debug=True, port =5000)