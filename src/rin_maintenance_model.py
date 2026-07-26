"""Stage 3 Power BI model construction for RIN maintenance data."""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass
from typing import Any

import pandas as pd


DESCRIPTOR_REQUIRED_COLUMNS = (
    "reporting_period",
    "maintenance_activity",
    "maintenance_asset_category",
    "source_workbook",
    "source_sheet",
    "source_row",
    "business",
    "row_classification",
    "analytic_row_eligible",
    "maintenance_activity_standard_id",
    "maintenance_activity_standard",
    "maintenance_asset_standard_id",
    "maintenance_asset_standard",
    "quantity_unit_standard",
    "asset_quantity_at_year_end",
    "asset_quantity_at_year_end_standard",
    "asset_quantity_at_year_end_status",
    "quantity_inspected_maintained",
    "quantity_inspected_maintained_standard",
    "quantity_inspected_maintained_status",
    "average_age_of_asset_group",
    "average_age_of_asset_group_standard",
    "average_age_of_asset_group_status",
    "inspection_cycle_years",
    "inspection_cycle_years_standard",
    "inspection_cycle_years_status",
    "maintenance_cycle_years",
    "maintenance_cycle_years_standard",
    "maintenance_cycle_years_status",
)
COST_REQUIRED_COLUMNS = (
    "reporting_period",
    "source_workbook",
    "source_sheet",
    "source_row",
    "business",
    "row_classification",
    "analytic_row_eligible",
    "maintenance_activity_standard_id",
    "maintenance_asset_standard_id",
)
WORKBOOK_MAPPING_REQUIRED_COLUMNS = (
    "source_workbook",
    "extraction_status",
    "extracted_reporting_period",
    "manifest_local_filename",
    "business",
    "landing_page_url",
    "source_page_url",
    "metadata_match_status",
)
RELATIONSHIP_REQUIRED_COLUMNS = (
    "reporting_period",
    "source_workbook",
    "source_sheet",
    "source_row",
    "business",
    "row_classification",
    "analytic_row_eligible",
    "maintenance_activity_standard_id",
    "maintenance_activity_standard",
    "maintenance_asset_standard_id",
    "maintenance_asset_standard",
    "currency_standard",
    "price_basis",
    "routine_maintenance_expenditure_standard",
    "routine_maintenance_expenditure_status",
    "non_routine_maintenance_expenditure_standard",
    "non_routine_maintenance_expenditure_status",
    "total_maintenance_expenditure_standard",
    "total_maintenance_expenditure_status",
    "relationship_status",
    "descriptor_source_workbook",
    "descriptor_source_sheet",
    "descriptor_source_row",
    "denominator_unit_standard",
    "installed_quantity_standard",
    "installed_quantity_status",
    "serviced_quantity_standard",
    "serviced_quantity_status",
    "installed_ratio_status",
    "serviced_ratio_status",
)
ISSUE_REQUIRED_COLUMNS = (
    "stage",
    "severity",
    "table_name",
    "source_workbook",
    "source_row",
    "issue_code",
    "message",
)
STAGE2_COMPLETENESS_KEYS = (
    "extraction_complete",
    "stage2a_complete",
    "stage2b_complete",
    "panel_complete",
    "pipeline_complete",
)

METRIC_DEFINITIONS = (
    {
        "metric_id": "asset_quantity_at_year_end",
        "metric_name": "Asset quantity at year end",
        "metric_group": "quantity",
        "source_column": "asset_quantity_at_year_end",
        "standard_column": "asset_quantity_at_year_end_standard",
        "status_column": "asset_quantity_at_year_end_status",
        "unit_column": "quantity_unit_standard",
    },
    {
        "metric_id": "quantity_inspected_maintained",
        "metric_name": "Quantity inspected or maintained",
        "metric_group": "quantity",
        "source_column": "quantity_inspected_maintained",
        "standard_column": "quantity_inspected_maintained_standard",
        "status_column": "quantity_inspected_maintained_status",
        "unit_column": "quantity_unit_standard",
    },
    {
        "metric_id": "average_age_of_asset_group",
        "metric_name": "Average age of asset group",
        "metric_group": "age",
        "source_column": "average_age_of_asset_group",
        "standard_column": "average_age_of_asset_group_standard",
        "status_column": "average_age_of_asset_group_status",
        "fixed_unit": "years",
    },
    {
        "metric_id": "inspection_cycle_years",
        "metric_name": "Inspection cycle",
        "metric_group": "cycle",
        "source_column": "inspection_cycle_years",
        "standard_column": "inspection_cycle_years_standard",
        "status_column": "inspection_cycle_years_status",
        "fixed_unit": "years",
    },
    {
        "metric_id": "maintenance_cycle_years",
        "metric_name": "Maintenance cycle",
        "metric_group": "cycle",
        "source_column": "maintenance_cycle_years",
        "standard_column": "maintenance_cycle_years_standard",
        "status_column": "maintenance_cycle_years_status",
        "fixed_unit": "years",
    },
)

