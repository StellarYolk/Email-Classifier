import json
from datetime import datetime
from pathlib import Path

from schema import Label

MEMORY_FILE = Path("memory.json")
MEMORY_MD_FILE = Path("memory.md")

PROMOTION_THRESHOLD = 2
DEFAULT_MAX_PATTERNS = 15
DISTILL_MIN_PER_LABEL = 3

_EMPTY_MEMORY = {
    "schema_version": 1,
    "sender_rules": {},
    "pending_proposals": {},
    "correction_log": [],
    "unresolved_log": [],
    "patterns": []
}

def _now() -> str:
    return datetime.now().isoformat(timespec="seconds")


def load_memory() -> dict:
    if not MEMORY_FILE.exists():
        return json.loads(json.dumps(_EMPTY_MEMORY))

    with MEMORY_FILE.open("r") as f:
        return json.load(f)

def save_memory(memory: dict) -> None:
    with MEMORY_FILE.open("w") as f:
        json.dump(memory, f, indent=2)
        f.flush()

    _construct_memory_md(memory)

def _construct_memory_md(memory: dict) -> None:
    lines = ["# Memory", ""]

    lines.append("## sender rules")
    if not memory["sender_rules"]:
        lines.append("_None confirmed yet_")
    for sender, rule in memory["sender_rules"].items():
        lines.append(
            f"- {sender} -> **{rule["label"]}**"
            f"(confirmed {rule["confirmed_at"]}, {rule["correction_count"]} correction(s))"
        )

    lines.append("")
    lines.append("## Unresolved (ambiguous)")
    unresolved_count = len(memory(["unresolved_log"]))
    if unresolved_count == 0:
        lines.append("_None logged yet_")
    else:
        lines.append(f"_{unresolved_count} email(s) left unresolved during held review -- raw entries in memory.json, not shown here._")

    lines.append("")
    lines.append("## patterns")
    if not memory["patterns"]:
        lines.append("_None found yet_")
    for pattern in memory["patterns"]:
        if not pattern.get("active", True):
            continue
        lines.append(f"- **{pattern["label"]}**: {pattern["rule"]}")

    MEMORY_MD_FILE.write_text("\n".join(lines) + "\n")


def get_sender_rule(memory: dict, sender: str) -> Label | None:
    rule = memory["sender_rules"].get(sender)
    if rule is None: return None

    rule["last_matched"] = _now()
    return Label(rule["label"])


def get_active_patterns(memory: dict, max_patterns: int = DEFAULT_MAX_PATTERNS) -> list[str]:
    active = [p["rule"] for p in memory["patterns"] if p.get("active", True)]
    return active[-max_patterns:]


def log_correction(memory: dict, email: dict, original_label: Label, corrected_label: Label, source: str) -> dict:
    correction_id = f"corr_{len(memory["correction_log"]):06d}"

    entry = {
        "id": correction_id,
        "timestamp": _now(),
        "email_id": email["id"],
        "sender": email["sender"],
        "subject": email["subject"],
        "body_snippet": email["body"][:200],
        "original_label": original_label,
        "corrected_label": corrected_label,
        "source": source
    }
    memory["correction_log"].append(entry)

    sender = email["sender"]
    proposal = memory["pending_proposals"].get(sender)

    if proposal is None or proposal["suggested_label"] != corrected_label.value:
        proposal = {
            "suggested_label": corrected_label.value,
            "corrections": [],
            "first_seen": _now()
        }

    proposal["corrections"].append(correction_id)
    memory["pending_proposals"][sender] = proposal

    return proposal

def proposal_is_promotable(proposal: dict) -> bool:
    return len(proposal["corrections"]) >= PROMOTION_THRESHOLD

def log_unresolved(memory: dict, email: dict, original_label: Label, source: str) -> dict:
    entry = {
        "id": f"unres_{len(memory["unresolved_log"]):06d}",
        "timestamp": _now(),
        "email_id": email["id"],
        "sender": email["sender"],
        "subject": email["subject"],
        "body_snippet": email["body"][:200],
        "original_label": original_label.value,
        "source": source,
    }
    memory["unresolved_log"].append(entry)
    return entry

def confirm_sender_rule(memory: dict, sender: str, label: Label) -> None:
    proposal = memory["pending_proposals"].pop(sender, None)
    correction_count = len(proposal["corrections"]) if proposal else 1

    memory["sender_rules"][sender] = {
        "label": label.value,
        "confirmed_at": _now(),
        "correction_count": correction_count,
        "last_matched": None
    }

def dismiss_proposals(memory: dict, sender: dict) -> None:
    memory["pending_proposals"].pop(sender, None)

# def add_pattern(memory: dict, rule_text: str, label: Label, derived_from: list[str]) -> None:
#     pattern_id = f"pat_{len(memory["patterns"]) + 1:02d}"
#     memory["patterns"].append({
#         "id": pattern_id,
#         "rule": rule_text,
#         "label": label.value,
#         "derived_from": derived_from,
#         "created_at": _now(),
#         "active": True
#     })


def get_undistilled_groups(memory: dict, min_per_label: int = DISTILL_MIN_PER_LABEL) -> dict[str, list[dict]]:
    groups: dict[str, list[dict]] = {}
    for entry in memory["correction_log"]:
        if entry.get("distilled", False):
            continue
        groups.setdefault(entry["corrected_label"], []).append(entry)
 
    return {label: entries for label, entries in groups.items() if len(entries) >= min_per_label}

def get_active_pattern_for_label(memory: dict, label_value: str) -> dict | None:
    return next(
        (p for p in memory["patterns"] if p["label"] == label_value and p.get("active", True)),
        None
    )

def replace_pattern(memory: dict, label: Label, rule_text: str, examples: list[dict], derived_from: list[str]) -> str:
    existing = get_active_pattern_for_label(memory, label.value)
    if existing is not None:
        existing["active"] = False

    pattern_id = f"pat_{len(memory["patterns"]) + 1:02d}"
    now = _now()
    memory["patterns"].append({
        "id": pattern_id,
        "rule": rule_text,
        "label": label.value,
        "examples": examples,
        "derived_from": derived_from,
        "created_at": existing["created_at"] if existing else now,
        "updated_at": now,
        "active": True
    })
    return pattern_id

def mark_correction_distilled(memory: dict, correction_ids: list[str]) -> None:
    ids = set(correction_ids)
    for entry in memory["correction_log"]:
        if entry["id"] in ids:
            entry["distilled"] = True