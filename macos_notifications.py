"""Post Cat Type's own macOS notifications through the system notification center.

pystray's macOS backend runs ``osascript``, so its notices are attributed to
Script Editor and carry its icon. Posting from the app bundle instead lets
macOS show the Cat Type icon and name. Outside a bundle (running from source)
there is no app identity to post as, so callers fall back to the tray.
"""

from __future__ import annotations

import sys
from collections.abc import Callable
from pathlib import Path

_center = None
_delegate = None


def _notification_center():
    """The shared center, set up once with a delegate; None when unavailable."""
    global _center, _delegate
    if _center is not None:
        return _center
    if sys.platform != "darwin":
        return None
    try:
        from Foundation import NSBundle, NSObject
        import UserNotifications as notifications
    except ImportError:
        return None
    # The center raises for a process with no bundle identity.
    if not NSBundle.mainBundle().bundleIdentifier():
        return None

    class _ShowWhileOpen(NSObject):
        """Show notices as banners even while a Cat Type window is in front."""

        def userNotificationCenter_willPresentNotification_withCompletionHandler_(
            self, _center, _notification, completion,
        ):
            completion(
                notifications.UNNotificationPresentationOptionBanner
                | notifications.UNNotificationPresentationOptionList
            )

    center = notifications.UNUserNotificationCenter.currentNotificationCenter()
    _delegate = _ShowWhileOpen.alloc().init()
    center.setDelegate_(_delegate)
    _center = center
    return center


def post_notice(
    title: str, body: str, identifier: str, fallback: Callable[[], None] | None = None,
    picture: str | None = None,
) -> bool:
    """Post a notice as Cat Type; False when the native center is unavailable.

    macOS asks once whether Cat Type may send notifications. A person who
    declines is respected: nothing is shown. When macOS refuses the app itself
    (for example an unsigned build), ``fallback`` runs instead so the notice
    is not lost.
    ``picture`` is a PNG shown beside the text; macOS moves the file into its
    own store once the notice is delivered.
    """
    center = _notification_center()
    if center is None:
        return False
    import UserNotifications as notifications

    content = notifications.UNMutableNotificationContent.alloc().init()
    content.setTitle_(title)
    content.setBody_(body)
    if picture:
        from Foundation import NSURL

        attachment, _error = notifications.UNNotificationAttachment.attachmentWithIdentifier_URL_options_error_(
            "picture", NSURL.fileURLWithPath_(picture), None, None,
        )
        if attachment is not None:
            content.setAttachments_([attachment])
    request = notifications.UNNotificationRequest.requestWithIdentifier_content_trigger_(
        identifier, content, None,
    )

    def refused(error: object) -> None:
        if error is not None and fallback is not None:
            fallback()

    def authorized(granted: bool, error: object) -> None:
        if granted:
            center.addNotificationRequest_withCompletionHandler_(request, refused)
        else:
            refused(error)

    def checked(settings: object) -> None:
        # macOS reports a person's "Don't Allow" with the same error it uses
        # when it refuses the app outright, so read the saved choice first:
        # a declined permission is respected, not routed around.
        if settings.authorizationStatus() == notifications.UNAuthorizationStatusDenied:
            if picture:
                Path(picture).unlink(missing_ok=True)
            return
        center.requestAuthorizationWithOptions_completionHandler_(
            notifications.UNAuthorizationOptionAlert, authorized,
        )

    center.getNotificationSettingsWithCompletionHandler_(checked)
    return True