BUSINESS_DIMENSION_COLUMNS = (
    "business_id",
    "business_name",
    "business_sort_order",
)
REPORTING_PERIOD_DIMENSION_COLUMNS = (
    "reporting_period",
    "period_start_year",
    "period_end_year",
    "period_sort_order",
    "is_common_panel",
)
CATEGORY_DIMENSION_COLUMNS = (
    "maintenance_category_key",
    "maintenance_activity_id",
    "maintenance_activity",
    "maintenance_asset_id",
    "maintenance_asset",
    "appears_in_descriptor",
    "appears_in_cost",
    "maintenance_category_sort_order",
)
METRIC_DIMENSION_COLUMNS = (
    "metric_id",
    "metric_name",
    "metric_group",
    "metric_sort_order",
)
SOURCE_WORKBOOK_DIMENSION_COLUMNS = (
    "source_workbook",
    "business_id",
    "reporting_period",
    "extraction_status",
    "metadata_match_status",
    "manifest_local_filename",
    "landing_page_url",
    "source_page_url",
)
DESCRIPTOR_FACT_COLUMNS = (
    "business_id",
    "reporting_period",
    "maintenance_category_key",
    "metric_id",
    "metric_value",
    "metric_unit",
    "metric_status",
    "source_value",
    "source_workbook",
    "source_sheet",
    "source_row",
)
COST_FACT_COLUMNS = (
    "business_id",
    "reporting_period",
    "maintenance_category_key",
    "routine_expenditure_aud",
    "routine_expenditure_status",
    "non_routine_expenditure_aud",
    "non_routine_expenditure_status",
    "total_expenditure_aud",
    "total_expenditure_status",
    "currency",
    "price_basis",
    "installed_quantity",
    "installed_quantity_status",
    "serviced_quantity",
    "serviced_quantity_status",
    "denominator_unit",
    "relationship_status",
    "installed_ratio_status",
    "serviced_ratio_status",
    "source_workbook",
    "source_sheet",
    "source_row",
    "descriptor_source_workbook",
    "descriptor_source_sheet",
    "descriptor_source_row",
)
MODEL_ISSUE_COLUMNS = (
    *ISSUE_REQUIRED_COLUMNS,
    "model_action",
)

__all__ = [
    "MaintenanceModelError",
    "MaintenanceModelResult",
    "build_rin_maintenance_model",
]


class MaintenanceModelError(RuntimeError):
    """Raised when Stage 3 inputs cannot produce a trustworthy model."""


@dataclass
class MaintenanceModelResult:
    """Power BI dimensions, facts, issues, and completion metadata."""

    business_dimension: pd.DataFrame
    reporting_period_dimension: pd.DataFrame
    maintenance_category_dimension: pd.DataFrame
    metric_dimension: pd.DataFrame
    source_workbook_dimension: pd.DataFrame
    descriptor_fact: pd.DataFrame
    cost_fact: pd.DataFrame
    issues: pd.DataFrame
    summary: dict[str, Any]


def _is_blank(value: object) -> bool:
    """Return whether a scalar source value is empty."""
    # Treat nulls and whitespace-only strings as missing model keys.
    if value is None or isinstance(value, str) and not value.strip():
        return True
    try:
        return bool(pd.isna(value))
    except (TypeError, ValueError):
        return False


def _display_text(value: object) -> str:
    """Return collapsed source text for stable labels and keys."""
    # Preserve submitted casing while removing presentation-only whitespace.
    if _is_blank(value):
        return ""
    return re.sub(r"\s+", " ", str(value)).strip()


def _source_identifier(value: object) -> str:
    """Create a deterministic identifier from a validated display label."""
    # Normalize Unicode and punctuation before collapsing words to underscores.
    normalized = unicodedata.normalize("NFKC", _display_text(value)).casefold()
    identifier = re.sub(r"[^a-z0-9]+", "_", normalized).strip("_")
    if not identifier:
        raise MaintenanceModelError("Cannot create an ID from a blank label")
    return identifier


def _require_dataframe(name: str, value: object) -> pd.DataFrame:
    """Validate one tabular Stage 2 input."""
    # Reject lookalike objects so column and row checks remain predictable.
    if not isinstance(value, pd.DataFrame):
        raise MaintenanceModelError(f"{name} must be a pandas DataFrame")
    if value.columns.has_duplicates:
        raise MaintenanceModelError(f"{name} contains duplicate columns")
    return value


def _require_columns(
    name: str,
    table: pd.DataFrame,
    required_columns: tuple[str, ...],
) -> None:
    """Require a stable set of columns in one Stage 2 input."""
    # Report all missing columns together to make contract failures actionable.
    missing = [column for column in required_columns if column not in table]
    if missing:
        raise MaintenanceModelError(
            f"{name} is missing required columns: {', '.join(missing)}"
        )


def _boolean_series(
    table: pd.DataFrame,
    column: str,
    table_name: str,
) -> pd.Series:
    """Parse a factual boolean column without treating arbitrary text as true."""
    # Normalize booleans and their ordinary CSV representations explicitly.
    parsed: list[bool] = []
    for value in table[column].tolist():
        if isinstance(value, bool):
            parsed.append(value)
            continue
        text = _display_text(value).casefold()
        if text in {"true", "1"}:
            parsed.append(True)
        elif text in {"false", "0", ""}:
            parsed.append(False)
        else:
            raise MaintenanceModelError(
                f"{table_name}.{column} contains invalid boolean value "
                f"{value!r}"
            )
    return pd.Series(parsed, index=table.index, dtype=bool)


