"""
JobHunter FastAPI Application
------------------------------
REST API serving the React dashboard and running the agent crew.
"""

from fastapi import FastAPI, Depends, HTTPException, BackgroundTasks, UploadFile, File
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update, desc
from pydantic import BaseModel
from typing import Optional, List
from datetime import datetime
import logging
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from models.database import init_db, get_db, Job, SearchRun, ResumeProfile, AsyncSessionLocal
from tools.job_scraper import fetch_all_jobs
from tools.ats_scorer import batch_score_jobs, score_job
from tools.job_extractor import extract_from_url, extract_from_text, is_url
from tools.resume_parser import extract_resume_text
from agents.crew import run_job_hunter_crew
from agents.agents import set_resume_cache

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(
    title="JobHunter Agent API",
    description="Multi-agent AI system for automated job search and application assistance",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://localhost:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
async def startup():
    await init_db()
    logger.info("Database initialized")
    # Load active resume into agent cache on startup
    await _load_resume_cache_on_startup()


async def _load_resume_cache_on_startup():
    """Load the most recent uploaded resume into agent memory on server start."""
    try:
        async with AsyncSessionLocal() as session:
            result = await session.execute(
                select(ResumeProfile)
                .where(ResumeProfile.is_active == True)
                .order_by(desc(ResumeProfile.uploaded_at))
                .limit(1)
            )
            profile = result.scalar_one_or_none()
            if profile and profile.resume_text:
                set_resume_cache(profile.resume_text)
                logger.info(f"Loaded resume into agent cache: {profile.filename} ({profile.char_count} chars)")
            else:
                logger.info("No uploaded resume found — using default candidate background")
    except Exception as e:
        logger.warning(f"Could not load resume cache on startup: {e}")


# ── Pydantic Schemas ──────────────────────────────────────────────────────────

class SearchRequest(BaseModel):
    query: str = ".NET Developer"
    location: str = "remote"
    limit_per_source: int = 5
    min_ats_score: float = 50.0


class JobUpdateRequest(BaseModel):
    status: Optional[str] = None
    notes: Optional[str] = None
    is_favorite: Optional[bool] = None


class EditableContentRequest(BaseModel):
    """Save user edits to AI-generated content."""
    tailored_resume_edited: Optional[str] = None
    cold_email_edited: Optional[str] = None
    notes_edited: Optional[str] = None


class PasteRequest(BaseModel):
    input: str          # Either a URL or raw JD text
    title: Optional[str] = None      # Optional override
    company: Optional[str] = None    # Optional override
    location: Optional[str] = None   # Optional override


class AnalyzeRequest(BaseModel):
    job_id: int


# ── Endpoints ─────────────────────────────────────────────────────────────────

@app.get("/health")
async def health():
    return {"status": "ok", "version": "1.0.0"}


# ── Resume Upload Endpoints ───────────────────────────────────────────────────

@app.post("/api/resume/upload")
async def upload_resume(
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_db),
):
    """
    Upload a resume PDF or DOCX file.
    Extracts text and stores it so AI agents can use it
    instead of the hardcoded default background.

    Accepts: .pdf, .docx, .txt
    Max size: 5MB
    """
    # Size check — 5MB max
    MAX_SIZE = 5 * 1024 * 1024
    file_bytes = await file.read()
    if len(file_bytes) > MAX_SIZE:
        raise HTTPException(
            status_code=413,
            detail="File too large. Maximum size is 5MB."
        )

    filename = file.filename or "resume"
    logger.info(f"Resume upload: {filename} ({len(file_bytes)} bytes)")

    # Extract text
    resume_text, error = extract_resume_text(filename, file_bytes)
    if error:
        raise HTTPException(status_code=422, detail=error)

    if len(resume_text.strip()) < 100:
        raise HTTPException(
            status_code=422,
            detail=(
                "Extracted text is too short — the file may be a scanned image or corrupted. "
                "Please try a text-based PDF or DOCX file."
            )
        )

    # Deactivate all previous profiles
    await db.execute(
        update(ResumeProfile).values(is_active=False)
    )

    # Save new profile
    file_type = filename.lower().rsplit(".", 1)[-1] if "." in filename else "unknown"
    profile = ResumeProfile(
        filename=filename,
        file_type=file_type,
        resume_text=resume_text,
        char_count=len(resume_text),
        is_active=True,
    )
    db.add(profile)
    await db.commit()
    await db.refresh(profile)

    # Update in-memory agent cache immediately
    set_resume_cache(resume_text)

    logger.info(f"Resume uploaded and cached: {filename} ({len(resume_text)} chars)")

    return {
        "message": "Resume uploaded successfully. AI agents will now use your resume.",
        "filename": filename,
        "char_count": len(resume_text),
        "preview": resume_text[:300] + "..." if len(resume_text) > 300 else resume_text,
        "profile_id": profile.id,
    }


