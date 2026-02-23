import google.generativeai as genai
import os
from dotenv import load_dotenv
import time

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

model_name = 'models/gemini-2.0-flash'
print(f"Testing model: {model_name}")

try:
    start = time.time()
    model = genai.GenerativeModel(model_name)
    response = model.generate_content("Say hello")
    print(f"Response: {response.text}")
    print(f"Time taken: {time.time() - start:.2f}s")
except Exception as e:
    print(f"❌ Error: {e}")
