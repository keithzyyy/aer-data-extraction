# RIN `2.8 Maintenance` workbook structure report

Date inspected: 23 July 2026

## Executive finding

The `2.8 Maintenance` sheets are sufficiently consistent to support one semantic extraction workflow, but not one fixed cell range. The 24 candidate workbooks fall into three main layout profiles:

1. A 2013-14 side-by-side layout, found only in the Transgrid 2013-14 workbook.
2. A stacked layout used from the inspected 2015-16 through 2022-23 workbooks, with formula/protection and values-only subvariants.
3. A revised stacked layout used by Powerlink and Transgrid in 2022-23 and by all four businesses in 2023-24. It moves both tables down one row and modernises unit labels.

A practical extractor should locate the `2.8.1` and `2.8.2` headings, identify their year rows, fill down merged activity labels, and reshape both tables into long form. It should use a special profile for the 2013-14 side-by-side layout and normalize business-specific category labels. It should not rely on Excel's declared used range or one set of absolute row numbers.

There is also a source-coverage issue that must be resolved before the project can satisfy the first scope point. Relative to the latest inspected period, 2019-20 through 2023-24, the manifest is missing Transgrid 2021-22, Powerlink 2019-20, and AusNet Transmission 2019-20.

## Assumptions and limitations

- Every row in `data/rin_manifest.csv` was treated as an inspection candidate even though manual review has not yet been completed.
- All spreadsheet attachments linked from the 24 manifest landing pages were downloaded. Each landing page exposed one `.xlsx` or `.xlsm` attachment; no attachment resolution failed.
- Downloaded files were treated as public AER source material and were not modified.
- Macro-enabled files were inspected as Open XML packages. Macros were not executed.
- Formula cells were read together with their cached values; formulas were not recalculated. This matters mainly for the 2013-14 and 2015-16 to 2017-18 files.
- The dedicated spreadsheet rendering runtime was not exposed in this session. The findings therefore come from read-only Open XML inspection rather than screenshots. Sheet names, cell positions, values, formulas, styles, merged ranges, grouping, protection, and hidden-state attributes were inspected directly.
- "Meaningful rows" below means rows carrying a category label or reported metric. Template identifiers, blank formula placeholders, and presentation-only padding are excluded.
- `$0's` is interpreted as individual dollars and `0's` as individual counts, consistent with formula evidence in the files. The 2013-14 cost header explicitly uses `$000's` and therefore requires a scale factor of 1,000. This interpretation should still be reconciled to any formal AER data dictionary before final transformation.
- This report evaluates structure, not whether the reported figures are substantively correct.

## `workbook_inventory`
Establishes which source workbooks were actually examined and whether coverage is sufficient for scope stage 1.
| Business | Candidate periods inspected | Count | Five-period coverage through 2023-24 | Finding |
|---|---|---:|---|---|
| Transgrid | 2013-14, 2017-18, 2018-19, 2019-20, 2020-21, 2022-23, 2023-24 | 7 | 4/5 | Missing 2021-22; older periods do not replace that gap for a continuous comparison. |
| ElectraNet | 2015-16 through 2023-24, continuous | 9 | 5/5 | Meets and exceeds the five-period requirement. |
| Powerlink | 2020-21 through 2023-24 | 4 | 4/5 | Missing 2019-20. |
| AusNet Transmission | 2020-21 through 2023-24 | 4 | 4/5 | Missing 2019-20. |
| **Total** | 24 candidate workbooks | **24** | — | Three source gaps remain for a complete five-period panel. |

## `maintenance_sheet_inventory`
Shows whether 2.8 Maintenance exists, varies in name, or is absent.

All 24 attachments opened as valid Open XML workbooks and contained a sheet named exactly `2.8 Maintenance`.

No case, spacing, or numbering variants were found in this candidate set.

