import os
from dotenv import load_dotenv
import google.generativeai as genai
from llm.llm_models import ClaudeLLM, GeminiLLM

#from ..llm.llm_models import ClaudeLLM, GeminiLLM # both are okey, if there a lot of file, use this.

load_dotenv(dotenv_path="MyLLM.env")

def get_model():
    model = None
    if "Gemini" in os.getenv("LLM"):
        genai.configure(api_key=os.getenv("GOOGLE_API_KEY"))
        model = GeminiLLM('gemini-1.5-pro')
    elif "Claude" in os.getenv("LLM"):
        model = ClaudeLLM(
            model_id="anthropic.claude-3-5-sonnet-20240620-v1:0",
            temperature=0.7,
            aws_region="us-east-1",
        )

    if model is None:
        raise ValueError("Model is not initialized.")
    
    return model
