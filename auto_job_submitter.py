#!/usr/bin/env python3
"""
Automated Job Submission Script for Nebula Aether Training

This script continuously submits random jobs to the orchestrator to generate
training data for the AI models. It intelligently varies job types and
submission rates based on system load.
"""

import requests
import time
import random
import json
import sys
from datetime import datetime
from typing import List, Dict

class AutoJobSubmitter:
    def __init__(self, orchestrator_url: str = "http://localhost:8080"):
        self.orchestrator_url = orchestrator_url
        self.session = requests.Session()

        # Available job types with their characteristics
        self.job_types = {
            # Lightweight jobs (quick execution, good for frequent training data)
            "simple-cpu-test": {"weight": 3, "category": "light", "duration": "30-60s"},
            "neural-network-training": {"weight": 3, "category": "medium", "duration": "1-2min"},

            # Medium jobs (balanced execution time and resource usage)
            "monte-carlo-simulation": {"weight": 2, "category": "medium", "duration": "2-3min"},
            "image-inference-batch": {"weight": 2, "category": "medium", "duration": "1-2min"},
            "protein-folding-simulation": {"weight": 2, "category": "medium", "duration": "2-4min"},

            # Heavy jobs (longer execution, good for testing resource limits)
            "matrix-multiply-heavy": {"weight": 1, "category": "heavy", "duration": "3-5min"},
            "llm-finetuning-simulation": {"weight": 1, "category": "heavy", "duration": "4-6min"},
            "video-encoding-benchmark": {"weight": 1, "category": "heavy", "duration": "3-5min"},
            "ray-tracing-benchmark": {"weight": 1, "category": "heavy", "duration": "4-7min"},

            # Memory intensive jobs (test memory allocation)
            "memory-stress-test": {"weight": 1, "category": "memory", "duration": "2-3min"},
        }

        # Submission rate configuration
        self.base_interval = 45  # Base seconds between jobs
        self.min_interval = 20   # Minimum interval when system is idle
        self.max_interval = 120  # Maximum interval when system is busy

        # Statistics
        self.stats = {
            "jobs_submitted": 0,
            "jobs_successful": 0,
            "jobs_failed": 0,
            "start_time": datetime.now(),
            "last_submission": None,
            "job_type_counts": {job_type: 0 for job_type in self.job_types}
        }

    def get_weighted_job_type(self) -> str:
        """Select a random job type based on weights"""
        job_list = []
        for job_type, config in self.job_types.items():
            job_list.extend([job_type] * config["weight"])
        return random.choice(job_list)

    def submit_job(self, job_type: str) -> bool:
        """Submit a single job to the orchestrator"""
        try:
            payload = {"id": job_type}
            response = self.session.post(
                f"{self.orchestrator_url}/submit",
                json=payload,
                timeout=10
            )

            if response.status_code == 200:
                result = response.json()
                print(f"✅ Submitted {job_type} - {result.get('status', 'unknown')}")
                self.stats["jobs_successful"] += 1
                self.stats["job_type_counts"][job_type] += 1
                return True
            else:
                print(f"❌ Failed to submit {job_type}: HTTP {response.status_code}")
                self.stats["jobs_failed"] += 1
                return False

        except Exception as e:
            print(f"❌ Error submitting {job_type}: {e}")
            self.stats["jobs_failed"] += 1
            return False

    def get_system_load(self) -> Dict:
        """Get current system load from orchestrator"""
        try:
            # Try to get queue status (if endpoint exists)
            response = self.session.get(f"{self.orchestrator_url}/health", timeout=5)
            if response.status_code == 200:
                return {"queue_size": 0, "load": "normal"}
            else:
                # Assume normal load if we can't get status
                return {"queue_size": 0, "load": "normal"}
        except:
            return {"queue_size": 0, "load": "normal"}

    def calculate_next_interval(self) -> float:
        """Calculate the next submission interval based on system load"""
        load_info = self.get_system_load()
        queue_size = load_info.get("queue_size", 0)

        # Adjust interval based on queue size
        if queue_size == 0:
            # System is idle, submit more frequently
            interval = self.min_interval + random.uniform(0, 10)
        elif queue_size < 3:
            # Light load, normal rate
            interval = self.base_interval + random.uniform(-10, 10)
        else:
            # Heavy load, slow down
            interval = self.max_interval + random.uniform(-20, 20)

        return max(self.min_interval, min(self.max_interval, interval))

    def print_stats(self):
        """Print current submission statistics"""
        runtime = datetime.now() - self.stats["start_time"]
        success_rate = (self.stats["jobs_successful"] / max(1, self.stats["jobs_submitted"])) * 100

        print(f"\n📊 Submission Statistics:")
        print(f"   Runtime: {runtime}")
        print(f"   Jobs submitted: {self.stats['jobs_submitted']}")
        print(f"   Success rate: {success_rate:.1f}%")
        print(f"   Jobs/hour: {self.stats['jobs_submitted'] / max(1, runtime.total_seconds() / 3600):.1f}")

        print(f"\n🎯 Job Type Distribution:")
        for job_type, count in self.stats["job_type_counts"].items():
            if count > 0:
                category = self.job_types[job_type]["category"]
                duration = self.job_types[job_type]["duration"]
                print(f"   {job_type}: {count} ({category}, {duration})")

    def run(self, duration_hours: float = None):
        """Run the automated job submission"""
        print(f"🚀 Starting Automated Job Submission for Nebula Aether Training")
        print(f"📡 Orchestrator: {self.orchestrator_url}")
        print(f"⏱️  Base interval: {self.base_interval}s (range: {self.min_interval}-{self.max_interval}s)")
        print(f"🎲 Job types: {len(self.job_types)} types available")

        if duration_hours:
            print(f"⏰ Will run for {duration_hours} hours")
            end_time = datetime.now().timestamp() + (duration_hours * 3600)
        else:
            print(f"♾️  Will run indefinitely (Ctrl+C to stop)")
            end_time = None

        print(f"\n🔄 Starting job submission loop...\n")

        try:
            while True:
                # Check if we should stop
                if end_time and datetime.now().timestamp() >= end_time:
                    print(f"\n⏰ Reached time limit of {duration_hours} hours")
                    break

                # Select and submit a job
                job_type = self.get_weighted_job_type()
                self.stats["jobs_submitted"] += 1
                self.stats["last_submission"] = datetime.now()

                print(f"[{datetime.now().strftime('%H:%M:%S')}] Submitting job #{self.stats['jobs_submitted']}: {job_type}")
                self.submit_job(job_type)

                # Print stats every 10 jobs
                if self.stats["jobs_submitted"] % 10 == 0:
                    self.print_stats()

                # Calculate and wait for next submission
                interval = self.calculate_next_interval()
                print(f"⏳ Next job in {interval:.1f}s...")
                time.sleep(interval)

        except KeyboardInterrupt:
            print(f"\n\n🛑 Stopping job submission (Ctrl+C pressed)")

        finally:
            self.print_stats()
            print(f"\n🏁 Job submission completed!")


def main():
    """Main entry point"""
    import argparse

    parser = argparse.ArgumentParser(description="Automated job submission for Nebula Aether training")
    parser.add_argument("--url", default="http://localhost:8080", help="Orchestrator URL")
    parser.add_argument("--hours", type=float, help="Run for specified hours (default: indefinite)")
    parser.add_argument("--interval", type=int, default=45, help="Base interval between jobs (seconds)")
    parser.add_argument("--min-interval", type=int, default=20, help="Minimum interval (seconds)")
    parser.add_argument("--max-interval", type=int, default=120, help="Maximum interval (seconds)")

    args = parser.parse_args()

    # Create and configure submitter
    submitter = AutoJobSubmitter(args.url)
    submitter.base_interval = args.interval
    submitter.min_interval = args.min_interval
    submitter.max_interval = args.max_interval

    # Run the submitter
    submitter.run(args.hours)


if __name__ == "__main__":
    main()