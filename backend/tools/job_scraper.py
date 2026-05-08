"""
Job scraper tool using publicly available RSS feeds and free APIs.
No authentication required for any source.

Sources:
  1. Indeed RSS          — largest job board, all roles
  2. Himalayas API       — remote-first, high quality tech jobs, free public API
  3. Remotive API        — established remote tech job board, free API
  4. Jobicy API          — remote tech jobs, free public API
  5. Arbeitnow API       — global job board aggregator, free public API

How to add a new source:
  1. Create a function scrape_<source>(query, limit) -> List[Dict]
  2. Each job dict must have: title, company, url, description, location, salary, source, posted_date
  3. Add your function call inside fetch_all_jobs()
  4. That's it — deduplication and scoring happen automatically
"""

import requests
import xml.etree.ElementTree as ET
from bs4 import BeautifulSoup
from typing import List, Dict
import time
import logging
import os

logger = logging.getLogger(__name__)

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    )
}


def _clean_html(html: str, max_chars: int = 2000) -> str:
    """Strip HTML tags and truncate."""
    soup = BeautifulSoup(html, "html.parser")
    return soup.get_text(separator=" ").strip()[:max_chars]


# ── Source 1: Indeed RSS ──────────────────────────────────────────────────────

def scrape_indeed_rss(query: str, location: str = "remote", limit: int = 10) -> List[Dict]:
    """
    Indeed public RSS feed. No auth required.
    Best for: US-based roles, all industries, most popular job board worldwide.
    """
    jobs = []
    try:
        q = query.replace(" ", "+")
        loc = location.replace(" ", "+")
        url = f"https://www.indeed.com/rss?q={q}&l={loc}&sort=date&limit={limit}"
        resp = requests.get(url, headers=HEADERS, timeout=15)
        if resp.status_code != 200:
            logger.warning(f"Indeed RSS: HTTP {resp.status_code}")
            return []

        root = ET.fromstring(resp.content)
        channel = root.find("channel")
        if channel is None:
            return []

        for item in channel.findall("item")[:limit]:
            title_raw = item.findtext("title", "").strip()
            link = item.findtext("link", "").strip()
            description_raw = item.findtext("description", "")
            pub_date = item.findtext("pubDate", "")

            description = _clean_html(description_raw)

            # Indeed format: "Job Title - Company Name"
            parts = title_raw.split(" - ")
            job_title = parts[0].strip() if parts else title_raw
            company = parts[1].strip() if len(parts) > 1 else "Unknown"

            if job_title and link:
                jobs.append({
                    "title": job_title,
                    "company": company,
                    "location": location,
                    "url": link,
                    "description": description,
                    "salary": "",
                    "source": "indeed",
                    "posted_date": pub_date,
                })
            time.sleep(0.05)

    except Exception as e:
        logger.error(f"Indeed RSS error: {e}")

    logger.info(f"Indeed: fetched {len(jobs)} jobs")
    return jobs


# ── Source 2: Himalayas API ───────────────────────────────────────────────────

def scrape_himalayas(query: str, limit: int = 10) -> List[Dict]:
    """
    Himalayas free public API. No auth required.
    Best for: high-quality remote tech jobs, well-structured data.
    Docs: https://himalayas.app/api
    """
    jobs = []
    try:
        url = "https://himalayas.app/jobs/api/search"
        params = {
            "q": query,
            "limit": min(limit, 20),  # API max is 20 per request
        }
        resp = requests.get(url, params=params, headers=HEADERS, timeout=15)
        if resp.status_code != 200:
            logger.warning(f"Himalayas API: HTTP {resp.status_code}")
            return []

        data = resp.json()
        for job in data.get("jobs", [])[:limit]:
            description = _clean_html(job.get("description", ""))
            location_parts = []
            if job.get("locations"):
                location_parts = [loc.get("name", "") for loc in job["locations"]]
            location = ", ".join(location_parts) if location_parts else "Remote"

            salary = ""
            if job.get("salaryMin") and job.get("salaryMax"):
                salary = f"${job['salaryMin']:,} - ${job['salaryMax']:,}"

            jobs.append({
                "title": job.get("title", ""),
                "company": job.get("company", {}).get("name", ""),
                "location": location,
                "url": job.get("applicationLink", job.get("url", "")),
                "description": description,
                "salary": salary,
                "source": "himalayas",
                "posted_date": job.get("createdAt", ""),
            })

    except Exception as e:
        logger.error(f"Himalayas API error: {e}")

    logger.info(f"Himalayas: fetched {len(jobs)} jobs")
    return jobs


