# RIN `2.8 Maintenance` data guide

## Purpose

This guide explains, in plain language, what the figures in the two
`2.8 Maintenance` tables represent and what an energy analyst or consultant
might reasonably investigate with them.

It bridges:

1. the figures extracted from the AER workbooks;
2. the Stage 2 decisions needed to make those figures comparable;
3. the consolidated data model prepared in Python; and
4. the eventual Power BI dashboard.

It is a high-level interpretation guide, not regulatory advice. The submitted
workbook and its accompanying Basis of Preparation remain the primary evidence
for what an individual business reported in a particular year.

## Regulatory context

The Australian Energy Regulator (AER) collected Category Analysis Regulatory
Information Notice (RIN) data to support expenditure assessment and
benchmarking of network service providers. For maintenance operating
expenditure, the AER sought:

- expenditure separated into routine and non-routine maintenance;
- information about the volume of maintenance activity;
- changes in the number and type of assets being serviced;
- asset-age and condition information; and
- inspection and maintenance intervals.

In simple terms, the expenditure table shows how much a business reported
spending, while the descriptor table provides information about the assets and
maintenance activity behind that spending.

The 2014 Category Analysis RIN is now historical, but it remains the relevant
semantic reference for the workbooks covered by this project. The AER's
current expenditure-assessment framework should be consulted for current
regulatory requirements.

## Source hierarchy

Interpret a figure using the following order of authority:

1. **AER Category Analysis RIN:** defines the reporting requirements and key
   terms.
2. **AER transmission template:** shows the intended tables, headings, units,
   and prescribed maintenance categories.
3. **AER explanatory statement:** explains why the information was requested
   and discusses limitations raised during consultation.
4. **Business Basis of Preparation:** explains how a particular business
   sourced, estimated, allocated, and classified its figures.
5. **Submitted workbook:** contains the actual reported labels, units, and
   values for that reporting period.
6. **Project interpretation:** defines standardisation mappings and derived
   analytical measures without changing the submitted evidence.

A Basis of Preparation is especially important when a figure was estimated or
allocated because the business's systems did not record information in the
exact form requested by the AER.

## How the two maintenance tables relate

```text
2.8.1 - assets, activity volumes, age, and cycles
                         +
2.8.2 - routine and non-routine direct expenditure
                         |
                         v
       trends and carefully controlled comparisons
```

The two tables describe related subject matter, but they are not guaranteed to
join row for row. The AER permitted businesses to add material subcategories.
It also allowed additional non-financial subcategories for inspection or
maintenance cycles without requiring the corresponding expenditure to be
split to the same level.

Consequently, a cost category and a descriptor category may be:

- directly comparable;
- comparable only at a broader parent-category level;
- related but based on an approximate volume measure; or
- unsuitable for a cost-per-unit calculation.

Stage 2 standardisation must record that relationship explicitly rather than
matching rows only because their labels look similar.

## Table 2.8.1 - descriptor metrics

Table `2.8.1` describes the assets and maintenance activity associated with
routine and non-routine maintenance. These are mainly non-financial measures.

| Field | Plain-language meaning | Possible analytical use | Important qualification |
| --- | --- | --- | --- |
| Maintenance activity | A broad parent grouping, such as transmission lines or substation maintenance. | Filtering and comparing broad areas of maintenance. | A blank source cell may visually continue a parent label from an earlier row. Stage 2A resolves this from bounded worksheet row context. |
| Maintenance asset category | The more detailed asset or activity to which the descriptor figures relate. | Comparing asset groups and connecting activity information to compatible cost categories. | Businesses may add categories, and similarly named children can occur under different parents. |
| Measure / asset quantity | A description of what is being counted, such as towers, route kilometres, switchbays, or transformers. | Explaining the meaning of the reported quantities and selecting a possible denominator. | This is descriptive metadata, not itself a numeric value. |
| Source unit | The submitted unit and scale, such as `number`, `km`, or `000' km`. | Converting quantities to a consistent unit. | Values cannot be compared or aggregated until the scale is interpreted explicitly. |
| Asset quantity at year end | The population of the relevant assets at the end of the regulatory year. | Tracking changes in the asset base and, where suitable, calculating cost per asset. | For grouped assets, the RIN directs businesses to use the highest-value asset type as the basis. It may therefore not describe every asset represented by the broad category. |
| Quantity inspected / maintained | The number or amount of assets actually inspected or maintained during the year. | Examining maintenance workload or the share of an asset population serviced. | The measure can represent inspection, maintenance, or both according to the row definition. It should not automatically be treated as a uniform measure across categories. |
| Average age of asset group | The reported average age, in years, for the relevant asset basis. | Providing context for trends in activity and expenditure. | An average hides the age distribution, and grouped categories use the highest-value asset type as the basis under the RIN instructions. |
| Inspection cycle | The planned or actual duration between consecutive inspections, expressed as every *n* years. | Understanding how frequently assets are inspected and contextualising inspection cost. | Different assets and tasks can have different cycles. Where several activities exist, the RIN directs reporting of the cycle associated with the highest-cost activity. |
| Maintenance cycle | The planned or actual duration between consecutive maintenance works, expressed as every *n* years. | Understanding planned maintenance frequency. | Some maintenance is condition-based and may not have a fixed numeric cycle. Explanatory source text must not be silently converted to zero. |

