"""Focused fail-closed inventory checks; no synthesis or aggregate CI."""
import unittest
from compare_pdk import check_corners, missing_used, normalized


class ComparisonGuards(unittest.TestCase):
    def test_corner_loss_rejected(self):
        for old, new in (({}, {}), ({'ss': 1}, {'tt': 1}),
                         ({'ss': 1, 'tt': 1}, {'ss': 1})):
            with self.subTest(old=old, new=new), self.assertRaises(ValueError):
                check_corners(old, new)
        check_corners({'ss': 1}, {'ss': 2, 'tt': 3})

    def test_used_definition_loss_detected(self):
        # Same guard is used independently for Liberty cells and LEF macros.
        self.assertEqual(missing_used({'used'}, {'unused': 1}), ['used'])
        self.assertEqual(missing_used({'used'}, {'used': 1}), [])

    def test_token_boundaries_preserved(self):
        self.assertNotEqual(normalized('a b'), normalized('ab'))
        self.assertEqual(normalized('a /* comment */ : "b c";'),
                         normalized('a:"b c";'))
        self.assertNotEqual(normalized('a:"b c";'), normalized('a:"bc";'))


if __name__ == '__main__':
    unittest.main()
