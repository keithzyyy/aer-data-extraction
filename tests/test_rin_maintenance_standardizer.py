import unittest

import pandas as pd
from pandas.testing import assert_frame_equal

from src import rin_maintenance_standardizer as standardizer


POWERLINK_WORKBOOK = "Powerlink 2021-22 sample.xlsx"
POWERLINK_PERIOD = "2021-22"


def _descriptor_row(
    *,
    workbook: str = POWERLINK_WORKBOOK,
    period: object = POWERLINK_PERIOD,
    source_sheet: str = "2.8 Maintenance",
    source_row: object = 12,
    activity: object = "Transmission lines maintenance",
    category: object = "Transmission towers",
    asset_quantity: object = 10.0,
) -> dict[str, object]:
    """Build one complete fabricated canonical descriptor row."""
    # Populate every canonical field so schema checks exercise real contracts.
    return {
        "reporting_period": period,
        "maintenance_activity": activity,
        "maintenance_asset_category": category,
        "measure_asset_quantity": "Number of towers",
        "source_unit": "number",
        "asset_quantity_at_year_end": asset_quantity,
        "quantity_inspected_maintained": 2.0,
        "average_age_of_asset_group": 30.0,
        "inspection_cycle_years": 1.0,
        "maintenance_cycle_years": 3.0,
        "source_workbook": workbook,
        "source_sheet": source_sheet,
        "source_row": source_row,
    }


def _cost_row(
    *,
    workbook: str = POWERLINK_WORKBOOK,
    period: object = POWERLINK_PERIOD,
    source_sheet: str = "2.8 Maintenance",
    source_row: object = 50,
    activity: object = "Transmission lines maintenance",
    subcategory: object = "Transmission towers",
    routine: object = 100.0,
    non_routine: object = 200.0,
) -> dict[str, object]:
    """Build one complete fabricated canonical cost row."""
    # Populate every canonical field so schema checks exercise real contracts.
    return {
        "reporting_period": period,
        "maintenance_activity": activity,
        "maintenance_asset_subcategory": subcategory,
        "source_currency_unit": "$",
        "routine_maintenance_expenditure": routine,
        "non_routine_maintenance_expenditure": non_routine,
        "source_workbook": workbook,
        "source_sheet": source_sheet,
        "source_row": source_row,
    }


def _run_record(
    *,
    workbook: str = POWERLINK_WORKBOOK,
    period: object = POWERLINK_PERIOD,
    status: str = "success",
    run_complete: object = True,
) -> dict[str, object]:
    """Build one fabricated preprocessing run-report record."""
    # Include only fields required by the Stage 2A input contract.
    return {
        "source_workbook": workbook,
        "status": status,
        "reporting_period": period,
        "run_complete": run_complete,
    }


def _manifest_record(
    *,
    business: str = "Powerlink",
    period: object = POWERLINK_PERIOD,
    landing_page_url: object = "https://www.aer.gov.au/documents/powerlink",
    source_page_url: object = "https://www.aer.gov.au/authors/powerlink",
) -> dict[str, object]:
    """Build one fabricated acquisition-manifest record."""
    # Supply authoritative business-period metadata used by reconciliation.
    return {
        "business": business,
        "reporting_period": period,
        "landing_page_url": landing_page_url,
        "source_page_url": source_page_url,
    }


