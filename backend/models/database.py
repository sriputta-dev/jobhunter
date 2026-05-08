from sqlalchemy import Column, Integer, String, Float, DateTime, Text, Boolean
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
from datetime import datetime
import os

Base = declarative_base()
DATABASE_URL = os.getenv("DATABASE_URL", "sqlite+aiosqlite:///./jobhunter.db")

engine = create_async_engine(DATABASE_URL, echo=False)
AsyncSessionLocal = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


class ResumeProfile(Base):
    """
    Stores the user's uploaded resume.
    Only one active profile at a time — new upload replaces old.
    AI agents read resume_text when generating tailored bullets.
    """
    __tablename__ = "resume_profiles"

    id = Column(Integer, primary_key=True, index=True)
    filename = Column(String(255))             # Original filename e.g. "Sri_Resume.pdf"
    file_type = Column(String(10))             # "pdf" or "docx"
    resume_text = Column(Text)                 # Full extracted plain text
    char_count = Column(Integer, default=0)    # Length for display
    uploaded_at = Column(DateTime, default=datetime.utcnow)
    is_active = Column(Boolean, default=True)  # Only one active at a time


class Job(Base):
    __tablename__ = "jobs"

    id = Column(Integer, primary_key=True, index=True)
    title = Column(String(255), nullable=False)
    company = Column(String(255), nullable=False)
    location = Column(String(255))
    url = Column(String(1000), unique=True)
    description = Column(Text)
    salary = Column(String(100))
    source = Column(String(50))
    posted_date = Column(String(50))
    ats_score = Column(Float, default=0.0)
    matched_keywords = Column(Text)
    missing_keywords = Column(Text)
    status = Column(String(50), default="new")
    tailored_resume = Column(Text)             # AI-generated resume bullets
    tailored_resume_edited = Column(Text)      # User-edited version (shown if present)
    cold_email = Column(Text)                  # AI-generated cold email
    cold_email_edited = Column(Text)           # User-edited version (shown if present)
    notes = Column(Text)                       # AI analysis + strategy
    notes_edited = Column(Text)                # User-edited strategy notes
    is_favorite = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class SearchRun(Base):
    __tablename__ = "search_runs"

    id = Column(Integer, primary_key=True, index=True)
    query = Column(String(255))
    location = Column(String(255))
    jobs_found = Column(Integer, default=0)
    jobs_scored = Column(Integer, default=0)
    status = Column(String(50), default="running")  # running, completed, failed
    error = Column(Text)
    started_at = Column(DateTime, default=datetime.utcnow)
    completed_at = Column(DateTime)


async def init_db():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


async def get_db():
    async with AsyncSessionLocal() as session:
        try:
            yield session
        finally:
            await session.close()
