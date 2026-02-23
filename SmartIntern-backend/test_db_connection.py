import asyncio
import os
from motor.motor_asyncio import AsyncIOMotorClient
from beanie import init_beanie, Document
from pydantic import EmailStr
from dotenv import load_dotenv

# Load env vars
load_dotenv("../.env")

class User(Document):
    email: EmailStr
    hashed_password: str
    
    class Settings:
        name = "users"

async def test_connection():
    mongo_url = os.environ.get("MONGODB_URL")
    print(f"Please check if this URL is correct: {mongo_url}")
    
    try:
        client = AsyncIOMotorClient(mongo_url)
        # Force connection verification
        await client.server_info() 
        print("✅ MongoDB Connection Successful!")
        
        await init_beanie(database=client["smart_intern_tracker"], document_models=[User])
        print("✅ Beanie Initialized!")
        
        # Try to find users
        count = await User.count()
        print(f"📊 Current User Count: {count}")
        
    except Exception as e:
        print(f"❌ Connection Failed: {e}")

if __name__ == "__main__":
    asyncio.run(test_connection())
