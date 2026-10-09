from schema import Label

INBOX_LABEL_ID = "INBOX"

LABEL_PREFIX = "Classifier/"

class LabelManager:
    def __init__(self, service):
        self.service = service
        self._cache: dict[str, str] = {}

    def _fetch_existing_labels(self) -> dict[str, str]:
        response = self.service.users().labels().list(userId="me").execute()
        return {label["name"]: label["id"] for label in response.get("labels", [])}


    def get_or_create_id(self, label: Label) -> str:
        display_name = LABEL_PREFIX + label.value.replace("_", " ").title()

        if display_name in self._cache:
            return self._cache[display_name]

        if not self._cache:
            self._cache.update(self._fetch_existing_labels())

        if display_name in self._cache:
            return self._cache[display_name]

        created = self.service.users().labels().create(
            userId="me",
            body={
                "name": display_name,
                "labelListVisibility": "labelShow",
                "messageListVisibility": "show"
            }
        ).execute()
        self._cache[display_name] = created["id"]
        return created["id"]

def apply_sorted(service, label_manager: LabelManager, message_id: str, label: Label) -> None:
    label_id = label_manager.get_or_create_id(label)
    service.users().messages().modify(
        userId = "me",
        id = message_id,
        body = {
            "addLabelIds": [label_id]
        }
    ).execute()

def apply_archived(service, label_manager: LabelManager, message_id: str, label: Label) -> None:
    label_id = label_manager.get_or_create_id(label)
    service.users().messages().modify(
        userId = "me",
        id = message_id,
        body = {
            "addLabelIds": [label_id],
            "removeLabelIds": INBOX_LABEL_ID
        }
    ).execute()

def apply_trash(service, message_id: str) -> None:
    service.users().messages().trash(userId = "me", id=message_id).execute()

def apply_outcome(service, label_manager: LabelManager, email: dict, bucket: str, label: Label | None) -> None:
    message_id = email["id"]

    if bucket == "sorted":
        apply_sorted(service, label_manager, message_id, label)
    elif bucket == "archived":
        apply_archived(service, label_manager, message_id, label)
    elif bucket == "deleted":
        apply_trash(service, message_id)
    elif bucket == "left":
        pass
    elif bucket == "relabeled":
        from schema import AUTO_ARCHIVED_LABELS
        
        if label in AUTO_ARCHIVED_LABELS: apply_archived(service, label_manager, message_id, label)
        else: apply_sorted(service, label_manager, message_id, label)
    
    else:
        raise ValueError(f"Unknown bucket '{bucket}' -- no Gmail action defined for it")