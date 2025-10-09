import boto3
import json
from dotenv import load_dotenv
import os
import tiktoken
from PyPDF2 import PdfReader

# --- Configuration ---
# load environment variables
load_dotenv()
# Set your AWS region (e.g., 'us-east-1', 'us-west-2', 'ap-southeast-2')
AWS_REGION = os.getenv("AWS_REGION", "ap-south-1")

# Get your long-term Bedrock API key from environment variable
BEDROCK_API_KEY = os.getenv("AWS_BEDROCK_API_KEY")

if not BEDROCK_API_KEY:
    BEDROCK_API_KEY = input("⚠️ Bedrock API key not found in environment. Please enter it manually: ").strip()

if not BEDROCK_API_KEY:
    raise ValueError("🚨 Bedrock API key is required. Exiting...")

print(f"✅ Using AWS Region: {AWS_REGION}")
print("🔐 Bedrock API key successfully retrieved.")

# --- Initialize Bedrock Runtime Client with API Key ---
try:
    bedrock_runtime = boto3.client(
        service_name='bedrock-runtime',
        region_name=AWS_REGION,
        aws_bedrock_api_key=BEDROCK_API_KEY
     
    )
    print("Bedrock runtime client initialized successfully with API Key.")
except Exception as e:
    print(f"Error initializing Bedrock client: {e}")
    print("Please ensure your AWS_BEDROCK_API_KEY is valid and the region is correct.")
    exit()

# --- Function to Summarize Text ---
def summarizer(prompt) -> str:

    body = json.dumps({
                "prompt": prompt,
                "max_tokens_to_sample": 8191,
                "temperature": 0.7,
                "top_p": 0.9,
                "stop_sequences": []
    })
        
    try:
        response = bedrock_runtime.invoke_model(

            modelId="anthropic.claude-3-sonnet-20240229-v1:0",    # the specific Bedrock model we are using
            body=body,
            contentType="application/json",
            accept="application/json"
        )
        
        # gathering the response from bedrock, and parsing to get specifically the answer
        response_body = json.loads(response.get('body').read())
        answer = response_body.get('text', '')
        return answer
    except Exception as e:
        print(f"Error during summarization: {e}")
        return "Failed to summarize the text."

# --- Function to Count Tokens ---
def num_tokens_from_string(string) -> int:
    encoding = tiktoken.get_encoding("cl100k_base")
    return len(encoding.encode(string))

# --- Function to Chunk Text by Tokens ---
def chunk_text_by_tokens(text, max_tokens=2000):
    encoding = tiktoken.get_encoding("cl100k_base")
    tokens = encoding.encode(text)
    
    chunks = []
    for i in range(0, len(tokens), max_tokens):
        chunk = tokens[i:i + max_tokens]
        decoded_chunk = encoding.decode(chunk)
        chunks.append(decoded_chunk)
    return chunks

# --- PDF Reader Function ---

def Chunk_and_Summarize(uploaded_file) -> str:
    try:
        reader = PdfReader(uploaded_file)
    except Exception as e:
        print(f"Error loading PDF: {e}")
        return "Failed to load PDF file."

    text = ""
    for page_num, page in enumerate(reader.pages):
        try:
            page_text = page.extract_text()
            if page_text:
                text += page_text + "\n"
        except Exception as e:
            print(f"Error extracting text from page {page_num + 1}: {e}")

    try:
        chunks = chunk_text_by_tokens(text)
    except Exception as e:
        print(f"Error chunking text: {e}")
        return "Failed to chunk the document."

    summary = ""
    for index, chunk_content in enumerate(chunks):
        try:
            prompt = f"""\n\nHuman: Provide a detailed summary for the chunk of text provided to you:
Text: {chunk_content}
\n\nAssistant:"""

            chunk_summary = summarizer(prompt)
            summary += chunk_summary

            print(f"\n\nNumber of tokens for Chunk {index + 1} with the prompt: {num_tokens_from_string(prompt)} tokens")
            print("-------------------------------------------------------------------------------------------------------")
        except Exception as e:
            print(f"Error summarizing chunk {index + 1}: {e}")

    try:
        final_summary_prompt = f"""\n\nHuman: You will be given a set of summaries from a document. Create a cohesive 
summary from the provided individual summaries. The summary should be very detailed and at least 1 page. 
Summaries: {summary}
\n\nAssistant:"""

        print(f"\nNumber of tokens for final prompt: {num_tokens_from_string(final_summary_prompt)}")

        final_summary = summarizer(final_summary_prompt)
        return final_summary

    except Exception as e:
        print(f"Error generating final summary: {e}")
        return "Failed to generate final document summary."

    