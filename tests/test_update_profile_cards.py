import importlib.util
import pathlib
import unittest


MODULE_PATH = pathlib.Path(__file__).resolve().parent.parent / "scripts" / "update_profile_cards.py"
SPEC = importlib.util.spec_from_file_location("update_profile_cards", MODULE_PATH)
MODULE = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(MODULE)


class BuildSnapshotTests(unittest.TestCase):
    def test_build_snapshot_aggregates_non_fork_metrics(self) -> None:
        user = {"public_repos": 26, "followers": 4}
        repos = [
            {
                "name": "byte-of-nanobot",
                "fork": False,
                "stargazers_count": 32,
                "forks_count": 5,
                "language": "Python",
            },
            {
                "name": "cosbench-guide",
                "fork": False,
                "stargazers_count": 10,
                "forks_count": 2,
                "language": "Java",
            },
            {
                "name": "upstream-fork",
                "fork": True,
                "stargazers_count": 99,
                "forks_count": 50,
                "language": "Rust",
            },
        ]
        languages_by_repo = {
            "byte-of-nanobot": {"Python": 900, "Shell": 100},
            "cosbench-guide": {"Java": 700, "Go": 300},
        }

        snapshot = MODULE.build_snapshot(user, repos, languages_by_repo)

        self.assertEqual(snapshot["public_repos"], 26)
        self.assertEqual(snapshot["followers"], 4)
        self.assertEqual(snapshot["source_repos"], 2)
        self.assertEqual(snapshot["stars"], 42)
        self.assertEqual(snapshot["forks"], 7)
        self.assertEqual(
            snapshot["top_languages"],
            [
                ("Python", 45.0),
                ("Java", 35.0),
                ("Go", 15.0),
                ("Shell", 5.0),
            ],
        )


class RenderSvgTests(unittest.TestCase):
    def test_render_stats_card_includes_snapshot_values(self) -> None:
        snapshot = {
            "public_repos": 26,
            "source_repos": 16,
            "followers": 4,
            "stars": 79,
            "forks": 15,
            "top_languages": [
                ("Python", 35.9),
                ("Java", 25.7),
                ("Go", 22.4),
                ("TypeScript", 5.2),
                ("JavaScript", 3.6),
            ],
        }

        svg = MODULE.render_stats_card(snapshot, "2026-04-05")

        self.assertIn("GitHub Snapshot", svg)
        self.assertIn("PUBLIC API SNAPSHOT • 2026-04-05", svg)
        self.assertIn(">79</text>", svg)
        self.assertIn(">15</text>", svg)

    def test_render_languages_card_renders_top_five_languages(self) -> None:
        snapshot = {
            "top_languages": [
                ("Python", 35.9),
                ("Java", 25.7),
                ("Go", 22.4),
                ("TypeScript", 5.2),
                ("JavaScript", 3.6),
                ("Shell", 3.2),
            ],
            "source_repos": 16,
        }

        svg = MODULE.render_languages_card(snapshot, "2026-04-05")

        self.assertIn("Top Languages", svg)
        self.assertIn("16 NON-FORK REPOS • 2026-04-05", svg)
        self.assertIn("Python", svg)
        self.assertIn("JavaScript", svg)
        self.assertNotIn("Shell", svg)


class RenderReadmeTests(unittest.TestCase):
    def test_build_byte_of_entries_uses_description_and_homepage(self) -> None:
        repos = [
            {
                "name": "byte-of-nanobot",
                "fork": False,
                "description": "Automation guide",
                "html_url": "https://github.com/sine-io/byte-of-nanobot",
                "homepage": "https://www.sineio.top/byte-of-nanobot",
                "updated_at": "2026-04-01T12:00:00Z",
            },
            {
                "name": "byte-of-vdbench",
                "fork": False,
                "description": "",
                "html_url": "https://github.com/sine-io/byte-of-vdbench",
                "homepage": "",
                "updated_at": "2026-04-05T12:00:00Z",
            },
            {
                "name": "byte-of-upstream",
                "fork": True,
                "description": "skip me",
                "html_url": "https://github.com/sine-io/byte-of-upstream",
                "homepage": "",
                "updated_at": "2026-04-06T12:00:00Z",
            },
        ]

        entries = MODULE.build_byte_of_entries(repos)

        self.assertEqual(
            entries,
            [
                {
                    "emoji": "💾",
                    "title": "Byte of Vdbench",
                    "focus": "Block/file storage testing",
                    "repo_url": "https://github.com/sine-io/byte-of-vdbench",
                    "site_url": "",
                },
                {
                    "emoji": "🤖",
                    "title": "Byte of Nanobot",
                    "focus": "Automation guide",
                    "repo_url": "https://github.com/sine-io/byte-of-nanobot",
                    "site_url": "https://www.sineio.top/byte-of-nanobot",
                },
            ],
        )

    def test_render_byte_of_section_includes_links(self) -> None:
        entries = [
            {
                "emoji": "🤖",
                "title": "Byte of Nanobot",
                "focus": "Automation guide",
                "repo_url": "https://github.com/sine-io/byte-of-nanobot",
                "site_url": "https://www.sineio.top/byte-of-nanobot",
            },
            {
                "emoji": "☁️",
                "title": "Byte of Cosbench",
                "focus": "Object storage benchmarking",
                "repo_url": "https://github.com/sine-io/byte-of-cosbench",
                "site_url": "",
            },
        ]

        section = MODULE.render_byte_of_section(entries)

        self.assertIn("## 🚀 The Byte-of Series", section)
        self.assertIn("| Series | Focus | Links |", section)
        self.assertIn("[Repo](https://github.com/sine-io/byte-of-nanobot)", section)
        self.assertIn("[Site](https://www.sineio.top/byte-of-nanobot)", section)
        self.assertIn("| ☁️ **Byte of Cosbench** | Object storage benchmarking | [Repo](https://github.com/sine-io/byte-of-cosbench) |", section)

    def test_replace_marked_section_updates_readme_body(self) -> None:
        readme = """before
<!-- byte-of-series:start -->
old
<!-- byte-of-series:end -->
after
"""

        updated = MODULE.replace_marked_section(
            readme,
            "byte-of-series",
            "new section",
        )

        self.assertEqual(
            updated,
            """before
<!-- byte-of-series:start -->
new section
<!-- byte-of-series:end -->
after
""",
        )


if __name__ == "__main__":
    unittest.main()
