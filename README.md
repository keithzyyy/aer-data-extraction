# AER Transmission Maintenance Analysis

This project extracts, standardises, models, and presents maintenance data from
semi-structured Category Analysis Regulatory Information Notice (RIN)
workbooks published by the
[Australian Energy Regulator](https://www.aer.gov.au/).

The analysis uses the `2.8 Maintenance` worksheet submitted by:

- AusNet Transmission
- ElectraNet
- Powerlink
- Transgrid

The primary comparison panel contains all four businesses for the five
reporting periods from 2019–20 through 2023–24. Additional available history is
retained separately. The current local acquisition inventory contains 27
workbooks.

## Project scope

The project implements four stages:

1. Extract maintenance data from the submitted RIN workbooks.
2. Standardise categories, units, and values for cross-business comparison.
3. Create a consolidated data model suitable for Power BI.
4. Develop a Power BI dashboard presenting key metrics, context, and data
   limitations.

```text
AER workbook discovery and acquisition
    ↓
Heading-driven workbook extraction
    ↓
Category, unit, and value standardisation
    ↓
Power BI fact and dimension tables
    ↓
Interactive Power BI dashboard
```

## Power BI dashboard

The MVP dashboard is available in
[`aer-data-model.pbix`](aer-data-model.pbix). It contains three report pages.

### Expenditure

The Expenditure page presents maintenance expenditure in nominal Australian
dollars. It includes:

- reconciled total, routine, and non-routine expenditure;
- total expenditure trends by business and reporting period;
- the routine and non-routine expenditure mix; and
- total expenditure by maintenance activity.

Users can filter the page by common five-year-panel membership, reporting
period, business, maintenance activity, and maintenance asset. Routine and
non-routine values shown with the total use the same eligible source rows, so
the components reconcile to total maintenance expenditure.

### Descriptor context

The Descriptor page provides operational context from the metrics submitted in
table `2.8.1`. It includes:

- asset quantity at year end;
- average asset age;
- total expenditure per installed unit; and
- the ratio of reported inspected or maintained quantity to year-end asset
  quantity.

The page requires one exact maintenance activity and asset selection. This
prevents unrelated asset groups and incompatible units from being combined.
Business and reporting-period selections can then be used to compare the
selected category across businesses and over time.

The reported maintained-quantity ratio is contextual. It should not
automatically be interpreted as the percentage of unique assets serviced,
because a submitted quantity can represent repeated work during a period.
Unit-cost figures are calculated only where the cost record has a unique,
compatible descriptor denominator.

### Data quality

The Data Quality page makes model limitations visible rather than silently
removing them. It includes:

- the number of cost records by cost-to-descriptor relationship status; and
- a traceable issue table containing severity, issue code, explanation, model
  action, source workbook, and source row.

This page distinguishes cost records with a supported denominator from records
without a descriptor match or usable denominator. The known AusNet
Transmission 2019–20 source exception remains disclosed, while its unresolved
row is excluded from analytic fact tables.

## Interpretation boundaries

Important limitations include:

- expenditure is nominal AUD and has not been adjusted for inflation;
- asset quantities can use different units, including counts and kilometres;
- counts, kilometres, and other denominator types must not be combined;
- routine and non-routine source components can contain blanks;
- a source blank is not automatically equivalent to zero;
- average age and maintenance cycles provide context but do not establish
  causality;
- a missing descriptor match does not invalidate a submitted cost record, but
  it prevents a supported unit-cost calculation; and
- AER author pages are useful discovery sources but are not assumed to be an
  exhaustive acquisition inventory.

See
[`docs/rin_maintenance_data_guide.md`](docs/rin_maintenance_data_guide.md)
for a plain-language explanation of the source tables and analytical
questions.

## Repository structure

```text
.
├── aer-data-model.pbix
├── config/
├── data/
│   ├── rin_manifest.csv
│   ├── raw/
│   ├── processed/
│   ├── standardize/
│   └── models/
├── docs/
├── notebooks/
├── scripts/
├── specs/
├── src/
└── tests/
```

| Path | Purpose |
|---|---|
| `aer-data-model.pbix` | Power BI semantic model and three-page dashboard. |
| `config/` | Author-page, heading-schema, and standardisation configuration. |
| `data/rin_manifest.csv` | Acquisition inventory linking businesses, reporting periods, AER pages, and local filenames. |
| `data/raw/` | Immutable downloaded RIN workbooks. This directory is intentionally not committed. |
| `data/processed/` | Stage 1 canonical wide tables and workbook extraction report. |
| `data/standardize/` | Stage 2 enriched and standardised tables, relationships, issues, and completeness summary. |
| `data/models/` | Stage 3 fact tables, dimensions, model issues, and summary consumed by Power BI. |
| `src/` | Reusable discovery, extraction, standardisation, and model-building logic. |
| `scripts/` | Command-line entry points for the reproducible pipeline stages. |
| `notebooks/` | Exploratory inspection and notebook-based validation. |
| `specs/` | Pipeline design, contracts, failure policies, and acceptance evidence. |
| `docs/` | Domain and interpretation guidance. |
| `tests/` | Unit tests using fabricated inputs and mocked file boundaries. |

## Reproducing the pipeline

Install the Python dependencies:

```powershell
python -m pip install -r requirements.txt
```

### 1. Discover workbook metadata

```powershell
python -m scripts.discover_rin_workbooks `
  --config-path config/author_pages.json `
  --manifest data/rin_manifest.csv
```

Discovery updates the manifest from configured AER author pages. Because those
pages are not exhaustive, required business-period coverage must still be
checked against the manifest.

Download the manifest workbooks into `data/raw/`. Acquisition can be manual,
programmatic, or AI-assisted, but downloaded source workbooks remain
immutable.

### 2. Extract the maintenance tables

```powershell
python -m scripts.preprocess_rin_maintenance `
  --raw-dir data/raw `
  --output-dir data/processed `
  --schema config/rin_maintenance_expected_schema.json `
  --overwrite
```

This stage finds the `2.8.1` descriptor and `2.8.2` cost tables by their
semantic headings rather than fixed worksheet coordinates.

### 3. Standardise the extracted data

```powershell
python -m scripts.standardize_rin_maintenance `
  --input-dir data/processed `
  --manifest data/rin_manifest.csv `
  --output-dir data/standardize `
  --config config/rin_maintenance_standardization.json `
  --overwrite
```

This stage reconciles business metadata, resolves omitted parent activity
labels, standardises categories and units, and establishes supported
cost-to-descriptor relationships.

### 4. Build the Power BI model

```powershell
python -m scripts.build_rin_maintenance_model `
  --input-dir data/standardize `
  --output-dir data/models `
  --overwrite
```

The resulting fact and dimension CSVs are the stable inputs to the Power BI
dashboard.

## Testing

Run the test suite with:

```powershell
python -m unittest discover -s tests -v
```

The tests cover extraction batching, manifest reconciliation, category and
unit standardisation, relationship safeguards, completeness flags, and Power
BI model construction.

## Further documentation

- [`specs/ingestion.md`](specs/ingestion.md) — complete pipeline specification
- [`docs/rin_maintenance_data_guide.md`](docs/rin_maintenance_data_guide.md) —
  source-table meaning and analytical guidance
- [`config/rin_maintenance_expected_schema.json`](config/rin_maintenance_expected_schema.json) —
  semantic workbook-heading configuration
- [`config/rin_maintenance_standardization.json`](config/rin_maintenance_standardization.json) —
  category, unit, and value-standardisation policy
