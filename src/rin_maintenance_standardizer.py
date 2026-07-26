"""Stage 2 enrichment and standardisation for RIN maintenance tables."""

from __future__ import annotations

import json
import re
import unicodedata
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any

import pandas as pd


DEFAULT_STANDARDIZATION_CONFIG = (
    Path(__file__).resolve().parents[1]
    / "config"
    / "rin_maintenance_standardization.json"
)

DESCRIPTOR_REQUIRED_COLUMNS = (
    "reporting_period",
    "maintenance_activity",
    "maintenance_asset_category",
    "measure_asset_quantity",
    "source_unit",
    "asset_quantity_at_year_end",
    "quantity_inspected_maintained",
    "average_age_of_asset_group",
    "inspection_cycle_years",
    "maintenance_cycle_years",
    "source_workbook",
    "source_sheet",
    "source_row",
)
DESCRIPTOR_METRIC_COLUMNS = (
    "asset_quantity_at_year_end",
    "quantity_inspected_maintained",
    "average_age_of_asset_group",
    "inspection_cycle_years",
    "maintenance_cycle_years",
)

COST_REQUIRED_COLUMNS = (
    "reporting_period",
    "maintenance_activity",
    "maintenance_asset_subcategory",
    "source_currency_unit",
    "routine_maintenance_expenditure",
    "non_routine_maintenance_expenditure",
    "source_workbook",
    "source_sheet",
    "source_row",
)
COST_METRIC_COLUMNS = (
    "routine_maintenance_expenditure",
    "non_routine_maintenance_expenditure",
)

RUN_REPORT_REQUIRED_COLUMNS = (
    "source_workbook",
    "status",
    "reporting_period",
    "run_complete",
)
MANIFEST_REQUIRED_COLUMNS = (
    "business",
    "reporting_period",
    "landing_page_url",
    "source_page_url",
    "local_filename",
)

ENRICHMENT_COLUMNS = (
    "business",
    "landing_page_url",
    "source_page_url",
    "metadata_match_status",
    "maintenance_activity_resolved",
    "activity_resolution_status",
    "activity_anchor_source_row",
    "row_classification",
)
WORKBOOK_MAPPING_COLUMNS = (
    "source_workbook",
    "extraction_status",
    "run_report_reporting_period",
    "extracted_reporting_period",
    "manifest_local_filename",
    "business",
    "manifest_reporting_period",
    "landing_page_url",
    "source_page_url",
    "metadata_match_status",
)
ISSUE_COLUMNS = (
    "severity",
    "table_name",
    "source_workbook",
    "source_row",
    "issue_code",
    "message",
)

TABLE_CONTRACTS = {
    "descriptor_metrics": {
        "required_columns": DESCRIPTOR_REQUIRED_COLUMNS,
        "child_column": "maintenance_asset_category",
        "metric_columns": DESCRIPTOR_METRIC_COLUMNS,
    },
    "cost_metrics": {
        "required_columns": COST_REQUIRED_COLUMNS,
        "child_column": "maintenance_asset_subcategory",
        "metric_columns": COST_METRIC_COLUMNS,
    },
}

VALID_EXTRACTION_STATUSES = {"success", "failed"}
VALID_BOOLEAN_TEXT = {"true": True, "false": False}
STAGE2B_ISSUE_COLUMNS = (
    "stage",
    "severity",
    "table_name",
    "source_workbook",
    "source_row",
    "issue_code",
    "message",
)
STAGE2B_CATEGORY_COLUMNS = (
    "analytic_row_eligible",
    "maintenance_activity_standard_id",
    "maintenance_activity_standard",
    "maintenance_asset_standard_id",
    "maintenance_asset_standard",
    "activity_mapping_status",
    "asset_mapping_status",
)
DESCRIPTOR_STANDARD_COLUMNS = (
    *STAGE2B_CATEGORY_COLUMNS,
    "quantity_unit_standard",
    "quantity_scale_factor",
    "quantity_unit_status",
    "asset_quantity_at_year_end_standard",
    "asset_quantity_at_year_end_status",
    "quantity_inspected_maintained_standard",
    "quantity_inspected_maintained_status",
    "average_age_of_asset_group_standard",
    "average_age_of_asset_group_status",
    "inspection_cycle_years_standard",
    "inspection_cycle_years_status",
    "maintenance_cycle_years_standard",
    "maintenance_cycle_years_status",
)
COST_STANDARD_COLUMNS = (
    *STAGE2B_CATEGORY_COLUMNS,
    "currency_standard",
    "price_basis",
    "currency_scale_factor",
    "currency_unit_status",
    "routine_maintenance_expenditure_standard",
    "routine_maintenance_expenditure_status",
    "non_routine_maintenance_expenditure_standard",
    "non_routine_maintenance_expenditure_status",
    "total_maintenance_expenditure_standard",
    "total_maintenance_expenditure_status",
)

__all__ = [
    "MaintenanceStage2AResult",
    "MaintenanceStage2BResult",
    "MaintenanceStandardizationError",
    "DEFAULT_STANDARDIZATION_CONFIG",
    "enrich_rin_maintenance",
    "load_standardization_config",
    "prepare_rin_maintenance",
    "standardize_rin_maintenance",
]


class MaintenanceStandardizationError(RuntimeError):
    """Raised when Stage 2 inputs cannot be processed safely."""


@dataclass
class MaintenanceStage2AResult:
    """Enriched tables, reconciliation evidence, and completeness flags."""

    descriptor_metrics: pd.DataFrame
    cost_metrics: pd.DataFrame
    workbook_mapping: pd.DataFrame
    issues: pd.DataFrame
    extraction_complete: bool
    stage2a_complete: bool


@dataclass
class MaintenanceStage2BResult:
    """Standardised tables, relationships, issues, and completeness flags."""

    descriptor_metrics: pd.DataFrame
    cost_metrics: pd.DataFrame
    workbook_mapping: pd.DataFrame
    cost_descriptor_relationships: pd.DataFrame
    issues: pd.DataFrame
    extraction_complete: bool
    stage2a_complete: bool
    stage2b_complete: bool
    panel_complete: bool


def _is_blank(value: object) -> bool:
    """Return whether a scalar source value should be treated as blank."""
    if value is None:
        return True

    # Treat whitespace-only source strings as blank without altering them.
    if isinstance(value, str):
        return not value.strip()

    # Recognize pandas scalar missing values without evaluating array-like data.
    try:
        return bool(pd.isna(value))
    except (TypeError, ValueError):
        return False


def _display_text(value: object) -> str:
    """Return collapsed display text while preserving submitted casing."""
    if _is_blank(value):
        return ""

    # Collapse presentation whitespace for identifiers and factual messages.
    return re.sub(r"\s+", " ", str(value)).strip()


def _normalize_match_text(value: object) -> str:
    """Normalize text for deterministic case-insensitive matching."""
    if _is_blank(value):
        return ""

    # Normalize compatible Unicode forms before applying case-insensitive rules.
    normalized = unicodedata.normalize("NFKC", str(value)).casefold()

    # Treat common typographic quotes and dashes as presentation equivalents.
    normalized = normalized.translate(
        str.maketrans(
            {
                "\u2018": "'",
                "\u2019": "'",
                "\u201c": '"',
                "\u201d": '"',
                "\u2013": "-",
                "\u2014": "-",
            }
        )
    )

    # Collapse whitespace so presentation differences do not affect matching.
    return re.sub(r"\s+", " ", normalized).strip()


def _require_dataframe(name: str, value: object) -> pd.DataFrame:
    """Require one pandas DataFrame input and return it unchanged."""
    # Reject non-tabular inputs before inspecting their expected contracts.
    if not isinstance(value, pd.DataFrame):
        raise MaintenanceStandardizationError(
            f"{name} must be a pandas DataFrame."
        )
    return value


def _require_columns(
    name: str,
    table: pd.DataFrame,
    required_columns: tuple[str, ...],
) -> None:
    """Require the columns needed by one Stage 2A input contract."""
    # Report every missing field together so the caller can fix one contract.
    missing_columns = [
        column for column in required_columns if column not in table.columns
    ]
    if missing_columns:
        raise MaintenanceStandardizationError(
            f"{name} is missing required column(s): "
            f"{', '.join(missing_columns)}."
        )


def _require_unique_columns(name: str, table: pd.DataFrame) -> None:
    """Require unambiguous column labels for scalar field access."""
    # Duplicate labels make pandas return tables where scalar columns are expected.
    duplicate_columns = table.columns[
        table.columns.duplicated(keep=False)
    ].tolist()
    if duplicate_columns:
        raise MaintenanceStandardizationError(
            f"{name} contains duplicate column label(s): "
            f"{', '.join(map(str, duplicate_columns))}."
        )


def _require_no_enrichment_collisions(
    name: str,
    table: pd.DataFrame,
) -> None:
    """Reject canonical inputs that already contain Stage 2A output fields."""
    # Prevent an enrichment run from silently replacing prior derived values.
    collisions = [
        column for column in ENRICHMENT_COLUMNS if column in table.columns
    ]
    if collisions:
        raise MaintenanceStandardizationError(
            f"{name} already contains Stage 2A column(s): "
            f"{', '.join(collisions)}."
        )


