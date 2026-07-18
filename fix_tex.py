# -*- coding: utf-8 -*-
"""
origin の question-body を、KaTeX 用の TeX 記法（$...$）を含む Markdown に変換する。

方針:
  数式は origin の明示タグ（<i>変数, <sup>, <sub>, overline span, 分数table, ギリシャ文字）を
  「アンカー」とし、それに隣接する演算子/数字/括弧/空白（グルー）をまとめて 1 つの数式にする。
  アンカーを含まない連なり（例:「（1）」「ATM」「M/M/1」）はテキストのまま。
  分数は \frac、上線は \overline、上付き ^{}、下付き _{}。
デフォルト dry-run、--apply で書き込み。
"""
import re
import os
import sys
import html as htmllib

ROOT = os.path.dirname(os.path.abspath(__file__))

OPS = {
    "・": r"\cdot ", "＋": "+", "−": "-", "×": r"\times ", "÷": r"\div ",
    "／": "/", "＝": "=", "＜": "<", "＞": ">", "≦": r"\leq ", "≧": r"\geq ",
    "≤": r"\leq ", "≥": r"\geq ", "∪": r"\cup ", "∩": r"\cap ",
    "⊆": r"\subseteq ", "⊇": r"\supseteq ", "∈": r"\in ", "∉": r"\notin ",
    "（": "(", "）": ")", "｛": r"\{", "｝": r"\}",
    "←": r"\leftarrow ", "→": r"\rightarrow ", "≠": r"\neq ", "≒": r"\approx ",
    "≈": r"\approx ", "±": r"\pm ", "∞": r"\infty ", "√": r"\sqrt ",
}
GREEK = {"ρ": r"\rho ", "α": r"\alpha ", "β": r"\beta ", "θ": r"\theta ",
         "λ": r"\lambda ", "μ": r"\mu ", "σ": r"\sigma ", "π": r"\pi "}
ASCII_OP = set("+-*/=<>(){}!,")
GLUE_EXTRA = set("0123456789. ")  # 数字/小数点/半角空白（全角空白はテキスト扱い）


def esc_text(s):
    # $ を含むリテラルは KaTeX 誤爆防止でエスケープ
    return s.replace("\\", "\\\\").replace("$", r"\$")


def tex_inline(frag):
    """<i>,<sup>,<sub>,overline を含む断片を『数式内 TeX』へ（グルーはそのまま連結）。"""
    frag = re.sub(r'<span[^>]*overline[^>]*>(.*?)</span>',
                  lambda m: r"\overline{" + tex_inline(m.group(1)) + "}", frag, flags=re.S)
    frag = re.sub(r"<sup>(.*?)</sup>", lambda m: "^{" + tex_inline(m.group(1)) + "}", frag, flags=re.S)
    frag = re.sub(r"<sub>(.*?)</sub>", lambda m: "_{" + tex_inline(m.group(1)) + "}", frag, flags=re.S)
    frag = re.sub(r"</?i>|</?b>|</?em>|</?strong>", "", frag)
    frag = re.sub(r"<[^>]+>", "", frag)
    frag = htmllib.unescape(frag).strip()
    out = []
    for ch in frag:
        out.append(OPS.get(ch) or GREEK.get(ch) or ch)
    tex = "".join(out)
    # 数式内の日本語（変数名など）は \text{} で囲む（KaTeX で正しく表示）
    tex = re.sub(r"[ぁ-ゟァ-ヺー一-鿋々〆]+", lambda m: r"\text{" + m.group(0) + "}", tex)
    return tex


# --- fraction ---
def frac_tex(tbl):
    def clean(s):
        return tex_inline(s)
    center = re.findall(r'<td align="center">(.*?)</td>', tbl, re.S)
    if len(center) < 2:
        return ""
    num, den = clean(center[0]), clean(center[-1])
    rowspans = re.findall(r'<td rowspan="3"[^>]*>(.*?)</td>', tbl, re.S)
    left = clean(rowspans[0]) if len(rowspans) >= 1 else ""
    right = clean(rowspans[-1]) if len(rowspans) >= 2 else ""
    return left + r"\frac{" + num + "}{" + den + "}" + right


