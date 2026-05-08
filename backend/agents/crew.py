"""
JobHunter Crew Orchestrator
----------------------------
Runs the 4-agent crew for a single job and returns structured results.
"""

from crewai import Crew, Process
from .tasks import (
    create_analysis_task,
    create_resume_task,
    create_outreach_task,
    create_strategy_task,
)
from .agents import (
    create_job_analyst_agent,
    create_resume_tailor_agent,
    create_outreach_agent,
    create_strategy_agent,
)
import logging
import time

logger = logging.getLogger(__name__)


def run_job_hunter_crew(
    job_title: str,
    company: str,
    job_description: str,
    ats_score: float,
) -> dict:
    """
    Run the full 4-agent crew for one job.
    Returns dict with analysis, tailored_resume, cold_email, strategy.
    """
    logger.info(f"Starting crew for: {job_title} at {company}")
    start = time.time()

    try:
        # Create tasks (with context chaining)
        analysis_task = create_analysis_task(job_title, company, job_description, ats_score)
        resume_task = create_resume_task(job_title, company, job_description, analysis_task)
        outreach_task = create_outreach_task(job_title, company, resume_task)
        strategy_task = create_strategy_task(job_title, company, analysis_task)

        # Assemble crew — sequential process so each agent builds on prior output
        crew = Crew(
            agents=[
                create_job_analyst_agent(),
                create_resume_tailor_agent(),
                create_outreach_agent(),
                create_strategy_agent(),
            ],
            tasks=[analysis_task, resume_task, outreach_task, strategy_task],
            process=Process.sequential,
            verbose=True,
        )

        result = crew.kickoff()
        elapsed = round(time.time() - start, 1)
        logger.info(f"Crew completed in {elapsed}s for {job_title} at {company}")

        # Parse outputs from each task
        task_outputs = result.tasks_output if hasattr(result, "tasks_output") else []

        analysis = str(task_outputs[0].raw) if len(task_outputs) > 0 else ""
        tailored_resume = str(task_outputs[1].raw) if len(task_outputs) > 1 else ""
        cold_email = str(task_outputs[2].raw) if len(task_outputs) > 2 else ""
        strategy = str(task_outputs[3].raw) if len(task_outputs) > 3 else ""

        return {
            "success": True,
            "analysis": analysis,
            "tailored_resume": tailored_resume,
            "cold_email": cold_email,
            "strategy": strategy,
            "elapsed_seconds": elapsed,
        }

    except Exception as e:
        logger.error(f"Crew failed for {job_title} at {company}: {e}")
        return {
            "success": False,
            "error": str(e),
            "analysis": "",
            "tailored_resume": "",
            "cold_email": "",
            "strategy": "",
        }
