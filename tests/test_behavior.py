import unittest
from dataclasses import fields
from unittest.mock import patch

from cat_type import (
    AppEvent,
    AnimationState,
    CaretLocator,
    ScreenRect,
    classify_portable_key,
    classify_windows_key,
    choose_fallback_position,
    choose_overlay_position,
)


class FakePortableKey:
    def __init__(self, char: str | None = None, name: str | None = None) -> None:
        self.char = char
        self.name = name


class KeyboardClassificationTests(unittest.TestCase):
    def test_windows_keys_follow_the_physical_keyboard_split(self) -> None:
        cases = (
            ((0x51, 0, 0), "left"),       # Q
            ((0x54, 0, 0), "left"),       # T
            ((0x59, 0, 0), "right"),      # Y
            ((0x4D, 0, 0), "right"),      # M
            ((0x20, 0, 0), "both"),       # Space
            ((0x70, 0, 0), "left"),       # F1
            ((0x76, 0, 0), "right"),      # F7
            ((0x10, 0x2A, 0), "left"),    # Generic left Shift
            ((0x10, 0x36, 0), "right"),   # Generic right Shift
            ((0x11, 0, 0), "left"),       # Generic left Ctrl
            ((0x11, 0, 1), "right"),      # Extended right Ctrl
            ((0x25, 0, 0), "right"),      # Left-arrow key cluster
            ((0x60, 0, 0), "right"),      # Numpad 0
            ((0xAD, 0, 0), "alternate"),  # Media mute
        )

        for arguments, expected in cases:
            with self.subTest(arguments=arguments):
                self.assertEqual(classify_windows_key(*arguments), expected)

    def test_portable_keys_follow_the_physical_keyboard_split(self) -> None:
        cases = (
            (FakePortableKey(char="q"), "left"),
            (FakePortableKey(char="!"), "left"),
            (FakePortableKey(char="y"), "right"),
            (FakePortableKey(char="^"), "right"),
            (FakePortableKey(char=" "), "both"),
            (FakePortableKey(name="space"), "both"),
            (FakePortableKey(name="shift_l"), "left"),
            (FakePortableKey(name="shift_r"), "right"),
            (FakePortableKey(name="f6"), "left"),
            (FakePortableKey(name="f7"), "right"),
            (FakePortableKey(name="left"), "right"),
            (FakePortableKey(name="media_volume_up"), "alternate"),
        )

        for key, expected in cases:
            with self.subTest(key=vars(key)):
                self.assertEqual(classify_portable_key(key), expected)

    def test_app_event_carries_a_paw_action_but_no_key_identity(self) -> None:
        event = AppEvent("key", 12.5, "left")

        self.assertEqual(event.paw, "left")
        self.assertEqual(
            {field.name for field in fields(event)},
            {"kind", "happened_at", "paw"},
        )


class FakeDegenerateTextRange:
    def __init__(
        self,
        can_move_forward: bool,
        forward_has_geometry: bool = True,
    ) -> None:
        self.can_move_forward = can_move_forward
        self.forward_has_geometry = forward_has_geometry

    def GetBoundingRectangles(self) -> tuple:
        return ()

    def Clone(self) -> "FakeTextRangeProbe":
        return FakeTextRangeProbe(
            self.can_move_forward,
            self.forward_has_geometry,
        )


class FakeTextRangeProbe:
    def __init__(
        self,
        can_move_forward: bool,
        forward_has_geometry: bool,
    ) -> None:
        self.can_move_forward = can_move_forward
        self.forward_has_geometry = forward_has_geometry
        self.rectangles: tuple = ()

    def MoveEndpointByUnit(
        self,
        endpoint: int,
        unit: int,
        count: int,
    ) -> int:
        del endpoint, unit
        if count == 1 and self.can_move_forward:
            if self.forward_has_geometry:
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

    def test_uses_previous_character_when_next_character_is_invisible(self) -> None:
        caret = CaretLocator._rect_from_uia_range(
            FakeDegenerateTextRange(
                can_move_forward=True,
                forward_has_geometry=False,
            )
        )

        self.assertEqual(caret, ScreenRect(108, 200, 110, 218))


class CaretFallbackTests(unittest.TestCase):
    def test_allows_corner_fallback_for_verified_text_control(self) -> None:
        locator = CaretLocator()

        with (
            patch("cat_type.IS_WINDOWS", True),
            patch.object(
                locator,
                "_locate_with_uia",
                return_value=(None, False, True),
            ),
            patch.object(locator, "_locate_with_win32", return_value=None),
        ):
            snapshot = locator.locate()

        self.assertTrue(snapshot.fallback_allowed)
        self.assertEqual(snapshot.source, "uia-fallback")


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

    def test_fallback_uses_preferred_work_area_corner(self) -> None:
        work = ScreenRect(-1920, 40, 0, 1080)
        expected = {
            "above-left": (-1914, 46),
            "above-right": (-94, 46),
            "below-left": (-1914, 986),
            "below-right": (-94, 986),
        }

        for placement, position in expected.items():
            with self.subTest(placement=placement):
                self.assertEqual(
                    choose_fallback_position(
                        88,
                        88,
                        work,
                        placement=placement,
                    ),
                    position,
                )


class AnimationStateTests(unittest.TestCase):
    def test_explicit_keyboard_sides_choose_matching_paws(self) -> None:
        animation = AnimationState(hide_after=0.9)

        animation.record_key(10.0, "left")
        self.assertEqual(animation.frame_name(10.01), "tap-left")
        animation.record_key(10.2, "right")
        self.assertEqual(animation.frame_name(10.21), "tap-right")

    def test_spacebar_uses_both_paws_then_settles(self) -> None:
        animation = AnimationState()

        animation.record_key(1.0, "both")

        self.assertEqual(animation.frame_name(1.01), "excited")
        self.assertEqual(animation.frame_name(1.17), "idle")

    def test_unknown_keys_keep_the_alternating_fallback(self) -> None:
        animation = AnimationState()

        animation.record_key(2.0, "alternate")
        self.assertEqual(animation.frame_name(2.01), "tap-left")
        animation.record_key(2.2, "alternate")
        self.assertEqual(animation.frame_name(2.21), "tap-right")

    def test_fast_typing_overrides_latest_side_with_both_paws(self) -> None:
        animation = AnimationState()
        for index, timestamp in enumerate((1.0, 1.05, 1.1, 1.15, 1.2)):
            paw = "left" if index % 2 == 0 else "right"
            animation.record_key(timestamp, paw)

        self.assertEqual(animation.frame_name(1.21), "excited")
        self.assertEqual(animation.frame_name(1.37), "idle")

    def test_settles_and_hides_on_the_existing_timing(self) -> None:
        animation = AnimationState(hide_after=0.9)
        animation.record_key(10.0, "left")

        self.assertEqual(animation.frame_name(10.17), "idle")
        self.assertTrue(animation.is_visible(10.8))
        self.assertFalse(animation.is_visible(11.2))

    def test_fades_during_the_end_of_the_visible_period(self) -> None:
        animation = AnimationState(hide_after=1.5, fade_seconds=0.3)
        animation.record_key(10.0, "left")

        self.assertEqual(animation.opacity(11.19), 1.0)
        self.assertAlmostEqual(animation.opacity(11.35), 0.5)
        self.assertEqual(animation.opacity(11.5), 0.0)

        animation.record_key(11.6, "right")
        self.assertEqual(animation.opacity(11.6), 1.0)


if __name__ == "__main__":
    unittest.main()
