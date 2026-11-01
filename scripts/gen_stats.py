#!/usr/bin/env python3
"""
Generate the GitHub profile stat cards as static SVG.

Renders assets/stats.svg and assets/langs.svg from live GitHub API data so the
profile README never depends on a third-party badge service (shields.io and
github-readme-stats have both had outages; a paused deployment leaves a broken
image in the README).

Usage:
    python3 scripts/gen_stats.py                 # reads GITHUB_TOKEN from env
    python3 scripts/gen_stats.py --token $TOKEN

Output is deterministic for a given input, so the weekly Action only produces a
commit when the numbers actually change.
"""

import json
import os
import subprocess
import sys
import urllib.request

OWNER = os.environ.get("PROFILE_OWNER", "rollroyces")

# Palette mirrors rollroyces.github.io
BG_A, BG_B = "#0a0e1a", "#1e293b"
CYAN, EMERALD = "#22d3ee", "#34d399"
TEXT, MUTED = "#e2e8f0", "#94a3b8"
BORDER = "#334155"

LANG_COLORS = {
    "Python": "#3572A5", "JavaScript": "#f1e05a", "TypeScript": "#3178c6",
    "R": "#198CE7", "HTML": "#e34c26", "CSS": "#563d7c", "Lean": "#4d4d4d",
    "Jupyter Notebook": "#DA5B0B", "Rust": "#dea584", "Shell": "#89e051",
    "Java": "#b07219", "C": "#555555", "C++": "#f34b7d", "Go": "#00ADD8",
    "Ruby": "#701516", "PHP": "#4F5D95", "Swift": "#F05138", "Kotlin": "#A97BFF",
    "Dart": "#00B4AB", "Lua": "#000080", "Scala": "#c22d40",
}


def gh_graphql(query, token):
    req = urllib.request.Request(
        "https://api.github.com/graphql",
        data=json.dumps({"query": query}).encode(),
        headers={
            "Authorization": f"bearer {token}",
            "Content-Type": "application/json",
            "User-Agent": "profile-stats-generator",
        },
    )
    with urllib.request.urlopen(req, timeout=45) as r:
        return json.load(r)


def fetch_stats(token):
    q = """
    { viewer { followers { totalCount }
        repositories(first: 100, ownerAffiliations: OWNER, isFork: false, privacy: PUBLIC) {
          totalCount
          nodes { stargazerCount primaryLanguage { name } }
        }
        contributionsCollection {
          commitContributionsByRepository(maxRepositories: 100) {
            contributions(first: 1) { totalCount }
          }
        } } }
    """
    d = gh_graphql(q, token)["data"]["viewer"]
    langs = {}
    for r in d["repositories"]["nodes"]:
        if r.get("primaryLanguage"):
            n = r["primaryLanguage"]["name"]
            langs[n] = langs.get(n, 0) + 1
    commits = sum(c["contributions"]["totalCount"]
                  for c in d["contributionsCollection"]["commitContributionsByRepository"])
    stars = sum(r["stargazerCount"] for r in d["repositories"]["nodes"])
    return {
        "followers": d["followers"]["totalCount"],
        "repos": d["repositories"]["totalCount"],
        "stars": stars,
        "commits": commits,
        "langs": sorted(langs.items(), key=lambda x: (-x[1], x[0]))[:6],
    }


def fetch_public_repo_count(token):
    req = urllib.request.Request(
        f"https://api.github.com/users/{OWNER}",
        headers={"Authorization": f"token {token}", "User-Agent": "profile-stats-generator"},
    )
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.load(r)["public_repos"]


