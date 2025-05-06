from openai import OpenAI


def resume_prompt(job_description, resume_content):
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


def get_completion(api_key, messages, model="gpt-4o", stream=False):
    client = OpenAI(api_key)
    response = client.chat.completions.create(
        model=model,
        stream=stream,
        modalities=["text"],
        messages=messages,
        temperature=0.2,
        top_p=0.95,
        max_tokens=1024,
    )
    
    return response.choices[0].message.content