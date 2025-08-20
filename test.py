import boto3
import json
from dotenv import load_dotenv
import os

# --- Configuration ---
# load environment variables
load_dotenv()
# Set your AWS region (e.g., 'us-east-1', 'us-west-2', 'ap-southeast-2')
AWS_REGION = os.getenv("AWS_REGION", "ap-south-1")

# Get your long-term Bedrock API key from environment variable
BEDROCK_API_KEY = os.getenv("AWS_BEDROCK_API_KEY")

# if not BEDROCK_API_KEY:
#     raise ValueError(
#         "AWS_BEDROCK_API_KEY environment variable not set. "
#         "Please set it with your long-term Bedrock API key."
#     )

# print(f"Using AWS Region: {AWS_REGION}")

if not BEDROCK_API_KEY:
    BEDROCK_API_KEY = input("⚠️ Bedrock API key not found in environment. Please enter it manually: ").strip()

if not BEDROCK_API_KEY:
    raise ValueError("🚨 Bedrock API key is required. Exiting...")

print(f"✅ Using AWS Region: {AWS_REGION}")
print("🔐 Bedrock API key successfully retrieved.")

# --- Initialize Bedrock Runtime Client with API Key ---
# When you provide `aws_bedrock_api_key`, boto3 will use it for authentication.
# You don't need to explicitly provide aws_access_key_id or aws_secret_access_key here,
# unless you also want to use traditional IAM credentials for other AWS services.
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

# --- Function to Invoke a Bedrock Model ---
def invoke_bedrock_model(model_id: str, prompt: str, temperature: float = 0.7, max_tokens: int = 200):
    """
    Invokes a specified Bedrock foundational model with the given prompt.
    Handles different payload formats for common models.
    """
    body = {}
    content_type = "application/json"
    accept = "application/json"

    print(f"\n--- Invoking Model: {model_id} ---")
    print(f"Prompt: {prompt}")

    try:
        if "titan-text" in model_id:
            body = json.dumps({
                "inputText": prompt,
                "textGenerationConfig": {
                    "maxTokenCount": max_tokens,
                    "temperature": temperature,
                    "topP": 0.9
                }
            })
        elif "claude" in model_id:
            # Claude models (Anthropic) use a "messages" API style
            body = json.dumps({
                "messages": [
                    {"role": "user", "content": [{"type": "text", "text": prompt}]}
                ],
                "max_tokens": max_tokens,
                "temperature": temperature,
                "anthropic_version": "bedrock-2023-05-31" # Required for Claude on Bedrock
            })
        elif "command" in model_id:
            # Cohere Command models
            body = json.dumps({
                "prompt": prompt,
                "max_tokens": max_tokens,
                "temperature": temperature,
                "p": 0.9,
                "k": 0
            })
        elif "mixtral" in model_id or "llama" in model_id:
            # Mistral and Llama models often use a simpler prompt/message format
            body = json.dumps({
                "prompt": prompt,
                "max_tokens": max_tokens,
                "temperature": temperature
            })
        else:
            print(f"Warning: Model {model_id} has an unknown payload format. Using a generic text-to-text format.")
            body = json.dumps({
                "prompt": prompt,
                "max_tokens_to_sample": max_tokens, # Common for some older models
                "temperature": temperature
            })

        response = bedrock_runtime.invoke_model(
            body=body,
            modelId=model_id,
            accept=accept,
            contentType=content_type
        )

        response_body = json.loads(response.get('body').read())

        if "titan-text" in model_id:
            text_response = response_body['results'][0]['outputText']
        elif "claude" in model_id:
            # Claude 3 models return content as a list of dictionaries
            text_response = response_body['content'][0]['text']
        elif "command" in model_id:
            text_response = response_body['generations'][0]['text']
        elif "mixtral" in model_id or "llama" in model_id:
            text_response = response_body['completion'] # Common for Mistral/Llama
        else:
            text_response = str(response_body) # Fallback to raw response if parsing is not defined

        print("Response:")
        print(text_response)

    except bedrock_runtime.exceptions.ResourceNotFoundException:
        print(f"Error: Model '{model_id}' not found or you don't have access to it in region {AWS_REGION}.")
        print("Please ensure you have requested model access in the Bedrock console.")
    except bedrock_runtime.exceptions.ValidationException as ve:
        print(f"Validation Error: {ve}")
        print("Check if the prompt format and parameters are correct for the model.")
    except Exception as e:
        print(f"An unexpected error occurred for model {model_id}: {e}")

# --- Example Invocations ---

# 1. Amazon Titan Text Express
# Model ID can vary slightly by region and version.
# Check the Bedrock console under "Foundation models" -> "Details" for exact ID.
titan_text_model_id = "amazon.titan-text-express-v1"
invoke_bedrock_model(titan_text_model_id, "Explain the concept of quantum entanglement in simple terms.")

# 2. Anthropic Claude 3 Sonnet (or other Claude models)
# Ensure you have access to Claude 3 Sonnet (or other Claude versions like Haiku, Opus, v2, v2:1)
# Model ID examples: "anthropic.claude-3-sonnet-20240229-v1:0", "anthropic.claude-3-haiku-20240307-v1:0"
claude_model_id = "anthropic.claude-3-sonnet-20240229-v1:0"
invoke_bedrock_model(claude_model_id, "Write a short, uplifting haiku about new beginnings.")

# 3. Cohere Command (or Command R, Command R+)
# Ensure you have access to Cohere Command models.
# Model ID examples: "cohere.command-text-v14", "cohere.command-r-v1:0"
cohere_command_model_id = "cohere.command-text-v14"
invoke_bedrock_model(cohere_command_model_id, "Summarize the main events of World War II in less than 100 words.")

# 4. Mistral 7B Instruct v0.2 (or Mixtral)
# Ensure you have access to Mistral models.
# Model ID examples: "mistral.mistral-7b-instruct-v0:2", "mistral.mixtral-8x7b-instruct-v0:1"
mistral_model_id = "mistral.mistral-7b-instruct-v0:2"
invoke_bedrock_model(mistral_model_id, "Give me a creative idea for a new mobile app.")

print("\n--- Program finished ---")