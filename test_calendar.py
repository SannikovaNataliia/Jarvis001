from calendar_helper import get_todays_university_events, find_current_or_next_event

print("=== Today's University Events ===")
events = get_todays_university_events()
if not events:
    print("No events found.")
else:
    for e in events:
        start = e["start"].get("dateTime", e["start"].get("date"))
        end = e["end"].get("dateTime", e["end"].get("date"))
        print(f"  {start} → {end}  |  {e.get('summary', '(no title)')}")

print()
print("=== Current / Next Event ===")
event = find_current_or_next_event()
if not event:
    print("No events today.")
else:
    start = event["start"].get("dateTime", event["start"].get("date"))
    end = event["end"].get("dateTime", event["end"].get("date"))
    print(f"  {start} → {end}  |  {event.get('summary', '(no title)')}")
