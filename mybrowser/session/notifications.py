from datetime import datetime
from typing import Literal, TypedDict, List

NotificationType = Literal["primary", "secondary", "success", "warning", "danger", "info"]


class Notification(TypedDict):
    msg_type: NotificationType
    msg_header: str
    msg_content: str
    timestamp: str


def post_notification(
        notifications: List[Notification],
        msg_type: NotificationType,
        msg_header: str,
        msg_content: str
):
    notifications.append(Notification(
        msg_type=msg_type,
        msg_header=msg_header,
        msg_content=msg_content,
        timestamp=datetime.now().isoformat()
    ))