def _meaningful_mask(table: pd.DataFrame) -> pd.Series:
    """Identify factual Stage 2 source rows eligible for model consideration."""
    # Match the explicit Stage 2 row classification case-insensitively.
    return (
        table["row_classification"]
        .astype("string")
        .str.strip()
        .str.casefold()
        .eq("meaningful")
        .fillna(False)
    )


def _normalize_source_row(value: object) -> str:
    """Normalize source-row values for issue and exclusion reconciliation."""
    # Make integer-like CSV values stable across string and numeric dtypes.
    if _is_blank(value):
        return ""
    try:
        numeric = float(value)
    except (TypeError, ValueError):
        return _display_text(value)
    if numeric.is_integer():
        return str(int(numeric))
    return str(numeric)


def _source_row_key(
    table_name: object,
    source_workbook: object,
    source_row: object,
) -> tuple[str, str, str]:
    """Build a stable table-workbook-row key for model issues."""
    # Normalize only identity fields while retaining full source values elsewhere.
    return (
        _display_text(table_name).casefold(),
        _display_text(source_workbook),
        _normalize_source_row(source_row),
    )


def _category_key(activity_id: object, asset_id: object) -> str:
    """Build the contextual parent-child category key."""
    # Require both semantic IDs so unsupported hierarchies cannot become facts.
    activity = _display_text(activity_id)
    asset = _display_text(asset_id)
    if not activity or not asset:
        raise MaintenanceModelError(
            "A maintenance category key requires activity and asset IDs"
        )
    return f"{activity}::{asset}"


def _validate_stage2_summary(summary: object) -> dict[str, bool]:
    """Validate the Stage 2 completeness summary used by the model."""
    # Require a JSON-object-like summary with factual boolean flags.
    if not isinstance(summary, dict):
        raise MaintenanceModelError("stage2_summary must be a dictionary")
    completeness: dict[str, bool] = {}
    for key in STAGE2_COMPLETENESS_KEYS:
        value = summary.get(key)
        if not isinstance(value, bool):
            raise MaintenanceModelError(
                f"stage2_summary.{key} must be a boolean"
            )
        completeness[key] = value

    # Reject a contradictory overall flag before it reaches model publication.
    derived_pipeline_complete = all(
        completeness[key]
        for key in STAGE2_COMPLETENESS_KEYS
        if key != "pipeline_complete"
    )
    if completeness["pipeline_complete"] != derived_pipeline_complete:
        raise MaintenanceModelError(
            "stage2_summary.pipeline_complete conflicts with its component "
            "flags"
        )
    return completeness


def _parse_reporting_period(period: object) -> tuple[int, int]:
    """Parse an AER reporting-period label into adjacent calendar years."""
    # Require the submitted four-digit/two-digit reporting-period convention.
    text = _display_text(period)
    match = re.fullmatch(r"((?:19|20)\d{2})-(\d{2})", text)
    if match is None:
        raise MaintenanceModelError(
            f"Unsupported reporting period: {period!r}"
        )

    # Resolve the two-digit end year within the start year's century.
    start_year = int(match.group(1))
    end_year = start_year // 100 * 100 + int(match.group(2))
    if end_year < start_year:
        end_year += 100
    if end_year != start_year + 1:
        raise MaintenanceModelError(
            f"Reporting period is not one year long: {text}"
        )
    return start_year, end_year


def _build_business_dimension(
    workbook_mapping: pd.DataFrame,
) -> tuple[pd.DataFrame, dict[str, str]]:
    """Build stable business IDs from authoritative workbook mappings."""
    # Collect nonblank business labels from the validated Stage 2 mappings.
    business_names = sorted(
        {
            _display_text(value)
            for value in workbook_mapping["business"].tolist()
            if not _is_blank(value)
        },
        key=str.casefold,
    )
    if not business_names:
        raise MaintenanceModelError("workbook_mapping contains no businesses")

    # Create deterministic IDs and reject label collisions after normalization.
    business_ids = {
        business_name: _source_identifier(business_name)
        for business_name in business_names
    }
    if len(set(business_ids.values())) != len(business_ids):
        raise MaintenanceModelError(
            "Distinct business labels resolve to the same business ID"
        )

    # Publish alphabetical display order for predictable Power BI slicers.
    records = [
        {
            "business_id": business_ids[business_name],
            "business_name": business_name,
            "business_sort_order": index,
        }
        for index, business_name in enumerate(business_names, start=1)
    ]
    return (
        pd.DataFrame(records, columns=BUSINESS_DIMENSION_COLUMNS),
        business_ids,
    )


