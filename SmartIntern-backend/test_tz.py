import asyncio, os, sys
sys.path.insert(0, os.path.abspath('.'))
from api.models import Automation
from motor.motor_asyncio import AsyncIOMotorClient
from beanie import init_beanie
async def main():
    client = AsyncIOMotorClient('mongodb://localhost:27017')
    await init_beanie(database=client.smartintern, document_models=[Automation])
    a = await Automation.find_one()
    print(repr(a.scheduled_at) if a else 'No auto')
asyncio.run(main())
