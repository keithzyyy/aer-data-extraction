import argparse
import json
import tempfile
from collections.abc import Sequence
from pathlib import Path

import pandas as pd

from src.rin_maintenance_standardizer import (
    DEFAULT_STANDARDIZATION_CONFIG,
    MaintenanceStage2BResult,
    load_standardization_config,
    prepare_rin_maintenance,
)


DEFAULT_OUTPUT_DIR = Path("data/standardize")
DESCRIPTOR_INPUT_FILENAME = "rin_maintenance_descriptor_metrics.csv"
COST_INPUT_FILENAME = "rin_maintenance_cost_metrics.csv"
RUN_REPORT_INPUT_FILENAME = "rin_maintenance_run_report.csv"
DESCRIPTOR_OUTPUT_FILENAME = "rin_maintenance_descriptor_standardized.csv"
COST_OUTPUT_FILENAME = "rin_maintenance_cost_standardized.csv"
MAPPING_OUTPUT_FILENAME = "rin_maintenance_workbook_mapping.csv"
RELATIONSHIPS_OUTPUT_FILENAME = (
    "rin_maintenance_cost_descriptor_relationships.csv"
)
ISSUES_OUTPUT_FILENAME = "rin_maintenance_issues.csv"
SUMMARY_OUTPUT_FILENAME = "rin_maintenance_stage2_summary.json"


def parse_args(
    argv: Sequence[str] | None = None,
) -> argparse.Namespace:
    """Parse the Stage 2 standardisation command-line arguments."""
    # Build one parser for the thin file-based Stage 2 entry point.
    parser = argparse.ArgumentParser(
        description=(
            "Enrich and standardize canonical RIN maintenance CSVs."
        )
    )

    # Require the Stage 1 artifact directory and authoritative manifest.
    parser.add_argument(
        "--input-dir",
        type=Path,
        required=True,
        help="Directory containing the three Stage 1 maintenance CSVs",
    )
    parser.add_argument(
        "--manifest",
        type=Path,
        required=True,
        help="Acquisition manifest CSV containing exact local filenames",
    )

    # Default Stage 2 outputs to their separate project data boundary.
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=DEFAULT_OUTPUT_DIR,
        help="Directory for standardized Stage 2 artifacts",
    )

    # Allow reviewed semantic rules to be selected without changing code.
    parser.add_argument(
        "--config",
        type=Path,
        default=DEFAULT_STANDARDIZATION_CONFIG,
        help="Stage 2 standardisation JSON configuration",
    )

    # Require explicit permission before replacing prior Stage 2 artifacts.
    parser.add_argument(
        "--overwrite",
        action="store_true",
        help="Replace existing Stage 2 artifacts",
    )

    # Parse caller-supplied arguments or the process command line.
    return parser.parse_args(argv)


def _input_paths(input_dir: Path) -> dict[str, Path]:
    """Resolve the fixed Stage 1 artifact paths."""
    # Keep Stage 1 filenames central so validation and reading cannot diverge.
    return {
        "descriptor": input_dir / DESCRIPTOR_INPUT_FILENAME,
        "cost": input_dir / COST_INPUT_FILENAME,
        "run_report": input_dir / RUN_REPORT_INPUT_FILENAME,
    }


def _output_paths(output_dir: Path) -> dict[str, Path]:
    """Resolve the fixed Stage 2 artifact paths."""
    # Keep the complete artifact set central for collision and publication checks.
    return {
        "descriptor": output_dir / DESCRIPTOR_OUTPUT_FILENAME,
        "cost": output_dir / COST_OUTPUT_FILENAME,
        "mapping": output_dir / MAPPING_OUTPUT_FILENAME,
        "relationships": output_dir / RELATIONSHIPS_OUTPUT_FILENAME,
        "issues": output_dir / ISSUES_OUTPUT_FILENAME,
        "summary": output_dir / SUMMARY_OUTPUT_FILENAME,
    }


def _status_counts(table: pd.DataFrame, column: str) -> dict[str, int]:
    """Count one factual status column in a JSON-safe mapping."""
    # Include missing statuses explicitly instead of dropping unexplained rows.
    counts: dict[str, int] = {}
    for value, count in table[column].value_counts(
        dropna=False,
    ).items():
        key = "<missing>" if pd.isna(value) else str(value)
        counts[key] = int(count)
    return counts


