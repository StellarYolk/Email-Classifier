import json
from datetime import datetime
from pathlib import Path

from schema import Label

MEMORY_FILE = Path("memory.json")
MEMORY_MD_FILE = Path("memory.md")

PROMOTION_THRESHOLD = 2
DEFAULT_MAX_PATTERNS = 15

_EMPTY_MEMORY = {
    "schema_version": 1,
    "sender_rules": {},
    "pending_proposals": {},
    "correction_log": [],
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

def add_pattern(memory: dict, rule_text: str, label: Label, derived_from: list[str]) -> None:
    pattern_id = f"pat_{len(memory["patterns"]) + 1:02d}"
    memory["patterns"].append({
        "id": pattern_id,
        "rule": rule_text,
        "label": label.value,
        "derived_from": derived_from,
        "created_at": _now(),
        "active": True
    })