"""
JobHunter CrewAI Tasks
----------------------
Sequential tasks that build on each other's output.
"""

from crewai import Task
from .agents import (
    get_candidate_background,
    create_job_analyst_agent,
    create_resume_tailor_agent,
    create_outreach_agent,
    create_strategy_agent,
)


def create_analysis_task(job_title: str, company: str, job_description: str, ats_score: float) -> Task:
    agent = create_job_analyst_agent()
    return Task(
        description=f"""
Analyze this job opportunity for our candidate.

CANDIDATE BACKGROUND:
{get_candidate_background()}

JOB DETAILS:
Title: {job_title}
Company: {company}
ATS Fit Score (keyword match): {ats_score}/100

JOB DESCRIPTION:
{job_description[:3000]}

Your analysis must include:
1. TOP 5 required skills and whether the candidate has them (Yes/Partial/No)
2. TOP 3 gaps to address
3. Why this role is a good or poor fit in 2-3 sentences
4. Overall recommendation: STRONG FIT / GOOD FIT / STRETCH / SKIP
5. Key selling points the candidate should emphasize
""",
        expected_output=(
            "A structured fit analysis with skill match table, gap analysis, "
            "fit recommendation, and key selling points. Clear and actionable."
        ),
        agent=agent,
    )


def create_resume_task(
    job_title: str,
    company: str,
    job_description: str,
    analysis_context: Task,
) -> Task:
    agent = create_resume_tailor_agent()
    return Task(
        description=f"""
Based on the job analysis, rewrite resume bullets for this specific role.

CANDIDATE BACKGROUND:
{get_candidate_background()}

TARGET ROLE: {job_title} at {company}

JOB DESCRIPTION (key parts):
{job_description[:2000]}

INSTRUCTIONS:
1. Rewrite the Professional Summary (3-4 sentences) specifically for this role
2. Provide 4-6 tailored bullet points for the most relevant experience
3. List the top 8-10 skills to highlight for this specific JD
4. Every bullet must: start with action verb, include metric if possible, use JD keywords naturally
5. Do NOT fabricate — only reframe real experience from the candidate background
6. Keep all bullets honest and verifiable

Format as:
SUMMARY: [rewritten summary]
BULLETS: [bulleted list]
SKILLS TO HIGHLIGHT: [comma-separated list]
""",
        expected_output=(
            "A tailored professional summary, 4-6 strong bullet points, "
            "and a prioritized skills list — all keyword-optimized for this specific JD."
        ),
        agent=agent,
        context=[analysis_context],
    )


def create_outreach_task(
    job_title: str,
    company: str,
    resume_task: Task,
) -> Task:
    agent = create_outreach_agent()
    return Task(
        description=f"""
Draft a cold outreach email for this job application.

CANDIDATE: [Your name from uploaded resume]
TARGET ROLE: {job_title} at {company}
CANDIDATE EMAIL: [Your email - add to your profile]

INSTRUCTIONS:
- Maximum 120 words - recruiters don't read long emails
- Subject line: compelling and specific (not generic)
- Opening: reference the specific role and company
- Middle: ONE compelling hook from candidate's background that matches this role
- Close: single clear ask (15-min call or coffee chat)
- Tone: confident, professional, human - not salesy

Output format:
SUBJECT: [subject line]
EMAIL BODY:
[email content]
""",
        expected_output=(
            "A subject line and email body under 120 words that is "
            "specific, compelling, and likely to get a response."
        ),
        agent=agent,
        context=[resume_task],
    )


def create_strategy_task(
    job_title: str,
    company: str,
    analysis_task: Task,
) -> Task:
    agent = create_strategy_agent()
    return Task(
        description=f"""
Provide interview preparation and application strategy for this role.

CANDIDATE BACKGROUND:
{get_candidate_background()}

TARGET ROLE: {job_title} at {company}

Provide:
1. TOP 5 technical questions likely to be asked (with brief answer hints)
2. TOP 3 behavioral questions with STAR method hints
3. ONE key thing to research about {company} before interviewing
4. RED FLAGS or concerns the candidate should be prepared to address
5. ONE thing that makes this candidate uniquely memorable for this role
""",
        expected_output=(
            "5 technical questions with hints, 3 behavioral questions with STAR hints, "
            "company research tip, red flags to address, and unique differentiator."
        ),
        agent=agent,
        context=[analysis_task],
    )