@app.get("/api/resume")
async def get_resume(db: AsyncSession = Depends(get_db)):
    """Get the currently active resume profile."""
    result = await db.execute(
        select(ResumeProfile)
        .where(ResumeProfile.is_active == True)
        .order_by(desc(ResumeProfile.uploaded_at))
        .limit(1)
    )
    profile = result.scalar_one_or_none()

    if not profile:
        return {
            "uploaded": False,
            "message": "No resume uploaded yet. Using default candidate profile.",
            "filename": None,
            "char_count": 0,
            "preview": None,
            "uploaded_at": None,
        }

    return {
        "uploaded": True,
        "filename": profile.filename,
        "char_count": profile.char_count,
        "preview": profile.resume_text[:400] + "..." if profile.char_count > 400 else profile.resume_text,
        "uploaded_at": profile.uploaded_at.isoformat() if profile.uploaded_at else None,
        "profile_id": profile.id,
    }


@app.delete("/api/resume")
async def delete_resume(db: AsyncSession = Depends(get_db)):
    """Remove uploaded resume — agents fall back to default profile."""
    await db.execute(update(ResumeProfile).values(is_active=False))
    await db.commit()
    set_resume_cache("")  # Clear cache
    return {"message": "Resume removed. Agents will use default candidate profile."}


@app.post("/api/jobs/paste")
async def paste_job(
    request: PasteRequest,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
):
    """
    Add a job via URL or pasted job description text.

    Accepts:
      - A URL from any job board (LinkedIn, Indeed, Dice, Glassdoor, company careers page, etc.)
      - Raw job description text pasted directly

    The system will:
      1. Extract title, company, location, description automatically
      2. Run ATS keyword scoring immediately
      3. Save to database
      4. Return the job — ready for AI analysis

    Optional fields (title, company, location) let users override
    extracted values if extraction is imperfect.
    """
    raw = request.input.strip()
    if not raw:
        raise HTTPException(status_code=400, detail="Input cannot be empty")

    # Extract job data from URL or text
    if is_url(raw):
        logger.info(f"Extracting job from URL: {raw[:80]}")
        job_data = extract_from_url(raw)
        input_type = "url"
    else:
        logger.info("Extracting job from pasted text")
        job_data = extract_from_text(raw)
        input_type = "text"

    # Apply user overrides
    if request.title:
        job_data["title"] = request.title.strip()
    if request.company:
        job_data["company"] = request.company.strip()
    if request.location:
        job_data["location"] = request.location.strip()

    # Validate we have enough to work with
    if not job_data.get("description") and not job_data.get("title"):
        raise HTTPException(
            status_code=422,
            detail=(
                "Could not extract job content. "
                "If pasting a URL, make sure it's publicly accessible. "
                "Try pasting the job description text directly instead."
            ),
        )

    # ATS score
    scored = score_job(
        job_data.get("description", ""),
        job_data.get("title", ""),
    )
    job_data.update(scored)

    # Check for duplicate URL
    url = job_data.get("url", "")
    if url:
        existing_result = await db.execute(select(Job).where(Job.url == url))
        existing = existing_result.scalar_one_or_none()
        if existing:
            return {
                "message": "Job already exists in your tracker",
                "job_id": existing.id,
                "job": job_to_dict(existing),
                "duplicate": True,
            }

    # Save to database
    job = Job(
        title=job_data.get("title", "Job Opening"),
        company=job_data.get("company", "Unknown"),
        location=job_data.get("location", ""),
        url=url,
        description=job_data.get("description", ""),
        salary=job_data.get("salary", ""),
        source=job_data.get("source", "manual"),
        posted_date=job_data.get("posted_date", ""),
        ats_score=job_data.get("ats_score", 0),
        matched_keywords=job_data.get("matched_keywords", "[]"),
        missing_keywords=job_data.get("missing_keywords", "[]"),
    )
    db.add(job)
    await db.commit()
    await db.refresh(job)

    logger.info(
        f"Pasted job saved: '{job.title}' at '{job.company}' "
        f"[ATS: {job.ats_score}] via {input_type}"
    )

    return {
        "message": f"Job added successfully (ATS score: {job.ats_score}%)",
        "job_id": job.id,
        "job": job_to_dict(job),
        "input_type": input_type,
        "duplicate": False,
    }


