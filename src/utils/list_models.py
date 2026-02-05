"""List available Gemini models"""
import google.generativeai as genai
import config

genai.configure(api_key=config.GOOGLE_API_KEY)

print("Available Gemini models:")
print("="*60)

try:
    for model in genai.list_models():
        if 'generateContent' in model.supported_generation_methods:
            print(f"- {model.name}")
except Exception as e:
    print(f"Error listing models: {e}")