| Business | Period | AER landing page | Attachment type | Sheet result |
|---|---:|---|---|---|
| Transgrid | 2013-14 | [Source](https://www.aer.gov.au/documents/transgrid-transmission-2013-14-category-analysis-rin-templates) | `.xlsm` | Exact match |
| Transgrid | 2017-18 | [Source](https://www.aer.gov.au/documents/transgrid-2017-18-category-analysis-rin-templates) | `.xlsm` | Exact match |
| Transgrid | 2018-19 | [Source](https://www.aer.gov.au/documents/transgrid-2018-19-category-analysis-rin-templates) | `.xlsx` | Exact match |
| Transgrid | 2019-20 | [Source](https://www.aer.gov.au/documents/transgrid-2019-20-category-analysis-rin-templates) | `.xlsx` | Exact match |
| Transgrid | 2020-21 | [Source](https://www.aer.gov.au/documents/transgrid-2020-21-category-analysis-rin-templates) | `.xlsx` | Exact match |
| Transgrid | 2022-23 | [Source](https://www.aer.gov.au/documents/transgrid-2022-23-category-analysis-rin-templates) | `.xlsx` | Exact match |
| Transgrid | 2023-24 | [Source](https://www.aer.gov.au/documents/transgrid-2023-24-category-analysis-rin-templates) | `.xlsx` | Exact match |
| ElectraNet | 2015-16 | [Source](https://www.aer.gov.au/documents/electranet-2015-16-category-analysis-rin-templates) | `.xlsm` | Exact match |
| ElectraNet | 2016-17 | [Source](https://www.aer.gov.au/documents/electranet-2016-17-category-analysis-rin-templates) | `.xlsm` | Exact match |
| ElectraNet | 2017-18 | [Source](https://www.aer.gov.au/documents/electranet-2017-18-category-analysis-rin-templates) | `.xlsm` | Exact match |
| ElectraNet | 2018-19 | [Source](https://www.aer.gov.au/documents/electranet-2018-19-category-analysis-rin-templates) | `.xlsx` | Exact match |
| ElectraNet | 2019-20 | [Source](https://www.aer.gov.au/documents/electranet-2019-20-category-analysis-rin-templates) | `.xlsx` | Exact match |
| ElectraNet | 2020-21 | [Source](https://www.aer.gov.au/documents/electranet-2020-21-category-analysis-rin-templates) | `.xlsx` | Exact match |
| ElectraNet | 2021-22 | [Source](https://www.aer.gov.au/documents/electranet-2021-22-category-analysis-rin-templates) | `.xlsx` | Exact match |
| ElectraNet | 2022-23 | [Source](https://www.aer.gov.au/documents/electranet-2022-23-category-analysis-rin-templates) | `.xlsx` | Exact match |
| ElectraNet | 2023-24 | [Source](https://www.aer.gov.au/documents/electranet-2023-24-category-analysis-rin-templates) | `.xlsx` | Exact match |
| Powerlink | 2020-21 | [Source](https://www.aer.gov.au/documents/powerlink-2020-21-category-analysis-rin-templates) | `.xlsx` | Exact match |
| Powerlink | 2021-22 | [Source](https://www.aer.gov.au/documents/powerlink-2021-22-category-analysis-rin-templates) | `.xlsx` | Exact match |
| Powerlink | 2022-23 | [Source](https://www.aer.gov.au/documents/powerlink-2022-23-category-analysis-rin-templates) | `.xlsx` | Exact match |
| Powerlink | 2023-24 | [Source](https://www.aer.gov.au/documents/powerlink-2023-24-category-analysis-rin-templates) | `.xlsx` | Exact match |
| AusNet Transmission | 2020-21 | [Source](https://www.aer.gov.au/documents/ausnet-services-transmission-2020-21-category-analysis-rin-templates) | `.xlsx` | Exact match |
| AusNet Transmission | 2021-22 | [Source](https://www.aer.gov.au/documents/ausnet-services-transmission-2021-22-category-analysis-rin-templates) | `.xlsx` | Exact match |
| AusNet Transmission | 2022-23 | [Source](https://www.aer.gov.au/documents/ausnet-services-transmission-2022-23-category-analysis-rin-templates) | `.xlsx` | Exact match |
| AusNet Transmission | 2023-24 | [Source](https://www.aer.gov.au/documents/ausnet-services-transmission-2023-24-category-analysis-rin-templates) | `.xlsx` | Exact match |

One Transgrid 2018-19 attachment has `.XLSM.xlsx` within its published filename, but the downloaded file is a valid `.xlsx` Open XML package.

## `sheet_structure_comparison`

Provides the main structural comparison.

Notation: `S/H/Y/D` means section-heading row, column-header row, reporting-year row, and meaningful data-row range. Formula counts include title/year formulas and formula placeholders, not only reported metrics.

| Business | Period | Meaningful/content extent | `2.8.1` S/H/Y/D | `2.8.2` S/H/Y/D | Descriptor/cost rows | Formula cells | Merges | Protected |
|---|---:|---|---|---|---:|---:|---:|---|
| Transgrid | 2013-14 | A1:N43 | 7/10/11/12-22 | 7/10/11/12-23 | 11/12 | 7 | 14 | Yes |
| Transgrid | 2017-18 | B1:J60; blank formulas extend to row 81 | 8/10/11/12-22 | 46/48/49/50-60 | 11/11 | 76 | 16 | Yes |
| Transgrid | 2018-19 | B1:J60 | 8/10/11/12-22 | 46/48/49/50-60 | 11/11 | 0 | 16 | No |
| Transgrid | 2019-20 | B1:J61 | 8/10/11/12-22 | 46/48/49/50-61 | 11/12 | 0 | 16 | No |
| Transgrid | 2020-21 | B1:J61 | 8/10/11/12-22 | 46/48/49/50-61 | 11/12 | 0 | 16 | No |
| Transgrid | 2022-23 | B1:J62 | 9/11/12/13-23 | 47/49/50/51-62 | 11/12 | 0 | 16 | No |
| Transgrid | 2023-24 | B1:J61 | 9/11/12/13-23 | 47/49/50/51-61 | 11/11 | 0 | 16 | No |
| ElectraNet | 2015-16 | B1:J59; blank formulas extend to row 81 | 8/10/11/12-21 | 46/48/49/50-59 | 10/10 | 94 | 16 | Yes |
| ElectraNet | 2016-17 | B1:J59; blank formulas extend to row 81 | 8/10/11/12-21 | 46/48/49/50-59 | 10/10 | 76 | 16 | Yes |
| ElectraNet | 2017-18 | B1:J60; blank formulas extend to row 81 | 8/10/11/12-22 | 46/48/49/50-60 | 11/11 | 74 | 16 | Yes |
| ElectraNet | 2018-19 | B1:J59 | 8/10/11/12-21 | 46/48/49/50-59 | 10/10 | 0 | 16 | No |
| ElectraNet | 2019-20 | B1:J59 | 8/10/11/12-21 | 46/48/49/50-59 | 10/10 | 0 | 16 | No |
| ElectraNet | 2020-21 | B1:J59 | 8/10/11/12-21 | 46/48/49/50-59 | 10/10 | 0 | 16 | No |
| ElectraNet | 2021-22 | B1:J59 | 8/10/11/12-21 | 46/48/49/50-59 | 10/10 | 0 | 16 | No |
| ElectraNet | 2022-23 | B1:J59 | 8/10/11/12-21 | 46/48/49/50-59 | 10/10 | 0 | 16 | No |
| ElectraNet | 2023-24 | B1:J60 | 9/11/12/13-22 | 47/49/50/51-60 | 10/10 | 0 | 16 | No |
| Powerlink | 2020-21 | B1:J60 | 8/10/11/12-22 | 46/48/49/50-60 | 11/11 | 0 | 16 | No |
| Powerlink | 2021-22 | B1:J60 | 8/10/11/12-22 | 46/48/49/50-60 | 11/11 | 0 | 16 | No |
| Powerlink | 2022-23 | B1:J61 | 9/11/12/13-23 | 47/49/50/51-61 | 11/11 | 0 | 16 | No |
| Powerlink | 2023-24 | B1:J61 | 9/11/12/13-23 | 47/49/50/51-61 | 11/11 | 0 | 16 | No |
| AusNet Transmission | 2020-21 | B1:J59 | 8/10/11/12-21 | 46/48/49/50-59 | 10/10 | 0 | 16 | No |
| AusNet Transmission | 2021-22 | B1:J59 | 8/10/11/12-21 | 46/48/49/50-59 | 10/10 | 0 | 16 | No |
| AusNet Transmission | 2022-23 | B1:J59 | 8/10/11/12-21 | 46/48/49/50-59 | 10/10 | 0 | 16 | No |
| AusNet Transmission | 2023-24 | B1:J60 | 9/11/12/13-22 | 47/49/50/51-60 | 10/10 | 0 | 16 | No |

### Shared table meaning

For the stacked layouts, `2.8.1` consistently carries:

- Column B: maintenance activity.
- Column C: maintenance asset category.
- Column D: asset-quantity measure.
- Column E: unit.
- Columns F-J: asset quantity at year end, quantity inspected/maintained, average age, inspection cycle, and maintenance cycle.

`2.8.2` consistently carries:

- Column B: asset/maintenance activity.
- Column C: asset subcategory.
- Column F: routine maintenance expenditure.
- Column G: non-routine maintenance expenditure.

The 2013-14 layout has the same semantic content but places `2.8.1` in A:I and `2.8.2` in J:N on the same rows. It also contains explicit template record identifiers in columns A and J.

### Numeric formats

- Modern stacked templates mainly use accounting-style integer and one-decimal formats. The format affects display precision but not the underlying numeric value.
- ElectraNet 2015-16 uses a wider mixture of integer, one-, two-, and three-decimal formats.
- The 2013-14 template primarily displays three decimal places, consistent with quantities and expenditures stored in thousands.
- Formula-heavy files retain cached numeric results. For example, ElectraNet 2015-16 contains expenditure formulas that multiply source amounts by 1,000 before displaying the result.

## `maintenance_label_comparison`

Captures row labels and maintenance categories without prematurely deciding their standardized names.

| Scope | Labels observed | Variants or exceptions | Standardisation implication |
|---|---|---|---|
| Common core | Transmission towers; transmission tower support structures; conductors; transmission cables; switchbays; power transformers; substation property; SCADA/network control; protection systems | Capitalisation and punctuation vary slightly. | A controlled label map is sufficient; retain the original label for lineage. |
| AusNet Transmission | Common core plus an `Other maintenance activity` heading | No named column-C subcategory was populated beneath that heading in the inspected sheets. | Permit a null asset subcategory rather than dropping the row automatically. |
| ElectraNet | Common core plus right-of-way maintenance | Variants include `Right of way (Row) maintenance`, `RIGHT OF WAY ROW MAINTENANCE`, `Right of Way (Row) Maintenance`, and `ROW MAINTENANCE`. | Normalize these to one right-of-way category using case/punctuation-insensitive matching. |
| Powerlink | Common core plus corridor maintenance and, in some periods, another tower-support row | Variants include `Corridor maintenance (Non vegetation)`, `Corridor maintenance (non veg)`, `Corridor Maintenance (Non-Veg)`, `Transmission Towers Support`, and the 2020-21 typo `Tramsission tower support structures`. | Use an explicit mapping; do not depend on exact spelling. Review whether the extra tower-support row is semantically distinct before combining it with the core tower-support category. |
| Transgrid, modern | Common core plus metering and communications | `Metering`/`Metering Systems` vary. Bushfire Remediation appears as an additional cost-only row in 2019-20, 2020-21, and 2022-23, but not every period. | Descriptor and cost tables cannot be assumed to have identical row counts or a one-to-one row join. |
| Transgrid 2013-14 | Uses `Telecomms Systems`, `Metering Systems`, and a cost-only `TRANSMISSION LINES MAINTENANCE ACCESS TRACKS` row | The cost table has 12 meaningful rows while the descriptor table has 11. | Extract the tables independently and relate records by normalized labels, not row number. |

## `structural_exceptions`

Records presentation-only sections, unusual formulas, merged headers, hidden content, and other exceptions.

| Scope | Exception | Evidence | Extraction impact |
|---|---|---|---|
| All workbooks | Declared used ranges are heavily inflated by formatting. | Most sheets declare `A1:WZV81` or `A1:WZV82`; the 2013-14 sheet declares `A1:XAA59`. Meaningful content is no wider than N and modern content no wider than J. | Do not use the workbook's declared dimension as the extraction boundary. Locate headings and inspect bounded columns instead. |
| All modern layouts | Large presentation/padding band separates the two tables. | Approximately rows 22/23 through 45/46 are blank of meaningful values. | Treat the two sections independently rather than reading one rectangular table. |
| All modern layouts | Data/template rows are grouped at outline level 1. | Group attributes cover the two table regions and unused template rows. No rows are marked hidden. | Grouping is presentational and should not affect extraction. |
| All workbooks | No hidden rows or hidden columns were found on `2.8 Maintenance`. | Hidden row count and hidden column count are zero in all 24 files. | No hidden maintenance records require a separate extraction pass in this candidate set. |
| Modern layouts | Sixteen merged ranges are used for multi-row headers and activity blocks. | The merge pattern is stable within each stacked template position. | Fill down merged column-B activity labels after reading values; never treat blank cells inside a merge as missing categories. |
| 2013-14 | Tables are side-by-side, include template IDs, and use 14 merges. | Descriptor table A:I; cost table J:N; IDs continue through row 43 despite many blank business fields. | Requires its own coordinate profile and removal of unpopulated template-ID rows. |
| 2013-14 | Cost unit is `$000's`. | Cost header at M9. | Multiply cost values by 1,000 when producing dollar-valued consolidated data, while retaining the original value/unit. |
| 2015-16 to 2017-18 macro workbooks | Numerous formulas and blank formula placeholders extend the apparent content to row 81. | 74-94 formula cells in the ElectraNet files and 76 in Transgrid 2017-18; later rows contain formulas returning blanks. | Use cached values but discard rows with neither a meaningful label nor metric value. Do not infer a data row solely from formula presence. |
| Older protected files | Sheet protection is enabled in Transgrid 2013-14 and 2017-18 and ElectraNet 2015-16 through 2017-18. | `sheetProtection` is present in those files only. | Read-only extraction is unaffected, but an Excel-based process should not rely on modifying or recalculating the source sheets. |
| Template transition | The revised layout is not determined by reporting period alone. | Powerlink and Transgrid use the revised layout in 2022-23; AusNet and ElectraNet still use the earlier layout for 2022-23. | Detect the template from headings/row positions or the template-date cell, not from year alone. |
| Revised template | Unit text and both tables move down one row. | Template-date cells include June/July 2023 or May 2024; descriptor data begins on row 13 and cost data on row 51. | Profile selection must precede extraction. Normalize `number` and legacy `0's` count units. |
| Cross-business comparison | Descriptor and cost row counts differ across businesses and sometimes within one workbook. | Modern candidate workbooks contain 10 or 11 descriptor rows and 10-12 cost rows. | Create separate descriptor and cost records, then standardize categories. Avoid positional joins. |

## `template_groups`

Groups workbooks by actual layout rather than assuming each business or year requires its own parser.

| Template group | Workbooks | Defining structure | Important differences within group |
|---|---|---|---|
| A — legacy side-by-side | Transgrid 2013-14 | Both sections begin on row 7; descriptor A:I and cost J:N; shared year row 11; data begins row 12. | `$000's` cost scaling, record-ID columns, 14 merges, protection, and 7 metadata/year formulas. |
| B1 — stacked, formula/protected | ElectraNet 2015-16 to 2017-18; Transgrid 2017-18 | `2.8.1` section/header/year/data start at 8/10/11/12; `2.8.2` at 46/48/49/50. | 74-94 formulas, blank formula padding through row 81, and sheet protection. |
| B2 — stacked, values-only | AusNet 2020-21 to 2022-23; ElectraNet 2018-19 to 2022-23; Powerlink 2020-21 to 2021-22; Transgrid 2018-19 to 2020-21 | Same row structure as B1, generally 16 merges, direct cost header `$0's`. | Business-specific category counts and labels; no worksheet formulas or protection. |
| C — revised stacked | Powerlink and Transgrid 2022-23; all four businesses 2023-24 | `2.8.1` at 9/11/12/13; `2.8.2` at 47/49/50/51; direct cost header `$`; count unit generally `number`. | Transgrid retains some `0's` unit labels for SCADA/protection/other categories. Business-specific extra rows remain. |

## `extraction_recommendations`

Concludes whether one extraction method is sufficient or whether layout-specific mappings are needed.

| Recommendation | Proposed handling | Effect on later scope stages |
|---|---|---|
| Use one semantic extractor with three profiles | Detect `2.8.1` and `2.8.2` headings. Select side-by-side or stacked parsing based on their relative coordinates; derive the data start from the year row. | Keeps scope stage 1 maintainable without building a parser per workbook. |
| Never trust declared used range | Restrict inspection to expected columns and stop meaningful data at the next section, at the last labelled/value row, or at a validated blank boundary. | Prevents thousands of formatted empty columns from contaminating standardisation and Power BI refreshes. |
| Extract descriptor and cost sections separately | Produce independent records for descriptor metrics and cost metrics; do not join by worksheet row. | Supports categories that exist in only one section and avoids losing Transgrid cost-only items. |
| Fill merged labels downward | After reading, forward-fill maintenance activity/category labels only within the detected section. | Produces complete category keys for the consolidated model without altering source files. |
| Reshape metric columns to long form | Convert asset quantity, inspected/maintained, average age, inspection cycle, maintenance cycle, routine cost, and non-routine cost into named metric rows. | A long fact table is easier to standardize and lets Power BI use one metric/value pattern. |
| Preserve units and apply explicit scale factors | Store `source_unit`, `standard_unit`, and `scale_factor`. Normalize `0's`/`number` to count and `$0's`/`$` to AUD; apply 1,000 only to explicit `$000's`. | Prevents silent magnitude errors in cross-year charts and aggregated Power BI measures. |
| Map category variants explicitly | Maintain a small reference table containing original label, normalized label, business, effective period, and review note. | Enables like-for-like cross-business comparison while preserving exceptions for audit. |
| Use cached values for formula workbooks and retain formula metadata | Read cached values for extraction; record whether the source cell contained a formula. Flag missing cached results rather than recalculating macro-enabled source files automatically. | Preserves reproducibility and prevents older formulas or named-range dependencies from breaking later refreshes. |
| Retain source lineage | For every normalized value, store business, reporting period, workbook filename, sheet name, section, and source cell. | Makes consolidated Power BI figures traceable back to the exact AER submission. |
| Validate by expected structure, not only non-empty output | Check sheet name, both section headings, year consistency, allowed columns, row-count ranges, numeric conversion, and unit recognition. | Stops structurally incomplete ingestion from creating misleading dashboard gaps. |
| Complete the five-period source panel before final modelling | Locate Transgrid 2021-22, Powerlink 2019-20, and AusNet Transmission 2019-20 or document why no submission is available. | Required for scope stage 1 and for defensible five-year comparisons in stages 3 and 4. |

### Suggested normalized outputs

Descriptor metrics:

```text
business
reporting_period
maintenance_activity
asset_category
measure
source_unit
standard_unit
metric_name
source_value
scale_factor
value_standard
source_workbook
source_sheet
source_cell
source_was_formula
```

Cost metrics:

```text
business
reporting_period
maintenance_activity
asset_subcategory
maintenance_type
source_currency_unit
source_value
scale_factor
value_aud
source_workbook
source_sheet
source_cell
source_was_formula
```

These can later be combined into one Power BI-friendly long fact table if desired, but keeping descriptor and cost extraction separate initially will make validation easier.

## Scope implications

1. **Extract:** the files are structurally viable for automated extraction, provided the three layout profiles and source-coverage gaps are handled.
2. **Standardise:** unit scaling and business-specific label mapping are more consequential than cell-position differences.
3. **Consolidate for Power BI:** a long metric/value model with explicit business, period, category, unit, and lineage fields will accommodate all inspected layouts.
4. **Dashboard:** comparisons will be unsafe until the missing business-period submissions are resolved and category mappings distinguish true equivalence from similarly named but potentially different activities.
