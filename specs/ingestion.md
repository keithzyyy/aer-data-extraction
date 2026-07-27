# Spec: RIN ingestion and maintenance-data pipeline

## Goal and relationship to the project scope

Acquire the Category Analysis RIN workbooks for Transgrid, AusNet Transmission,
Powerlink, and ElectraNet for at least the last five reporting years, then
extract the `2.8 Maintenance` data without changing the submitted workbooks.

This specification connects the four project stages:

1. **Acquire and extract:** discover, record, download, and extract the required
   RIN workbook data.
2. **Standardise:** make source labels, units, categories, and values comparable
   while preserving their submitted forms.
3. **Consolidate for Power BI:** combine the standardised data and source
   metadata into a stable cross-business data model.
4. **Develop the Power BI dashboard:** build calculations and visuals over the
   validated consolidated data.

The current implementation is concentrated in stage 1. Stages 2 to 4 are
described at their intended boundaries so that stage-1 choices do not obstruct
later comparison or dashboard work.

## Pipeline overview

```text
AER author pages
    -> landing-page inventory in rin_manifest.csv
    -> immutable downloaded workbooks in data/raw/
    -> heading-driven extraction from 2.8.1 and 2.8.2
    -> canonical wide descriptor and cost CSVs
    -> business reconciliation and parent-child enrichment
    -> category, unit, and type standardisation
    -> consolidated Power BI data model
    -> Power BI measures, visuals, and dashboard
```

Acquisition completeness, extraction success, and later data validation are
separate checks. Passing one check does not imply that the others are complete.

## Stage 1 - Acquire and extract RIN maintenance data

### Purpose

Stage 1 must produce repeatable, traceable copies of the maintenance data as
submitted. It should resolve presentation differences between workbook
templates, but it must not yet normalise categories, rescale units, or interpret
the values for Power BI.

### Workflow

#### 1. Discover RIN document landing pages

Crawl every paginated AER author page configured for the four transmission
businesses:

```python
AUTHOR_PAGES = {
    "Transgrid": "https://www.aer.gov.au/authors/transgrid-t",
    "ElectraNet": "https://www.aer.gov.au/authors/electranet",
    "Powerlink": "https://www.aer.gov.au/authors/powerlink",
    "AusNet Transmission": "https://www.aer.gov.au/authors/ausnet-services-t",
}
```

Retain Category Analysis RIN document landing-page URLs rather than assuming
that an attachment URL is permanent. Follow pagination until no next page
remains, with a visited-page check to stop an accidental pagination loop.

Reusable discovery logic belongs in `src/rin_discovery.py`. The thin
`scripts/discover_rin_workbooks.py` entry point and author-page JSON
configuration make repeat discovery possible without changing the module.
Notebook use remains appropriate for manual inspection.

AER author pages are useful discovery sources, but they are not exhaustive.
They may omit a required submission even when its document exists elsewhere on
the AER website. Discovery success therefore does not prove acquisition
completeness. Completeness is assessed against the required business-period
matrix, and missing cells must be found through targeted AER searches or
recorded as acquisition gaps.

#### 2. Maintain the acquisition manifest

Use `data/rin_manifest.csv` as the inventory of discovered source documents.
Deduplicate records by AER landing-page URL and preserve existing notes when
discovery is rerun.

The manifest must provide or resolve:

- business;
- reporting period or a document title from which it can be derived;
- AER document landing-page URL;
- workbook attachment URL;
- the exact downloaded `local_filename`; and
- a factual acquisition error when a landing page or attachment cannot be
  resolved.

`local_filename` must be unique for every acquired workbook. It is the
authoritative bridge from a canonical Stage 1 `source_workbook` value to the
manifest; business names must not be inferred from filenames during later
processing.

The manifest is an acquisition inventory, not an approval queue. Fields such as
`pending`, `approved`, or `rejected` must not determine whether a workbook is
downloaded or extracted. If a legacy review field remains, it has no gating
meaning under this specification.

#### 3. Download the manifest workbooks

Resolve each required manifest landing page to its spreadsheet attachment and
save the workbook under `data/raw/`. Downloading may be manual, programmatic, or
AI-assisted. The required outcome is the same: each required manifest record
leads to an immutable local workbook or a recorded acquisition error.

Do not edit, recalculate, or overwrite a downloaded source workbook. Preserve
its original extension, including `.xlsm`, and do not execute macros.

#### 4. Extract one workbook

Use `extract_rin_maintenance` from
`src/rin_maintenance_heading_extractor.py` to open one workbook
non-destructively and extract `2.8.1` and `2.8.2`. The extractor never saves or
recalculates the source workbook.

Expected section titles, semantic headings, accepted aliases, and multi-row
heading relationships are stored in
`config/rin_maintenance_expected_schema.json`. The configuration contains no
absolute row numbers or column letters.

The extractor returns two canonical wide pandas DataFrames:

- `descriptor_metrics` for `2.8.1`; and
- `cost_metrics` for `2.8.2`.

Canonical means that known workbook layouts produce the same agreed column
names and meanings. Wide means that each metric has its own column. Canonical
does not mean that source categories, units, or values have already been
standardised.

#### 5. Batch and save successful extractions

The preprocessing entry point scans an explicitly supplied raw directory and
calls `extract_rin_maintenance` once for every supported workbook. It combines
the successful descriptor results with one another and the successful cost
results with one another, then saves two canonical wide CSVs.

This entry point does not require the manifest and does not infer business
identity from filenames. The manifest is used for source acquisition and will
be joined later through an explicit local-file mapping. Keeping this boundary
prevents batch extraction from guessing business metadata.

This batching step is not stage-3 consolidation. It only places the same type
of extracted records into neat, consistently shaped files.

### Data contracts and invariants

Use the following AER publications as semantic references:

- [AER Category Analysis data template for transmission network service providers](https://www.aer.gov.au/documents/aer-category-analysis-data-template-transmission-network-service-providers)
- [Expenditure forecast assessment guideline: regulatory information notices for category analysis](https://www.aer.gov.au/industry/registers/resources/guidelines/expenditure-forecast-assessment-guideline-regulatory-information-notices-category-analysis-2014)

The 2014 template explains the intended meaning of the tables, but its exact
coordinates are not a universal contract for later submissions. Each submitted
workbook remains authoritative for its reporting period, including additional
categories and later template revisions.

Apply the stage-1 contract in layers:

1. **AER semantic contract:** AER documentation defines what the maintenance
   tables represent.
2. **Acquisition contract:** the manifest traces the AER landing page to a local
   source workbook or records an acquisition error.
3. **Raw-source contract:** downloaded workbooks remain immutable and preserve
   their submitted values, labels, units, and workbook structure.
4. **Canonical extraction contract:** the expected-heading configuration
   defines the required semantic fields. Missing or ambiguous required
   structure stops extraction; non-fatal value differences remain with
   warnings.
5. **Batch-output contract:** successful one-workbook results are concatenated
   without category mapping, unit scaling, or business inference.

The descriptor CSV must use the configured canonical order:

```text
reporting_period
maintenance_activity
maintenance_asset_category
measure_asset_quantity
source_unit
asset_quantity_at_year_end
quantity_inspected_maintained
average_age_of_asset_group
inspection_cycle_years
maintenance_cycle_years
source_workbook
source_sheet
source_row
```

The cost CSV must use the configured canonical order:

```text
reporting_period
maintenance_activity
maintenance_asset_subcategory
source_currency_unit
routine_maintenance_expenditure
non_routine_maintenance_expenditure
source_workbook
source_sheet
source_row
```

Descriptor and cost row counts may differ. The two sections must not be joined
by worksheet row because some submissions contain cost-only records.

### Implemented heading-driven extraction

The extractor treats the worksheet as a map with named landmarks. Coordinates
are recorded after discovery for traceability; they are extraction results, not
hardcoded assumptions.

#### High-level function responsibilities

`load_expected_schema`

Loads and validates the JSON configuration containing expected worksheet,
section, and column-heading semantics.

`normalize_heading`

Normalises capitalisation, whitespace, line breaks, slashes, and common Unicode
punctuation so harmless presentation differences do not prevent a heading
match. It does not use fuzzy matching, which could conceal a genuine template
change.

`load_maintenance_sheet`

Loads `2.8 Maintenance` as a raw pandas grid with `header=None`, so no
presentation row is incorrectly treated as the DataFrame header. It also loads
the worksheet metadata needed to inspect real merged ranges without modifying
the source.

`find_section_anchors`

Searches the worksheet for the `2.8.1` and `2.8.2` titles regardless of their
absolute positions.

`detect_layout_profile`

Compares the discovered title positions. Titles on the same row indicate the
legacy side-by-side layout; `2.8.2` below `2.8.1` indicates a stacked layout. A
template-date marker distinguishes the observed baseline and revised stacked
profiles.

`derive_section_regions`

Uses the relative title positions to create separate descriptor and cost search
regions.

`build_merged_value_lookup`

Reads actual Excel merged ranges. Heading and activity values are propagated
only to cells covered by a real merge; unrestricted DataFrame forward filling
is not used.

`resolve_section_headers`

Searches each section for the semantic headings defined in the JSON
configuration and maps them to discovered worksheet columns. It supports
simple headings and multi-row paths such as
`ASSET QUANTITY > AT YEAR END` and
`DIRECT EXPENDITURE > ROUTINE MAINTENANCE`.

`resolve_reporting_period`

Finds the reporting period and confirms that the descriptor and cost sections
refer to the same period.

`extract_section_rows`

Starts below the discovered headings and reporting-period row, reads only the
semantically mapped columns, and retains rows containing an activity, category,
subcategory, or reported metric.

`validate_extracted_section`

Checks the canonical columns and meaningful records. Unexpected numeric text
or source units are preserved and returned as warnings rather than silently
converted or discarded.

`extract_rin_maintenance`

Orchestrates the process for one workbook and returns the two canonical wide
tables together with the reporting period, template metadata, layout profile,
header locations, source lineage, and warnings.

#### Extraction flow

```text
load semantic schema
    -> load the worksheet without assuming a header row
    -> find the 2.8.1 and 2.8.2 titles
    -> derive their relative table regions
    -> find expected headings within each region
    -> use the discovered columns
    -> confirm the reporting period
    -> extract and validate both tables independently
```

Do not use Excel's declared used range as the extraction boundary. Formatting
may extend to columns such as `WZV` even when meaningful content ends near
column `J`. Search within the bounded pandas grid and the semantically resolved
columns.

### Implemented preprocessing entry point

The stage-1 batch interface is a thin command-line wrapper around
`extract_rin_maintenance`:

```text
python -m scripts.preprocess_rin_maintenance --raw-dir data/raw --output-dir data/processed [--schema config/rin_maintenance_expected_schema.json] [--overwrite]
```

The entry point:

```text
validate arguments and output collisions
find .xlsx and .xlsm files directly under the raw directory
ignore temporary Excel files such as ~$...

for each workbook:
    call extract_rin_maintenance
    collect descriptor and cost tables on success
    record warnings or the extraction error
    continue with the remaining workbooks

combine and save every successful extraction
save the run report
return an exit code representing overall completion
```

It creates:

- `rin_maintenance_descriptor_metrics.csv`;
- `rin_maintenance_cost_metrics.csv`; and
- `rin_maintenance_run_report.csv`.

The run report contains one row per attempted workbook with:

- source workbook;
- success or failure status;
- reporting period and layout profile when resolved;
- descriptor and cost row counts;
- warnings;
- error details; and
- the overall `run_complete` value.

The batch policies are:

- Non-fatal extractor warnings still count as successful extraction.
- When some workbooks fail, save all successful rows, mark the run incomplete,
  save the report, and exit `1`.
- When every attempted workbook succeeds, mark the run complete and exit `0`.
- Invalid arguments, no supported workbooks, or an output or setup failure
  exits `2`.
- When all attempted workbooks fail, save the run report but do not create
  misleading canonical data files.
- Existing outputs are not replaced unless `--overwrite` is supplied.
- The output directory cannot be the raw directory or one of its descendants.
- Source workbooks are never moved, modified, recalculated, or deleted.

The operating-system exit code supports future command automation. The CSV
report preserves completion information for later file-based processing.
Canonical describes the output schema; complete describes workbook coverage.
A canonical CSV may therefore be incomplete.

### Failure modes and edge cases

`extract_rin_maintenance` raises `MaintenanceExtractionError` when required
structure cannot be resolved safely. Examples include a missing maintenance
sheet, missing or duplicate section anchors, ambiguous required headings,
unsupported section orientation, inconsistent reporting periods, or no
meaningful extracted rows. No partial result is returned for that workbook.

The source workbook is not rejected, edited, or deleted after an extraction
failure. The failure identifies a case for investigation or an explicit
expected-heading configuration change.

Non-fatal differences, such as unfamiliar units or text in an expected numeric
field, remain in the returned tables and warnings. Additional business-specific
categories remain eligible for extraction.

At batch level:

- one workbook failure must not prevent the remaining workbooks from being
  attempted;
- an incomplete run must remain usable for exploratory stage-2 work;
- its incompleteness must remain visible in the run report and exit code;
- temporary Excel lock files must not be treated as source workbooks; and
- output collisions must not silently overwrite earlier results.

### Automated verification

`tests/test_preprocess_rin_maintenance.py` contains 13 isolated unit tests for
the batch preprocessing entry point. The tests use Python's built-in
`unittest`, temporary directories, fabricated `MaintenanceExtractionResult`
objects, and mocked calls to `extract_rin_maintenance`.

The toy workbook inputs are empty files with workbook-like names such as
`a.xlsx` and `b.xlsm`. They are sufficient for testing file discovery because
the one-workbook extractor is mocked. The fabricated extraction results contain
small descriptor and cost DataFrames with a reporting period, source workbook,
layout profile, and optional warnings. Temporary inputs and outputs are removed
automatically after each test.

The tests verify:

- deterministic discovery of direct-child `.xlsx` and `.xlsm` files;
- exclusion of temporary Excel lock files, unsupported files, directories, and
  nested workbooks;
- complete runs that produce both canonical CSVs, a complete report, and exit
  code `0`;
- non-fatal warnings that remain successful and are stored as JSON in the
  report;
- partial failures that retain successful rows, record the failed workbook,
  mark the run incomplete, and exit `1`;
- all-failure runs that write a report without misleading canonical data
  files;
- explicit overwrite behaviour, including removal of stale canonical data
  after an all-failure replacement;
- refusal to overwrite existing outputs without `--overwrite`;
- setup failures for missing raw directories, nested output directories, no
  supported workbooks, and invalid schemas;
- rejection and reporting of extractor results whose canonical columns do not
  match the configured schema;
- forwarding of command-line arguments and the orchestrator exit code; and
- the important processing, failure, and final-summary print messages.

These tests verify batch coordination and artifact safety. The placeholder
files are not valid Excel workbooks, so the tests do not repeat the heading
extractor's cell-level parsing checks or reconcile extracted values against
independently approved expected outputs.

The historical 24-workbook evidence below supplies point-in-time
real-workbook coverage for the heading extractor. A future golden-output test
may add automated cell-to-CSV reconciliation after representative expected
values have been independently reviewed.

Later stages require separate verification:

- stage 2 must test category mappings, scale factors, retained source values,
  and enforced data types;
- stage 3 must test business-period coverage, uniqueness, model relationships,
  and reconciliation to the standardised tables; and
- stage 4 must reconcile Power BI calculations and displayed totals to the
  validated Python outputs.

### Historical feasibility evidence and current acceptance status

The first workbook download and workbook-structure review were an exploratory
feasibility pass rather than the recurring ingestion process:

- workbook landing-page metadata came from `data/rin_manifest.csv`;
- Codex resolved public AER attachments and downloaded the source workbooks to
  `data/raw/`;
- ordinary Python workbook tooling, principally `openpyxl` and direct Open XML
  inspection, was sufficient to inspect workbook structure;
- the pass tested whether acquisition and heading-driven extraction could be
  programmatic; and
- Codex accelerated the investigation but is not an architectural or
  operational dependency.

The detailed findings remain in the
[RIN maintenance structure report](../.agents/rin_maintenance_structure_report.md).
The report is historical, point-in-time feasibility evidence that informed the
extractor. It is not a production dataset or a planned recurring audit.

Historical 24-workbook feasibility evidence:

- all 24 candidate landing pages exposed a spreadsheet attachment;
- all 24 downloaded workbooks opened successfully;
- every workbook contained `2.8 Maintenance`;
- all 24 workbooks passed heading-driven extraction;
- the detected profiles were 17 stacked baseline, 6 stacked revised, and 1
  legacy side-by-side;
- descriptor and cost tables can have different row counts without losing
  records;
- cost-only records such as Bushfire Remediation remain present;
- additional business-specific categories are retained;
- the legacy `$000's` unit is preserved rather than silently scaled;
- unfamiliar units and nonnumeric metric text produce warnings; and
- inflated worksheet dimensions do not determine extraction bounds.

After the required business-period matrix exposed three omissions from the
author-page discovery results, the acquisition inventory was extended to 27
workbooks. The refreshed current evidence is:

- all 27 manifest workbooks have an exact, unique `local_filename`;
- all 27 workbooks passed heading-driven extraction;
- the four scoped businesses each have one workbook for every reporting period
  from 2019-20 through 2023-24; and
- the historical 17 stacked baseline, 6 stacked revised, and 1 legacy
  side-by-side counts remain evidence for the original 24-workbook feasibility
  set rather than asserted profile counts for the expanded set.

Stage 1 is complete for a source workbook when:

- the manifest traces its AER landing page or records an acquisition error;
- an acquired workbook remains unchanged under `data/raw/`;
- successful extraction returns both canonical tables; or
- failed extraction retains the workbook and records a clear error without
  producing an unsafe partial workbook result.

The CLI implements the documented scan, output, partial-success, overwrite,
report, and exit-code contracts. All 13 isolated unit tests currently pass
without accessing the ignored raw-workbook directory.

## Stage 2 - Enrich and standardise extracted maintenance data

### Purpose

Stage 2 will first recover business identity and parent-child maintenance
structure that is implicit in the submitted workbooks, then convert submitted
labels, units, and values into explicitly comparable data. The canonical
stage-1 outputs remain unchanged as source evidence; the heading extractor and
preprocessing entry point must not perform these semantic transformations.

Stage 2 is divided into two parts:

1. **Stage 2A - Enrich and structurally resolve extracted data.**
2. **Stage 2B - Standardise labels, units, and values.**

The Stage 2A and Stage 2B implementations are notebook-oriented Python
functions that return DataFrames for inspection. A stage-2 CLI and persistent
standardised outputs will be considered only after both parts are reviewed.

### Stage 2A - Enrich and structurally resolve extracted data

#### Purpose and workflow

Stage 2A reconciles each extracted workbook with its acquisition metadata,
recover omitted parent maintenance activities from bounded row context, and
classify extracted rows without changing their submitted values.

```text
read descriptor, cost, run-report, and manifest DataFrames
    -> reconcile each source workbook with one manifest record
    -> process each workbook and table in source-row order
    -> reconstruct omitted parent maintenance activities
    -> classify meaningful, empty-template, and unresolved rows
    -> return enriched tables, workbook mapping, issues, and completeness
```

The stage-1 run report supplies extraction completeness. A successful Stage 2A
result describes enrichment of the canonical rows that were supplied; it does
not prove that all required submissions were acquired or that every business
has five reporting periods.

#### Business reconciliation

The manifest is the authoritative source of business identity and AER
landing-page metadata. Stage 2A requires an exact
`source_workbook == manifest.local_filename` match. `local_filename` is a
required manifest field, must be nonblank for acquired records, and must be
unique. Filename aliases and inferred business names are not accepted
reconciliation fallbacks.

The extracted reporting period and run-report period must agree with the
uniquely matched manifest record. A zero-match, duplicate local filename,
reporting-period conflict, or incomplete AER metadata remains visible in the
mapping and issues outputs, leaves the affected metadata unresolved, and makes
Stage 2A incomplete. Stage 2A must not modify the manifest, download statuses,
or local filenames.

#### Parent activity resolution

The descriptor and cost tables each contain a parent `maintenance_activity`
column and a child category or subcategory column. Some workbooks visually
continue an activity across several rows **without** merging or repeating its cell.
Those source blanks are continuation labels rather than new activities.

Stage 2A resolves them as follows:

```text
for each workbook, sheet, and table:
    sort rows by source_row
    reset the current parent activity

    for each row:
        if maintenance_activity is populated:
            retain it as the current parent and record its source row
        else if the row has a child category and follows the current group:
            inherit the last explicit parent and record its anchor source row
        else:
            leave the parent unresolved and report the row
```

Resolution must never cross a workbook, sheet, or table boundary. A gap or
other break in the expected source-row context must be reported rather than
filled silently. The child category label must not determine its parent by
itself because the same child label can appear under different activities.
Multiple consecutive continuation rows inherit the last explicit parent, not
the preceding row's literal blank value.

The source `maintenance_activity` column remains unchanged. Stage 2A appends a
resolved value, a resolution status, and the source row containing the explicit
parent.

#### Observed null-pattern evidence

The historical 24-workbook canonical outputs contained:

- 11 descriptor rows with at least one missing category field and at least one
  reported numeric metric; and
- 16 cost rows with the same condition.

In all 27 cases, only `maintenance_activity` is missing, the child category or
subcategory is present, and the last explicit parent in source-row context is
`Other maintenance activity`. This evidence supports the bounded continuation
rule, but the implementation must not hardcode every missing activity as
`Other maintenance activity`.

The expanded 27-workbook set adds one different case in AusNet Transmission
2019-20: a descriptor row has an explicit `Other maintenance activity` parent
and a serviced quantity of zero, but no child category, measure, or source
unit. Stage 2A correctly preserves it as a meaningful row with a submitted
parent. Stage 2B separately reports its unresolved child hierarchy and unit;
this new case must not be folded into the historical continuation-row rule.

#### Row classification

Row classification and activity resolution describe different facts and must
use separate fields.

`activity_resolution_status` will use:

- `submitted` when the activity is present in the source row;
- `continued_group_label` when it is inherited from a defensible source-row
  group; and
- `unresolved_missing` when a meaningful row has no defensible parent.

`row_classification` will use:

- `meaningful` when a child category or relevant metric is present;
- `empty_template_row` when no child category or relevant metric was
  submitted; and
- `unresolved` when the row is meaningful but its required parent structure
  cannot be resolved.

A child category may remain meaningful when all its numeric metrics are blank.
Metric blanks remain factual source blanks; Stage 2A must not infer that a
blank means zero or `not_applicable`. Empty template rows remain in the
enriched outputs for inspection rather than being deleted.

#### Implemented module interface and outputs

The notebook-oriented implementation is provided by
`src/rin_maintenance_standardizer.py`:

```python
@dataclass
class MaintenanceStage2AResult:
    descriptor_metrics: pd.DataFrame
    cost_metrics: pd.DataFrame
    workbook_mapping: pd.DataFrame
    issues: pd.DataFrame
    extraction_complete: bool
    stage2a_complete: bool
```

```python
class MaintenanceStandardizationError(RuntimeError):
    """Raised when Stage 2 inputs cannot be processed safely."""
```

```python
def enrich_rin_maintenance(
    descriptor_metrics: pd.DataFrame,
    cost_metrics: pd.DataFrame,
    run_report: pd.DataFrame,
    manifest: pd.DataFrame,
) -> MaintenanceStage2AResult:
```

The enriched descriptor and cost DataFrames will retain every canonical source
column and append:

```text
business
landing_page_url
source_page_url
metadata_match_status
maintenance_activity_resolved
activity_resolution_status
activity_anchor_source_row
row_classification
```

`workbook_mapping` will contain one row per attempted source workbook,
including its exact matched manifest filename, resolved business, extracted
and manifest reporting periods, AER URLs, and match status. `issues` will
contain severity, table name, source workbook, source row, issue code, and a
factual message.

`extraction_complete` will carry the overall stage-1 run-report result.
`stage2a_complete` will be true only when every workbook represented in the
canonical inputs has one validated manifest match and every meaningful
extracted row has a resolved parent. It describes Stage 2A enrichment of the
supplied data and remains separate from acquisition and reporting-period
coverage.

Missing required input columns or invalid input schemas will raise
`MaintenanceStandardizationError`. Workbook- or row-level reconciliation
problems will remain in the returned outputs and issues, set
`stage2a_complete` to false, and will not suppress rows that were enriched
successfully.

#### Implemented verification and acceptance

Fabricated DataFrame tests confirm that:

- submitted activity values and all other canonical source columns are
  unchanged;
- continuation rows inherit the last explicit parent and record its source
  row;
- multiple continuation rows retain the same explicit parent;
- resolution never crosses workbook, sheet, or table boundaries;
- child labels cannot determine their parent without source-row context;
- child categories with blank metrics remain meaningful;
- rows without a child category or meaningful metrics are empty template rows;
- meaningful rows without a defensible parent remain unresolved;
- source workbooks require exactly one matching manifest `local_filename`;
- missing or duplicate local filenames and reporting-period conflicts are
  reported; and
- incomplete extraction remains distinguishable from incomplete Stage 2A
  enrichment.

The current 27-workbook dataset will also be used read-only as an integration
check. All workbooks should reconcile with one manifest record, and the known
continuation rows should resolve from their actual source-row context rather
than from a hardcoded category assumption.

### Stage 2B - Standardise labels, units, and values

#### Purpose and workflow

Stage 2B consumes the enriched Stage 2A tables and performs the semantic
transformations needed for defensible cross-business comparison while
preserving every submitted row and source field:

```text
read enriched descriptor and cost DataFrames
    -> map parent-child category variations with contextual rules
    -> standardise descriptor quantities and nominal expenditure
    -> relate each meaningful cost row to a unique descriptor row
    -> calculate only ratios with valid numerators and denominators
    -> return standardised tables, relationships, issues, and completeness
```

`config/rin_maintenance_standardization.json` defines the four target
businesses, required reporting periods, category rules, unit conversions,
measure-label fallbacks, and recognized special metric text. Configuration
rules use normalized matching only for presentation differences; they do not
permit fuzzy semantic matching.

High-confidence aliases include casing, whitespace, Unicode, the submitted
`Tramsission tower support structures` and `Transmission Towers Support`
variants, corridor-maintenance `non vegetation`/`non veg` variants, and clear
ROW/right-of-way punctuation variants. `Metering` and `Metering Systems`
remain distinct. `Communications`, `Telecomms Systems`, and
`Telecommunications Systems` also remain distinct.

Unknown business-specific categories are retained with a deterministic
source-derived identifier and `retained_source_category` mapping status. An
unknown category alone does not make Stage 2B incomplete.

#### Public interface

The notebook-oriented implementation is provided by
`src/rin_maintenance_standardizer.py`:

```python
@dataclass
class MaintenanceStage2BResult:
    descriptor_metrics: pd.DataFrame
    cost_metrics: pd.DataFrame
    workbook_mapping: pd.DataFrame
    cost_descriptor_relationships: pd.DataFrame
    issues: pd.DataFrame
    extraction_complete: bool
    stage2a_complete: bool
    stage2b_complete: bool
    panel_complete: bool
```

```python
def load_standardization_config(
    config_path: str | Path,
) -> dict[str, Any]:
```

```python
def standardize_rin_maintenance(
    stage2a_result: MaintenanceStage2AResult,
    *,
    config_path: str | Path = DEFAULT_STANDARDIZATION_CONFIG,
) -> MaintenanceStage2BResult:
```

```python
def prepare_rin_maintenance(
    descriptor_metrics: pd.DataFrame,
    cost_metrics: pd.DataFrame,
    run_report: pd.DataFrame,
    manifest: pd.DataFrame,
    *,
    config_path: str | Path = DEFAULT_STANDARDIZATION_CONFIG,
) -> MaintenanceStage2BResult:
```

`prepare_rin_maintenance` runs Stage 2A and then Stage 2B. It is the single
in-memory entry point used by the Stage 2 CLI; the core function itself
performs no file writes.

#### Standardised data contract

Stage 2B:

- store standardised values separately rather than overwriting source values;
- map categories using resolved parent-child context rather than child labels
  alone;
- distinguish an unmapped category from a missing category;
- set `analytic_row_eligible` only for rows classified as `meaningful`;
- apply descriptor quantity conversions of `0's` and `number` to count,
  `km` to kilometres, and `000' km` to kilometres with a factor of 1,000;
- infer a blank descriptor unit only from an exact configured measure label;
- apply nominal-AUD scale factors explicitly, including legacy `$000's`;
- report nonnumeric metric text rather than silently coercing it to zero; and
- retain additional categories until an explicit mapping decision is made.

Numeric value statuses are `numeric`, `blank`, `recognized_special`, or
`invalid_numeric`. `Nil. Cond mon.&corr mtce` is retained in the source column
and represented by a null standard maintenance-cycle value with
`recognized_special`; it is never converted to zero. Total maintenance
expenditure is calculated only when both routine and non-routine source
components are numeric. A blank component is not treated as zero.

Meaningful cost and descriptor rows are related using business, reporting
period, standard maintenance-activity ID, and standard asset-category ID.
Duplicate descriptor keys are detected before joining so a many-to-many merge
cannot silently multiply rows. Relationship statuses are:

- `matched_with_denominator`;
- `matched_without_denominator`;
- `no_descriptor_match`; and
- `ambiguous_match`.

Stage 2B calculates routine, non-routine, and total nominal-AUD expenditure per
installed unit and per serviced unit only when the relationship is unique, the
standardized denominator is greater than zero, the numerator is numeric, and
the relevant currency and quantity units were standardized. Total ratios also
require both expenditure components. Missing and zero denominators, incomplete
components, and absent or ambiguous matches remain null with factual statuses.

`no_descriptor_match` and `matched_without_denominator` are non-fatal when
reported. Ambiguous matches, invalid numeric text, and unknown or conflicting
units make `stage2b_complete=False`.

Stage 2A and Stage 2B issues are combined into:

```text
stage
severity
table_name
source_workbook
source_row
issue_code
message
```

The four completeness flags remain independent:

- `extraction_complete` reports the Stage 1 run;
- `stage2a_complete` reports exact manifest reconciliation and parent
  resolution;
- `stage2b_complete` reports safe category, unit, value, and relationship
  standardisation; and
- `panel_complete` reports whether every target business has one successfully
  processed workbook for every required reporting period.

Exploratory Stage 2 work may proceed when an earlier flag is false so
successful workbooks remain useful. Incompleteness must be carried forward and
must not be mistaken for a complete cross-business panel.

#### Verification and current acceptance

Fabricated DataFrame tests cover exact local-filename reconciliation, source
preservation, contextual category aliases, retained unknown categories, unit
and currency scaling, recognized special text, invalid values, relationship
cardinality, ratios, completeness flags, panel coverage, and the combined
Stage 2 orchestrator.

The refreshed 27-workbook integration target is:

- 27 validated workbook mappings;
- 285 descriptor rows retained, including 280 meaningful rows;
- 289 cost rows retained, including 283 meaningful rows;
- 283 cost relationship rows;
- 267 relationships matched with denominators, 7 matched without
  denominators, 9 without descriptor matches, and no ambiguous relationships;
- 265 positive installed denominators and 265 positive serviced denominators;
- 260 eligible routine, non-routine, and total ratios for each denominator
  type; and
- complete coverage for all four businesses from 2019-20 through 2023-24.

The read-only integration check meets all of these row, relationship, ratio,
and panel targets. `extraction_complete`, `stage2a_complete`, and
`panel_complete` are true. `stage2b_complete` remains false for one preserved
AusNet Transmission 2019-20 descriptor row: it reports a serviced quantity of
zero but has no child category, measure, or source unit. The row is retained
and reported as `unresolved_category_hierarchy` and `missing_unit` rather than
being silently deleted, assigned to a category, or treated as dashboard-ready.

The `.agents/cost_descriptor_matches.csv` file is review evidence only and is
not an input to production code.

#### Stage 2 standardisation entry point

The file-based Stage 2 interface is a thin wrapper around
`prepare_rin_maintenance`:

```text
python -m scripts.standardize_rin_maintenance \
  --input-dir data/processed \
  --manifest data/rin_manifest.csv \
  [--output-dir data/standardize] \
  [--config config/rin_maintenance_standardization.json] \
  [--overwrite]
```

`--input-dir` must contain the fixed Stage 1 descriptor, cost, and run-report
CSVs. `data/standardize` is the default output directory, although notebook
experiments and tests may supply another directory. The output directory
cannot equal or be nested inside the Stage 1 input directory.

The entry point writes:

- `rin_maintenance_descriptor_standardized.csv`;
- `rin_maintenance_cost_standardized.csv`;
- `rin_maintenance_workbook_mapping.csv`;
- `rin_maintenance_cost_descriptor_relationships.csv`;
- `rin_maintenance_issues.csv`; and
- `rin_maintenance_stage2_summary.json`.

Every CSV is UTF-8 and excludes the pandas index. The JSON summary records the
four independent completeness flags, overall `pipeline_complete`, row and
issue counts, relationship-status counts, and installed- and serviced-ratio
status counts. It is published last so file-based consumers can treat it as
the durable description of the artifact set.

The entry point validates paths, required inputs, configuration, and output
collisions before processing. It reads the four input CSVs, calls
`prepare_rin_maintenance`, stages the complete artifact set, publishes the
five data artifacts, and publishes the JSON summary last.

Exit codes distinguish processing success from analytical completeness:

- `0` means extraction, Stage 2A, Stage 2B, and panel completeness are all
  true;
- `1` means usable outputs were saved but at least one completeness flag is
  false; and
- `2` means setup, input reading, configuration, processing, collision, or
  output writing failed.

Without `--overwrite`, any existing member of the Stage 2 artifact set stops
the run before processing. Nonfatal warnings and explicitly classified
unmatched relationships remain in the outputs. With the current 27-workbook
data, the known AusNet Transmission 2019-20 anomaly produces usable outputs
and exit `1`; it must not be mistaken for a fully standardised Power BI input.

## Stage 3 - Create the consolidated Power BI data model

### Purpose

Stage 3 reads the persistent Stage 2 artifacts under `data/standardize` and
uses their standardised data and enriched acquisition metadata to create a
small star model under `data/models`. In plain terms, Python resolves workbook
irregularities, category identities, units, table relationships, and source
exceptions before Power BI is asked to calculate or display comparisons.

`data/standardize` remains the detailed Stage 2 evidence. `data/models`
contains the narrower, stable tables intended for Power BI.

### Workflow

```text
read all six stage-2 artifacts
    -> verify the business and AER metadata enriched in stage 2A
    -> verify reporting-period and business coverage
    -> build shared business, period, category, metric, and workbook dimensions
    -> reshape descriptor metrics to a long fact table
    -> retain maintenance expenditure and matched denominators in a cost fact
    -> preserve unresolved rows in the model issues output
    -> verify declared fact-table grains and foreign keys
    -> publish Power BI model tables and the model summary
```

### MVP star-model contract

The MVP model uses shared dimensions rather than joining the descriptor and
cost tables into one mixed-grain table:

```text
dim_business -------------------+
dim_reporting_period -----------+
dim_maintenance_category -------+--> fact_descriptor_metric
dim_metric ---------------------+

dim_business -------------------+
dim_reporting_period -----------+--> fact_maintenance_cost
dim_maintenance_category -------+
```

The category key combines the standard maintenance activity ID and standard
asset ID. A child asset ID is not sufficient by itself because the same child
can occur under different parent activities. The category dimension is built
from the union of descriptor and cost categories so descriptor-only and
cost-only records remain visible.

The dimensions are:

- `dim_business.csv`, containing stable business IDs and display names;
- `dim_reporting_period.csv`, containing period start and end years, sort
  order, and an `is_common_panel` flag;
- `dim_maintenance_category.csv`, containing the contextual activity-asset
  key, IDs, labels, source-table presence flags, and display order;
- `dim_metric.csv`, containing the five descriptor metric IDs, labels, groups,
  and display order; and
- `dim_source_workbook.csv`, retaining the validated workbook-to-manifest
  relationship, AER URLs, business, period, and extraction metadata.

`fact_descriptor_metric.csv` has one row for each meaningful, resolved
business-period-category-metric combination. It reshapes these five Stage 2
descriptor fields into a single metric value:

- asset quantity at year end;
- quantity inspected or maintained;
- average asset age;
- inspection cycle; and
- maintenance cycle.

The fact retains the standard value, standard unit, factual value status,
submitted source value, workbook, worksheet, and source row. Blank and
recognised-special metric statuses remain present rather than being converted
to zero or dropped. Its declared grain is unique across business, reporting
period, contextual maintenance category, and metric.

`fact_maintenance_cost.csv` has one row for each meaningful standardised cost
record. It is built from the Stage 2 cost-descriptor relationship table so
matched, denominator-less, and unmatched expenditure records remain visible.
It retains routine, non-routine, and total nominal AUD expenditure; installed
and serviced denominators; units and statuses; relationship status; and cost
and descriptor source lineage. Its declared grain is unique across business,
reporting period, and contextual maintenance category.

The six Stage 2 row-ratio columns are not published in the Power BI-facing
fact. Power BI must calculate ratios as the sum of an eligible expenditure
numerator divided by the sum of its compatible denominator, not as an average
of row ratios. A ratio must remain within a compatible category and denominator
unit; counts and kilometres must never be added together.

All available reporting periods remain in the model. `is_common_panel` is true
for periods represented by every model business, allowing cross-business pages
to default to the balanced five-year panel while preserving older history.

### Known exception and completeness policy

Meaningful Stage 2 rows without a resolved contextual category are not assigned
to an invented `Unknown` category. They are excluded from analytic facts,
retained with source lineage in `rin_maintenance_model_issues.csv`, and counted
in the model summary. Empty template rows remain available in Stage 2 but do
not become fact records.

For the current data, this policy affects one AusNet Transmission 2019-20
descriptor row. The submitted row contains an inspected or maintained quantity
of zero but no child category, measure, or source unit. Excluding it does not
change a standard numeric total because Stage 2 could not establish its unit,
but the omission remains explicit.

`rin_maintenance_model_summary.json` separates successful model construction
from source-pipeline completeness. It records the Stage 2 completeness flags,
`model_build_complete`, `source_pipeline_complete`, `model_complete`, common
panel periods, row and issue counts, excluded source rows, and relationship
status counts. The current model is usable with a disclosed exception but is
not labelled complete.

### Stage 3 model-building entry point

The file-based Stage 3 interface is:

```text
python -m scripts.build_rin_maintenance_model \
  --input-dir data/standardize \
  [--output-dir data/models] \
  [--overwrite]
```

The input directory must contain the complete fixed Stage 2 artifact set:

- `rin_maintenance_descriptor_standardized.csv`;
- `rin_maintenance_cost_standardized.csv`;
- `rin_maintenance_workbook_mapping.csv`;
- `rin_maintenance_cost_descriptor_relationships.csv`;
- `rin_maintenance_issues.csv`; and
- `rin_maintenance_stage2_summary.json`.

The entry point validates paths, the Stage 2 summary, input contracts, output
collisions, dimension keys, fact grains, and foreign-key coverage. It stages
all outputs, publishes the CSV artifacts, and publishes the JSON summary last.
The output directory cannot equal or be nested inside the Stage 2 input
directory. Existing outputs are not replaced unless `--overwrite` is supplied.

Exit codes are:

- `0` when the model is built and every upstream completeness flag is true;
- `1` when usable model outputs were saved but an upstream completeness flag
  or disclosed source exception keeps `model_complete` false; and
- `2` when setup, input reading, contract validation, model construction,
  collision handling, or output writing fails.

The CLI uses concise `[model]` progress messages. It does not standardise data,
repair unresolved source meaning, calculate dashboard measures, or create a
Power BI file.

### Verification and acceptance

Fabricated-DataFrame tests must verify:

- dimension keys are stable and unique;
- the contextual category dimension uses the union of both facts;
- source-only, cost-only, and shared categories remain present;
- descriptor values reshape to the five configured metric rows without
  changing source values or statuses;
- cost rows retain unmatched relationships and valid denominators;
- no precomputed row-ratio column reaches the cost fact;
- unresolved meaningful rows remain in model issues and not analytic facts;
- empty template rows do not become fact records;
- fact grains contain no unintended duplicates;
- every fact foreign key resolves to its dimension;
- the common-panel flag is derived from business-period coverage;
- complete and incomplete Stage 2 summaries produce exit codes `0` and `1`;
  and
- setup, collision, validation, and writing failures return exit code `2`
  without presenting partial files as a complete model.

Power BI must consume these model outputs rather than reading irregular
workbooks, canonical Stage 1 CSVs, or detailed Stage 2 tables directly.

## Stage 4 - Develop the Power BI dashboard

### Purpose

Stage 4 will present the cross-business maintenance metrics and insights in a
Power BI `.pbix` file. Power BI will be responsible for the data model
relationships, calculations used by visuals, filters, and dashboard layout. It
will not be responsible for repairing source workbook structure or guessing
units.

### Power BI loading workflow

```text
run the Stage 3 model-building entry point
    -> review the model summary and disclosed issues
    -> import each model CSV separately
    -> import and flatten the model-summary JSON
    -> assign Power BI data types and display sorting
    -> create one-to-many dimension-to-fact relationships
    -> define documented measures
    -> build and validate the dashboard pages
```

First create the Stage 3 artifact set:

```text
python -m scripts.build_rin_maintenance_model \
  --input-dir data/standardize \
  --output-dir data/models
```

Review `rin_maintenance_model_summary.json` and
`rin_maintenance_model_issues.csv` before opening Power BI. Exit `1` currently
means that usable model outputs were written with the disclosed AusNet
Transmission exception; it does not mean model construction failed.

In Power BI Desktop, use **Get Data -> Text/CSV** to import each model CSV
separately. The files have different schemas, so the Folder connector is not
needed for this fixed artifact set. Use **Get Data -> JSON** to import
`rin_maintenance_model_summary.json`, then flatten its required completeness
and publication fields into a one-row `model_status` table for the data-quality
page.

Assign Power BI data types deliberately:

- IDs, labels, reporting periods, statuses, and units are text;
- sort orders and source rows are whole numbers;
- descriptor values, quantities, and expenditure are decimal numbers; and
- panel, presence, and completeness flags are true/false values.

Configure these display orders:

- sort `reporting_period` by `period_sort_order`;
- sort maintenance categories by `maintenance_category_sort_order`; and
- sort descriptor metrics by `metric_sort_order`.

Create one-to-many, single-direction relationships from:

- `dim_business` to both fact tables using `business_id`;
- `dim_reporting_period` to both fact tables using `reporting_period`;
- `dim_maintenance_category` to both fact tables using
  `maintenance_category_key`;
- `dim_metric` to `fact_descriptor_metric` using `metric_id`; and
- `dim_source_workbook` to both fact tables and
  `rin_maintenance_model_issues` using `source_workbook`.

Do not directly relate `fact_descriptor_metric` to
`fact_maintenance_cost`. Do not create additional relationships from business
or reporting-period dimensions through `dim_source_workbook`, because that
would introduce alternative filter paths. Avoid bidirectional filtering unless
a later, documented dashboard requirement demonstrates that it is necessary.

Technical keys and source-lineage fields may be hidden from ordinary report
views after relationships are verified. They must remain in the model for
drill-through, source reconciliation, and issue investigation.

### MVP dashboard pages and analytical questions

The first dashboard should contain four pages aligned with the analytical
questions in `docs/rin_maintenance_data_guide.md`.

#### 1. Overview

This page should answer:

- How has maintenance expenditure changed by business and reporting period?
- Is a change persistent or concentrated in one period?
- Which maintenance activities explain the largest reported expenditure?
- How has the routine and non-routine maintenance mix changed?

Suggested visuals are:

- ✅cards for total, routine, and non-routine maintenance expenditure;
- ✅a line chart of total expenditure by reporting period, with business as the
  legend;
- ✅a 100% stacked column chart of routine and non-routine expenditure share;
- a clustered bar chart of expenditure by maintenance activity; and
- slicers for business, reporting period, maintenance activity, maintenance
  category, and common-panel membership.

All expenditure visuals must identify the figures as nominal AUD because no
inflation adjustment has been applied.

#### 2. Business and unit-cost comparison

This page should answer:

- Which maintenance activities explain differences between businesses?
- What is expenditure per compatible installed asset, kilometre, or other
  reported unit?
- What is expenditure per compatible serviced unit?
- Is a change associated mainly with work volume or expenditure per unit?

Suggested visuals are:

- a clustered bar chart of expenditure by business for the selected category;
- a line chart of expenditure per installed unit over time;
- a line chart of expenditure per serviced unit over time;
- a combo chart with expenditure as columns and a compatible quantity as the
  line; and
- a detail matrix containing business, category, expenditure, denominator
  value, denominator unit, and relationship status.

Unit-cost visuals must use only records with compatible approved denominators,
remain within one contextual category and unit, and return blank when a valid
denominator is unavailable. Power BI must calculate an aggregate unit cost as
the sum of eligible expenditure divided by the sum of its compatible quantity.
It must never average source-row ratios.

#### 3. Maintenance context

This page should answer:

- Has the reported asset population grown or contracted?
- How much of the relevant asset population was inspected or maintained?
- Are expenditure changes accompanied by changes in reported asset or activity
  quantities?
- Do average age, inspection cycles, or maintenance cycles coincide with
  expenditure changes?

Suggested visuals are:

- a line chart of asset quantity and serviced quantity over time;
- a column chart of inspection or maintenance coverage;
- a scatter chart of average asset age against non-routine expenditure or an
  eligible unit-cost measure;
- a line chart of inspection and maintenance cycles over time; and
- tooltips containing business, category, unit, reporting period, and source
  workbook.

Age and cycle visuals should normally require a single maintenance category.
Combining unrelated asset groups into one unweighted average would be
misleading. These visuals describe contextual associations and must not imply
that asset age or maintenance frequency caused an expenditure outcome.

#### 4. Data quality and definitions

This page should answer:

- Which business-periods, categories, or metrics are missing?
- Which categories are business-specific or available in only one fact table?
- Which cost records lack a compatible descriptor denominator?
- Which comparisons are direct, unsupported, or affected by a source issue?

Suggested visuals are:

- a business-by-reporting-period matrix with conditional formatting for
  coverage;
- a bar chart of records by relationship status;
- a bar chart of issues by issue code or severity;
- a table containing source workbook, source row, issue, model action, and AER
  landing-page information;
- cards for publication status, excluded source rows, and common-panel
  periods; and
- plain-language definitions and comparison warnings taken from
  `docs/rin_maintenance_data_guide.md`.

The known AusNet Transmission 2019-20 exception must remain visible on this
page while it remains unresolved.

### Measures and comparison safeguards

The MVP should define documented Power BI measures for:

- total, routine, and non-routine maintenance expenditure;
- routine and non-routine expenditure share;
- asset quantity at year end;
- quantity inspected or maintained;
- maintenance or inspection coverage;
- expenditure per installed unit;
- expenditure per serviced unit; and
- year-on-year change.

Measures must preserve these safeguards:

- unit-cost measures return blank for unmatched, denominator-less, or
  incompatible records;
- counts and kilometres are never aggregated into the same denominator;
- average-age and cycle measures are not summed;
- blanks, recognised-special values, and unsupported comparisons are not
  converted to zero;
- nominal expenditure trends are not described as real-price changes;
- the common five-year panel is the default for cross-business comparisons;
  and
- material source, extraction, standardisation, and model limitations are
  disclosed to dashboard users.

### Dashboard verification and acceptance

Before the `.pbix` is accepted:

- every relationship must have the documented one-to-many cardinality and
  single filter direction;
- Power BI fact and dimension row counts must reconcile to
  `rin_maintenance_model_summary.json`;
- the five common-panel periods must be present and sorted chronologically;
- expenditure totals by business and reporting period must reconcile to
  `fact_maintenance_cost.csv`;
- descriptor values for representative categories and metrics must reconcile
  to `fact_descriptor_metric.csv`;
- relationship-status and issue counts must reconcile to the model outputs;
- unit-cost measures must return blank outside a compatible category and unit
  context;
- no visual may silently exclude the known source exception; and
- a non-specialist reader must be able to distinguish reported values, derived
  measures, and data-quality warnings.

The final dashboard must not silently present an incomplete business-period
panel as complete. Missing submissions, failed extractions, and unresolved
standardisation issues must either block final publication or be disclosed
clearly in the dashboard and its supporting documentation.

## Cross-stage traceability and completeness

Track these conditions separately:

1. **Acquisition completeness:** every required manifest record resolves to a
   local workbook or a factual acquisition error.
2. **Extraction completeness:** every supported workbook present in the
   selected raw directory produces both canonical tables.
3. **Enrichment completeness:** every canonical source workbook has one
   validated manifest match and every meaningful row has a resolved parent
   activity or a factual issue.
4. **Standardisation completeness:** every retained source label, unit, and
   value is mapped or explicitly reported, and no blocking numeric, unit, or
   relationship ambiguity remains.
5. **Panel completeness:** each target business has one successfully processed
   workbook for every required reporting period.
6. **Model completeness:** the intended business-period panel and metric set are
   present without unintended duplicates.
7. **Dashboard completeness:** published measures and visuals reconcile to the
   validated model and disclose material gaps.

`run_complete` from the preprocessing CLI describes only extraction
across the supported files found in the selected raw directory. It does not
prove that all required manifest workbooks were downloaded or that every
business has five reporting periods.

The historical feasibility pass identified missing periods for Transgrid
2021-22, Powerlink 2019-20, and AusNet Transmission 2019-20. Targeted
acquisition subsequently filled those cells. This history demonstrates why
author-page discovery and extraction success remain separate from current
panel completeness.

Source traceability must be maintained across stages:

```text
AER landing page
    -> manifest record
    -> immutable raw workbook
    -> canonical extracted row
    -> stage-2A enriched row and activity resolution
    -> stage-2B standardised value
    -> consolidated model record
    -> Power BI measure or visual
```

## Out of scope

- Automating workbook downloads; manual, programmatic, and AI-assisted
  acquisition remain acceptable.
- A recurring comprehensive inventory of workbook formatting, hidden content,
  protection, formulas, or merge counts.
- Normalising categories or applying unit and currency scale factors in the
  stage-1 extractor or preprocessing entry point.
- Persistent intermediate Stage 2A outputs.
- Creating Power BI relationships, measures, visuals, or the `.pbix` file.
- Changing the existing manifest or raw workbooks.
- Adding a logging framework.

## Notes

- standardize `maintenance_asset_[sub]category` to  `asset_category`