# token kinds: ('anchor', tex) forces math ; ('glue', orig, tex) ; ('text', s) ; ('br',)
def tokenize(html):
    html = re.sub(r"<style.*?</style>", "", html, flags=re.S)
    html = re.sub(r"<script.*?</script>", "", html, flags=re.S)
    html = re.sub(r"<img[^>]*>", "", html)
    toks = []
    i, n = 0, len(html)
    while i < n:
        if html.startswith("<br", i):
            j = html.find(">", i)
            toks.append(("br",)); i = j + 1; continue
        m = re.match(r'<table class="p-division-number">.*?</table>', html[i:], re.S)
        if m:
            toks.append(("anchor", frac_tex(m.group(0)))); i += m.end(); continue
        m = re.match(r'<span[^>]*overline[^>]*>(.*?)</span>', html[i:], re.S)
        if m:
            toks.append(("anchor", r"\overline{" + tex_inline(m.group(1)) + "}")); i += m.end(); continue
        m = re.match(r"<sup>(.*?)</sup>", html[i:], re.S)
        if m:
            toks.append(("sup", "^{" + tex_inline(m.group(1)) + "}")); i += m.end(); continue
        m = re.match(r"<sub>(.*?)</sub>", html[i:], re.S)
        if m:
            toks.append(("sub", "_{" + tex_inline(m.group(1)) + "}")); i += m.end(); continue
        m = re.match(r"<i>(.*?)</i>", html[i:], re.S)
        if m:
            toks.append(("anchor", tex_inline(m.group(1)))); i += m.end(); continue
        if html[i] == "<":
            j = html.find(">", i); i = (j + 1) if j >= 0 else i + 1; continue
        ch = html[i]; i += 1
        # decode entity boundary handled later; classify char
        if ch in OPS:
            toks.append(("glue", ch, OPS[ch]))
        elif ch in GREEK:
            toks.append(("anchor2", GREEK[ch], ch))   # greek: anchor but keep orig if text
        elif ch in ASCII_OP:
            toks.append(("glue", ch, ch))
        elif ch in GLUE_EXTRA:
            toks.append(("glue", ch, ch))
        elif re.match(r"[A-Za-z]", ch):
            toks.append(("glue", ch, ch))            # ASCII letter = glue (not anchor)
        else:
            toks.append(("text", ch))
    return toks


JP = re.compile(r"[ぁ-ゟァ-ヺー一-鿋々〆〤]")  # かな・漢字（・ は数式なので除外）


def tex_of(t):
    return t[2] if t[0] == "glue" else t[1]          # glue: [orig,tex]=[1,2]; others: tex at [1]


def orig_of(t):
    return t[1] if t[0] == "glue" else t[2] if t[0] == "anchor2" else ""


def _line_orig(line_toks):
    return "".join(orig_of(t) if t[0] != "text" else t[1] for t in line_toks)