def _build_reporting_period_dimension(
    workbook_mapping: pd.DataFrame,
    business_names: set[str],
) -> tuple[pd.DataFrame, list[str]]:
    """Build reporting-period attributes and balanced-panel membership."""
    # Validate one authoritative business-period mapping per source workbook.
    coverage = workbook_mapping.loc[
        :,
        ["business", "extracted_reporting_period"],
    ].copy()
    coverage["business"] = coverage["business"].map(_display_text)
    coverage["reporting_period"] = coverage[
        "extracted_reporting_period"
    ].map(_display_text)
    if (coverage["business"] == "").any() or (
        coverage["reporting_period"] == ""
    ).any():
        raise MaintenanceModelError(
            "workbook_mapping contains blank business or reporting period"
        )

    # Find periods represented by every model business without discarding history.
    coverage = coverage.drop_duplicates(["business", "reporting_period"])
    represented_counts = coverage.groupby("reporting_period")[
        "business"
    ].nunique()
    common_panel_periods = sorted(
        [
            period
            for period, count in represented_counts.items()
            if int(count) == len(business_names)
        ],
        key=lambda value: _parse_reporting_period(value)[0],
    )

    # Create chronological attributes for every available reporting period.
    records: list[dict[str, object]] = []
    all_periods = sorted(
        coverage["reporting_period"].unique().tolist(),
        key=lambda value: _parse_reporting_period(value)[0],
    )
    for sort_order, period in enumerate(all_periods, start=1):
        start_year, end_year = _parse_reporting_period(period)
        records.append(
            {
                "reporting_period": period,
                "period_start_year": start_year,
                "period_end_year": end_year,
                "period_sort_order": sort_order,
                "is_common_panel": period in common_panel_periods,
            }
        )
    return (
        pd.DataFrame(records, columns=REPORTING_PERIOD_DIMENSION_COLUMNS),
        common_panel_periods,
    )


def _build_source_workbook_dimension(
    workbook_mapping: pd.DataFrame,
    business_ids: dict[str, str],
) -> pd.DataFrame:
    """Build the technical workbook lineage dimension."""
    # Require one mapping row per immutable local workbook.
    if workbook_mapping["source_workbook"].duplicated().any():
        raise MaintenanceModelError(
            "workbook_mapping contains duplicate source_workbook values"
        )

    # Convert validated business labels to the shared dimension key.
    records: list[dict[str, object]] = []
    for _, row in workbook_mapping.iterrows():
        business_name = _display_text(row["business"])
        if business_name not in business_ids:
            raise MaintenanceModelError(
                f"Workbook has unknown business: {business_name!r}"
            )
        records.append(
            {
                "source_workbook": row["source_workbook"],
                "business_id": business_ids[business_name],
                "reporting_period": _display_text(
                    row["extracted_reporting_period"]
                ),
                "extraction_status": row["extraction_status"],
                "metadata_match_status": row["metadata_match_status"],
                "manifest_local_filename": row["manifest_local_filename"],
                "landing_page_url": row["landing_page_url"],
                "source_page_url": row["source_page_url"],
            }
        )

    # Sort the technical dimension for reproducible CSV diffs.
    dimension = pd.DataFrame(
        records,
        columns=SOURCE_WORKBOOK_DIMENSION_COLUMNS,
    )
    return dimension.sort_values(
        ["business_id", "reporting_period", "source_workbook"],
        kind="stable",
    ).reset_index(drop=True)