### Reading descriptor figures carefully

The descriptor metrics are useful context, but they do not by themselves
measure asset condition, reliability, or maintenance quality. For example:

- an older average asset age does not prove that assets are in poor condition;
- a shorter inspection cycle does not by itself indicate inefficiency;
- a larger maintained quantity may reflect a larger network, a different
  maintenance strategy, or a different definition of the reported measure; and
- a blank value means only that no numeric value was submitted in that cell,
  unless a source document establishes a more specific meaning.

## Table 2.8.2 - cost metrics

Table `2.8.2` reports direct operating expenditure for routine and non-routine
maintenance by maintenance activity and asset subcategory.

| Field | Plain-language meaning | Possible analytical use | Important qualification |
| --- | --- | --- | --- |
| Asset category | The broad maintenance activity under which expenditure is reported. | Comparing expenditure across major maintenance groupings. | A blank source cell can continue the preceding group. Stage 2A resolves this using source-row evidence. |
| Asset subcategory | The detailed asset or maintenance grouping receiving the expenditure. | Detailed cost trends and controlled links to descriptor measures. | Additional business-specific subcategories are valid and must not be discarded merely because they differ from the common template. |
| Source currency unit | The submitted monetary unit and scale, such as `$`, `$0's`, or `$000's`. | Converting expenditure to a consistent monetary unit. | The scale must be applied explicitly before values are summed or compared. |
| Routine maintenance expenditure | Operating expenditure on recurrent or programmed activities undertaken regardless of an individual asset's condition, often at predictable intervals. | Trend analysis, maintenance-mix analysis, and selected unit-cost comparisons. | The business's Basis of Preparation may explain allocation or estimation methods and what direct costs exclude. |
| Non-routine maintenance expenditure | Operating expenditure mainly associated with managing asset condition, correcting defects, or responding to non-routine needs. | Identifying volatility, condition-driven work, and changes in maintenance mix. | The RIN definition includes emergency response. A high value alone does not demonstrate poor performance or inefficiency. |

The RIN definition of maintenance covers operational repair and maintenance of
the transmission system, including testing, investigation, validation, and
correction that do not involve capital expenditure. It excludes activities
whose main purpose is asset replacement or new asset installation. Routine and
non-routine expenditure should therefore not be interpreted as total network
investment.

## What an analyst or consultant may want to know

The following are analytical questions suggested by the reported fields and
the AER's stated use of expenditure and activity data. They are not claims that
the RIN figures alone provide a complete answer.

### Expenditure trends

- How has reported maintenance expenditure changed by business and year?
- Which maintenance activities explain the largest changes?
- Is a change persistent, or is it concentrated in one reporting period?
- How has the mix of routine and non-routine maintenance changed?

### Network scale and maintenance activity

- Has the reported asset population grown or contracted?
- How much of the relevant asset population was inspected or maintained?
- Are changes in expenditure accompanied by changes in asset quantities or
  maintenance activity volumes?

### Selected unit-cost comparisons

- What is the reported expenditure per compatible asset, kilometre, or unit of
  activity?
- Is a change in expenditure driven mainly by changing work volume or changing
  expenditure per unit?
- Are unit-cost patterns materially different across businesses?

These questions require an approved relationship between a cost row and a
descriptor denominator. A mathematically possible division is not necessarily
a meaningful maintenance indicator.

### Asset age and maintenance strategy

- Do older reported asset groups coincide with different inspection or
  maintenance cycles?
- Do changes in inspection frequency help explain changes in routine
  expenditure?
- Does a rise in non-routine expenditure coincide with changes in asset age or
  maintenance activity?

These are contextual associations. They do not establish that age or a
particular maintenance strategy caused the expenditure.

### Data quality and comparability

- Which business-years, categories, or metrics are missing?
- Which values were estimated or allocated?
- Which categories are business-specific?
- Which rows use unusual units or explanatory text instead of a number?
- Which comparisons are direct, approximate, or unsupported?

## Candidate derived measures

| Measure | Illustrative calculation | Use only when |
| --- | --- | --- |
| Routine expenditure share | routine expenditure / total maintenance expenditure | Both expenditure components use the same currency basis and the denominator is non-zero. |
| Non-routine expenditure share | non-routine expenditure / total maintenance expenditure | Both expenditure components use the same currency basis and the denominator is non-zero. |
| Maintenance or inspection coverage | quantity inspected or maintained / asset quantity at year end | The numerator and denominator describe compatible assets in the same unit and the numerator's meaning is clear. |
| Expenditure per asset | compatible expenditure / year-end asset quantity | The cost category has an approved relationship to that asset population. |
| Expenditure per activity unit | compatible expenditure / quantity inspected or maintained | The quantity represents the work underlying the expenditure and uses a compatible unit. |
| Year-on-year change | current standardised value / prior standardised value - 1 | Reporting periods are consecutive and values use the same definition, category mapping, unit, and price basis. |

