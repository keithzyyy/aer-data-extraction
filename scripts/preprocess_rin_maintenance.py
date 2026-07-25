import argparse
import json
import tempfile
from collections.abc import Sequence
from pathlib import Path

import pandas as pd

from src.rin_maintenance_heading_extractor import (
    DEFAULT_SCHEMA_PATH,
    MaintenanceExtractionResult,
    extract_rin_maintenance,
    load_expected_schema,
)


SUPPORTED_WORKBOOK_SUFFIXES = {".xlsx", ".xlsm"}
DESCRIPTOR_OUTPUT_FILENAME = "rin_maintenance_descriptor_metrics.csv"
COST_OUTPUT_FILENAME = "rin_maintenance_cost_metrics.csv"
REPORT_OUTPUT_FILENAME = "rin_maintenance_run_report.csv"
REPORT_COLUMNS = [
    "source_workbook",
    "status",
    "reporting_period",
    "layout_profile",
    "descriptor_row_count",
    "cost_row_count",
    "warnings",
    "error",
    "run_complete",
]


def parse_args(
    argv: Sequence[str] | None = None,
) -> argparse.Namespace:
    """Parse the maintenance preprocessing command-line arguments."""
    # Build one parser for the thin batch-extraction entry point.
    parser = argparse.ArgumentParser(
        description=(
            "Extract canonical 2.8 Maintenance tables from downloaded "
            "RIN workbooks."
        )
    )

    # Require explicit source and destination directories for each run.
    parser.add_argument(
        "--raw-dir",
        type=Path,
        required=True,
        help="Directory containing downloaded .xlsx and .xlsm workbooks",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        required=True,
        help="Directory in which to write canonical CSV outputs",
    )

    # Allow schema experiments without changing the extractor module.
    parser.add_argument(
        "--schema",
        type=Path,
        default=DEFAULT_SCHEMA_PATH,
        help="Maintenance expected-heading JSON schema",
    )

    # Require an explicit flag before replacing derived output artifacts.
    parser.add_argument(
        "--overwrite",
        action="store_true",
        help="Replace existing preprocessing CSV outputs",
    )

    # Parse supplied arguments or fall back to the process command line.
    return parser.parse_args(argv)


def _find_workbooks(raw_dir: Path) -> list[Path]:
    """Return supported direct-child workbooks in deterministic order."""
    # Keep only real workbook files and exclude temporary Excel lock files.
    workbooks = [
        path
        for path in raw_dir.iterdir()
        if path.is_file()
        and not path.name.startswith("~$")
        and path.suffix.casefold() in SUPPORTED_WORKBOOK_SUFFIXES
    ]

    # Stabilise processing and output order across repeated runs.
    return sorted(workbooks, key=lambda path: path.name.casefold())


def _validate_result_columns(
    result: MaintenanceExtractionResult,
    descriptor_columns: list[str],
    cost_columns: list[str],
) -> None:
    """Require one-workbook outputs to match the configured contracts."""
    # Compare descriptor names and order before accepting any descriptor rows.
    actual_descriptor_columns = list(result.descriptor_metrics.columns)
    if actual_descriptor_columns != descriptor_columns:
        raise ValueError(
            "Descriptor columns do not match the expected schema: "
            f"expected {descriptor_columns}, got {actual_descriptor_columns}"
        )

    # Compare cost names and order before accepting any cost rows.
    actual_cost_columns = list(result.cost_metrics.columns)
    if actual_cost_columns != cost_columns:
        raise ValueError(
            "Cost columns do not match the expected schema: "
            f"expected {cost_columns}, got {actual_cost_columns}"
        )


def _output_paths(output_dir: Path) -> dict[str, Path]:
    """Resolve the three fixed output artifact paths."""
    # Keep filenames central so validation, staging, and publication agree.
    return {
        "descriptor": output_dir / DESCRIPTOR_OUTPUT_FILENAME,
        "cost": output_dir / COST_OUTPUT_FILENAME,
        "report": output_dir / REPORT_OUTPUT_FILENAME,
    }


