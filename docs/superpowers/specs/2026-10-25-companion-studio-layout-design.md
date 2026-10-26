# Companion Studio settings layout

## Decision

Recompose the settings window around a compact companion studio shell. The new shell gives the updated Butter Sun palette and soft pill controls a matching information hierarchy instead of placing them inside the previous form layout.

## Shell

- Keep a persistent left toy rail for Settings, Metrics, Wardrobe, and Achievements.
- Put the cat preview inside the Cat Type brand area at the top of the rail.
- Remove the large middle Companion Studio title card.
- Let the active page begin directly in the main content area.
- Keep the rail and page surfaces neutral; Butter Sun marks active, enabled, focused, and recently saved states.

## Page composition

Each destination owns its own content structure. Page names provide enough orientation, so repeated purpose paragraphs are not shown beneath page titles.

### Settings

Use prototype-style shelves:

- **Companion:** cat style, favorite spot, preview scale, hang-around timing,
  and soft fade timing.
- **Behavior:** visibility while typing and launch-at-sign-in behavior.
- **Updates:** version status and the existing update/release actions remain
  available without changing the page's visual hierarchy.

Each setting is a readable row with a label, short consequence-oriented helper text, and a right-aligned control.

### Metrics

Use a compact aggregate summary followed by one focused activity shelf containing the chart, range/view controls, and period navigation.

### Wardrobe

Use an accessory tray with rounded item tiles. The page should stay about outfit selection; general settings belong to Settings.

### Achievements

Use a progress header followed by a reward album/grid. Each reward keeps its artwork, requirement, progress, and unlocked state together.

## Save feedback

The saved state is quiet when nothing has changed. After a setting interaction completes, show a prominent Butter Sun **Saved!** pill in the page heading area. Clear it after a short interval and do not show “Saved automatically” persistently.

## Copy and visual hierarchy

- Avoid redundant page-purpose descriptions when the page title and shelf labels are self-explanatory.
- Keep the compact cat preview as identity and orientation, not as a second page title.
- Use neutral shelves, dark ink, restrained muted text, and one Butter Sun accent.
- Keep the shared soft pill treatment for navigation, choices, and actions.
- Preserve visible keyboard focus and pressed-state movement.

## Prototype evidence

The throwaway prototype at `.superpowers/companion-studio-prototype/index.html` demonstrates the approved shell, tab ownership, compact rail preview, page-specific shelves, and delayed Saved! feedback. It is not production code.

## Out of scope

This layout decision does not change the settings data model, metrics calculations, wardrobe inventory, achievement rules, persistence behavior, or page destinations.
