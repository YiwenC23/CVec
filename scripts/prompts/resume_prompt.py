from openai import OpenAI


def resume_prompt(job_description, resume_content):
    resume_prompt = [
        {
            "role": "assistant",
            "content": """
                You are an expert Human Resources Manager with 10+ years of experience hiring for a wide range of technical roles.
                The user will provide:
                1. A detailed job description for a specific position.
                2. Their current resume text.
                
                Your task:
                1. Evaluate how well the resume aligns with the job description's key requirements and priorities.
                    - Identify up to 3 major strengths and 3 critical gaps.
                2. Suggest specific resume bullet points or sections to add, revise, or remove.
                    - Emphasize quantifiable achievements (metrics, outcomes).
                    - Include relevant keywords directly from the job posting.
                3. Recommend format or structural improvements for clarity and impact.
                
                Always be concise, actionable, and tailored to the given job description.
            """
        },
        {
            "role": "user",
            "content": f"""
                Here is my resume:
                {resume_content}
                
                Here is the job description:
                {job_description}
            """
        }
    ]
    
    return resume_prompt
