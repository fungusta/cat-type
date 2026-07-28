import unittest

from cat_type import (
    AnimationState,
    CaretLocator,
    ScreenRect,
    choose_overlay_position,
)


class FakeDegenerateTextRange:
    def __init__(self, can_move_forward: bool) -> None:
        self.can_move_forward = can_move_forward

    def GetBoundingRectangles(self) -> tuple:
        return ()

    def Clone(self) -> "FakeTextRangeProbe":
        return FakeTextRangeProbe(self.can_move_forward)


class FakeTextRangeProbe:
    def __init__(self, can_move_forward: bool) -> None:
        self.can_move_forward = can_move_forward
        self.rectangles: tuple = ()

    def MoveEndpointByUnit(
        self,
        endpoint: int,
        unit: int,
        count: int,
    ) -> int:
        del endpoint, unit
        if count == 1 and self.can_move_forward:
            self.rectangles = (100.0, 200.0, 8.0, 18.0)
            return 1
        if count == -1:
            self.rectangles = (100.0, 200.0, 8.0, 18.0)
            return -1
        return 0

    def GetBoundingRectangles(self) -> tuple:
        return self.rectangles


class CaretRangeTests(unittest.TestCase):
    def test_uses_next_character_geometry_for_degenerate_uia_caret(self) -> None:
        caret = CaretLocator._rect_from_uia_range(
            FakeDegenerateTextRange(can_move_forward=True)
        )

        self.assertEqual(caret, ScreenRect(100, 200, 102, 218))

    def test_uses_previous_character_right_edge_at_document_end(self) -> None:
        caret = CaretLocator._rect_from_uia_range(
            FakeDegenerateTextRange(can_move_forward=False)
        )

        self.assertEqual(caret, ScreenRect(108, 200, 110, 218))


class OverlayPositionTests(unittest.TestCase):
    def setUp(self) -> None:
        self.work = ScreenRect(0, 0, 1920, 1040)

    def test_prefers_above_and_right_of_caret(self) -> None:
        caret = ScreenRect(100, 300, 102, 320)
        self.assertEqual(
            choose_overlay_position(caret, 88, 88, self.work),
            (108, 206),
        )

    def test_flips_left_near_right_edge_but_stays_above(self) -> None:
        caret = ScreenRect(1900, 1020, 1902, 1040)
        self.assertEqual(
            choose_overlay_position(caret, 88, 88, self.work),
            (1806, 926),
        )

    def test_flips_below_when_caret_is_near_top(self) -> None:
        work = ScreenRect(-1920, 0, 0, 1040)
        caret = ScreenRect(-1918, 5, -1916, 25)
        self.assertEqual(
            choose_overlay_position(caret, 88, 88, work),
            (-1910, 31),
        )

    def test_uses_work_area_top_when_deciding_to_flip_below(self) -> None:
        work = ScreenRect(0, 40, 1920, 1080)
        caret = ScreenRect(200, 100, 202, 120)
        self.assertEqual(
            choose_overlay_position(caret, 88, 88, work),
            (208, 126),
        )


class AnimationStateTests(unittest.TestCase):
    def test_alternates_paws_then_settles_and_hides(self) -> None:
        animation = AnimationState(hide_after=0.9)
        animation.record_key(10.0)
        self.assertEqual(animation.frame_name(10.01), "tap-left")
        animation.record_key(10.2)
        self.assertEqual(animation.frame_name(10.21), "tap-right")
        self.assertEqual(animation.frame_name(10.4), "idle")
        self.assertTrue(animation.is_visible(10.8))
        self.assertFalse(animation.is_visible(11.2))

    def test_fast_typing_uses_excited_frame(self) -> None:
        animation = AnimationState()
        for timestamp in (1.0, 1.05, 1.1, 1.15, 1.2):
            animation.record_key(timestamp)
        self.assertEqual(animation.frame_name(1.21), "excited")

    def test_fades_during_the_end_of_the_visible_period(self) -> None:
        animation = AnimationState(hide_after=1.5, fade_seconds=0.3)
        animation.record_key(10.0)

        self.assertEqual(animation.opacity(11.19), 1.0)
        self.assertAlmostEqual(animation.opacity(11.35), 0.5)
        self.assertEqual(animation.opacity(11.5), 0.0)

        animation.record_key(11.6)
        self.assertEqual(animation.opacity(11.6), 1.0)


if __name__ == "__main__":
    unittest.main()
