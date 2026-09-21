"""CLI for the experimental replay bundle."""

import argparse
import json

from .core import create_bundle, replay_bundle


def main() -> None:
    parser = argparse.ArgumentParser(prog="python -m decision_replay")
    subparsers = parser.add_subparsers(dest="command", required=True)
    create = subparsers.add_parser("create")
    create.add_argument("output")
    create.add_argument("--scenario", default="clean")
    replay = subparsers.add_parser("replay")
    replay.add_argument("bundle")
    args = parser.parse_args()
    result = create_bundle(args.output, args.scenario) if args.command == "create" else replay_bundle(args.bundle)
    print(json.dumps(result, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()