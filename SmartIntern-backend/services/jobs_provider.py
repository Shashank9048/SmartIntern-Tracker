import os
import httpx
import logging
from abc import ABC, abstractmethod
from typing import List, Optional, Dict, Any
from datetime import datetime, timedelta
import asyncio

# Assuming models are in api.models (adjust import if needed)
from api.models import Job

logger = logging.getLogger(__name__)

class JobsProvider(ABC):
    """
    Interface for job data providers.
    """
    @abstractmethod
    async def fetch_jobs(self, query: str = "", location: str = "", limit: int = 20) -> List[Job]:
        pass

class MockJobsProvider(JobsProvider):
    """
    Returns realistic fixture postings for Indian tech internships/entry-level roles.
    """
    def __init__(self):
        self.fixtures = self._generate_fixtures()

    def _generate_fixtures(self) -> List[Job]:
        now = datetime.now()
        fixtures_data = [
            {
                "title": "Software Engineering Intern",
                "company": "Google",
                "location": "Bangalore, India",
                "description": "Join Google's engineering team as an intern. Work on core infrastructure, Search, or Cloud products.",
                "required_skills": ["Python", "C++", "Java", "Data Structures", "Algorithms"],
                "source": "mock"
            },
            {
                "title": "Frontend Developer Intern",
                "company": "Swiggy",
                "location": "Bangalore, India",
                "description": "Help build seamless user experiences for millions of Swiggy users. Work with React and Redux.",
                "required_skills": ["React", "JavaScript", "HTML", "CSS", "Redux"],
                "source": "mock"
            },
            {
                "title": "Backend Engineering Intern",
                "company": "Zomato",
                "location": "Gurgaon, India",
                "description": "Scale Zomato's backend systems. Experience with microservices and caching is a plus.",
                "required_skills": ["Node.js", "Python", "MongoDB", "Redis", "AWS"],
                "source": "mock"
            },
            {
                "title": "Data Science Intern",
                "company": "Flipkart",
                "location": "Bangalore, India",
                "description": "Analyze large datasets to improve e-commerce recommendation systems and supply chain logistics.",
                "required_skills": ["Python", "Pandas", "Machine Learning", "SQL", "Scikit-Learn"],
                "source": "mock"
            },
            {
                "title": "Full Stack Intern",
                "company": "Razorpay",
                "location": "Remote",
                "description": "Work on building robust payment gateways and modern dashboards for merchants.",
                "required_skills": ["React", "Node.js", "TypeScript", "PostgreSQL"],
                "source": "mock"
            },
            {
                "title": "SDE Intern (Entry Level)",
                "company": "Amazon",
                "location": "Hyderabad, India",
                "description": "Design and build scalable services for AWS. Strong problem-solving skills required.",
                "required_skills": ["Java", "C++", "System Design", "AWS"],
                "source": "mock"
            },
            {
                "title": "React Native Intern",
                "company": "Cred",
                "location": "Bangalore, India",
                "description": "Contribute to building the most premium credit card payment app in India.",
                "required_skills": ["React Native", "TypeScript", "Mobile Development"],
                "source": "mock"
            },
            {
                "title": "Machine Learning Intern",
                "company": "Ola",
                "location": "Bangalore, India",
                "description": "Optimize routing algorithms and pricing models using advanced machine learning techniques.",
                "required_skills": ["Python", "TensorFlow", "PyTorch", "Algorithms"],
                "source": "mock"
            },
            {
                "title": "DevOps Intern",
                "company": "PhonePe",
                "location": "Bangalore, India",
                "description": "Help manage highly available infrastructure and deployment pipelines.",
                "required_skills": ["Linux", "Docker", "Kubernetes", "CI/CD", "AWS"],
                "source": "mock"
            },
            {
                "title": "Product Analyst Intern",
                "company": "Paytm",
                "location": "Noida, India",
                "description": "Analyze user behavior and provide actionable insights for product development.",
                "required_skills": ["SQL", "Excel", "Data Analysis", "Python"],
                "source": "mock"
            },
            {
                "title": "UI/UX Design Intern",
                "company": "MakeMyTrip",
                "location": "Gurgaon, India",
                "description": "Design intuitive travel booking experiences for millions of users.",
                "required_skills": ["Figma", "UI/UX", "Prototyping", "User Research"],
                "source": "mock"
            },
            {
                "title": "Cloud Engineering Intern",
                "company": "Freshworks",
                "location": "Chennai, India",
                "description": "Learn to manage and scale cloud resources efficiently.",
                "required_skills": ["AWS", "Azure", "Linux", "Networking"],
                "source": "mock"
            },
            {
                "title": "Cybersecurity Intern",
                "company": "Zerodha",
                "location": "Remote",
                "description": "Assist in vulnerability assessments and ensuring platform security.",
                "required_skills": ["Network Security", "Ethical Hacking", "Python"],
                "source": "mock"
            },
            {
                "title": "Go Developer Intern",
                "company": "Gojek",
                "location": "Bangalore, India",
                "description": "Build high-throughput microservices using Golang.",
                "required_skills": ["Golang", "Microservices", "gRPC", "Docker"],
                "source": "mock"
            },
            {
                "title": "Android Developer Intern",
                "company": "ShareChat",
                "location": "Bangalore, India",
                "description": "Build features for India's largest vernacular social network.",
                "required_skills": ["Android", "Kotlin", "Java", "MVVM"],
                "source": "mock"
            },
            {
                "title": "iOS Developer Intern",
                "company": "Dream11",
                "location": "Mumbai, India",
                "description": "Create engaging experiences for fantasy sports enthusiasts on iOS.",
                "required_skills": ["Swift", "iOS", "Xcode", "UIKit"],
                "source": "mock"
            },
            {
                "title": "SDE-1 (Fresher)",
                "company": "Microsoft",
                "location": "Hyderabad, India",
                "description": "Join as an entry-level SDE working on Azure, Office, or Windows ecosystems.",
                "required_skills": ["C#", "C++", "System Design", "Algorithms"],
                "source": "mock"
            },
            {
                "title": "Junior Python Developer",
                "company": "Groww",
                "location": "Bangalore, India",
                "description": "Build scalable financial and investing tools. Fast-paced startup environment.",
                "required_skills": ["Python", "Django", "PostgreSQL", "REST APIs"],
                "source": "mock"
            },
            {
                "title": "Web Development Intern",
                "company": "Postman",
                "location": "Bangalore, India",
                "description": "Contribute to the world's leading API platform.",
                "required_skills": ["JavaScript", "React", "Node.js", "API Design"],
                "source": "mock"
            },
            {
                "title": "Game Developer Intern",
                "company": "MPL (Mobile Premier League)",
                "location": "Remote",
                "description": "Develop and optimize mobile games for the MPL platform.",
                "required_skills": ["Unity", "C#", "Game Design", "C++"],
                "source": "mock"
            }
        ]

        self.fixtures_data = fixtures_data

    async def fetch_jobs(self, query: str = "", location: str = "", limit: int = 20) -> List[Job]:
        now = datetime.now()
        jobs = []
        for i, item in enumerate(self.fixtures_data):
            posted_time = now - timedelta(days=i % 14, hours=i * 2)
            job = Job(
                title=item["title"],
                company=item["company"],
                description=item["description"],
                required_skills=item["required_skills"],
                location=item["location"],
                source=item["source"],
                external_id=f"mock-{i}",
                posted_at=posted_time
            )
            jobs.append(job)
            
        # Filter fixtures dynamically based on query
        filtered = jobs
        if query:
            q_lower = query.lower()
            filtered = [j for j in filtered if q_lower in j.title.lower() or q_lower in j.company.lower() or any(q_lower in s.lower() for s in j.required_skills)]
        if location:
            l_lower = location.lower()
            filtered = [j for j in filtered if l_lower in j.location.lower()]
            
        # Return limit
        return filtered[:limit]


