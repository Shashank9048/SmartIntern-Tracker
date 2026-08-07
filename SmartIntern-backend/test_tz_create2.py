import asyncio, os, sys, datetime
sys.path.insert(0, os.path.abspath('.'))
from api.models import Automation
from motor.motor_asyncio import AsyncIOMotorClient
from beanie import init_beanie
async def main():
    client = AsyncIOMotorClient('mongodb://localhost:27017')
    await init_beanie(database=client.smartintern, document_models=[Automation])
    a = Automation(user_id='test', application_id='test', type='followup', status='active', scheduled_at=datetime.datetime.now(datetime.timezone.utc))
    await a.insert()
    a = await Automation.find_one({'user_id': 'test'})
    print('Retrieved:', repr(a.scheduled_at))
    await a.delete()
asyncio.run(main())
