#!/usr/bin/env python3

from __future__ import annotations

import argparse
import json
import os
import re
import urllib.parse
import urllib.request
from urllib.error import HTTPError
from collections import Counter
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from xml.sax.saxutils import escape


API_BASE = "https://api.github.com"
BYTE_OF_PREFIX = "byte-of-"
BYTE_OF_MARKER = "byte-of-series"
BYTE_OF_CARD_FILENAME = "byte-of-series-card.svg"
DISPLAY_NAME_OVERRIDES = {
    "ai": "AI",
    "cosbench": "Cosbench",
    "cpa": "CPA",
    "nanobot": "Nanobot",
    "vdbench": "Vdbench",
}
EMOJI_OVERRIDES = {
    "ai": "🧠",
    "cosbench": "☁️",
    "cpa": "📊",
    "nanobot": "🤖",
    "vdbench": "💾",
}
FOCUS_OVERRIDES = {
    "ai": "AI tutorial",
    "cosbench": "Object storage benchmarking",
    "cpa": "CPA tutorial",
    "nanobot": "Automation guide",
    "vdbench": "Block/file storage testing",
}


def fetch_json(url: str, token: str | None = None) -> Any:
    headers = {
        "Accept": "application/vnd.github+json",
        "User-Agent": "sine-io-profile-cards",
    }
    if token:
        headers["Authorization"] = f"Bearer {token}"

    request = urllib.request.Request(url, headers=headers)
    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            return json.load(response)
    except HTTPError as exc:
        if exc.code == 403 and not token:
            raise RuntimeError(
                "GitHub API rate limit exceeded. Re-run with GITHUB_TOKEN set."
            ) from exc
        raise


def fetch_repos(owner: str, token: str | None = None) -> list[dict[str, Any]]:
    repos: list[dict[str, Any]] = []
    page = 1

    while True:
        params = urllib.parse.urlencode(
            {
                "per_page": 100,
                "page": page,
                "type": "owner",
                "sort": "updated",
            }
        )
        page_data = fetch_json(f"{API_BASE}/users/{owner}/repos?{params}", token=token)
        if not page_data:
            return repos
        repos.extend(page_data)
        page += 1


def fetch_languages(repos: list[dict[str, Any]], token: str | None = None) -> dict[str, dict[str, int]]:
    languages_by_repo: dict[str, dict[str, int]] = {}
    for repo in repos:
        if repo.get("fork"):
            continue
        languages_by_repo[repo["name"]] = fetch_json(repo["languages_url"], token=token)
    return languages_by_repo


def build_snapshot(
    user: dict[str, Any],
    repos: list[dict[str, Any]],
    languages_by_repo: dict[str, dict[str, int]],
) -> dict[str, Any]:
    source_repos = [repo for repo in repos if not repo.get("fork")]
    language_bytes: Counter[str] = Counter()

    for repo in source_repos:
        language_bytes.update(languages_by_repo.get(repo["name"], {}))

    total_bytes = sum(language_bytes.values())
    top_languages: list[tuple[str, float]] = []
    if total_bytes:
        for name, byte_count in language_bytes.most_common(5):
            percentage = round(byte_count / total_bytes * 100, 1)
            top_languages.append((name, percentage))

    return {
        "public_repos": user["public_repos"],
        "followers": user["followers"],
        "source_repos": len(source_repos),
        "stars": sum(repo["stargazers_count"] for repo in source_repos),
        "forks": sum(repo["forks_count"] for repo in source_repos),
        "top_languages": top_languages,
    }


