import React, { useState, useEffect, useRef } from "react";
import { io } from "socket.io-client";
import { v4 as uuidv4 } from "uuid";

const socket = io("http://localhost:5000");

function UserUI() {
  const [messages, setMessages] = useState("");
  const [chat, setChat] = useState<
    {
      sender: string;
      text: string;
      buttons?: { title: string; payload: string }[];
    }[]
  >([]);
  const [username, setUsername] = useState("");
  const hasPrompted = useRef(false);
  const [senderId, setSenderId] = useState("");

  // const csr_ids = ["csr1", "csr2", "csr3"];

  useEffect(() => {
    let id = localStorage.getItem("senderId");
    if (!id) {
      id = uuidv4();
      localStorage.setItem("senderId", id || "");
    }
    setSenderId(id || "");
  }, []);

  useEffect(() => {
    if (!hasPrompted.current) {
      const nameValue = prompt("Enter your username:");
      if (nameValue) {
        setUsername(nameValue);
        socket.emit("user_room", { username: nameValue }); // Join user room
        socket.emit("csr_room", { username: nameValue }); // Join CSR room if CSR
      }
      hasPrompted.current = true;
    }
  }, []);

  useEffect(() => {
    socket.on("connect", () => {
      if (username) socket.emit("user_room", { username });
      console.log("Joined room:", username);
    });

    // ✅ Bot responses
    socket.on("bot_response", (msg) => {
      setChat((prev) => [
        ...prev,
        { sender: "bot", text: msg.text, buttons: msg.buttons },
      ]);
    });

    // CSR or User messages during handoff
    socket.on("message", (msg) => {
      setChat((prev) => [...prev, { sender: msg.sender, text: msg.text }]);
    });

    const handleJoinRequest = (data: { username: string; msg: string }) => {
      if (window.confirm(`${data.msg} (User: ${data.username})`)) {
        socket.emit("csr_join", { csr_id: username, user: data.username });
      }
    };

    socket.on("join_request", handleJoinRequest);

    return () => {
      socket.off("bot_response");
      socket.off("message");
      socket.off("join_request", handleJoinRequest);
    };
  }, [username]);

  const sendMessage = () => {
    if (!messages.trim()) return;
    const userMessage = { sender: "user", text: messages, username };
    socket.emit("message", { sender_id: senderId, text: messages, username });
    setChat((prev) => [...prev, userMessage]);
    setMessages("");
  };

  // Send payload when button clicked
  const humanHandoff = (payload: string, title: string) => {
    const userMessage = { sender: "user", text: title };
    socket.emit("message", { sender_id: senderId, text: payload, username });
    // show the clicked button title in chat
    setChat((prev) => [...prev, userMessage]);
  };

  const resumeConversation = () => {
    const userMessage = { sender: "user", text: "resume" };

    // Show "resume" in chat UI
    setChat((prev) => [...prev, userMessage]);

    // Emit the resume event to backend
    socket.emit("resume_conversation", { sender_id: senderId, username });
  };

  // Handle Enter key to send message
  const handleKeyDown = (e: React.KeyboardEvent<HTMLInputElement>) => {
    if (e.key === "Enter") {
      sendMessage();
    }
  };

  return (
    <div>
      {/* <h2>UserUI</h2> */}
      <div>
        {username ? (
          <h1>Welcome, {username}!</h1>
        ) : (
          <h1>Please enter your username</h1>
        )}
      </div>
      <div
        style={{
          border: "1px solid gray",
          padding: "10px",
          height: "200px",
          overflowY: "scroll",
        }}
      >
        {chat.map((c, index) => (
          <div key={index}>
            <p>
              <strong>{c.sender}</strong> {c.text}
            </p>
            {c.buttons && c.buttons.length > 0 && (
              <div>
                {c.buttons.map((btn, btnIdx) => (
                  <button
                    key={btnIdx}
                    onClick={() => humanHandoff(btn.payload, btn.title)}
                  >
                    {btn.title}
                  </button>
                ))}
              </div>
            )}
          </div>
        ))}
      </div>
      <input
        value={messages}
        onChange={(e) => setMessages(e.target.value)}
        onKeyDown={handleKeyDown} // <-- Send message on Enter
        placeholder="Type a message..."
      />

      <button onClick={sendMessage}>Send</button>
      <button onClick={resumeConversation}>Resume</button>
    </div>
  );
}

export default UserUI;
