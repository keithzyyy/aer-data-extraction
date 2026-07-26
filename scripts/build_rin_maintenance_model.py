"""Command-line entry point for the Stage 3 RIN maintenance model."""

from __future__ import annotations

import argparse
import json
import tempfile
from collections.abc import Sequence
from pathlib import Path

import pandas as pd

from src.rin_maintenance_model import (
    MaintenanceModelResult,
    build_rin_maintenance_model,
)


DEFAULT_OUTPUT_DIR = Path("data/models")
DESCRIPTOR_INPUT_FILENAME = "rin_maintenance_descriptor_standardized.csv"
COST_INPUT_FILENAME = "rin_maintenance_cost_standardized.csv"
MAPPING_INPUT_FILENAME = "rin_maintenance_workbook_mapping.csv"
RELATIONSHIPS_INPUT_FILENAME = (
    "rin_maintenance_cost_descriptor_relationships.csv"
)
ISSUES_INPUT_FILENAME = "rin_maintenance_issues.csv"
STAGE2_SUMMARY_INPUT_FILENAME = "rin_maintenance_stage2_summary.json"

BUSINESS_OUTPUT_FILENAME = "dim_business.csv"
REPORTING_PERIOD_OUTPUT_FILENAME = "dim_reporting_period.csv"
CATEGORY_OUTPUT_FILENAME = "dim_maintenance_category.csv"
METRIC_OUTPUT_FILENAME = "dim_metric.csv"
SOURCE_WORKBOOK_OUTPUT_FILENAME = "dim_source_workbook.csv"
DESCRIPTOR_FACT_OUTPUT_FILENAME = "fact_descriptor_metric.csv"
COST_FACT_OUTPUT_FILENAME = "fact_maintenance_cost.csv"
ISSUES_OUTPUT_FILENAME = "rin_maintenance_model_issues.csv"
MODEL_SUMMARY_OUTPUT_FILENAME = "rin_maintenance_model_summary.json"


def parse_args(
    argv: Sequence[str] | None = None,
) -> argparse.Namespace:
    """Parse the Stage 3 model-building command-line arguments."""
    # Build one parser for the thin file-based Stage 3 boundary.
    parser = argparse.ArgumentParser(
        description=(
            "Build Power BI model tables from standardized RIN maintenance "
            "artifacts."
        )
    )

    # Require the directory containing the complete Stage 2 artifact set.
    parser.add_argument(
        "--input-dir",
        type=Path,
        required=True,
        help="Directory containing the six Stage 2 artifacts",
    )

    # Default model outputs to their separate Stage 3 project boundary.
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=DEFAULT_OUTPUT_DIR,
        help="Directory for Power BI model CSVs and summary",
    )

    # Require explicit permission before replacing an earlier model artifact set.
    parser.add_argument(
        "--overwrite",
        action="store_true",
        help="Replace existing Stage 3 model artifacts",
    )

    # Parse caller-supplied arguments or the process command line.
    return parser.parse_args(argv)


def _input_paths(input_dir: Path) -> dict[str, Path]:
    """Resolve the fixed Stage 2 artifact paths."""
    # Keep input names central so validation and reading cannot diverge.
    return {
        "descriptor": input_dir / DESCRIPTOR_INPUT_FILENAME,
        "cost": input_dir / COST_INPUT_FILENAME,
        "mapping": input_dir / MAPPING_INPUT_FILENAME,
        "relationships": input_dir / RELATIONSHIPS_INPUT_FILENAME,
        "issues": input_dir / ISSUES_INPUT_FILENAME,
        "stage2_summary": input_dir / STAGE2_SUMMARY_INPUT_FILENAME,
    }