# ── Source 3: Remotive API ────────────────────────────────────────────────────

def scrape_remotive(query: str, limit: int = 10) -> List[Dict]:
    """
    Remotive free public API. No auth required.
    Best for: established remote tech jobs, good description quality.
    Docs: https://remotive.com/api/remote-jobs
    """
    jobs = []
    try:
        url = f"https://remotive.com/api/remote-jobs?search={query}&limit={limit}"
        resp = requests.get(url, headers=HEADERS, timeout=15)
        if resp.status_code != 200:
            logger.warning(f"Remotive API: HTTP {resp.status_code}")
            return []

        data = resp.json()
        for job in data.get("jobs", [])[:limit]:
            description = _clean_html(job.get("description", ""))
            jobs.append({
                "title": job.get("title", ""),
                "company": job.get("company_name", ""),
                "location": job.get("candidate_required_location", "Remote"),
                "url": job.get("url", ""),
                "description": description,
                "salary": job.get("salary", ""),
                "source": "remotive",
                "posted_date": job.get("publication_date", ""),
            })

    except Exception as e:
        logger.error(f"Remotive API error: {e}")

    logger.info(f"Remotive: fetched {len(jobs)} jobs")
    return jobs


# ── Source 4: Jobicy API ──────────────────────────────────────────────────────

def scrape_jobicy(query: str, limit: int = 10) -> List[Dict]:
    """
    Jobicy free public API. No auth required.
    Best for: remote tech and startup jobs, good global coverage.
    Docs: https://jobicy.com/api/v2/remote-jobs
    """
    jobs = []
    try:
        url = "https://jobicy.com/api/v2/remote-jobs"
        params = {
            "count": min(limit, 50),
            "tag": query.split()[0],  # Jobicy uses single tag keywords best
        }
        resp = requests.get(url, params=params, headers=HEADERS, timeout=15)
        if resp.status_code != 200:
            logger.warning(f"Jobicy API: HTTP {resp.status_code}")
            return []

        data = resp.json()
        for job in data.get("jobs", [])[:limit]:
            description = _clean_html(job.get("jobDescription", ""))
            salary = job.get("annualSalaryMin", "")
            if salary and job.get("annualSalaryMax"):
                salary = f"${salary:,} - ${job['annualSalaryMax']:,}"
            elif salary:
                salary = f"${salary:,}+"

            # Filter by query relevance since Jobicy tag matching is broad
            title = job.get("jobTitle", "")
            query_lower = query.lower()
            if not any(word in title.lower() or word in description.lower()
                       for word in query_lower.split()[:3]):
                continue

            jobs.append({
                "title": title,
                "company": job.get("companyName", ""),
                "location": job.get("jobGeo", "Remote"),
                "url": job.get("url", ""),
                "description": description,
                "salary": str(salary) if salary else "",
                "source": "jobicy",
                "posted_date": job.get("pubDate", ""),
            })

    except Exception as e:
        logger.error(f"Jobicy API error: {e}")

    logger.info(f"Jobicy: fetched {len(jobs)} jobs")
    return jobs


# ── Source 5: Arbeitnow API ───────────────────────────────────────────────────

