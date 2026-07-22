# Project Instructions

## Project brief

This project is a data-handling exercise involving semi-structured Excel workbooks published by the Australian Energy Regulator (AER) at https://www.aer.gov.au/.

The required source data is found in the AER's RIN workbooks. Extract the `Category Analysis RIN` template under `2.8 Maintenance` for these transmission businesses:

1. Transgrid
2. AusNet Transmission
3. Powerlink
4. ElectraNet

The work must cover at least the last five years of submissions for each business. The intended deliverables are a structured CSV and a Power BI (`.pbix`) file.

This is only a summary. Read the actual `README.md` whenever more detail or authoritative project context is needed.

## Four-point scope of work

All discussions, questions, proposals, plans, specifications, implementation choices, and reviews must be anchored to these four stages:

1. Extract the required RIN data from each transmission business submission for at least the last five years.
2. Standardise and structure the extracted data to enable cross-business comparison.
3. Create a consolidated data model suitable for Power BI.
4. Develop a Power BI dashboard that presents key metrics and insights.

Consider downstream effects across the full scope. For example, when discussing extraction or schema choices, explain how they affect later standardisation, consolidation, validation, and Power BI dashboard development.

## Editing and planning

- Do not edit, create, delete, rename, or otherwise modify files unless the user explicitly permits it.
- Before implementing code or making project changes, first develop a plan. At minimum, include high-level pseudocode.
- Planning may involve iterative discussion and clarifying questions; it does not have to follow a rigid sequence.
- Resolve material uncertainties and fix the implementation plan before asking for approval to implement it.
- An explicit user instruction to implement an agreed, fixed plan grants permission for the edits described in that plan.
- Implementation permission is limited to the agreed plan. If a material change or additional edit becomes necessary, stop, explain its effect on the four-point scope, and request further permission.
- Do not hesitate to ask clarifying questions during planning or an authorized edit when ambiguity could affect the result or later stages of the scope.

## Specifications

- Every feature must have a high-level approach documented in the `specs` directory before its implementation.
- The specification should connect the feature to the relevant parts of the four-point scope and describe important downstream effects.
- Treat creation or modification of a specification as an edit subject to the permission and planning rules above.

## File access

- Do not access files or directories matched by `.gitignore` unless the user explicitly permits access.
- Check `.gitignore` before inspecting project files when necessary to ensure this restriction is respected.

## Power BI communication

- Do not assume the user has Power BI knowledge.
- Explain Power BI concepts, constraints, decisions, and trade-offs in plain language.
- Clearly distinguish between work performed in Python (such as extraction, transformation, validation, or preparation of dashboard-ready data) and work performed in Power BI (such as the data model, measures, visuals, and `.pbix` dashboard).
