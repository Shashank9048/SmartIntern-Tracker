
import asyncio
from services.jobs_provider import ArbeitnowProvider
from api.routes.jobs import _is_job_current_and_upcoming

async def main():
    p = ArbeitnowProvider()
    jobs = await p.fetch_jobs()
    print("Fetched:", len(jobs))
    valid = [j for j in jobs if _is_job_current_and_upcoming(j)]
    print("Valid:", len(valid))
    if valid:
        print("First valid:", valid[0].application_url)

asyncio.run(main())

