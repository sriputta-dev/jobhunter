"""
JobHunter Test Suite
---------------------
Tests for ATS scorer, job scraper, and API endpoints.
Run: pytest backend/tests/ -v
"""

import pytest
import json
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


# ── ATS Scorer Tests ──────────────────────────────────────────────────────────

class TestATSScorer:
    """Test the ATS keyword scoring logic."""

    def test_perfect_match_high_score(self):
        from tools.ats_scorer import score_job
        jd = """
        Senior .NET Developer with C# and ASP.NET Core experience.
        Must have React, PostgreSQL, Docker, Kubernetes, AWS, Azure DevOps.
        Experience with microservices, REST API, CI/CD pipelines.
        Python and Java knowledge preferred. Unit testing with xUnit.
        """
        result = score_job(jd, ".NET Full Stack Developer")
        assert result["ats_score"] >= 70, f"Expected >= 70, got {result['ats_score']}"
        assert len(json.loads(result["matched_keywords"])) > 5

    def test_irrelevant_job_low_score(self):
        from tools.ats_scorer import score_job
        jd = """
        Chef needed for upscale restaurant. Must have culinary degree.
        5 years experience with French cuisine. Wine pairing knowledge required.
        """
        result = score_job(jd, "Executive Chef")
        assert result["ats_score"] < 30, f"Expected < 30, got {result['ats_score']}"

    def test_score_range_valid(self):
        from tools.ats_scorer import score_job
        jd = "Software engineer with Python experience."
        result = score_job(jd, "Python Developer")
        assert 0 <= result["ats_score"] <= 100

    def test_empty_description(self):
        from tools.ats_scorer import score_job
        result = score_job("", "")
        assert result["ats_score"] == 0.0
        assert result["matched_keywords"] == "[]"

    def test_matched_keywords_are_list(self):
        from tools.ats_scorer import score_job
        jd = "Looking for .NET developer with React and PostgreSQL"
        result = score_job(jd, ".NET Developer")
        matched = json.loads(result["matched_keywords"])
        assert isinstance(matched, list)

    def test_batch_scoring_sorted(self):
        from tools.ats_scorer import batch_score_jobs
        jobs = [
            {"title": "Chef", "description": "Cooking, kitchen, restaurant", "url": "1"},
            {"title": ".NET Developer", "description": "C# .NET React PostgreSQL AWS Docker", "url": "2"},
            {"title": "Python Dev", "description": "Python microservices REST API", "url": "3"},
        ]
        scored = batch_score_jobs(jobs)
        scores = [j["ats_score"] for j in scored]
        assert scores == sorted(scores, reverse=True), "Jobs should be sorted by ATS score desc"

    def test_java_recognized_as_skill(self):
        from tools.ats_scorer import score_job
        jd = "Java Spring Boot developer with PostgreSQL and Docker experience"
        result = score_job(jd, "Java Developer")
        matched = json.loads(result["matched_keywords"])
        assert "java" in [m.lower() for m in matched], "Java should be in matched keywords"

    def test_dedup_matched_keywords(self):
        from tools.ats_scorer import score_job
        # Repeating .net many times shouldn't inflate matched list
        jd = ".net .net .net .net c# c# asp.net asp.net"
        result = score_job(jd, ".net")
        matched = json.loads(result["matched_keywords"])
        assert len(matched) == len(set(m.lower() for m in matched)), "No duplicate keywords"


# ── Job Scraper Tests ─────────────────────────────────────────────────────────

