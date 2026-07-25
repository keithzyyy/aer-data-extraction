import io
import json
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from unittest.mock import patch

import pandas as pd

from scripts import preprocess_rin_maintenance as preprocessing
from src.rin_maintenance_heading_extractor import (
    MaintenanceExtractionError,
    MaintenanceExtractionResult,
)


DESCRIPTOR_COLUMNS = ["reporting_period", "source_workbook"]
COST_COLUMNS = ["reporting_period", "source_workbook"]
FAKE_SCHEMA = {
    "sections": {
        "descriptor_metrics": {
            "output_columns": DESCRIPTOR_COLUMNS,
        },
        "cost_metrics": {
            "output_columns": COST_COLUMNS,
        },
    }
}


def _create_workbook_placeholder(path: Path) -> None:
    """Create an empty path that represents a discovered workbook."""
    # Create only the filename because the extractor is mocked in unit tests.
    path.write_bytes(b"")


def _make_result(
    workbook_path: Path,
    *,
    reporting_period: str = "2023-24",
    warnings: list[str] | None = None,
    descriptor_columns: list[str] | None = None,
    cost_columns: list[str] | None = None,
) -> MaintenanceExtractionResult:
    """Build a small extraction result for batch-orchestration tests."""
    # Use caller-selected columns to exercise valid and invalid contracts.
    resolved_descriptor_columns = (
        descriptor_columns
        if descriptor_columns is not None
        else DESCRIPTOR_COLUMNS
    )
    resolved_cost_columns = (
        cost_columns
        if cost_columns is not None
        else COST_COLUMNS
    )

    # Populate one traceable row in each canonical table.
    descriptor_metrics = pd.DataFrame(
        [
            {
                "reporting_period": reporting_period,
                "source_workbook": workbook_path.name,
            }
        ],
        columns=resolved_descriptor_columns,
    )
    cost_metrics = pd.DataFrame(
        [
            {
                "reporting_period": reporting_period,
                "source_workbook": workbook_path.name,
            }
        ],
        columns=resolved_cost_columns,
    )

    # Return the same result shape as the real one-workbook extractor.
    return MaintenanceExtractionResult(
        workbook_path=workbook_path,
        sheet_name="2.8 Maintenance",
        reporting_period=reporting_period,
        template_date=None,
        layout_profile="stacked_baseline",
        descriptor_metrics=descriptor_metrics,
        cost_metrics=cost_metrics,
        header_locations={},
        warnings=warnings or [],
    )


class WorkbookDiscoveryTests(unittest.TestCase):
    def test_find_workbooks_filters_and_sorts_direct_children(self) -> None:
        # Arrange supported, temporary, unsupported, and nested paths.
        with tempfile.TemporaryDirectory() as temporary_directory:
            raw_dir = Path(temporary_directory)
            _create_workbook_placeholder(raw_dir / "b.XLSM")
            _create_workbook_placeholder(raw_dir / "A.xlsx")
            _create_workbook_placeholder(raw_dir / "~$locked.xlsx")
            _create_workbook_placeholder(raw_dir / "notes.csv")
            nested_dir = raw_dir / "nested"
            nested_dir.mkdir()
            _create_workbook_placeholder(nested_dir / "nested.xlsx")

            # Execute direct-child workbook discovery.
            workbooks = preprocessing._find_workbooks(raw_dir)

            # Assert filtering and deterministic case-insensitive ordering.
            self.assertEqual(
                [path.name for path in workbooks],
                ["A.xlsx", "b.XLSM"],
            )


