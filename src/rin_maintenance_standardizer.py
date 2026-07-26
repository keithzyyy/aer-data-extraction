"""Stage 2A enrichment helpers for canonical RIN maintenance tables."""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation

import pandas as pd


BUSINESS_FILENAME_ALIASES = {
    "Transgrid": ("transgrid",),
    "AusNet Transmission": ("ausnet",),
    "Powerlink": ("powerlink",),
    "ElectraNet": ("electranet",),
}

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
    "business_candidate",
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

__all__ = [
    "MaintenanceStage2AResult",
    "MaintenanceStandardizationError",
    "enrich_rin_maintenance",
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


def _business_candidates(source_workbook: object) -> list[str]:
    """Return canonical businesses whose aliases occur in one filename."""
    # Normalize the complete filename once for every configured alias check.
    normalized_filename = _normalize_match_text(source_workbook)

    # Collapse token-bounded aliases for one business into one candidate.
    return [
        business
        for business, aliases in BUSINESS_FILENAME_ALIASES.items()
        if any(
            re.search(
                (
                    r"(?<![0-9a-z])"
                    + re.escape(_normalize_match_text(alias))
                    + r"(?![0-9a-z])"
                ),
                normalized_filename,
            )
            for alias in aliases
        )
    ]


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

        # Derive the filename candidate even when extraction failed.
        candidates = _business_candidates(source_workbook)
        business_candidate: object = (
            candidates[0] if len(candidates) == 1 else pd.NA
        )

        # Initialize unresolved metadata fields before applying match rules.
        extracted_period: object = pd.NA
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
                    "business_candidate": business_candidate,
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
        elif not candidates:
            # Require a known scoped-business alias before consulting the manifest.
            metadata_status = "unmatched_business_alias"
            issues.append(
                _issue(
                    table_name="workbook_mapping",
                    source_workbook=source_workbook,
                    issue_code=metadata_status,
                    message="No configured business alias matched the filename.",
                )
            )
        elif len(candidates) > 1:
            # Refuse to choose between multiple filename business candidates.
            metadata_status = "ambiguous_business_alias"
            issues.append(
                _issue(
                    table_name="workbook_mapping",
                    source_workbook=source_workbook,
                    issue_code=metadata_status,
                    message=(
                        "Multiple business aliases matched the filename: "
                        f"{', '.join(candidates)}."
                    ),
                )
            )
        else:
            # Match the validated candidate and period to manifest metadata.
            candidate = candidates[0]
            manifest_business = manifest["business"].map(_display_text)
            manifest_periods = manifest["reporting_period"].map(_display_text)
            matches = manifest.loc[
                manifest_business.eq(candidate)
                & manifest_periods.eq(_display_text(extracted_period))
            ]

            if matches.empty:
                # Preserve a factual zero-match result for notebook review.
                metadata_status = "manifest_no_match"
                issues.append(
                    _issue(
                        table_name="workbook_mapping",
                        source_workbook=source_workbook,
                        issue_code=metadata_status,
                        message=(
                            "No manifest record matched business "
                            f"{candidate} and period "
                            f"{_display_text(extracted_period)}."
                        ),
                    )
                )
            elif len(matches) > 1:
                # Refuse ambiguous business-period records in the inventory.
                metadata_status = "manifest_multiple_matches"
                issues.append(
                    _issue(
                        table_name="workbook_mapping",
                        source_workbook=source_workbook,
                        issue_code=metadata_status,
                        message=(
                            "Multiple manifest records matched business "
                            f"{candidate} and period "
                            f"{_display_text(extracted_period)}."
                        ),
                    )
                )
            else:
                # Read the unique authoritative metadata without changing it.
                manifest_row = matches.iloc[0]
                resolved_business = manifest_row["business"]
                manifest_period = manifest_row["reporting_period"]
                landing_page_url = manifest_row["landing_page_url"]
                source_page_url = manifest_row["source_page_url"]

                # Require both URLs before declaring the reconciliation complete.
                if _is_blank(landing_page_url) or _is_blank(source_page_url):
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
                    metadata_status = "validated_manifest_match"

        # Record every resolved and unresolved field in a stable mapping schema.
        mapping_rows.append(
            {
                "source_workbook": source_workbook,
                "extraction_status": extraction_status,
                "run_report_reporting_period": run_period,
                "extracted_reporting_period": extracted_period,
                "business_candidate": business_candidate,
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
