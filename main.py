from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from datetime import datetime, timedelta
import pytz
from app.services import (
    authenticate_google_calendar,
    get_calendar_events,
    find_available_slots,
    match_candidates_to_recruiters,
    schedule_interview,
)
from app.models import db,candidates_collection,recruiters_collection, scheduled_interviews_collection

app = FastAPI()

class InterviewRequest(BaseModel):
    candidate_name: str
    skillset: list
    email: str
    date: str  # YYYY-MM-DD format

@app.post("/schedule_interview")
async def schedule_interview_api(request: InterviewRequest):
    try:
        service = authenticate_google_calendar()

        # Define timezone-aware datetime ranges
        ist = pytz.timezone("Asia/Kolkata")
        start_date = ist.localize(datetime(2025, 1, 20, 0, 0, 0))
        end_date = start_date + timedelta(weeks=1)

        # Fetch events
        events = get_calendar_events(service, start_date, end_date)

        # Find available slots
        available_slots = find_available_slots(events, start_date, end_date)
        print(len(available_slots))
        for slot in available_slots:
            print(f"Available slot: {slot[0]} to {slot[1]}")

        # Get all recruiters
        recruiters = list(recruiters_collection.find())
        candidate = {"name": request.candidate_name, "skillset": request.skillset, "email": request.email}

        print("candidate",candidate)

        # Match candidate to recruiters
        matches, _ = match_candidates_to_recruiters([candidate], recruiters)
        print("matched ",matches,_)
        if not matches:
            raise HTTPException(status_code=404, detail="No matching recruiter found for the candidate's skillset.")

        candidate, recruiter = matches[0]

        if not available_slots:
            raise HTTPException(status_code=404, detail="No available slots for the specified date.")

        # Schedule interview
        slot_start, slot_end = available_slots.pop(0)
        scheduled_event = schedule_interview(service, candidate, recruiter, slot_start, slot_end)

        # Save the scheduled interview in MongoDB
        scheduled_interviews_collection.insert_one({
            "candidate_name": candidate["name"],
            "recruiter_name": recruiter["name"],
            "start_time": slot_start,
            "end_time": slot_end,
            "meeting_link": scheduled_event["hangoutLink"],
            "event_id": scheduled_event["id"],
        })

        return {
            "message": f"Interview scheduled between {candidate['name']} and {recruiter['name']}.",
            "meeting_link": scheduled_event["hangoutLink"],
            "start_time": slot_start,
            "end_time": slot_end,
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
