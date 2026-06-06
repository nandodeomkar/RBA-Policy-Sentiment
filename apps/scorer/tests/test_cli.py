"""Phase A smoke tests: the CLI wires up all four subcommands and runs."""

import pytest

from rba_scorer.cli import main


@pytest.mark.parametrize("command", ["ingest", "score", "benchmark", "export"])
def test_subcommand_parses_and_runs(command: str) -> None:
    # Each stub returns 0; this proves the subcommand is registered and wired.
    assert main([command]) == 0


def test_requires_a_subcommand() -> None:
    # argparse exits (code 2) when no subcommand is given.
    with pytest.raises(SystemExit):
        main([])