def _eligible_category_rows(
    table: pd.DataFrame,
    table_name: str,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Separate resolved analytic rows from meaningful exclusions."""
    # Apply the explicit Stage 2 classification and analytic eligibility flags.
    meaningful = _meaningful_mask(table)
    analytic = _boolean_series(
        table,
        "analytic_row_eligible",
        table_name,
    )
    resolved = (
        table["maintenance_activity_standard_id"].map(
            lambda value: not _is_blank(value)
        )
        & table["maintenance_asset_standard_id"].map(
            lambda value: not _is_blank(value)
        )
    )

    # Return rows safe for facts and meaningful rows needing disclosure.
    included = table.loc[meaningful & analytic & resolved].copy()
    excluded = table.loc[meaningful & ~(analytic & resolved)].copy()
    return included, excluded


def _build_category_dimension(
    descriptor_rows: pd.DataFrame,
    cost_rows: pd.DataFrame,
) -> pd.DataFrame:
    """Build the union of contextual descriptor and cost categories."""
    # Collect one labelled record per source table and contextual key.
    category_records: list[dict[str, object]] = []
    for table_name, table in (
        ("descriptor", descriptor_rows),
        ("cost", cost_rows),
    ):
        for _, row in table.iterrows():
            category_records.append(
                {
                    "maintenance_category_key": _category_key(
                        row["maintenance_activity_standard_id"],
                        row["maintenance_asset_standard_id"],
                    ),
                    "maintenance_activity_id": _display_text(
                        row["maintenance_activity_standard_id"]
                    ),
                    "maintenance_activity": _display_text(
                        row["maintenance_activity_standard"]
                    ),
                    "maintenance_asset_id": _display_text(
                        row["maintenance_asset_standard_id"]
                    ),
                    "maintenance_asset": _display_text(
                        row["maintenance_asset_standard"]
                    ),
                    "source_table": table_name,
                }
            )
    if not category_records:
        raise MaintenanceModelError("No resolved maintenance categories found")

    # Require one consistent label pair for every contextual semantic key.
    categories = pd.DataFrame(category_records)
    label_counts = categories.groupby("maintenance_category_key").agg(
        activity_ids=("maintenance_activity_id", "nunique"),
        activity_labels=("maintenance_activity", "nunique"),
        asset_ids=("maintenance_asset_id", "nunique"),
        asset_labels=("maintenance_asset", "nunique"),
    )
    inconsistent = label_counts[
        (label_counts != 1).any(axis=1)
    ].index.tolist()
    if inconsistent:
        raise MaintenanceModelError(
            "Category keys have inconsistent IDs or labels: "
            + ", ".join(inconsistent)
        )

    # Collapse source occurrences while retaining descriptor and cost presence.
    records: list[dict[str, object]] = []
    for key, group in categories.groupby(
        "maintenance_category_key",
        sort=False,
    ):
        first = group.iloc[0]
        source_tables = set(group["source_table"].tolist())
        records.append(
            {
                "maintenance_category_key": key,
                "maintenance_activity_id": first[
                    "maintenance_activity_id"
                ],
                "maintenance_activity": first["maintenance_activity"],
                "maintenance_asset_id": first["maintenance_asset_id"],
                "maintenance_asset": first["maintenance_asset"],
                "appears_in_descriptor": "descriptor" in source_tables,
                "appears_in_cost": "cost" in source_tables,
            }
        )

    # Sort parent and child labels before assigning a durable display order.
    dimension = pd.DataFrame(records).sort_values(
        ["maintenance_activity", "maintenance_asset"],
        key=lambda column: column.astype("string").str.casefold(),
        kind="stable",
    ).reset_index(drop=True)
    dimension["maintenance_category_sort_order"] = range(
        1,
        len(dimension) + 1,
    )
    return dimension.loc[:, CATEGORY_DIMENSION_COLUMNS]


def _build_metric_dimension() -> pd.DataFrame:
    """Build the fixed descriptor metric dimension."""
    # Publish semantic names and ordering without source-column implementation data.
    records = [
        {
            "metric_id": definition["metric_id"],
            "metric_name": definition["metric_name"],
            "metric_group": definition["metric_group"],
            "metric_sort_order": index,
        }
        for index, definition in enumerate(METRIC_DEFINITIONS, start=1)
    ]
    return pd.DataFrame(records, columns=METRIC_DIMENSION_COLUMNS)


def _business_id_for_row(
    row: pd.Series,
    business_ids: dict[str, str],
) -> str:
    """Resolve a fact row to its shared business dimension key."""
    # Require the Stage 2 business label to match an authoritative mapping label.
    business_name = _display_text(row["business"])
    if business_name not in business_ids:
        raise MaintenanceModelError(
            f"Fact row has unknown business: {business_name!r}"
        )
    return business_ids[business_name]


def _build_descriptor_fact(
    descriptor_rows: pd.DataFrame,
    business_ids: dict[str, str],
) -> pd.DataFrame:
    """Reshape resolved descriptor metrics to the long model grain."""
    # Expand each source category row into the five explicit metric records.
    records: list[dict[str, object]] = []
    for _, row in descriptor_rows.iterrows():
        category_key = _category_key(
            row["maintenance_activity_standard_id"],
            row["maintenance_asset_standard_id"],
        )
        for definition in METRIC_DEFINITIONS:
            unit = (
                row[definition["unit_column"]]
                if "unit_column" in definition
                else definition["fixed_unit"]
            )
            records.append(
                {
                    "business_id": _business_id_for_row(
                        row,
                        business_ids,
                    ),
                    "reporting_period": _display_text(
                        row["reporting_period"]
                    ),
                    "maintenance_category_key": category_key,
                    "metric_id": definition["metric_id"],
                    "metric_value": row[definition["standard_column"]],
                    "metric_unit": unit,
                    "metric_status": row[definition["status_column"]],
                    "source_value": row[definition["source_column"]],
                    "source_workbook": row["source_workbook"],
                    "source_sheet": row["source_sheet"],
                    "source_row": row["source_row"],
                }
            )

    # Preserve a fixed schema even when fabricated inputs contain no safe rows.
    return pd.DataFrame(records, columns=DESCRIPTOR_FACT_COLUMNS)


def _source_record_keys(table: pd.DataFrame) -> set[tuple[str, str, str]]:
    """Return workbook-sheet-row identities for cost coverage validation."""
    # Normalize source identity fields so CSV dtype inference cannot change keys.
    return {
        (
            _display_text(row["source_workbook"]),
            _display_text(row["source_sheet"]),
            _normalize_source_row(row["source_row"]),
        )
        for _, row in table.iterrows()
    }


def _validate_cost_relationship_coverage(
    cost_rows: pd.DataFrame,
    relationship_rows: pd.DataFrame,
) -> None:
    """Require one relationship row for every resolved analytic cost row."""
    # Compare source identities before the relationship table becomes the fact.
    cost_keys = _source_record_keys(cost_rows)
    relationship_keys = _source_record_keys(relationship_rows)
    if cost_keys != relationship_keys:
        missing = sorted(cost_keys - relationship_keys)
        unexpected = sorted(relationship_keys - cost_keys)
        raise MaintenanceModelError(
            "Cost relationship coverage differs from standardized cost rows; "
            f"missing={missing}, unexpected={unexpected}"
        )


def _build_cost_fact(
    relationship_rows: pd.DataFrame,
    business_ids: dict[str, str],
) -> pd.DataFrame:
    """Build the Power BI cost fact without precomputed row ratios."""
    # Rename only standardized expenditures and matched denominator evidence.
    records: list[dict[str, object]] = []
    for _, row in relationship_rows.iterrows():
        records.append(
            {
                "business_id": _business_id_for_row(row, business_ids),
                "reporting_period": _display_text(
                    row["reporting_period"]
                ),
                "maintenance_category_key": _category_key(
                    row["maintenance_activity_standard_id"],
                    row["maintenance_asset_standard_id"],
                ),
                "routine_expenditure_aud": row[
                    "routine_maintenance_expenditure_standard"
                ],
                "routine_expenditure_status": row[
                    "routine_maintenance_expenditure_status"
                ],
                "non_routine_expenditure_aud": row[
                    "non_routine_maintenance_expenditure_standard"
                ],
                "non_routine_expenditure_status": row[
                    "non_routine_maintenance_expenditure_status"
                ],
                "total_expenditure_aud": row[
                    "total_maintenance_expenditure_standard"
                ],
                "total_expenditure_status": row[
                    "total_maintenance_expenditure_status"
                ],
                "currency": row["currency_standard"],
                "price_basis": row["price_basis"],
                "installed_quantity": row[
                    "installed_quantity_standard"
                ],
                "installed_quantity_status": row[
                    "installed_quantity_status"
                ],
                "serviced_quantity": row[
                    "serviced_quantity_standard"
                ],
                "serviced_quantity_status": row[
                    "serviced_quantity_status"
                ],
                "denominator_unit": row["denominator_unit_standard"],
                "relationship_status": row["relationship_status"],
                "installed_ratio_status": row["installed_ratio_status"],
                "serviced_ratio_status": row["serviced_ratio_status"],
                "source_workbook": row["source_workbook"],
                "source_sheet": row["source_sheet"],
                "source_row": row["source_row"],
                "descriptor_source_workbook": row[
                    "descriptor_source_workbook"
                ],
                "descriptor_source_sheet": row[
                    "descriptor_source_sheet"
                ],
                "descriptor_source_row": row[
                    "descriptor_source_row"
                ],
            }
        )
    return pd.DataFrame(records, columns=COST_FACT_COLUMNS)


def _build_model_issues(
    stage2_issues: pd.DataFrame,
    descriptor_exclusions: pd.DataFrame,
    cost_exclusions: pd.DataFrame,
) -> tuple[pd.DataFrame, int]:
    """Preserve Stage 2 issues and disclose rows excluded from model facts."""
    # Build the complete set of meaningful source rows omitted from facts.
    excluded_keys: set[tuple[str, str, str]] = set()
    excluded_rows: list[tuple[str, pd.Series]] = []
    for table_name, table in (
        ("descriptor_metrics", descriptor_exclusions),
        ("cost_metrics", cost_exclusions),
    ):
        for _, row in table.iterrows():
            key = _source_row_key(
                table_name,
                row["source_workbook"],
                row["source_row"],
            )
            excluded_keys.add(key)
            excluded_rows.append((table_name, row))

    # Attach a model action to each existing Stage 2 issue.
    records: list[dict[str, object]] = []
    covered_exclusions: set[tuple[str, str, str]] = set()
    for _, issue in stage2_issues.iterrows():
        key = _source_row_key(
            issue["table_name"],
            issue["source_workbook"],
            issue["source_row"],
        )
        action = (
            "excluded_from_analytic_fact"
            if key in excluded_keys
            else "retained_for_review"
        )
        if key in excluded_keys:
            covered_exclusions.add(key)
        records.append(
            {
                **{
                    column: issue[column]
                    for column in ISSUE_REQUIRED_COLUMNS
                },
                "model_action": action,
            }
        )

    # Generate a Stage 3 issue when an excluded row lacks upstream disclosure.
    for table_name, row in excluded_rows:
        key = _source_row_key(
            table_name,
            row["source_workbook"],
            row["source_row"],
        )
        if key in covered_exclusions:
            continue
        records.append(
            {
                "stage": "3",
                "severity": "error",
                "table_name": table_name,
                "source_workbook": row["source_workbook"],
                "source_row": row["source_row"],
                "issue_code": "excluded_unresolved_model_row",
                "message": (
                    "A meaningful row lacks the resolved category or "
                    "eligibility required for an analytic fact."
                ),
                "model_action": "excluded_from_analytic_fact",
            }
        )

    # Preserve a fixed issue schema for empty and nonempty results.
    return (
        pd.DataFrame(records, columns=MODEL_ISSUE_COLUMNS),
        len(excluded_keys),
    )


def _require_unique_grain(
    table_name: str,
    table: pd.DataFrame,
    grain_columns: list[str],
) -> None:
    """Reject unintended duplicates at a declared fact or dimension grain."""
    # Show representative duplicate keys rather than silently aggregating them.
    duplicates = table.loc[
        table.duplicated(grain_columns, keep=False),
        grain_columns,
    ].drop_duplicates()
    if not duplicates.empty:
        examples = duplicates.head(5).to_dict("records")
        raise MaintenanceModelError(
            f"{table_name} has duplicate grain values: {examples}"
        )


def _require_foreign_keys(
    fact_name: str,
    fact: pd.DataFrame,
    fact_column: str,
    dimension: pd.DataFrame,
    dimension_column: str,
) -> None:
    """Require every fact key to exist in its shared dimension."""
    # Compare nonblank key sets and report every unresolved foreign key.
    dimension_keys = set(dimension[dimension_column].dropna().tolist())
    fact_keys = set(fact[fact_column].dropna().tolist())
    missing = sorted(fact_keys - dimension_keys)
    if missing:
        raise MaintenanceModelError(
            f"{fact_name}.{fact_column} has unresolved keys: {missing}"
        )


def _validate_model(
    result_tables: dict[str, pd.DataFrame],
) -> None:
    """Validate model grains and relationships before publication."""
    # Require unique natural keys in each shared dimension.
    _require_unique_grain(
        "business_dimension",
        result_tables["business_dimension"],
        ["business_id"],
    )
    _require_unique_grain(
        "reporting_period_dimension",
        result_tables["reporting_period_dimension"],
        ["reporting_period"],
    )
    _require_unique_grain(
        "maintenance_category_dimension",
        result_tables["maintenance_category_dimension"],
        ["maintenance_category_key"],
    )
    _require_unique_grain(
        "metric_dimension",
        result_tables["metric_dimension"],
        ["metric_id"],
    )
    _require_unique_grain(
        "source_workbook_dimension",
        result_tables["source_workbook_dimension"],
        ["source_workbook"],
    )

    # Require the business-period-category-metric descriptor grain.
    _require_unique_grain(
        "descriptor_fact",
        result_tables["descriptor_fact"],
        [
            "business_id",
            "reporting_period",
            "maintenance_category_key",
            "metric_id",
        ],
    )

    # Require the business-period-category cost grain.
    _require_unique_grain(
        "cost_fact",
        result_tables["cost_fact"],
        [
            "business_id",
            "reporting_period",
            "maintenance_category_key",
        ],
    )

    # Require all fact keys to resolve to the shared dimensions.
    for fact_name in ("descriptor_fact", "cost_fact"):
        fact = result_tables[fact_name]
        _require_foreign_keys(
            fact_name,
            fact,
            "business_id",
            result_tables["business_dimension"],
            "business_id",
        )
        _require_foreign_keys(
            fact_name,
            fact,
            "reporting_period",
            result_tables["reporting_period_dimension"],
            "reporting_period",
        )
        _require_foreign_keys(
            fact_name,
            fact,
            "maintenance_category_key",
            result_tables["maintenance_category_dimension"],
            "maintenance_category_key",
        )
        _require_foreign_keys(
            fact_name,
            fact,
            "source_workbook",
            result_tables["source_workbook_dimension"],
            "source_workbook",
        )
    _require_foreign_keys(
        "descriptor_fact",
        result_tables["descriptor_fact"],
        "metric_id",
        result_tables["metric_dimension"],
        "metric_id",
    )


def _status_counts(table: pd.DataFrame, column: str) -> dict[str, int]:
    """Count a model status column without discarding blank values."""
    # Convert missing statuses to an explicit JSON-safe label.
    counts: dict[str, int] = {}
    for value, count in table[column].value_counts(
        dropna=False,
    ).items():
        key = "<missing>" if pd.isna(value) else str(value)
        counts[key] = int(count)
    return counts


def _build_model_summary(
    completeness: dict[str, bool],
    result_tables: dict[str, pd.DataFrame],
    common_panel_periods: list[str],
    excluded_source_rows: int,
) -> dict[str, Any]:
    """Build the durable Stage 3 publication and coverage summary."""
    # Separate successful model construction from upstream source completeness.
    source_pipeline_complete = bool(completeness["pipeline_complete"])
    model_build_complete = True
    model_complete = (
        source_pipeline_complete
        and excluded_source_rows == 0
    )
    publication_status = (
        "complete"
        if model_complete
        else "usable_with_disclosed_exceptions"
    )

    # Count every published table and the distinct omitted source rows.
    row_counts = {
        "business_dimension_rows": int(
            len(result_tables["business_dimension"])
        ),
        "reporting_period_dimension_rows": int(
            len(result_tables["reporting_period_dimension"])
        ),
        "maintenance_category_dimension_rows": int(
            len(result_tables["maintenance_category_dimension"])
        ),
        "metric_dimension_rows": int(
            len(result_tables["metric_dimension"])
        ),
        "source_workbook_dimension_rows": int(
            len(result_tables["source_workbook_dimension"])
        ),
        "descriptor_fact_rows": int(
            len(result_tables["descriptor_fact"])
        ),
        "cost_fact_rows": int(len(result_tables["cost_fact"])),
        "model_issue_rows": int(len(result_tables["issues"])),
        "excluded_source_rows": int(excluded_source_rows),
    }

    # Retain cost relationship outcomes needed to interpret ratio coverage.
    status_counts = {
        "relationship_status": _status_counts(
            result_tables["cost_fact"],
            "relationship_status",
        ),
        "installed_ratio_status": _status_counts(
            result_tables["cost_fact"],
            "installed_ratio_status",
        ),
        "serviced_ratio_status": _status_counts(
            result_tables["cost_fact"],
            "serviced_ratio_status",
        ),
    }

    # Return one explicit summary for CLI exit codes and Power BI disclosure.
    return {
        "stage2_completeness": {
            key: completeness[key]
            for key in STAGE2_COMPLETENESS_KEYS
        },
        "model_build_complete": model_build_complete,
        "source_pipeline_complete": source_pipeline_complete,
        "model_complete": model_complete,
        "publication_status": publication_status,
        "common_panel_periods": common_panel_periods,
        "row_counts": row_counts,
        "status_counts": status_counts,
    }


def build_rin_maintenance_model(
    descriptor_metrics: pd.DataFrame,
    cost_metrics: pd.DataFrame,
    workbook_mapping: pd.DataFrame,
    cost_descriptor_relationships: pd.DataFrame,
    issues: pd.DataFrame,
    stage2_summary: dict[str, Any],
) -> MaintenanceModelResult:
    """Build the Stage 3 star model from persistent Stage 2 artifacts."""
    # Validate every public input and its minimum Stage 2 column contract.
    inputs = {
        "descriptor_metrics": _require_dataframe(
            "descriptor_metrics",
            descriptor_metrics,
        ),
        "cost_metrics": _require_dataframe("cost_metrics", cost_metrics),
        "workbook_mapping": _require_dataframe(
            "workbook_mapping",
            workbook_mapping,
        ),
        "cost_descriptor_relationships": _require_dataframe(
            "cost_descriptor_relationships",
            cost_descriptor_relationships,
        ),
        "issues": _require_dataframe("issues", issues),
    }
    for name, required_columns in (
        ("descriptor_metrics", DESCRIPTOR_REQUIRED_COLUMNS),
        ("cost_metrics", COST_REQUIRED_COLUMNS),
        ("workbook_mapping", WORKBOOK_MAPPING_REQUIRED_COLUMNS),
        (
            "cost_descriptor_relationships",
            RELATIONSHIP_REQUIRED_COLUMNS,
        ),
        ("issues", ISSUE_REQUIRED_COLUMNS),
    ):
        _require_columns(name, inputs[name], required_columns)
    completeness = _validate_stage2_summary(stage2_summary)

    # Build authoritative business, period, and workbook dimensions first.
    business_dimension, business_ids = _build_business_dimension(
        inputs["workbook_mapping"]
    )
    business_names = set(business_ids)
    reporting_period_dimension, common_panel_periods = (
        _build_reporting_period_dimension(
            inputs["workbook_mapping"],
            business_names,
        )
    )
    source_workbook_dimension = _build_source_workbook_dimension(
        inputs["workbook_mapping"],
        business_ids,
    )

    # Separate resolved analytic rows from meaningful disclosed exceptions.
    descriptor_rows, descriptor_exclusions = _eligible_category_rows(
        inputs["descriptor_metrics"],
        "descriptor_metrics",
    )
    cost_rows, cost_exclusions = _eligible_category_rows(
        inputs["cost_metrics"],
        "cost_metrics",
    )
    relationship_rows, relationship_exclusions = _eligible_category_rows(
        inputs["cost_descriptor_relationships"],
        "cost_descriptor_relationships",
    )
    if not relationship_exclusions.empty:
        cost_exclusions = pd.concat(
            [cost_exclusions, relationship_exclusions],
            ignore_index=True,
        )

    # Require the relationship artifact to cover every safe Stage 2 cost row.
    _validate_cost_relationship_coverage(cost_rows, relationship_rows)

    # Build shared category and metric dimensions from resolved source semantics.
    maintenance_category_dimension = _build_category_dimension(
        descriptor_rows,
        relationship_rows,
    )
    metric_dimension = _build_metric_dimension()

    # Build the two facts at their distinct, declared analytical grains.
    descriptor_fact = _build_descriptor_fact(
        descriptor_rows,
        business_ids,
    )
    cost_fact = _build_cost_fact(
        relationship_rows,
        business_ids,
    )

    # Preserve upstream issues and disclose every meaningful omitted source row.
    model_issues, excluded_source_rows = _build_model_issues(
        inputs["issues"],
        descriptor_exclusions,
        cost_exclusions,
    )

    # Validate all model keys and grains before declaring a build successful.
    result_tables = {
        "business_dimension": business_dimension,
        "reporting_period_dimension": reporting_period_dimension,
        "maintenance_category_dimension": (
            maintenance_category_dimension
        ),
        "metric_dimension": metric_dimension,
        "source_workbook_dimension": source_workbook_dimension,
        "descriptor_fact": descriptor_fact,
        "cost_fact": cost_fact,
        "issues": model_issues,
    }
    _validate_model(result_tables)

    # Build the summary only after every table passes structural validation.
    summary = _build_model_summary(
        completeness,
        result_tables,
        common_panel_periods,
        excluded_source_rows,
    )

    # Return in-memory tables for both notebook review and file-based CLI use.
    return MaintenanceModelResult(
        business_dimension=business_dimension,
        reporting_period_dimension=reporting_period_dimension,
        maintenance_category_dimension=maintenance_category_dimension,
        metric_dimension=metric_dimension,
        source_workbook_dimension=source_workbook_dimension,
        descriptor_fact=descriptor_fact,
        cost_fact=cost_fact,
        issues=model_issues,
        summary=summary,
    )
