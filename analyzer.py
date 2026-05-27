import pandas as pd
from datetime import datetime, timedelta
from collections import Counter
import os
import sys

CSV_FILE = "github_trending_history.csv"
REPORT_FILE = "insight_report.md"

CATEGORY_KEYWORDS = {
    "AI/ML": ["ai", "ml", "machine-learning", "deep-learning", "llm", "gpt", "neural", "transformer", "nlp", "computer-vision", "ai-agent"],
    "Web": ["web", "frontend", "react", "vue", "angular", "nextjs", "css", "html", "javascript", "typescript", "fullstack"],
    "Backend": ["api", "server", "backend", "rest", "graphql", "microservice", "node", "django", "flask", "fastapi", "express"],
    "DevTools": ["cli", "terminal", "git", "docker", "kubernetes", "devtools", "lint", "formatter", "editor", "vscode", "neovim"],
    "Systems": ["rust", "c", "cpp", "go", "os", "kernel", "embedded", "compiler", "systems"],
    "Mobile": ["android", "ios", "flutter", "react-native", "mobile", "swift", "kotlin"],
    "Data": ["database", "sql", "postgres", "mongodb", "redis", "data", "analytics", "pandas", "spark"],
    "Security": ["security", "crypto", "encryption", "vulnerability", "pentest", "cve", "auth"],
    "Game": ["game", "gamedev", "unity", "unreal", "godot", "pixel"],
    "Docs/Education": ["tutorial", "learn", "documentation", "course", "awesome", "guide", "book"],
}


def classify_repo(topics, description):
    text = f"{topics} {description}".lower()
    scores = {}
    for category, keywords in CATEGORY_KEYWORDS.items():
        score = sum(1 for kw in keywords if kw in text)
        if score > 0:
            scores[category] = score
    if scores:
        return max(scores, key=scores.get)
    return "Other"


def load_data(days=7):
    if not os.path.exists(CSV_FILE):
        print(f"Error: {CSV_FILE} not found. Run scraper.py first.")
        sys.exit(1)

    df = pd.read_csv(CSV_FILE)
    df["date"] = pd.to_datetime(df["date"])
    cutoff = datetime.now() - timedelta(days=days)
    return df[df["date"] >= cutoff]


def analyze_languages(df):
    lang_counts = df.groupby("language").size().sort_values(ascending=False)
    lang_stars = df.groupby("language")["stars_total"].mean().sort_values(ascending=False)
    return lang_counts, lang_stars


def find_rising_repos(df):
    repo_freq = df.groupby("full_name").agg(
        appearances=("date", "nunique"),
        avg_stars=("stars_total", "mean"),
        language=("language", "first"),
        url=("url", "first"),
        description=("description", "first"),
    ).sort_values("appearances", ascending=False)
    return repo_freq[repo_freq["appearances"] >= 2]


def detect_categories(df):
    df = df.copy()
    df["category"] = df.apply(
        lambda r: classify_repo(str(r.get("topics", "")), str(r.get("description", ""))),
        axis=1,
    )
    return df["category"].value_counts()


def generate_report(df, lang_counts, lang_stars, rising, categories):
    date_now = datetime.now().strftime("%Y-%m-%d")
    lines = [
        f"# GitHub Trending Insight Report",
        f"**Generated:** {date_now}",
        f"**Period:** Last 7 days | **Repos tracked:** {len(df)} | **Unique repos:** {df['full_name'].nunique()}",
        "",
        "---",
        "",
        "## Top Languages",
        "",
        "| Rank | Language | Appearances | Avg Stars |",
        "|------|----------|-------------|-----------|",
    ]

    for i, (lang, count) in enumerate(lang_counts.head(10).items(), 1):
        avg = int(lang_stars.get(lang, 0))
        lines.append(f"| {i} | {lang} | {count} | {avg:,} |")

    lines += [
        "",
        "**Insight:** Fokus belajar/kontribusi di bahasa top 3. Repo yang pakai bahasa ini punya traffic tinggi, PR kamu lebih visible.",
        "",
        "---",
        "",
        "## Rising Repos (Multiple Days Trending)",
        "",
    ]

    if len(rising) == 0:
        lines.append("_Belum ada data cukup. Jalankan scraper beberapa hari dulu._")
    else:
        lines += [
            "| Repo | Days | Avg Stars | Language |",
            "|------|------|-----------|----------|",
        ]
        for name, row in rising.head(10).iterrows():
            desc = str(row.get("description", ""))[:60]
            lines.append(f"| [{name}]({row['url']}) | {row['appearances']} | {int(row['avg_stars']):,} | {row['language']} |")

        lines += [
            "",
            "**Insight:** Repo muncul berkali-kali = momentum tinggi. Cek issues, cari `good first issue` atau `help wanted`. Ini target kontribusi terbaik.",
            "",
        ]

    lines += [
        "---",
        "",
        "## Category Trends",
        "",
        "| Category | Count |",
        "|----------|-------|",
    ]

    for cat, count in categories.items():
        lines.append(f"| {cat} | {count} |")

    lines += [
        "",
        "**Insight:** Kategori dominan = area yang lagi hot. Kalau minatmu sejajar, kontribusi di area ini dampaknya lebih besar.",
        "",
        "---",
        "",
        "## Rekomendasi Hari Ini",
        "",
    ]

    # Generate recommendation
    top_lang = lang_counts.index[0] if len(lang_counts) > 0 else "Unknown"
    if len(rising) > 0:
        top_repo = rising.index[0]
        top_url = rising.iloc[0]["url"]
        lines += [
            f"1. **Bahasa fokus:** {top_lang}",
            f"2. **Target kontribusi:** [{top_repo}]({top_url})",
            f"   - Cek issues label `good first issue` atau `help wanted`",
            f"   - Baca CONTRIBUTING.md di repo tersebut",
            f"   - Mulai dari docs fix atau minor bug → build trust",
            f"3. **Kategori hot:** {categories.index[0] if len(categories) > 0 else 'N/A'}",
        ]
    else:
        lines += [
            f"1. **Bahasa fokus:** {top_lang}",
            "2. **Target kontribusi:** Data belum cukup. Jalankan scraper beberapa hari.",
            f"3. **Kategori hot:** {categories.index[0] if len(categories) > 0 else 'N/A'}",
        ]

    lines += [
        "",
        "---",
        "",
        "_Generated by analyzer.py — GitHub Trending Insight Pipeline_",
    ]

    return "\n".join(lines)


def main():
    print("Loading data (last 7 days)...")
    df = load_data(days=7)
    print(f"Found {len(df)} records, {df['full_name'].nunique()} unique repos.\n")

    lang_counts, lang_stars = analyze_languages(df)
    print("=== TOP LANGUAGES ===")
    for lang, count in lang_counts.head(5).items():
        print(f"  {lang}: {count} appearances")

    rising = find_rising_repos(df)
    print(f"\n=== RISING REPOS ({len(rising)} repos trending multiple days) ===")
    for name, row in rising.head(5).iterrows():
        print(f"  {name} — {row['appearances']} days, ~{int(row['avg_stars']):,} stars")

    categories = detect_categories(df)
    print(f"\n=== CATEGORIES ===")
    for cat, count in categories.head(5).items():
        print(f"  {cat}: {count}")

    report = generate_report(df, lang_counts, lang_stars, rising, categories)
    with open(REPORT_FILE, "w", encoding="utf-8") as f:
        f.write(report)
    print(f"\nReport saved to {REPORT_FILE}")


if __name__ == "__main__":
    main()