@app.get("/api/jobs")
async def list_jobs(
    status: Optional[str] = None,
    min_score: Optional[float] = None,
    source: Optional[str] = None,
    limit: int = 50,
    db: AsyncSession = Depends(get_db),
):
    """List all jobs with optional filters."""
    query = select(Job).order_by(desc(Job.ats_score)).limit(limit)

    if status:
        query = query.where(Job.status == status)
    if min_score is not None:
        query = query.where(Job.ats_score >= min_score)
    if source:
        query = query.where(Job.source == source)

    result = await db.execute(query)
    jobs = result.scalars().all()

    return {
        "jobs": [job_to_dict(j) for j in jobs],
        "total": len(jobs),
    }


@app.get("/api/jobs/{job_id}")
async def get_job(job_id: int, db: AsyncSession = Depends(get_db)):
    """Get a single job by ID."""
    result = await db.execute(select(Job).where(Job.id == job_id))
    job = result.scalar_one_or_none()
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    return job_to_dict(job)


@app.patch("/api/jobs/{job_id}")
async def update_job(
    job_id: int,
    data: JobUpdateRequest,
    db: AsyncSession = Depends(get_db),
):
    """Update job status, notes, or favorite flag."""
    result = await db.execute(select(Job).where(Job.id == job_id))
    job = result.scalar_one_or_none()
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")

    if data.status is not None:
        job.status = data.status
    if data.notes is not None:
        job.notes = data.notes
    if data.is_favorite is not None:
        job.is_favorite = data.is_favorite

    job.updated_at = datetime.utcnow()
    await db.commit()
    return {"success": True, "job": job_to_dict(job)}


@app.patch("/api/jobs/{job_id}/edit")
async def save_edited_content(
    job_id: int,
    data: EditableContentRequest,
    db: AsyncSession = Depends(get_db),
):
    """
    Save user edits to AI-generated content.
    Edited versions are stored separately and shown in priority over AI output.
    The original AI output is always preserved — user can revert any time.
    """
    result = await db.execute(select(Job).where(Job.id == job_id))
    job = result.scalar_one_or_none()
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")

    if data.tailored_resume_edited is not None:
        job.tailored_resume_edited = data.tailored_resume_edited.strip() or None
    if data.cold_email_edited is not None:
        job.cold_email_edited = data.cold_email_edited.strip() or None
    if data.notes_edited is not None:
        job.notes_edited = data.notes_edited.strip() or None

    job.updated_at = datetime.utcnow()
    await db.commit()

    return {"success": True, "message": "Edits saved successfully"}
async def search_jobs(
    request: SearchRequest,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
):
    """
    Trigger a job search. Runs scraping + ATS scoring synchronously,
    then returns immediately. AI analysis runs in background per job.
    """
    # Create search run record
    run = SearchRun(query=request.query, location=request.location)
    db.add(run)
    await db.commit()
    await db.refresh(run)

    # Fetch jobs from all sources
    logger.info(f"Fetching jobs for: {request.query} in {request.location}")
    raw_jobs = fetch_all_jobs(request.query, request.location, request.limit_per_source)

    if not raw_jobs:
        run.status = "completed"
        run.jobs_found = 0
        run.completed_at = datetime.utcnow()
        await db.commit()
        return {"message": "No jobs found", "search_run_id": run.id, "jobs_found": 0}

    # ATS score all jobs
    scored_jobs = batch_score_jobs(raw_jobs)
    filtered = [j for j in scored_jobs if j["ats_score"] >= request.min_ats_score]

    # Save to database (skip existing URLs)
    saved_count = 0
    new_job_ids = []
    for job_data in filtered:
        # Check if already exists
        existing = await db.execute(select(Job).where(Job.url == job_data.get("url", "")))
        if existing.scalar_one_or_none():
            continue

        job = Job(
            title=job_data.get("title", ""),
            company=job_data.get("company", ""),
            location=job_data.get("location", ""),
            url=job_data.get("url", ""),
            description=job_data.get("description", ""),
            salary=job_data.get("salary", ""),
            source=job_data.get("source", ""),
            posted_date=job_data.get("posted_date", ""),
            ats_score=job_data.get("ats_score", 0),
            matched_keywords=job_data.get("matched_keywords", "[]"),
            missing_keywords=job_data.get("missing_keywords", "[]"),
        )
        db.add(job)
        await db.flush()
        new_job_ids.append(job.id)
        saved_count += 1

    run.jobs_found = len(raw_jobs)
    run.jobs_scored = saved_count
    run.status = "completed"
    run.completed_at = datetime.utcnow()
    await db.commit()

    logger.info(f"Saved {saved_count} new jobs")

    return {
        "message": f"Found {len(raw_jobs)} jobs, saved {saved_count} new ones",
        "search_run_id": run.id,
        "jobs_found": len(raw_jobs),
        "jobs_saved": saved_count,
        "new_job_ids": new_job_ids,
    }