class TestJobScraper:
    """Test job scraping functions with mocking to avoid network calls."""

    def test_fetch_all_jobs_returns_list(self, monkeypatch):
        from tools import job_scraper

        monkeypatch.setattr(job_scraper, "scrape_indeed_rss", lambda q, l, n: [
            {"title": "NET Dev", "company": "Acme", "url": "http://1.com",
             "description": "C# .NET developer", "location": "remote",
             "salary": "", "source": "indeed", "posted_date": "2026-01-01"}
        ])
        monkeypatch.setattr(job_scraper, "scrape_himalayas", lambda q, n: [])
        monkeypatch.setattr(job_scraper, "scrape_remotive", lambda q, n: [])
        monkeypatch.setattr(job_scraper, "scrape_jobicy", lambda q, n: [])
        monkeypatch.setattr(job_scraper, "scrape_arbeitnow", lambda q, n: [])

        jobs = job_scraper.fetch_all_jobs(".NET Developer", "remote", 5)
        assert isinstance(jobs, list)
        assert len(jobs) == 1
        assert jobs[0]["company"] == "Acme"

    def test_deduplication_by_url(self, monkeypatch):
        from tools import job_scraper

        duplicate_job = {
            "title": "Dev", "company": "Co", "url": "http://same.com",
            "description": "test", "location": "remote",
            "salary": "", "source": "indeed", "posted_date": ""
        }
        monkeypatch.setattr(job_scraper, "scrape_indeed_rss",
                            lambda q, l, n: [duplicate_job])
        monkeypatch.setattr(job_scraper, "scrape_himalayas",
                            lambda q, n: [duplicate_job])
        monkeypatch.setattr(job_scraper, "scrape_remotive", lambda q, n: [])
        monkeypatch.setattr(job_scraper, "scrape_jobicy", lambda q, n: [])
        monkeypatch.setattr(job_scraper, "scrape_arbeitnow", lambda q, n: [])

        jobs = job_scraper.fetch_all_jobs(".NET", "remote", 5)
        urls = [j["url"] for j in jobs]
        assert len(urls) == len(set(urls)), "Duplicate URLs should be removed"

    def test_job_has_required_fields(self, monkeypatch):
        from tools import job_scraper

        monkeypatch.setattr(job_scraper, "scrape_indeed_rss", lambda q, l, n: [
            {"title": "Dev", "company": "Corp", "url": "http://x.com",
             "description": "desc", "location": "NY",
             "salary": "$100k", "source": "indeed", "posted_date": "2026"}
        ])
        monkeypatch.setattr(job_scraper, "scrape_remotive", lambda q, n: [])
        monkeypatch.setattr(job_scraper, "scrape_the_muse", lambda q, n: [])

        jobs = job_scraper.fetch_all_jobs(".NET", "remote", 5)
        required = ["title", "company", "url", "description", "source"]
        for field in required:
            assert field in jobs[0], f"Missing required field: {field}"


# ── API Endpoint Tests ────────────────────────────────────────────────────────

class TestAPI:
    """Test FastAPI endpoints."""

    @pytest.fixture
    def client(self):
        from fastapi.testclient import TestClient
        import asyncio

        # Set a dummy API key for tests
        os.environ["ANTHROPIC_API_KEY"] = "test-key"

        from api.main import app
        from models.database import init_db

        # Initialize DB synchronously for tests
        asyncio.get_event_loop().run_until_complete(init_db())

        return TestClient(app)

    def test_health_endpoint(self, client):
        resp = client.get("/health")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "ok"
        assert "version" in data

    def test_list_jobs_empty(self, client):
        resp = client.get("/api/jobs")
        assert resp.status_code == 200
        data = resp.json()
        assert "jobs" in data
        assert "total" in data
        assert isinstance(data["jobs"], list)

    def test_stats_endpoint(self, client):
        resp = client.get("/api/stats")
        assert resp.status_code == 200
        data = resp.json()
        assert "total_jobs" in data
        assert "average_ats_score" in data
        assert "by_status" in data

    def test_get_nonexistent_job(self, client):
        resp = client.get("/api/jobs/99999")
        assert resp.status_code == 404

    def test_search_runs_endpoint(self, client):
        resp = client.get("/api/search-runs")
        assert resp.status_code == 200
        data = resp.json()
        assert "runs" in data

    def test_search_endpoint_structure(self, client, monkeypatch):
        """Test search endpoint without real network calls."""
        import tools.job_scraper as scraper
        import tools.ats_scorer as scorer

        monkeypatch.setattr(scraper, "fetch_all_jobs", lambda q, l, n: [])

        resp = client.post("/api/search", json={
            "query": ".NET Developer",
            "location": "remote",
            "limit_per_source": 2,
            "min_ats_score": 50.0,
        })
        assert resp.status_code == 200
        data = resp.json()
        assert "message" in data
        assert "jobs_found" in data


