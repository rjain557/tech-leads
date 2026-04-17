"""
ingest_services.py — Placeholder for PDF → services.yml re-ingestion.

The initial services.yml was authored by reading all 10 One-Pager PDFs manually (token-efficient).
If the PDFs change materially, re-run this script to rebuild the YAML.

Current implementation: opens each PDF path, sends its text to Claude to re-extract
the structured fields. Stubbed until the first re-ingest is actually needed.
"""

from pathlib import Path
import sys

SERVICES_PDF_ROOT = Path(r"D:\vscode\tech-branding\Services")


def discover_services() -> list[Path]:
    """Return paths to brochure/one-pager PDFs for every service (excludes pre-release)."""
    result: list[Path] = []
    for d in sorted(SERVICES_PDF_ROOT.iterdir()):
        if not d.is_dir():
            continue
        if d.name.lower().endswith("-pre-release"):
            continue
        # Prefer one-pagers (compact); fall back to brochure.
        one_pagers = sorted(d.glob("*One-Pager*.pdf"))
        brochures = sorted(d.glob("*Brochure*.pdf"))
        if one_pagers:
            result.extend(one_pagers)
        elif brochures:
            result.extend(brochures)
    return result


def main() -> int:
    pdfs = discover_services()
    print(f"Would re-ingest {len(pdfs)} PDFs:")
    for p in pdfs:
        print(f"  - {p.relative_to(SERVICES_PDF_ROOT)}")
    print("\n(Stub — actual Claude-powered extraction not wired up.)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
