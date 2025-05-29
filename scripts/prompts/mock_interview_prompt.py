import os
import getpass

from pathlib import Path
from openai import OpenAI


if not os.environ.get("OPENAI_API_KEY"):
    os.environ["OPENAI_API_KEY"] = getpass.getpass("Please enter your OPENAI_API_KEY: ")

client = OpenAI()


def get_default_instructions(resume_content, job_description):
    interview_prompt = f"""
                You are conducting the live mock interview.
                
                Here is my resume:
                {resume_content}
                
                Here is the job description:
                {job_description}
                
                Your task is to conduct a mock interview with the candidate following the instructions below.
                
                Style & rules:
                    • Speak directly to the candidate using *second-person* pronouns ("you"), **never** their name.
                    • Ask ONE question at a time and finish the full question before pausing.
                    • After asking, go silent and wait until the candidate explicitly finished the question.
                    • Do not interrupt or proceed to the next question before that cue.
                    • After the "Done" cue, give a brief (≤ 40 words) constructive comment
                        (strength & improvement) and then ask the next question.
                    • Keep each interviewer turn ≤ 120 words and do **not** reveal internal
                        scoring, rubric or hidden rationale.
            """
    return interview_prompt