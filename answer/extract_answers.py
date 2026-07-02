import pdfplumber, re, json, glob, os

out = {}
for path in glob.glob(os.path.join(os.path.dirname(__file__), "*_ans.pdf")):
    name = os.path.basename(path)
    with pdfplumber.open(path) as pdf:
        text = pdf.pages[0].extract_text()
    if not text:
        print(name, "NO TEXT - needs OCR")
        out[name] = {}
        continue
    pairs = re.findall(r'問(\d+)\s+([アイウエ])(?:\s+[ＴＭＳ])?', text)
    d = {n: a for n, a in pairs}
    out[name] = d
    print(name, len(d))

with open(os.path.join(os.path.dirname(__file__), "answers.json"), "w", encoding="utf-8") as f:
    json.dump(out, f, ensure_ascii=False, indent=2)
