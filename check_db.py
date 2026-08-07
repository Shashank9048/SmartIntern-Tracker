import asyncio
from motor.motor_asyncio import AsyncIOMotorClient
import os
from dotenv import load_dotenv

load_dotenv('.env')

async def main():
    client = AsyncIOMotorClient(os.environ['MONGODB_URL'])
    db = client.smart_intern_tracker
    users = await db.users.find().to_list(100)
    for u in users:
        print(f"User: {u.get('email')} | Admin: {u.get('is_admin')}")

asyncio.run(main())
