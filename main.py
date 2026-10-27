from classify import classify_email
from schema import AUTO_SORTED_LABELS, AUTO_ARCHIVED_LABELS, HELD_LABELS, Label
from persistance import mark_processed, load_processed_ids, start_report, append_report_entry, append_held_report_entry
from gmail_client import get_service, fetch_unread_ids, fetch_full_message, parse_message
from gmail_actions import LabelManager, apply_outcome
from memory import load_memory, save_memory, log_correction

BATCH_SIZE = 20

def chunk(items: list, size: int) -> list[list]:
    return [items[i:i + size] for i in range(0, len(items), size)]

def route(classification, email) -> str:
    label = classification.label
    if label in AUTO_SORTED_LABELS: return "sorted"
    elif label in AUTO_ARCHIVED_LABELS: return "archived"
    elif label in HELD_LABELS: return "held"
    else:
        raise ValueError(f"label {label} is not as signed to any bucket")

def _bucket_for_label(label: Label) -> str:
    if label == Label.DELETE: return "deleted"
    elif label in AUTO_SORTED_LABELS: return "sorted"
    elif label in AUTO_ARCHIVED_LABELS: return "archived"
    else:
        raise ValueError(f"label {label} has no apply-time bucket")

def _build_relabel_menu(include_delete: bool) -> list[Label]:
    options = sorted(AUTO_SORTED_LABELS, key=lambda l: l.value)
    options += sorted(AUTO_ARCHIVED_LABELS, key=lambda l: l.value)
    if include_delete: options.append(Label.DELETE)

    return options

def _prompt_choice(options: list[Label]) -> str:
    display = [l.value for l in options] + ['leave']
    for i, name in enumerate(display, start=1):
        print(f"\t{i}, {name}")

    while True:
        choice = input("Choose a number: ").strip()
        if choice.isdigit() and 1 <= int(choice) <= len(display):
            return display[int(choice) -1]
        print(f"Invalid choice -- enter a number from 1 to {len(display)}")

def process_held_emails(held_emails: list[dict], report_path, memory, processed_ids, service = None, label_manager = None ) -> list[dict]:
    resolved = []

    if not held_emails: return resolved

    print(f"\n--- {len(held_emails)} held email(s) need your review ---")

    for item in held_emails:
        email = item["email"]
        original = item["classification"]

        print(f"\nFrom: {email["sender"]}")
        print(f"Subject: {email['subject']}")
        print(f"Body: \n{email['body']}")
        print(f"===> Model originality guessed: {original.label.value} ({original.reasoning})")

        if original.label == Label.DELETE:
            confirm = input("Model suggests DELETE. Confirm? [y/n] ").strip().lower()
            if confirm == "y": 
                decision = "delete"
            else:
                options = _build_relabel_menu(include_delete=False)
                choice = _prompt_choice(options)
                decision = "leave" if choice == "leave" else Label(choice)
        else:
            options = _build_relabel_menu(include_delete=True)
            choice = _prompt_choice(options)
            if choice == "leave": decision = "leave"
            elif choice == "delete": decision = "delete"
            else: decision = Label(choice)

        bucket = {"delete": "delete", "leave": "left"}.get(decision, "relabeled")
        final_label = decision if isinstance(decision, Label)  else None

        corrected_label = Label.DELETE if decision == "delete" else final_label
        if corrected_label is not None and corrected_label != original.label:
            log_correction(memory, email, original.label, corrected_label, source="held_review")


        if service is not None:
            apply_outcome(service, label_manager, email, bucket, final_label)

        mark_processed(email["id"])
        processed_ids.add(email["id"])
        append_held_report_entry(report_path, email, original, decision)

        resolved.append({
            "email": email,
            "classification": original,
            "bucket": bucket,
            "final_decision": decision
        })

    return resolved

def process_batch(emails: list[dict], processed_ids: set[str], report_path, memory, service = None, label_manager = None) -> tuple[list[dict], dict]:
    # results = []
    held_emails = []
    pending_items = []
    counts = {"sorted": 0, "archived": 0, "held": 0}

    for email in emails:
        if email["id"] in processed_ids:
            print(f"Already processed {email["id"]}, Skipping")
            continue

        classification = classify_email(
            sender=email["sender"],
            subject=email["subject"],
            body=email["body"]
        )

        bucket = route(classification, email)
        counts[bucket] += 1
        item = {"email": email, "classification": classification, "bucket": bucket}

        if bucket == "held":
            held_emails.append(item)
        else: 
            pending_items.append(item)
            # if service is not None:
            #     apply_outcome(service, label_manager, email, bucket, classification.label)
            
            # mark_processed(email["id"])
            # append_report_entry(report_path, email, classification, bucket)
            # processed_ids.add(email["id"])
            # results.append(item)

    resolved = process_held_emails(held_emails, report_path, memory, processed_ids, service, label_manager)
    # results.extend(resolved)

    return resolved, pending_items, counts

