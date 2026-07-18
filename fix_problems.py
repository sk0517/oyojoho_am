# -*- coding: utf-8 -*-
"""
origin の question-body HTML を正として、MD の「## 問題文」を再構築する。
書式方針（Unicode 忠実再現）:
  上線 <span overline>  -> 各文字 + U+0305 結合上線
  上付き <sup>          -> Unicode 上付き（全文字対応時）／なければ ^(...)
  下付き <sub>          -> _ 表記（_A, _S, _1, _AB ...）
  分数 table.p-division-number -> 分子 / (分母)
  <style>/<script>     -> 除去（CSS 漏れ対策）
  <img>                -> 本文からは除去（使用画像は別管理）

デフォルトは dry-run（差分表示のみ）。--apply で書き込み。
"""
import re
import os
import sys
import html as htmllib

ROOT = os.path.dirname(os.path.abspath(__file__))

SUP = {
    "0": "⁰", "1": "¹", "2": "²", "3": "³", "4": "⁴", "5": "⁵", "6": "⁶",
    "7": "⁷", "8": "⁸", "9": "⁹", "+": "⁺", "＋": "⁺", "-": "⁻", "−": "⁻",
    "(": "⁽", ")": "⁾", "n": "ⁿ", "i": "ⁱ",
}
OVERLINE = "̅"


def to_sup(s):
    s = s.strip()
    if s and all(ch in SUP for ch in s):
        return "".join(SUP[ch] for ch in s)
    return ("^(" + s + ")") if len(s) > 1 else ("^" + s)


def convert_inline(frag):
    # overline spans -> combining overline per char
    def ol(m):
        inner = re.sub(r"<[^>]+>", "", m.group(1))
        return "".join(ch + OVERLINE for ch in inner)
    frag = re.sub(r'<span[^>]*text-decoration:\s*overline[^>]*>(.*?)</span>', ol, frag, flags=re.S)
    # sup / sub (inner may contain <i>)
    frag = re.sub(r"<sup>(.*?)</sup>", lambda m: to_sup(re.sub(r"<[^>]+>", "", m.group(1))), frag, flags=re.S)
    frag = re.sub(r"<sub>(.*?)</sub>", lambda m: "_" + re.sub(r"<[^>]+>", "", m.group(1)).strip(), frag, flags=re.S)
    # italics / bold just unwrap
    frag = re.sub(r"</?i>|</?b>|</?em>|</?strong>", "", frag)
    return frag


def _has_toplevel_op(s):
    depth = 0
    for ch in s:
        if ch in "(（":
            depth += 1
        elif ch in ")）":
            depth -= 1
        elif depth == 0 and ch in "＋－+-×÷・*/":
            return True
    return False


def _is_single_atom(s):
    # 単一の数・変数（添字/階乗可）は括弧不要
    return bool(re.fullmatch(r"\d+", s) or re.fullmatch(r"[A-Za-zαβρθ](_[A-Za-z0-9]+)?!?", s))


def _wrap_num(s):
    return f"（{s}）" if _has_toplevel_op(s) else s


def _wrap_den(s):
    if _has_toplevel_op(s) or not _is_single_atom(s):
        return f"（{s}）"
    return s


def convert_fractions(frag):
    def clean(s):
        return re.sub(r"<[^>]+>", "", s).strip()

    def one(m):
        tbl = m.group(0)
        center = re.findall(r'<td align="center">(.*?)</td>', tbl, re.S)
        if len(center) < 2:
            return " "
        num = clean(center[0])
        den = clean(center[-1])
        # rowspan="3" セル = 分数の左右に付く係数（例: ×T_S、() でくくる、・y）
        rowspans = re.findall(r'<td rowspan="3"[^>]*>(.*?)</td>', tbl, re.S)
        left = clean(rowspans[0]) if len(rowspans) >= 1 else ""
        right = clean(rowspans[-1]) if len(rowspans) >= 2 else ""
        return f" {left}{_wrap_num(num)}／{_wrap_den(den)}{right} "
    return re.sub(r'<table class="p-division-number">.*?</table>', one, frag, flags=re.S)


def extract_body(html):
    i = html.find('class="question-body"')
    start = html.rfind("<div", 0, i)
    seg = html[start:]
    # cut at the </div> that closes the body, before <script>
    m = re.search(r"</div>\s*<script", seg)
    seg = seg[: m.start()] if m else seg
    inner = seg[seg.find(">") + 1:]
    return inner


def convert_body(html):
    frag = extract_body(html)
    frag = re.sub(r"<style.*?</style>", "", frag, flags=re.S)
    frag = re.sub(r"<script.*?</script>", "", frag, flags=re.S)
    frag = convert_inline(frag)          # overline/sup/sub/i first
    frag = convert_fractions(frag)       # then fraction tables (td already converted)
    imgs = re.findall(r'<img[^>]+src="\./([^"]+)"', frag)
    imgs = [x for x in imgs if not x.startswith(("fracline", "loading", "dekidas"))]
    frag = re.sub(r"<img[^>]*>", "", frag)      # drop images from text
    frag = re.sub(r"<br\s*/?>", "\n", frag)
    frag = re.sub(r"<[^>]+>", "", frag)          # strip remaining tags
    frag = htmllib.unescape(frag)
    # strip each line but KEEP single blank lines as paragraph separators
    raw = [ln.strip() for ln in frag.split("\n")]
    lines, prev_blank = [], True
    for ln in raw:
        if ln == "":
            if not prev_blank:
                lines.append("")
            prev_blank = True
        else:
            lines.append(ln)
            prev_blank = False
    # drop empty choice markers (image-choice questions: choices live in 使用画像)
    lines = [ln for ln in lines if not re.match(r"^[アイウエ][　\s]*$", ln)]
    # ensure a blank line before each non-empty choice marker
    out = []
    for ln in lines:
        if re.match(r"^[アイウエ][　\s]*\S", ln) and out and out[-1] != "":
            out.append("")
        out.append(ln)
    text = "\n".join(out)
    text = re.sub(r"\n{3,}", "\n\n", text).strip()
    return text, imgs


def replace_problem(md, new_problem):
    return re.sub(r"(## 問題文\n)(.*?)(\n## 使用画像)",
                  lambda m: m.group(1) + "\n" + new_problem + "\n" + m.group(3),
                  md, count=1, flags=re.S)


def main(targets, apply):
    from verify_origin import origin_iframe
    for tag in targets:
        period, qn = tag.split("/")
        qn = int(qn)
        of = origin_iframe(period, qn)
        mdp = os.path.join(ROOT, f"{period}_am_summary", f"{qn:02d}.md")
        if not of or not os.path.exists(mdp):
            print(f"SKIP {tag} (missing)")
            continue
        html = open(of, encoding="utf-8").read()
        new_problem, imgs = convert_body(html)
        md = open(mdp, encoding="utf-8").read()
        old = re.search(r"## 問題文\n(.*?)\n## 使用画像", md, re.S).group(1).strip()
        print(f"\n########## {tag}  (origin images: {imgs}) ##########")
        print("----- OLD -----")
        print(old)
        print("----- NEW -----")
        print(new_problem)
        if apply:
            new_md = replace_problem(md, new_problem)
            open(mdp, "w", encoding="utf-8").write(new_md)
            print("[APPLIED]")


if __name__ == "__main__":
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    apply = "--apply" in sys.argv
    main(args, apply)
