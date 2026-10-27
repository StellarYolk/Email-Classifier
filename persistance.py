from datetime import datetime
from pathlib import Path

CURSOR_FILE = Path("processed_ids.txt")
REPORT_DIR = Path(".")

def load_processed_ids() -> set[str]:
    if not CURSOR_FILE.exists(): return set()

    with CURSOR_FILE.open("r") as f:
        return {line.strip() for line in f if line.strip()}

def mark_processed(email_id: str) -> None:
    with CURSOR_FILE.open("a") as f:
        f.write(email_id + "\n")
        f.flush()

def start_report() -> Path:
    timestamp = datetime.now().strftime("%Y-%m-%d_%H%M")
    report_path = REPORT_DIR / f"report_{timestamp}.txt"
    report_path.touch()
    return report_path

def append_report_entry(report_path: Path, email: dict, classification, bucket: str, final_label = None) -> None:
    applied_label = final_label if final_label is not None else classification.label
    override_note = ""
    if final_label is not None and final_label != classification.label:
        override_note = f"  (model originally guessed: {classification.label.value}\n)"
    
    
    entry = (
        f"[{bucket.upper()}] {applied_label.value}\n"
        f"  Reason : {classification.reasoning}"
        f"  From : {email["sender"]}\n"
        f"  Subject : {email["subject"]}\n"
        f"  Body : {email["body"]}\n"
        f"{'-' * 50}\n"
    )
    with report_path.open('a') as f:
        f.write(entry)
        f.flush()

def append_held_report_entry(report_path: Path, email: dict, original_classification, decision) -> None:
    if decision == "delete": outcome_line = "DELETED (moved to trash)"
    elif decision == "leave": outcome_line = "LEFT UNLABELED (untouched, inbox)"
    else: outcome_line = f"RELABELED -> {decision.value}"
    
    entry = (
        f"[RESOLVED] {outcome_line}\n"
        f"\tFrom: {email["sender"]}"
        f"\tSubject: {email["subject"]}\n"
        f"\tModel originally guessed: {original_classification.label.value}"
        f"({original_classification.reasoning})\n"
        f"{'-' * 50}\n"
    )
    with report_path.open("a") as f:
        f.write(entry)
        f.flush()