class AdzunaProvider(JobsProvider):
    """
    Calls Adzuna using ADZUNA_APP_ID/ADZUNA_APP_KEY. 
    If those env vars are missing, returns nothing and logs a warning.
    """
    def __init__(self):
        self.app_id = os.getenv("ADZUNA_APP_ID")
        self.app_key = os.getenv("ADZUNA_APP_KEY")
        self.base_url = "https://api.adzuna.com/v1/api/jobs/in/search/1" # Default to India ('in')

    async def fetch_jobs(self, query: str = "", location: str = "", limit: int = 20) -> List[Job]:
        if not self.app_id or not self.app_key:
            logger.warning("ADZUNA_APP_ID or ADZUNA_APP_KEY is missing. Returning empty jobs from AdzunaProvider.")
            return []

        params = {
            "app_id": self.app_id,
            "app_key": self.app_key,
            "results_per_page": limit,
            "what": query,
            "where": location,
            "content-type": "application/json"
        }

        jobs = []
        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(self.base_url, params=params)
                response.raise_for_status()
                data = response.json()

                for result in data.get("results", []):
                    # Extract skills roughly from description or category if possible,
                    # Adzuna doesn't give a neat required_skills array
                    category = result.get("category", {}).get("label", "")
                    
                    job = Job(
                        title=result.get("title", ""),
                        company=result.get("company", {}).get("display_name", ""),
                        description=result.get("description", ""),
                        required_skills=[category] if category else [],
                        location=result.get("location", {}).get("display_name", ""),
                        source="adzuna",
                        external_id=str(result.get("id", "")),
                        posted_at=datetime.strptime(result.get("created"), "%Y-%m-%dT%H:%M:%SZ") if result.get("created") else datetime.now()
                    )
                    jobs.append(job)
        except Exception as e:
            logger.error(f"Error fetching jobs from Adzuna: {e}")

        return jobs