def _write_outputs(
    output_dir: Path,
    descriptor_metrics: pd.DataFrame | None,
    cost_metrics: pd.DataFrame | None,
    run_report: pd.DataFrame,
    *,
    overwrite: bool,
) -> None:
    """Stage and publish the current preprocessing artifact set."""
    # Resolve final paths once so staged files publish to known destinations.
    output_paths = _output_paths(output_dir)

    # Serialize every intended artifact before changing published outputs.
    with tempfile.TemporaryDirectory(
        prefix=".rin_maintenance_",
        dir=output_dir,
    ) as staging_directory:
        staging_dir = Path(staging_directory)
        staged_report = staging_dir / REPORT_OUTPUT_FILENAME

        # Stage both canonical tables only when at least one workbook succeeded.
        staged_descriptor = None
        staged_cost = None
        if descriptor_metrics is not None and cost_metrics is not None:
            staged_descriptor = staging_dir / DESCRIPTOR_OUTPUT_FILENAME
            staged_cost = staging_dir / COST_OUTPUT_FILENAME
            descriptor_metrics.to_csv(
                staged_descriptor,
                index=False,
                encoding="utf-8",
            )
            cost_metrics.to_csv(
                staged_cost,
                index=False,
                encoding="utf-8",
            )

        # Stage the run report that describes the complete artifact set.
        run_report.to_csv(
            staged_report,
            index=False,
            encoding="utf-8",
        )

        # Publish canonical tables before the report that describes their run.
        if staged_descriptor is not None and staged_cost is not None:
            staged_descriptor.replace(output_paths["descriptor"])
            staged_cost.replace(output_paths["cost"])
            print(
                f"[preprocess] Wrote {len(descriptor_metrics)} "
                f"descriptor row(s) to {output_paths['descriptor'].resolve()}"
            )
            print(
                f"[preprocess] Wrote {len(cost_metrics)} "
                f"cost row(s) to {output_paths['cost'].resolve()}"
            )
        elif overwrite:
            # Remove prior canonical tables so they cannot resemble this failed run.
            for output_name in ("descriptor", "cost"):
                stale_path = output_paths[output_name]
                if stale_path.exists():
                    stale_path.unlink()

        # Publish the report last as the durable statement of run completeness.
        staged_report.replace(output_paths["report"])
        print(
            "[preprocess] Wrote run report to "
            f"{output_paths['report'].resolve()}"
        )