@app.post("/api/jobs/{job_id}/analyze")
async def analyze_job(
    job_id: int,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
):
    """
    Run the 4-agent AI crew on a specific job.
    Runs in background to avoid timeout.
    """
    result = await db.execute(select(Job).where(Job.id == job_id))
    job = result.scalar_one_or_none()
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")

    background_tasks.add_task(
        _run_crew_background,
        job_id=job_id,
        job_title=job.title,
        company=job.company,
        description=job.description or "",
        ats_score=job.ats_score,
    )

    return {
        "message": "AI analysis started in background",
        "job_id": job_id,
        "note": "Poll GET /api/jobs/{job_id} to see results when tailored_resume is populated",
    }


async def _run_crew_background(
    job_id: int,
    job_title: str,
    company: str,
    description: str,
    ats_score: float,
):
    """Background task: run crew and save results to DB."""
    async with AsyncSession(
        __import__("models.database", fromlist=["engine"]).engine
    ) as session:
        crew_result = run_job_hunter_crew(job_title, company, description, ats_score)

        if crew_result["success"]:
            await session.execute(
                update(Job)
                .where(Job.id == job_id)
                .values(
                    tailored_resume=crew_result.get("tailored_resume", ""),
                    cold_email=crew_result.get("cold_email", ""),
                    notes=(
                        f"ANALYSIS:\n{crew_result.get('analysis', '')}\n\n"
                        f"STRATEGY:\n{crew_result.get('strategy', '')}"
                    ),
                    updated_at=datetime.utcnow(),
                )
            )
            await session.commit()
            logger.info(f"Crew results saved for job {job_id}")
        else:
            logger.error(f"Crew failed for job {job_id}: {crew_result.get('error')}")


@app.get("/api/stats")
async def get_stats(db: AsyncSession = Depends(get_db)):
    """Dashboard stats."""
    all_jobs = (await db.execute(select(Job))).scalars().all()

    total = len(all_jobs)
    by_status = {}
    by_source = {}
    high_score = [j for j in all_jobs if j.ats_score >= 80]
    analyzed = [j for j in all_jobs if j.tailored_resume]

    for job in all_jobs:
        by_status[job.status] = by_status.get(job.status, 0) + 1
        by_source[job.source] = by_source.get(job.source, 0) + 1

    avg_score = (
        round(sum(j.ats_score for j in all_jobs) / total, 1) if total else 0
    )

    return {
        "total_jobs": total,
        "high_fit_jobs": len(high_score),
        "analyzed_jobs": len(analyzed),
        "average_ats_score": avg_score,
        "by_status": by_status,
        "by_source": by_source,
    }


@app.get("/api/search-runs")
async def list_search_runs(db: AsyncSession = Depends(get_db)):
    """List recent search runs."""
    result = await db.execute(
        select(SearchRun).order_by(desc(SearchRun.started_at)).limit(20)
    )
    runs = result.scalars().all()
    return {"runs": [run_to_dict(r) for r in runs]}


# ── Helpers ───────────────────────────────────────────────────────────────────

def job_to_dict(job: Job) -> dict:
    return {
        "id": job.id,
        "title": job.title,
        "company": job.company,
        "location": job.location,
        "url": job.url,
        "description": job.description,
        "salary": job.salary,
        "source": job.source,
        "posted_date": job.posted_date,
        "ats_score": job.ats_score,
        "matched_keywords": json.loads(job.matched_keywords or "[]"),
        "missing_keywords": json.loads(job.missing_keywords or "[]"),
        "status": job.status,
        # AI-generated originals
        "tailored_resume": job.tailored_resume,
        "cold_email": job.cold_email,
        "notes": job.notes,
        # User-edited versions (None if not edited yet)
        "tailored_resume_edited": job.tailored_resume_edited,
        "cold_email_edited": job.cold_email_edited,
        "notes_edited": job.notes_edited,
        "is_favorite": job.is_favorite,
        "created_at": job.created_at.isoformat() if job.created_at else None,
        "updated_at": job.updated_at.isoformat() if job.updated_at else None,
    }


def run_to_dict(run: SearchRun) -> dict:
    return {
        "id": run.id,
        "query": run.query,
        "location": run.location,
        "jobs_found": run.jobs_found,
        "jobs_scored": run.jobs_scored,
        "status": run.status,
        "started_at": run.started_at.isoformat() if run.started_at else None,
        "completed_at": run.completed_at.isoformat() if run.completed_at else None,
    }
