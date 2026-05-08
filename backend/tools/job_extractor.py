"""
Job Content Extractor
----------------------
Given a URL (LinkedIn, Indeed, Dice, any job board) or raw JD text,
extracts structured job information for ATS scoring and AI analysis.

Handles:
  - Raw job description text (paste directly)
  - Any job board URL (fetches and parses the page)
  - Extracts title, company, location, salary, description intelligently
"""

import re
import requests
from bs4 import BeautifulSoup
from typing import Dict
import logging

logger = logging.getLogger(__name__)

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "en-US,en;q=0.9",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
}


def extract_from_url(url: str) -> Dict:
    """
    Fetch a job posting page and extract structured information.
    Works with any publicly accessible job URL.
    """
    try:
        resp = requests.get(url, headers=HEADERS, timeout=20)
        resp.raise_for_status()
        html = resp.text
    except requests.exceptions.RequestException as e:
        logger.warning(f"Could not fetch URL {url}: {e}")
        return _empty_job(url=url, source="manual")

    soup = BeautifulSoup(html, "html.parser")

    # Remove noise elements
    for tag in soup.find_all(["script", "style", "nav", "footer",
                               "header", "noscript", "iframe"]):
        tag.decompose()

    # ── Title extraction ──────────────────────────────────────────────────────
    title = ""
    # Try structured meta first (most reliable)
    for sel in [
        'meta[property="og:title"]',
        'meta[name="twitter:title"]',
    ]:
        el = soup.select_one(sel)
        if el and el.get("content"):
            title = el["content"].strip()
            break

    if not title:
        for sel in [
            "h1.job-title", "h1.jobTitle", "h1[data-testid='jobTitle']",
            ".job-title h1", ".jobsearch-JobInfoHeader-title", "h1",
        ]:
            el = soup.select_one(sel)
            if el:
                title = el.get_text(strip=True)
                break

    # Clean up title — remove site name suffix
    title = re.sub(r"\s*[\|\-–]\s*(LinkedIn|Indeed|Glassdoor|Dice|ZipRecruiter|Lever|Greenhouse).*$",
                   "", title, flags=re.IGNORECASE).strip()

    # ── Company extraction ────────────────────────────────────────────────────
    company = ""
    for sel in [
        'meta[property="og:site_name"]',
        '[data-testid="InlineCompanyName"]',
        ".jobsearch-CompanyInfoWithoutLink",
        ".company-name",
        '[class*="companyName"]',
        '[class*="company-name"]',
    ]:
        el = soup.select_one(sel)
        if el:
            text = el.get("content", "") or el.get_text(strip=True)
            if text and len(text) < 100:
                company = text.strip()
                break

    # ── Location extraction ───────────────────────────────────────────────────
    location = ""
    for sel in [
        '[data-testid="job-location"]',
        ".jobsearch-JobInfoHeader-locationContainer",
        '[class*="location"]',
        '[class*="Location"]',
    ]:
        el = soup.select_one(sel)
        if el:
            location = el.get_text(strip=True)
            break

    if not location:
        # Try meta description for location hints
        desc_meta = soup.select_one('meta[name="description"]')
        if desc_meta:
            content = desc_meta.get("content", "")
            loc_match = re.search(
                r'\b([A-Z][a-z]+,\s*[A-Z]{2}|Remote|Hybrid)\b', content
            )
            if loc_match:
                location = loc_match.group(1)

    # ── Salary extraction ─────────────────────────────────────────────────────
    salary = ""
    salary_pattern = re.compile(
        r'\$[\d,]+(?:\s*[-–]\s*\$[\d,]+)?(?:\s*(?:K|k|per\s+year|/yr|/year|annually))?',
        re.IGNORECASE,
    )
    page_text = soup.get_text(" ")
    salary_match = salary_pattern.search(page_text)
    if salary_match:
        salary = salary_match.group(0).strip()

    # ── Description extraction ────────────────────────────────────────────────
    description = ""

    # Priority selectors for job description containers
    desc_selectors = [
        # Indeed
        "#jobDescriptionText",
        ".jobsearch-jobDescriptionText",
        # LinkedIn
        ".description__text",
        ".job-description",
        '[class*="description"]',
        # Greenhouse/Lever/Workday ATS
        "#content",
        ".posting-description",
        "[data-automation='jobDescription']",
        # Dice
        ".job-description-section",
        # Generic
        "article",
        "main",
    ]

    for sel in desc_selectors:
        el = soup.select_one(sel)
        if el:
            text = el.get_text(separator="\n", strip=True)
            if len(text) > 200:  # Must have meaningful content
                description = text[:4000]
                break

    # Fallback: body text
    if not description:
        description = soup.get_text(separator="\n", strip=True)[:4000]

    # ── Determine source from URL ─────────────────────────────────────────────
    source = _detect_source(url)

    return {
        "title": title or "Job Opening",
        "company": company or "Unknown Company",
        "location": location or "See job posting",
        "url": url,
        "description": description,
        "salary": salary,
        "source": source,
        "posted_date": "",
    }


