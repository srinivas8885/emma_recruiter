import os, json
from datetime import datetime, timedelta
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
import pytz

SCOPES = ['https://www.googleapis.com/auth/calendar']

def authenticate_google_calendar():
    creds = None
    if os.path.exists("token.json"):
        creds = Credentials.from_authorized_user_file("token.json", SCOPES)
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file("emma_client_secret.json", SCOPES)
            creds = flow.run_local_server(port=0)
        with open("token.json", "w") as token:
            token.write(creds.to_json())
    return build("calendar", "v3", credentials=creds)

def get_calendar_events(service, start_date, end_date):
    ist = pytz.timezone("Asia/Kolkata")
    utc = pytz.UTC

    # Ensure datetime inputs are timezone-aware
    if start_date.tzinfo is None:
        start_date = ist.localize(start_date)
    if end_date.tzinfo is None:
        end_date = ist.localize(end_date)

    # Convert to UTC for Google Calendar API
    start_date_utc = start_date.astimezone(utc)
    end_date_utc = end_date.astimezone(utc)

    events_result = service.events().list(
        calendarId="primary",
        timeMin=start_date_utc.isoformat(),
        timeMax=end_date_utc.isoformat(),
        singleEvents=True,
        orderBy="startTime",
    ).execute()

    return events_result.get("items", [])

def find_available_slots(events, start_date, end_date):
    ist = pytz.timezone("Asia/Kolkata")
    if start_date.tzinfo is None:
        start_date = ist.localize(start_date)
    if end_date.tzinfo is None:
        end_date = ist.localize(end_date)

    available_slots = []
    current_date = start_date

    while current_date <= end_date:
        if current_date.weekday() < 5:  # Monday to Friday
            working_hours = [
                (current_date.replace(hour=9, minute=0), current_date.replace(hour=13, minute=0)),
                (current_date.replace(hour=14, minute=0), current_date.replace(hour=17, minute=0)),
            ]

            for start, end in working_hours:
                slot_start = start
                while slot_start < end:
                    slot_end = slot_start + timedelta(hours=1)

                    if not any(
                        slot_start < datetime.fromisoformat(
                            e["end"].get("dateTime", e["end"].get("date")).replace("Z", "+00:00")
                        ) and
                        slot_end > datetime.fromisoformat(
                            e["start"].get("dateTime", e["start"].get("date")).replace("Z", "+00:00")
                        )
                        for e in events
                    ):
                        available_slots.append((slot_start, slot_end))

                    slot_start = slot_end

        current_date += timedelta(days=1)

    return available_slots

def match_candidates_to_recruiters(candidates, recruiters):
    matches = []
    unmatched_candidates = []

    for candidate in candidates:
        # Convert candidate's skills to lowercase
        candidate_skills = {skill.lower() for skill in candidate['skillset']}
        matched = False

        for recruiter in recruiters:
            # Convert recruiter's skills to lowercase
            recruiter_skills = {skill.lower() for skill in recruiter['skillset']}

            # Check if candidate's skills are a subset of the recruiter's skills
            if candidate_skills.issubset(recruiter_skills):
                matches.append((candidate, recruiter))
                matched = True
                break

        if not matched:
            unmatched_candidates.append(candidate)

    return matches, unmatched_candidates
    
def schedule_interview(service, candidate, recruiter, slot_start, slot_end):
    # Ensure slot_start and slot_end are localized to IST
    ist = pytz.timezone("Asia/Kolkata")
    slot_start_ist = slot_start.astimezone(ist)
    slot_end_ist = slot_end.astimezone(ist)

    event = {
        'summary': 'Interview with {}'.format(candidate['name']),
        'description': 'Interview between {} and {}'.format(candidate['name'], recruiter['name']),
        'start': {
            'dateTime': slot_start_ist.isoformat(),
            'timeZone': 'Asia/Kolkata',
        },
        'end': {
            'dateTime': slot_end_ist.isoformat(),
            'timeZone': 'Asia/Kolkata',
        },
        'attendees': [
            {'email': candidate['email']}
        ],
        'conferenceData': {
            'createRequest': {
                'requestId': '123456789',  # Unique identifier
                'conferenceSolutionKey': {'type': 'hangoutsMeet'},
            }
        },
        'sendUpdates': 'all',  
    }
    try:
        scheduled_event = service.events().insert(
            calendarId='primary',
            body=event,
            conferenceDataVersion=1
        ).execute()
        
        print(f"Scheduled event: {scheduled_event['summary']}")  # Log successful event creation
        print(candidate['email'], candidate['name'], slot_start_ist, slot_end_ist, scheduled_event.get('hangoutLink'))
        return scheduled_event
    except Exception as e:
        print(f"Error scheduling event: {e}")  # Log errors
        raise e