class PreprocessingWorkflowTests(unittest.TestCase):
    def test_complete_run_writes_canonical_outputs_and_report(self) -> None:
        # Arrange two workbook paths and successful extraction results.
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            raw_dir = root / "raw"
            output_dir = root / "processed"
            raw_dir.mkdir()
            first_path = raw_dir / "a.xlsx"
            second_path = raw_dir / "b.xlsm"
            _create_workbook_placeholder(first_path)
            _create_workbook_placeholder(second_path)
            extraction_results = [
                _make_result(first_path, reporting_period="2022-23"),
                _make_result(second_path, reporting_period="2023-24"),
            ]
            printed_output = io.StringIO()

            # Execute the complete batch with schema and extractor boundaries mocked.
            with (
                patch.object(
                    preprocessing,
                    "load_expected_schema",
                    return_value=FAKE_SCHEMA,
                ),
                patch.object(
                    preprocessing,
                    "extract_rin_maintenance",
                    side_effect=extraction_results,
                ) as extract_mock,
                redirect_stdout(printed_output),
            ):
                exit_code = preprocessing.preprocess_rin_maintenance(
                    raw_dir,
                    output_dir,
                )

            # Load each artifact to verify the published batch contract.
            descriptor_output = pd.read_csv(
                output_dir
                / preprocessing.DESCRIPTOR_OUTPUT_FILENAME
            )
            cost_output = pd.read_csv(
                output_dir / preprocessing.COST_OUTPUT_FILENAME
            )
            run_report = pd.read_csv(
                output_dir / preprocessing.REPORT_OUTPUT_FILENAME
            )

            # Assert successful order, schemas, report status, and progress output.
            self.assertEqual(exit_code, 0)
            self.assertEqual(
                list(descriptor_output.columns),
                DESCRIPTOR_COLUMNS,
            )
            self.assertEqual(
                descriptor_output["source_workbook"].tolist(),
                ["a.xlsx", "b.xlsm"],
            )
            self.assertEqual(
                cost_output["source_workbook"].tolist(),
                ["a.xlsx", "b.xlsm"],
            )
            self.assertEqual(
                list(run_report.columns),
                preprocessing.REPORT_COLUMNS,
            )
            self.assertTrue(run_report["run_complete"].all())
            self.assertEqual(extract_mock.call_count, 2)
            self.assertIn(
                "[preprocess] Processing 1/2: a.xlsx",
                printed_output.getvalue(),
            )
            self.assertIn(
                "[preprocess] Complete: 2 succeeded, 0 failed",
                printed_output.getvalue(),
            )

    def test_warning_remains_successful_and_is_json_encoded(self) -> None:
        # Arrange one successful result containing a non-fatal warning.
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            raw_dir = root / "raw"
            output_dir = root / "processed"
            raw_dir.mkdir()
            workbook_path = raw_dir / "warning.xlsx"
            _create_workbook_placeholder(workbook_path)
            warning = "descriptor_metrics: unfamiliar source unit 000' KM"
            extraction_result = _make_result(
                workbook_path,
                warnings=[warning],
            )

            # Execute the batch while returning the warning-bearing result.
            with (
                patch.object(
                    preprocessing,
                    "load_expected_schema",
                    return_value=FAKE_SCHEMA,
                ),
                patch.object(
                    preprocessing,
                    "extract_rin_maintenance",
                    return_value=extraction_result,
                ),
                redirect_stdout(io.StringIO()),
            ):
                exit_code = preprocessing.preprocess_rin_maintenance(
                    raw_dir,
                    output_dir,
                )

            # Read the report and assert warnings do not change success status.
            run_report = pd.read_csv(
                output_dir / preprocessing.REPORT_OUTPUT_FILENAME
            )
            self.assertEqual(exit_code, 0)
            self.assertEqual(run_report.loc[0, "status"], "success")
            self.assertEqual(
                json.loads(run_report.loc[0, "warnings"]),
                [warning],
            )
            self.assertTrue(bool(run_report.loc[0, "run_complete"]))

    def test_partial_failure_saves_successful_rows_and_incomplete_report(
        self,
    ) -> None:
        # Arrange one successful workbook followed by one extraction failure.
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            raw_dir = root / "raw"
            output_dir = root / "processed"
            raw_dir.mkdir()
            success_path = raw_dir / "a-success.xlsx"
            failure_path = raw_dir / "b-failure.xlsx"
            _create_workbook_placeholder(success_path)
            _create_workbook_placeholder(failure_path)
            printed_output = io.StringIO()

            # Execute both attempts while the second raises a structural error.
            with (
                patch.object(
                    preprocessing,
                    "load_expected_schema",
                    return_value=FAKE_SCHEMA,
                ),
                patch.object(
                    preprocessing,
                    "extract_rin_maintenance",
                    side_effect=[
                        _make_result(success_path),
                        MaintenanceExtractionError("missing section"),
                    ],
                ),
                redirect_stdout(printed_output),
            ):
                exit_code = preprocessing.preprocess_rin_maintenance(
                    raw_dir,
                    output_dir,
                )

            # Load partial data and the two-workbook factual report.
            descriptor_output = pd.read_csv(
                output_dir
                / preprocessing.DESCRIPTOR_OUTPUT_FILENAME
            )
            run_report = pd.read_csv(
                output_dir / preprocessing.REPORT_OUTPUT_FILENAME
            )

            # Assert successful data remains available and failure is explicit.
            self.assertEqual(exit_code, 1)
            self.assertEqual(
                descriptor_output["source_workbook"].tolist(),
                ["a-success.xlsx"],
            )
            self.assertEqual(
                run_report["status"].tolist(),
                ["success", "failed"],
            )
            self.assertFalse(run_report["run_complete"].any())
            self.assertIn(
                "MaintenanceExtractionError: missing section",
                run_report.loc[1, "error"],
            )
            self.assertIn(
                "[preprocess] Failed b-failure.xlsx",
                printed_output.getvalue(),
            )
            self.assertIn(
                "[preprocess] Incomplete: 1 succeeded, 1 failed",
                printed_output.getvalue(),
            )

    def test_all_failures_write_only_the_run_report(self) -> None:
        # Arrange two workbook paths that will both fail extraction.
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            raw_dir = root / "raw"
            output_dir = root / "processed"
            raw_dir.mkdir()
            _create_workbook_placeholder(raw_dir / "a.xlsx")
            _create_workbook_placeholder(raw_dir / "b.xlsx")

            # Execute the batch with one reusable per-workbook failure.
            with (
                patch.object(
                    preprocessing,
                    "load_expected_schema",
                    return_value=FAKE_SCHEMA,
                ),
                patch.object(
                    preprocessing,
                    "extract_rin_maintenance",
                    side_effect=MaintenanceExtractionError(
                        "unsupported layout"
                    ),
                ),
                redirect_stdout(io.StringIO()),
            ):
                exit_code = preprocessing.preprocess_rin_maintenance(
                    raw_dir,
                    output_dir,
                )

            # Assert the incomplete report exists without misleading data files.
            run_report_path = (
                output_dir / preprocessing.REPORT_OUTPUT_FILENAME
            )
            self.assertEqual(exit_code, 1)
            self.assertTrue(run_report_path.is_file())
            self.assertFalse(
                (
                    output_dir
                    / preprocessing.DESCRIPTOR_OUTPUT_FILENAME
                ).exists()
            )
            self.assertFalse(
                (
                    output_dir / preprocessing.COST_OUTPUT_FILENAME
                ).exists()
            )
            run_report = pd.read_csv(run_report_path)
            self.assertEqual(
                run_report["status"].tolist(),
                ["failed", "failed"],
            )
            self.assertFalse(run_report["run_complete"].any())

    def test_overwrite_removes_stale_data_after_all_failures(self) -> None:
        # Arrange a new failing run beside a complete stale artifact set.
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            raw_dir = root / "raw"
            output_dir = root / "processed"
            raw_dir.mkdir()
            output_dir.mkdir()
            _create_workbook_placeholder(raw_dir / "failure.xlsx")
            descriptor_path = (
                output_dir
                / preprocessing.DESCRIPTOR_OUTPUT_FILENAME
            )
            cost_path = output_dir / preprocessing.COST_OUTPUT_FILENAME
            report_path = output_dir / preprocessing.REPORT_OUTPUT_FILENAME
            descriptor_path.write_text("stale", encoding="utf-8")
            cost_path.write_text("stale", encoding="utf-8")
            report_path.write_text("stale", encoding="utf-8")

            # Execute an explicitly authorised replacement that cannot extract data.
            with (
                patch.object(
                    preprocessing,
                    "load_expected_schema",
                    return_value=FAKE_SCHEMA,
                ),
                patch.object(
                    preprocessing,
                    "extract_rin_maintenance",
                    side_effect=RuntimeError("unexpected workbook issue"),
                ),
                redirect_stdout(io.StringIO()),
            ):
                exit_code = preprocessing.preprocess_rin_maintenance(
                    raw_dir,
                    output_dir,
                    overwrite=True,
                )

            # Assert stale data is removed and the current report replaces it.
            self.assertEqual(exit_code, 1)
            self.assertFalse(descriptor_path.exists())
            self.assertFalse(cost_path.exists())
            run_report = pd.read_csv(report_path)
            self.assertEqual(run_report.loc[0, "status"], "failed")
            self.assertIn(
                "RuntimeError: unexpected workbook issue",
                run_report.loc[0, "error"],
            )

    def test_existing_output_without_overwrite_stops_before_extraction(
        self,
    ) -> None:
        # Arrange a source workbook and one colliding output artifact.
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            raw_dir = root / "raw"
            output_dir = root / "processed"
            raw_dir.mkdir()
            output_dir.mkdir()
            _create_workbook_placeholder(raw_dir / "source.xlsx")
            collision_path = (
                output_dir
                / preprocessing.DESCRIPTOR_OUTPUT_FILENAME
            )
            collision_path.write_text("keep me", encoding="utf-8")

            # Execute without overwrite while observing the extractor boundary.
            with (
                patch.object(
                    preprocessing,
                    "load_expected_schema",
                    return_value=FAKE_SCHEMA,
                ),
                patch.object(
                    preprocessing,
                    "extract_rin_maintenance",
                ) as extract_mock,
                redirect_stdout(io.StringIO()),
            ):
                exit_code = preprocessing.preprocess_rin_maintenance(
                    raw_dir,
                    output_dir,
                )

            # Assert setup fails without extraction or replacement.
            self.assertEqual(exit_code, 2)
            extract_mock.assert_not_called()
            self.assertEqual(
                collision_path.read_text(encoding="utf-8"),
                "keep me",
            )

    def test_missing_raw_directory_returns_setup_error(self) -> None:
        # Arrange a missing raw path and a separate prospective output path.
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            raw_dir = root / "missing"
            output_dir = root / "processed"

            # Execute preprocessing without an available source directory.
            with redirect_stdout(io.StringIO()):
                exit_code = preprocessing.preprocess_rin_maintenance(
                    raw_dir,
                    output_dir,
                )

            # Assert setup fails without creating derived outputs.
            self.assertEqual(exit_code, 2)
            self.assertFalse(output_dir.exists())

    def test_output_nested_inside_raw_directory_is_rejected(self) -> None:
        # Arrange an existing raw directory and a nested output destination.
        with tempfile.TemporaryDirectory() as temporary_directory:
            raw_dir = Path(temporary_directory) / "raw"
            output_dir = raw_dir / "processed"
            raw_dir.mkdir()

            # Execute preprocessing before any output directory is created.
            with redirect_stdout(io.StringIO()):
                exit_code = preprocessing.preprocess_rin_maintenance(
                    raw_dir,
                    output_dir,
                )

            # Assert the immutable raw tree remains free of generated outputs.
            self.assertEqual(exit_code, 2)
            self.assertFalse(output_dir.exists())

    def test_no_supported_workbooks_returns_setup_error(self) -> None:
        # Arrange a raw directory containing only an unsupported file.
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            raw_dir = root / "raw"
            output_dir = root / "processed"
            raw_dir.mkdir()
            (raw_dir / "notes.csv").write_text(
                "not,a,workbook",
                encoding="utf-8",
            )

            # Execute discovery with a valid mocked global schema.
            with (
                patch.object(
                    preprocessing,
                    "load_expected_schema",
                    return_value=FAKE_SCHEMA,
                ),
                redirect_stdout(io.StringIO()),
            ):
                exit_code = preprocessing.preprocess_rin_maintenance(
                    raw_dir,
                    output_dir,
                )

            # Assert no-workbook setup fails without producing outputs.
            self.assertEqual(exit_code, 2)
            self.assertFalse(output_dir.exists())

    def test_invalid_schema_returns_setup_error(self) -> None:
        # Arrange one discoverable workbook and a schema validation failure.
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            raw_dir = root / "raw"
            output_dir = root / "processed"
            raw_dir.mkdir()
            _create_workbook_placeholder(raw_dir / "source.xlsx")

            # Execute preprocessing while global schema validation fails.
            with (
                patch.object(
                    preprocessing,
                    "load_expected_schema",
                    side_effect=MaintenanceExtractionError(
                        "invalid schema"
                    ),
                ),
                patch.object(
                    preprocessing,
                    "extract_rin_maintenance",
                ) as extract_mock,
                redirect_stdout(io.StringIO()),
            ):
                exit_code = preprocessing.preprocess_rin_maintenance(
                    raw_dir,
                    output_dir,
                )

            # Assert the setup error prevents extraction and output creation.
            self.assertEqual(exit_code, 2)
            extract_mock.assert_not_called()
            self.assertFalse(output_dir.exists())

    def test_schema_mismatch_is_recorded_as_workbook_failure(self) -> None:
        # Arrange a returned descriptor table with an unexpected column.
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            raw_dir = root / "raw"
            output_dir = root / "processed"
            raw_dir.mkdir()
            workbook_path = raw_dir / "mismatch.xlsx"
            _create_workbook_placeholder(workbook_path)
            mismatched_result = _make_result(
                workbook_path,
                descriptor_columns=["unexpected_column"],
            )

            # Execute preprocessing with a structurally invalid result.
            with (
                patch.object(
                    preprocessing,
                    "load_expected_schema",
                    return_value=FAKE_SCHEMA,
                ),
                patch.object(
                    preprocessing,
                    "extract_rin_maintenance",
                    return_value=mismatched_result,
                ),
                redirect_stdout(io.StringIO()),
            ):
                exit_code = preprocessing.preprocess_rin_maintenance(
                    raw_dir,
                    output_dir,
                )

            # Assert mismatched rows are excluded and the error is reported.
            run_report = pd.read_csv(
                output_dir / preprocessing.REPORT_OUTPUT_FILENAME
            )
            self.assertEqual(exit_code, 1)
            self.assertEqual(run_report.loc[0, "status"], "failed")
            self.assertIn(
                "ValueError: Descriptor columns do not match",
                run_report.loc[0, "error"],
            )
            self.assertFalse(
                (
                    output_dir
                    / preprocessing.DESCRIPTOR_OUTPUT_FILENAME
                ).exists()
            )


class CommandLineInterfaceTests(unittest.TestCase):
    def test_parse_args_and_main_forward_the_cli_contract(self) -> None:
        # Arrange all documented arguments and a mocked orchestrator status.
        arguments = [
            "--raw-dir",
            "raw-input",
            "--output-dir",
            "csv-output",
            "--schema",
            "schema.json",
            "--overwrite",
        ]

        # Execute main so argument parsing and orchestration are exercised together.
        with patch.object(
            preprocessing,
            "preprocess_rin_maintenance",
            return_value=1,
        ) as preprocess_mock:
            exit_code = preprocessing.main(arguments)

        # Assert paths, overwrite intent, and the orchestrator exit code propagate.
        self.assertEqual(exit_code, 1)
        preprocess_mock.assert_called_once_with(
            Path("raw-input"),
            Path("csv-output"),
            schema_path=Path("schema.json"),
            overwrite=True,
        )


if __name__ == "__main__":
    # Allow the test module to run directly without an additional test runner.
    unittest.main()
