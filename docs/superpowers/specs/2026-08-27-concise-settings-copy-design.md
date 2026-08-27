# Concise Settings Copy Design

## Goal

Make the Settings and Metrics pages faster to scan by removing decorative,
whimsical, explanatory, and privacy copy that is not needed to operate the
controls.

## Layout

Remove the large hero header from both pages. The Settings / Metrics switcher
becomes the first element in the scrollable content.

The animated cat preview remains useful because it reflects the selected cat
style. Move it into the Cat style card instead of preserving a
separate decorative banner. The narrow and wide layouts continue to use the
existing card columns and scrolling behavior.

## Copy to Remove

Remove:

- the `YOUR TINY TYPING PAL` badge;
- the Settings and Metrics hero headlines and descriptions;
- every card subtitle, including phrases such as `The important purr-t`,
  `Pick a favorite fluff`, and `Tiny bean or big floof`;
- the descriptions beneath the enabled and launch-at-startup toggles;
- the `smol` and `chonky` slider endpoint labels;
- the footer privacy message; and
- the Metrics activity privacy paragraph.

Do not replace removed text with shorter marketing copy.

## Copy to Keep

Keep text that identifies a setting, state, value, or action:

- page names: `Settings` and `Metrics`;
- card titles such as `Companion`, `Cat style`, `Cat size`, `Timing`,
  `Updates`, and `Activity`;
- control labels such as `Show my cat while I type`, `Start Cat Type when I
  sign in`, `Favorite spot`, `Preview scale`, `Hang around`, `Soft fade`,
  `Range`, and `View`;
- metric labels and values;
- the installed version and live update status;
- action buttons; and
- empty-state messages that explain why a chart has no marks.

## Component Changes

Allow cards to render a title without a subtitle. Card spacing should remain
consistent whether heading actions are present or absent.

Allow toggles to render without a description. Removing the second line must
also remove its reserved vertical space while preserving the full clickable
area, keyboard focus, and accessible title.

Place the existing preview canvas inside the Cat style card. Preserve its
animation and selected-style behavior; this change does not alter cat assets,
settings values, or persistence.

Remove footer-message fitting logic once the footer contains only its action
buttons.

## Behavior and Compatibility

No setting defaults, saved data, Metrics data, privacy behavior, update logic,
or application behavior changes. This is a presentation-only refinement.

The window remains resizable, scrollable, keyboard accessible, and usable at
its existing minimum dimensions. The Metrics view/range selector and remembered
chart preference remain unchanged.

## Testing

Automated coverage will verify that:

- the hero copy and all specified filler/privacy strings are absent;
- cards render title-only headings without empty subtitle space;
- both toggles render title-only rows and remain keyboard focusable;
- the preview canvas is mapped inside the Cat style card in the Settings view;
- the Settings / Metrics switcher is the first visible content section;
- the footer retains `Cancel` and `Save changes` without a message placeholder;
- functional labels, update status, Metrics controls, empty states, and save
  behavior remain available; and
- the complete cross-platform test selection remains green.

## Out of Scope

This change does not redesign colors, typography, cards, controls, chart
rendering, settings organization, window dimensions, or application branding
outside the Settings window.
