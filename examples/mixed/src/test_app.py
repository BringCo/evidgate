import unittest

from app import estimate


class TestEstimate(unittest.TestCase):
    def test_positive(self):
        self.assertGreater(estimate(4, 2), 0)

    def test_edition_changes_value(self):
        self.assertNotEqual(estimate(0, 1), estimate(0, 3))


if __name__ == "__main__":
    unittest.main()
