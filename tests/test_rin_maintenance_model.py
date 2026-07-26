import unittest

import pandas as pd

from src.rin_maintenance_model import (
    ISSUE_REQUIRED_COLUMNS,
    MaintenanceModelError,
    build_rin_maintenance_model,
)


def _descriptor_row(
    *,
    workbook: str,
    business: str,
    period: str,
    source_row: int,
    activity_id: object = "lines",
    activity_label: object = "Transmission lines maintenance",
    asset_id: object = "towers",
    asset_label: object = "Transmission towers",
    classification: str = "meaningful",
    analytic: bool = True,
) -> dict[str, object]:
    """Build one fabricated standardized descriptor row."""
    # Populate identity, lineage, and Stage 2 eligibility fields.
    row: dict[str, object] = {
        "reporting_period": period,
        "maintenance_activity": activity_label,
        "maintenance_asset_category": asset_label,
        "source_workbook": workbook,
        "source_sheet": "2.8 Maintenance",
        "source_row": source_row,
        "business": business,
        "row_classification": classification,
        "analytic_row_eligible": analytic,
        "maintenance_activity_standard_id": activity_id,
        "maintenance_activity_standard": activity_label,
        "maintenance_asset_standard_id": asset_id,
        "maintenance_asset_standard": asset_label,
        "quantity_unit_standard": "count",
    }

    # Populate the five source, standardized, and status metric groups.
    for source_column, standard_column, status_column, value in (
        (
            "asset_quantity_at_year_end",
            "asset_quantity_at_year_end_standard",
            "asset_quantity_at_year_end_status",
            10.0,
        ),
        (
            "quantity_inspected_maintained",
            "quantity_inspected_maintained_standard",
            "quantity_inspected_maintained_status",
            4.0,
        ),
        (
            "average_age_of_asset_group",
            "average_age_of_asset_group_standard",
            "average_age_of_asset_group_status",
            20.0,
        ),
        (
            "inspection_cycle_years",
            "inspection_cycle_years_standard",
            "inspection_cycle_years_status",
            2.0,
        ),
        (
            "maintenance_cycle_years",
            "maintenance_cycle_years_standard",
            "maintenance_cycle_years_status",
            5.0,
        ),
    ):
        row[source_column] = value
        row[standard_column] = value
        row[status_column] = "numeric"
    return row


def _cost_row(
    *,
    workbook: str,
    business: str,
    period: str,
    source_row: int,
    activity_id: str,
    asset_id: str,
) -> dict[str, object]:
    """Build one fabricated standardized cost row."""
    # Populate only the identity and eligibility contract used for coverage.
    return {
        "reporting_period": period,
        "source_workbook": workbook,
        "source_sheet": "2.8 Maintenance",
        "source_row": source_row,
        "business": business,
        "row_classification": "meaningful",
        "analytic_row_eligible": True,
        "maintenance_activity_standard_id": activity_id,
        "maintenance_asset_standard_id": asset_id,
    }


def _relationship_row(
    *,
    workbook: str,
    business: str,
    period: str,
    source_row: int,
    activity_id: str,
    activity_label: str,
    asset_id: str,
    asset_label: str,
    relationship_status: str = "matched_with_denominator",
) -> dict[str, object]:
    """Build one fabricated cost-descriptor relationship row."""
    # Populate the shared standardized cost and category fields.
    row: dict[str, object] = {
        "reporting_period": period,
        "source_workbook": workbook,
        "source_sheet": "2.8 Maintenance",
        "source_row": source_row,
        "business": business,
        "row_classification": "meaningful",
        "analytic_row_eligible": True,
        "maintenance_activity_standard_id": activity_id,
        "maintenance_activity_standard": activity_label,
        "maintenance_asset_standard_id": asset_id,
        "maintenance_asset_standard": asset_label,
        "currency_standard": "AUD",
        "price_basis": "nominal",
        "routine_maintenance_expenditure_standard": 100.0,
        "routine_maintenance_expenditure_status": "numeric",
        "non_routine_maintenance_expenditure_standard": 25.0,
        "non_routine_maintenance_expenditure_status": "numeric",
        "total_maintenance_expenditure_standard": 125.0,
        "total_maintenance_expenditure_status": "numeric",
        "relationship_status": relationship_status,
    }

    # Populate descriptor lineage and denominator evidence by match status.
    matched = relationship_status == "matched_with_denominator"
    row.update(
        {
            "descriptor_source_workbook": workbook if matched else pd.NA,
            "descriptor_source_sheet": (
                "2.8 Maintenance" if matched else pd.NA
            ),
            "descriptor_source_row": source_row if matched else pd.NA,
            "denominator_unit_standard": "count" if matched else pd.NA,
            "installed_quantity_standard": 10.0 if matched else pd.NA,
            "installed_quantity_status": (
                "numeric" if matched else "no_descriptor_match"
            ),
            "serviced_quantity_standard": 4.0 if matched else pd.NA,
            "serviced_quantity_status": (
                "numeric" if matched else "no_descriptor_match"
            ),
            "installed_ratio_status": (
                "calculated" if matched else "no_descriptor_match"
            ),
            "serviced_ratio_status": (
                "calculated" if matched else "no_descriptor_match"
            ),
        }
    )

    # Include Stage 2 row ratios to confirm Stage 3 deliberately omits them.
    row["routine_expenditure_per_installed_unit"] = (
        10.0 if matched else pd.NA
    )
    row["total_expenditure_per_serviced_unit"] = (
        31.25 if matched else pd.NA
    )
    return row


