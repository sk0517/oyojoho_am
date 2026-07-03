import json
import os
import re
import glob

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT_DIR = os.path.dirname(os.path.abspath(__file__))

FOLDER_ORDER = [
    "2025_haru", "2025_aki",
    "2024_haru", "2024_aki",
    "2023_haru", "2023_aki",
    "2022_haru", "2022_aki",
    "2021_haru", "2021_aki",
    "2020_aki",
    "2019_haru", "2019_aki",
    "2018_haru", "2018_aki",
    "2017_haru", "2017_aki",
    "2016_haru", "2016_aki",
    "2015_haru", "2015_aki",
]

SEASON_LABEL = {"haru": "春期", "aki": "秋期"}


def parse_frontmatter(text):
    m = re.match(r"^---\n(.*?)\n---\n", text, re.S)
    fm = {}
    if m:
        for line in m.group(1).split("\n"):
            if ":" in line:
                k, v = line.split(":", 1)
                fm[k.strip()] = v.strip()
    return fm, text[m.end():] if m else text


def extract_section(body, start_marker, end_markers):
    pattern = re.escape(start_marker) + r"\n(.*?)(?=\n## |\Z)"
    m = re.search(pattern, body, re.S)
    return m.group(1).strip() if m else ""


def parse_images(section_text):
    return re.findall(r"!\[[^\]]*\]\(([^)]+)\)", section_text)


def parse_answer(section_text):
    m = re.search(r"\*\*正解[：:]\s*([アイウエ])\*\*", section_text)
    letter = m.group(1) if m else None
    # everything after the 正解 line is explanation (including the IPA公式 line)
    return letter, section_text.strip()


def main():
    periods = []
    for key in FOLDER_ORDER:
        year, season = key.split("_")
        folder = os.path.join(ROOT, f"{key}_am_summary")
        if not os.path.isdir(folder):
            continue
        questions = []
        for n in range(1, 81):
            fp = os.path.join(folder, f"{n:02d}.md")
            if not os.path.exists(fp):
                continue
            text = open(fp, encoding="utf-8").read()
            fm, body = parse_frontmatter(text)
            question_text = extract_section(body, "## 問題文", None)
            images_section = extract_section(body, "## 使用画像", None)
            answer_section = extract_section(body, "## 解答と解説", None)
            images = parse_images(images_section)
            image_urls = [f"../{key}_am_summary/images/{os.path.basename(img)}" for img in images]
            letter, explanation = parse_answer(answer_section)
            questions.append({
                "n": n,
                "category": fm.get("カテゴリ", ""),
                "difficulty": fm.get("難易度", ""),
                "importance": fm.get("重要度", ""),
                "tags": fm.get("タグ", ""),
                "question": question_text,
                "images": image_urls,
                "answer": letter,
                "explanation": explanation,
            })
        periods.append({
            "key": key,
            "label": f"{year}年 {SEASON_LABEL.get(season, season)}",
            "questions": questions,
        })

    out_path = os.path.join(OUT_DIR, "data.js")
    with open(out_path, "w", encoding="utf-8") as f:
        f.write("const PERIODS = ")
        json.dump(periods, f, ensure_ascii=False)
        f.write(";\n")

    total = sum(len(p["questions"]) for p in periods)
    print(f"Wrote {out_path}: {len(periods)} periods, {total} questions")


if __name__ == "__main__":
    main()