def build_byte_of_entries(repos: list[dict[str, Any]]) -> list[dict[str, str]]:
    entries: list[dict[str, str]] = []
    for repo in repos:
        name = repo["name"]
        if repo.get("fork") or not name.startswith(BYTE_OF_PREFIX):
            continue

        slug = name[len(BYTE_OF_PREFIX) :]
        display_name = DISPLAY_NAME_OVERRIDES.get(slug.lower(), slug.replace("-", " ").title())
        focus = (repo.get("description") or "").strip() or FOCUS_OVERRIDES.get(
            slug.lower(),
            f"{display_name} tutorial",
        )
        entries.append(
            {
                "emoji": EMOJI_OVERRIDES.get(slug.lower(), "📘"),
                "title": f"Byte of {display_name}",
                "focus": focus,
                "repo_url": repo["html_url"],
                "site_url": (repo.get("homepage") or "").strip(),
                "updated_at": (repo.get("updated_at") or ""),
            }
        )

    entries.sort(
        key=lambda entry: (
            entry["updated_at"],
            entry["title"].lower(),
        ),
        reverse=True,
    )
    for entry in entries:
        entry.pop("updated_at", None)
    return entries


def truncate_text(value: str, limit: int) -> str:
    text = value.strip()
    if len(text) <= limit:
        return text
    return f"{text[: limit - 3].rstrip()}..."


def render_byte_of_card(entries: list[dict[str, str]], snapshot_date: str) -> str:
    width = 1100
    row_height = 38
    start_y = 148
    card_height = 150 + len(entries) * row_height
    subtitle = f"{len(entries)} ACTIVE REPOS • SORTED BY LAST UPDATE • {snapshot_date}"
    rows: list[str] = []

    for index, entry in enumerate(entries):
        y = start_y + index * row_height
        divider_y = y - 18
        focus = truncate_text(entry["focus"], 52)

        if index:
            rows.append(
                f'  <line x1="32" y1="{divider_y}" x2="{width - 32}" y2="{divider_y}" stroke="#12324B" stroke-opacity="0.7"/>'
            )

        rows.extend(
            [
                f'  <text x="36" y="{y}" fill="#E9FBFF" font-family="JetBrains Mono, Consolas, monospace" font-size="18" font-weight="700">{escape(entry["emoji"] + " " + entry["title"])}</text>',
                f'  <text x="360" y="{y}" fill="#8AA6C2" font-family="JetBrains Mono, Consolas, monospace" font-size="13">{escape(focus)}</text>',
                f'  <rect x="{width - 188}" y="{y - 18}" width="68" height="24" rx="12" fill="#081728" stroke="#12324B"/>',
                f'  <text x="{width - 154}" y="{y - 2}" text-anchor="middle" fill="#00E5FF" font-family="JetBrains Mono, Consolas, monospace" font-size="11" font-weight="700">REPO</text>',
            ]
        )
        if entry["site_url"]:
            rows.extend(
                [
                    f'  <rect x="{width - 108}" y="{y - 18}" width="68" height="24" rx="12" fill="#081728" stroke="#12324B"/>',
                    f'  <text x="{width - 74}" y="{y - 2}" text-anchor="middle" fill="#4BD6C5" font-family="JetBrains Mono, Consolas, monospace" font-size="11" font-weight="700">SITE</text>',
                ]
            )

    rows_markup = "\n".join(rows)
    return f"""<svg width="{width}" height="{card_height}" viewBox="0 0 {width} {card_height}" fill="none" xmlns="http://www.w3.org/2000/svg" role="img" aria-labelledby="title desc">
  <title id="title">sine-io Byte-of series</title>
  <desc id="desc">A cyber-wave themed overview card for the Byte-of tutorial repositories.</desc>
  <defs>
    <linearGradient id="bg" x1="0" y1="0" x2="{width}" y2="{card_height}" gradientUnits="userSpaceOnUse">
      <stop stop-color="#040814"/>
      <stop offset="1" stop-color="#0A1124"/>
    </linearGradient>
    <linearGradient id="accent" x1="32" y1="0" x2="{width - 32}" y2="0" gradientUnits="userSpaceOnUse">
      <stop stop-color="#00E5FF"/>
      <stop offset="1" stop-color="#5B8CFF"/>
    </linearGradient>
    <filter id="glow" x="-20%" y="-20%" width="140%" height="140%" color-interpolation-filters="sRGB">
      <feGaussianBlur stdDeviation="6" result="blur"/>
      <feMerge>
        <feMergeNode in="blur"/>
        <feMergeNode in="SourceGraphic"/>
      </feMerge>
    </filter>
  </defs>

  <rect width="{width}" height="{card_height}" rx="24" fill="url(#bg)"/>
  <rect x="1" y="1" width="{width - 2}" height="{card_height - 2}" rx="23" stroke="#12324B" stroke-opacity="0.85"/>

  <path d="M32 54H170" stroke="url(#accent)" stroke-width="3.5" stroke-linecap="round" filter="url(#glow)"/>
  <text x="32" y="88" fill="#E9FBFF" font-family="JetBrains Mono, Consolas, monospace" font-size="22" font-weight="700">The Byte-of Series</text>
  <text x="32" y="112" fill="#82A8C9" font-family="JetBrains Mono, Consolas, monospace" font-size="12" letter-spacing="2">{escape(subtitle)}</text>

{rows_markup}
</svg>
"""