def review_and_flag(pending_items: list[dict], memory) -> None:
    if not pending_items: return

    print(f"\n--- {len(pending_items)} email(s) classified this batch (not yet applied) ---")
    for i, item in enumerate(pending_items, start=1):
        email = item["email"]
        print(f"    {i}. [{item["bucket"].upper()}] {item["classification"].label.value} -- {email["sender"]} -- {email["subject"]}")

    raw = input("\n Flag any to correct before applying? Numbers comma-separated, or Enter to skip;  ").strip()
    if not raw: return

    try:
        indices = {int(x.strip()) for x in raw.split(",") if x.strip()}
    except ValueError:
        print("Couldn't parse that input -- skipping flagging\n")

    for i in indices:
        if not (1 <= i <= len(pending_items)):
            print(f"skipping invalid index {i}")
            return

        item = pending_items[i-1]
        email = item["email"]
        original = item["classification"]

        print(f"\nFrom: {email["sender"]}")
        print(f"\nsubject: {email["subject"]}")
        print(f"\nModel guessed: {original.label.value} ({original.reasoning})")

        options = _build_relabel_menu(include_delete=True)
        choice = _prompt_choice(options)

        if choice == "leave":
            continue

        new_label = Label(choice)
        if new_label == original.label:
            continue

        item["final_bucket"] = new_label
        item["bucket"] = _bucket_for_label(new_label)

        log_correction(memory, email, original.label, new_label, source="flagged_after_apply")

def finalize_batch(pending_items: list[dict], report_path, processed_ids, service = None, label_manager = None) -> None:
    for item in pending_items:
        email = item["email"]
        classification = item["classification"]
        bucket = item["bucket"]
        final_label = item["final_label"]

        if service is not None:
            apply_outcome(service, label_manager, email, bucket, final_label)

        mark_processed(email["id"])
        append_report_entry(report_path, email, classification, bucket, final_label)
        processed_ids.add(email["id"])

def run(all_emails: list[dict]) -> list[dict]:
    batches = chunk(all_emails, BATCH_SIZE)
    all_results = []

    processed_ids = load_processed_ids()
    report_path = start_report()
    memory = load_memory()
    print(f"Report: {report_path}")
    print(f"Already processed (will skip): {len(processed_ids)} emails")

    for batch_num, batch in enumerate(batches, start=1):
        print(f"\n--- Batch {batch_num}/{len(batches)} || {len(batch)} emails ---")

        resolved, pending_items, counts = process_batch(batch, processed_ids, report_path, memory)
        all_results.extend(resolved)

        review_and_flag(pending_items, memory)

        print(f"sorted: {counts["sorted"]}\t Archived: {counts["archived"]}\t Held: {counts["held"]}\n")

        is_last_batch = batch_num == len(batch)
        answer = "n"
        if not is_last_batch:
            answer = input(f"Continue to batch {batch_num + 1}? [y/n]: ").strip().lower()

        print("applying this batch's labels...")
        finalize_batch(pending_items, report_path, processed_ids)
        all_results.extend(pending_items)
        save_memory(memory)

        if not is_last_batch and answer != "y":
            print("Stopped by user\n")
            break

    return all_results

def run_from_gmail() -> list[dict]:
    service= get_service()
    label_manager = LabelManager(service)

    processed_ids = load_processed_ids()
    report_path = start_report()
    memory = load_memory()
    print(f"Report: {report_path}")
    print(f"Already processed : {len(processed_ids)} email(s)")

    all_results = []
    page_token = None
    batch_num = 0

    while True:
        batch_num += 1
        message_ids, page_token = fetch_unread_ids(service, BATCH_SIZE, page_token)

        if not message_ids:
            print("no more unread emails")
            break

        print(f"\n--- Batch {batch_num} ({len(message_ids)}) emails ---")

        batch_emails = [parse_message(fetch_full_message(service, mId)) for mId in message_ids]
        resolved, pending_items, counts = process_batch(batch_emails, processed_ids, report_path, memory, service, label_manager)
        all_results.extend(resolved)

        review_and_flag(pending_items, memory)

        print(f"Sorted : {counts["sorted"]}\tArchived : {counts["archived"]}\tHeld : {counts["held"]}\n")

        has_more = page_token is not None
        answer = "n"
        if has_more:
            answer = input("Continue to next batch? (y/n) ").strip().lower()

        print("Applying this batch's labels...")
        finalize_batch(pending_items, report_path, processed_ids, service, label_manager)
        all_results.extend(pending_items)
        save_memory()

        if not has_more:
            print("no more unread emails")
            break

        if answer != "y":
            print("Stopped by user")
            break

    return all_results

if __name__ == "__main__":
    # fake_emails = [
    #     {
    #         "id": f"fake-{i}",
    #         "sender": f"sender{i}@example.com",
    #         "subject": f"Test Email {i}",
    #         "body": "Generic test content, please put some effort"
    #     }
    #     for i in range(1, 26)
    # ]
    # run(fake_emails)
    run_from_gmail()