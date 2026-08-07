
import asyncio
from services.jobs_provider import ArbeitnowProvider

async def main():
    p = ArbeitnowProvider()
    jobs = await p.fetch_jobs()
    print("Found:", len(jobs))
    if jobs:
        print("Locations:", [j.location for j in jobs[:5]])

asyncio.run(main())

