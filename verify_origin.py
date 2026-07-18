# -*- coding: utf-8 -*-
"""
origin/ の元 HTML を正として、変換済み MD の「## 問題文」に書式崩れが無いか検証する。

検出カテゴリ:
  overline   : <span style="text-decoration:overline"> （否定・補集合バー）欠落
  sup        : <sup> （上付き・指数）欠落
  sub        : <sub> （下付き・添字）欠落
  fraction   : <table class="p-division-number"> （分数）欠落
  css_leak   : <style> の CSS 文字列が問題文に混入
  img_miss   : origin の画像数と MD 使用画像数が不一致

対象: 2015〜2025（対応 MD がある期のみ）。
使い方: python verify_origin.py [--list カテゴリ]
"""
import re
import os
import sys
import glob

ROOT = os.path.dirname(os.path.abspath(__file__))


def periods():
    out = []
    for y in range(2015, 2026):
        for s in ("haru", "aki"):
            if os.path.isdir(os.path.join(ROOT, f"{y}_{s}_am_summary")):
                out.append(f"{y}_{s}")
    return out


def origin_iframe(period, qn):
    d = os.path.join(ROOT, "origin", f"{period}_am", f"{qn:02d}_files")
    if not os.path.isdir(d):
        return None
    for fn in os.listdir(d):
        if fn.endswith(".html"):
            path = os.path.join(d, fn)
            try:
                txt = open(path, encoding="utf-8").read()
            except Exception:
                continue
            if "question-body" in txt:
                return path
    return None


def question_body(html):
    i = html.find('class="question-body"')
    if i < 0:
        return ""
    # take from the opening div to the closing </div> that ends the body
    start = html.rfind("<div", 0, i)
    depth = 0
    j = start
    # simple: cut a generous window then trim at the <script> that follows
    seg = html[start:]
    m = re.search(r"</div>\s*(?:<script|</body|\Z)", seg)
    return seg[: m.start()] if m else seg[:2000]


def md_body(md):
    m = re.search(r"## 問題文\n(.*?)\n## 使用画像", md, re.S)
    return m.group(1) if m else ""


def md_images(md):
    m = re.search(r"## 使用画像\n(.*?)(\n## |\Z)", md, re.S)
    seg = m.group(1) if m else ""
    return [os.path.basename(x) for x in re.findall(r"!\[[^\]]*\]\(([^)]+)\)", seg)]


def origin_images(qb):
    imgs = re.findall(r'<img[^>]+src="\./([^"]+\.(?:gif|png|jpg|jpeg))"', qb)
    return [i for i in imgs if not i.startswith(("fracline", "loading", "dekidas"))]


def audit():
    cats = {k: [] for k in ("overline", "sup", "sub", "fraction", "css_leak", "img_miss")}
    for period in periods():
        for qn in range(1, 81):
            mdp = os.path.join(ROOT, f"{period}_am_summary", f"{qn:02d}.md")
            if not os.path.exists(mdp):
                continue
            of = origin_iframe(period, qn)
            if not of:
                continue
            md = open(mdp, encoding="utf-8").read()
            body = md_body(md)
            qb = question_body(open(of, encoding="utf-8").read())
            tag = f"{period}/{qn:02d}"

            if "overline" in qb:
                cats["overline"].append(tag)
            if "<sup" in qb:
                cats["sup"].append(tag)
            if "<sub" in qb:
                cats["sub"].append(tag)
            if "p-division-number" in qb:
                cats["fraction"].append(tag)
            if re.search(r"(line-height:|font-size:|text-decoration:|p-division|display:\s*inline|vertical-align)", body):
                cats["css_leak"].append(tag)
            o_imgs = set(origin_images(qb))
            m_imgs = set(md_images(md))
            if len(o_imgs) != len(m_imgs):
                cats["img_miss"].append(f"{tag} (origin {len(o_imgs)} / md {len(m_imgs)})")
    return cats


def main():
    cats = audit()
    only = None
    if len(sys.argv) >= 3 and sys.argv[1] == "--list":
        only = sys.argv[2]
    total = 0
    for k, v in cats.items():
        if only and k != only:
            continue
        print(f"\n=== {k}: {len(v)} 件 ===")
        print("\n".join(v))
        total += len(v)
    print(f"\n合計(重複含む): {total} 件")


if __name__ == "__main__":
    main()