def _output_paths(output_dir: Path) -> dict[str, Path]:
    """Resolve the fixed Stage 3 artifact paths."""
    # Keep the complete model set central for collision and publication checks.
    return {
        "business": output_dir / BUSINESS_OUTPUT_FILENAME,
        "reporting_period": (
            output_dir / REPORTING_PERIOD_OUTPUT_FILENAME
        ),
        "category": output_dir / CATEGORY_OUTPUT_FILENAME,
        "metric": output_dir / METRIC_OUTPUT_FILENAME,
        "source_workbook": (
            output_dir / SOURCE_WORKBOOK_OUTPUT_FILENAME
        ),
        "descriptor_fact": (
            output_dir / DESCRIPTOR_FACT_OUTPUT_FILENAME
        ),
        "cost_fact": output_dir / COST_FACT_OUTPUT_FILENAME,
        "issues": output_dir / ISSUES_OUTPUT_FILENAME,
        "summary": output_dir / MODEL_SUMMARY_OUTPUT_FILENAME,
    }


def _read_stage2_inputs(
    input_paths: dict[str, Path],
) -> tuple[
    pd.DataFrame,
    pd.DataFrame,
    pd.DataFrame,
    pd.DataFrame,
    pd.DataFrame,
    dict[str, object],
]:
    """Read the complete fixed Stage 2 artifact set."""
    # Read each tabular artifact without altering its submitted columns.
    descriptor = pd.read_csv(input_paths["descriptor"])
    cost = pd.read_csv(input_paths["cost"])
    mapping = pd.read_csv(input_paths["mapping"])
    relationships = pd.read_csv(input_paths["relationships"])
    issues = pd.read_csv(input_paths["issues"])

    # Decode the durable Stage 2 summary as the publication control input.
    stage2_summary = json.loads(
        input_paths["stage2_summary"].read_text(encoding="utf-8")
    )
    if not isinstance(stage2_summary, dict):
        raise ValueError("Stage 2 summary must contain a JSON object")
    return (
        descriptor,
        cost,
        mapping,
        relationships,
        issues,
        stage2_summary,
    )


def _write_outputs(
    output_dir: Path,
    result: MaintenanceModelResult,
) -> None:
    """Stage and publish the complete Stage 3 model artifact set."""
    # Resolve final paths once so staging and publication remain synchronized.
    output_paths = _output_paths(output_dir)

    # Serialize every artifact successfully before replacing published files.
    with tempfile.TemporaryDirectory(
        prefix=".rin_maintenance_model_",
        dir=output_dir,
    ) as staging_directory:
        staging_dir = Path(staging_directory)
        staged_paths = {
            name: staging_dir / path.name
            for name, path in output_paths.items()
        }

        # Stage every dimension, fact, and issue table without pandas indexes.
        tables = {
            "business": result.business_dimension,
            "reporting_period": result.reporting_period_dimension,
            "category": result.maintenance_category_dimension,
            "metric": result.metric_dimension,
            "source_workbook": result.source_workbook_dimension,
            "descriptor_fact": result.descriptor_fact,
            "cost_fact": result.cost_fact,
            "issues": result.issues,
        }
        for name, table in tables.items():
            table.to_csv(
                staged_paths[name],
                index=False,
                encoding="utf-8",
            )

        # Stage the durable model summary after every CSV serializes.
        staged_paths["summary"].write_text(
            json.dumps(
                result.summary,
                indent=2,
                ensure_ascii=False,
            )
            + "\n",
            encoding="utf-8",
        )

        # Publish all model tables before the summary that describes their set.
        for name in (
            "business",
            "reporting_period",
            "category",
            "metric",
            "source_workbook",
            "descriptor_fact",
            "cost_fact",
            "issues",
        ):
            staged_paths[name].replace(output_paths[name])
            print(
                f"[model] Wrote {len(tables[name])} row(s) to "
                f"{output_paths[name].resolve()}"
            )

        # Publish the summary last as the durable completion signal.
        staged_paths["summary"].replace(output_paths["summary"])
        print(
            "[model] Wrote model summary to "
            f"{output_paths['summary'].resolve()}"
        )


