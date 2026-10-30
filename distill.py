import os
from dotenv import load_dotenv
load_dotenv()

import json
import requests
from pydantic import BaseModel, Field, ValidationError

from schema import Label
from memory import load_memory, save_memory, get_undistilled_groups, get_active_pattern_for_label, replace_pattern, mark_corrections_distilled

DISTILL_URL = os.environ["DISTILL_URL"]
DISTILL_MODEL = os.environ["DISTILL_MODEL"]
OPENROUTER_API_KEY = os.environ["OPENROUTER_API_KEY"]

MAX_RETRIES = 2

LABEL_DEFINITIONS = """
- job_postings: recruiter outreach, job alerts, application status updates
- coding_contests: competitive programming contests (Codeforces, LeetCode, CodeChef, etc.)
- hackathons: hackathon announcements, invitations, or related updates
- food_delivery: order confirmations, delivery updates from food apps (Swiggy, Zomato, etc.)
- newsletter: recurring digest/newsletter content the user is subscribed to
- security: verification codes, sign-in alerts, password reset emails, account security notices
- spam: promotions, meetup invites, marketing unrelated to the above
- delete: content that is clearly junk and not worth even reviewing, but doesn't cleanly fit "spam"
"""

SYSTEM_PROMPT = f"""
You are helping refine the classification rules for a personal email sorter.
You will be shown a label and a set of real corrections where the user told the
system an email actually belonged to that label -- sometimes correcting a wrong
guess, sometimes correcting a sender rule that went stale. You may also be shown
an existing rule derived from earlier evidence; treat it as something to refine
and sharpen, not restate unchanged.
 
Label definitions, for context on how this label differs from the others:
{LABEL_DEFINITIONS}
 
Write ONE short, general rule (a single sentence) that captures what
distinguishes this label in the corrections shown -- specific enough to be
useful, general enough to apply to emails you haven't seen. Then pick the 1-2
clearest, most representative corrections as examples, by their id.
 
Respond with ONLY a JSON object matching this shape, nothing else, no prose,
no code fences:
{{"rule": "<the rule>", "example_ids": ["<id1>", "<id2>"]}}
"""

class DistilledPattern(BaseModel):
    rule: str = Field(..., min_length=1, max_length=300)
    example_ids: list[str] = Field(..., min_length=1, max_length=2)

def _build_user_prompt(label: str, corrections: list[dict], existing_rule: str | None) -> str:
    lines = [f"Label: {label}", ""]
    if existing_rule:
        lines.append(f"Existing rule (refine, don't just restate): {existing_rule}")
        lines.append("")
    lines.append("Corrections:")
    for c in corrections:
        lines.append(
            f'- id={c["id"]} | sender={c["sender"]} | subject="{c["subject"]}" | '
            f'snippet="{c["body_snippet"]}" | was originally labeled {c["original_label"]}'
        )
    return "\n".join(lines)

def _extract_json(raw_content: str) -> dict:
    start = raw_content.index("{")
    end = raw_content.index("}") + 1
    return json.loads(raw_content[start:end])

def _call_distill_model(system_prompt: str, user_prompt: str) -> dict | None:
    headers = {
        "Authorization": f"Bearer {OPENROUTER_API_KEY}",
        "Content-Type": "application/json"
    }
    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_prompt}
    ]

    payload = {
        "model": DISTILL_MODEL,
        "messages": messages,
        "response_format": {
            "type": "json_schema",
            "json_schema": {
                "name": "distilled_pattern",
                "strict": True,
                "schema": DistilledPattern.model_json_schema()
            }
        },
        "temperature": 0
    }

    for attempt in range(MAX_RETRIES + 1):
        response = requests.post(DISTILL_MODEL, headers=headers, json=payload, timeout=120)
        response.raise_for_status()
        raw_content = response.json()["choices"][0]["message"]["content"]
 
        try:
            parsed = _extract_json(raw_content)
            return DistilledPattern.model_validate(parsed).model_dump()
        except (ValueError, ValidationError) as e:
            if attempt == MAX_RETRIES:
                return None
            messages.append({"role": "assistant", "content": raw_content})
            messages.append({
                "role": "user",
                "content": f"That wasn't valid JSON matching the required schema ({e}). "
                           f"Respond with ONLY the JSON object, nothing else."
            })
            payload["messages"] = messages
 
    return None

def distill_label(memory: dict, label_value: str, corrections: list[dict]) -> bool:
    label = Label(label_value)
    existing = get_active_pattern_for_label(memory, label_value)
    existing_rule = existing["rule"] if existing else None
 
    user_prompt = _build_user_prompt(label_value, corrections, existing_rule)
    result = _call_distill_model(SYSTEM_PROMPT, user_prompt)
 
    if result is None:
        print(f"  [{label_value}] distillation failed after retries -- skipping this round.")
        return False
 
    valid_ids = {c["id"] for c in corrections}
    example_ids = [eid for eid in result["example_ids"] if eid in valid_ids]
    if not example_ids:
        example_ids = [c["id"] for c in corrections[:2]]
 
    examples = [
        {"sender": c["sender"], "subject": c["subject"], "snippet": c["body_snippet"]}
        for c in corrections if c["id"] in example_ids
    ]
 
    replace_pattern(memory, label, result["rule"], examples, derived_from=[c["id"] for c in corrections])
    mark_corrections_distilled(memory, [c["id"] for c in corrections])
 
    verb = "updated" if existing else "created"
    print(f"  [{label_value}] pattern {verb}: {result['rule']}")
    return True

def run_distillation() -> None:
    memory = load_memory()
    groups = get_undistilled_groups(memory)
 
    if not groups:
        print("No label has enough new corrections to distill yet.")
        return
 
    print(f"Distilling patterns for {len(groups)} label(s): {', '.join(groups)}")
 
    for label_value, corrections in groups.items():
        distill_label(memory, label_value, corrections)
 
    save_memory(memory)
    print("Done. memory.md updated.")
 
 
if __name__ == "__main__":
    run_distillation()