def render_byte_of_section(entries: list[dict[str, str]]) -> str:
    lines = [
        "## 🚀 The Byte-of Series",
        "",
        '<p align="center">',
        f'  <img src="./assets/{BYTE_OF_CARD_FILENAME}" alt="Byte-of series overview" width="100%" />',
        "</p>",
        "",
        "| Series | Focus | Links |",
        "| --- | --- | --- |",
    ]

    if not entries:
        lines.append("| - | No byte-of repositories found yet. | - |")
        return "\n".join(lines)

    for entry in entries:
        links = [f"[Repo]({entry['repo_url']})"]
        if entry["site_url"]:
            links.append(f"[Site]({entry['site_url']})")
        lines.append(
            f"| {entry['emoji']} **{entry['title']}** | {entry['focus']} | {' · '.join(links)} |"
        )

    return "\n".join(lines)


def replace_marked_section(readme_text: str, marker_name: str, new_content: str) -> str:
    pattern = re.compile(
        rf"(<!-- {re.escape(marker_name)}:start -->\n)(.*?)(\n<!-- {re.escape(marker_name)}:end -->)",
        re.DOTALL,
    )
    updated, count = pattern.subn(rf"\1{new_content}\3", readme_text, count=1)
    if count != 1:
        raise RuntimeError(f"Could not find unique marker block for {marker_name}")
    return updated


