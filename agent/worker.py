import os
from groq import Groq

class GroqWorker:
    def __init__(self):
        api_key = os.getenv("GROQ_API_KEY")
        self.client = Groq(api_key=api_key)
        self.model_name = "llama-3.3-70b-versatile"

    def generate_patch(self, reasoning_plan, files_content_dict):
        
        files_text = ""
        for path, content in files_content_dict.items():
            files_text += f"\n--- {path} ---\n{content}\n"

        prompt = f"""You are an autonomous execution worker powered by Groq. 
You are tasked with applying a fix to a codebase based on a provided step-by-step reasoning plan.

<reasoning_plan>
{reasoning_plan}
</reasoning_plan>

<files_to_modify>
{files_text}
</files_to_modify>

Your task is to write the complete modified file contents for ALL files that need changing.
CRITICAL DIRECTIVES:
1. Output the ENTIRE updated file contents. Do not use diff formatting. Do not use `...` to skip code. You must rewrite the exact file natively with your fixes injected.
2. For each file you modify, wrap the entire file content strictly inside a block that starts with `<<<FILE: filepath.py>>>` and ends with `<<<ENDFILE>>>`.
3. Provide absolutely no markdown formatting outside or inside of these blocks. Do not use ```python markdowns.

Output format MUST be strictly:
<<<FILE: path/to/target.py>>>
import sys
# full code here
<<<ENDFILE>>>
"""

        try:
            response = self.client.chat.completions.create(
                messages=[{"role": "user", "content": prompt}],
                model=self.model_name,
                temperature=0.1,
            )
            
            patch = response.choices[0].message.content

            
            usage = response.usage
            metrics = {
                "prompt_tokens": getattr(usage, "prompt_tokens", 0),
                "completion_tokens": getattr(usage, "completion_tokens", 0)
            }
            
            return patch.strip(), metrics
            
        except Exception as e:
            return "", {"prompt_tokens": 0, "completion_tokens": 0}
