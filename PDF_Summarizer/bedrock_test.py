import requests
import os
import json
from dotenv import load_dotenv
import streamlit as st
from PyPDF2 import PdfReader
import fitz  # PyMuPDF

#loading environment variables
load_dotenv()

class bedrockAPI:
    def __init__(self):
        self.url = "https://bedrock-runtime.ap-south-1.amazonaws.com/model/anthropic.claude-3-sonnet-20240229-v1:0/converse"
        self.AWS_REGION = os.getenv("AWS_REGION", "ap-south-1")
        self.BEDROCK_API_KEY = os.getenv('AWS_BEDROCK_API_KEY')

        if not self.BEDROCK_API_KEY:
            raise ValueError("🚨 Bedrock API key is required. Exiting...")

        print(f"✅ Using AWS Region: {self.AWS_REGION}")
        print("🔐 Bedrock API key successfully retrieved.")

    def get_headers(self):
        return {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.BEDROCK_API_KEY}"
        }

    def summarizer(self, extracted_text):
        # prompt_text = input("Enter your prompt: ")
        payload = {
            "messages": [
                {
                    "role": "user",
                    "content": [{"text": f"Summarize the following pdf content: \n\n{extracted_text}"}]
                }
            ],
            "maxTokens": 1000,
            "temperature": 0.7
        }

        response = requests.post(self.url, headers=self.get_headers(), json=payload)
        
        if response.status_code == 200:
            try:
                result = response.json()
                return result["output"]["message"]["content"][0]["text"]
            except Exception as e:
                print("Error parsing response:", e)
                return "Error parsing response"
        else:
            print(f"Error: {response.status_code} - {response.text}")
            return f"Error: {response.status_code} - {response.text}"
        
    def extract_text_from_pdf(self, pdf_path):
            """
            Extracts text from a PDF file.
            """
            try:
                with open(pdf_path, "rb") as file:
                    doc = fitz.open(stream=file.read(), filetype="pdf")
                    text = ""
                    for page in doc:
                        text += page.get_text()
                    return text
            except Exception as e:
                print("Error extracting text from PDF:", e)
                return None
        
    

def main(pdf_path):
    bedrock = bedrockAPI()
    # response = bedrock.send_request()
    extracted_text = bedrock.extract_text_from_pdf(pdf_path)  # Example PDF file path
    

    print(extracted_text)

    if extracted_text and not extracted_text.startswith("Error"):
        st.success("✅ Text extracted successfully!")
        st.subheader("📑 Extracted Text Preview:")
        st.text_area("Extracted Text", extracted_text[:3000] + "...", height=200)

        if st.button("🔍 Summarize PDF"):
            with st.spinner("Sending to Claude for summarization..."):
                summary = bedrock.summarizer(extracted_text)
            st.subheader("🧠 Summary:")
            st.write(summary)
            
    else:
        st.error(extracted_text)
    



if __name__ == "__main__":
    main()

