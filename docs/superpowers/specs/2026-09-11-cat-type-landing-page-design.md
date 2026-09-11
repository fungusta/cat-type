# Cat Type landing page design

## Goal

Help a first-time visitor understand Cat Type through its two strongest moments: watch the cat move, then customize it. The primary conversion is a platform download.

## Audience and voice

The audience is a new user discovering Cat Type. Copy uses calm product language with occasional dry cat asides. It uses real Cat Type terms: typing companion, cat style, wardrobe, achievement, and Mix it up.

## Visual direction

The page uses a warm, companionable visual system: cream and paper surfaces, terracotta accents, forest green actions, dark brown text, and lightly illustrated desk cues. The existing flat cat artwork is the focal point. The page should feel authored and specific to Cat Type, avoiding stock imagery, generic dashboard patterns, decorative gradients, excessive rounded-card UI, and empty AI-style marketing language.

## Page structure

1. A compact wordmark and navigation links to movement, wardrobe, and downloads.
2. A hero with the headline “A tiny friend for every keystroke,” supporting copy, a detected-platform download action, and a three-platform strip for Windows, macOS, and Linux.
3. A tiny typing window where a visitor can enter a short line and see the cat react locally.
4. A wardrobe shelf beside the cat with one clear action, “Mix it up,” that varies the outfit using existing accessory SVGs. Visitors do not configure a full accessory form on the landing page.
5. Three proof points based on actual behavior: paws follow the keyboard side, spacebar taps both paws, and fast typing makes the cat excited.
6. A visual rail showing the six cat styles and a small selection of outfits.
7. A download and trust area with version/build context and the note that typed text is not collected.

## Interaction and data flow

The typing demo listens only to the local text field and maps short-lived input state to idle, paw, and excited visual states. Mix it up selects from a fixed local list of existing accessory combinations and updates the displayed cat without a network request. Download buttons link to the project’s release destinations; platform detection only changes the button label and does not block access to other platforms.

## Responsive and accessibility requirements

The hero becomes a single column on narrow screens. All controls have visible labels, keyboard focus styles, and semantic button/input elements. Motion is decorative and pauses or remains understandable when reduced motion is requested. The typing demo has an accessible label and never requires typing to read the page.

## Technology decision

Do not use three.js. Cat Type’s expressive artwork is flat SVG, and the homepage moment is better served by CSS and lightweight JavaScript. A 3D scene would add payload and complexity without improving the watch-and-customize experience. The page should remain a small static surface that can be hosted without a runtime service.

## Validation

Verify the page at desktop and narrow widths, test keyboard focus and reduced-motion behavior, confirm the typing demo transitions and Mix it up action, check all six cat styles and accessory assets load, and verify platform download links and favicon metadata.
