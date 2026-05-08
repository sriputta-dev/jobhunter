"""
ATS Scoring Tool - scores job descriptions against a candidate profile.
Uses keyword extraction and weighted matching to produce a 0-100 fit score.
"""

import re
import json
from typing import Dict, List, Tuple

# Candidate profile keywords - customize this with your own skills
# Primary skills drive 70% of the ATS score
# Replace these with your actual tech stack for accurate scoring
CANDIDATE_PROFILE = {
    "primary_skills": [
        "c#", ".net", ".net core", "asp.net", "asp.net core", "csharp",
        "react", "react.js", "javascript", "typescript", "angular",
        "python", "java", "node.js", "express",
        "sql server", "postgresql", "mongodb", "oracle",
        "docker", "kubernetes", "aws", "azure",
        "kafka", "rabbitmq", "microservices", "rest api", "restful",
        "entity framework", "linq", "signalr",
        "ci/cd", "azure devops", "github actions",
        "html", "html5", "css", "css3",
        "blazor", "mvc", "web api",
    ],
    "secondary_skills": [
        "agile", "scrum", "tdd", "unit testing", "xunit", "jest", "moq",
        "git", "jenkins", "redis", "elasticsearch",
        "event-driven", "distributed systems", "cqrs",
        "jwt", "oauth", "authentication", "authorization",
        "figma", "swagger", "postman",
        "llm", "gpt", "ai", "machine learning", "langchain",
        "prompt engineering", "rag",
    ],
    "experience_keywords": [
        "full stack", "full-stack", "backend", "frontend", "software engineer",
        "software developer", "developer", "architect",
        "financial", "fintech", "payments", "banking",
        "enterprise", "scalable", "distributed",
        "mentoring", "leadership", "cross-functional",
        "5 years", "4 years", "senior",
    ],
    "soft_skills": [
        "communication", "collaboration", "independent", "autonomous",
        "problem solving", "analytical", "ownership",
        "agile", "fast-paced", "startup",
    ],
}

# Weights for scoring
WEIGHTS = {
    "primary_skills": 0.70,
    "secondary_skills": 0.18,
    "experience_keywords": 0.10,
    "soft_skills": 0.02,
}


def extract_keywords_from_jd(description: str) -> List[str]:
    """Extract meaningful keywords from a job description."""
    text = description.lower()
    # Remove special chars except spaces and hyphens
    text = re.sub(r"[^\w\s\-\.\+#]", " ", text)
    words = text.split()
    # Build bigrams too
    bigrams = [f"{words[i]} {words[i+1]}" for i in range(len(words) - 1)]
    return words + bigrams


def score_job(job_description: str, job_title: str = "") -> Dict:
    """
    Score a job against the candidate profile.
    
    Logic: Extract technical keywords from JD, check how many the candidate has.
    Score = (JD keywords candidate has) / (total JD tech keywords) * 100
    
    Returns score (0-100), matched keywords, missing important keywords.
    """
    if not job_description.strip() and not job_title.strip():
        return {
            "ats_score": 0.0,
            "matched_keywords": "[]",
            "missing_keywords": "[]",
            "breakdown": {}
        }

    jd_text = (job_description + " " + job_title).lower()

    # All candidate skills in one flat set
    all_candidate_skills = set()
    for skills in CANDIDATE_PROFILE.values():
        for s in skills:
            all_candidate_skills.add(s.lower())

    # Extract meaningful words from JD (filter noise)
    noise_words = {
        "the", "and", "or", "for", "with", "you", "will", "have", "this",
        "that", "are", "from", "our", "your", "their", "they", "been",
        "more", "not", "but", "can", "all", "any", "each", "how", "its",
        "may", "who", "other", "into", "than", "then", "some", "such",
        "also", "about", "when", "where", "which", "while", "what",
        "work", "team", "role", "join", "help", "build", "looking",
        "experience", "strong", "working", "including", "across",
    }

    jd_words = set(re.sub(r"[^\w\s\-\.\+#]", " ", jd_text).split())
    jd_bigrams = set()
    words_list = jd_text.split()
    for i in range(len(words_list) - 1):
        jd_bigrams.add(f"{words_list[i]} {words_list[i+1]}")

    jd_tokens = jd_words | jd_bigrams

    # Find which candidate skills appear in the JD
    matched = []
    for skill in all_candidate_skills:
        if skill in jd_text or skill in jd_tokens:
            matched.append(skill)

    # Find which primary skills appear in JD (for missing list)
    primary_in_jd = []
    primary_missing = []
    for skill in CANDIDATE_PROFILE["primary_skills"]:
        if skill.lower() in jd_text:
            primary_in_jd.append(skill)
        else:
            primary_missing.append(skill)

    # Score: based on how many candidate skills the JD requires
    # Weighted by skill category importance
    primary_matched = [s for s in CANDIDATE_PROFILE["primary_skills"] if s.lower() in jd_text]
    secondary_matched = [s for s in CANDIDATE_PROFILE["secondary_skills"] if s.lower() in jd_text]
    exp_matched = [s for s in CANDIDATE_PROFILE["experience_keywords"] if s.lower() in jd_text]
    soft_matched = [s for s in CANDIDATE_PROFILE["soft_skills"] if s.lower() in jd_text]

    # Base score: primary matches drive it
    # Cap each category contribution
    primary_score = min(len(primary_matched) / 8, 1.0)   # 8 primary matches = max
    secondary_score = min(len(secondary_matched) / 5, 1.0) # 5 secondary = max
    exp_score = min(len(exp_matched) / 3, 1.0)            # 3 exp = max
    soft_score = min(len(soft_matched) / 2, 1.0)          # 2 soft = max

    weighted = (
        primary_score * WEIGHTS["primary_skills"] +
        secondary_score * WEIGHTS["secondary_skills"] +
        exp_score * WEIGHTS["experience_keywords"] +
        soft_score * WEIGHTS["soft_skills"]
    )

    # Title boost
    target_titles = [".net", "full stack", "fullstack", "software engineer",
                     "backend", "react", "java", "node", "python", "angular"]
    if any(t in job_title.lower() for t in target_titles):
        weighted = min(weighted * 1.15, 1.0)

    final_score = round(weighted * 100, 1)

    return {
        "ats_score": final_score,
        "matched_keywords": json.dumps(list(set(primary_matched + secondary_matched[:5]))[:20]),
        "missing_keywords": json.dumps(primary_missing[:8]),
        "breakdown": {
            "primary": {"matched": len(primary_matched), "score": round(primary_score * 100, 1)},
            "secondary": {"matched": len(secondary_matched), "score": round(secondary_score * 100, 1)},
            "experience": {"matched": len(exp_matched), "score": round(exp_score * 100, 1)},
        }
    }


def batch_score_jobs(jobs: List[Dict]) -> List[Dict]:
    """Score a list of jobs and return sorted by ATS score descending."""
    scored = []
    for job in jobs:
        result = score_job(
            job.get("description", ""),
            job.get("title", "")
        )
        job.update(result)
        scored.append(job)

    return sorted(scored, key=lambda x: x["ats_score"], reverse=True)