def _build_summary(result: MaintenanceStage2BResult) -> dict[str, object]:
    """Build the durable Stage 2 completeness and row-count summary."""
    # Preserve the four stage-specific facts before deriving overall completion.
    completeness = {
        "extraction_complete": bool(result.extraction_complete),
        "stage2a_complete": bool(result.stage2a_complete),
        "stage2b_complete": bool(result.stage2b_complete),
        "panel_complete": bool(result.panel_complete),
    }
    pipeline_complete = all(completeness.values())

    # Count retained and analytically eligible rows across both tables.
    row_counts = {
        "descriptor_rows": int(len(result.descriptor_metrics)),
        "descriptor_analytic_rows": int(
            result.descriptor_metrics["analytic_row_eligible"]
            .fillna(False)
            .astype(bool)
            .sum()
        ),
        "cost_rows": int(len(result.cost_metrics)),
        "cost_analytic_rows": int(
            result.cost_metrics["analytic_row_eligible"]
            .fillna(False)
            .astype(bool)
            .sum()
        ),
        "workbook_mappings": int(len(result.workbook_mapping)),
        "cost_descriptor_relationships": int(
            len(result.cost_descriptor_relationships)
        ),
        "issues": int(len(result.issues)),
    }

    # Separate issue severities so blocking errors remain visible to Stage 3.
    issue_counts = {
        "errors": int(
            result.issues["severity"]
            .astype("string")
            .str.casefold()
            .eq("error")
            .sum()
        ),
        "warnings": int(
            result.issues["severity"]
            .astype("string")
            .str.casefold()
            .eq("warning")
            .sum()
        ),
    }

    # Record relationship and ratio outcomes for reconciliation without rereading CSVs.
    status_counts = {
        "relationship_status": _status_counts(
            result.cost_descriptor_relationships,
            "relationship_status",
        ),
        "installed_ratio_status": _status_counts(
            result.cost_descriptor_relationships,
            "installed_ratio_status",
        ),
        "serviced_ratio_status": _status_counts(
            result.cost_descriptor_relationships,
            "serviced_ratio_status",
        ),
    }

    # Return one stable, human-readable summary document.
    return {
        **completeness,
        "pipeline_complete": pipeline_complete,
        "row_counts": row_counts,
        "issue_counts": issue_counts,
        "status_counts": status_counts,
    }


