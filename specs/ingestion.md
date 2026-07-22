# Spec: extracting all required RIN workbook data for the 4 businesses, at least 5 years back for each business.
Related to the first point of the scope of the work

# High-Level Approach

Programmatically scrape and download all RIN document data across all 4 businesses from `aer.gov.au`. Will be done in stages:
1. Crawl every paginated page in `"https://www.aer.gov.au/authors/<BUSINESS-NAME>"`, **retain document landing-page links (NOT attachment links), and structure them in a neat structure, say a table**. No download is peformed at this stage. Author pages to retrieve: 
    ```python
    AUTHOR_PAGES = {
        "Transgrid": "https://www.aer.gov.au/authors/transgrid-t",
        "ElectraNet": "https://www.aer.gov.au/authors/electranet",
        "Powerlink": "https://www.aer.gov.au/authors/powerlink",
        "AusNet Transmission": "https://www.aer.gov.au/authors/ausnet-services-t",
    }
    ```
2. Manually confirm all relevant 5+ year submissions per business.
3. (Programmatically or manually) visit those document pages and extract their attachment links (attachment URLs).

