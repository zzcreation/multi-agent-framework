#!/usr/bin/env python3
"""Worker Runtime 进程入口。"""

from worker import WorkerRuntime


def main():
    runtime = WorkerRuntime(worker_id="worker-local-1", capabilities=["review", "security", "sandbox"])
    runtime.run_forever()


if __name__ == "__main__":
    main()
