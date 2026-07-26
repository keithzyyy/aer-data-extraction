import io
import json
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from unittest.mock import patch

import pandas as pd

from scripts import standardize_rin_maintenance as cli
from src.rin_maintenance_standardizer import MaintenanceStage2BResult


def _create_stage1_inputs(root: Path) -> tuple[Path, Path]:
    """Create minimal readable Stage 1 and manifest CSV inputs."""
    # Create the fixed Stage 1 directory and its three required artifacts.
    input_dir = root / "processed"
    input_dir.mkdir()
    for filename in (
        cli.DESCRIPTOR_INPUT_FILENAME,
        cli.COST_INPUT_FILENAME,
        cli.RUN_REPORT_INPUT_FILENAME,
    ):
        pd.DataFrame([{"source": filename}]).to_csv(
            input_dir / filename,
            index=False,
        )

    # Create a separate readable manifest for the mocked core boundary.
    manifest_path = root / "rin_manifest.csv"
    pd.DataFrame([{"local_filename": "sample.xlsx"}]).to_csv(
        manifest_path,
        index=False,
    )
    return input_dir, manifest_path


def _make_stage2_result(
    *,
    complete: bool = True,
) -> MaintenanceStage2BResult:
    """Build a small fabricated Stage 2 result for file orchestration tests."""
    # Build standardized tables containing both retained and analytic rows.
    descriptor = pd.DataFrame(
        [
            {
                "source_workbook": "sample.xlsx",
                "analytic_row_eligible": True,
                "asset_quantity_at_year_end_standard": 10.0,
            },
            {
                "source_workbook": "sample.xlsx",
                "analytic_row_eligible": False,
                "asset_quantity_at_year_end_standard": pd.NA,
            },
        ]
    )
    cost = pd.DataFrame(
        [
            {
                "source_workbook": "sample.xlsx",
                "analytic_row_eligible": True,
                "total_maintenance_expenditure_standard": 30.0,
            }
        ]
    )

    # Build workbook and relationship evidence used by the JSON summary.
    mapping = pd.DataFrame(
        [
            {
                "source_workbook": "sample.xlsx",
                "metadata_match_status": "validated_manifest_match",
            }
        ]
    )
    relationships = pd.DataFrame(
        [
            {
                "source_workbook": "sample.xlsx",
                "relationship_status": "matched_with_denominator",
                "installed_ratio_status": "calculated",
                "serviced_ratio_status": "calculated",
            },
            {
                "source_workbook": "sample.xlsx",
                "relationship_status": "no_descriptor_match",
                "installed_ratio_status": "no_descriptor_match",
                "serviced_ratio_status": "no_descriptor_match",
            },
        ]
    )

    # Represent complete and incomplete runs with factual issue severity.
    issues = pd.DataFrame(
        [
            {
                "stage": "2B",
                "severity": "warning" if complete else "error",
                "issue_code": (
                    "retained_source_category"
                    if complete
                    else "missing_unit"
                ),
            }
        ]
    )

    # Return the same public result contract as the real core workflow.
    return MaintenanceStage2BResult(
        descriptor_metrics=descriptor,
        cost_metrics=cost,
        workbook_mapping=mapping,
        cost_descriptor_relationships=relationships,
        issues=issues,
        extraction_complete=True,
        stage2a_complete=True,
        stage2b_complete=complete,
        panel_complete=True,
    )