def extract_from_text(raw_text: str) -> Dict:
    """
    Parse a raw job description text (pasted directly by user).
    Extracts title, company, location, salary heuristically.
    """
    text = raw_text.strip()

    # ── Title: first non-empty line or line containing "engineer/developer/manager"
    lines = [l.strip() for l in text.split("\n") if l.strip()]
    title = lines[0] if lines else "Pasted Job"

    # If first line is very long it's probably a description, not title
    if len(title) > 100:
        # Try to find a shorter title-like line in first 5 lines
        for line in lines[:5]:
            if 10 < len(line) < 80:
                title = line
                break

    # ── Company: look for "at <Company>" or "Company:" patterns
    company = ""
    company_patterns = [
        r'(?:at|@)\s+([A-Z][A-Za-z0-9\s&.,]+?)(?:\s*[\|\-–\n]|$)',
        r'Company:\s*(.+?)(?:\n|$)',
        r'Employer:\s*(.+?)(?:\n|$)',
    ]
    for pat in company_patterns:
        m = re.search(pat, text[:500])
        if m:
            company = m.group(1).strip()[:80]
            break

    # ── Location
    location = ""
    loc_match = re.search(
        r'\b(Remote|Hybrid|On-?site|[A-Z][a-z]+,\s*[A-Z]{2}(?:\s+\d{5})?)\b',
        text[:1000]
    )
    if loc_match:
        location = loc_match.group(1)

    # ── Salary
    salary = ""
    salary_match = re.search(
        r'\$[\d,]+(?:\s*[-–k]?\s*\$?[\d,]+)?(?:\s*(?:K|k|per year|\/yr|annually))?',
        text,
        re.IGNORECASE,
    )
    if salary_match:
        salary = salary_match.group(0).strip()

    return {
        "title": title,
        "company": company or "Unknown Company",
        "location": location or "See description",
        "url": "",          # No URL for pasted content
        "description": text[:4000],
        "salary": salary,
        "source": "manual",
        "posted_date": "",
    }


def _detect_source(url: str) -> str:
    """Detect job board from URL."""
    url_lower = url.lower()
    if "linkedin.com" in url_lower:
        return "linkedin"
    if "indeed.com" in url_lower:
        return "indeed"
    if "dice.com" in url_lower:
        return "dice"
    if "glassdoor.com" in url_lower:
        return "glassdoor"
    if "ziprecruiter.com" in url_lower:
        return "ziprecruiter"
    if "lever.co" in url_lower:
        return "lever"
    if "greenhouse.io" in url_lower or "boards.greenhouse" in url_lower:
        return "greenhouse"
    if "workday.com" in url_lower:
        return "workday"
    if "jobs.google.com" in url_lower or "careers.google" in url_lower:
        return "google"
    if "careers." in url_lower or "/careers" in url_lower or "jobs." in url_lower or "/jobs" in url_lower:
        return "company_careers"
    return "manual"


def _empty_job(url: str = "", source: str = "manual") -> Dict:
    return {
        "title": "",
        "company": "",
        "location": "",
        "url": url,
        "description": "",
        "salary": "",
        "source": source,
        "posted_date": "",
    }


def is_url(text: str) -> bool:
    """Check if input looks like a URL."""
    text = text.strip()
    return text.startswith(("http://", "https://", "www."))
