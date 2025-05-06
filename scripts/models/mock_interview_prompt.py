import os
import getpass

from pathlib import Path
from openai import OpenAI


if not os.environ.get("OPENAI_API_KEY"):
    os.environ["OPENAI_API_KEY"] = getpass.getpass("Please enter your OPENAI_API_KEY: ")

client = OpenAI()


def mockInterview_prompt():
    mock_interview_prompt = [
        {
            "role": "developer",
            "content": """
                You are a professional Human Resource Manager. Based on the job description,
                you are responsible for reviewing the resume of a candidate and providing feedback on the candidate's resume.
            """
        },
        {
            "role": "user",
            "content": """
            """
        }
    ]
    
    return mock_interview_prompt


def get_completion(messages, model="gpt-4o-realtime-preview-2024-12-17", stream=True):
    response = client.chat.completions.create(
        model=model,
        stream=stream,
        modalities=["text"],
        messages=messages,
    )
    
    return response.choices[0].message.content