def _validated_source_rows(
    name: str,
    table: pd.DataFrame,
) -> pd.Series:
    """Validate source lineage and return source rows as nullable integers."""
    # Require stable workbook and sheet identifiers for bounded grouping.
    for column in ("source_workbook", "source_sheet"):
        if table[column].map(_is_blank).any():
            raise MaintenanceStandardizationError(
                f"{name}.{column} contains a blank value."
            )

    # Parse each physical row exactly so booleans and oversized integers fail.
    normalized_rows: list[int] = []
    int64_max = 2**63 - 1
    for value in table["source_row"]:
        if isinstance(value, bool) or type(value).__name__ == "bool_":
            raise MaintenanceStandardizationError(
                f"{name}.source_row must contain positive whole numbers."
            )

        # Use decimal text to avoid float overflow and precision surprises.
        try:
            numeric_value = Decimal(_display_text(value))
        except (InvalidOperation, ValueError):
            raise MaintenanceStandardizationError(
                f"{name}.source_row must contain positive whole numbers."
            ) from None
        if (
            not numeric_value.is_finite()
            or numeric_value != numeric_value.to_integral_value()
        ):
            raise MaintenanceStandardizationError(
                f"{name}.source_row must contain positive whole numbers."
            )

        # Bound physical rows to pandas' nullable signed-integer representation.
        integer_value = int(numeric_value)
        if integer_value < 1 or integer_value > int64_max:
            raise MaintenanceStandardizationError(
                f"{name}.source_row must contain positive whole numbers."
            )
        normalized_rows.append(integer_value)

    # Keep normalized rows private while retaining the submitted source column.
    source_rows = pd.Series(
        pd.array(normalized_rows, dtype="Int64"),
        index=table.index,
    )

    # Reject duplicate source coordinates because their order is ambiguous.
    lineage = pd.DataFrame(
        {
            "source_workbook": table["source_workbook"].to_numpy(),
            "source_sheet": table["source_sheet"].to_numpy(),
            "source_row": source_rows.to_numpy(),
        }
    )
    if lineage.duplicated(
        ["source_workbook", "source_sheet", "source_row"],
        keep=False,
    ).any():
        raise MaintenanceStandardizationError(
            f"{name} contains duplicate workbook, sheet, and source-row "
            "lineage."
        )

    return source_rows


def _parse_run_complete(value: object) -> bool:
    """Parse one factual run-completion value without truthy coercion."""
    # Accept the boolean text emitted by CSV round-tripping and real booleans.
    normalized = _normalize_match_text(value)
    if normalized not in VALID_BOOLEAN_TEXT:
        raise MaintenanceStandardizationError(
            "run_report.run_complete must contain only true or false values."
        )
    return VALID_BOOLEAN_TEXT[normalized]


def _validate_run_report(
    run_report: pd.DataFrame,
) -> tuple[list[str], bool]:
    """Validate one preprocessing run report and derive completion."""
    # Require at least one attempted workbook to define the supplied run.
    if run_report.empty:
        raise MaintenanceStandardizationError(
            "run_report must contain at least one attempted workbook."
        )

    # Require one nonblank, unique report record for each attempted workbook.
    if run_report["source_workbook"].map(_is_blank).any():
        raise MaintenanceStandardizationError(
            "run_report.source_workbook contains a blank value."
        )
    if run_report["source_workbook"].duplicated(keep=False).any():
        raise MaintenanceStandardizationError(
            "run_report contains duplicate source_workbook records."
        )

    # Normalize extraction statuses while retaining their source columns.
    statuses = [
        _normalize_match_text(value) for value in run_report["status"]
    ]
    invalid_statuses = sorted(
        {status for status in statuses if status not in VALID_EXTRACTION_STATUSES}
    )
    if invalid_statuses:
        raise MaintenanceStandardizationError(
            "run_report.status contains unsupported value(s): "
            f"{', '.join(invalid_statuses)}."
        )

    # Require one consistent run-level completion value across report rows.
    completion_values = {
        _parse_run_complete(value)
        for value in run_report["run_complete"]
    }
    if len(completion_values) != 1:
        raise MaintenanceStandardizationError(
            "run_report.run_complete is inconsistent across workbooks."
        )
    extraction_complete = completion_values.pop()

    # Ensure the summary flag agrees with the per-workbook extraction statuses.
    expected_complete = all(status == "success" for status in statuses)
    if extraction_complete != expected_complete:
        raise MaintenanceStandardizationError(
            "run_report.run_complete conflicts with workbook statuses."
        )

    return statuses, extraction_complete


def _validate_artifact_inventory(
    descriptor_metrics: pd.DataFrame,
    cost_metrics: pd.DataFrame,
    run_report: pd.DataFrame,
    statuses: list[str],
) -> None:
    """Require canonical tables and the run report to describe one run."""
    # Require both canonical tables to contain at least one successful workbook.
    if descriptor_metrics.empty or cost_metrics.empty:
        raise MaintenanceStandardizationError(
            "descriptor_metrics and cost_metrics must both contain rows."
        )

    # Compare exact workbook identities across both canonical table contracts.
    descriptor_workbooks = set(descriptor_metrics["source_workbook"])
    cost_workbooks = set(cost_metrics["source_workbook"])
    if descriptor_workbooks != cost_workbooks:
        raise MaintenanceStandardizationError(
            "Descriptor and cost tables contain different source workbooks."
        )

    # Require the canonical workbooks to equal the successful report inventory.
    successful_workbooks = {
        run_report.iloc[position]["source_workbook"]
        for position, status in enumerate(statuses)
        if status == "success"
    }
    if descriptor_workbooks != successful_workbooks:
        raise MaintenanceStandardizationError(
            "Canonical workbooks do not match successful run-report records."
        )


def _validate_manifest_inventory(manifest: pd.DataFrame) -> None:
    """Require exact, unique local filenames for Stage 2A reconciliation."""
    # Reject blank filenames because they cannot identify a local source file.
    if manifest["local_filename"].map(_is_blank).any():
        raise MaintenanceStandardizationError(
            "manifest.local_filename contains a blank value."
        )

    # Reject duplicate exact filenames before any workbook-level matching.
    if manifest["local_filename"].duplicated(keep=False).any():
        duplicates = sorted(
            {
                _display_text(value)
                for value in manifest.loc[
                    manifest["local_filename"].duplicated(keep=False),
                    "local_filename",
                ]
            }
        )
        raise MaintenanceStandardizationError(
            "manifest.local_filename contains duplicate value(s): "
            f"{', '.join(duplicates)}."
        )


def _period_evidence(
    source_workbook: str,
    descriptor_metrics: pd.DataFrame,
    cost_metrics: pd.DataFrame,
) -> tuple[object, set[str], bool]:
    """Collect extracted period evidence for one successful workbook."""
    # Read period values from both independent maintenance tables.
    period_values: list[object] = []
    for table in (descriptor_metrics, cost_metrics):
        workbook_rows = table.loc[
            table["source_workbook"].eq(source_workbook),
            "reporting_period",
        ]
        period_values.extend(workbook_rows.tolist())

    # Track blanks separately because they cannot identify a manifest record.
    has_blank = any(_is_blank(value) for value in period_values)
    periods = {
        _display_text(value)
        for value in period_values
        if not _is_blank(value)
    }
    extracted_period: object = (
        next(iter(periods))
        if len(periods) == 1 and not has_blank
        else pd.NA
    )
    return extracted_period, periods, has_blank


def _issue(
    *,
    table_name: str,
    source_workbook: object,
    issue_code: str,
    message: str,
    source_row: object = pd.NA,
) -> dict[str, object]:
    """Construct one fixed-schema Stage 2A issue record."""
    # Treat all current reconciliation issues as publication-blocking errors.
    return {
        "severity": "error",
        "table_name": table_name,
        "source_workbook": source_workbook,
        "source_row": source_row,
        "issue_code": issue_code,
        "message": message,
    }


def _build_workbook_mapping(
    descriptor_metrics: pd.DataFrame,
    cost_metrics: pd.DataFrame,
    run_report: pd.DataFrame,
    manifest: pd.DataFrame,
    statuses: list[str],
) -> tuple[pd.DataFrame, list[dict[str, object]]]:
    """Reconcile attempted workbooks with manifest business metadata."""
    # Accumulate one mapping row per report record and local reconciliation issues.
    mapping_rows: list[dict[str, object]] = []
    issues: list[dict[str, object]] = []

    # Preserve run-report order so notebook output matches the attempted run.
    for position in range(len(run_report)):
        report_row = run_report.iloc[position]
        source_workbook = report_row["source_workbook"]
        extraction_status = statuses[position]
        run_period = (
            pd.NA
            if _is_blank(report_row["reporting_period"])
            else _display_text(report_row["reporting_period"])
        )

        # Initialize unresolved metadata fields before applying match rules.
        extracted_period: object = pd.NA
        manifest_local_filename: object = pd.NA
        resolved_business: object = pd.NA
        manifest_period: object = pd.NA
        landing_page_url: object = pd.NA
        source_page_url: object = pd.NA
        metadata_status = "extraction_failed"

        # Failed workbooks have no canonical rows to enrich in this stage.
        if extraction_status == "failed":
            mapping_rows.append(
                {
                    "source_workbook": source_workbook,
                    "extraction_status": extraction_status,
                    "run_report_reporting_period": run_period,
                    "extracted_reporting_period": extracted_period,
                    "manifest_local_filename": manifest_local_filename,
                    "business": resolved_business,
                    "manifest_reporting_period": manifest_period,
                    "landing_page_url": landing_page_url,
                    "source_page_url": source_page_url,
                    "metadata_match_status": metadata_status,
                }
            )
            continue

        # Reconcile period evidence across descriptor, cost, and run-report data.
        extracted_period, extracted_periods, has_blank_period = _period_evidence(
            source_workbook,
            descriptor_metrics,
            cost_metrics,
        )
        run_period_conflicts = (
            _is_blank(run_period)
            or has_blank_period
            or len(extracted_periods) != 1
            or _display_text(extracted_period) != _display_text(run_period)
        )
        if run_period_conflicts:
            metadata_status = "reporting_period_conflict"
            period_details = ", ".join(sorted(extracted_periods)) or "none"
            issues.append(
                _issue(
                    table_name="workbook_mapping",
                    source_workbook=source_workbook,
                    issue_code=metadata_status,
                    message=(
                        "Descriptor/cost period evidence "
                        f"({period_details}) does not agree with run-report "
                        f"period {_display_text(run_period) or 'none'}."
                    ),
                )
            )
        else:
            # Match the canonical workbook to one exact local manifest filename.
            matches = manifest.loc[
                manifest["local_filename"].eq(source_workbook)
            ]

            if matches.empty:
                # Preserve a factual zero-match result for notebook review.
                metadata_status = "manifest_local_filename_no_match"
                issues.append(
                    _issue(
                        table_name="workbook_mapping",
                        source_workbook=source_workbook,
                        issue_code=metadata_status,
                        message=(
                            "No manifest local_filename exactly matched the "
                            "canonical source_workbook."
                        ),
                    )
                )
            else:
                # Read the unique authoritative record after inventory validation.
                manifest_row = matches.iloc[0]
                manifest_local_filename = manifest_row["local_filename"]
                resolved_business = manifest_row["business"]
                manifest_period = manifest_row["reporting_period"]
                landing_page_url = manifest_row["landing_page_url"]
                source_page_url = manifest_row["source_page_url"]

                # Require the canonical period to agree with acquisition metadata.
                if _display_text(manifest_period) != _display_text(
                    extracted_period
                ):
                    metadata_status = "manifest_reporting_period_conflict"
                    resolved_business = pd.NA
                    landing_page_url = pd.NA
                    source_page_url = pd.NA
                    issues.append(
                        _issue(
                            table_name="workbook_mapping",
                            source_workbook=source_workbook,
                            issue_code=metadata_status,
                            message=(
                                "The exact manifest filename matched, but its "
                                "reporting period does not agree with the "
                                "canonical extraction."
                            ),
                        )
                    )
                elif _is_blank(resolved_business):
                    # Require manifest identity rather than guessing from filenames.
                    metadata_status = "manifest_business_missing"
                    resolved_business = pd.NA
                    landing_page_url = pd.NA
                    source_page_url = pd.NA
                    issues.append(
                        _issue(
                            table_name="workbook_mapping",
                            source_workbook=source_workbook,
                            issue_code=metadata_status,
                            message=(
                                "The exact manifest record has no business "
                                "identity."
                            ),
                        )
                    )
                elif _is_blank(landing_page_url) or _is_blank(source_page_url):
                    # Require both AER URLs before declaring reconciliation complete.
                    metadata_status = "manifest_metadata_missing"
                    landing_page_url = (
                        pd.NA
                        if _is_blank(landing_page_url)
                        else landing_page_url
                    )
                    source_page_url = (
                        pd.NA
                        if _is_blank(source_page_url)
                        else source_page_url
                    )
                    issues.append(
                        _issue(
                            table_name="workbook_mapping",
                            source_workbook=source_workbook,
                            issue_code=metadata_status,
                            message=(
                                "The matched manifest record is missing an "
                                "AER landing-page or source-page URL."
                            ),
                        )
                    )
                else:
                    # Mark the exact filename and period reconciliation as valid.
                    metadata_status = "validated_manifest_match"

        # Record every resolved and unresolved field in a stable mapping schema.
        mapping_rows.append(
            {
                "source_workbook": source_workbook,
                "extraction_status": extraction_status,
                "run_report_reporting_period": run_period,
                "extracted_reporting_period": extracted_period,
                "manifest_local_filename": manifest_local_filename,
                "business": resolved_business,
                "manifest_reporting_period": manifest_period,
                "landing_page_url": landing_page_url,
                "source_page_url": source_page_url,
                "metadata_match_status": metadata_status,
            }
        )

    # Fix column order when a partial run also contains failed workbooks.
    mapping = pd.DataFrame(mapping_rows, columns=WORKBOOK_MAPPING_COLUMNS)
    return mapping, issues


