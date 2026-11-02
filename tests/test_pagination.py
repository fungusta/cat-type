import unittest
from dataclasses import FrozenInstanceError
from pagination import page_window, page_slice, page_label


class PaginationTests(unittest.TestCase):
    def test_empty_collection(self):
        window = page_window(0, 9, 4)
        self.assertEqual((window.index, window.page_count, window.start, window.end), (0, 0, 0, 0))
        self.assertEqual(page_label(window), 'Page 0 of 0')
        self.assertEqual(page_slice([], 9, 4), ())

    def test_single_page(self):
        window = page_window(3, 0, 4)
        self.assertEqual((window.index, window.page_count, window.start, window.end), (0, 1, 0, 3))
        self.assertEqual(page_label(window), 'Page 1 of 1')

    def test_clamps_page_index(self):
        self.assertEqual(page_window(22, -5, 4).index, 0)
        self.assertEqual(page_window(22, 99, 4).index, 5)
        self.assertEqual(page_slice(list(range(6)), 99, 4), (4, 5))

    def test_partial_final_page(self):
        window = page_window(22, 5, 4)
        self.assertEqual((window.index, window.page_count, window.start, window.end), (5, 6, 20, 22))
        self.assertEqual(page_label(window), 'Page 6 of 6')
        self.assertEqual(page_slice(tuple(range(6)), 1, 4), (4, 5))

    def test_validates_sizes(self):
        for total, size in [(-1, 4), (1, 0), (1, -1), (0, 0)]:
            with self.subTest(total=total, size=size), self.assertRaises(ValueError):
                page_window(total, 0, size)

    def test_window_is_immutable(self):
        with self.assertRaises(FrozenInstanceError):
            page_window(1, 0, 4).index = 3