class Stage2CliWorkflowTests(unittest.TestCase):
    def test_complete_run_writes_all_artifacts_and_summary(self) -> None:
        # Arrange readable inputs, a complete result, and isolated output paths.
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            input_dir, manifest_path = _create_stage1_inputs(root)
            output_dir = root / "standardize"
            result = _make_stage2_result()
            printed_output = io.StringIO()

            # Execute the file workflow with semantic processing mocked.
            with (
                patch.object(
                    cli,
                    "load_standardization_config",
                    return_value={"schema_version": 1},
                ),
                patch.object(
                    cli,
                    "prepare_rin_maintenance",
                    return_value=result,
                ) as prepare_mock,
                redirect_stdout(printed_output),
            ):
                exit_code = cli.standardize_rin_maintenance_files(
                    input_dir,
                    manifest_path,
                    output_dir=output_dir,
                )

            # Read every artifact to verify the durable output contract.
            output_paths = cli._output_paths(output_dir)
            descriptor = pd.read_csv(output_paths["descriptor"])
            relationships = pd.read_csv(output_paths["relationships"])
            summary = json.loads(
                output_paths["summary"].read_text(encoding="utf-8")
            )

            # Assert complete publication, index-free CSVs, counts, and statuses.
            self.assertEqual(exit_code, 0)
            self.assertTrue(all(path.is_file() for path in output_paths.values()))
            self.assertNotIn("Unnamed: 0", descriptor.columns)
            self.assertNotIn("Unnamed: 0", relationships.columns)
            self.assertTrue(summary["pipeline_complete"])
            self.assertEqual(summary["row_counts"]["descriptor_rows"], 2)
            self.assertEqual(
                summary["row_counts"]["descriptor_analytic_rows"],
                1,
            )
            self.assertEqual(summary["issue_counts"]["warnings"], 1)
            self.assertEqual(
                summary["status_counts"]["relationship_status"],
                {
                    "matched_with_denominator": 1,
                    "no_descriptor_match": 1,
                },
            )
            self.assertEqual(prepare_mock.call_count, 1)
            self.assertIn(
                "[standardize] Complete: all completeness checks passed",
                printed_output.getvalue(),
            )

    def test_incomplete_run_saves_outputs_and_exits_one(self) -> None:
        # Arrange an analytically incomplete but otherwise usable Stage 2 result.
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            input_dir, manifest_path = _create_stage1_inputs(root)
            output_dir = root / "standardize"
            result = _make_stage2_result(complete=False)
            printed_output = io.StringIO()

            # Execute the same publication path used for complete results.
            with (
                patch.object(
                    cli,
                    "load_standardization_config",
                    return_value={"schema_version": 1},
                ),
                patch.object(
                    cli,
                    "prepare_rin_maintenance",
                    return_value=result,
                ),
                redirect_stdout(printed_output),
            ):
                exit_code = cli.standardize_rin_maintenance_files(
                    input_dir,
                    manifest_path,
                    output_dir=output_dir,
                )

            # Read the durable summary after all usable outputs were published.
            output_paths = cli._output_paths(output_dir)
            summary = json.loads(
                output_paths["summary"].read_text(encoding="utf-8")
            )

            # Assert incompleteness remains durable without withholding data.
            self.assertEqual(exit_code, 1)
            self.assertTrue(all(path.is_file() for path in output_paths.values()))
            self.assertFalse(summary["stage2b_complete"])
            self.assertFalse(summary["pipeline_complete"])
            self.assertEqual(summary["issue_counts"]["errors"], 1)
            self.assertIn(
                "[standardize] Incomplete: outputs were saved",
                printed_output.getvalue(),
            )

    def test_missing_inputs_invalid_config_and_processing_failure_exit_two(
        self,
    ) -> None:
        # Arrange one root for independent setup and processing failure cases.
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            input_dir, manifest_path = _create_stage1_inputs(root)

            # Remove one fixed input and assert setup stops before processing.
            (input_dir / cli.COST_INPUT_FILENAME).unlink()
            with redirect_stdout(io.StringIO()):
                missing_exit = cli.standardize_rin_maintenance_files(
                    input_dir,
                    manifest_path,
                    output_dir=root / "missing-output",
                )
            self.assertEqual(missing_exit, 2)

        # Arrange fresh readable inputs for invalid configuration handling.
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            input_dir, manifest_path = _create_stage1_inputs(root)

            # Execute and assert configuration errors stop before CSV processing.
            with (
                patch.object(
                    cli,
                    "load_standardization_config",
                    side_effect=ValueError("invalid config"),
                ),
                patch.object(cli, "prepare_rin_maintenance") as prepare_mock,
                redirect_stdout(io.StringIO()),
            ):
                config_exit = cli.standardize_rin_maintenance_files(
                    input_dir,
                    manifest_path,
                    output_dir=root / "config-output",
                )
            self.assertEqual(config_exit, 2)
            prepare_mock.assert_not_called()

        # Arrange fresh readable inputs for a core processing exception.
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            input_dir, manifest_path = _create_stage1_inputs(root)

            # Execute and assert no artifact is published after processing fails.
            output_dir = root / "process-output"
            with (
                patch.object(
                    cli,
                    "load_standardization_config",
                    return_value={"schema_version": 1},
                ),
                patch.object(
                    cli,
                    "prepare_rin_maintenance",
                    side_effect=RuntimeError("processing failed"),
                ),
                redirect_stdout(io.StringIO()),
            ):
                process_exit = cli.standardize_rin_maintenance_files(
                    input_dir,
                    manifest_path,
                    output_dir=output_dir,
                )
            self.assertEqual(process_exit, 2)
            self.assertFalse(
                any(path.exists() for path in cli._output_paths(output_dir).values())
            )

    def test_invalid_output_location_and_write_failure_exit_two(self) -> None:
        # Arrange readable inputs for path-boundary validation.
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            input_dir, manifest_path = _create_stage1_inputs(root)

            # Execute and assert outputs cannot be nested under Stage 1 inputs.
            with (
                patch.object(
                    cli,
                    "load_standardization_config",
                    return_value={"schema_version": 1},
                ),
                redirect_stdout(io.StringIO()),
            ):
                nested_exit = cli.standardize_rin_maintenance_files(
                    input_dir,
                    manifest_path,
                    output_dir=input_dir / "standardize",
                )
            self.assertEqual(nested_exit, 2)

        # Arrange fresh inputs and a mocked publication failure.
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            input_dir, manifest_path = _create_stage1_inputs(root)

            # Execute and assert output-writing exceptions use setup exit code 2.
            with (
                patch.object(
                    cli,
                    "load_standardization_config",
                    return_value={"schema_version": 1},
                ),
                patch.object(
                    cli,
                    "prepare_rin_maintenance",
                    return_value=_make_stage2_result(),
                ),
                patch.object(
                    cli,
                    "_write_outputs",
                    side_effect=OSError("disk unavailable"),
                ),
                redirect_stdout(io.StringIO()),
            ):
                write_exit = cli.standardize_rin_maintenance_files(
                    input_dir,
                    manifest_path,
                    output_dir=root / "write-output",
                )
            self.assertEqual(write_exit, 2)

    def test_collision_requires_overwrite_before_processing(self) -> None:
        # Arrange readable inputs and one member of an existing artifact set.
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            input_dir, manifest_path = _create_stage1_inputs(root)
            output_dir = root / "standardize"
            output_dir.mkdir()
            stale_relationships = (
                output_dir / cli.RELATIONSHIPS_OUTPUT_FILENAME
            )
            stale_relationships.write_text("stale\n", encoding="utf-8")

            # Execute without overwrite and assert processing never starts.
            with (
                patch.object(
                    cli,
                    "load_standardization_config",
                    return_value={"schema_version": 1},
                ),
                patch.object(cli, "prepare_rin_maintenance") as prepare_mock,
                redirect_stdout(io.StringIO()),
            ):
                collision_exit = cli.standardize_rin_maintenance_files(
                    input_dir,
                    manifest_path,
                    output_dir=output_dir,
                )
            self.assertEqual(collision_exit, 2)
            prepare_mock.assert_not_called()
            self.assertEqual(
                stale_relationships.read_text(encoding="utf-8"),
                "stale\n",
            )

            # Execute with overwrite and replace the complete artifact set.
            with (
                patch.object(
                    cli,
                    "load_standardization_config",
                    return_value={"schema_version": 1},
                ),
                patch.object(
                    cli,
                    "prepare_rin_maintenance",
                    return_value=_make_stage2_result(),
                ),
                redirect_stdout(io.StringIO()),
            ):
                overwrite_exit = cli.standardize_rin_maintenance_files(
                    input_dir,
                    manifest_path,
                    output_dir=output_dir,
                    overwrite=True,
                )

            # Assert overwrite publishes current relationships and all artifacts.
            self.assertEqual(overwrite_exit, 0)
            self.assertNotEqual(
                stale_relationships.read_text(encoding="utf-8"),
                "stale\n",
            )
            self.assertTrue(
                all(
                    path.is_file()
                    for path in cli._output_paths(output_dir).values()
                )
            )