def _append_workbook_metadata(
    table: pd.DataFrame,
    workbook_mapping: pd.DataFrame,
) -> pd.DataFrame:
    """Append resolved workbook metadata without mutating canonical columns."""
    # Build exact-filename lookups from the one-row-per-workbook mapping.
    mapping_by_workbook = workbook_mapping.set_index(
        "source_workbook",
        drop=False,
    )

    # Copy deeply so source values, columns, indexes, and caller inputs survive.
    enriched = table.copy(deep=True)

    # Append metadata in the documented order without reordering source rows.
    validated_workbooks = mapping_by_workbook[
        "metadata_match_status"
    ].eq("validated_manifest_match")
    for column in (
        "business",
        "landing_page_url",
        "source_page_url",
        "metadata_match_status",
    ):
        values = enriched["source_workbook"].map(
            mapping_by_workbook[column]
        )

        # Expose authoritative metadata only after the complete match validates.
        if column != "metadata_match_status":
            workbook_is_valid = enriched["source_workbook"].map(
                validated_workbooks
            )
            values = values.where(workbook_is_valid, pd.NA)
        enriched[column] = values.to_numpy()

    return enriched


def _row_has_value(
    table: pd.DataFrame,
    position: int,
    columns: tuple[str, ...],
) -> bool:
    """Return whether one row reports any value in selected columns."""
    # Treat zero as reported while ignoring scalar missing and blank strings.
    return any(
        not _is_blank(table.iloc[position][column])
        for column in columns
    )


def _resolve_activity_groups(
    table: pd.DataFrame,
    table_name: str,
    source_rows: pd.Series,
) -> tuple[pd.DataFrame, list[dict[str, object]]]:
    """Resolve bounded parent activities and classify canonical rows."""
    # Resolve the table-specific child and metric fields from its contract.
    contract = TABLE_CONTRACTS[table_name]
    child_column = contract["child_column"]
    metric_columns = contract["metric_columns"]

    # Allocate positional outputs so duplicate input indexes remain unchanged.
    row_count = len(table)
    resolved_activities: list[object] = [pd.NA] * row_count
    resolution_statuses: list[object] = [pd.NA] * row_count
    anchor_source_rows: list[object] = [pd.NA] * row_count
    row_classifications: list[object] = [pd.NA] * row_count
    anchor_positions: set[int] = set()
    issues: list[dict[str, object]] = []

    # Build a private ordering frame without changing the canonical table.
    order = pd.DataFrame(
        {
            "_position": range(row_count),
            "source_workbook": table["source_workbook"].to_numpy(),
            "source_sheet": table["source_sheet"].to_numpy(),
            "_source_row": source_rows.to_numpy(),
        }
    )
    order = order.sort_values(
        ["source_workbook", "source_sheet", "_source_row"],
        kind="stable",
    )

    # Reset activity context for every independent workbook-sheet group.
    groups = order.groupby(
        ["source_workbook", "source_sheet"],
        sort=False,
        dropna=False,
    )
    for _, group in groups:
        active_parent: object = pd.NA
        active_anchor_row: object = pd.NA
        active_anchor_position: int | None = None
        previous_source_row: int | None = None

        # Walk physical source rows while retaining the explicit parent anchor.
        for position_value, source_row_value in group[
            ["_position", "_source_row"]
        ].itertuples(index=False, name=None):
            position = int(position_value)
            source_row = int(source_row_value)
            activity = table.iloc[position]["maintenance_activity"]
            child_present = not _is_blank(
                table.iloc[position][child_column]
            )
            metric_present = _row_has_value(
                table,
                position,
                metric_columns,
            )
            meaningful_source = child_present or metric_present

            if not _is_blank(activity):
                # Use the exact submitted label as the new explicit group parent.
                resolved_activities[position] = activity
                resolution_statuses[position] = "submitted"
                anchor_source_rows[position] = source_row
                active_parent = activity
                active_anchor_row = source_row
                active_anchor_position = position
            else:
                # Require both a child label and consecutive source-row context.
                consecutive = (
                    previous_source_row is not None
                    and source_row == previous_source_row + 1
                )
                can_continue = (
                    child_present
                    and not _is_blank(active_parent)
                    and consecutive
                )
                if can_continue:
                    # Carry the last explicit parent through consecutive children.
                    resolved_activities[position] = active_parent
                    resolution_statuses[position] = (
                        "continued_group_label"
                    )
                    anchor_source_rows[position] = active_anchor_row
                    if active_anchor_position is not None:
                        anchor_positions.add(active_anchor_position)
                elif meaningful_source:
                    # Preserve meaningful data while reporting unsafe structure.
                    resolution_statuses[position] = "unresolved_missing"
                    issue_code = (
                        "unresolved_parent_row_gap"
                        if (
                            not _is_blank(active_parent)
                            and not consecutive
                        )
                        else "unresolved_parent_no_anchor"
                    )
                    issues.append(
                        _issue(
                            table_name=table_name,
                            source_workbook=table.iloc[position][
                                "source_workbook"
                            ],
                            source_row=source_row,
                            issue_code=issue_code,
                            message=(
                                "A meaningful row has no defensible explicit "
                                "maintenance-activity parent."
                            ),
                        )
                    )

                    # Clear context so later blanks cannot inherit a stale parent.
                    active_parent = pd.NA
                    active_anchor_row = pd.NA
                    active_anchor_position = None
                else:
                    # Treat an otherwise empty blank row as a structural boundary.
                    active_parent = pd.NA
                    active_anchor_row = pd.NA
                    active_anchor_position = None

            # Compare the next row with this physical source position.
            previous_source_row = source_row

    # Classify rows after knowing which activity-only rows anchored children.
    for position in range(row_count):
        child_present = not _is_blank(table.iloc[position][child_column])
        metric_present = _row_has_value(
            table,
            position,
            metric_columns,
        )
        meaningful_source = child_present or metric_present

        if (
            meaningful_source
            and resolution_statuses[position] == "unresolved_missing"
        ):
            row_classifications[position] = "unresolved"
        elif meaningful_source:
            row_classifications[position] = "meaningful"
        elif position in anchor_positions:
            row_classifications[position] = "group_header_only"
        else:
            row_classifications[position] = "empty_template_row"

    # Append derived activity evidence while preserving every source column.
    enriched = table.copy(deep=True)
    enriched["maintenance_activity_resolved"] = resolved_activities
    enriched["activity_resolution_status"] = resolution_statuses
    enriched["activity_anchor_source_row"] = pd.array(
        anchor_source_rows,
        dtype="Int64",
    )
    enriched["row_classification"] = row_classifications
    return enriched, issues


def _build_issues_frame(
    issue_rows: list[dict[str, object]],
) -> pd.DataFrame:
    """Construct the fixed issues schema, including for a clean run."""
    # Preserve the documented column order for notebook inspection and tests.
    issues = pd.DataFrame(issue_rows, columns=ISSUE_COLUMNS)

    # Use a nullable integer so workbook-level issues can omit a source row.
    issues["source_row"] = pd.array(
        issues["source_row"],
        dtype="Int64",
    )
    return issues


