import json
import os
import time

class BenchmarkTracker:
    def __init__(self, filename="benchmark_results.json"):
        self.filename = filename
        self.results = []
        self._load_existing()

    def _load_existing(self):
        if os.path.exists(self.filename):
            try:
                with open(self.filename, 'r', encoding='utf-8') as f:
                    self.results = json.load(f)
            except json.JSONDecodeError:
                self.results = []

    def record_instance(self, instance_id, metrics):
        record = {
            "instance_id": instance_id,
            "timestamp": time.time(),
            **metrics
        }
        self.results.append(record)
        self.save()
        
    def save(self):
        with open(self.filename, 'w', encoding='utf-8') as f:
            json.dump(self.results, f, indent=4)
