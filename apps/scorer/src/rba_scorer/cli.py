"""Command-line entry point for the RBA Policy Sentiment scorer.

Subcommands (built out across implementation-plan Phases B–E):
    ingest      Fetch + parse RBA decision releases into data/decisions.json
    score       Run the reconciled ensemble over ingested decisions
    benchmark   Evaluate scores against the labelled benchmark (the M0 gate)
    export      Write the published CSV from scores.json

Phase A: subcommands are wired but not yet implemented — each logs a notice
and exits 0 so the scaffold is runnable end to end.
"""

from __future__ import annotations

import argparse
import logging
import sys
from collections.abc import Sequence

logger = logging.getLogger("rba_scorer")


def _not_implemented(name: str) -> int:
    logger.warning("`%s` is not implemented yet (Phase A scaffolding).", name)
    return 0


def cmd_ingest(args: argparse.Namespace) -> int:
    from rba_scorer.ingest.pipeline import run_ingest

    decisions = run_ingest(since_year=int(args.since[:4]), force=args.force)
    logger.info("ingested %d decisions -> data/decisions.json", len(decisions))
    return 0


def cmd_score(args: argparse.Namespace) -> int:
    return _not_implemented("score")


def cmd_benchmark(args: argparse.Namespace) -> int:
    return _not_implemented("benchmark")


def cmd_export(args: argparse.Namespace) -> int:
    return _not_implemented("export")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="rba-scorer",
        description="RBA Policy Sentiment — offline scorer (Milestone 0).",
    )
    parser.add_argument("-v", "--verbose", action="store_true", help="Enable debug logging.")
    sub = parser.add_subparsers(dest="command", required=True)

    p_ingest = sub.add_parser("ingest", help="Fetch + parse RBA decision releases.")
    p_ingest.add_argument(
        "--since",
        default="2020-01-01",
        help="Earliest decision date to ingest (YYYY-MM-DD).",
    )
    p_ingest.add_argument(
        "--force",
        action="store_true",
        help="Bypass the raw-page cache and re-fetch from rba.gov.au.",
    )
    p_ingest.set_defaults(func=cmd_ingest)

    p_score = sub.add_parser("score", help="Score ingested decisions with the ensemble.")
    p_score.add_argument(
        "--force",
        action="store_true",
        help="Re-score even if the engine_version is unchanged.",
    )
    p_score.set_defaults(func=cmd_score)

    p_benchmark = sub.add_parser(
        "benchmark", help="Evaluate scores against the labelled benchmark."
    )
    p_benchmark.set_defaults(func=cmd_benchmark)

    p_export = sub.add_parser("export", help="Write the published CSV from scores.json.")
    p_export.set_defaults(func=cmd_export)

    return parser


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
