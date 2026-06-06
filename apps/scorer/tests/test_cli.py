"""CLI smoke tests: subcommands are wired; stubs run; ingest parses (no network)."""

import pytest

from rba_scorer.cli import build_parser, main


def test_stub_subcommand_runs() -> None:
    # `export` is still a stub (Phase E) and returns 0 without side effects.
    # `ingest`/`benchmark`/`score` are implemented and covered in their own tests.
    assert main(["export"]) == 0


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
