# Automatic settings

Every setting change must be saved and applied without a Save button. Closing
the window must keep changes, including wardrobe choices.

Observe the persisted Tk variables after window construction and reuse the
existing settings normalization and save callback. Save discrete changes
synchronously so closing immediately cannot lose them. Use the same callback
for metrics preferences so failures are visible and retried consistently.
Debounce size changes by 200 ms to avoid rebuilding every animation frame while
the slider is being dragged; flush the latest size on another edit or close.
Ignore repeated normalized values to avoid redundant application side effects.

Replace Cancel and Save changes with Close and a short automatic-save status.
Saving must keep the window open. Show a failed save in the footer, allow later
changes to retry, and retry a failed save before closing. Retain the existing
save keyboard shortcut as a retry without closing the window.

Validate real settings-file persistence for controls and closing, wardrobe
selection/removal, normalization, duplicate events, and save-error recovery.
Unrelated autosaves must preserve a pending macOS permission request; an
explicit pause must still cancel it. Run the existing settings, wardrobe, and
application tests for regressions.

Keep the open enabled control synchronized with tray and permission changes
without triggering another save, so a later autosave cannot undo a tray pause.
