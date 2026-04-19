import sys
import os
import argparse
import time
import json
from dotenv import load_dotenv

load_dotenv()

sys.path.append(os.path.dirname(os.path.dirname(__file__)))

from datasets import load_dataset
from evaluation.telemetry import BenchmarkTracker
from agent.orchestrator import GeminiOrchestrator
from agent.worker import GroqWorker
from ingest.main import clone_repo

PREDICTIONS_FILE = "predictions.jsonl"

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--limit", type=int, default=1)
    args = parser.parse_args()

    dataset = load_dataset("princeton-nlp/SWE-bench_Lite", split="test")
    
    tracker = BenchmarkTracker()
    orchestrator = GeminiOrchestrator()
    worker = GroqWorker()

    count = 0
    for instance in dataset:
        if count >= args.limit:
            break
            
        instance_id = instance['instance_id']
        repo = instance['repo']
        base_commit = instance['base_commit']
        problem_statement = instance['problem_statement']
        
        try:
            repo_url = f"https://github.com/{repo}.git"
            clone_dir = f"data/repos/{instance_id}"
            
            clone_repo(repo_url, clone_dir=clone_dir, base_commit=base_commit)
            
            files_list = []
            for root, _, files in os.walk(clone_dir):
                if '.git' in root: continue
                for f in files:
                    if f.endswith('.py'):
                        files_list.append(os.path.relpath(os.path.join(root, f), clone_dir))
            
            repo_context = f"Available Python files:\n" + "\n".join(files_list[:1000])
            
            start_plan = time.time()
            plan_result, plan_metrics = orchestrator.plan_resolution(problem_statement, repo_context)
            plan_latency = time.time() - start_plan
            
            target_files = plan_result.get("target_files", [])
            reasoning_plan = plan_result.get("reasoning_plan", "")
            
            files_content_dict = {}
            for path in target_files:
                full_path = os.path.join(clone_dir, path)
                if os.path.exists(full_path):
                    with open(full_path, "r", encoding="utf-8") as f:
                        files_content_dict[path] = f.read()
            
            start_exec = time.time()
            patch, exec_metrics = worker.generate_patch(reasoning_plan, files_content_dict)
            exec_latency = time.time() - start_exec
            
            prediction = {
                "instance_id": instance_id,
                "model_patch": patch,
                "model_name_or_path": "amigo-hybrid-agent"
            }
            with open(PREDICTIONS_FILE, "a", encoding="utf-8") as f:
                f.write(json.dumps(prediction) + "\n")

            record = {
                "prompt_tokens_gemini": plan_metrics.get("prompt_tokens"),
                "completion_tokens_gemini": plan_metrics.get("completion_tokens"),
                "prompt_tokens_groq": exec_metrics.get("prompt_tokens"),
                "completion_tokens_groq": exec_metrics.get("completion_tokens"),
                "latency_planning_seconds": round(plan_latency, 2),
                "latency_execution_seconds": round(exec_latency, 2)
            }
            tracker.record_instance(instance_id, record)
            
        except Exception as e:
            import traceback
            traceback.print_exc()
            tracker.record_instance(instance_id, {"error": str(e)})

        count += 1

if __name__ == "__main__":
    main()
