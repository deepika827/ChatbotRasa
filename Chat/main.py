from urllib import response
from flask import Flask, request, jsonify
import requests
from flask_socketio import SocketIO, send, join_room, leave_room, emit
from flask_cors import CORS
from pymongo import MongoClient

client = MongoClient("mongodb://localhost:27017/")
db = client['chatbot_db']
collection = db['conversation']

handoff_pairs = {}
# import psycopg2

# conn = psycopg2.connect(
#         host="localhost",
#         database="chatbot",
#         user= "postgres",
#         password= "postgres")

# # Open a cursor to perform database operations
# cur = conn.cursor()

# # Execute a command: this creates a new table
# cur.execute('DROP TABLE IF EXISTS conversation;')
# cur.execute('CREATE TABLE conversation (id serial PRIMARY KEY,'
#                                  'client varchar (150) NOT NULL,'
#                                  'bot varchar (50) NOT NULL,'
#                                  'csr varchar (50) NOT NULL,'
#                                  'created_at date DEFAULT CURRENT_TIMESTAMP);'
#                                  )
# conn.commit()

# cur.close()
# conn.close()



RASA_API_URL = "http://localhost:5005/webhooks/rest/webhook"
# global_sender_id = "f5d2c1ce-d745-41b4-bd6e-f0bb913e0739"


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
    join_room(username)
    emit("bot_response", {"text": f"CSR {csr_name} has joined the chat {username}."}, to=username)

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
    
     # 1. If CSR → forward to the paired user
    if username in handoff_pairs.values():
        # find which user is mapped to this CSR
        user = next((u for u, c in handoff_pairs.items() if c == username), None)
        if user:
            emit("message", {"sender": username, "text": user_text}, room=user)
            print(f"Forwarded CSR {username} -> User ")
        return

    # 2. If User is in handoff → forward to CSR
    if username in handoff_pairs:
        csr = handoff_pairs[username]
        emit("message", {"sender": username, "text": user_text}, room=csr)
        print(f"Forwarded User {username} -> CSR {csr}: {user_text}")
        return

    # 3. Otherwise → Send to Rasa
    try:
        rasa_response = requests.post(RASA_API_URL, json={"sender": sender_id, "message": user_text})
        bot_message = rasa_response.json() if rasa_response.status_code == 200 else None
        print("Rasa response:", bot_message)
    except Exception as e:
        print("Error contacting Rasa:", e)
        emit("bot_response", {"sender": "bot", "text": "⚠️ Could not reach Rasa server."}, room=username)
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














