import argparse
import asyncio
import os
import sys

from agent_os.agent_os import AgentOS


def main():
    parser = argparse.ArgumentParser(description="AgentOS CLI — High-Performance Parallel Agentic IDE OS")
    subparsers = parser.add_subparsers(dest="command", help="Subcommand to execute")

    # Command: run
    run_parser = subparsers.add_parser("run", help="Run a reasoning loop goal")
    run_parser.add_argument("--goal", required=True, help="User goal description")
    run_parser.add_argument("--workspace", default=".", help="Workspace path")

    # Command: status
    status_parser = subparsers.add_parser("status", help="Get current AgentOS status")
    status_parser.add_argument("--workspace", default=".", help="Workspace path")

    # Command: report
    report_parser = subparsers.add_parser("report", help="Generate performance metrics report")
    report_parser.add_argument("--workspace", default=".", help="Workspace path")

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        sys.exit(1)

    workspace = os.path.abspath(getattr(args, "workspace", "."))
    
    # Initialize facade
    aos = AgentOS(workspace_root=workspace)
    
    # Run the boot async loop cleanly
    try:
        loop = asyncio.get_event_loop()
    except RuntimeError:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        
    loop.run_until_complete(aos.boot())

    try:
        if args.command == "run":
            print(f"Goal: {args.goal}")
            res = loop.run_until_complete(aos.execute_goal(args.goal))
            print(f"Status: {res['status'].upper()}")
            if res["status"] == "failed":
                print(f"Error: {res.get('error')}")
                sys.exit(1)
        elif args.command == "status":
            print(aos.status())
        elif args.command == "report":
            print(aos.optimizer.generate_report())
    finally:
        aos.shutdown()

if __name__ == "__main__":
    main()