def enrich_rin_maintenance(
    descriptor_metrics: pd.DataFrame,
    cost_metrics: pd.DataFrame,
    run_report: pd.DataFrame,
    manifest: pd.DataFrame,
) -> MaintenanceStage2AResult:
    """Enrich canonical RIN maintenance tables for Stage 2 inspection."""
    # Require all public inputs to be DataFrames before reading their columns.
    descriptor_metrics = _require_dataframe(
        "descriptor_metrics",
        descriptor_metrics,
    )
    cost_metrics = _require_dataframe("cost_metrics", cost_metrics)
    run_report = _require_dataframe("run_report", run_report)
    manifest = _require_dataframe("manifest", manifest)

    # Validate the four independent input schemas and derived-column boundary.
    _require_unique_columns("descriptor_metrics", descriptor_metrics)
    _require_unique_columns("cost_metrics", cost_metrics)
    _require_unique_columns("run_report", run_report)
    _require_unique_columns("manifest", manifest)
    _require_columns(
        "descriptor_metrics",
        descriptor_metrics,
        DESCRIPTOR_REQUIRED_COLUMNS,
    )
    _require_columns(
        "cost_metrics",
        cost_metrics,
        COST_REQUIRED_COLUMNS,
    )
    _require_columns(
        "run_report",
        run_report,
        RUN_REPORT_REQUIRED_COLUMNS,
    )
    _require_columns(
        "manifest",
        manifest,
        MANIFEST_REQUIRED_COLUMNS,
    )
    _validate_manifest_inventory(manifest)
    _require_no_enrichment_collisions(
        "descriptor_metrics",
        descriptor_metrics,
    )
    _require_no_enrichment_collisions("cost_metrics", cost_metrics)

    # Validate source coordinates without changing submitted source-row fields.
    descriptor_source_rows = _validated_source_rows(
        "descriptor_metrics",
        descriptor_metrics,
    )
    cost_source_rows = _validated_source_rows(
        "cost_metrics",
        cost_metrics,
    )

    # Validate extraction facts and ensure every input describes the same run.
    statuses, extraction_complete = _validate_run_report(run_report)
    _validate_artifact_inventory(
        descriptor_metrics,
        cost_metrics,
        run_report,
        statuses,
    )

    # Reconcile each attempted workbook with authoritative manifest metadata.
    workbook_mapping, mapping_issues = _build_workbook_mapping(
        descriptor_metrics,
        cost_metrics,
        run_report,
        manifest,
        statuses,
    )

    # Attach metadata before resolving each table's independent row hierarchy.
    descriptor_with_metadata = _append_workbook_metadata(
        descriptor_metrics,
        workbook_mapping,
    )
    cost_with_metadata = _append_workbook_metadata(
        cost_metrics,
        workbook_mapping,
    )
    enriched_descriptor, descriptor_issues = _resolve_activity_groups(
        descriptor_with_metadata,
        "descriptor_metrics",
        descriptor_source_rows,
    )
    enriched_cost, cost_issues = _resolve_activity_groups(
        cost_with_metadata,
        "cost_metrics",
        cost_source_rows,
    )

    # Combine local problems into one fixed, notebook-friendly issues table.
    issues = _build_issues_frame(
        mapping_issues + descriptor_issues + cost_issues
    )

    # Evaluate enrichment only for canonical workbooks, independently of Stage 1.
    successful_mapping = workbook_mapping.loc[
        workbook_mapping["extraction_status"].eq("success")
    ]
    metadata_complete = successful_mapping[
        "metadata_match_status"
    ].eq("validated_manifest_match").all()
    resolution_complete = (
        not enriched_descriptor["row_classification"].eq("unresolved").any()
        and not enriched_cost["row_classification"].eq("unresolved").any()
    )
    stage2a_complete = bool(metadata_complete and resolution_complete)

    # Return new DataFrames and independent completeness flags without I/O.
    return MaintenanceStage2AResult(
        descriptor_metrics=enriched_descriptor,
        cost_metrics=enriched_cost,
        workbook_mapping=workbook_mapping,
        issues=issues,
        extraction_complete=extraction_complete,
        stage2a_complete=stage2a_complete,
    )


def _require_config_list(
    config: dict[str, Any],
    key: str,
) -> list[Any]:
    """Return one required, non-empty configuration list."""
    # Reject absent or empty rule groups before building partial lookups.
    value = config.get(key)
    if not isinstance(value, list) or not value:
        raise MaintenanceStandardizationError(
            f"Standardization config {key} must be a non-empty list."
        )
    return value


def _validate_named_alias_rules(
    rules: list[Any],
    rule_name: str,
) -> None:
    """Validate common identifiers, labels, and aliases in mapping rules."""
    # Track identifiers and normalized aliases so configuration is deterministic.
    identifiers: set[str] = set()
    aliases: set[str] = set()
    for rule in rules:
        if not isinstance(rule, dict):
            raise MaintenanceStandardizationError(
                f"Every {rule_name} rule must be an object."
            )

        # Require stable identifiers, display labels, and at least one alias.
        identifier = rule.get("id")
        label = rule.get("label")
        rule_aliases = rule.get("aliases")
        if (
            not isinstance(identifier, str)
            or not identifier.strip()
            or not isinstance(label, str)
            or not label.strip()
            or not isinstance(rule_aliases, list)
            or not rule_aliases
            or any(
                not isinstance(alias, str) or not alias.strip()
                for alias in rule_aliases
            )
        ):
            raise MaintenanceStandardizationError(
                f"Every {rule_name} rule requires id, label, and aliases."
            )

        # Reject duplicate IDs and aliases that would make a mapping ambiguous.
        if identifier in identifiers:
            raise MaintenanceStandardizationError(
                f"Duplicate {rule_name} id: {identifier}."
            )
        identifiers.add(identifier)
        for alias in rule_aliases:
            normalized_alias = _normalize_match_text(alias)
            if normalized_alias in aliases:
                raise MaintenanceStandardizationError(
                    f"Duplicate {rule_name} alias: {alias}."
                )
            aliases.add(normalized_alias)


def _validate_scaled_alias_rules(
    rules: list[Any],
    rule_name: str,
    alias_key: str,
    required_fields: tuple[str, ...],
) -> None:
    """Validate exact aliases and positive scale factors for unit rules."""
    # Track aliases across rules so one submitted unit has only one conversion.
    aliases: set[str] = set()
    for rule in rules:
        if not isinstance(rule, dict):
            raise MaintenanceStandardizationError(
                f"Every {rule_name} rule must be an object."
            )

        # Require each conversion field and at least one nonblank exact alias.
        rule_aliases = rule.get(alias_key)
        if (
            not isinstance(rule_aliases, list)
            or not rule_aliases
            or any(
                not isinstance(alias, str) or not alias.strip()
                for alias in rule_aliases
            )
            or any(
                not isinstance(rule.get(field), str)
                or not rule[field].strip()
                for field in required_fields
            )
        ):
            raise MaintenanceStandardizationError(
                f"Every {rule_name} rule has an invalid contract."
            )

        # Require a finite, positive numeric scale to prevent sign mistakes.
        try:
            scale_factor = Decimal(str(rule.get("scale_factor")))
        except InvalidOperation:
            raise MaintenanceStandardizationError(
                f"Every {rule_name} scale_factor must be positive."
            ) from None
        if not scale_factor.is_finite() or scale_factor <= 0:
            raise MaintenanceStandardizationError(
                f"Every {rule_name} scale_factor must be positive."
            )

        # Reject normalized aliases assigned to more than one conversion rule.
        for alias in rule_aliases:
            normalized_alias = _normalize_match_text(alias)
            if normalized_alias in aliases:
                raise MaintenanceStandardizationError(
                    f"Duplicate {rule_name} alias: {alias}."
                )
            aliases.add(normalized_alias)


def load_standardization_config(
    config_path: str | Path,
) -> dict[str, Any]:
    """Load and validate the Stage 2B semantic standardisation rules."""
    # Resolve and read the JSON file on every call for notebook iteration.
    path = Path(config_path)
    try:
        with path.open("r", encoding="utf-8") as config_file:
            config = json.load(config_file)
    except (OSError, json.JSONDecodeError) as exc:
        raise MaintenanceStandardizationError(
            f"Could not load standardization config {path}: {exc}."
        ) from exc

    # Require the supported schema and every top-level semantic rule group.
    if not isinstance(config, dict) or config.get("schema_version") != 1:
        raise MaintenanceStandardizationError(
            "Standardization config must use schema_version 1."
        )
    target_businesses = _require_config_list(config, "target_businesses")
    required_periods = _require_config_list(
        config,
        "required_reporting_periods",
    )
    parent_rules = _require_config_list(config, "parent_categories")
    category_rules = _require_config_list(
        config,
        "contextual_category_aliases",
    )
    quantity_rules = _require_config_list(
        config,
        "descriptor_quantity_units",
    )
    fallback_rules = _require_config_list(
        config,
        "missing_unit_measure_fallbacks",
    )
    currency_rules = _require_config_list(config, "cost_currency_units")
    special_rules = _require_config_list(
        config,
        "recognized_special_metric_text",
    )

    # Require unique, nonblank panel dimensions before coverage evaluation.
    for key, values in (
        ("target_businesses", target_businesses),
        ("required_reporting_periods", required_periods),
    ):
        if (
            any(not isinstance(value, str) or not value.strip() for value in values)
            or len({_normalize_match_text(value) for value in values})
            != len(values)
        ):
            raise MaintenanceStandardizationError(
                f"Standardization config {key} must contain unique strings."
            )

    # Validate the parent vocabulary and build its referenced identifier set.
    _validate_named_alias_rules(parent_rules, "parent category")
    parent_ids = {rule["id"] for rule in parent_rules}

    # Validate contextual child aliases independently by table and parent.
    contextual_aliases: set[tuple[str, str, str]] = set()
    valid_tables = {"descriptor_metrics", "cost_metrics"}
    for rule in category_rules:
        if not isinstance(rule, dict):
            raise MaintenanceStandardizationError(
                "Every contextual category rule must be an object."
            )

        # Require the contextual table, parent, child ID, label, and aliases.
        tables = rule.get("tables")
        aliases = rule.get("aliases")
        parent_id = rule.get("parent_id")
        if (
            not isinstance(tables, list)
            or not tables
            or any(table not in valid_tables for table in tables)
            or parent_id not in parent_ids
            or not isinstance(rule.get("id"), str)
            or not rule["id"].strip()
            or not isinstance(rule.get("label"), str)
            or not rule["label"].strip()
            or not isinstance(aliases, list)
            or not aliases
            or any(
                not isinstance(alias, str) or not alias.strip()
                for alias in aliases
            )
        ):
            raise MaintenanceStandardizationError(
                "Every contextual category rule has an invalid contract."
            )

        # Reject aliases that map one context to multiple standard children.
        for table_name in tables:
            for alias in aliases:
                key = (
                    table_name,
                    parent_id,
                    _normalize_match_text(alias),
                )
                if key in contextual_aliases:
                    raise MaintenanceStandardizationError(
                        "A contextual category alias is defined more than once: "
                        f"{table_name}, {parent_id}, {alias}."
                    )
                contextual_aliases.add(key)

    # Validate quantity, fallback, and currency scale-factor vocabularies.
    _validate_scaled_alias_rules(
        quantity_rules,
        "descriptor quantity unit",
        "aliases",
        ("standard_unit",),
    )
    _validate_scaled_alias_rules(
        fallback_rules,
        "missing-unit measure fallback",
        "measure_aliases",
        ("standard_unit",),
    )
    _validate_scaled_alias_rules(
        currency_rules,
        "cost currency unit",
        "aliases",
        ("currency", "price_basis"),
    )

    # Require recognized special text to target known descriptor metrics.
    special_keys: set[tuple[str, str]] = set()
    for rule in special_rules:
        aliases = rule.get("aliases") if isinstance(rule, dict) else None
        metric = rule.get("metric") if isinstance(rule, dict) else None
        if (
            metric not in DESCRIPTOR_METRIC_COLUMNS
            or not isinstance(aliases, list)
            or not aliases
            or any(
                not isinstance(alias, str) or not alias.strip()
                for alias in aliases
            )
        ):
            raise MaintenanceStandardizationError(
                "Every recognized special metric rule has an invalid contract."
            )
        for alias in aliases:
            key = (metric, _normalize_match_text(alias))
            if key in special_keys:
                raise MaintenanceStandardizationError(
                    "A recognized special metric alias is duplicated."
                )
            special_keys.add(key)

    return config


