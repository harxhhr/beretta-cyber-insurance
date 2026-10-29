set -e
cd "$(dirname "$0")"
SOFF=/root/.claude/skills/synced/9423e164-49c8-462e-9254-515d79bd218f_82dca609-13d6-40b7-b1f6-dcda75423960/docx/scripts/office/soffice.py
rm -f pages.json
for pass in 1 2; do
  node build_agent_guide.js >/dev/null
  python3 $SOFF --headless --convert-to pdf Beretta_Agent_Complete_Guide.docx >/dev/null 2>&1
  python3 - <<'PY'
import json, subprocess
heads = json.load(open("headings.json"))
info = subprocess.run(["pdfinfo","Beretta_Agent_Complete_Guide.pdf"],capture_output=True,text=True).stdout
n = int([l for l in info.splitlines() if l.startswith("Pages")][0].split()[1])
texts = [subprocess.run(["pdftotext","-f",str(i),"-l",str(i),"-layout","Beretta_Agent_Complete_Guide.pdf","-"],capture_output=True,text=True).stdout for i in range(1,n+1)]
pages = {}
for lvl, t in heads:
    key = " ".join(t.split())[:40]
    for i, tx in enumerate(texts[2:], start=3):
        if any(" ".join(line.split()).startswith(key) for line in tx.splitlines()):
            pages[t] = str(i); break
json.dump(pages, open("pages.json","w"))
print("pages", n, "missing", [t for _, t in heads if t not in pages])
PY
done
rm -f pages.json headings.json
