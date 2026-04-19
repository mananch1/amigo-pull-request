import os
import json
from google import genai
from google.genai import types

class GeminiOrchestrator:
    def __init__(self):
        api_key = os.getenv("GEMINI_API_KEY")
        self.client = genai.Client(api_key=api_key)
        self.model_name = "gemini-2.5-flash"

    def plan_resolution(self, problem_statement, repo_context):
        
        prompt = f"""You are a senior software architect acting as the Orchestrator for an autonomous coding agent. 
We have a bug/feature request described as follows:

<problem_statement>
{problem_statement}
</problem_statement>

<repository_context>
{repo_context}
</repository_context>

Based on the problem statement and context, your task is to:
1. Identify the specific files that need to be modified.
2. Provide a step-by-step, logical reasoning plan on exactly how to implement the fix.

Respond in strict JSON format matching the following schema:
{{
    "target_files": ["path/to/file1.py", "path/to/file2.py"],
    "reasoning_plan": "Step 1: ..., Step 2: ..."
}}
        """

        try:
            response = self.client.models.generate_content(
                model=self.model_name,
                contents=prompt,
                config=types.GenerateContentConfig(
                    response_mime_type="application/json",
                    temperature=0.2,
                )
            )
            
            usage = response.usage_metadata
            metrics = {
                "prompt_tokens": getattr(usage, "prompt_token_count", 0),
                "completion_tokens": getattr(usage, "candidates_token_count", 0)
            }
            
            return json.loads(response.text), metrics
        except Exception as e:
            print(f"Orchestrator failed: {e}")
            return {"target_files": [], "reasoning_plan": str(e)}, {"prompt_tokens": 0, "completion_tokens": 0}
