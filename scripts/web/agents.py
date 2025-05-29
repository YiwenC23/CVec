import os
from pydantic import BaseModel
from openai import AsyncOpenAI
from typing import List, Dict, Any
from agents import (
    Agent,
    Runner,
    RunResult,
    WebSearchTool,
    model_settings,
    set_default_openai_client,
    set_tracing_disabled,
    set_default_openai_api,
)
from agents.run import RunConfig
from agents.extensions.handoff_prompt import prompt_with_handoff_instructions
from openai.types.responses import ResponseTextDeltaEvent
from agents.items import ReasoningItem, ItemHelpers


set_default_openai_api(os.environ["OPENAI_API_KEY"])
client = AsyncOpenAI(api_key=os.environ["OPENAI_API_KEY"])
set_default_openai_client(client)
set_tracing_disabled(False)


# ────────────────────────────────────────────────────────────────────────────────
#                           Resume Polishing Agents
# ────────────────────────────────────────────────────────────────────────────────

job_detailing_search_agent = Agent(
    name="Job Detailer",
    instructions=prompt_with_handoff_instructions("""
                    You are a job searching assistant. Given the data of a job position and user's messages, search the web for information related to this job position.
                    Capture the information that would increase the chances of candidates to get this job position.
                    Only looking for information over this job position that is relevant, necessary, and helpful for job hunting.
                """),
    model="gpt-4.1-2025-04-14",
    model_settings=model_settings.ModelSettings(tool_choice="required"),
    tools=[WebSearchTool()]
)

resume_skill_search_agent = Agent(
    name="Resume Skill Search",
    instructions=prompt_with_handoff_instructions("""
                    You are a resume skill searching assistant. Given the user's resume content and user's messages, search the web for information related to the user's resume.
                    Capture the information that is relevant, important, and helpful for the user to polish their resume.
                """),
    model="gpt-4.1-2025-04-14",
    model_settings=model_settings.ModelSettings(tool_choice="required"),
    tools=[WebSearchTool()]
)

class WebSearchItem(BaseModel):
    reason: str
    "Your reasoning for why this search is important to the query."
    
    query: str
    "The search term to use for the web search."

class WebSearchPlan(BaseModel):
    searches: List[WebSearchItem]
    """A list of web searches to perform to best answer the query."""

search_planner_agent = Agent(
    name="Search Planner",
    instructions=prompt_with_handoff_instructions("You are a search planner. Given a query, come up with a set of web searches to be performed to best answer the query."),
    model="gpt-4.1-2025-04-14",
    output_type=WebSearchPlan,
)

hr_agent = Agent(
    name="Resume Reviewer",
    instructions=prompt_with_handoff_instructions("""
        You are an expert Human Resources Manager with 10+ years of experience hiring technical talent.
        The user will provide:
            1. A detailed job description.
            2. Their current resume text.
        
        Please structure your response in **four** sections.
        For any item that has supporting evidence in the resume, add a `Source:` line on the next line
        and quote the exact sentence.  
        If the resume provides **no** supporting sentence, do **not** write a `Source:` line at all;  
        instead, make sure section 4 asks a follow-up question about that gap.
        
        1. Job Overview
            • Briefly summarize the role's key responsibilities and required skills.
        
        2. Alignment Analysis
            • **Strengths** - for every requirement met, write one bullet:
                - Description of the strength
                - `Source:` "exact sentence from resume"
            • **Weaknesses** - for each missing requirement:
                - Description of the gap
                - `Source:` (missing)
        
        3. Recommendations
            • For each weakness above, provide an **Original → Revised** rewrite:
                - **Original**: "<original sentence from resume>" (or note "none")
                - **Revised**: "<new sentence that incorporates the exact keyword(s) and quantifiable data>"
            • Offer one or two formatting or structure tips (e.g. reorder sections, concise bullet style).
        
        4. Follow-up & Improvement
            For **each** weakness listed:
                a) Ask a **specific** follow-up question to clarify the user's experience or project.
                b) Propose a detailed resume bullet (Original → Revised) that addresses the gap.
        
        Always be concise, actionable, and tailored to this specific job description.
    """),
    model="o3-2025-04-16",
    handoffs=[job_detailing_search_agent, resume_skill_search_agent, search_planner_agent]
)


async def run_hr_agent(conversation_history: List[Dict[str,str]]):
    #* Phase 1: "Thinking" with o3 (no streaming) ─────────────────────────────
    thinker = hr_agent.clone(model="o3-2025-04-16")
    # Use async Runner.run instead of run_sync to avoid nested event loops
    analysis = await Runner.run(
        thinker,
        conversation_history,
        run_config=RunConfig(tracing_disabled=False, trace_include_sensitive_data=True)
    )
    
    #? Extract every internal reasoning item as text
    chain_parts: List[str] = []
    for item in analysis.new_items:
        if isinstance(item, ReasoningItem):
            text = ItemHelpers.extract_last_text(item.raw_item)
            if text:
                chain_parts.append(text)
    chain_text = "\n".join(chain_parts)
    
    #* Phase 2: Streaming reply with a stronger model
    def streaming_instructions(_: Any, __: Any) -> str:
        return f"{chain_text}\n\nNow provide the final, user-facing feedback in a concise, actionable way."
    
    streamer = hr_agent.clone(
        model="gpt-4o",
        instructions=streaming_instructions
    )
    
    streamed = Runner.run_streamed(streamer, conversation_history)
    async for event in streamed.stream_events():
        if event.type == "raw_response_event" and isinstance(event.data, ResponseTextDeltaEvent):
            yield event.data.delta

