import argparse
import datetime
import io
import os
import sys

from plan import PLAN
from act import act
from observe import observe_all_services, observe_mcp_mode, observe_rag_mode
from adapt import human_review, adapt
from review_modes import run_review_mode

REVIEW_MODES = ("multi-agent", "testing", "cloud")


class Tee:
    def __init__(self, *streams):
        self.streams = streams

    def write(self, data):
        for s in self.streams:
            s.write(data)

    def flush(self):
        for s in self.streams:
            s.flush()


def run_observe(mode):
    if mode in REVIEW_MODES:
        return run_review_mode(mode)
    if mode == "mcp":
        print("OBSERVE (MCP validation mode)")
        return observe_mcp_mode()
    if mode == "rag":
        print("OBSERVE (RAG validation mode)")
        return observe_rag_mode()
    print("OBSERVE")
    return observe_all_services(PLAN)


def run_loop(mode):
    print("=" * 60)
    print("GROUP 24 SHARED AGENTIC LOOP")
    print(f"Mode: {mode}")
    print("=" * 60)

    print()
    print("PLAN")
    print(PLAN)

    print()
    act()

    print()
    results = run_observe(mode)

    print()
    print("Evidence collected:")
    for line in results:
        print(f"  {line}")

    print()
    decision = human_review()

    print()
    print(f"Decision: {decision}")
    adapt(decision)

    if mode == "cloud":
        status = {"Accept": "READY", "Partially Accept": "READY WITH NOTED RISKS"}.get(decision, "NOT READY")
        print()
        print("RELEASE DECISION")
        print(f"Status: {status}")
        print(f"Approved by: {os.getenv('USER', 'reviewer')}")
        print(f"Date: {datetime.date.today().isoformat()}")

    print()
    print("LOOP COMPLETE")


def main():
    parser = argparse.ArgumentParser(description="Group 24 shared agentic loop")
    parser.add_argument(
        "--mode",
        choices=["all", "mcp", "rag", "multi-agent", "testing", "cloud"],
        default="all",
        help="'all' = Release 0 service health checks, 'mcp' = MCP tool "
             "validation, 'rag' = RAG grounded-answer validation, "
             "'multi-agent' / 'testing' / 'cloud' = Release 2 review modes",
    )
    parser.add_argument("--report", default=None, help="Path to write the captured-output report")
    args = parser.parse_args()

    report_path = args.report or f"reports/{args.mode}-validation-report.md"
    os.makedirs(os.path.dirname(report_path) or ".", exist_ok=True)

    buffer = io.StringIO()
    original_stdout = sys.stdout
    sys.stdout = Tee(original_stdout, buffer)
    try:
        run_loop(args.mode)
    finally:
        sys.stdout = original_stdout

    with open(report_path, "w") as f:
        f.write(f"# Group 24 Agentic Loop - {args.mode} validation\n\n")
        f.write(f"Captured: {datetime.datetime.now().isoformat()}\n\n")
        f.write("```\n")
        f.write(buffer.getvalue())
        f.write("```\n")

    print(f"\nReport written to {report_path}")


if __name__ == "__main__":
    main()
