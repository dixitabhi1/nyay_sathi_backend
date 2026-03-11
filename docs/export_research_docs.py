from __future__ import annotations

from pathlib import Path

from export_synopsis import export_docx, export_pdf, parse_markdown


ROOT = Path(__file__).resolve().parent
SOURCES = [
    ROOT / "NyayaSetu_Research_Evaluation_Approach.md",
    ROOT / "NyayaSetu_Research_Evaluation_Results.md",
    ROOT / "NyayaSetu_Research_Comparison_and_Improvement.md",
]


def main() -> None:
    for source in SOURCES:
        blocks = parse_markdown(source)
        docx_output = source.with_suffix(".docx")
        pdf_output = source.with_suffix(".pdf")
        export_docx(blocks, docx_output)
        export_pdf(blocks, pdf_output)
        print(f"Wrote {docx_output}")
        print(f"Wrote {pdf_output}")


if __name__ == "__main__":
    main()
