import argparse
import json
from pathlib import Path

import pandas as pd

from src.rin_discovery import crawl_author, update_manifest


def parse_args() -> argparse.Namespace:
    """
    Parse command-line arguments.
    --config-path:
        Path to JSON config file.
    """

    parser = argparse.ArgumentParser(
        description="CLI for discovering RIN workbooks across businesses."
    )

    parser.add_argument(
        "--config-path",
        "--config_path",
        dest="config_path",
        type=Path,
        required=True,
        help="Path to the JSON author-pages config file",
    )

    parser.add_argument(
        "--business",
        help="Optionally select one configured business",
    )

    parser.add_argument(
        "--manifest",
        type=Path,
        required=True,
        help="Path to write the discovered RIN workbook manifest",
    )

    return parser.parse_args()


def main() -> None:
    # 0. Parse command-line arguments.
    args = parse_args()

    # 1. Load the inputs required for discovery.
    # 1.1 Load author-page URLs from the supplied JSON config path.
    with args.config_path.open(encoding="utf-8") as file:
        author_pages = json.load(file)

    # 1.2 Restrict discovery when the user selects one configured business.
    selected_author_pages = author_pages
    if args.business:
        if args.business not in author_pages:
            valid_businesses = ", ".join(author_pages)
            raise SystemExit(
                f"Error: unknown business {args.business!r}. "
                f"Choose one of: {valid_businesses}"
            )

        selected_author_pages = {
            args.business: author_pages[args.business],
        }

    # 1.3 Load the existing manifest when one is already available.
    manifest_file_path = args.manifest

    # Create the output directory before reading or writing the manifest.
    manifest_file_path.parent.mkdir(parents=True, exist_ok=True)

    # Check whether the path is an existing file rather than a directory.
    existing_manifest = None
    if manifest_file_path.is_file():
        existing_manifest = pd.read_csv(manifest_file_path)

    # 2. Crawl RIN workbook links for the selected authors.
    discoveries = []

    for business, author_url in selected_author_pages.items():
        discoveries.extend(crawl_author(business, author_url))

    # 3. Update the existing manifest with newly discovered RIN workbooks.
    manifest = update_manifest(existing_manifest, discoveries)

    # 4. Write the updated manifest and report the completed output.
    manifest.to_csv(manifest_file_path, index=False)
    print(
        f"[manifest] Wrote {len(manifest)} row(s) to "
        f"{manifest_file_path.resolve()}"
    )


if __name__ == "__main__":
    main()