def _source_identifier(prefix: str, *values: object) -> str:
    """Create a deterministic identifier for a retained source category."""
    # Join normalized semantic components before replacing punctuation.
    normalized = "__".join(
        _normalize_match_text(value) or "missing"
        for value in values
    )

    # Retain letters and digits while making punctuation deterministic.
    slug = re.sub(r"[^\w]+", "_", normalized, flags=re.UNICODE).strip("_")
    return f"{prefix}__{slug or 'missing'}"


def _stage2b_issue(
    *,
    severity: str,
    table_name: str,
    source_workbook: object,
    source_row: object,
    issue_code: str,
    message: str,
) -> dict[str, object]:
    """Construct one fixed-schema Stage 2B issue record."""
    # Include the stage explicitly so combined issues remain attributable.
    return {
        "stage": "2B",
        "severity": severity,
        "table_name": table_name,
        "source_workbook": source_workbook,
        "source_row": source_row,
        "issue_code": issue_code,
        "message": message,
    }


def _build_category_lookups(
    config: dict[str, Any],
) -> tuple[
    dict[str, dict[str, str]],
    dict[tuple[str, str, str], dict[str, str]],
]:
    """Build exact normalized parent and contextual child lookups."""
    # Map every approved parent alias to its stable identifier and label.
    parent_lookup: dict[str, dict[str, str]] = {}
    for rule in config["parent_categories"]:
        for alias in rule["aliases"]:
            parent_lookup[_normalize_match_text(alias)] = {
                "id": rule["id"],
                "label": rule["label"],
            }

    # Map every approved child alias within its table and resolved parent.
    child_lookup: dict[tuple[str, str, str], dict[str, str]] = {}
    for rule in config["contextual_category_aliases"]:
        for table_name in rule["tables"]:
            for alias in rule["aliases"]:
                child_lookup[
                    (
                        table_name,
                        rule["parent_id"],
                        _normalize_match_text(alias),
                    )
                ] = {
                    "id": rule["id"],
                    "label": rule["label"],
                }
    return parent_lookup, child_lookup


def _standardize_categories(
    table: pd.DataFrame,
    table_name: str,
    child_column: str,
    config: dict[str, Any],
    issue_rows: list[dict[str, object]],
) -> pd.DataFrame:
    """Append contextual category identifiers without changing source labels."""
    # Build rule lookups once for all rows in this table.
    parent_lookup, child_lookup = _build_category_lookups(config)
    standardized = table.copy(deep=True)

    # Accumulate derived values positionally to preserve duplicate user indexes.
    analytic_flags: list[bool] = []
    activity_ids: list[object] = []
    activity_labels: list[object] = []
    asset_ids: list[object] = []
    asset_labels: list[object] = []
    activity_statuses: list[str] = []
    asset_statuses: list[str] = []

    # Standardize only analytically meaningful rows while retaining every row.
    for position in range(len(table)):
        row = table.iloc[position]
        analytic = row["row_classification"] == "meaningful"
        analytic_flags.append(bool(analytic))
        parent_source = row["maintenance_activity_resolved"]
        child_source = row[child_column]

        if not analytic:
            # Keep presentation-only rows visible without inventing categories.
            activity_ids.append(pd.NA)
            activity_labels.append(pd.NA)
            asset_ids.append(pd.NA)
            asset_labels.append(pd.NA)
            activity_statuses.append("not_applicable")
            asset_statuses.append("not_applicable")
            continue

        if _is_blank(parent_source) or _is_blank(child_source):
            # Block an analytic category when either required hierarchy level is absent.
            activity_ids.append(pd.NA)
            activity_labels.append(pd.NA)
            asset_ids.append(pd.NA)
            asset_labels.append(pd.NA)
            activity_statuses.append("unresolved_missing")
            asset_statuses.append("unresolved_missing")
            issue_rows.append(
                _stage2b_issue(
                    severity="error",
                    table_name=table_name,
                    source_workbook=row["source_workbook"],
                    source_row=row["source_row"],
                    issue_code="unresolved_category_hierarchy",
                    message=(
                        "A meaningful row is missing a resolved parent or "
                        "child category."
                    ),
                )
            )
            continue

        # Resolve the parent through explicit aliases or retain its source identity.
        parent_match = parent_lookup.get(
            _normalize_match_text(parent_source)
        )
        if parent_match is None:
            parent_id = _source_identifier(
                "source_activity",
                parent_source,
            )
            parent_label = _display_text(parent_source)
            parent_status = "retained_source_category"
            issue_rows.append(
                _stage2b_issue(
                    severity="warning",
                    table_name=table_name,
                    source_workbook=row["source_workbook"],
                    source_row=row["source_row"],
                    issue_code="retained_source_activity",
                    message=(
                        "The submitted maintenance activity was retained with "
                        "a deterministic source-derived identifier."
                    ),
                )
            )
        else:
            parent_id = parent_match["id"]
            parent_label = parent_match["label"]
            parent_status = "mapped"

        # Resolve the child only within its table and standard parent context.
        child_match = child_lookup.get(
            (
                table_name,
                parent_id,
                _normalize_match_text(child_source),
            )
        )
        if child_match is None:
            child_id = _source_identifier(
                "source_asset",
                parent_id,
                child_source,
            )
            child_label = _display_text(child_source)
            child_status = "retained_source_category"
            issue_rows.append(
                _stage2b_issue(
                    severity="warning",
                    table_name=table_name,
                    source_workbook=row["source_workbook"],
                    source_row=row["source_row"],
                    issue_code="retained_source_asset_category",
                    message=(
                        "The submitted asset category was retained with a "
                        "deterministic source-derived identifier."
                    ),
                )
            )
        else:
            child_id = child_match["id"]
            child_label = child_match["label"]
            child_status = "mapped"

        # Store stable identifiers alongside readable labels and mapping evidence.
        activity_ids.append(parent_id)
        activity_labels.append(parent_label)
        asset_ids.append(child_id)
        asset_labels.append(child_label)
        activity_statuses.append(parent_status)
        asset_statuses.append(child_status)

    # Append the category fields in their documented order.
    standardized["analytic_row_eligible"] = analytic_flags
    standardized["maintenance_activity_standard_id"] = activity_ids
    standardized["maintenance_activity_standard"] = activity_labels
    standardized["maintenance_asset_standard_id"] = asset_ids
    standardized["maintenance_asset_standard"] = asset_labels
    standardized["activity_mapping_status"] = activity_statuses
    standardized["asset_mapping_status"] = asset_statuses
    return standardized


def _parse_standard_numeric(
    value: object,
    special_aliases: set[str],
) -> tuple[object, str]:
    """Parse one submitted metric without treating blanks or text as zero."""
    # Preserve factual blanks before inspecting textual special values.
    if _is_blank(value):
        return pd.NA, "blank"

    # Recognize explicitly configured semantic text before numeric parsing.
    if _normalize_match_text(value) in special_aliases:
        return pd.NA, "recognized_special"

    # Reject booleans even though Python treats them as integers.
    if isinstance(value, bool) or type(value).__name__ == "bool_":
        return pd.NA, "invalid_numeric"

    # Accept ordinary numbers and conservative comma or parenthesis notation.
    numeric_text = _display_text(value).replace(",", "")
    if numeric_text.startswith("(") and numeric_text.endswith(")"):
        numeric_text = f"-{numeric_text[1:-1]}"
    try:
        numeric = Decimal(numeric_text)
    except InvalidOperation:
        return pd.NA, "invalid_numeric"
    if not numeric.is_finite():
        return pd.NA, "invalid_numeric"
    return float(numeric), "numeric"


def _build_scaled_lookup(
    rules: list[dict[str, Any]],
    alias_key: str,
) -> dict[str, dict[str, Any]]:
    """Build an exact normalized lookup for configured scale rules."""
    # Expand aliases while retaining each rule's semantic conversion fields.
    lookup: dict[str, dict[str, Any]] = {}
    for rule in rules:
        for alias in rule[alias_key]:
            lookup[_normalize_match_text(alias)] = rule
    return lookup