def build_rin_maintenance_model_files(
    input_dir: Path,
    *,
    output_dir: Path = DEFAULT_OUTPUT_DIR,
    overwrite: bool = False,
) -> int:
    """Build and persist the Stage 3 model from Stage 2 artifacts."""
    # Normalize caller paths without requiring them to exist yet.
    resolved_input_dir = Path(input_dir)
    resolved_output_dir = Path(output_dir)

    # Validate the Stage 2 directory before resolving its fixed artifacts.
    print(f"[model] Reading Stage 2 inputs from {resolved_input_dir}")
    if not resolved_input_dir.is_dir():
        print(
            "[model] Error: input directory does not exist: "
            f"{resolved_input_dir}"
        )
        return 2
    input_paths = _input_paths(resolved_input_dir)

    # Require the complete Stage 2 artifact set before model construction.
    missing_inputs = [
        path for path in input_paths.values() if not path.is_file()
    ]
    if missing_inputs:
        missing_names = ", ".join(path.name for path in missing_inputs)
        print(
            "[model] Error: missing required Stage 2 file(s): "
            f"{missing_names}"
        )
        return 2

    # Keep Stage 3 outputs outside the Stage 2 input boundary.
    absolute_input_dir = resolved_input_dir.resolve()
    absolute_output_dir = resolved_output_dir.resolve()
    if (
        absolute_output_dir == absolute_input_dir
        or absolute_input_dir in absolute_output_dir.parents
    ):
        print(
            "[model] Error: output directory cannot be the input "
            "directory or one of its descendants"
        )
        return 2

    # Validate or create the separate Stage 3 model directory.
    if resolved_output_dir.exists() and not resolved_output_dir.is_dir():
        print(
            "[model] Error: output path is not a directory: "
            f"{resolved_output_dir}"
        )
        return 2
    try:
        resolved_output_dir.mkdir(parents=True, exist_ok=True)
    except Exception as error:
        print(
            "[model] Error: could not create output directory: "
            f"{type(error).__name__}: {error}"
        )
        return 2

    # Refuse to replace any member of an earlier model set implicitly.
    output_paths = _output_paths(resolved_output_dir)
    collisions = [
        path for path in output_paths.values() if path.exists()
    ]
    if collisions and not overwrite:
        collision_names = ", ".join(path.name for path in collisions)
        print(
            "[model] Error: output file(s) already exist; use "
            f"--overwrite to replace them: {collision_names}"
        )
        return 2

    # Read all Stage 2 inputs before invoking semantic model construction.
    try:
        (
            descriptor,
            cost,
            mapping,
            relationships,
            issues,
            stage2_summary,
        ) = _read_stage2_inputs(input_paths)
    except Exception as error:
        print(
            "[model] Error: could not read Stage 2 inputs: "
            f"{type(error).__name__}: {error}"
        )
        return 2

    # Delegate all table grains and relationship logic to the core module.
    print("[model] Building Stage 3 dimensions and facts")
    try:
        result = build_rin_maintenance_model(
            descriptor,
            cost,
            mapping,
            relationships,
            issues,
            stage2_summary,
        )
    except Exception as error:
        print(
            "[model] Error: model construction failed: "
            f"{type(error).__name__}: {error}"
        )
        return 2

    # Stage and publish one model artifact set with its summary last.
    try:
        _write_outputs(resolved_output_dir, result)
    except Exception as error:
        print(
            "[model] Error: could not write Stage 3 outputs: "
            f"{type(error).__name__}: {error}"
        )
        return 2

    # Distinguish complete publication inputs from usable disclosed exceptions.
    if result.summary["model_complete"]:
        print("[model] Complete: model and upstream checks passed")
        return 0
    print(
        "[model] Incomplete: usable outputs were saved; inspect the "
        "model summary and issues"
    )
    return 1


def main(argv: Sequence[str] | None = None) -> int:
    """Run the Stage 3 model-building command-line interface."""
    # Parse the command line once at the executable boundary.
    args = parse_args(argv)

    # Forward every public option to the file-based workflow.
    return build_rin_maintenance_model_files(
        args.input_dir,
        output_dir=args.output_dir,
        overwrite=args.overwrite,
    )


if __name__ == "__main__":
    # Return the documented exit code to the invoking shell.
    raise SystemExit(main())