def _write_outputs(
    output_dir: Path,
    result: MaintenanceStage2BResult,
    summary: dict[str, object],
) -> None:
    """Stage and publish the complete Stage 2 artifact set."""
    # Resolve final paths once so staging and publication remain synchronized.
    output_paths = _output_paths(output_dir)

    # Serialize every artifact successfully before replacing published files.
    with tempfile.TemporaryDirectory(
        prefix=".rin_maintenance_stage2_",
        dir=output_dir,
    ) as staging_directory:
        staging_dir = Path(staging_directory)
        staged_paths = {
            name: staging_dir / path.name
            for name, path in output_paths.items()
        }

        # Stage each DataFrame without a pandas index or source-value changes.
        tables = {
            "descriptor": result.descriptor_metrics,
            "cost": result.cost_metrics,
            "mapping": result.workbook_mapping,
            "relationships": result.cost_descriptor_relationships,
            "issues": result.issues,
        }
        for name, table in tables.items():
            table.to_csv(
                staged_paths[name],
                index=False,
                encoding="utf-8",
            )

        # Stage the durable completeness summary after all tabular serialization.
        staged_paths["summary"].write_text(
            json.dumps(summary, indent=2, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )

        # Publish all data artifacts before the summary that describes their set.
        for name in (
            "descriptor",
            "cost",
            "mapping",
            "relationships",
            "issues",
        ):
            staged_paths[name].replace(output_paths[name])
            print(
                f"[standardize] Wrote {len(tables[name])} row(s) to "
                f"{output_paths[name].resolve()}"
            )

        # Publish the summary last as the durable completion signal.
        staged_paths["summary"].replace(output_paths["summary"])
        print(
            "[standardize] Wrote Stage 2 summary to "
            f"{output_paths['summary'].resolve()}"
        )


def standardize_rin_maintenance_files(
    input_dir: Path,
    manifest_path: Path,
    *,
    output_dir: Path = DEFAULT_OUTPUT_DIR,
    config_path: Path = DEFAULT_STANDARDIZATION_CONFIG,
    overwrite: bool = False,
) -> int:
    """Run Stage 2 from canonical CSV inputs and persist its result."""
    # Normalize caller paths without requiring them to exist yet.
    resolved_input_dir = Path(input_dir)
    resolved_manifest_path = Path(manifest_path)
    resolved_output_dir = Path(output_dir)
    resolved_config_path = Path(config_path)

    # Validate the Stage 1 directory before resolving its fixed artifacts.
    print(f"[standardize] Reading Stage 1 inputs from {resolved_input_dir}")
    if not resolved_input_dir.is_dir():
        print(
            "[standardize] Error: input directory does not exist: "
            f"{resolved_input_dir}"
        )
        return 2
    input_paths = _input_paths(resolved_input_dir)

    # Require every fixed Stage 1 artifact before any Stage 2 processing.
    missing_inputs = [
        path for path in input_paths.values() if not path.is_file()
    ]
    if missing_inputs:
        missing_names = ", ".join(path.name for path in missing_inputs)
        print(
            "[standardize] Error: missing required Stage 1 file(s): "
            f"{missing_names}"
        )
        return 2

    # Require the authoritative manifest as a regular input file.
    if not resolved_manifest_path.is_file():
        print(
            "[standardize] Error: manifest file does not exist: "
            f"{resolved_manifest_path}"
        )
        return 2

    # Keep Stage 2 outputs outside the Stage 1 artifact directory.
    absolute_input_dir = resolved_input_dir.resolve()
    absolute_output_dir = resolved_output_dir.resolve()
    if (
        absolute_output_dir == absolute_input_dir
        or absolute_input_dir in absolute_output_dir.parents
    ):
        print(
            "[standardize] Error: output directory cannot be the input "
            "directory or one of its descendants"
        )
        return 2

    # Validate semantic rules before creating or replacing output artifacts.
    try:
        load_standardization_config(resolved_config_path)
    except Exception as error:
        print(
            f"[standardize] Error: {type(error).__name__}: {error}"
        )
        return 2

    # Validate or create the separate Stage 2 output directory.
    if resolved_output_dir.exists() and not resolved_output_dir.is_dir():
        print(
            "[standardize] Error: output path is not a directory: "
            f"{resolved_output_dir}"
        )
        return 2
    try:
        resolved_output_dir.mkdir(parents=True, exist_ok=True)
    except Exception as error:
        print(
            "[standardize] Error: could not create output directory: "
            f"{type(error).__name__}: {error}"
        )
        return 2

    # Refuse to replace any member of an earlier Stage 2 artifact set implicitly.
    output_paths = _output_paths(resolved_output_dir)
    collisions = [
        path for path in output_paths.values() if path.exists()
    ]
    if collisions and not overwrite:
        collision_names = ", ".join(path.name for path in collisions)
        print(
            "[standardize] Error: output file(s) already exist; use "
            f"--overwrite to replace them: {collision_names}"
        )
        return 2

    # Read source artifacts without modifying their files or submitted columns.
    try:
        descriptor_metrics = pd.read_csv(input_paths["descriptor"])
        cost_metrics = pd.read_csv(input_paths["cost"])
        run_report = pd.read_csv(input_paths["run_report"])
        manifest = pd.read_csv(resolved_manifest_path)
    except Exception as error:
        print(
            "[standardize] Error: could not read an input CSV: "
            f"{type(error).__name__}: {error}"
        )
        return 2

    # Delegate all enrichment and semantic transformation to the core module.
    print("[standardize] Running Stage 2A and Stage 2B")
    try:
        result = prepare_rin_maintenance(
            descriptor_metrics,
            cost_metrics,
            run_report,
            manifest,
            config_path=resolved_config_path,
        )
    except Exception as error:
        print(
            "[standardize] Error: Stage 2 processing failed: "
            f"{type(error).__name__}: {error}"
        )
        return 2

    # Build and persist one complete result set with its durable summary.
    summary = _build_summary(result)
    try:
        _write_outputs(resolved_output_dir, result, summary)
    except Exception as error:
        print(
            "[standardize] Error: could not write Stage 2 outputs: "
            f"{type(error).__name__}: {error}"
        )
        return 2

    # Distinguish complete publication inputs from usable investigative outputs.
    if summary["pipeline_complete"]:
        print("[standardize] Complete: all completeness checks passed")
        return 0
    print(
        "[standardize] Incomplete: outputs were saved; inspect the "
        "summary and issues"
    )
    return 1


def main(argv: Sequence[str] | None = None) -> int:
    """Run the Stage 2 standardisation command-line interface."""
    # Parse the command line once at the executable boundary.
    args = parse_args(argv)

    # Forward every public option to the file-based workflow.
    return standardize_rin_maintenance_files(
        args.input_dir,
        args.manifest,
        output_dir=args.output_dir,
        config_path=args.config,
        overwrite=args.overwrite,
    )


if __name__ == "__main__":
    # Return the documented exit code to the invoking shell.
    raise SystemExit(main())
