#!/usr/bin/env python3
"""Send book club reminder email when a GMA book club event is coming up."""

import html
import json
import re
import smtplib
import sys
from datetime import date, timedelta
from email.mime.text import MIMEText
from pathlib import Path

# Reuse GCal auth from the scheduling project
DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(DIR.parent / "dada_science" / "scheduling"))
import gcal

SCHEDULING_CONFIG = DIR.parent / "dada_science" / "scheduling" / "config.json"

SENDER = "vitruviansandwich@gmail.com"
RECIPIENTS = [
    "vitruviansandwich@gmail.com",
    "madeleinejbergeron@gmail.com",
    "heli.anderson@gmail.com",
    "gaildbergeron@gmail.com",
    "janlchidester@gmail.com"
]
EVENT_KEYWORD = "gma book club"


def find_bookclub_event():
    config = json.loads(SCHEDULING_CONFIG.read_text())
    today = date.today()
    dates = [today + timedelta(days=i) for i in range(1, 5)]
    keyword_compact = EVENT_KEYWORD.replace(" ", "")
    for ev in gcal.pull_gcal_events(dates, config):
        title_compact = ev["title"].lower().replace(" ", "")
        if keyword_compact in title_compact:
            return ev
    return None


def parse_reading_list():
    text = (DIR / "reading_list.md").read_text()
    upcoming, past, section = [], [], None
    for line in text.splitlines():
        stripped = line.strip()
        if stripped == "# Upcoming":
            section = "upcoming"
        elif stripped == "# Past":
            section = "past"
        elif line.startswith("- ") and section:
            entry = line[2:].strip()
            (upcoming if section == "upcoming" else past).append(entry)
    return upcoming, past


def save_reading_list(upcoming, past):
    lines = ["# Upcoming"]
    lines += [f"- {b}" for b in upcoming]
    lines += ["", "# Past"]
    lines += [f"- {b}" for b in past]
    lines.append("")
    (DIR / "reading_list.md").write_text("\n".join(lines))


def _text_to_html(text: str) -> str:
    """Convert plain text to HTML, preserving paragraph and line breaks."""
    escaped = html.escape(text)
    paragraphs = escaped.split("\n\n")
    return "".join(f"<p>{p.replace(chr(10), '<br>')}</p>" for p in paragraphs)


def _format_book_entry(entry: str) -> str:
    """Render 'Name -- Title by Author' with italicized title."""
    if " -- " in entry and " by " in entry:
        name, rest = entry.split(" -- ", 1)
        by_idx = rest.find(" by ")
        if by_idx != -1:
            title = rest[:by_idx]
            author = rest[by_idx + 4:]
            return (
                f"{html.escape(name)} &ndash; "
                f"<em>{html.escape(title)}</em> by {html.escape(author)}"
            )
    return html.escape(entry)


def compose_body(event_date: date, upcoming: list) -> str:
    formatted = event_date.strftime("%A, %B %-d")
    greeting = (DIR / "greeting.md").read_text().strip()
    greeting = greeting.replace("{{DATE}}", formatted)

    book_items = "".join(
        f"<li>{_format_book_entry(b)}</li>"
        for b in upcoming
    )
    link = (DIR / "link.md").read_text().strip()

    return (
        f"{_text_to_html(greeting)}"
        f"<p>Reading list:</p><ol>{book_items}</ol>"
        f"{_text_to_html(link)}"
    )


def send(body: str, smtp_password: str):
    msg = MIMEText(body, "html")
    msg["Subject"] = "GMA Book Club Reminder"
    msg["From"] = SENDER
    msg["To"] = ", ".join(RECIPIENTS)
    with smtplib.SMTP("smtp.gmail.com", 587) as server:
        server.starttls()
        server.login(SENDER, smtp_password)
        server.sendmail(SENDER, RECIPIENTS, msg.as_string())


def main():
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--date", help="Override meeting date (YYYY-MM-DD) for testing")
    args = parser.parse_args()

    config = json.loads((DIR / "config.json").read_text())
    smtp_password = config["smtp_password"]
    if smtp_password == "YOUR_GMAIL_APP_PASSWORD_HERE":
        print("Set smtp_password in config.json first.")
        sys.exit(1)

    if args.date:
        event_date = date.fromisoformat(args.date)
    else:
        event = find_bookclub_event()
        if event is None:
            print("No GMA book club event in the next 4 days.")
            return
        event_date = date.fromisoformat(event["date"])
    upcoming, past = parse_reading_list()

    if not upcoming:
        print("No upcoming books in reading_list.md.")
        return

    body = compose_body(event_date, upcoming)
    send(body, smtp_password)

    # Mark the book being discussed as past
    marked = f"{upcoming[0]} — Discussed: {event_date.strftime('%B %-d, %Y')}"
    save_reading_list(upcoming[1:], past + [marked])

    print(f"Sent. Marked '{upcoming[0]}' as discussed on {event_date}.")


if __name__ == "__main__":
    main()
