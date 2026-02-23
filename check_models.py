import google.generativeai as genai
import os
from dotenv import load_dotenv

# Load env same as backend
current_dir = os.path.dirname(os.path.abspath(__file__))
while current_dir != os.path.dirname(current_dir):
    env_path = os.path.join(current_dir, ".env")
    if os.path.exists(env_path):
        load_dotenv(env_path)
        print(f"✅ Loaded .env from: {env_path}")
        break
    current_dir = os.path.dirname(current_dir)

api_key = os.environ.get("GEMINI_API_KEY")
if not api_key:
    print("❌ No API Key found")
    exit(1)

genai.configure(api_key=api_key)

print("Checking specific models...")
target_models = ['gemini-1.5-flash', 'gemini-pro', 'models/gemini-1.5-flash', 'models/gemini-pro']
available = []
output_lines = []

try:
    for m in genai.list_models():
        if 'generateContent' in m.supported_generation_methods:
            available.append(m.name)

    for target in target_models:
        if target in available or f"models/{target}" in available:
             output_lines.append(f"Found: {target}")
        else:
             output_lines.append(f"Not Found: {target}")
             
    output_lines.append("First 5 available:")
    for m in available[:5]:
        output_lines.append(m)

    with open("models_output.txt", "w", encoding="utf-8") as f:
        f.write("\n".join(output_lines))
    print("Output written to models_output.txt")

except Exception as e:
    with open("models_output.txt", "w", encoding="utf-8") as f:
        f.write(f"Error: {str(e)}")
    print(f"Error: {e}")
