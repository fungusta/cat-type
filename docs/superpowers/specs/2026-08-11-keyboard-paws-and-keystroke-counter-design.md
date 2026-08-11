# Keyboard-Aware Paws and Keystroke Counter

## Problem

Cat Type currently discards key identity and alternates its left- and
right-paw frames after every recognized keydown. The animation therefore does
not reflect which side of the keyboard was used. The application also has no
way to show how many keystrokes it has reacted to during the current session.

## Behavior

- A key on the left side of a conventional QWERTY keyboard uses the
  `tap-left` frame.
- A key on the right side uses the `tap-right` frame.
- Spacebar uses the existing `excited` frame, whose pose shows both paws
  tapping.
- The existing rapid-typing behavior remains: five keystrokes within 340 ms
  temporarily use the `excited` both-paws frame even when the latest key is on
  only one side.
- When typing slows, the latest explicit left or right action determines the
  paw frame. The cat returns to `idle` after the existing 160 ms tap interval
  and follows the existing visibility and fade timing.
- Every keydown processed while Cat Type is enabled increments a session
  counter. Operating-system key-repeat events count individually because each
  one produces a visible typing reaction.
- The counter starts at zero whenever Cat Type launches. It is not written to
  disk and does not increase while Cat Type is disabled. The artificial
  startup appearance does not increment it.
- The counter is shown only in the Settings window. It is not drawn in the cat
  overlay. The Settings window shows a clearly labelled
  **Keystrokes this session** value in the existing Companion card.
- The displayed value is initialized from the current session total whenever
  Settings opens and updates live while that window remains open.

## Keyboard Classification

Keyboard input is classified immediately inside `KeyboardMonitor`, before an
event reaches the application queue. Only a paw action and timestamp leave the
listener; the application never retains, reconstructs, logs, or persists the
actual key.

The conventional QWERTY split is:

- Left: backtick, `1` through `5`, `Q` through `T`, `A` through `G`, `Z`
  through `B`, Escape, Tab, Caps Lock, and left-side modifiers.
- Right: `6` through `0`, minus, equals, `Y` through `P`, bracket and
  backslash keys, `H` through `L`, semicolon and quote, `N` through slash,
  Backspace, Enter, navigation keys, arrow keys, number-pad keys, and
  right-side modifiers.
- Both: Spacebar.
- Function keys use their physical split: F1 through F6 are left and F7
  through F12 are right.
- Keys that the platform listener cannot place reliably, such as some media
  keys, use the existing alternating-paw fallback so they still produce a
  reaction.

Windows classification uses the virtual-key and scan-code information already
available to the low-level hook. macOS and Linux classification uses the
`pynput` key name, character, and virtual-key metadata available in the
portable listener. Shifted characters are normalized to their underlying key
where the platform supplies that information.

The Ctrl+Alt+Q quit chord continues to take precedence over normal activity.
It must still quit immediately and must not enqueue the `Q` as a typing event.

## Architecture and Data Flow

`KeyboardMonitor` gains small, pure classification helpers for Windows key
metadata and portable `pynput` keys. A classified keydown is queued as an
activity containing one of `left`, `right`, `both`, or `alternate`, plus its
monotonic timestamp. Non-key tray and lifecycle events retain their existing
meaning.

`CatTypeApp._tick` consumes the classified activity. If the companion is
enabled, it increments the session count, records the requested paw in
`AnimationState`, notifies caret tracking, and pushes the new total to an open
Settings window. Disabled activity is discarded as it is today.

`AnimationState.record_key` accepts the requested paw action and retains it
for the short tap interval. `frame_name` first applies the approved rapid-
typing override, then maps `both` to `excited`, explicit sides to their
matching tap frame, and `alternate` to the old alternating fallback. Timing,
opacity, and recent-activity tracking otherwise remain unchanged.

`CatTypeApp` owns the integer session total because it is application state,
not animation state or persisted user configuration. `SettingsWindow`
accepts the current total when constructed and exposes a narrow update method
that changes only the counter's `StringVar`. No new setting is added to
`AppSettings` or `SettingsStore`.

## Error Handling and Privacy

- A platform key that cannot be classified falls back to alternating paws
  instead of suppressing activity or failing the listener.
- Updating the counter is conditional on the Settings window still existing,
  matching the current lifecycle checks used when reopening Settings.
- Keyboard listener installation errors retain their current shutdown path.
- Event payloads contain only timing and paw-side information. Debug output
  must not include keys, characters, scan codes, or virtual-key codes.
- The README privacy description will be updated to state that keys are
  classified into paw sides and immediately discarded.

## Testing

Automated tests will cover:

- representative left, right, spacebar, function, modifier, navigation, and
  unknown keys for both Windows and portable classification helpers;
- queued keyboard activities containing a paw action but no retained key
  value;
- left, right, both, rapid-typing override, alternating fallback, idle,
  visibility, and fade behavior in `AnimationState`;
- one increment per enabled keydown, no increment while disabled, and no
  increment for the startup appearance;
- initial and live counter values in the Settings window;
- the absence of counter widgets or geometry changes in the cat overlay;
- the complete existing unit test suite on the supported CI platforms.

