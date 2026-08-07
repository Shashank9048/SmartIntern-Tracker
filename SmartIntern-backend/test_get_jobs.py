
import asyncio
from services.jobs_provider import ArbeitnowProvider
from api.routes.jobs import _is_job_current_and_upcoming

async def main():
    try:
        p = ArbeitnowProvider()
        jobs = await p._fetch_fresh(limit=50)
        print("Raw fetched:", len(jobs))
        valid = [j for j in jobs if _is_job_current_and_upcoming(j) and j.application_url and j.application_url.startswith("http")]
        print("Valid after filtering:", len(valid))
    except Exception as e:
        print("Error:", e)

asyncio.run(main())

