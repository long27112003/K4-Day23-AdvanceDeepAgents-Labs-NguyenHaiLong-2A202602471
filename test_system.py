"""test_system.py - Unit tests for check_citations, slugify, and with_retry."""
import unittest
from unittest.mock import MagicMock, patch

from check_citations import check
from research import slugify
from tools import RetryableError, with_retry


class TestResearchSystem(unittest.TestCase):
    def test_slugify(self):
        self.assertEqual(slugify("survey about world model"), "survey-about-world-model")
        self.assertEqual(slugify("../../path/traversal"), "path-traversal")
        self.assertEqual(slugify(""), "topic")
        self.assertTrue(len(slugify("a" * 100)) <= 60)

    def test_check_citations_valid(self):
        report = """# Title
## TL;DR
- Key point [1].
- Another point [2].

## Background
World models are promising [1, 2].

## Method
Comparing approach A and B [1-2].

## References
[1] Title A. arxiv. https://arxiv.org/abs/1803.10122 (2018)
[2] Title B. web. https://example.com/b (2024)
"""
        sources = [
            {"n": 1, "id": "1803.10122", "url": "https://arxiv.org/abs/1803.10122", "title": "Title A", "source": "arxiv"},
            {"n": 2, "id": "b", "url": "https://example.com/b", "title": "Title B", "source": "web"},
        ]
        problems = check(report, sources)
        self.assertEqual(problems, [])

    def test_check_citations_missing_source(self):
        report = """# Title
## TL;DR
- Key point [1].
## References
[1] Title A. arxiv. https://arxiv.org/abs/1803.10122 (2018)
"""
        sources = [
            {"n": 1, "id": "1", "url": "https://arxiv.org/abs/1803.10122", "title": "A", "source": "arxiv"},
            {"n": 2, "id": "2", "url": "https://arxiv.org/abs/1803.10123", "title": "B", "source": "arxiv"},
        ]
        problems = check(report, sources)
        self.assertTrue(any("never cited" in p for p in problems))

    @patch("time.sleep", return_value=None)
    def test_with_retry_success_after_failure(self, mock_sleep):
        fn = MagicMock(side_effect=[RetryableError("temp error"), "success"])
        res = with_retry(fn, attempts=3, base=0.1, cap=1.0)
        self.assertEqual(res, "success")
        self.assertEqual(fn.call_count, 2)
        mock_sleep.assert_called_once()


if __name__ == "__main__":
    unittest.main()