def scrape_arbeitnow(query: str, limit: int = 10) -> List[Dict]:
    """
    Arbeitnow free public API. No auth required.
    Best for: global job board aggregating from ATS systems, good for tech roles.
    Docs: https://www.arbeitnow.com/blog/job-board-api
    """
    jobs = []
    try:
        url = "https://www.arbeitnow.com/api/job-board-api"
        resp = requests.get(url, headers=HEADERS, timeout=15)
        if resp.status_code != 200:
            logger.warning(f"Arbeitnow API: HTTP {resp.status_code}")
            return []

        data = resp.json()
        query_lower = query.lower()
        query_words = query_lower.split()

        count = 0
        for job in data.get("data", []):
            if count >= limit:
                break

            title = job.get("title", "")
            description_raw = job.get("description", "")
            tags = [t.lower() for t in job.get("tags", [])]

            # Filter by relevance
            title_lower = title.lower()
            description_text = _clean_html(description_raw, 500).lower()
            relevant = any(
                word in title_lower or word in tags or word in description_text
                for word in query_words[:3]
            )
            if not relevant:
                continue

            description = _clean_html(description_raw)
            location = job.get("location", "Remote")
            if job.get("remote"):
                location = "Remote" if location == "" else f"{location} (Remote)"

            jobs.append({
                "title": title,
                "company": job.get("company_name", ""),
                "location": location,
                "url": job.get("url", ""),
                "description": description,
                "salary": "",
                "source": "arbeitnow",
                "posted_date": str(job.get("created_at", "")),
            })
            count += 1

    except Exception as e:
        logger.error(f"Arbeitnow API error: {e}")

    logger.info(f"Arbeitnow: fetched {len(jobs)} jobs")
    return jobs




# ── Source 6: JSearch via RapidAPI ───────────────────────────────────────────

def scrape_jsearch(query: str, location: str = "", limit: int = 10) -> List[Dict]:
    """
    JSearch API via RapidAPI. Requires RAPIDAPI_KEY in .env
    Covers: LinkedIn, Indeed, Glassdoor, ZipRecruiter, Dice, Monster, and more.
    This is the single most comprehensive job data source available.

    Free tier: 200 requests/month
    Paid tier: $10/month for 500 requests, $30/month for 2000 requests

    How to get API key:
    1. Go to rapidapi.com → Sign Up (free)
    2. Search "JSearch" → Subscribe → Free plan
    3. Copy X-RapidAPI-Key from the Endpoints tab
    4. Add to your .env as RAPIDAPI_KEY=your_key_here
    """
    api_key = os.getenv("RAPIDAPI_KEY", "")
    if not api_key:
        logger.info("JSearch: No RAPIDAPI_KEY set — skipping. Add to .env to enable LinkedIn/Indeed/Dice coverage.")
        return []

    jobs = []
    try:
        search_query = f"{query} in {location}" if location and location.lower() != "remote" else query
        if location.lower() == "remote":
            search_query = f"{query} remote"

        url = "https://jsearch.p.rapidapi.com/search"
        headers = {
            "X-RapidAPI-Key": api_key,
            "X-RapidAPI-Host": "jsearch.p.rapidapi.com",
        }
        params = {
            "query": search_query,
            "page": "1",
            "num_pages": "1",
            "date_posted": "week",          # Jobs posted in last 7 days
            "remote_jobs_only": "false",
        }

        resp = requests.get(url, headers=headers, params=params, timeout=20)
        if resp.status_code == 403:
            logger.warning("JSearch: Invalid or expired API key")
            return []
        if resp.status_code != 200:
            logger.warning(f"JSearch API: HTTP {resp.status_code}")
            return []

        data = resp.json()
        for job in data.get("data", [])[:limit]:
            # Build salary string
            salary = ""
            sal_min = job.get("job_min_salary")
            sal_max = job.get("job_max_salary")
            sal_currency = job.get("job_salary_currency", "USD")
            sal_period = job.get("job_salary_period", "")
            if sal_min and sal_max:
                salary = f"{sal_currency} {sal_min:,.0f} - {sal_max:,.0f} {sal_period}".strip()
            elif sal_min:
                salary = f"{sal_currency} {sal_min:,.0f}+ {sal_period}".strip()

            # Location
            city = job.get("job_city", "")
            state = job.get("job_state", "")
            country = job.get("job_country", "")
            if job.get("job_is_remote"):
                loc = "Remote"
            elif city and state:
                loc = f"{city}, {state}"
            elif city:
                loc = f"{city}, {country}"
            else:
                loc = country or "USA"

            # Apply URL — prefer direct company URL
            apply_links = job.get("job_apply_link", "")
            apply_options = job.get("apply_options", [])
            if apply_options:
                apply_url = apply_options[0].get("apply_link", apply_links)
            else:
                apply_url = apply_links

            description = (job.get("job_description", "") or "")[:2000]

            # Source attribution — which board this job came from
            publisher = job.get("job_publisher", "jsearch").lower()
            source_name = "jsearch"
            if "linkedin" in publisher:
                source_name = "linkedin"
            elif "indeed" in publisher:
                source_name = "indeed"
            elif "dice" in publisher:
                source_name = "dice"
            elif "glassdoor" in publisher:
                source_name = "glassdoor"
            elif "ziprecruiter" in publisher:
                source_name = "ziprecruiter"

            jobs.append({
                "title": job.get("job_title", ""),
                "company": job.get("employer_name", ""),
                "location": loc,
                "url": apply_url,
                "description": description,
                "salary": salary,
                "source": source_name,
                "posted_date": job.get("job_posted_at_datetime_utc", ""),
            })

    except Exception as e:
        logger.error(f"JSearch API error: {e}")

    logger.info(f"JSearch: fetched {len(jobs)} jobs")
    return jobs

