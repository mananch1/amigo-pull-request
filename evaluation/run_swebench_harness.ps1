# SWE-bench Evaluation Harness Wrapper
# Note: You must have Docker running and swebench installed:
# pip install swebench

$predictions_path = "predictions.jsonl"
$dataset_name = "princeton-nlp/SWE-bench_Lite"
$run_id = "amigo-hybrid-eval"

Write-Host "Ensuring predictions file exists..."
if (-Not (Test-Path $predictions_path)) {
    Write-Host "Error: predictions.jsonl not found. Please run the evaluation script first:"
    Write-Host "python -m evaluation.run_eval"
    exit 1
}

Write-Host "Starting SWE-Bench Official Evaluation Harness via Docker...`n"
python -m swebench.harness.run_evaluation `
    --predictions_path $predictions_path `
    --dataset_name $dataset_name `
    --run_id $run_id `
    --max_workers 4