class Stage2CommandLineTests(unittest.TestCase):
    def test_parse_args_defaults_and_main_forwarding(self) -> None:
        # Arrange the minimum required command-line arguments.
        argv = [
            "--input-dir",
            "data/processed",
            "--manifest",
            "data/rin_manifest.csv",
        ]

        # Parse arguments and assert the reviewed default output boundary.
        args = cli.parse_args(argv)
        self.assertEqual(args.input_dir, Path("data/processed"))
        self.assertEqual(args.manifest, Path("data/rin_manifest.csv"))
        self.assertEqual(args.output_dir, Path("data/standardize"))
        self.assertEqual(args.config, cli.DEFAULT_STANDARDIZATION_CONFIG)
        self.assertFalse(args.overwrite)

        # Execute main with every optional argument supplied explicitly.
        forwarded_argv = [
            *argv,
            "--output-dir",
            "alternate/output",
            "--config",
            "alternate/config.json",
            "--overwrite",
        ]
        with patch.object(
            cli,
            "standardize_rin_maintenance_files",
            return_value=1,
        ) as workflow_mock:
            exit_code = cli.main(forwarded_argv)

        # Assert main returns and forwards the workflow's complete CLI contract.
        self.assertEqual(exit_code, 1)
        workflow_mock.assert_called_once_with(
            Path("data/processed"),
            Path("data/rin_manifest.csv"),
            output_dir=Path("alternate/output"),
            config_path=Path("alternate/config.json"),
            overwrite=True,
        )


if __name__ == "__main__":
    # Run this isolated unittest module when invoked directly.
    unittest.main()