def _mapping_row(
    *,
    workbook: str,
    business: str,
    period: str,
) -> dict[str, object]:
    """Build one fabricated validated workbook mapping."""
    # Preserve the authoritative business-period and AER lineage fields.
    return {
        "source_workbook": workbook,
        "extraction_status": "success",
        "extracted_reporting_period": period,
        "manifest_local_filename": workbook,
        "business": business,
        "landing_page_url": f"https://example.test/{workbook}",
        "source_page_url": "https://example.test/search",
        "metadata_match_status": "validated_manifest_match",
    }


def _stage2_inputs(
    *,
    include_exception: bool = True,
) -> tuple[
    pd.DataFrame,
    pd.DataFrame,
    pd.DataFrame,
    pd.DataFrame,
    pd.DataFrame,
    dict[str, object],
]:
    """Build a small multi-business Stage 2 artifact set."""
    # Arrange three workbooks with one shared and two source-specific categories.
    descriptor_rows = [
        _descriptor_row(
            workbook="grid-a-2019.xlsx",
            business="Grid A",
            period="2019-20",
            source_row=10,
        ),
        _descriptor_row(
            workbook="grid-a-2020.xlsx",
            business="Grid A",
            period="2020-21",
            source_row=10,
            activity_id="other",
            activity_label="Other maintenance activity",
            asset_id="corridor",
            asset_label="Corridor maintenance",
        ),
        _descriptor_row(
            workbook="grid-b-2019.xlsx",
            business="Grid B",
            period="2019-20",
            source_row=10,
        ),
        _descriptor_row(
            workbook="grid-b-2019.xlsx",
            business="Grid B",
            period="2019-20",
            source_row=99,
            activity_id=pd.NA,
            activity_label=pd.NA,
            asset_id=pd.NA,
            asset_label=pd.NA,
            classification="empty_template_row",
            analytic=False,
        ),
    ]

    # Add one meaningful unresolved row to exercise disclosure policy.
    if include_exception:
        unresolved = _descriptor_row(
            workbook="grid-b-2019.xlsx",
            business="Grid B",
            period="2019-20",
            source_row=21,
            activity_id=pd.NA,
            activity_label="Other maintenance activity",
            asset_id=pd.NA,
            asset_label=pd.NA,
        )
        unresolved["quantity_unit_standard"] = pd.NA
        unresolved["quantity_inspected_maintained"] = 0.0
        unresolved["quantity_inspected_maintained_standard"] = pd.NA
        unresolved["quantity_inspected_maintained_status"] = "blank"
        descriptor_rows.append(unresolved)

    # Arrange cost rows with shared and cost-only contextual categories.
    cost_rows = [
        _cost_row(
            workbook="grid-a-2019.xlsx",
            business="Grid A",
            period="2019-20",
            source_row=50,
            activity_id="lines",
            asset_id="towers",
        ),
        _cost_row(
            workbook="grid-a-2020.xlsx",
            business="Grid A",
            period="2020-21",
            source_row=50,
            activity_id="other",
            asset_id="access_tracks",
        ),
        _cost_row(
            workbook="grid-b-2019.xlsx",
            business="Grid B",
            period="2019-20",
            source_row=50,
            activity_id="lines",
            asset_id="towers",
        ),
    ]
    relationships = [
        _relationship_row(
            workbook="grid-a-2019.xlsx",
            business="Grid A",
            period="2019-20",
            source_row=50,
            activity_id="lines",
            activity_label="Transmission lines maintenance",
            asset_id="towers",
            asset_label="Transmission towers",
        ),
        _relationship_row(
            workbook="grid-a-2020.xlsx",
            business="Grid A",
            period="2020-21",
            source_row=50,
            activity_id="other",
            activity_label="Other maintenance activity",
            asset_id="access_tracks",
            asset_label="Transmission line access tracks",
            relationship_status="no_descriptor_match",
        ),
        _relationship_row(
            workbook="grid-b-2019.xlsx",
            business="Grid B",
            period="2019-20",
            source_row=50,
            activity_id="lines",
            activity_label="Transmission lines maintenance",
            asset_id="towers",
            asset_label="Transmission towers",
        ),
    ]

    # Arrange authoritative mappings for an unbalanced historical panel.
    mappings = [
        _mapping_row(
            workbook="grid-a-2019.xlsx",
            business="Grid A",
            period="2019-20",
        ),
        _mapping_row(
            workbook="grid-a-2020.xlsx",
            business="Grid A",
            period="2020-21",
        ),
        _mapping_row(
            workbook="grid-b-2019.xlsx",
            business="Grid B",
            period="2019-20",
        ),
    ]

    # Preserve two upstream issue codes for the one unresolved source row.
    issue_rows: list[dict[str, object]] = []
    if include_exception:
        for issue_code in (
            "unresolved_category_hierarchy",
            "missing_unit",
        ):
            issue_rows.append(
                {
                    "stage": "2B",
                    "severity": "error",
                    "table_name": "descriptor_metrics",
                    "source_workbook": "grid-b-2019.xlsx",
                    "source_row": 21,
                    "issue_code": issue_code,
                    "message": "Known fabricated descriptor exception.",
                }
            )

    # Align Stage 2 completeness with the presence of the known exception.
    complete = not include_exception
    summary = {
        "extraction_complete": True,
        "stage2a_complete": True,
        "stage2b_complete": complete,
        "panel_complete": True,
        "pipeline_complete": complete,
    }
    return (
        pd.DataFrame(descriptor_rows),
        pd.DataFrame(cost_rows),
        pd.DataFrame(mappings),
        pd.DataFrame(relationships),
        pd.DataFrame(issue_rows, columns=ISSUE_REQUIRED_COLUMNS),
        summary,
    )