def _build_special_lookup(
    config: dict[str, Any],
) -> dict[str, set[str]]:
    """Group recognized special text by its descriptor metric."""
    # Initialize every descriptor metric so callers need no missing-key branch.
    lookup = {metric: set() for metric in DESCRIPTOR_METRIC_COLUMNS}
    for rule in config["recognized_special_metric_text"]:
        lookup[rule["metric"]].update(
            _normalize_match_text(alias)
            for alias in rule["aliases"]
        )
    return lookup


def _standardize_descriptor_metrics(
    table: pd.DataFrame,
    config: dict[str, Any],
    issue_rows: list[dict[str, object]],
) -> pd.DataFrame:
    """Standardize descriptor categories, units, and numeric values."""
    # Standardize parent-child categories before applying row-level unit rules.
    standardized = _standardize_categories(
        table,
        "descriptor_metrics",
        "maintenance_asset_category",
        config,
        issue_rows,
    )
    unit_lookup = _build_scaled_lookup(
        config["descriptor_quantity_units"],
        "aliases",
    )
    fallback_lookup = _build_scaled_lookup(
        config["missing_unit_measure_fallbacks"],
        "measure_aliases",
    )
    special_lookup = _build_special_lookup(config)

    # Parse every metric first so unit requirements can use factual quantity data.
    parsed_values: dict[str, list[object]] = {
        metric: [] for metric in DESCRIPTOR_METRIC_COLUMNS
    }
    parsed_statuses: dict[str, list[str]] = {
        metric: [] for metric in DESCRIPTOR_METRIC_COLUMNS
    }
    for position in range(len(standardized)):
        row = standardized.iloc[position]
        for metric in DESCRIPTOR_METRIC_COLUMNS:
            value, status = _parse_standard_numeric(
                row[metric],
                special_lookup[metric],
            )
            parsed_values[metric].append(value)
            parsed_statuses[metric].append(status)

            # Report invalid analytic values without suppressing the source row.
            if (
                row["analytic_row_eligible"]
                and status == "invalid_numeric"
            ):
                issue_rows.append(
                    _stage2b_issue(
                        severity="error",
                        table_name="descriptor_metrics",
                        source_workbook=row["source_workbook"],
                        source_row=row["source_row"],
                        issue_code="invalid_numeric_value",
                        message=(
                            f"{metric} contains unrecognized numeric text: "
                            f"{_display_text(row[metric])}."
                        ),
                    )
                )

    # Resolve one shared quantity unit for installed and serviced quantities.
    quantity_units: list[object] = []
    quantity_scales: list[object] = []
    quantity_unit_statuses: list[str] = []
    for position in range(len(standardized)):
        row = standardized.iloc[position]
        analytic = bool(row["analytic_row_eligible"])
        quantity_reported = any(
            parsed_statuses[metric][position] != "blank"
            for metric in (
                "asset_quantity_at_year_end",
                "quantity_inspected_maintained",
            )
        )
        source_unit_key = _normalize_match_text(row["source_unit"])
        measure_key = _normalize_match_text(row["measure_asset_quantity"])
        source_rule = unit_lookup.get(source_unit_key)
        fallback_rule = fallback_lookup.get(measure_key)

        if not analytic:
            # Presentation-only rows do not require a quantity conversion.
            quantity_units.append(pd.NA)
            quantity_scales.append(pd.NA)
            quantity_unit_statuses.append("not_applicable")
        elif source_rule is not None:
            # Detect contradictory dimensions while trusting a submitted scale.
            dimension_conflict = (
                fallback_rule is not None
                and source_rule["standard_unit"]
                != fallback_rule["standard_unit"]
            )
            if dimension_conflict:
                quantity_units.append(pd.NA)
                quantity_scales.append(pd.NA)
                quantity_unit_statuses.append("conflicting_unit")
                issue_rows.append(
                    _stage2b_issue(
                        severity="error",
                        table_name="descriptor_metrics",
                        source_workbook=row["source_workbook"],
                        source_row=row["source_row"],
                        issue_code="conflicting_quantity_unit",
                        message=(
                            "The submitted quantity unit and exact measure "
                            "label imply different standard dimensions."
                        ),
                    )
                )
            else:
                quantity_units.append(source_rule["standard_unit"])
                quantity_scales.append(float(source_rule["scale_factor"]))
                quantity_unit_statuses.append("standardized_source_unit")
        elif not source_unit_key and fallback_rule is not None:
            # Infer a missing unit only from an exact configured measure label.
            quantity_units.append(fallback_rule["standard_unit"])
            quantity_scales.append(float(fallback_rule["scale_factor"]))
            quantity_unit_statuses.append("inferred_from_measure")
        elif not quantity_reported:
            # A wholly blank denominator does not need a conversion.
            quantity_units.append(pd.NA)
            quantity_scales.append(pd.NA)
            quantity_unit_statuses.append("not_required")
        else:
            # Preserve unknown or missing unit evidence and block standardisation.
            quantity_units.append(pd.NA)
            quantity_scales.append(pd.NA)
            status = (
                "missing_unit"
                if not source_unit_key
                else "unrecognized_unit"
            )
            quantity_unit_statuses.append(status)
            issue_rows.append(
                _stage2b_issue(
                    severity="error",
                    table_name="descriptor_metrics",
                    source_workbook=row["source_workbook"],
                    source_row=row["source_row"],
                    issue_code=status,
                    message=(
                        "A reported descriptor quantity has no recognized "
                        "source unit or exact measure-label fallback."
                    ),
                )
            )

    # Append unit evidence before producing standardized numeric columns.
    standardized["quantity_unit_standard"] = quantity_units
    standardized["quantity_scale_factor"] = pd.array(
        quantity_scales,
        dtype="Float64",
    )
    standardized["quantity_unit_status"] = quantity_unit_statuses

    # Scale quantity metrics only when their submitted value and unit are valid.
    for metric in (
        "asset_quantity_at_year_end",
        "quantity_inspected_maintained",
    ):
        standard_values: list[object] = []
        for position, value in enumerate(parsed_values[metric]):
            scale = quantity_scales[position]
            standard_values.append(
                value * scale
                if (
                    parsed_statuses[metric][position] == "numeric"
                    and not _is_blank(scale)
                )
                else pd.NA
            )
        standardized[f"{metric}_standard"] = pd.array(
            standard_values,
            dtype="Float64",
        )
        standardized[f"{metric}_status"] = parsed_statuses[metric]

    # Preserve year-based metrics numerically without a quantity scale factor.
    for metric in (
        "average_age_of_asset_group",
        "inspection_cycle_years",
        "maintenance_cycle_years",
    ):
        standardized[f"{metric}_standard"] = pd.array(
            parsed_values[metric],
            dtype="Float64",
        )
        standardized[f"{metric}_status"] = parsed_statuses[metric]
    return standardized


def _standardize_cost_metrics(
    table: pd.DataFrame,
    config: dict[str, Any],
    issue_rows: list[dict[str, object]],
) -> pd.DataFrame:
    """Standardize cost categories, nominal currency, and numeric values."""
    # Standardize parent-child categories before applying currency conversions.
    standardized = _standardize_categories(
        table,
        "cost_metrics",
        "maintenance_asset_subcategory",
        config,
        issue_rows,
    )
    currency_lookup = _build_scaled_lookup(
        config["cost_currency_units"],
        "aliases",
    )

    # Parse both submitted cost components independently.
    component_values: dict[str, list[object]] = {
        metric: [] for metric in COST_METRIC_COLUMNS
    }
    component_statuses: dict[str, list[str]] = {
        metric: [] for metric in COST_METRIC_COLUMNS
    }
    for position in range(len(standardized)):
        row = standardized.iloc[position]
        for metric in COST_METRIC_COLUMNS:
            value, status = _parse_standard_numeric(row[metric], set())
            component_values[metric].append(value)
            component_statuses[metric].append(status)

            # Report invalid analytic expenditure without coercing it to zero.
            if (
                row["analytic_row_eligible"]
                and status == "invalid_numeric"
            ):
                issue_rows.append(
                    _stage2b_issue(
                        severity="error",
                        table_name="cost_metrics",
                        source_workbook=row["source_workbook"],
                        source_row=row["source_row"],
                        issue_code="invalid_numeric_value",
                        message=(
                            f"{metric} contains unrecognized numeric text: "
                            f"{_display_text(row[metric])}."
                        ),
                    )
                )

    # Resolve one nominal-AUD conversion for both expenditure components.
    currencies: list[object] = []
    price_bases: list[object] = []
    currency_scales: list[object] = []
    currency_statuses: list[str] = []
    for position in range(len(standardized)):
        row = standardized.iloc[position]
        analytic = bool(row["analytic_row_eligible"])
        currency_rule = currency_lookup.get(
            _normalize_match_text(row["source_currency_unit"])
        )
        costs_reported = any(
            component_statuses[metric][position] != "blank"
            for metric in COST_METRIC_COLUMNS
        )

        if not analytic:
            # Presentation-only rows do not require a currency conversion.
            currencies.append(pd.NA)
            price_bases.append(pd.NA)
            currency_scales.append(pd.NA)
            currency_statuses.append("not_applicable")
        elif currency_rule is not None:
            # Apply the configured nominal currency and explicit scale factor.
            currencies.append(currency_rule["currency"])
            price_bases.append(currency_rule["price_basis"])
            currency_scales.append(float(currency_rule["scale_factor"]))
            currency_statuses.append("standardized_source_unit")
        elif not costs_reported:
            # A wholly blank cost row retains its category without needing scale.
            currencies.append(pd.NA)
            price_bases.append(pd.NA)
            currency_scales.append(pd.NA)
            currency_statuses.append("not_required")
        else:
            # Preserve the unknown currency source and block standardisation.
            currencies.append(pd.NA)
            price_bases.append(pd.NA)
            currency_scales.append(pd.NA)
            status = (
                "missing_unit"
                if _is_blank(row["source_currency_unit"])
                else "unrecognized_unit"
            )
            currency_statuses.append(status)
            issue_rows.append(
                _stage2b_issue(
                    severity="error",
                    table_name="cost_metrics",
                    source_workbook=row["source_workbook"],
                    source_row=row["source_row"],
                    issue_code=status,
                    message=(
                        "Reported expenditure has no recognized nominal-AUD "
                        "source currency unit."
                    ),
                )
            )

    # Append currency evidence before calculating standardized components.
    standardized["currency_standard"] = currencies
    standardized["price_basis"] = price_bases
    standardized["currency_scale_factor"] = pd.array(
        currency_scales,
        dtype="Float64",
    )
    standardized["currency_unit_status"] = currency_statuses

    # Scale each component only when both value and currency are valid.
    for metric in COST_METRIC_COLUMNS:
        standard_values: list[object] = []
        for position, value in enumerate(component_values[metric]):
            scale = currency_scales[position]
            standard_values.append(
                value * scale
                if (
                    component_statuses[metric][position] == "numeric"
                    and not _is_blank(scale)
                )
                else pd.NA
            )
        standardized[f"{metric}_standard"] = pd.array(
            standard_values,
            dtype="Float64",
        )
        standardized[f"{metric}_status"] = component_statuses[metric]

    # Calculate totals only when both source components are numeric and scaled.
    total_values: list[object] = []
    total_statuses: list[str] = []
    for position in range(len(standardized)):
        routine_status = component_statuses[
            "routine_maintenance_expenditure"
        ][position]
        non_routine_status = component_statuses[
            "non_routine_maintenance_expenditure"
        ][position]
        routine_value = standardized.iloc[position][
            "routine_maintenance_expenditure_standard"
        ]
        non_routine_value = standardized.iloc[position][
            "non_routine_maintenance_expenditure_standard"
        ]
        if routine_status == "numeric" and non_routine_status == "numeric":
            if _is_blank(routine_value) or _is_blank(non_routine_value):
                total_values.append(pd.NA)
                total_statuses.append("unstandardized_currency")
            else:
                total_values.append(routine_value + non_routine_value)
                total_statuses.append("numeric")
        elif routine_status == "blank" and non_routine_status == "blank":
            total_values.append(pd.NA)
            total_statuses.append("blank")
        elif (
            routine_status == "invalid_numeric"
            or non_routine_status == "invalid_numeric"
        ):
            total_values.append(pd.NA)
            total_statuses.append("invalid_numeric")
        else:
            total_values.append(pd.NA)
            total_statuses.append("incomplete_components")

    # Append the derived total separately from submitted components.
    standardized["total_maintenance_expenditure_standard"] = pd.array(
        total_values,
        dtype="Float64",
    )
    standardized["total_maintenance_expenditure_status"] = total_statuses
    return standardized