def preprocess_rin_maintenance(
    raw_dir: Path,
    output_dir: Path,
    *,
    schema_path: Path = DEFAULT_SCHEMA_PATH,
    overwrite: bool = False,
) -> int:
    """Extract and batch canonical maintenance tables from one directory."""
    # Normalize caller inputs without requiring the paths to exist yet.
    resolved_raw_dir = Path(raw_dir)
    resolved_output_dir = Path(output_dir)
    resolved_schema_path = Path(schema_path)

    # Validate the immutable source directory before inspecting its contents.
    print(f"[preprocess] Scanning {resolved_raw_dir}")
    if not resolved_raw_dir.is_dir():
        print(
            f"[preprocess] Error: raw directory does not exist: "
            f"{resolved_raw_dir}"
        )
        return 2

    # Keep generated outputs outside the immutable raw-workbook tree.
    absolute_raw_dir = resolved_raw_dir.resolve()
    absolute_output_dir = resolved_output_dir.resolve()
    if (
        absolute_output_dir == absolute_raw_dir
        or absolute_raw_dir in absolute_output_dir.parents
    ):
        print(
            "[preprocess] Error: output directory cannot be the raw "
            "directory or one of its descendants"
        )
        return 2

    # Validate the global semantic schema once before attempting workbooks.
    try:
        schema = load_expected_schema(resolved_schema_path)
    except Exception as error:
        print(
            f"[preprocess] Error: {type(error).__name__}: {error}"
        )
        return 2

    # Discover supported workbooks without traversing nested directories.
    try:
        workbooks = _find_workbooks(resolved_raw_dir)
    except Exception as error:
        print(
            f"[preprocess] Error: could not scan raw directory: "
            f"{type(error).__name__}: {error}"
        )
        return 2

    # Stop setup when no supported source workbook can be processed.
    print(f"[preprocess] Found {len(workbooks)} workbook(s)")
    if not workbooks:
        print("[preprocess] Error: no supported workbooks found")
        return 2

    # Validate or create the derived-output directory before extraction.
    if resolved_output_dir.exists() and not resolved_output_dir.is_dir():
        print(
            f"[preprocess] Error: output path is not a directory: "
            f"{resolved_output_dir}"
        )
        return 2
    try:
        resolved_output_dir.mkdir(parents=True, exist_ok=True)
    except Exception as error:
        print(
            f"[preprocess] Error: could not create output directory: "
            f"{type(error).__name__}: {error}"
        )
        return 2

    # Refuse to replace any member of an earlier artifact set implicitly.
    output_paths = _output_paths(resolved_output_dir)
    collisions = [
        path
        for path in output_paths.values()
        if path.exists()
    ]
    if collisions and not overwrite:
        collision_names = ", ".join(path.name for path in collisions)
        print(
            "[preprocess] Error: output file(s) already exist; use "
            f"--overwrite to replace them: {collision_names}"
        )
        return 2

    # Read canonical column contracts from the already validated schema.
    descriptor_columns = list(
        schema["sections"]["descriptor_metrics"]["output_columns"]
    )
    cost_columns = list(
        schema["sections"]["cost_metrics"]["output_columns"]
    )

    # Collect successful tables and one factual report row per workbook.
    descriptor_tables: list[pd.DataFrame] = []
    cost_tables: list[pd.DataFrame] = []
    report_rows: list[dict[str, object]] = []

    # Attempt every workbook so one failure does not hide later results.
    for position, workbook_path in enumerate(workbooks, start=1):
        print(
            f"[preprocess] Processing {position}/{len(workbooks)}: "
            f"{workbook_path.name}"
        )
        try:
            # Delegate heading discovery and cell extraction to the core module.
            result = extract_rin_maintenance(
                workbook_path,
                schema_path=resolved_schema_path,
                print_warnings=True,
            )

            # Reject schema drift before combining this workbook's records.
            _validate_result_columns(
                result,
                descriptor_columns,
                cost_columns,
            )

            # Preserve the extractor's row order when collecting successful tables.
            descriptor_tables.append(result.descriptor_metrics)
            cost_tables.append(result.cost_metrics)

            # Record successful metadata and warnings without interpreting them.
            report_rows.append(
                {
                    "source_workbook": workbook_path.name,
                    "status": "success",
                    "reporting_period": result.reporting_period,
                    "layout_profile": result.layout_profile,
                    "descriptor_row_count": len(
                        result.descriptor_metrics
                    ),
                    "cost_row_count": len(result.cost_metrics),
                    "warnings": json.dumps(
                        result.warnings,
                        ensure_ascii=False,
                    ),
                    "error": "",
                }
            )
        except Exception as error:
            # Record a normal per-workbook failure and continue the batch.
            error_detail = f"{type(error).__name__}: {error}"
            print(
                f"[preprocess] Failed {workbook_path.name}: "
                f"{error_detail}"
            )
            report_rows.append(
                {
                    "source_workbook": workbook_path.name,
                    "status": "failed",
                    "reporting_period": "",
                    "layout_profile": "",
                    "descriptor_row_count": 0,
                    "cost_row_count": 0,
                    "warnings": json.dumps([]),
                    "error": error_detail,
                }
            )

    # Compute one run-level completion value after every workbook was attempted.
    succeeded_count = len(descriptor_tables)
    failed_count = len(workbooks) - succeeded_count
    run_complete = failed_count == 0
    for report_row in report_rows:
        report_row["run_complete"] = run_complete

    # Construct the fixed report schema even when every workbook failed.
    run_report = pd.DataFrame(
        report_rows,
        columns=REPORT_COLUMNS,
    )

    # Concatenate only successful results without deduplicating or reshaping them.
    descriptor_metrics = None
    cost_metrics = None
    if descriptor_tables and cost_tables:
        descriptor_metrics = pd.concat(
            descriptor_tables,
            ignore_index=True,
        )
        cost_metrics = pd.concat(
            cost_tables,
            ignore_index=True,
        )

    # Stage and publish the current run's complete artifact set.
    try:
        _write_outputs(
            resolved_output_dir,
            descriptor_metrics,
            cost_metrics,
            run_report,
            overwrite=overwrite,
        )
    except Exception as error:
        print(
            f"[preprocess] Error: could not write outputs: "
            f"{type(error).__name__}: {error}"
        )
        return 2

    # Summarize completion and return the matching automation exit code.
    if run_complete:
        print(
            f"[preprocess] Complete: {succeeded_count} succeeded, "
            f"{failed_count} failed"
        )
        return 0

    print(
        f"[preprocess] Incomplete: {succeeded_count} succeeded, "
        f"{failed_count} failed"
    )
    return 1


def main(argv: Sequence[str] | None = None) -> int:
    """Run maintenance preprocessing from command-line arguments."""
    # Parse the external interface before handing work to the orchestrator.
    args = parse_args(argv)

    # Return the orchestrator status for the process-level exit code.
    return preprocess_rin_maintenance(
        args.raw_dir,
        args.output_dir,
        schema_path=args.schema,
        overwrite=args.overwrite,
    )


if __name__ == "__main__":
    # Expose the returned status to shells and future automation.
    raise SystemExit(main())