def _input_frames(
    *,
    descriptor_rows: list[dict[str, object]] | None = None,
    cost_rows: list[dict[str, object]] | None = None,
    run_rows: list[dict[str, object]] | None = None,
    manifest_rows: list[dict[str, object]] | None = None,
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    """Build four fabricated Stage 2A input DataFrames."""
    # Use one valid row per canonical table unless a test overrides it.
    resolved_descriptor_rows = (
        descriptor_rows
        if descriptor_rows is not None
        else [_descriptor_row()]
    )
    resolved_cost_rows = (
        cost_rows if cost_rows is not None else [_cost_row()]
    )
    resolved_run_rows = (
        run_rows if run_rows is not None else [_run_record()]
    )
    resolved_manifest_rows = (
        manifest_rows
        if manifest_rows is not None
        else [_manifest_record()]
    )

    # Fix canonical column order independently of row dictionary construction.
    descriptor = pd.DataFrame(
        resolved_descriptor_rows,
        columns=standardizer.DESCRIPTOR_REQUIRED_COLUMNS,
    )
    cost = pd.DataFrame(
        resolved_cost_rows,
        columns=standardizer.COST_REQUIRED_COLUMNS,
    )
    run_report = pd.DataFrame(
        resolved_run_rows,
        columns=standardizer.RUN_REPORT_REQUIRED_COLUMNS,
    )
    manifest = pd.DataFrame(
        resolved_manifest_rows,
        columns=standardizer.MANIFEST_REQUIRED_COLUMNS,
    )
    return descriptor, cost, run_report, manifest


class Stage2AWorkflowTests(unittest.TestCase):
    def test_clean_run_enriches_metadata_and_continuation_rows(self) -> None:
        # Arrange explicit parents followed by one unmerged continuation row.
        descriptor_rows = [
            _descriptor_row(
                source_row=12,
                activity="Other maintenance activity",
                category="Metering",
            ),
            _descriptor_row(
                source_row=13,
                activity=None,
                category="Communications",
            ),
        ]
        cost_rows = [
            _cost_row(
                source_row=50,
                activity="Other maintenance activity",
                subcategory="Metering",
            ),
            _cost_row(
                source_row=51,
                activity=None,
                subcategory="Communications",
            ),
        ]
        inputs = _input_frames(
            descriptor_rows=descriptor_rows,
            cost_rows=cost_rows,
        )
        descriptor_before = inputs[0].copy(deep=True)
        cost_before = inputs[1].copy(deep=True)

        # Execute one complete in-memory enrichment.
        result = standardizer.enrich_rin_maintenance(*inputs)

        # Assert metadata, parent resolution, source preservation, and completion.
        self.assertTrue(result.extraction_complete)
        self.assertTrue(result.stage2a_complete)
        self.assertTrue(result.issues.empty)
        self.assertEqual(
            list(result.issues.columns),
            list(standardizer.ISSUE_COLUMNS),
        )
        self.assertEqual(
            result.descriptor_metrics.columns.tolist(),
            list(standardizer.DESCRIPTOR_REQUIRED_COLUMNS)
            + list(standardizer.ENRICHMENT_COLUMNS),
        )
        self.assertEqual(
            result.cost_metrics.columns.tolist(),
            list(standardizer.COST_REQUIRED_COLUMNS)
            + list(standardizer.ENRICHMENT_COLUMNS),
        )
        self.assertEqual(
            result.workbook_mapping.loc[0, "metadata_match_status"],
            "validated_manifest_match",
        )
        self.assertEqual(
            result.descriptor_metrics.loc[1, "business"],
            "Powerlink",
        )
        self.assertTrue(
            pd.isna(
                result.descriptor_metrics.loc[1, "maintenance_activity"]
            )
        )
        self.assertEqual(
            result.descriptor_metrics.loc[
                1, "maintenance_activity_resolved"
            ],
            "Other maintenance activity",
        )
        self.assertEqual(
            result.descriptor_metrics.loc[
                1, "activity_resolution_status"
            ],
            "continued_group_label",
        )
        self.assertEqual(
            result.descriptor_metrics.loc[
                1, "activity_anchor_source_row"
            ],
            12,
        )
        assert_frame_equal(inputs[0], descriptor_before)
        assert_frame_equal(inputs[1], cost_before)

    def test_all_scoped_filename_aliases_match_manifest_businesses(self) -> None:
        # Arrange one successful workbook for each scoped filename alias.
        cases = [
            ("tRaNsGrId 2021-22 sample.xlsx", "Transgrid"),
            ("AusNet (T) 2021-22 sample.xlsx", "AusNet Transmission"),
            ("Powerlink 2021-22 sample.xlsx", "Powerlink"),
            ("ElectraNet 2021-22 sample.xlsx", "ElectraNet"),
        ]
        descriptor_rows = [
            _descriptor_row(workbook=workbook) for workbook, _ in cases
        ]
        cost_rows = [
            _cost_row(workbook=workbook) for workbook, _ in cases
        ]
        run_rows = [
            _run_record(workbook=workbook) for workbook, _ in cases
        ]
        manifest_rows = [
            _manifest_record(
                business=business,
                landing_page_url=(
                    f"https://www.aer.gov.au/documents/{business}"
                ),
                source_page_url=(
                    f"https://www.aer.gov.au/authors/{business}"
                ),
            )
            for _, business in cases
        ]
        inputs = _input_frames(
            descriptor_rows=descriptor_rows,
            cost_rows=cost_rows,
            run_rows=run_rows,
            manifest_rows=manifest_rows,
        )

        # Execute reconciliation across all project-scope businesses.
        result = standardizer.enrich_rin_maintenance(*inputs)

        # Assert each candidate is validated against its unique manifest record.
        self.assertTrue(result.stage2a_complete)
        self.assertEqual(
            result.workbook_mapping["business"].tolist(),
            [business for _, business in cases],
        )
        self.assertTrue(
            result.workbook_mapping["metadata_match_status"]
            .eq("validated_manifest_match")
            .all()
        )

    def test_group_header_and_empty_template_rows_are_distinguished(
        self,
    ) -> None:
        # Arrange one activity-only anchor, two continuations, and one unused row.
        cost_rows = [
            _cost_row(
                source_row=59,
                activity="Other maintenance activity",
                subcategory=None,
                routine=None,
                non_routine=None,
            ),
            _cost_row(
                source_row=60,
                activity=None,
                subcategory="Communications",
            ),
            _cost_row(
                source_row=61,
                activity=None,
                subcategory="Bushfire Remediation",
            ),
            _cost_row(
                source_row=62,
                activity="Other maintenance activity",
                subcategory=None,
                routine=None,
                non_routine=None,
            ),
        ]
        inputs = _input_frames(cost_rows=cost_rows)

        # Execute post-resolution row classification.
        result = standardizer.enrich_rin_maintenance(*inputs)
        enriched = result.cost_metrics

        # Assert the structural anchor and unused template row remain distinct.
        self.assertEqual(
            enriched["row_classification"].tolist(),
            [
                "group_header_only",
                "meaningful",
                "meaningful",
                "empty_template_row",
            ],
        )
        self.assertEqual(
            enriched.loc[1:2, "activity_anchor_source_row"].tolist(),
            [59, 59],
        )
        self.assertEqual(
            enriched.loc[
                1:2, "maintenance_activity_resolved"
            ].tolist(),
            ["Other maintenance activity", "Other maintenance activity"],
        )

    def test_source_row_gap_is_unresolved_and_clears_stale_parent(
        self,
    ) -> None:
        # Arrange a parent followed by two blank activities after a row gap.
        cost_rows = [
            _cost_row(
                source_row=59,
                activity="Other maintenance activity",
                subcategory="Metering",
            ),
            _cost_row(
                source_row=61,
                activity=None,
                subcategory="Communications",
            ),
            _cost_row(
                source_row=62,
                activity=None,
                subcategory="Bushfire Remediation",
            ),
        ]
        inputs = _input_frames(cost_rows=cost_rows)

        # Execute bounded parent resolution.
        result = standardizer.enrich_rin_maintenance(*inputs)

        # Assert the gap and subsequent stale-context row remain unresolved.
        self.assertFalse(result.stage2a_complete)
        self.assertEqual(
            result.cost_metrics["row_classification"].tolist(),
            ["meaningful", "unresolved", "unresolved"],
        )
        self.assertEqual(
            result.issues["issue_code"].tolist(),
            [
                "unresolved_parent_row_gap",
                "unresolved_parent_no_anchor",
            ],
        )
        self.assertTrue(
            result.cost_metrics.loc[
                1:2, "maintenance_activity_resolved"
            ].isna().all()
        )

    def test_resolution_resets_at_sheet_and_table_boundaries(self) -> None:
        # Arrange a descriptor parent and a cost parent on only the first sheet.
        descriptor_rows = [
            _descriptor_row(
                source_sheet="Sheet A",
                source_row=12,
                activity="Other maintenance activity",
            )
        ]
        cost_rows = [
            _cost_row(
                source_sheet="Sheet A",
                source_row=50,
                activity="Other maintenance activity",
            ),
            _cost_row(
                source_sheet="Sheet B",
                source_row=51,
                activity=None,
                subcategory="Communications",
            ),
        ]
        inputs = _input_frames(
            descriptor_rows=descriptor_rows,
            cost_rows=cost_rows,
        )

        # Execute independent descriptor and cost grouping.
        result = standardizer.enrich_rin_maintenance(*inputs)

        # Assert neither the other sheet nor descriptor table supplies a parent.
        self.assertEqual(
            result.cost_metrics.loc[1, "row_classification"],
            "unresolved",
        )
        self.assertTrue(
            pd.isna(
                result.cost_metrics.loc[
                    1, "maintenance_activity_resolved"
                ]
            )
        )
        self.assertEqual(
            result.issues.loc[0, "issue_code"],
            "unresolved_parent_no_anchor",
        )

    def test_child_category_with_blank_metrics_remains_meaningful(self) -> None:
        # Arrange submitted categories whose numeric metric cells are all blank.
        descriptor_row = _descriptor_row(asset_quantity=None)
        for column in standardizer.DESCRIPTOR_METRIC_COLUMNS:
            descriptor_row[column] = None
        cost_row = _cost_row(routine=None, non_routine=None)
        inputs = _input_frames(
            descriptor_rows=[descriptor_row],
            cost_rows=[cost_row],
        )

        # Execute row classification without numeric coercion.
        result = standardizer.enrich_rin_maintenance(*inputs)

        # Assert category identity alone keeps both rows meaningful.
        self.assertEqual(
            result.descriptor_metrics.loc[0, "row_classification"],
            "meaningful",
        )
        self.assertEqual(
            result.cost_metrics.loc[0, "row_classification"],
            "meaningful",
        )
        self.assertTrue(result.stage2a_complete)

    def test_alias_problems_are_returned_as_local_issues(self) -> None:
        # Arrange unmatched and ambiguous filenames as separate valid runs.
        cases = [
            (
                "Unknown Network 2021-22.xlsx",
                "unmatched_business_alias",
            ),
            (
                "NotPowerlink 2021-22.xlsx",
                "unmatched_business_alias",
            ),
            (
                "Powerlink ElectraNet 2021-22.xlsx",
                "ambiguous_business_alias",
            ),
        ]

        # Execute each local reconciliation failure without raising globally.
        for workbook, expected_status in cases:
            with self.subTest(expected_status=expected_status):
                inputs = _input_frames(
                    descriptor_rows=[_descriptor_row(workbook=workbook)],
                    cost_rows=[_cost_row(workbook=workbook)],
                    run_rows=[_run_record(workbook=workbook)],
                )
                result = standardizer.enrich_rin_maintenance(*inputs)

                # Assert partial outputs remain available and explicitly incomplete.
                self.assertFalse(result.stage2a_complete)
                self.assertEqual(
                    result.workbook_mapping.loc[
                        0, "metadata_match_status"
                    ],
                    expected_status,
                )
                self.assertEqual(
                    result.issues.loc[0, "issue_code"],
                    expected_status,
                )
                self.assertTrue(
                    result.descriptor_metrics["business"].isna().all()
                )

    def test_manifest_match_problems_are_returned_as_local_issues(
        self,
    ) -> None:
        # Arrange zero-match, multiple-match, and missing-URL manifest scenarios.
        cases = [
            (
                [_manifest_record(business="ElectraNet")],
                "manifest_no_match",
            ),
            (
                [_manifest_record(), _manifest_record()],
                "manifest_multiple_matches",
            ),
            (
                [_manifest_record(landing_page_url=None)],
                "manifest_metadata_missing",
            ),
        ]

        # Execute each manifest defect without suppressing canonical rows.
        for manifest_rows, expected_status in cases:
            with self.subTest(expected_status=expected_status):
                inputs = _input_frames(manifest_rows=manifest_rows)
                result = standardizer.enrich_rin_maintenance(*inputs)

                # Assert the mapping and issue use the same factual status.
                self.assertFalse(result.stage2a_complete)
                self.assertEqual(
                    result.workbook_mapping.loc[
                        0, "metadata_match_status"
                    ],
                    expected_status,
                )
                self.assertEqual(
                    result.issues.loc[0, "issue_code"],
                    expected_status,
                )
                if expected_status == "manifest_metadata_missing":
                    self.assertTrue(
                        result.descriptor_metrics["business"].isna().all()
                    )
                    self.assertTrue(
                        result.descriptor_metrics[
                            "landing_page_url"
                        ].isna().all()
                    )

    def test_reporting_period_conflict_is_reported(self) -> None:
        # Arrange descriptor and cost rows that disagree on reporting period.
        inputs = _input_frames(
            descriptor_rows=[_descriptor_row(period="2021-22")],
            cost_rows=[_cost_row(period="2022-23")],
        )

        # Execute metadata reconciliation with conflicting period evidence.
        result = standardizer.enrich_rin_maintenance(*inputs)

        # Assert period ambiguity prevents authoritative business enrichment.
        self.assertFalse(result.stage2a_complete)
        self.assertEqual(
            result.workbook_mapping.loc[0, "metadata_match_status"],
            "reporting_period_conflict",
        )
        self.assertEqual(
            result.issues.loc[0, "issue_code"],
            "reporting_period_conflict",
        )

    def test_parent_resolution_never_crosses_workbook_boundaries(
        self,
    ) -> None:
        # Arrange the same child label under two workbooks, with no second parent.
        second_workbook = "ElectraNet 2021-22 sample.xlsx"
        descriptor_rows = [
            _descriptor_row(),
            _descriptor_row(
                workbook=second_workbook,
                activity="Transmission lines maintenance",
            ),
        ]
        cost_rows = [
            _cost_row(
                activity="Other maintenance activity",
                subcategory="Communications",
            ),
            _cost_row(
                workbook=second_workbook,
                source_row=51,
                activity=None,
                subcategory="Communications",
            ),
        ]
        run_rows = [
            _run_record(),
            _run_record(workbook=second_workbook),
        ]
        manifest_rows = [
            _manifest_record(),
            _manifest_record(
                business="ElectraNet",
                landing_page_url=(
                    "https://www.aer.gov.au/documents/electranet"
                ),
                source_page_url=(
                    "https://www.aer.gov.au/authors/electranet"
                ),
            ),
        ]
        inputs = _input_frames(
            descriptor_rows=descriptor_rows,
            cost_rows=cost_rows,
            run_rows=run_rows,
            manifest_rows=manifest_rows,
        )

        # Execute grouping where the child text alone could invite a false fill.
        result = standardizer.enrich_rin_maintenance(*inputs)

        # Assert the second workbook cannot inherit the first workbook's parent.
        self.assertEqual(
            result.cost_metrics.loc[1, "row_classification"],
            "unresolved",
        )
        self.assertTrue(
            pd.isna(
                result.cost_metrics.loc[
                    1, "maintenance_activity_resolved"
                ]
            )
        )
        self.assertEqual(
            result.issues.loc[0, "issue_code"],
            "unresolved_parent_no_anchor",
        )

    def test_partial_extraction_can_have_complete_stage2a_enrichment(
        self,
    ) -> None:
        # Arrange one successful canonical workbook and one failed attempt.
        failed_workbook = "ElectraNet failed workbook.xlsx"
        run_rows = [
            _run_record(run_complete=False),
            _run_record(
                workbook=failed_workbook,
                period="",
                status="failed",
                run_complete=False,
            ),
        ]
        inputs = _input_frames(run_rows=run_rows)

        # Execute enrichment over the successful Stage 1 subset.
        result = standardizer.enrich_rin_maintenance(*inputs)

        # Assert extraction and enrichment completeness remain independent.
        self.assertFalse(result.extraction_complete)
        self.assertTrue(result.stage2a_complete)
        self.assertEqual(len(result.workbook_mapping), 2)
        self.assertEqual(
            result.workbook_mapping.loc[1, "metadata_match_status"],
            "extraction_failed",
        )

    def test_input_order_index_and_source_dtypes_are_preserved(self) -> None:
        # Arrange unsorted source rows with non-default indexes and mixed values.
        descriptor_rows = [
            _descriptor_row(source_row=13, activity=None),
            _descriptor_row(
                source_row=12,
                activity="Other maintenance activity",
            ),
        ]
        cost_rows = [
            _cost_row(source_row=51, activity=None),
            _cost_row(
                source_row=50,
                activity="Other maintenance activity",
            ),
        ]
        inputs = list(
            _input_frames(
                descriptor_rows=descriptor_rows,
                cost_rows=cost_rows,
            )
        )
        inputs[0].index = [8, 3]
        inputs[1].index = [7, 2]
        descriptor_before = inputs[0].copy(deep=True)
        cost_before = inputs[1].copy(deep=True)

        # Execute source-row sorting internally while retaining caller layout.
        result = standardizer.enrich_rin_maintenance(*inputs)

        # Assert output order/index and every canonical source field are unchanged.
        self.assertEqual(result.descriptor_metrics.index.tolist(), [8, 3])
        self.assertEqual(result.cost_metrics.index.tolist(), [7, 2])
        assert_frame_equal(
            result.descriptor_metrics[
                list(standardizer.DESCRIPTOR_REQUIRED_COLUMNS)
            ],
            descriptor_before,
        )
        assert_frame_equal(
            result.cost_metrics[
                list(standardizer.COST_REQUIRED_COLUMNS)
            ],
            cost_before,
        )
        assert_frame_equal(inputs[0], descriptor_before)
        assert_frame_equal(inputs[1], cost_before)


class Stage2AInputValidationTests(unittest.TestCase):
    def test_invalid_argument_schema_and_derived_collision_raise(self) -> None:
        # Arrange valid base inputs for three independent contract mutations.
        inputs = list(_input_frames())

        # Execute and assert rejection of a non-DataFrame public argument.
        with self.assertRaisesRegex(
            standardizer.MaintenanceStandardizationError,
            "must be a pandas DataFrame",
        ):
            standardizer.enrich_rin_maintenance(
                "not a dataframe",
                inputs[1],
                inputs[2],
                inputs[3],
            )

        # Execute and assert rejection of a missing canonical source column.
        missing_column = inputs[0].drop(columns=["source_sheet"])
        with self.assertRaisesRegex(
            standardizer.MaintenanceStandardizationError,
            "missing required column",
        ):
            standardizer.enrich_rin_maintenance(
                missing_column,
                inputs[1],
                inputs[2],
                inputs[3],
            )

        # Execute and assert rejection before replacing an existing derived field.
        collision = inputs[0].copy()
        collision["business"] = "Powerlink"
        with self.assertRaisesRegex(
            standardizer.MaintenanceStandardizationError,
            "already contains Stage 2A",
        ):
            standardizer.enrich_rin_maintenance(
                collision,
                inputs[1],
                inputs[2],
                inputs[3],
            )

        # Execute and assert rejection of duplicate scalar column labels.
        duplicate_columns = pd.concat(
            [
                inputs[0],
                inputs[0][["source_workbook"]].rename(
                    columns={"source_workbook": "reporting_period"}
                ),
            ],
            axis=1,
        )
        with self.assertRaisesRegex(
            standardizer.MaintenanceStandardizationError,
            "duplicate column label",
        ):
            standardizer.enrich_rin_maintenance(
                duplicate_columns,
                inputs[1],
                inputs[2],
                inputs[3],
            )

    def test_invalid_and_duplicate_source_lineage_raise(self) -> None:
        # Arrange one non-integral source row and one duplicate source coordinate.
        invalid_inputs = list(_input_frames())
        invalid_inputs[0]["source_row"] = invalid_inputs[0][
            "source_row"
        ].astype(float)
        invalid_inputs[0].loc[0, "source_row"] = 12.5
        duplicate_descriptor = pd.DataFrame(
            [_descriptor_row(), _descriptor_row()],
            columns=standardizer.DESCRIPTOR_REQUIRED_COLUMNS,
        )
        duplicate_inputs = list(_input_frames())
        duplicate_inputs[0] = duplicate_descriptor

        # Execute and assert source-row numeric validation.
        with self.assertRaisesRegex(
            standardizer.MaintenanceStandardizationError,
            "positive whole numbers",
        ):
            standardizer.enrich_rin_maintenance(*invalid_inputs)

        # Execute and assert duplicate physical lineage rejection.
        with self.assertRaisesRegex(
            standardizer.MaintenanceStandardizationError,
            "duplicate workbook, sheet, and source-row lineage",
        ):
            standardizer.enrich_rin_maintenance(*duplicate_inputs)

        # Execute and assert boolean and out-of-range physical rows are rejected.
        for invalid_row in (True, 2**63):
            with self.subTest(invalid_row=invalid_row):
                bounded_inputs = list(_input_frames())
                bounded_inputs[0]["source_row"] = bounded_inputs[0][
                    "source_row"
                ].astype(object)
                bounded_inputs[0].loc[0, "source_row"] = invalid_row
                with self.assertRaisesRegex(
                    standardizer.MaintenanceStandardizationError,
                    "positive whole numbers",
                ):
                    standardizer.enrich_rin_maintenance(*bounded_inputs)

    def test_inconsistent_run_report_contract_raises(self) -> None:
        # Arrange conflicting completion and duplicate workbook report records.
        conflicting_inputs = list(_input_frames())
        conflicting_inputs[2].loc[0, "run_complete"] = False
        duplicate_inputs = list(_input_frames())
        duplicate_inputs[2] = pd.concat(
            [duplicate_inputs[2], duplicate_inputs[2]],
            ignore_index=True,
        )

        # Execute and assert run-level completion/status consistency.
        with self.assertRaisesRegex(
            standardizer.MaintenanceStandardizationError,
            "conflicts with workbook statuses",
        ):
            standardizer.enrich_rin_maintenance(*conflicting_inputs)

        # Execute and assert one report record per attempted workbook.
        with self.assertRaisesRegex(
            standardizer.MaintenanceStandardizationError,
            "duplicate source_workbook",
        ):
            standardizer.enrich_rin_maintenance(*duplicate_inputs)

        # Execute and assert invalid status, completion text, and emptiness fail.
        invalid_cases = [
            ("status", "pending", "unsupported value"),
            ("run_complete", "", "only true or false"),
        ]
        for column, value, expected_message in invalid_cases:
            with self.subTest(column=column):
                invalid_report_inputs = list(_input_frames())
                invalid_report_inputs[2][column] = invalid_report_inputs[2][
                    column
                ].astype(object)
                invalid_report_inputs[2].loc[0, column] = value
                with self.assertRaisesRegex(
                    standardizer.MaintenanceStandardizationError,
                    expected_message,
                ):
                    standardizer.enrich_rin_maintenance(
                        *invalid_report_inputs
                    )

        # Execute and assert a report with no attempted workbooks is invalid.
        empty_report_inputs = list(_input_frames())
        empty_report_inputs[2] = empty_report_inputs[2].iloc[0:0]
        with self.assertRaisesRegex(
            standardizer.MaintenanceStandardizationError,
            "at least one attempted workbook",
        ):
            standardizer.enrich_rin_maintenance(*empty_report_inputs)

    def test_canonical_and_run_report_inventory_mismatch_raises(self) -> None:
        # Arrange a successful report whose workbook differs from canonical data.
        inputs = list(_input_frames())
        inputs[2] = pd.DataFrame(
            [_run_record(workbook="ElectraNet 2021-22 sample.xlsx")],
            columns=standardizer.RUN_REPORT_REQUIRED_COLUMNS,
        )

        # Execute the orchestrator against artifacts from inconsistent runs.
        with self.assertRaisesRegex(
            standardizer.MaintenanceStandardizationError,
            "do not match successful run-report records",
        ):
            standardizer.enrich_rin_maintenance(*inputs)

        # Assert the input artifacts remain untouched after validation failure.
        self.assertEqual(
            inputs[0].loc[0, "source_workbook"],
            POWERLINK_WORKBOOK,
        )

        # Execute and assert descriptor/cost workbook disagreement also fails.
        table_mismatch_inputs = list(_input_frames())
        table_mismatch_inputs[1].loc[
            0, "source_workbook"
        ] = "ElectraNet 2021-22 sample.xlsx"
        with self.assertRaisesRegex(
            standardizer.MaintenanceStandardizationError,
            "different source workbooks",
        ):
            standardizer.enrich_rin_maintenance(*table_mismatch_inputs)

        # Execute and assert Stage 2A is not invoked without canonical successes.
        all_failed_inputs = list(_input_frames())
        all_failed_inputs[0] = all_failed_inputs[0].iloc[0:0]
        all_failed_inputs[1] = all_failed_inputs[1].iloc[0:0]
        all_failed_inputs[2].loc[0, "status"] = "failed"
        all_failed_inputs[2].loc[0, "reporting_period"] = ""
        all_failed_inputs[2].loc[0, "run_complete"] = False
        with self.assertRaisesRegex(
            standardizer.MaintenanceStandardizationError,
            "must both contain rows",
        ):
            standardizer.enrich_rin_maintenance(*all_failed_inputs)


if __name__ == "__main__":
    # Run the isolated unittest module when invoked directly.
    unittest.main()