class MaintenanceModelConstructionTests(unittest.TestCase):
    def test_builds_star_model_and_preserves_disclosed_exception(self) -> None:
        # Arrange a Stage 2 result with source-specific categories and one issue.
        inputs = _stage2_inputs(include_exception=True)

        # Execute the in-memory Stage 3 model construction.
        result = build_rin_maintenance_model(*inputs)

        # Assert shared dimensions retain the complete source semantics.
        self.assertEqual(len(result.business_dimension), 2)
        self.assertEqual(len(result.reporting_period_dimension), 2)
        self.assertEqual(
            result.reporting_period_dimension.loc[
                result.reporting_period_dimension["is_common_panel"],
                "reporting_period",
            ].tolist(),
            ["2019-20"],
        )
        self.assertEqual(
            set(
                result.maintenance_category_dimension[
                    "maintenance_category_key"
                ]
            ),
            {
                "lines::towers",
                "other::corridor",
                "other::access_tracks",
            },
        )

        # Assert descriptor rows expand to five metrics and preserve statuses.
        self.assertEqual(len(result.descriptor_fact), 15)
        self.assertEqual(
            set(result.descriptor_fact["metric_id"]),
            {
                "asset_quantity_at_year_end",
                "quantity_inspected_maintained",
                "average_age_of_asset_group",
                "inspection_cycle_years",
                "maintenance_cycle_years",
            },
        )
        descriptor_sample = result.descriptor_fact.query(
            "metric_id == 'asset_quantity_at_year_end'"
        ).iloc[0]
        self.assertEqual(descriptor_sample["source_value"], 10.0)
        self.assertEqual(descriptor_sample["metric_value"], 10.0)

        # Assert cost-only records remain and row-ratio columns are not published.
        self.assertEqual(len(result.cost_fact), 3)
        self.assertIn(
            "no_descriptor_match",
            set(result.cost_fact["relationship_status"]),
        )
        self.assertNotIn(
            "routine_expenditure_per_installed_unit",
            result.cost_fact.columns,
        )
        self.assertNotIn(
            "total_expenditure_per_serviced_unit",
            result.cost_fact.columns,
        )

        # Assert one source row remains disclosed without inventing a category.
        self.assertEqual(
            set(result.issues["model_action"]),
            {"excluded_from_analytic_fact"},
        )
        self.assertEqual(
            result.summary["row_counts"]["excluded_source_rows"],
            1,
        )
        self.assertFalse(result.summary["model_complete"])
        self.assertEqual(
            result.summary["publication_status"],
            "usable_with_disclosed_exceptions",
        )

    def test_complete_inputs_produce_complete_model(self) -> None:
        # Arrange a complete Stage 2 result without unresolved meaningful rows.
        inputs = _stage2_inputs(include_exception=False)

        # Execute model construction across the same balanced and historic data.
        result = build_rin_maintenance_model(*inputs)

        # Assert build and upstream completeness produce a complete publication.
        self.assertTrue(result.summary["model_build_complete"])
        self.assertTrue(result.summary["source_pipeline_complete"])
        self.assertTrue(result.summary["model_complete"])
        self.assertEqual(result.summary["publication_status"], "complete")
        self.assertEqual(
            result.summary["row_counts"]["excluded_source_rows"],
            0,
        )

    def test_duplicate_descriptor_grain_is_rejected(self) -> None:
        # Arrange complete inputs with one duplicate semantic descriptor row.
        inputs = list(_stage2_inputs(include_exception=False))
        descriptor = inputs[0]
        inputs[0] = pd.concat(
            [descriptor, descriptor.iloc[[0]]],
            ignore_index=True,
        )

        # Execute model construction and capture the declared-grain failure.
        with self.assertRaises(MaintenanceModelError) as error_context:
            build_rin_maintenance_model(*inputs)

        # Assert duplicates are never silently aggregated for Power BI.
        self.assertIn(
            "descriptor_fact has duplicate grain values",
            str(error_context.exception),
        )

    def test_cost_relationship_coverage_mismatch_is_rejected(self) -> None:
        # Arrange complete inputs with one relationship row removed.
        inputs = list(_stage2_inputs(include_exception=False))
        inputs[3] = inputs[3].iloc[:-1].copy()

        # Execute model construction and capture cost coverage validation.
        with self.assertRaises(MaintenanceModelError) as error_context:
            build_rin_maintenance_model(*inputs)

        # Assert missing cost relationships cannot disappear from the model.
        self.assertIn(
            "Cost relationship coverage differs",
            str(error_context.exception),
        )

    def test_unknown_source_workbook_is_rejected(self) -> None:
        # Arrange complete inputs whose descriptor fact lacks a workbook mapping.
        inputs = list(_stage2_inputs(include_exception=False))
        inputs[0].loc[0, "source_workbook"] = "unmapped.xlsx"

        # Execute model construction and capture foreign-key validation.
        with self.assertRaises(MaintenanceModelError) as error_context:
            build_rin_maintenance_model(*inputs)

        # Assert every fact row remains traceable to validated workbook metadata.
        self.assertIn(
            "descriptor_fact.source_workbook has unresolved keys",
            str(error_context.exception),
        )

    def test_contradictory_stage2_summary_is_rejected(self) -> None:
        # Arrange otherwise complete inputs with an inconsistent overall flag.
        inputs = list(_stage2_inputs(include_exception=False))
        inputs[5] = {**inputs[5], "pipeline_complete": False}

        # Execute model construction and capture summary validation.
        with self.assertRaises(MaintenanceModelError) as error_context:
            build_rin_maintenance_model(*inputs)

        # Assert Stage 3 cannot publish against contradictory completeness data.
        self.assertIn(
            "pipeline_complete conflicts",
            str(error_context.exception),
        )


if __name__ == "__main__":
    # Run this isolated unittest module when invoked directly.
    unittest.main()
