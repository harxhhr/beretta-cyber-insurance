"""Build every document on Windows: DOCX with the docx npm package, PDF with Microsoft Word.

    set NODE_PATH=<folder holding node_modules\\docx>     (npm install docx@9 there)
    python docs/build_all_windows.py            (all four)
    python docs/build_all_windows.py vm         (only names containing "vm")

Two passes per document, as the old twopass_*.sh scripts did with LibreOffice: the first pass writes
headings.json and a PDF, the page of each heading is read from the PDF (pdftotext), and the second
pass writes those page numbers into the static contents.
"""
import json
import os
import subprocess
import sys
import tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DOCS = [
    (os.path.join(ROOT, "docs"), "build_agent_guide.js", "Beretta_Agent_Complete_Guide"),
    (os.path.join(ROOT, "docs"), "build_link_doc.js", "Beretta_Part1_Part2_Link"),
    (os.path.join(ROOT, "docs"), "build_vm_guide.js", "Beretta_VM_Setup_and_Demo_Guide"),
    (os.path.join(ROOT, "kyh-agent", "docs"), "build_doc.js", "Beretta_Live_Monitoring_Agent"),
]

PS = r"""
$w = New-Object -ComObject Word.Application
$w.Visible = $false
try {
  $d = $w.Documents.Open('%s', $false, $true)
  $d.SaveAs2('%s', 17)
  $d.Close($false)
} finally { $w.Quit() }
"""


def to_pdf(docx, pdf):
    with tempfile.NamedTemporaryFile("w", suffix=".ps1", delete=False) as fh:
        fh.write(PS % (docx, pdf))
    try:
        subprocess.run(["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", fh.name], check=True)
    finally:
        os.remove(fh.name)


def page_texts(pdf):
    out = subprocess.run(["pdftotext", "-enc", "UTF-8", "-layout", pdf, "-"], capture_output=True).stdout.decode("utf-8", "replace")
    return out.split("\f")


only = sys.argv[1:]   # optional: build only documents whose name contains one of these words
for folder, script, name in DOCS:
    if only and not any(w.lower() in name.lower() for w in only):
        continue
    docx, pdf = os.path.join(folder, name + ".docx"), os.path.join(folder, name + ".pdf")
    pages_json, heads_json = os.path.join(folder, "pages.json"), os.path.join(folder, "headings.json")
    if os.path.exists(pages_json):
        os.remove(pages_json)
    for _ in (1, 2):
        subprocess.run(["node", script], cwd=folder, check=True, stdout=subprocess.DEVNULL)
        to_pdf(docx, pdf)
        texts = page_texts(pdf)
        heads = json.load(open(heads_json, encoding="utf-8"))
        pages = {}
        for _lvl, t in heads:
            key = " ".join(t.split())[:40]
            for i, tx in enumerate(texts[2:], start=3):   # skip the title page and the contents
                if any(" ".join(line.split()).startswith(key) for line in tx.splitlines()):
                    pages[t] = str(i)
                    break
        json.dump(pages, open(pages_json, "w", encoding="utf-8"))
    missing = [t for _, t in heads if t not in pages]
    print(f"{name}: {len([p for p in texts if p.strip()])} pages" + (f", headings not found: {missing}" if missing else ""))
    os.remove(pages_json)
    os.remove(heads_json)