def render_stats_card(snapshot: dict[str, Any], snapshot_date: str) -> str:
    return f"""<svg width="540" height="220" viewBox="0 0 540 220" fill="none" xmlns="http://www.w3.org/2000/svg" role="img" aria-labelledby="title desc">
  <title id="title">sine-io GitHub snapshot</title>
  <desc id="desc">A cyber-wave themed GitHub snapshot card for sine-io with public repository, source repository, followers, stars, and forks counts.</desc>
  <defs>
    <linearGradient id="bg" x1="0" y1="0" x2="540" y2="220" gradientUnits="userSpaceOnUse">
      <stop stop-color="#040814"/>
      <stop offset="1" stop-color="#0A1124"/>
    </linearGradient>
    <linearGradient id="accent" x1="30" y1="0" x2="510" y2="0" gradientUnits="userSpaceOnUse">
      <stop stop-color="#00E5FF"/>
      <stop offset="1" stop-color="#5B8CFF"/>
    </linearGradient>
    <filter id="glow" x="-20%" y="-20%" width="140%" height="140%" color-interpolation-filters="sRGB">
      <feGaussianBlur stdDeviation="6" result="blur"/>
      <feMerge>
        <feMergeNode in="blur"/>
        <feMergeNode in="SourceGraphic"/>
      </feMerge>
    </filter>
  </defs>

  <rect width="540" height="220" rx="24" fill="url(#bg)"/>
  <rect x="1" y="1" width="538" height="218" rx="23" stroke="#12324B" stroke-opacity="0.85"/>

  <path d="M30 74C56 62 82 38 108 38C134 38 160 74 186 74C212 74 238 38 264 38C290 38 316 74 342 74C368 74 394 38 420 38C446 38 472 74 498 74C506 74 512 71 510 71" stroke="url(#accent)" stroke-width="3.5" stroke-linecap="round" filter="url(#glow)"/>

  <text x="30" y="110" fill="#E9FBFF" font-family="JetBrains Mono, Consolas, monospace" font-size="22" font-weight="700">GitHub Snapshot</text>
  <text x="30" y="134" fill="#82A8C9" font-family="JetBrains Mono, Consolas, monospace" font-size="12" letter-spacing="2">PUBLIC API SNAPSHOT • {escape(snapshot_date)}</text>

  <g font-family="JetBrains Mono, Consolas, monospace">
    <text x="30" y="172" fill="#8AA6C2" font-size="12">Public repos</text>
    <text x="30" y="198" fill="#F3FCFF" font-size="28" font-weight="700">{snapshot["public_repos"]}</text>

    <text x="170" y="172" fill="#8AA6C2" font-size="12">Source repos</text>
    <text x="170" y="198" fill="#F3FCFF" font-size="28" font-weight="700">{snapshot["source_repos"]}</text>

    <text x="310" y="172" fill="#8AA6C2" font-size="12">Followers</text>
    <text x="310" y="198" fill="#F3FCFF" font-size="28" font-weight="700">{snapshot["followers"]}</text>

    <text x="430" y="172" fill="#8AA6C2" font-size="12">Stars</text>
    <text x="430" y="198" fill="#F3FCFF" font-size="28" font-weight="700">{snapshot["stars"]}</text>
  </g>

  <rect x="360" y="96" width="150" height="34" rx="10" fill="#081728" stroke="#12324B"/>
  <text x="378" y="118" fill="#8AA6C2" font-family="JetBrains Mono, Consolas, monospace" font-size="12">Forks</text>
  <text x="470" y="118" text-anchor="end" fill="#00E5FF" font-family="JetBrains Mono, Consolas, monospace" font-size="16" font-weight="700">{snapshot["forks"]}</text>
</svg>
"""


