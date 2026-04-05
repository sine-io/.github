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


if __name__ == "__main__":
    unittest.main()
