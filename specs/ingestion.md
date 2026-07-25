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

#### 2. Maintain the acquisition manifest

Use `data/rin_manifest.csv` as the inventory of discovered source documents.
Deduplicate records by AER landing-page URL and preserve existing notes when
discovery is rerun.

The manifest should provide or eventually resolve:

- business;
- reporting period or a document title from which it can be derived;
- AER document landing-page URL;
- workbook attachment URL;
- downloaded local filename or path; and
- a factual acquisition error when a landing page or attachment cannot be
  resolved.

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

Current evidence:

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

Stage 1 is complete for a source workbook when:

- the manifest traces its AER landing page or records an acquisition error;
- an acquired workbook remains unchanged under `data/raw/`;
- successful extraction returns both canonical tables; or
- failed extraction retains the workbook and records a clear error without
  producing an unsafe partial workbook result.

The CLI implements the documented scan, output, partial-success, overwrite,
report, and exit-code contracts. All 13 isolated unit tests currently pass
without accessing the ignored raw-workbook directory.

## Stage 2 - Standardise extracted maintenance data

### Purpose

Stage 2 will convert submitted labels, units, and values into explicitly
comparable data while retaining the canonical extraction outputs as evidence.
It begins after stage 1; the heading extractor itself must not perform these
semantic transformations.

### Planned workflow

```text
read the canonical wide descriptor and cost CSVs
    -> read the stage-1 run report
    -> map category and label variations explicitly
    -> apply documented unit and currency scale factors
    -> validate and enforce intended data types
    -> preserve the original submitted labels, units, and values
    -> produce validated standardised tables
```

### Planned data contract and safeguards

Stage 2 must:

- preserve source workbook, sheet, row, reporting period, submitted label,
  submitted unit, and submitted value;
- store standardised values separately rather than overwriting source values;
- distinguish an unmapped category from a missing category;
- apply scale factors explicitly, including legacy `$000's`;
- report nonnumeric metric text rather than silently coercing it to zero; and
- retain additional categories until an explicit mapping decision is made.

Exploratory standardisation may proceed when the stage-1 run is incomplete so
that successful workbooks remain useful. Incompleteness must be carried forward
and must not be mistaken for a complete cross-business panel.

Stage-2 implementation details, mapping tables, final data types, and tests
remain to be specified before code is written.

## Stage 3 - Create the consolidated Power BI data model

### Purpose

Stage 3 will combine the validated standardised data with acquisition metadata
into stable tables that Power BI can load directly. In plain terms, Python
should resolve workbook irregularities and semantic differences before Power BI
is asked to calculate or display comparisons.

### Planned workflow

```text
read validated stage-2 outputs
    -> join business and AER landing-page metadata from the manifest
    -> verify reporting-period and business coverage
    -> reshape metrics where a long-form model is beneficial
    -> attach appropriate source lineage
    -> produce stable Power BI input tables
```

### Planned data contract and Power BI boundary

The consolidated model must:

- identify business and reporting period explicitly;
- use stable metric and category identifiers;
- distinguish descriptor quantities from maintenance expenditure;
- expose normalised values and units while retaining source references;
- prevent duplicate records at its declared level of detail; and
- carry acquisition, extraction, and standardisation completeness information.

The exact table relationships and long-form output contract remain to be
specified. Power BI must consume these validated outputs rather than reading the
irregular workbooks or interpreting the canonical extraction CSVs directly.

## Stage 4 - Develop the Power BI dashboard

### Purpose

Stage 4 will present the cross-business maintenance metrics and insights in a
Power BI `.pbix` file. Power BI will be responsible for the data model
relationships, calculations used by visuals, filters, and dashboard layout. It
will not be responsible for repairing source workbook structure or guessing
units.

### Planned workflow and safeguards

```text
load the validated consolidated tables
    -> define and verify table relationships
    -> create documented calculations and comparison measures
    -> build filters and visuals
    -> disclose material coverage limitations
    -> reconcile displayed totals to the validated Python outputs
```

The final dashboard must not silently present an incomplete business-period
panel as complete. Missing submissions, failed extractions, and unresolved
standardisation issues must either block final publication or be disclosed
clearly in the dashboard and its supporting documentation.

Dashboard requirements, measures, visual design, and `.pbix` verification
remain to be specified before implementation.

## Cross-stage traceability and completeness

Track these conditions separately:

1. **Acquisition completeness:** every required manifest record resolves to a
   local workbook or a factual acquisition error.
2. **Extraction completeness:** every supported workbook present in the
   selected raw directory produces both canonical tables.
3. **Standardisation completeness:** every retained source label, unit, and
   value is mapped or explicitly reported as unresolved.
4. **Model completeness:** the intended business-period panel and metric set are
   present without unintended duplicates.
5. **Dashboard completeness:** published measures and visuals reconcile to the
   validated model and disclose material gaps.

`run_complete` from the preprocessing CLI describes only extraction
across the supported files found in the selected raw directory. It does not
prove that all required manifest workbooks were downloaded or that every
business has five reporting periods.

The feasibility pass identified missing periods for Transgrid 2021-22,
Powerlink 2019-20, and AusNet Transmission 2019-20. These are coverage findings
to locate or document before defensible five-year comparisons. They are
separate from extraction success.

Source traceability must be maintained across stages:

```text
AER landing page
    -> manifest record
    -> immutable raw workbook
    -> canonical extracted row
    -> standardised value
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
- Final stage-2 mapping tables, type enforcement, and reconciliation tests.
- Final long-form tables and the stage-3 Power BI model contract.
- Producing the standardised or consolidated CSV deliverables.
- Creating Power BI relationships, measures, visuals, or the `.pbix` file.
- Changing the existing manifest or raw workbooks.
- Adding a logging framework.
