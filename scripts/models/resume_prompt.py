import os
import sys
import getpass

from pathlib import Path
from openai import OpenAI

__package__ = "scripts"
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from vectorDB.vector_search import process_resume, vector_search
from vectorDB.vector_store import load_data

if not os.environ.get("OPENAI_API_KEY"):
    os.environ["OPENAI_API_KEY"] = getpass.getpass("Please enter your OPENAI_API_KEY: ")

client = OpenAI()


def prompts(job_description, resume_content):
    resume_prompt = [
        {
            "role": "developer",
            "content": """
                You are a professional Human Resource Manager. Based on the job description,
                you are responsible for reviewing the resume of a candidate and providing feedback on the candidate's resume.
            """
        },
        {
            "role": "user",
            "content": f"""
                Here is the job description:
                {job_description}
                
                Here is the candidate's resume:
                {resume_content}
                
                Please analyze how well this resume matches the job requirements. Provide the following:
                1. Key strengths in the resume that align with the job
                2. Important missing skills or experiences
                3. Specific recommendations to improve the resume for this position
            """
        }
    ]
    
    return resume_prompt


# mock_interview_prompt = [
#     {
#         "role": "developer",
#     }
# ]


def get_completion(messages, model="gpt-4o", stream=False):
    response = client.chat.completions.create(
        model=model,
        stream=stream,
        modalities=["text"],
        messages=messages,
        temperature=0.2,
        top_p=0.95,
        max_tokens=500,
    )
    
    return response.choices[0].message.content


def main():
    resume_path = "/Users/yiwen/Desktop/Resume_Yiwen.docx"
    model_name = "text-embedding-3-large"
    collection = "ds_jobs"
    k = 10
    
    resume_embeddings = process_resume(resume_path, model_name)
    top_jobs = vector_search(resume_embeddings, collection, k)
    
    #? Get first job from top_jobs for testing
    job = top_jobs[0]
    
    #? Get job description from job
    job_description = job.payload.get("jobDescription")
    
    resume = load_data(resume_path)
    resume_content = resume[0].page_content
    
    #? Get completion
    messages = prompts(job_description, resume_content)
    completion = get_completion(messages)
    
    print(completion)

if __name__ == "__main__":
    BASE_DIR = Path(__file__).resolve().parents[2]
    
    main()
