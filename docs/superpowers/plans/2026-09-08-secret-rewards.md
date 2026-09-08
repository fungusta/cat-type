# Secret Rewards Implementation Plan

> **For agentic workers:** Execute the tightly coupled core inline; delegate only independent SVG artwork and final read-only review.

**Goal:** Add nine item achievements, secret discovery, and the beta bandana.

**Architecture:** Extend the existing one-to-one catalog and tracker; carry three
new slots through settings, renderer, platform surfaces, and both UI tabs.

**Tech Stack:** Python, Tkinter, Pillow, editable SVG, unittest, PyInstaller.

## Global constraints

- Follow `docs/superpowers/specs/2026-09-08-secret-rewards-design.md` exactly.
- Preserve the six existing reward IDs, equipped choices, and unlock permanence.
- Hidden rewards have no visible UI presence or contribution to totals until earned.
- Every achievement grants an item. Use existing counts; no key contents.
- Beta qualification comes from an explicit build flag, not version guessing.
- New slots are `neck`, `back`, `ears`; default `none`; max three wardrobe columns.
- No public release; retain the numeric version and designate this preview beta.

## Steps

- [x] Inspect baseline and run existing reward tests (30 passed).
- [ ] Add meaningful failing core tests in `tests/test_achievements.py` for new rules, unknown rules, beta entitlement and new slot persistence. Add `hidden=False` to Accessory and catalog entries/slot constants; update `progress`, `requirement`, visibility helper and tracker eligibility.
- [ ] Delegate nine SVG assets listed in the spec; generate a contact sheet and inspect compatibility with existing cats and paws.
- [ ] Extend `cat_artwork.py`, `cat_settings.py`, and all `cat_type.py` render paths/cache invalidation to five slots; cover each with behavior tests in existing artwork/integration test modules.
- [ ] Add failing UI tests for absent secret cards and items/counts, live reveal and multislot pending choices. Update both views and SettingsWindow to the new slots and dynamic visibility.
- [ ] Update README with public rewards and spoiler-free secret/beta behavior. Update package checks if needed; keep existing CI test discovery working.
- [ ] Run focused and full suites, inspect normal/narrow/scaled windows and artwork, request read-only review and resolve findings.
- [ ] Build and verify the Windows beta preview, record evidence, integrate locally and clean the owned worktree.
