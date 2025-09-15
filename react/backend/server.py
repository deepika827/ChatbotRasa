from flask import Flask, request, jsonify
import requests
from flask_socketio import SocketIO, send, join_room, leave_room, emit
from flask_cors import CORS
from pymongo import MongoClient
import datetime


client = MongoClient("mongodb://localhost:27017/")
db = client["mcp_database"]
chat_collection = db["mcp_collection"]

handoff_pairs = {}
RASA_API_URL = "http://localhost:5005/webhooks/rest/webhook"




app= Flask(__name__)


socketio = SocketIO(app, cors_allowed_origins="*") ## allow react frontend
CORS(app)

# CSR room name
CSR_ROOM = "csr_room_all"

@socketio.on("connect")
def handle_connect():
    print("🔌 A client connected *******************************")
    emit("message", {"user": "Bot", "msg": "Welcome to the chat!"})
    print('Socket ID:', request.sid)

@socketio.on("disconnect")
def handle_disconnect():
    print("❌ A client disconnected")

@socketio.on('user_room')
def user_room(data):

    username = data['username']

    join_room(username)
    send(f"{username} has entered the room.", to=username)

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

    # Put CSR into the user's room
    join_room(f'user_{username}')
    emit("bot_response", {"text": f"CSR {csr_name} has joined the chat {username}."}, to=f'user_{username}')

    # emit("handoff_active",{"user":username,"csr":csr_name}, room = username)




# --- New handler for resuming conversation ---
@socketio.on("resume_conversation")
def handle_resume(data):

    username = data.get("username")
    sender_id = data.get("sender_id")  # <- this must match what React emits
    if not sender_id or not username:
        print("Missing sender_id or username!")
        return

    try: # First, unpause the conversation directly with events API
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
        # Even if Rasa returns empty, still notify user
        print("Response from Rasa:", response.status_code, response.json())
        # Send response to client (regardless of Rasa response)
        emit("bot_response", {"sender": "bot", "text": "Conversation resumed with bot ✅"}, room=username)

        if username in handoff_pairs:
            del handoff_pairs[username]

    except Exception as e:
        print("Error resuming conversation:", e)
        emit("bot_response", {"sender": "bot", "text": "Error resuming conversation."}, room=username)

@socketio.on("message")
def handle_message(data):
    print("Message from react **********************", data)
    user_text = data.get("text", "")
    sender_id = data.get("sender_id")
    username = data.get("username", "user")

## input texts from user
    print("Extracted text:", user_text)
    print("Sender:", sender_id)   
    print("username:", username)  

    
    # --- Always store USER message ---
    user_message = {
        "username": username,
        "sender": "user",
        "text": user_text,
        "timestamp": datetime.datetime.now()
    }
    chat_collection.insert_one(user_message)
    print("✅ User message stored in MongoDB")
    
     # 1. If CSR → forward to the paired user
    if username in handoff_pairs.values():
        # find which user is mapped to this CSR
        user = next((u for u, c in handoff_pairs.items() if c == username), None)
        if user:
            emit("message", {"sender": username, "text": user_text}, room=user)
            print(f"Forwarded CSR {username} -> User ")
        # return

             # Store CSR message
            csr_message = {
                "username": user,
                "sender": username,
                "text": user_text,
                "timestamp": datetime.datetime.utcnow()
            }
            chat_collection.insert_one(csr_message)
            print("✅ CSR message stored in MongoDB")
        return


    # 2. If User is in handoff → forward to CSR
    if username in handoff_pairs:
        csr = handoff_pairs[username]
        emit("message", {"sender": username, "text": user_text}, room=csr)
        print(f"Forwarded User {username} -> CSR {csr}: {user_text}")

        # return

        
        # Store forwarded user message
        forwarded_msg = {
            "username": username,
            "sender": username,
            "text": user_text,
            "timestamp": datetime.datetime.now()
        }
        chat_collection.insert_one(forwarded_msg)
        print("✅ Forwarded User message stored in MongoDB")
        return
    


    # 3. Try Llama first, then fallback to Rasa if needed
    try:
        # First try Llama
        llama_response = requests.post('http://localhost:5002/chat', json={"message": user_text})
        if llama_response.status_code == 200:
            llama_data = llama_response.json()
            if llama_data.get('success') and 'content' in llama_data:
                bot_message = [{"text": llama_data['content']}]
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

    if bot_message:
            combined_texts = []
            buttons = []
            handoff_required = False

            for msg in bot_message:
                if "text" in msg:
                    combined_texts.append(msg["text"])
                if "buttons" in msg:
                    buttons.extend(msg["buttons"])
                if "custom" in msg and msg['custom'].get("handoff"):
                    handoff_required = True

            bot_reply = {"sender": "bot", "text": " ".join(combined_texts)}
            if buttons:
                bot_reply["buttons"] = buttons
            emit("bot_response", bot_reply, room=username)

             # --- Store BOT message in MongoDB ---
            bot_message_doc = {
                "username": username,
                "sender": "bot",
                "text": " ".join(combined_texts),
                "timestamp": datetime.datetime.utcnow()
            }
            chat_collection.insert_one(bot_message_doc)
            print("✅ Bot message stored in MongoDB")

            # Notify CSR if human handoff is needed
            if handoff_required:
                emit("join_request",
                    {"username": username, "msg": "A human agent is required. Click join to assist."},
                    room=CSR_ROOM, include_self=False)






@app.route("/")
def index():
    return "Chatbot server is running"



if __name__ == '__main__':
    socketio.run(app,debug=True, port =5000)