def _relationship_key(row: pd.Series) -> tuple[object, ...]:
    """Return the documented cost-to-descriptor relationship key."""
    # Use resolved business, period, parent ID, and contextual child ID.
    return (
        row["business"],
        row["reporting_period"],
        row["maintenance_activity_standard_id"],
        row["maintenance_asset_standard_id"],
    )


def _ratio_values(
    relationship_status: str,
    denominator: object,
    denominator_value_status: object,
    denominator_unit: object,
    currency_status: object,
    routine_value: object,
    routine_status: object,
    non_routine_value: object,
    non_routine_status: object,
    total_value: object,
    total_status: object,
) -> tuple[object, object, object, str]:
    """Calculate one denominator family's ratios and factual status."""
    # Stop before arithmetic when the descriptor relationship is not unique.
    if relationship_status == "no_descriptor_match":
        return pd.NA, pd.NA, pd.NA, "no_descriptor_match"
    if relationship_status == "ambiguous_match":
        return pd.NA, pd.NA, pd.NA, "ambiguous_match"

    # Require a standardized, positive descriptor denominator.
    if denominator_value_status != "numeric" or _is_blank(denominator):
        return pd.NA, pd.NA, pd.NA, "missing_denominator"
    if _is_blank(denominator_unit):
        return pd.NA, pd.NA, pd.NA, "unstandardized_denominator"
    if denominator <= 0:
        return pd.NA, pd.NA, pd.NA, "nonpositive_denominator"

    # Require a recognized cost currency before calculating any ratio.
    if currency_status != "standardized_source_unit":
        return pd.NA, pd.NA, pd.NA, "unstandardized_currency"

    # Calculate each component only when its submitted numerator is numeric.
    routine_ratio = (
        routine_value / denominator
        if routine_status == "numeric" and not _is_blank(routine_value)
        else pd.NA
    )
    non_routine_ratio = (
        non_routine_value / denominator
        if (
            non_routine_status == "numeric"
            and not _is_blank(non_routine_value)
        )
        else pd.NA
    )
    total_ratio = (
        total_value / denominator
        if total_status == "numeric" and not _is_blank(total_value)
        else pd.NA
    )

    # Summarize whether every component ratio or only a subset was calculable.
    if total_status == "numeric":
        ratio_status = "calculated"
    elif (
        routine_status == "invalid_numeric"
        or non_routine_status == "invalid_numeric"
    ):
        ratio_status = "invalid_numerator"
    elif routine_status == "blank" and non_routine_status == "blank":
        ratio_status = "missing_numerators"
    else:
        ratio_status = "incomplete_cost_components"
    return routine_ratio, non_routine_ratio, total_ratio, ratio_status


def _build_cost_descriptor_relationships(
    descriptor: pd.DataFrame,
    cost: pd.DataFrame,
    issue_rows: list[dict[str, object]],
) -> pd.DataFrame:
    """Relate meaningful costs to unique descriptors and calculate ratios."""
    # Restrict relationship work to rows eligible for analysis.
    descriptor_rows = descriptor.loc[
        descriptor["analytic_row_eligible"]
    ]
    relationships = cost.loc[
        cost["analytic_row_eligible"]
    ].copy(deep=True)

    # Group descriptor positions before any join to expose duplicate keys.
    descriptor_positions: dict[tuple[object, ...], list[int]] = {}
    for position in range(len(descriptor_rows)):
        row = descriptor_rows.iloc[position]
        descriptor_positions.setdefault(_relationship_key(row), []).append(
            position
        )

    # Report every duplicated descriptor source row as an ambiguous key.
    for positions in descriptor_positions.values():
        if len(positions) <= 1:
            continue
        for position in positions:
            row = descriptor_rows.iloc[position]
            issue_rows.append(
                _stage2b_issue(
                    severity="error",
                    table_name="descriptor_metrics",
                    source_workbook=row["source_workbook"],
                    source_row=row["source_row"],
                    issue_code="duplicate_relationship_key",
                    message=(
                        "Multiple meaningful descriptor rows share the same "
                        "business, period, activity, and asset-category key."
                    ),
                )
            )

    # Allocate descriptor evidence, relationship classifications, and ratios.
    relationship_statuses: list[str] = []
    descriptor_workbooks: list[object] = []
    descriptor_sheets: list[object] = []
    descriptor_source_rows: list[object] = []
    denominator_units: list[object] = []
    installed_values: list[object] = []
    installed_value_statuses: list[object] = []
    serviced_values: list[object] = []
    serviced_value_statuses: list[object] = []
    installed_ratio_units: list[object] = []
    serviced_ratio_units: list[object] = []
    installed_ratio_statuses: list[str] = []
    serviced_ratio_statuses: list[str] = []
    routine_installed_ratios: list[object] = []
    non_routine_installed_ratios: list[object] = []
    total_installed_ratios: list[object] = []
    routine_serviced_ratios: list[object] = []
    non_routine_serviced_ratios: list[object] = []
    total_serviced_ratios: list[object] = []

    # Resolve one descriptor match for each cost row without multiplying rows.
    for position in range(len(relationships)):
        cost_row = relationships.iloc[position]
        matches = descriptor_positions.get(_relationship_key(cost_row), [])
        descriptor_row: pd.Series | None = None
        if not matches:
            relationship_status = "no_descriptor_match"
        elif len(matches) > 1:
            relationship_status = "ambiguous_match"
            issue_rows.append(
                _stage2b_issue(
                    severity="error",
                    table_name="cost_descriptor_relationships",
                    source_workbook=cost_row["source_workbook"],
                    source_row=cost_row["source_row"],
                    issue_code="ambiguous_descriptor_match",
                    message=(
                        "The cost relationship key matches multiple "
                        "descriptor rows."
                    ),
                )
            )
        else:
            descriptor_row = descriptor_rows.iloc[matches[0]]
            has_denominator = (
                descriptor_row["asset_quantity_at_year_end_status"]
                == "numeric"
                or descriptor_row["quantity_inspected_maintained_status"]
                == "numeric"
            )
            relationship_status = (
                "matched_with_denominator"
                if has_denominator
                else "matched_without_denominator"
            )

        # Attach nullable descriptor lineage and quantity evidence.
        relationship_statuses.append(relationship_status)
        descriptor_workbooks.append(
            descriptor_row["source_workbook"]
            if descriptor_row is not None
            else pd.NA
        )
        descriptor_sheets.append(
            descriptor_row["source_sheet"]
            if descriptor_row is not None
            else pd.NA
        )
        descriptor_source_rows.append(
            descriptor_row["source_row"]
            if descriptor_row is not None
            else pd.NA
        )
        denominator_unit = (
            descriptor_row["quantity_unit_standard"]
            if descriptor_row is not None
            else pd.NA
        )
        installed_value = (
            descriptor_row["asset_quantity_at_year_end_standard"]
            if descriptor_row is not None
            else pd.NA
        )
        installed_value_status = (
            descriptor_row["asset_quantity_at_year_end_status"]
            if descriptor_row is not None
            else pd.NA
        )
        serviced_value = (
            descriptor_row["quantity_inspected_maintained_standard"]
            if descriptor_row is not None
            else pd.NA
        )
        serviced_value_status = (
            descriptor_row["quantity_inspected_maintained_status"]
            if descriptor_row is not None
            else pd.NA
        )
        denominator_units.append(denominator_unit)
        installed_values.append(installed_value)
        installed_value_statuses.append(installed_value_status)
        serviced_values.append(serviced_value)
        serviced_value_statuses.append(serviced_value_status)

        # Calculate installed-unit ratios under the shared eligibility policy.
        (
            routine_installed,
            non_routine_installed,
            total_installed,
            installed_status,
        ) = _ratio_values(
            relationship_status,
            installed_value,
            installed_value_status,
            denominator_unit,
            cost_row["currency_unit_status"],
            cost_row["routine_maintenance_expenditure_standard"],
            cost_row["routine_maintenance_expenditure_status"],
            cost_row["non_routine_maintenance_expenditure_standard"],
            cost_row["non_routine_maintenance_expenditure_status"],
            cost_row["total_maintenance_expenditure_standard"],
            cost_row["total_maintenance_expenditure_status"],
        )
        routine_installed_ratios.append(routine_installed)
        non_routine_installed_ratios.append(non_routine_installed)
        total_installed_ratios.append(total_installed)
        installed_ratio_statuses.append(installed_status)
        installed_ratio_units.append(
            f"nominal_AUD_per_{denominator_unit}"
            if installed_status in {
                "calculated",
                "incomplete_cost_components",
                "missing_numerators",
            }
            else pd.NA
        )

        # Calculate serviced-unit ratios independently of installed quantities.
        (
            routine_serviced,
            non_routine_serviced,
            total_serviced,
            serviced_status,
        ) = _ratio_values(
            relationship_status,
            serviced_value,
            serviced_value_status,
            denominator_unit,
            cost_row["currency_unit_status"],
            cost_row["routine_maintenance_expenditure_standard"],
            cost_row["routine_maintenance_expenditure_status"],
            cost_row["non_routine_maintenance_expenditure_standard"],
            cost_row["non_routine_maintenance_expenditure_status"],
            cost_row["total_maintenance_expenditure_standard"],
            cost_row["total_maintenance_expenditure_status"],
        )
        routine_serviced_ratios.append(routine_serviced)
        non_routine_serviced_ratios.append(non_routine_serviced)
        total_serviced_ratios.append(total_serviced)
        serviced_ratio_statuses.append(serviced_status)
        serviced_ratio_units.append(
            f"nominal_AUD_per_{denominator_unit}"
            if serviced_status in {
                "calculated",
                "incomplete_cost_components",
                "missing_numerators",
            }
            else pd.NA
        )

    # Append relationship, denominator, lineage, and unit metadata.
    relationships["relationship_status"] = relationship_statuses
    relationships["descriptor_source_workbook"] = descriptor_workbooks
    relationships["descriptor_source_sheet"] = descriptor_sheets
    relationships["descriptor_source_row"] = pd.array(
        descriptor_source_rows,
        dtype="Int64",
    )
    relationships["denominator_unit_standard"] = denominator_units
    relationships["installed_quantity_standard"] = pd.array(
        installed_values,
        dtype="Float64",
    )
    relationships["installed_quantity_status"] = installed_value_statuses
    relationships["serviced_quantity_standard"] = pd.array(
        serviced_values,
        dtype="Float64",
    )
    relationships["serviced_quantity_status"] = serviced_value_statuses
    relationships["installed_ratio_unit"] = installed_ratio_units
    relationships["installed_ratio_status"] = installed_ratio_statuses
    relationships["serviced_ratio_unit"] = serviced_ratio_units
    relationships["serviced_ratio_status"] = serviced_ratio_statuses

    # Append all six nominal expenditure ratios without filling missing values.
    ratio_columns = {
        "routine_expenditure_per_installed_unit": routine_installed_ratios,
        "non_routine_expenditure_per_installed_unit": (
            non_routine_installed_ratios
        ),
        "total_expenditure_per_installed_unit": total_installed_ratios,
        "routine_expenditure_per_serviced_unit": routine_serviced_ratios,
        "non_routine_expenditure_per_serviced_unit": (
            non_routine_serviced_ratios
        ),
        "total_expenditure_per_serviced_unit": total_serviced_ratios,
    }
    for column, values in ratio_columns.items():
        relationships[column] = pd.array(values, dtype="Float64")
    return relationships.reset_index(drop=True)


