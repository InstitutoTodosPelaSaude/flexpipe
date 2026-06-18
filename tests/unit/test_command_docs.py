from pathlib import Path

DOCS = Path(__file__).parent.parent.parent / "docs" / "commands.md"


def test_command_reference_does_not_use_removed_flags():
    text = DOCS.read_text(encoding="utf-8")
    removed_flags = [
        "--remote-metadata",
        "--remote-sequences",
        "--date-column",
        "--date-formats",
        "--latitude-column",
        "--longitude-column",
        "--new-cache",
        "--existing-cache",
        "--trait-column",
        "--hues",
        "--color-scheme",
    ]

    for flag in removed_flags:
        assert flag not in text


def test_command_reference_uses_current_flags_for_common_helpers():
    text = DOCS.read_text(encoding="utf-8")
    current_snippets = [
        "--pathoplexus-metadata",
        "--pathoplexus-sequences",
        "--date-field date",
        "--policy dates.yaml",
        "--filter-log results/ingest/filter_log.tsv",
        "--qc-report results/qc_report.json",
        "--columns country division location",
        "--new-latlongs latlongs.tsv",
        "--cache cache/cache_coordinates.tsv",
        "--colours name2hue.tsv",
        "--levels continent country division location",
    ]

    for snippet in current_snippets:
        assert snippet in text