def esc(s):
    return (str(s).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;"))


def stats_svg(s, public_repos):
    W, H = 480, 200
    tiles = [
        ("Total stars", f"{s['stars']:,}", CYAN),
        ("Commits (1 yr)", f"{s['commits']:,}", EMERALD),
        ("Followers", f"{s['followers']:,}", CYAN),
        ("Public repos", f"{public_repos:,}", EMERALD),
    ]
    p = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" '
        f'viewBox="0 0 {W} {H}" role="img" aria-label="GitHub stats for {OWNER}">',
        f'<defs><linearGradient id="g" x1="0" y1="0" x2="1" y2="1">'
        f'<stop offset="0%" stop-color="{BG_A}"/><stop offset="100%" stop-color="{BG_B}"/>'
        f'</linearGradient></defs>',
        f'<rect width="{W}" height="{H}" rx="10" fill="url(#g)" stroke="{BORDER}"/>',
        # avatar mark
        f'<rect x="20" y="18" width="26" height="26" rx="7" fill="{BG_B}" stroke="{CYAN}" stroke-opacity="0.5"/>',
        f'<path d="M26 26 Q33 22 40 26 T47 26 M26 36 Q33 40 40 36 T47 36" '
        f'stroke="{CYAN}" stroke-width="1.6" fill="none" stroke-linecap="round"/>',
        f'<circle cx="33" cy="31" r="2" fill="{EMERALD}"/>',
        f'<text x="58" y="29" font-family="DejaVu Sans,Verdana,sans-serif" font-size="15" '
        f'font-weight="600" fill="{TEXT}">Royce Lam</text>',
        f'<text x="58" y="45" font-family="DejaVu Sans,Verdana,sans-serif" font-size="11" '
        f'fill="{MUTED}">ML × Bioinformatics Engineer</text>',
    ]
    # 2x2 tile grid
    tw, th, gx, gy = 208, 58, 12, 12
    x0, y0 = 20, 64
    for i, (label, value, color) in enumerate(tiles):
        cx = x0 + (i % 2) * (tw + gx)
        cy = y0 + (i // 2) * (th + gy)
        p.append(f'<rect x="{cx}" y="{cy}" width="{tw}" height="{th}" rx="8" '
                 f'fill="{BG_A}" fill-opacity="0.45" stroke="{BORDER}" stroke-opacity="0.7"/>')
        p.append(f'<text x="{cx + 14}" y="{cy + 22}" font-family="DejaVu Sans,Verdana,sans-serif" '
                 f'font-size="10.5" fill="{MUTED}">{esc(label)}</text>')
        p.append(f'<text x="{cx + 14}" y="{cy + 45}" font-family="DejaVu Sans,Verdana,sans-serif" '
                 f'font-size="22" font-weight="700" fill="{color}">{esc(value)}</text>')
    p.append(f'<text x="20" y="{H - 12}" font-family="DejaVu Sans,Verdana,sans-serif" '
             f'font-size="9.5" fill="{MUTED}" fill-opacity="0.8">'
             f'github.com/{OWNER}</text>')
    p.append("</svg>")
    return "\n".join(p)


def langs_svg(s):
    W, H = 330, 200
    langs = s["langs"]
    total = sum(c for _, c in langs) or 1
    p = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" '
        f'viewBox="0 0 {W} {H}" role="img" aria-label="Top languages for {OWNER}">',
        f'<defs><linearGradient id="g2" x1="0" y1="0" x2="1" y2="1">'
        f'<stop offset="0%" stop-color="{BG_A}"/><stop offset="100%" stop-color="{BG_B}"/>'
        f'</linearGradient></defs>',
        f'<rect width="{W}" height="{H}" rx="10" fill="url(#g2)" stroke="{BORDER}"/>',
        f'<text x="20" y="30" font-family="DejaVu Sans,Verdana,sans-serif" font-size="13" '
        f'font-weight="600" fill="{TEXT}">Top languages</text>',
        f'<text x="{W-20}" y="30" text-anchor="end" font-family="DejaVu Sans,Verdana,sans-serif" '
        f'font-size="10" fill="{MUTED}">{len(s["langs"])} shown</text>',
    ]
    y = 52
    maxw = W - 40 - 34
    for name, count in langs:
        color = LANG_COLORS.get(name, CYAN)
        w = max(4, int(maxw * count / total))
        p.append(f'<text x="20" y="{y}" font-family="DejaVu Sans,Verdana,sans-serif" '
                 f'font-size="11" fill="{TEXT}">{esc(name)}</text>')
        p.append(f'<text x="{W-20}" y="{y}" text-anchor="end" '
                 f'font-family="DejaVu Sans,Verdana,sans-serif" font-size="10.5" '
                 f'fill="{MUTED}">{count}</text>')
        p.append(f'<rect x="20" y="{y + 7}" width="{maxw}" height="7" rx="3.5" '
                 f'fill="{BORDER}" fill-opacity="0.45"/>')
        p.append(f'<rect x="20" y="{y + 7}" width="{w}" height="7" rx="3.5" fill="{color}"/>')
        y += 24
    p.append(f'<text x="20" y="{H - 12}" font-family="DejaVu Sans,Verdana,sans-serif" '
             f'font-size="9.5" fill="{MUTED}" fill-opacity="0.8">by repository count</text>')
    p.append("</svg>")
    return "\n".join(p)


def main():
    token = None
    if "--token" in sys.argv:
        token = sys.argv[sys.argv.index("--token") + 1]
    token = token or os.environ.get("GITHUB_TOKEN")
    if not token:
        sys.exit("GITHUB_TOKEN required (or pass --token)")

    s = fetch_stats(token)
    public_repos = fetch_public_repo_count(token)

    os.makedirs("assets", exist_ok=True)
    with open("assets/stats.svg", "w", encoding="utf-8") as fh:
        fh.write(stats_svg(s, public_repos))
    with open("assets/langs.svg", "w", encoding="utf-8") as fh:
        fh.write(langs_svg(s))
    print(json.dumps({**s, "public_repos": public_repos}, indent=2))


if __name__ == "__main__":
    main()