def fetch_all_jobs(
    query: str,
    location: str = "remote",
    limit_per_source: int = 5,
) -> List[Dict]:
    """
    Aggregate jobs from all 5 sources and deduplicate by URL.

    To add a new job source:
    1. Create a scrape_<source>() function following the pattern above
    2. Add it to the SOURCES list below
    3. Done — scoring and deduplication happen automatically

    Sources used:
    - Indeed RSS      (all roles, US-focused)
    - Himalayas API   (remote tech, high quality)
    - Remotive API    (remote tech)
    - Jobicy API      (remote tech + startups)
    - Arbeitnow API   (global, aggregated from ATS)
    """
    SOURCES = [
        ("Indeed RSS",    lambda: scrape_indeed_rss(query, location, limit_per_source)),
        ("Himalayas",     lambda: scrape_himalayas(query, limit_per_source)),
        ("Remotive",      lambda: scrape_remotive(query, limit_per_source)),
        ("Jobicy",        lambda: scrape_jobicy(query, limit_per_source)),
        ("Arbeitnow",     lambda: scrape_arbeitnow(query, limit_per_source)),
        # JSearch: LinkedIn + Indeed + Dice + Glassdoor + ZipRecruiter in one API
        # Requires RAPIDAPI_KEY in .env — free tier 200 req/month at rapidapi.com
        ("JSearch",       lambda: scrape_jsearch(query, location, limit_per_source * 2)),
    ]

    all_jobs = []
    for name, scraper in SOURCES:
        try:
            logger.info(f"Fetching from {name}...")
            results = scraper()
            all_jobs.extend(results)
            logger.info(f"{name}: {len(results)} jobs")
        except Exception as e:
            logger.error(f"{name} failed: {e}")

    # Deduplicate by URL
    seen_urls = set()
    unique_jobs = []
    for job in all_jobs:
        url = job.get("url", "").strip()
        if url and url not in seen_urls:
            seen_urls.add(url)
            # Skip jobs with empty title or company
            if job.get("title") and job.get("company"):
                unique_jobs.append(job)

    logger.info(f"Total unique jobs: {len(unique_jobs)} from {len(all_jobs)} fetched")
    return unique_jobs