def _combine_stage_issues(
    stage2a_issues: pd.DataFrame,
    stage2b_issue_rows: list[dict[str, object]],
) -> pd.DataFrame:
    """Combine Stage 2A and Stage 2B issues under one stable contract."""
    # Copy Stage 2A issues and identify their origin without mutating the input.
    stage2a = stage2a_issues.copy(deep=True)
    stage2a.insert(0, "stage", "2A")
    stage2a = stage2a.loc[:, STAGE2B_ISSUE_COLUMNS]

    # Construct the Stage 2B side even when the run has no new issues.
    stage2b = pd.DataFrame(
        stage2b_issue_rows,
        columns=STAGE2B_ISSUE_COLUMNS,
    )

    # Preserve nullable source rows across workbook-level and row-level issues.
    combined = pd.concat([stage2a, stage2b], ignore_index=True)
    combined["source_row"] = pd.array(
        combined["source_row"],
        dtype="Int64",
    )
    return combined


def _panel_is_complete(
    workbook_mapping: pd.DataFrame,
    config: dict[str, Any],
) -> bool:
    """Evaluate the required business-period matrix independently."""
    # Restrict coverage to successfully extracted and reconciled workbooks.
    eligible = workbook_mapping.loc[
        workbook_mapping["extraction_status"].eq("success")
        & workbook_mapping["metadata_match_status"].eq(
            "validated_manifest_match"
        )
    ]

    # Count exact business-period records and require every configured cell once.
    counts = eligible.groupby(
        ["business", "manifest_reporting_period"],
        dropna=False,
    ).size()
    required_cells = {
        (business, period)
        for business in config["target_businesses"]
        for period in config["required_reporting_periods"]
    }
    return all(counts.get(cell, 0) == 1 for cell in required_cells)


def _validate_stage2a_result(
    stage2a_result: MaintenanceStage2AResult,
) -> None:
    """Require the Stage 2A contracts needed by standardisation."""
    # Reject unrelated objects before reading dataclass attributes.
    if not isinstance(stage2a_result, MaintenanceStage2AResult):
        raise MaintenanceStandardizationError(
            "stage2a_result must be a MaintenanceStage2AResult."
        )

    # Require all result tables and their unambiguous column contracts.
    for name, table in (
        ("descriptor_metrics", stage2a_result.descriptor_metrics),
        ("cost_metrics", stage2a_result.cost_metrics),
        ("workbook_mapping", stage2a_result.workbook_mapping),
        ("issues", stage2a_result.issues),
    ):
        _require_dataframe(name, table)
        _require_unique_columns(name, table)
    _require_columns(
        "descriptor_metrics",
        stage2a_result.descriptor_metrics,
        DESCRIPTOR_REQUIRED_COLUMNS + ENRICHMENT_COLUMNS,
    )
    _require_columns(
        "cost_metrics",
        stage2a_result.cost_metrics,
        COST_REQUIRED_COLUMNS + ENRICHMENT_COLUMNS,
    )
    _require_columns(
        "workbook_mapping",
        stage2a_result.workbook_mapping,
        WORKBOOK_MAPPING_COLUMNS,
    )
    _require_columns("issues", stage2a_result.issues, ISSUE_COLUMNS)

    # Prevent accidental re-standardisation from replacing prior derived values.
    for name, table, derived_columns in (
        (
            "descriptor_metrics",
            stage2a_result.descriptor_metrics,
            DESCRIPTOR_STANDARD_COLUMNS,
        ),
        (
            "cost_metrics",
            stage2a_result.cost_metrics,
            COST_STANDARD_COLUMNS,
        ),
    ):
        collisions = [
            column for column in derived_columns if column in table.columns
        ]
        if collisions:
            raise MaintenanceStandardizationError(
                f"{name} already contains Stage 2B column(s): "
                f"{', '.join(collisions)}."
            )


def standardize_rin_maintenance(
    stage2a_result: MaintenanceStage2AResult,
    *,
    config_path: str | Path = DEFAULT_STANDARDIZATION_CONFIG,
) -> MaintenanceStage2BResult:
    """Standardize one in-memory Stage 2A result for analysis."""
    # Validate the result boundary and reload the semantic configuration.
    _validate_stage2a_result(stage2a_result)
    config = load_standardization_config(config_path)
    stage2b_issue_rows: list[dict[str, object]] = []

    # Standardize both maintenance tables without changing Stage 2A inputs.
    descriptor = _standardize_descriptor_metrics(
        stage2a_result.descriptor_metrics,
        config,
        stage2b_issue_rows,
    )
    cost = _standardize_cost_metrics(
        stage2a_result.cost_metrics,
        config,
        stage2b_issue_rows,
    )

    # Build cost-to-descriptor relationships and eligible nominal ratios.
    relationships = _build_cost_descriptor_relationships(
        descriptor,
        cost,
        stage2b_issue_rows,
    )

    # Combine factual issues and evaluate Stage 2B independently of earlier flags.
    issues = _combine_stage_issues(
        stage2a_result.issues,
        stage2b_issue_rows,
    )
    stage2b_complete = not any(
        issue["severity"] == "error" for issue in stage2b_issue_rows
    )
    panel_complete = _panel_is_complete(
        stage2a_result.workbook_mapping,
        config,
    )

    # Return copied mapping evidence and every independent completeness flag.
    return MaintenanceStage2BResult(
        descriptor_metrics=descriptor,
        cost_metrics=cost,
        workbook_mapping=stage2a_result.workbook_mapping.copy(deep=True),
        cost_descriptor_relationships=relationships,
        issues=issues,
        extraction_complete=stage2a_result.extraction_complete,
        stage2a_complete=stage2a_result.stage2a_complete,
        stage2b_complete=bool(stage2b_complete),
        panel_complete=bool(panel_complete),
    )


def prepare_rin_maintenance(
    descriptor_metrics: pd.DataFrame,
    cost_metrics: pd.DataFrame,
    run_report: pd.DataFrame,
    manifest: pd.DataFrame,
    *,
    config_path: str | Path = DEFAULT_STANDARDIZATION_CONFIG,
) -> MaintenanceStage2BResult:
    """Run Stage 2A enrichment followed by Stage 2B standardisation."""
    # Reconcile metadata and resolve submitted parent groups first.
    stage2a_result = enrich_rin_maintenance(
        descriptor_metrics,
        cost_metrics,
        run_report,
        manifest,
    )

    # Apply semantic mappings and relationships through the reviewed config.
    return standardize_rin_maintenance(
        stage2a_result,
        config_path=config_path,
    )