def render_line(line_toks, force_choice_math=False):
    """1 行分のトークンを描画。純数式行（日本語なし）は全体を 1 つの $...$ に。"""
    # 前後の空白のみのトークンを除去（<br> 直後の改行由来のゴミ対策）
    def is_ws(t):
        return (t[0] == "text" and t[1].strip() == "") or (t[0] == "glue" and t[1].strip() == "")
    while line_toks and is_ws(line_toks[0]):
        line_toks = line_toks[1:]
    while line_toks and is_ws(line_toks[-1]):
        line_toks = line_toks[:-1]
    orig = _line_orig(line_toks)
    # 先頭ラベル（ア〜エ / （1）等の手順番号）は数式に含めずプレフィックスとして退避
    mk = re.match(r"^([アイウエ]　*|（\d+）　*)", orig)
    body_toks = line_toks
    prefix = ""
    is_choice = bool(re.match(r"^[アイウエ]", orig))
    if mk:
        label = mk.group(0)
        prefix = label if not is_choice else (label.rstrip("　 ") + "　")
        consumed = 0
        acc = ""
        for k, t in enumerate(line_toks):
            piece = orig_of(t) if t[0] != "text" else t[1]
            acc += piece
            consumed = k + 1
            if len(acc) >= len(label):
                break
        body_toks = line_toks[consumed:]
    rest_orig = "".join(orig_of(t) if t[0] != "text" else t[1] for t in body_toks)
    has_anchor = any(t[0] in ("anchor", "anchor2", "sup", "sub") for t in body_toks)
    pure_formula = bool(body_toks) and not JP.search(rest_orig)
    # 純数式行 → 全体を 1 つの $...$（兄弟選択肢に数式があれば anchor 無しでも数式化）
    if pure_formula and (has_anchor or (force_choice_math and is_choice)):
        tex = "".join(tex_of(t) for t in body_toks).strip()
        return prefix + "$" + tex + "$"
    # それ以外は span 単位で $...$ を挿入
    out, run = [prefix] if prefix else [], []

    def flush():
        if not run:
            return
        if any(t[0] in ("anchor", "anchor2", "sup", "sub") for t in run):
            out.append("$" + "".join(tex_of(t) for t in run).strip() + "$")
        else:
            out.append(esc_text("".join(orig_of(t) for t in run)))
        run.clear()

    for t in body_toks:
        if t[0] == "text":
            flush(); out.append(esc_text(t[1]))
        else:
            run.append(t)
    flush()
    return "".join(out)


def render(toks):
    # split into lines on 'br'
    lines, cur = [], []
    for t in toks:
        if t[0] == "br":
            lines.append(cur); cur = []
        else:
            cur.append(t)
    lines.append(cur)
    rendered = [render_line(l) for l in lines]
    # 選択肢のどれかが数式化されたら、兄弟の純数式選択肢も数式化して統一
    if any(re.match(r"^[アイウエ]", r) and "$" in r for r in rendered):
        rendered = [render_line(l, force_choice_math=True) for l in lines]
    text = "\n".join(rendered)
    # tidy: collapse spaces around newlines, blank-line handling
    lines = [ln.strip() for ln in text.split("\n")]
    res, prev_blank = [], True
    for ln in lines:
        if ln == "":
            if not prev_blank:
                res.append("")
            prev_blank = True
        else:
            res.append(ln); prev_blank = False
    res = [ln for ln in res if not re.match(r"^[アイウエ][　\s]*$", ln)]
    out2 = []
    for ln in res:
        if re.match(r"^[アイウエ][　\s]*\S", ln) and out2 and out2[-1] != "":
            out2.append("")
        out2.append(ln)
    return re.sub(r"\n{3,}", "\n\n", "\n".join(out2)).strip()


def convert(html):
    i = html.find('class="question-body"')
    start = html.rfind("<div", 0, i)
    seg = html[start:]
    m = re.search(r"</div>\s*<script", seg)
    seg = seg[: m.start()] if m else seg
    inner = seg[seg.find(">") + 1:]
    return render(tokenize(inner))


def main(targets, apply):
    from verify_origin import origin_iframe
    for tag in targets:
        p, q = tag.split("/"); q = int(q)
        of = origin_iframe(p, q)
        mdp = os.path.join(ROOT, f"{p}_am_summary", f"{q:02d}.md")
        html = open(of, encoding="utf-8").read()
        new = convert(html)
        md = open(mdp, encoding="utf-8").read()
        old = re.search(r"## 問題文\n(.*?)\n## 使用画像", md, re.S).group(1).strip()
        print(f"\n########## {tag} ##########\n----- OLD -----\n{old}\n----- NEW -----\n{new}")
        if apply:
            nm = re.sub(r"(## 問題文\n)(.*?)(\n## 使用画像)",
                        lambda mm: mm.group(1) + "\n" + new + "\n" + mm.group(3), md, count=1, flags=re.S)
            open(mdp, "w", encoding="utf-8").write(nm)
            print("[APPLIED]")


if __name__ == "__main__":
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    main(args, "--apply" in sys.argv)
