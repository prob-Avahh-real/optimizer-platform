import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

class TestSmoke(unittest.TestCase):
    def test_agents_or_readme(self):
        self.assertTrue((ROOT / "AGENTS.md").exists() or (ROOT / "README.md").exists())

if __name__ == "__main__":
    unittest.main()
