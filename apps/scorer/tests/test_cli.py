"""CLI smoke tests: subcommands are wired; stubs run; ingest parses (no network)."""

import pytest

from rba_scorer.cli import build_parser, main


@pytest.mark.parametrize("command", ["score", "export"])
def test_stub_subcommand_runs(command: str) -> None:
    # Still-stubbed commands (Phases D–E) return 0 without side effects.
    # `benchmark` is implemented (Phase C) and is covered in test_benchmark.py.
    assert main([command]) == 0


@pytest.mark.parametrize(
    "argv",
    [["ingest"], ["ingest", "--since", "2021-01-01"], ["ingest", "--force"], ["score", "--force"]],
)
def test_subcommand_parses(argv: list[str]) -> None:
    # Parse only (don't execute) so the network-touching `ingest` doesn't run.
    namespace = build_parser().parse_args(argv)
    assert hasattr(namespace, "func")


def test_requires_a_subcommand() -> None:
    with pytest.raises(SystemExit):
        main([])