# ────────────────────────────────────────────────────────────────────────────────
#                           Mock-Interview Agents
# ────────────────────────────────────────────────────────────────────────────────

#* Search agent: gather interview-relevant knowledge
interview_knowledge_search_agent = Agent(
    name="Interview Knowledge Search",
    instructions=prompt_with_handoff_instructions("""
        You are an interview-preparation assistant. Given the job description,
        candidate resume and current chat context, search the web for interview
        questions, domain knowledge and best-practice guidelines that are *directly*
        relevant to this position (e.g. behavioural questions, data-science theory,
        coding / system-design topics).  Only surface content that could
        realistically be asked in a 1-hour interview.
    """),
    model="gpt-4.1-2025-04-14",
    model_settings=model_settings.ModelSettings(tool_choice="required"),
    tools=[WebSearchTool()]
)

#* Planner agent: uses o3 to draft the full 1-hour interview
interview_planner_agent = Agent(
    name="Interview Planner",
    instructions=prompt_with_handoff_instructions("""
        You are a senior technical interviewer. Draft a complete 60-minute
        interview plan tailored to the provided job description and candidate
        resume.
        
        Requirements for the plan:
            • 5-min introduction / rapport building
            • 45-min Q&A split across:
            - Behavioural & culture-fit
            - Technical / data-science theory & coding
            - Role-specific case study or scenario
            • 10-min wrap-up and candidate questions
        
        For *each* question include:
            • The exact question text
            • The competency it assesses (rationale)
            • Cite the *exact* resume sentence if the question leverages a
                candidate experience, or the job-description requirement if relevant.
        
        Output the full agenda followed by the ordered list of questions and
        rationales in plain text.
    """),
    model="o3-2025-04-16",
    handoffs=[
        job_detailing_search_agent,
        interview_knowledge_search_agent,
        search_planner_agent,
    ],
)

#* Live interviewer (streaming – gpt-4.1)
mock_interviewer_agent = Agent(
    name="Mock Interviewer",
    instructions=prompt_with_handoff_instructions("""
        You are conducting the live mock interview.
        
        Style & rules:
            • Speak directly to the candidate using *second-person* pronouns ("you"), **never** their name.
            • Ask ONE question at a time and finish the full question before pausing.
            • After asking, go silent and wait until the candidate explicitly says **"Done."**
            • Do not interrupt or proceed to the next question before that cue.
            • After the "Done" cue, give a brief (≤ 40 words) constructive comment
                (strength & improvement) and then ask the next question.
            • Keep each interviewer turn ≤ 120 words and do **not** reveal internal
                scoring, rubric or hidden rationale.
    """),
    model="gpt-4.1-2025-04-14",
)

#* Helper to run the two-phase mock-interview
async def run_mock_interview_agent(conversation_history: List[Dict[str, str]]):
    """
        1) Use the o3 planner to prepare a 1-hour interview agenda & question set
           with web-search hand-offs.
        2) Feed that plan into a streaming gpt-4.1 interviewer that interacts with
           the candidate in real time.
    """
    
    #* Phase 1: Planning (no streaming)
    analysis = await Runner.run(
        interview_planner_agent,
        conversation_history,
        run_config=RunConfig(
            tracing_disabled=False, trace_include_sensitive_data=True
        ),
    )
    
    #* Pull the planner's internal reasoning / plan
    chain_parts: List[str] = []
    for item in analysis.new_items:
        if isinstance(item, ReasoningItem):
            text = ItemHelpers.extract_last_text(item.raw_item)
            if text:
                chain_parts.append(text)
    chain_text = "\n".join(chain_parts)
    
    #* Phase 2: Live streaming interviewer
    def streaming_instructions(_: Any, __: Any) -> str:
        return (
            f"{chain_text}\n\n"
            "You are now live with the candidate.  Remember:\n"
            "• Use *you* when addressing the candidate.\n"
            "• Ask one complete question, then wait silently until the candidate says 'Done.'\n"
            "• Only after hearing 'Done' give short feedback and move to the next question."
        )
    
    streamer = mock_interviewer_agent.clone(
        model="gpt-4.1-2025-04-14",
        instructions=streaming_instructions,
    )
    
    streamed = Runner.run_streamed(streamer, conversation_history)
    async for event in streamed.stream_events():
        if (
            event.type == "raw_response_event"
            and isinstance(event.data, ResponseTextDeltaEvent)
        ):
            yield event.data.delta


#* Post-Interview Evaluation Agent
interview_evaluator_agent = Agent(
    name="Interview Evaluator",
    instructions=prompt_with_handoff_instructions("""
        You are an experienced hiring manager.  You will receive the **full
        transcript** of a mock interview (your questions + the candidate's answers).
        
        Produce a fact-based evaluation with these sections:
            
            1. Overall Performance (2-3 sentences)
            
            2. Strengths - bullet list; for each bullet add 'Source:' and quote the exact sentence fragment.
            
            3. Areas to Improve - bullet list with actionable advice; each bullet followed by 'Source:'
                quoting the relevant part of the transcript.
            
            4. Final Recommendation - Hire / Borderline / No-Hire with a one-sentence rationale.
        
        Base every point strictly on the transcript; do not speculate beyond it.
        Write in clear, professional English.
    """),
    model="o3-2025-04-16",
)

async def run_interview_evaluation(transcript: str) -> str:
    """
    Given the plain-text transcript of Q&A, return the evaluator's feedback.
    """
    result: RunResult = await Runner.run(
        interview_evaluator_agent,
        [{"role": "user", "content": transcript}],
        run_config=RunConfig(tracing_disabled=False, trace_include_sensitive_data=True),
    )
    return result.output.strip()