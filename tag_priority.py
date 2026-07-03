# -*- coding: utf-8 -*-
import re
import os
import glob

ROOT = os.path.dirname(os.path.abspath(__file__))
MEMO_PATH = os.path.join(ROOT, "出題傾向メモ.md")

# --- Tier 1: topic-based priority tags (matched against existing タグ field) ---
TOPIC_TAGS = {
    "最優先": [
        "リスク対応戦略", "システム監査", "IPアドレス・サブネット", "契約・調達", "計算問題",
        "情報セキュリティ用語（JIS Q 27000）", "メール・Web通信", "認証・パスワード",
        "信頼性・稼働率", "仮想記憶", "財務・会計", "データモデル", "経営分析フレームワーク",
        "OS・プロセス管理", "暗号・PKI", "SQL", "TCP/IP", "VPN・トンネリング", "ジョブスケジューリング",
    ],
    "高頻出": [
        "IoT", "電気回路", "ネットワーク機器・規格", "ITIL・CSF", "進数変換", "キャッシュメモリ",
    ],
    "増加傾向": [
        "機械学習", "AI", "アジャイル・スクラム", "アジャイル宣言", "FPGA・HDL", "セキュリティ攻撃・対策",
    ],
    "減少傾向": [
        "クレジットカード不正対策", "XP・プラクティス", "論理回路（順序回路）",
    ],
}

SEASON_MAP = {"春": "haru", "秋": "aki"}

# --- Tier 2: reused-question sections -> priority tag per section ---
REUSE_SECTIONS = {
    "4回以上使い回された問題": "頻出(4回以上)",
    "3回使い回された問題（抜粋）": "頻出(3回)",
    "2回使い回された問題（主要なもの）": "頻出(2回)",
    "ほぼ同一問題（類似度0.97〜0.99・表記揺れのみ）": "頻出(2回)",
}


def parse_reuse_targets():
    text = open(MEMO_PATH, encoding="utf-8").read()
    # split into sections by "### " headers
    parts = re.split(r"\n### ", text)
    targets = {}  # (year, season_key, num) -> set of tags
    for part in parts:
        header = part.split("\n", 1)[0].strip()
        if header not in REUSE_SECTIONS:
            continue
        tag = REUSE_SECTIONS[header]
        for m in re.finditer(r"(\d{4})(春|秋)問(\d+)", part):
            year, season_kanji, num = m.group(1), m.group(2), int(m.group(3))
            key = (year, SEASON_MAP[season_kanji], num)
            targets.setdefault(key, set()).add(tag)
    return targets


def parse_frontmatter_tags(text):
    m = re.search(r"タグ:\s*(.+)", text)
    if not m:
        return None, None
    raw = m.group(1).strip()
    tags = [t.strip() for t in re.split(r"[,、]", raw) if t.strip()]
    return raw, tags


def compute_topic_tags(existing_tags):
    existing_set = set(existing_tags)
    new_tags = []
    for priority_tag, topic_list in TOPIC_TAGS.items():
        if existing_set & set(topic_list):
            new_tags.append(priority_tag)
    return new_tags


def main():
    reuse_targets = parse_reuse_targets()
    print(f"Parsed {len(reuse_targets)} reused-question targets from memo")

    changed = 0
    total = 0
    for folder in sorted(glob.glob(os.path.join(ROOT, "*_am_summary"))):
        base = os.path.basename(folder)
        m = re.match(r"(\d{4})_(haru|aki)_am_summary", base)
        if not m:
            continue
        year, season = m.group(1), m.group(2)
        for fp in sorted(glob.glob(os.path.join(folder, "*.md"))):
            num = int(os.path.splitext(os.path.basename(fp))[0])
            total += 1
            text = open(fp, encoding="utf-8").read()
            raw, existing_tags = parse_frontmatter_tags(text)
            if raw is None:
                continue

            to_add = []
            to_add += compute_topic_tags(existing_tags)
            key = (year, season, num)
            if key in reuse_targets:
                to_add += sorted(reuse_targets[key])

            to_add = [t for t in to_add if t not in existing_tags]
            if not to_add:
                continue

            new_tag_line = raw + ", " + ", ".join(to_add)
            new_text = text.replace(f"タグ: {raw}", f"タグ: {new_tag_line}", 1)
            if new_text == text:
                print(f"WARN: no replacement happened for {fp}")
                continue
            open(fp, "w", encoding="utf-8").write(new_text)
            changed += 1

    print(f"Updated {changed} / {total} files")


if __name__ == "__main__":
    main()
