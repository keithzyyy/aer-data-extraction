import io
import json
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from unittest.mock import patch

import pandas as pd

from scripts import build_rin_maintenance_model as cli
from src.rin_maintenance_model import MaintenanceModelResult


def _create_stage2_inputs(root: Path) -> Path:
    """Create the complete fixed Stage 2 artifact set."""
    # Create one input directory and its five readable CSV artifacts.
    input_dir = root / "standardize"
    input_dir.mkdir()
    for filename in (
        cli.DESCRIPTOR_INPUT_FILENAME,
        cli.COST_INPUT_FILENAME,
        cli.MAPPING_INPUT_FILENAME,
        cli.RELATIONSHIPS_INPUT_FILENAME,
        cli.ISSUES_INPUT_FILENAME,
    ):
        pd.DataFrame([{"source": filename}]).to_csv(
            input_dir / filename,
            index=False,
        )

    # Create one internally consistent Stage 2 completeness summary.
    summary = {
        "extraction_complete": True,
        "stage2a_complete": True,
        "stage2b_complete": True,
        "panel_complete": True,
        "pipeline_complete": True,
    }
    (input_dir / cli.STAGE2_SUMMARY_INPUT_FILENAME).write_text(
        json.dumps(summary),
        encoding="utf-8",
    )
    return input_dir


def _make_model_result(
    *,
    complete: bool = True,
) -> MaintenanceModelResult:
    """Build a small fabricated Stage 3 result for CLI tests."""
    # Build compact dimensions using the public model output names.
    business = pd.DataFrame(
        [
            {
                "business_id": "grid_a",
                "business_name": "Grid A",
                "business_sort_order": 1,
            }
        ]
    )
    periods = pd.DataFrame(
        [
            {
                "reporting_period": "2019-20",
                "period_start_year": 2019,
                "period_end_year": 2020,
                "period_sort_order": 1,
                "is_common_panel": True,
            }
        ]
    )
    categories = pd.DataFrame(
        [
            {
                "maintenance_category_key": "lines::towers",
                "maintenance_activity_id": "lines",
                "maintenance_activity": "Lines",
                "maintenance_asset_id": "towers",
                "maintenance_asset": "Towers",
                "appears_in_descriptor": True,
                "appears_in_cost": True,
                "maintenance_category_sort_order": 1,
            }
        ]
    )
    metrics = pd.DataFrame(
        [
            {
                "metric_id": "asset_quantity_at_year_end",
                "metric_name": "Asset quantity at year end",
                "metric_group": "quantity",
                "metric_sort_order": 1,
            }
        ]
    )
    workbooks = pd.DataFrame(
        [
            {
                "source_workbook": "grid-a.xlsx",
                "business_id": "grid_a",
                "reporting_period": "2019-20",
            }
        ]
    )

    # Build one descriptor record and one cost record without pandas indexes.
    descriptor_fact = pd.DataFrame(
        [
            {
                "business_id": "grid_a",
                "reporting_period": "2019-20",
                "maintenance_category_key": "lines::towers",
                "metric_id": "asset_quantity_at_year_end",
                "metric_value": 10.0,
            }
        ]
    )
    cost_fact = pd.DataFrame(
        [
            {
                "business_id": "grid_a",
                "reporting_period": "2019-20",
                "maintenance_category_key": "lines::towers",
                "routine_expenditure_aud": 100.0,
            }
        ]
    )
    issues = pd.DataFrame(
        []
        if complete
        else [
            {
                "stage": "2B",
                "severity": "error",
                "issue_code": "missing_unit",
                "model_action": "excluded_from_analytic_fact",
            }
        ]
    )

    # Align the durable publication flags with the fabricated issue state.
    summary = {
        "stage2_completeness": {
            "extraction_complete": True,
            "stage2a_complete": True,
            "stage2b_complete": complete,
            "panel_complete": True,
            "pipeline_complete": complete,
        },
        "model_build_complete": True,
        "source_pipeline_complete": complete,
        "model_complete": complete,
        "publication_status": (
            "complete"
            if complete
            else "usable_with_disclosed_exceptions"
        ),
        "common_panel_periods": ["2019-20"],
        "row_counts": {
            "descriptor_fact_rows": 1,
            "cost_fact_rows": 1,
            "excluded_source_rows": 0 if complete else 1,
        },
        "status_counts": {
            "relationship_status": {
                "matched_with_denominator": 1,
            }
        },
    }

    # Return the same public result contract used by the real model builder.
    return MaintenanceModelResult(
        business_dimension=business,
        reporting_period_dimension=periods,
        maintenance_category_dimension=categories,
        metric_dimension=metrics,
        source_workbook_dimension=workbooks,
        descriptor_fact=descriptor_fact,
        cost_fact=cost_fact,
        issues=issues,
        summary=summary,
    )


