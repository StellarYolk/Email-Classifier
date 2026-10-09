import base64
from googleapiclient.discovery import build
from gmail_auth import get_credentials
from html_utils import clean_html_body

GMAIL_QUERY = "in:inbox is:unread"

def get_service():
    creds = get_credentials()
    return build("gmail", "v1", credentials=creds)

def fetch_unread_ids(service, max_results: int = 20, page_token: str | None = None):
    response = service.users().messages().list(
        userId = "me",
        q=GMAIL_QUERY,
        maxResults=max_results,
        pageToken = page_token
    ).execute()

    message_ids = [m["id"] for m in response.get("messages", [])]
    next_page_token = response.get("nextPageToken")
    return message_ids, next_page_token

def fetch_full_message(service, message_id: str) -> dict:
    return service.users().messages().get(userId="me", id=message_id, format="full").execute()

def _get_header(headers: list[dict]) -> str:
    sender, subject = None, None
    for h in headers:
        if h["name"].lower() == "from":
            sender = h["value"]
        elif h["name"].lower() == "subject":
            subject = h["value"]

        if subject and sender: return sender, subject
 
    return ""

def _decode_body_data(data: str) -> str:
    padded = data + "=" * (-len(data) % 4)
    return base64.urlsafe_b64decode(padded).decode("utf-8", errors="replace")

def _extract_body(payload: dict) -> str:

    def find_part(node: dict, mime_type: str) -> str | None:
        if node.get("mimeType") == mime_type:
            data = node.get("body", {}).get("data")
            if data:
                return _decode_body_data(data)

        for sub_part in node.get("parts", []):
            result = find_part(sub_part, mime_type)
            if result is not None: 
                return result

        return None

    plain = find_part(payload, "text/plain")
    if plain is not None:
        return plain

    html = find_part(payload, "text/html")
    if html is not None:
        return clean_html_body(html)

    return ""

def parse_message(raw_mesage: dict) -> dict:
    headers = raw_mesage["payload"].get("headers", [])
    sender, subject = _get_header(headers)
    return {
        "id": raw_mesage["id"],
        "sender": sender,
        "subject": subject,
        "body": _extract_body(raw_mesage["payload"])
    }


# Manual Smoke Test
if __name__ == "__main__":
    service = get_service()
    ids, next_token = fetch_unread_ids(service, max_results=20)
    print(f"Found {len(ids)} unread message(s). next_page_token = {next_token}")

    for msg_id in ids:
        raw = fetch_full_message(service, msg_id)
        email = parse_message(raw)
        print("-" * 50)
        print(f"id: {email["id"]}")
        print(f"from: {email["sender"]}")
        print(f"subject: {email["subject"]}")
        print(f"body: {email["body"][:200]!r}")