#!/usr/bin/env python3
"""
ML Lab Site Builder
Converts Jupyter notebooks to HTML and generates site manifest.
"""
import os, json, shutil, subprocess, re
from datetime import datetime, timezone
from pathlib import Path

ROOT  = Path(".")
SITE  = Path("_site")
TMPL  = Path("website/index.html")

# ──────────────────────────────────────────────
# Helpers
# ──────────────────────────────────────────────
def fmt_title(name: str) -> str:
    m = re.match(r"([a-zA-Z]+)(\d+)", name)
    if m:
        word = re.sub(r"([a-z])([A-Z])", r"\1 \2", m.group(1))
        return f"{word.title()} {m.group(2)}"
    return name.replace("_", " ").title()

def nb_to_html(nb_path: Path, out_dir: Path) -> bool:
    out_dir.mkdir(parents=True, exist_ok=True)
    cmd = [
        "jupyter", "nbconvert", "--to", "html",
        "--output", nb_path.stem + ".html",
        "--output-dir", str(out_dir),
        "--HTMLExporter.theme=light",
        str(nb_path),
    ]
    r = subprocess.run(cmd, capture_output=True, text=True, timeout=180)
    if r.returncode != 0:
        print(f"    ⚠  nbconvert warn: {r.stderr[:300]}")
    return r.returncode == 0

# ──────────────────────────────────────────────
# Syllabus processor
# ──────────────────────────────────────────────
def process_syllabus(src: Path, key: str, site_syl: Path):
    practicals = []
    if not src.exists():
        print(f"  ⚠  {src} not found, skipping.")
        return practicals

    for prac_dir in sorted(src.iterdir(), key=lambda p: p.name):
        if not prac_dir.is_dir() or prac_dir.name.startswith("."):
            continue

        notebooks = sorted([
            f for f in prac_dir.rglob("*.ipynb")
            if ".ipynb_checkpoints" not in str(f)
        ])
        if not notebooks:
            continue

        prac_id = prac_dir.name
        out_dir  = site_syl / prac_id
        nb_entries = []

        for nb in notebooks:
            rel      = nb.relative_to(prac_dir)
            nb_out   = out_dir / rel.parent
            nb_out.mkdir(parents=True, exist_ok=True)

            print(f"    📓 {nb.relative_to(ROOT)}")
            ok = nb_to_html(nb, nb_out)

            # copy raw ipynb for download
            shutil.copy2(nb, nb_out / nb.name)

            html_path = f"{key}/{prac_id}/{('/'.join(rel.parent.parts) + '/') if rel.parent.parts else ''}{nb.stem}.html"
            ipynb_path = f"{key}/{prac_id}/{('/'.join(rel.parent.parts) + '/') if rel.parent.parts else ''}{nb.name}"

            nb_entries.append({
                "name": nb.stem,
                "label": fmt_title(nb.stem),
                "html":  html_path.replace("//", "/") if ok else None,
                "ipynb": ipynb_path.replace("//", "/"),
            })

        # copy data / csv files
        for f in prac_dir.iterdir():
            if f.is_file() and f.suffix in (".csv", ".txt", ".json", ".xlsx", ".xls", ".pdf"):
                shutil.copy2(f, out_dir / f.name)

        practicals.append({
            "id":        prac_id,
            "title":     fmt_title(prac_id),
            "notebooks": nb_entries,
            "count":     len(nb_entries),
        })

    return practicals

# ──────────────────────────────────────────────
# Main build
# ──────────────────────────────────────────────
def build():
    print("\n🔨  Building ML Lab site …\n")

    if SITE.exists():
        shutil.rmtree(SITE)
    SITE.mkdir()

    manifest = {
        "updated":  datetime.now(timezone.utc).strftime("%d %b %Y, %H:%M UTC"),
        "syllabi":  {},
    }

    # read syllabus.md if present
    syl_md = ROOT / "syllabus.md"
    if syl_md.exists():
        manifest["syllabus_md"] = syl_md.read_text(encoding="utf-8")
        shutil.copy2(syl_md, SITE / "syllabus.md")

    syllabus_map = [
        ("new_Syllabus", "new_syllabus", "New Syllabus",
         "Latest curriculum with updated practicals"),
        ("old_Syllabus", "old_syllabus", "Old Syllabus",
         "Previous curriculum practicals and PDFs"),
    ]

    for src_name, key, title, desc in syllabus_map:
        print(f"  📚  {title}")
        practicals = process_syllabus(ROOT / src_name, key, SITE / key)
        manifest["syllabi"][key] = {
            "title":       title,
            "description": desc,
            "practicals":  practicals,
        }
        print(f"       ✓  {len(practicals)} practicals\n")

    # write manifest
    (SITE / "manifest.json").write_text(
        json.dumps(manifest, indent=2), encoding="utf-8"
    )

    # copy website template
    shutil.copy2(TMPL, SITE / "index.html")

    # also copy pdfs from old syllabus if present
    old_pdf = ROOT / "old_Syllabus" / "pdfs"
    if old_pdf.exists():
        dest_pdf = SITE / "old_syllabus" / "pdfs"
        dest_pdf.mkdir(parents=True, exist_ok=True)
        for f in old_pdf.glob("*.pdf"):
            shutil.copy2(f, dest_pdf / f.name)

    total_nb = sum(
        p["count"]
        for s in manifest["syllabi"].values()
        for p in s["practicals"]
    )
    print(f"✅  Done!  {total_nb} notebooks converted → {SITE}/")

if __name__ == "__main__":
    build()