The source workbooks report nominal expenditure. A time-series comparison in
real terms would require a separately documented inflation adjustment. That is
a later analytical transformation, not part of source extraction.

## Comparison safeguards

Do not:

- add or compare monetary figures before applying their submitted scale;
- treat a blank, text response, or missing category as zero;
- infer a parent maintenance activity from a child label alone;
- assume descriptor and cost subcategories have a one-to-one relationship;
- divide expenditure by the nearest available quantity without an approved
  semantic mapping;
- remove additional categories solely because they are uncommon;
- interpret average asset age as the condition of every asset in the group;
- treat an association between age, cycles, activity, and cost as causation;
- rank a business as efficient or inefficient from these maintenance tables
  alone; or
- hide missing business-years or unresolved standardisation decisions in a
  dashboard.

Network size, terrain, bushfire exposure, asset mix, maintenance policy,
accounting systems, and cost-allocation methods can all affect comparisons.
The AER's broader benchmarking work considers business characteristics and
outputs beyond the two maintenance tables.

## Implications for Stage 2 standardisation

Stage 2 should preserve the submitted evidence and add interpretation beside
it. At a minimum, it should retain or create:

```text
submitted parent and child labels
standardised parent and child labels
submitted value and unit
numeric standardised value and unit
explicit scale factor
mapping and parsing status
business and reporting period
source workbook, sheet, and row
```

Category mapping should use the table, resolved parent activity, and submitted
child category together. Unit conversion should preserve the original value
and record the applied scale factor. Explanatory text should receive an
explicit semantic status rather than being coerced to zero.

A separate eligibility rule should identify which descriptor measure, if any,
is a valid denominator for each cost category. This rule is necessary before
Stage 3 creates derived measures for Power BI.

## Implications for the Power BI dashboard

Python should complete extraction, structural enrichment, category and unit
standardisation, and data-quality validation before Power BI loads the data.
Power BI can then focus on relationships, calculations, filters, and visuals.

A useful first dashboard could contain:

1. **Overview:** expenditure trends, routine/non-routine mix, and visible
   coverage warnings.
2. **Business comparison:** comparable categories and approved normalised
   measures.
3. **Maintenance context:** asset quantity, activity volume, average age, and
   inspection or maintenance cycles.
4. **Definitions and data quality:** missing periods, added categories,
   estimation notes, unit conversions, and comparison limitations.

The dashboard should distinguish directly reported values from derived
measures and should make material coverage or comparability limitations
visible to a non-specialist user.

## Principal sources

- [AER Category Analysis RIN guideline and supporting documents, 2014](https://www.aer.gov.au/industry/registers/resources/guidelines/expenditure-forecast-assessment-guideline-regulatory-information-notices-category-analysis-2014)
- [AER Final Category Analysis RIN for transmission network service providers, March 2014](https://www.aer.gov.au/system/files/AER%20final%20category%20analysis%20RIN%20-%20transmission%20network%20service%20providers.pdf)
- [AER Category Analysis data template for transmission network service providers](https://www.aer.gov.au/documents/aer-category-analysis-data-template-transmission-network-service-providers)
- [AER explanatory statement for the final Category Analysis RINs, March 2014](https://www.aer.gov.au/system/files/AER%20explanatory%20statement%20-%20final%20category%20analysis%20RINs.pdf)
- [AER Expenditure Forecast Assessment Guideline for electricity transmission](https://www.aer.gov.au/system/files/Expenditure%20Forecast%20Assessment%20Guideline%20-%20Transmission%20-%20FINAL.pdf)
- [AER annual benchmarking reports 2025](https://www.aer.gov.au/industry/registers/resources/reviews/annual-benchmarking-reports-2025)
- [AusNet Transmission 2014-15 Category Analysis Basis of Preparation](https://www.aer.gov.au/system/files/2026-01/AusNet%20Services%20%28ET%29%202014-15%20-%20Category%20Analysis%20-%20Basis%20of%20Preparation%20%28D15%20113137%29.pdf)
- [Powerlink 2015-16 Category Analysis RIN Basis of Preparation](https://www.aer.gov.au/system/files/2026-01/Powerlink%202015-16%20-%20Category%20Analysis%20RIN%20-%20Basis%20of%20preparation%20%28D16%20140243%29.pdf)
- [Transgrid 2013-14 Category Analysis Basis of Preparation](https://www.aer.gov.au/system/files/2026-02/Transgrid%202013-14%20-%20Category%20Analysis%20-%20Basis%20of%20Preparation_0.pdf)

Business Basis of Preparation documents are examples of the type of
submission-specific evidence that should be consulted. The document applicable
to the exact business and reporting period takes precedence over an example
from another period.