class Stage3CliWorkflowTests(unittest.TestCase):
    def test_complete_run_writes_all_artifacts_and_exits_zero(self) -> None:
        # Arrange readable Stage 2 inputs and an isolated model directory.
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            input_dir = _create_stage2_inputs(root)
            output_dir = root / "models"
            result = _make_model_result()
            printed_output = io.StringIO()

            # Execute the file workflow with semantic construction mocked.
            with (
                patch.object(
                    cli,
                    "build_rin_maintenance_model",
                    return_value=result,
                ) as build_mock,
                redirect_stdout(printed_output),
            ):
                exit_code = cli.build_rin_maintenance_model_files(
                    input_dir,
                    output_dir=output_dir,
                )

            # Read representative outputs and the publication summary.
            output_paths = cli._output_paths(output_dir)
            descriptor = pd.read_csv(output_paths["descriptor_fact"])
            cost = pd.read_csv(output_paths["cost_fact"])
            summary = json.loads(
                output_paths["summary"].read_text(encoding="utf-8")
            )

            # Assert the complete fixed artifact set and CLI contract.
            self.assertEqual(exit_code, 0)
            self.assertTrue(
                all(path.is_file() for path in output_paths.values())
            )
            self.assertNotIn("Unnamed: 0", descriptor.columns)
            self.assertNotIn("Unnamed: 0", cost.columns)
            self.assertTrue(summary["model_complete"])
            self.assertEqual(build_mock.call_count, 1)
            self.assertIn(
                "[model] Complete: model and upstream checks passed",
                printed_output.getvalue(),
            )

    def test_incomplete_run_saves_outputs_and_exits_one(self) -> None:
        # Arrange valid inputs and a model with one disclosed source exception.
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            input_dir = _create_stage2_inputs(root)
            output_dir = root / "models"
            result = _make_model_result(complete=False)
            printed_output = io.StringIO()

            # Execute the same publication path used for complete models.
            with (
                patch.object(
                    cli,
                    "build_rin_maintenance_model",
                    return_value=result,
                ),
                redirect_stdout(printed_output),
            ):
                exit_code = cli.build_rin_maintenance_model_files(
                    input_dir,
                    output_dir=output_dir,
                )

            # Read the durable summary after all usable tables are published.
            output_paths = cli._output_paths(output_dir)
            summary = json.loads(
                output_paths["summary"].read_text(encoding="utf-8")
            )

            # Assert incompleteness remains explicit without withholding data.
            self.assertEqual(exit_code, 1)
            self.assertTrue(
                all(path.is_file() for path in output_paths.values())
            )
            self.assertFalse(summary["model_complete"])
            self.assertEqual(
                summary["publication_status"],
                "usable_with_disclosed_exceptions",
            )
            self.assertIn(
                "[model] Incomplete: usable outputs were saved",
                printed_output.getvalue(),
            )

    def test_missing_inputs_invalid_summary_and_build_failure_exit_two(
        self,
    ) -> None:
        # Arrange one root for independent setup and reading failure cases.
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            input_dir = _create_stage2_inputs(root)

            # Remove one fixed input and assert setup stops before construction.
            (input_dir / cli.COST_INPUT_FILENAME).unlink()
            with (
                patch.object(
                    cli,
                    "build_rin_maintenance_model",
                ) as build_mock,
                redirect_stdout(io.StringIO()),
            ):
                missing_exit = cli.build_rin_maintenance_model_files(
                    input_dir,
                    output_dir=root / "missing-output",
                )
            self.assertEqual(missing_exit, 2)
            build_mock.assert_not_called()

        # Arrange fresh inputs with malformed Stage 2 JSON.
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            input_dir = _create_stage2_inputs(root)
            (input_dir / cli.STAGE2_SUMMARY_INPUT_FILENAME).write_text(
                "{not valid json",
                encoding="utf-8",
            )

            # Execute and assert malformed summaries fail before construction.
            with (
                patch.object(
                    cli,
                    "build_rin_maintenance_model",
                ) as build_mock,
                redirect_stdout(io.StringIO()),
            ):
                summary_exit = cli.build_rin_maintenance_model_files(
                    input_dir,
                    output_dir=root / "summary-output",
                )
            self.assertEqual(summary_exit, 2)
            build_mock.assert_not_called()

        # Arrange fresh inputs for a core model-construction exception.
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            input_dir = _create_stage2_inputs(root)
            output_dir = root / "build-output"

            # Execute and assert construction errors publish no model artifact.
            with (
                patch.object(
                    cli,
                    "build_rin_maintenance_model",
                    side_effect=RuntimeError("invalid grain"),
                ),
                redirect_stdout(io.StringIO()),
            ):
                build_exit = cli.build_rin_maintenance_model_files(
                    input_dir,
                    output_dir=output_dir,
                )
            self.assertEqual(build_exit, 2)
            self.assertFalse(
                any(
                    path.exists()
                    for path in cli._output_paths(output_dir).values()
                )
            )

    def test_invalid_output_location_and_write_failure_exit_two(self) -> None:
        # Arrange readable inputs for path-boundary validation.
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            input_dir = _create_stage2_inputs(root)

            # Execute and assert models cannot be nested under Stage 2 inputs.
            with redirect_stdout(io.StringIO()):
                nested_exit = cli.build_rin_maintenance_model_files(
                    input_dir,
                    output_dir=input_dir / "models",
                )
            self.assertEqual(nested_exit, 2)

        # Arrange fresh inputs and a mocked publication failure.
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            input_dir = _create_stage2_inputs(root)

            # Execute and assert output-writing exceptions use exit code 2.
            with (
                patch.object(
                    cli,
                    "build_rin_maintenance_model",
                    return_value=_make_model_result(),
                ),
                patch.object(
                    cli,
                    "_write_outputs",
                    side_effect=OSError("disk unavailable"),
                ),
                redirect_stdout(io.StringIO()),
            ):
                write_exit = cli.build_rin_maintenance_model_files(
                    input_dir,
                    output_dir=root / "write-output",
                )
            self.assertEqual(write_exit, 2)

    def test_collision_requires_overwrite_before_model_build(self) -> None:
        # Arrange readable inputs and one member of an existing model set.
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            input_dir = _create_stage2_inputs(root)
            output_dir = root / "models"
            output_dir.mkdir()
            stale_fact = output_dir / cli.COST_FACT_OUTPUT_FILENAME
            stale_fact.write_text("stale\n", encoding="utf-8")

            # Execute without overwrite and assert construction never starts.
            with (
                patch.object(
                    cli,
                    "build_rin_maintenance_model",
                ) as build_mock,
                redirect_stdout(io.StringIO()),
            ):
                collision_exit = cli.build_rin_maintenance_model_files(
                    input_dir,
                    output_dir=output_dir,
                )
            self.assertEqual(collision_exit, 2)
            build_mock.assert_not_called()
            self.assertEqual(
                stale_fact.read_text(encoding="utf-8"),
                "stale\n",
            )

            # Execute with overwrite and replace the complete model artifact set.
            with (
                patch.object(
                    cli,
                    "build_rin_maintenance_model",
                    return_value=_make_model_result(),
                ),
                redirect_stdout(io.StringIO()),
            ):
                overwrite_exit = cli.build_rin_maintenance_model_files(
                    input_dir,
                    output_dir=output_dir,
                    overwrite=True,
                )

            # Assert overwrite publishes current facts and all model artifacts.
            self.assertEqual(overwrite_exit, 0)
            self.assertNotEqual(
                stale_fact.read_text(encoding="utf-8"),
                "stale\n",
            )
            self.assertTrue(
                all(
                    path.is_file()
                    for path in cli._output_paths(output_dir).values()
                )
            )


class Stage3CommandLineTests(unittest.TestCase):
    def test_parse_args_defaults_and_main_forwarding(self) -> None:
        # Arrange the minimum required Stage 3 command-line arguments.
        argv = ["--input-dir", "data/standardize"]

        # Parse arguments and assert the reviewed default model boundary.
        args = cli.parse_args(argv)
        self.assertEqual(args.input_dir, Path("data/standardize"))
        self.assertEqual(args.output_dir, Path("data/models"))
        self.assertFalse(args.overwrite)

        # Execute main with every optional argument supplied explicitly.
        forwarded_argv = [
            *argv,
            "--output-dir",
            "alternate/models",
            "--overwrite",
        ]
        with patch.object(
            cli,
            "build_rin_maintenance_model_files",
            return_value=1,
        ) as workflow_mock:
            exit_code = cli.main(forwarded_argv)

        # Assert main returns and forwards the workflow's public options.
        self.assertEqual(exit_code, 1)
        workflow_mock.assert_called_once_with(
            Path("data/standardize"),
            output_dir=Path("alternate/models"),
            overwrite=True,
        )


if __name__ == "__main__":
    # Run this isolated unittest module when invoked directly.
    unittest.main()
