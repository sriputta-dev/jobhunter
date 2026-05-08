"""
JobHunter CrewAI Agents
-----------------------
4 specialized agents that collaborate in sequence:

1. JobAnalystAgent   - Analyzes JD, extracts requirements, scores fit
2. ResumeTailorAgent - Rewrites resume bullets to match JD keywords
3. OutreachAgent     - Drafts personalized cold emails to recruiters
4. StrategyAgent     - Provides interview prep and application strategy
"""

from crewai import Agent
import os


def get_llm_config():
    """Return LLM configuration. Uses Claude if key available, else OpenAI."""
    anthropic_key = os.getenv("ANTHROPIC_API_KEY")
    openai_key = os.getenv("OPENAI_API_KEY")

    if anthropic_key:
        return {
            "model": "claude-sonnet-4-20250514",
            "api_key": anthropic_key,
        }
    elif openai_key:
        return {
            "model": "gpt-4o-mini",
            "api_key": openai_key,
        }
    else:
        raise ValueError(
            "No LLM API key found. Set ANTHROPIC_API_KEY or OPENAI_API_KEY in .env"
        )


DEFAULT_CANDIDATE_BACKGROUND = """
Alex Johnson — Full Stack Software Engineer
- 2 years experience in Java, Springboot, React JS, Angular, Python
- Enterprise financial platforms, payment pipelines, and distributed systems
- Microservices architecture with Kafka, RabbitMQ, Docker, Kubernetes
- Databases: PostgreSQL, MS SQL Server, MongoDB, Oracle
- Cloud: AWS (EC2, S3, RDS, Lambda, API Gateway), Azure DevOps CI/CD
- Testing: xUnit, Moq, Jest, TDD, maintaining 85%+ code coverage
- AI tools: GPT-4o, Claude, GitHub Copilot — actively building RAG and agentic AI projects
- M.S. Computer Science Engineering, GPA 3.9
- Certifications: Azure AI Engineer, Azure Fundamentals
- Open to relocation anywhere in the US
- GitHub: github.com/alexjohnson-dev

NOTE TO USER: Replace this entire block with your own background.
Edit DEFAULT_CANDIDATE_BACKGROUND in backend/agents/agents.py
or simply upload your resume PDF/DOCX — it overrides this automatically.
"""

# Module-level cache — updated when resume is uploaded
_resume_text_cache: str = ""


def get_candidate_background() -> str:
    """
    Returns the candidate background for AI agents.
    Priority: uploaded resume text > default hardcoded text.
    Called fresh each time so agents always get latest uploaded resume.
    """
    global _resume_text_cache
    if _resume_text_cache.strip():
        return _resume_text_cache
    return DEFAULT_CANDIDATE_BACKGROUND.strip()


def set_resume_cache(text: str):
    """Called after resume upload to update the in-memory cache."""
    global _resume_text_cache
    _resume_text_cache = text.strip()


# Keep CANDIDATE_BACKGROUND as alias for backward compatibility
CANDIDATE_BACKGROUND = DEFAULT_CANDIDATE_BACKGROUND


def create_job_analyst_agent() -> Agent:
    return Agent(
        role="Senior Job Market Analyst",
        goal=(
            "Analyze job descriptions with expert precision to extract key requirements, "
            "identify skill gaps, and provide a comprehensive fit assessment for the candidate."
        ),
        backstory=(
            "You are a veteran technical recruiter with 15 years experience placing "
            "software engineers at top tech companies. You have deep expertise in ATS systems, "
            "keyword matching, and understanding what hiring managers actually want beyond "
            "what the job description says. You know how to read between the lines."
        ),
        verbose=True,
        allow_delegation=False,
        llm="anthropic/claude-3-haiku-20240307",
    )


def create_resume_tailor_agent() -> Agent:
    return Agent(
        role="Expert Resume Strategist",
        goal=(
            "Rewrite and tailor resume bullet points to maximize ATS score and human appeal "
            "for a specific job, while keeping all claims honest and verifiable."
        ),
        backstory=(
            "You are a certified professional resume writer who has helped 500+ engineers "
            "land jobs at FAANG companies. You understand ATS algorithms deeply and know "
            "exactly which keywords to include and how to frame experience authentically. "
            "You never fabricate — you reframe real experience compellingly."
        ),
        verbose=True,
        allow_delegation=False,
        llm="anthropic/claude-sonnet-4-20250514",
    )


def create_outreach_agent() -> Agent:
    return Agent(
        role="Professional Outreach Specialist",
        goal=(
            "Draft concise, personalized, and compelling cold emails to recruiters and "
            "hiring managers that get responses — not spam filters."
        ),
        backstory=(
            "You are a sales communication expert who spent 10 years in technical recruiting. "
            "You know that the best cold emails are short (under 150 words), specific, "
            "lead with value, and have a single clear call to action. "
            "You always mention the specific role and one compelling reason why this candidate fits."
        ),
        verbose=True,
        allow_delegation=False,
        llm="anthropic/claude-3-haiku-20240307",
    )


def create_strategy_agent() -> Agent:
    return Agent(
        role="Career Strategy Coach",
        goal=(
            "Provide actionable interview preparation, application strategy, "
            "and career advice tailored to the specific role and company."
        ),
        backstory=(
            "You are an executive career coach who has coached engineers through interviews "
            "at Google, Meta, Amazon, and Microsoft. You know the STAR method, system design "
            "patterns, behavioral questions, and company-specific culture signals. "
            "You give practical, specific advice — not generic platitudes."
        ),
        verbose=True,
        allow_delegation=False,
        llm="anthropic/claude-sonnet-4-20250514",
    )