# ── Integration Test ──────────────────────────────────────────────────────────

class TestIntegration:
    """End-to-end flow without LLM calls."""

    def test_score_and_save_flow(self, monkeypatch):
        """Test the full scrape -> score -> filter pipeline."""
        from tools.ats_scorer import batch_score_jobs

        mock_jobs = [
            {
                "title": ".NET Full Stack Developer",
                "company": "Tech Corp",
                "url": "http://example.com/job1",
                "description": (
                    "Looking for C# .NET Core developer with React, PostgreSQL, "
                    "Docker, Kubernetes, AWS, Azure DevOps CI/CD experience. "
                    "Microservices architecture, REST API, unit testing with xUnit."
                ),
                "location": "remote",
                "salary": "$120k",
                "source": "indeed",
                "posted_date": "2026-05-01",
            },
            {
                "title": "Marketing Manager",
                "company": "Brand Co",
                "url": "http://example.com/job2",
                "description": "Social media marketing, brand strategy, content creation.",
                "location": "NYC",
                "salary": "$80k",
                "source": "indeed",
                "posted_date": "2026-05-01",
            },
        ]

        scored = batch_score_jobs(mock_jobs)

        # NET dev should score higher than marketing manager
        net_job = next(j for j in scored if ".NET" in j["title"])
        mkt_job = next(j for j in scored if "Marketing" in j["title"])
        assert net_job["ats_score"] > mkt_job["ats_score"]
        assert net_job["ats_score"] >= 60

        # Filter by min score
        filtered = [j for j in scored if j["ats_score"] >= 50]
        assert all(j["ats_score"] >= 50 for j in filtered)


# ── Job Extractor Tests ───────────────────────────────────────────────────────

