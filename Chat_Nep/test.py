from flask import Flask, request, jsonify
import requests
from flask_socketio import SocketIO, send, join_room, leave_room, emit
from flask_cors import CORS
from pymongo import MongoClient
import gridfs
import datetime
from PyPDF2 import PdfReader


client = MongoClient("mongodb://localhost:27017/")
db = client["mcp_database"]
chat_collection = db["mcp_collection"]

fs = gridfs.GridFS(db)


def upload_pdf_if_not_exists(pdf_path, filename):

    existing_pdf = db["pdf_texts"].find_one({"filename": filename})
   

    if existing_pdf:
        print("PDF already exists in database")
        return existing_pdf  # Return the existing document
    else:
    # Upload PDF and extract text
        with open("MunaMadan.pdf", "rb") as f:
            file_id = fs.put(f, filename="MunaMadan PDF", contentType="application/pdf")

            f.seek(0)  # Reset file pointer to the beginning
            reader = PdfReader(f)
            pdf_text = ""
            for page in reader.pages:
                pdf_text += page.extract_text() or ""

            doc = db["pdf_texts"].insert_one({"file_id": file_id, "filename": filename, "text": pdf_text})
            return doc