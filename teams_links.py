import subprocess
from config import TEAMS_PATH, TEAMS_TENANT_ID

TENANT_ID = TEAMS_TENANT_ID

SUBJECTS = [
    {
        "name": "Іноземна мова",
        "keywords": ["іноземна", "іноземна мова", "комунікативні"],
        "groupId": "0683a3fe-9cc4-4dfd-a50a-df45ad1d7a76",
        "threadId": "19%3A-4Fam3gar2Zs_B_5cZoFzl-E72uXLovVeiN6eqnz8hY1%40thread.tacv2",
    },
    {
        "name": "Веб-програмування",
        "keywords": ["веб", "програмування"],
        "groupId": "592a8e0b-6fd6-4ef1-9543-50ca07a5dabb",
        "threadId": "19%3A6aYqSbMlIXpgeJ67eECwvySOuH-4dhflZRrpaHO16JI1%40thread.tacv2",
    },
    {
        "name": "Теорія прийняття рішень",
        "keywords": ["теорія", "прийняття рішень"],
        "groupId": "01b1ab6d-deb3-47c8-a451-c7a94f354145",
        "threadId": "19%3AZ_-3wf4Zp1y1VHvzSRd0LhYIzQ67imk8dTS-PMSnv9g1%40thread.tacv2",
    },
    {
        "name": "Організація баз даних знань",
        "keywords": ["організація", "бази даних", "знань"],
        "groupId": "0147a626-44b9-478b-9c6a-582fae4af138",
        "threadId": "19%3Aj6wV1JWYF3v9Zm1KjLYi9PUJBJJRbqcnkgg7Bt2xkE41%40thread.tacv2",
    },
    {
        "name": "Інтелектуальний аналіз даних",
        "keywords": ["інтелектуальний", "аналіз даних"],
        "groupId": "c33c2be0-2c37-4135-9beb-7552b4d53100",
        "threadId": "19%3AXH5g-DmYSlTgmsXHid5lVDmvjJ8oMzJUY_Okac3cgcw1%40thread.tacv2",
    },
]


def find_teams_link(event_name):
    """Return (subject_name, teams_url) for the matched subject, or (None, None)."""
    name_lower = event_name.lower()
    for subject in SUBJECTS:
        if any(kw in name_lower for kw in subject["keywords"]):
            url = (
                f"https://teams.microsoft.com/l/team/{subject['threadId']}/conversations"
                f"?groupId={subject['groupId']}&tenantId={TENANT_ID}"
            )
            return subject["name"], url
    return None, None


def open_teams_for_subject(event_name):
    """
    Open the Teams channel matching event_name using the Teams desktop app.
    Returns the matched subject name for Jarvis to speak, or None if not found.
    """
    name_lower = event_name.lower()
    for subject in SUBJECTS:
        if any(kw in name_lower for kw in subject["keywords"]):
            group_id = subject["groupId"]
            thread_id = subject["threadId"]
            url = (
                f"https://teams.microsoft.com/l/team/{thread_id}/conversations"
                f"?groupId={group_id}&tenantId={TENANT_ID}"
            )
            subprocess.Popen([TEAMS_PATH, url])
            return subject["name"]
    return None