def render_languages_card(snapshot: dict[str, Any], snapshot_date: str) -> str:
    palette = ["#00E5FF", "#5B8CFF", "#4BD6C5", "#8A7DFF", "#FFC857"]
    rows: list[str] = []
    start_y = 136
    row_gap = 18
    max_bar_width = 248
    max_percentage = snapshot["top_languages"][0][1] if snapshot["top_languages"] else 100.0

    for index, (language, percentage) in enumerate(snapshot["top_languages"][:5]):
        y = start_y + index * row_gap
        bar_y = y - 8
        fill_width = round(max_bar_width * percentage / max_percentage)
        rows.extend(
            [
                f'    <text x="30" y="{y}" fill="#D8F8FF">{escape(language)}</text>',
                f'    <rect x="128" y="{bar_y}" width="{max_bar_width}" height="8" rx="4" fill="#0D2235"/>',
                f'    <rect x="128" y="{bar_y}" width="{fill_width}" height="8" rx="4" fill="{palette[index]}"/>',
                f'    <text x="505" y="{y}" text-anchor="end" fill="#D8F8FF">{percentage:.1f}%</text>',
            ]
        )

    rows_markup = "\n".join(rows)
    return f"""<svg width="540" height="220" viewBox="0 0 540 220" fill="none" xmlns="http://www.w3.org/2000/svg" role="img" aria-labelledby="title desc">
  <title id="title">sine-io top languages</title>
  <desc id="desc">A cyber-wave themed top languages card for sine-io showing the current top five languages across non-fork repositories.</desc>
  <defs>
    <linearGradient id="bg" x1="0" y1="0" x2="540" y2="220" gradientUnits="userSpaceOnUse">
      <stop stop-color="#040814"/>
      <stop offset="1" stop-color="#0A1124"/>
    </linearGradient>
    <linearGradient id="accent" x1="30" y1="0" x2="510" y2="0" gradientUnits="userSpaceOnUse">
      <stop stop-color="#00E5FF"/>
      <stop offset="1" stop-color="#5B8CFF"/>
    </linearGradient>
    <filter id="glow" x="-20%" y="-20%" width="140%" height="140%" color-interpolation-filters="sRGB">
      <feGaussianBlur stdDeviation="6" result="blur"/>
      <feMerge>
        <feMergeNode in="blur"/>
        <feMergeNode in="SourceGraphic"/>
      </feMerge>
    </filter>
  </defs>

  <rect width="540" height="220" rx="24" fill="url(#bg)"/>
  <rect x="1" y="1" width="538" height="218" rx="23" stroke="#12324B" stroke-opacity="0.85"/>

  <path d="M30 54H120" stroke="url(#accent)" stroke-width="3.5" stroke-linecap="round" filter="url(#glow)"/>
  <text x="30" y="88" fill="#E9FBFF" font-family="JetBrains Mono, Consolas, monospace" font-size="22" font-weight="700">Top Languages</text>
  <text x="30" y="112" fill="#82A8C9" font-family="JetBrains Mono, Consolas, monospace" font-size="12" letter-spacing="2">{snapshot["source_repos"]} NON-FORK REPOS • {escape(snapshot_date)}</text>

  <g font-family="JetBrains Mono, Consolas, monospace" font-size="11">
{rows_markup}
  </g>
</svg>
"""


def write_cards(
    snapshot: dict[str, Any],
    byte_of_entries: list[dict[str, str]],
    snapshot_date: str,
    output_dir: Path,
) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / "github-stats-card.svg").write_text(
        render_stats_card(snapshot, snapshot_date),
        encoding="utf-8",
    )
    (output_dir / "top-langs-card.svg").write_text(
        render_languages_card(snapshot, snapshot_date),
        encoding="utf-8",
    )
    (output_dir / BYTE_OF_CARD_FILENAME).write_text(
        render_byte_of_card(byte_of_entries, snapshot_date),
        encoding="utf-8",
    )


def update_readme(readme_path: Path, byte_of_entries: list[dict[str, str]]) -> None:
    readme_text = readme_path.read_text(encoding="utf-8")
    section = render_byte_of_section(byte_of_entries)
    updated = replace_marked_section(readme_text, BYTE_OF_MARKER, section)
    readme_path.write_text(updated, encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description="Regenerate local GitHub profile stats cards.")
    parser.add_argument("--owner", default="sine-io")
    parser.add_argument("--output-dir", default="profile/assets")
    parser.add_argument("--readme-path", default="profile/README.md")
    parser.add_argument("--snapshot-date")
    args = parser.parse_args()

    token = os.getenv("GITHUB_TOKEN") or os.getenv("GH_TOKEN")
    snapshot_date = args.snapshot_date or datetime.now(UTC).date().isoformat()

    user = fetch_json(f"{API_BASE}/users/{args.owner}", token=token)
    repos = fetch_repos(args.owner, token=token)
    languages_by_repo = fetch_languages(repos, token=token)
    snapshot = build_snapshot(user, repos, languages_by_repo)
    byte_of_entries = build_byte_of_entries(repos)
    write_cards(snapshot, byte_of_entries, snapshot_date, Path(args.output_dir))
    update_readme(Path(args.readme_path), byte_of_entries)

    print(
        f"Updated profile cards for {args.owner} on {snapshot_date}: "
        f"{snapshot['public_repos']} public repos, {snapshot['stars']} stars."
    )


if __name__ == "__main__":
    main()