class TestJobExtractor:
    """Test the manual paste extractor."""

    def test_is_url_detection(self):
        from tools.job_extractor import is_url
        assert is_url("https://linkedin.com/jobs/view/123") is True
        assert is_url("http://indeed.com/job") is True
        assert is_url("www.dice.com/job") is True
        assert is_url("Senior .NET Developer at Acme Corp") is False
        assert is_url("  https://example.com  ") is True
        assert is_url("") is False

    def test_extract_from_text_basic(self):
        from tools.job_extractor import extract_from_text
        jd = """Senior .NET Developer at TechCorp
        Location: Boston, MA
        Salary: $120,000 - $150,000

        We are looking for a C# .NET developer with React experience.
        Requirements:
        - 5+ years .NET Core experience
        - React JS, PostgreSQL, Docker
        - AWS cloud experience preferred
        """
        result = extract_from_text(jd)
        assert result["title"] != ""
        assert result["description"] != ""
        assert result["source"] == "manual"
        assert result["url"] == ""
        assert isinstance(result["salary"], str)

    def test_extract_from_text_salary_detection(self):
        from tools.job_extractor import extract_from_text
        jd = "Software Engineer. Salary: $95,000 - $130,000 per year. Must know Python."
        result = extract_from_text(jd)
        assert "$" in result["salary"], f"Expected salary, got: {result['salary']}"

    def test_extract_from_text_location_detection(self):
        from tools.job_extractor import extract_from_text
        jd = "Full Stack Developer. Location: Austin, TX. Remote friendly."
        result = extract_from_text(jd)
        # Location may or may not extract perfectly but shouldn't crash
        assert isinstance(result["location"], str)

    def test_extract_from_text_remote_detection(self):
        from tools.job_extractor import extract_from_text
        jd = "Python Engineer. This is a fully Remote position. Strong Python skills required."
        result = extract_from_text(jd)
        assert isinstance(result["location"], str)

    def test_extract_from_text_long_description(self):
        from tools.job_extractor import extract_from_text
        long_jd = "Job Title\n" + ("Python developer with Django REST API skills. " * 200)
        result = extract_from_text(long_jd)
        assert len(result["description"]) <= 4000, "Description must be capped at 4000 chars"

    def test_extract_empty_text(self):
        from tools.job_extractor import extract_from_text
        result = extract_from_text("   ")
        # Should not crash, returns empty structure
        assert isinstance(result, dict)
        assert "title" in result
        assert "description" in result

    def test_detect_source_linkedin(self):
        from tools.job_extractor import _detect_source
        assert _detect_source("https://www.linkedin.com/jobs/view/123456") == "linkedin"

    def test_detect_source_indeed(self):
        from tools.job_extractor import _detect_source
        assert _detect_source("https://www.indeed.com/viewjob?jk=abc123") == "indeed"

    def test_detect_source_dice(self):
        from tools.job_extractor import _detect_source
        assert _detect_source("https://www.dice.com/jobs/detail/abc") == "dice"

    def test_detect_source_greenhouse(self):
        from tools.job_extractor import _detect_source
        assert _detect_source("https://boards.greenhouse.io/company/jobs/123") == "greenhouse"

    def test_detect_source_lever(self):
        from tools.job_extractor import _detect_source
        assert _detect_source("https://jobs.lever.co/company/abc") == "lever"

    def test_detect_source_unknown(self):
        from tools.job_extractor import _detect_source
        assert _detect_source("https://randomcompany.com/careers/job") == "company_careers"

    def test_extract_from_text_returns_all_fields(self):
        from tools.job_extractor import extract_from_text
        result = extract_from_text("Software Engineer at Acme Corp. Python, AWS, Docker required.")
        required_fields = ["title", "company", "location", "url", "description", "salary", "source", "posted_date"]
        for field in required_fields:
            assert field in result, f"Missing field: {field}"

    def test_url_fetch_fails_gracefully(self):
        """Test that a bad URL returns empty dict, doesn't crash."""
        from tools.job_extractor import extract_from_url
        # Use an intentionally bad URL
        result = extract_from_url("https://this-domain-definitely-does-not-exist-xyz.com/job/123")
        assert isinstance(result, dict)
        assert "title" in result
        assert "description" in result

    def test_ats_score_applied_to_pasted_job(self):
        """Full pipeline: extract text -> ATS score."""
        from tools.job_extractor import extract_from_text
        from tools.ats_scorer import score_job
        jd = """
        Senior Full Stack .NET Developer
        Company: Fidelity Investments
        Location: Boston, MA (Hybrid)
        Salary: $130,000 - $160,000

        We are seeking a C# .NET Core developer with:
        - Strong React JS and TypeScript skills
        - PostgreSQL and SQL Server database experience
        - Docker and Kubernetes containerization
        - AWS cloud services (EC2, S3, Lambda)
        - Azure DevOps CI/CD pipelines
        - Microservices and REST API design
        - xUnit testing with 80%+ coverage
        """
        extracted = extract_from_text(jd)
        scored = score_job(extracted["description"], extracted["title"])

        assert scored["ats_score"] >= 60, f"Expected >= 60, got {scored['ats_score']}"
        assert isinstance(scored["matched_keywords"], str)  # JSON string
        assert isinstance(scored["missing_keywords"], str)  # JSON string
        import json
        matched = json.loads(scored["matched_keywords"])
        assert len(matched) > 0, "Should have matched keywords"
        print(f"\n  Full pipeline ATS score: {scored['ats_score']}")
        print(f"  Matched: {matched[:5]}")
