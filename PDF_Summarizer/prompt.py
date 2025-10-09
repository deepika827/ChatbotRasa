import requests
import json
import boto3
from dotenv import load_dotenv
import os
import streamlit as st


# load environment variables
load_dotenv()

url = "https://bedrock-runtime.ap-south-1.amazonaws.com/model/anthropic.claude-3-sonnet-20240229-v1:0/converse" ###############


# Set your AWS region (e.g., 'us-east-1', 'us-west-2', 'ap-southeast-2')
AWS_REGION = os.getenv("AWS_REGION", "ap-south-1")    #########################

BEDROCK_API_KEY = os.getenv('AWS_BEDROCK_API_KEY')  ##################################
# BEDROCK_API_URL = "https://bedrock-runtime.amazonaws.com"

if not BEDROCK_API_KEY:
    BEDROCK_API_KEY = input("⚠️ Bedrock API key not found in environment. Please enter it manually: ")

if not BEDROCK_API_KEY:
    raise ValueError("🚨 Bedrock API key is required. Exiting...")

print(f"✅ Using AWS Region: {AWS_REGION}")
print("🔐 Bedrock API key successfully retrieved.")
# print(BEDROCK_API_KEY)


# Prompt user for input
# prompt_text = input("Enter your prompt: ")

headers = {
    
    "Content-Type": "application/json",
    "Authorization": f"Bearer {BEDROCK_API_KEY}"
}

print(headers)




payload = {
    "messages": [   
        {
            "role": "user",
            "content": [{"text": "Write a short story about a robot learning to love."}]
        }
    ],
    "maxTokens": 1000,  
    "temperature": 0.7
}

response = requests.post(url, headers=headers, json=payload)

print(response.status_code)
print(response.text)

st.title("Claude 3 Sonnet API Response")

if response.status_code == 200:
    st.subheader("✅ Success")
    st.json(response.json())  # Nicely formatted JSON output
else:
    st.subheader("❌ Error")
    st.write(f"Status Code: {response.status_code}")
    st.json(response.json())  # Show error details

# print("authentication successful")

# try:
#     bedrock_runtime = boto3.client(service_name='bedrock-runtime',region_name=AWS_REGION)
#     print("Bedrock runtime client initialized successfully with API Key.")
# except Exception as e:
#     print(f"Error initializing Bedrock client: {e}")
#     print("Please ensure your AWS_BEDROCK_API_KEY is valid and the region is correct.")
#     exit()


# body=json.dumps(payload)
# response_body = bedrock_runtime.invoke_model(
#             body=body,
#             modelId="anthropic.claude-3-sonnet-20240229-v1:0",
#             accept="application/json",
#            )


# response = requests.request("POST","https://bedrock-runtime.ap-south-1.amazonaws.com/model/anthropic.claude-3-sonnet-20240229-v1:0/converse", headers=headers, json=response_body)
# response.raise_for_status()  # Raise an error for bad responses
# result = response.json()

# print(result)




# import requests

# url = "https://bedrock-runtime.ap-south-1.amazonaws.com/model/anthropic.claude-3-sonnet-20240229-v1:0/converse"

# payload = {
#     "messages": [
#         {
#             "role": "user",
#             "content": [{"text": "Hello"}]
#         }
#     ]
# }
# api_key = 'ABSKQmVkcm9ja0FQSUtleS1rdXhpLWF0LTM4MTQ5MjAwMDk3OToveUs3K254TUdYS1pCekZtc1RIN2hUU1FUMXh5UktvbUh1b0JxWHFkM3kvNnJMaXpGU2dzTiszVm9GTT0='
# headers = {
#     "Content-Type": "application/json",
#     "Authorization": f"Bearer {api_key}"
# }

# response = requests.request("POST", url, json=payload, headers=headers)

# print(response.text)