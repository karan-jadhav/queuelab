import argparse

from queuelab import __version__


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="queuelab",
        description="Run QueueLab reliability experiments.",
    )
    parser.add_argument(
        "--version",
        action="version",
        version=f"queuelab {__version__}",
    )

    subcommands = parser.add_subparsers(dest="command")

    dataset = subcommands.add_parser(
        "dataset",
        help="Download and inspect normalized job datasets.",
    )
    dataset.add_subparsers(dest="dataset_command")

    subcommands.add_parser(
        "run",
        help="Run an experiment backend.",
    )

    report = subcommands.add_parser(
        "report",
        help="Export and summarize experiment results.",
    )
    report.add_subparsers(dest="report_command")

    return parser


def main() -> None:
    parser = build_parser()
    parser.parse_args()
