# Rapid-Input Overlay Continuity and Cat Type v1.0.8

## Purpose

Prevent the cat overlay from flickering while the user types rapidly, without
allowing a new appearance to use stale caret geometry. Publish the fix as Cat
Type v1.0.8.

## Root Cause

Keyboard activity and caret discovery run asynchronously. Every accepted key
event immediately advances `CatTypeApp._last_key_at`, while `CaretTracker`
publishes snapshots from a background thread. The 16 ms Tk tick rejects a
snapshot captured more than 50 ms before the latest key. Today every rejected
snapshot enters the normal hide path, which withdraws a visible window; the
next fresh snapshot deiconifies it. Repeating that race during rapid input
produces visible hide/show flicker even though the animation is still active
and the snapshot still contains a usable caret rectangle.

## Overlay Policy

The existing 50 ms freshness threshold remains the gate for a new appearance.
An overlay that is currently hidden must not appear until the snapshot is
fresh, contains a rectangle, and is not a password-field snapshot.

Once the overlay is visible and anchored, a temporarily stale snapshot with a
usable rectangle may continue through the existing show/render path. The
anchor remains unchanged, while frame and opacity updates continue. A fresh
snapshot then resumes normal rendering without a withdraw/deiconify cycle.

Disabled state, an expired animation, a missing rectangle, and a detected
password field continue to hide the overlay immediately. Password suppression
therefore remains stronger than the continuity behavior.

## Alternatives Rejected

- Increasing the freshness tolerance only moves the race boundary and can
  still flicker when UI Automation or thread scheduling exceeds the new
  threshold.
- Looking up caret geometry synchronously from the Tk tick would block the UI
  thread on accessibility APIs and make animation responsiveness depend on
  external controls.
- Ignoring snapshot freshness entirely would let a new appearance anchor at a
  caret position from the previous typing burst.

## Testing

Add tick-level regression coverage using the real `AnimationState` and the
real event-draining path. The regression must show that a visible overlay with
an active animation and a valid snapshot stays on the show path when that
snapshot is 60 ms behind a new key event. A companion test must show that the
same stale snapshot cannot display an overlay that is currently hidden. The
existing caret/password, animation, rendering, packaging, and update tests
must remain green.

## Release

The release version is `1.0.8`, with annotated Git tag `v1.0.8`. Update every
version-bearing runtime, macOS, Windows, test, and README location checked by
`scripts/check_release_version.py`.

Before tagging, local tests and static checks must pass, then the pushed `main`
commit must pass the cross-platform build workflow. Push the immutable
annotated tag only after that build succeeds. The tag-triggered release
workflow must finish successfully and publish all five platform packages plus
`SHA256SUMS.txt` in a non-draft GitHub Release.

If the pre-tag build fails, do not push the tag. After the tag is pushed, do
not move or recreate it; any code or metadata correction requires another
patch version.
