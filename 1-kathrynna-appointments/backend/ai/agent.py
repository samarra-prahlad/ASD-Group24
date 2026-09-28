import asyncio
import json
import os
import re
from datetime import date as date_cls
from datetime import datetime

import requests

from mcp_client import call_get_appointment, call_rag_answer_question
from service.llm_client import OLLAMA_MODEL, create_chat_completion
from service.prompt_loader import load_prompt


DATABASE_SERVICE_URL = os.getenv(
    "DATABASE_SERVICE_URL",
    "http://appointments-database:6001"
)


PATIENT_INTENTS = [
    "check_availability",
    "list_my_appointments",
    "recommend_specialty",
    "get_appointment_status",
    "general_question",
    "unsupported_action",
]


ADMIN_INTENTS = [
    "find_patient_appointment",
    "next_scheduled_appointment",
    "appointments_today_count",
    "get_appointment_status",
    "general_question",
    "unsupported_action",
]


# Matches "appointment 102", "appointment id 102", "appointment #102",
# "appointment number 102". The lookahead stops "appointment 10:30" or
# "appointment 3pm" from being read as an ID.
APPOINTMENT_ID_PATTERN = re.compile(
    r"appointment\s*(?:id|number|no\.?|#)?\s*#?\s*(\d+)\b(?!\s*(?:am|pm|:))",
    re.IGNORECASE,
)


# "How do I...", "how long is...", "what do I need..." questions are about
# clinic procedure, so they go to the knowledge base. A 0.5B model often
# misreads them as database lookups, so this is a rule rather than an LLM call.
HOWTO_PATTERN = re.compile(
    r"^\s*(how (do|does|can|long|much)|what (do i need|happens|is the policy)|do i need|is there a)\b",
    re.IGNORECASE,
)


# Phrasing that really is a lookup of the patient's own appointments.
LIST_PATTERN = re.compile(
    r"\b(my|upcoming|booked|scheduled)\b.*\bappointments?\b|\bwhen is my\b|\bnext appointment\b",
    re.IGNORECASE,
)


def _extract_appointment_id(message):
    match = APPOINTMENT_ID_PATTERN.search(message)
    return int(match.group(1)) if match else None


def plan(message, context):

    role = context.get("role", "patient")

    # Deterministic routing for the MCP tool: a 0.5B model is unreliable at
    # picking tools, so if the message names an appointment ID we go straight
    # to the MCP-backed intent without asking the LLM.
    appointment_id = _extract_appointment_id(message)

    if appointment_id is not None:
        return {
            "intent": "get_appointment_status",
            "appointment_id": appointment_id,
            "raw_message": message
        }

    # Procedure questions go straight to the knowledge base (RAG).
    if HOWTO_PATTERN.search(message):
        return {
            "intent": "general_question",
            "raw_message": message,
            "specialty": None,
            "date": None,
            "symptom_description": None,
            "patient_identifier": None,
            "appointment_id": None
        }

    if role == "admin":
        system_prompt = load_prompt("admin_system_prompt.txt")
        supported_intents = ADMIN_INTENTS
        default_fields = {
            "patient_identifier": None,
            "date": None,
            "appointment_id": None
        }
    else:
        system_prompt = load_prompt("system_prompt.txt")
        supported_intents = PATIENT_INTENTS
        default_fields = {
            "specialty": None,
            "date": None,
            "symptom_description": None,
            "appointment_id": None
        }

    recent_history = context.get("history", [])[-4:]

    raw = create_chat_completion(
        [
            {
                "role": "system",
                "content": system_prompt
            },
            *recent_history,
            {
                "role": "user",
                "content": message
            },
        ],
        max_tokens=200,
        temperature=0.1,
        model=OLLAMA_MODEL,
    )

    parsed = _try_parse_json(raw)

    if not parsed or parsed.get("intent") not in supported_intents:
        return {
            "intent": "general_question",
            "raw_message": message,
            **default_fields
        }

    # Only trust the model's database intents when the message has what they
    # need; otherwise treat it as a knowledge-base question.
    if parsed.get("intent") == "check_availability" and not (
        parsed.get("specialty") and parsed.get("date")
    ):
        parsed["intent"] = "general_question"

    if parsed.get("intent") == "list_my_appointments" and not LIST_PATTERN.search(message):
        parsed["intent"] = "general_question"

    parsed["raw_message"] = message

    return parsed


def _try_parse_json(raw):
    try:
        return json.loads(raw)

    except (json.JSONDecodeError, TypeError):
        pass

    if not isinstance(raw, str):
        return None

    start = raw.find("{")
    end = raw.rfind("}")

    if start != -1 and end != -1 and end > start:
        try:
            return json.loads(
                raw[start:end + 1]
            )
        except json.JSONDecodeError:
            return None

    return None


def query_availability(specialty, requested_date):

    if not specialty or not requested_date:
        return []

    response = requests.get(
        f"{DATABASE_SERVICE_URL}/availability",
        params={
            "specialty": specialty,
            "date": requested_date
        },
        timeout=5
    )

    response.raise_for_status()

    result = response.json()

    doctors = result.get("doctors", [])

    available_slots = []

    for doctor in doctors:

        availability = doctor.get("availability", "")
        booked_times = set(
            doctor.get("booked_times", [])
        )

        slots = _generate_available_slots(
            availability,
            requested_date
        )

        for slot in slots:

            if slot not in booked_times:
                available_slots.append({
                    "doctor_name": doctor.get("doctor_name"),
                    "specialty": doctor.get("specialty"),
                    "date": requested_date,
                    "time": slot
                })

    return available_slots


def _generate_available_slots(availability, requested_date):
    """
    Convert doctor availability such as:

        Mon-Fri 09:00-17:00

    into 30-minute appointment slots.
    """

    if not availability:
        return []

    try:
        requested = datetime.strptime(
            requested_date,
            "%Y-%m-%d"
        )

        day_name = requested.strftime("%a")

    except ValueError:
        return []

    availability = availability.strip()

    if " " not in availability:
        return []

    day_part, time_part = availability.split(
        " ",
        1
    )

    if "-" not in time_part:
        return []

    start_time, end_time = time_part.split(
        "-",
        1
    )

    if not _day_matches(day_name, day_part):
        return []

    try:
        start = datetime.strptime(
            start_time,
            "%H:%M"
        )

        end = datetime.strptime(
            end_time,
            "%H:%M"
        )

    except ValueError:
        return []

    slots = []

    current_minutes = (
        start.hour * 60 +
        start.minute
    )

    end_minutes = (
        end.hour * 60 +
        end.minute
    )

    while current_minutes < end_minutes:

        hour = current_minutes // 60
        minute = current_minutes % 60

        slots.append(
            f"{hour:02d}:{minute:02d}"
        )

        current_minutes += 30

    return slots


def _day_matches(day_name, availability_days):
    """
    Check whether a date's weekday is included in availability.

    Supports:
        Mon-Fri
        Mon
        Tue
        Sat-Sun
    """

    days = [
        "Mon",
        "Tue",
        "Wed",
        "Thu",
        "Fri",
        "Sat",
        "Sun"
    ]

    availability_days = availability_days.strip()

    if "," in availability_days:
        parts = [
            part.strip()
            for part in availability_days.split(",")
        ]

        return day_name in parts

    if "-" in availability_days:

        start_day, end_day = [
            part.strip()
            for part in availability_days.split("-", 1)
        ]

        if start_day not in days or end_day not in days:
            return False

        start_index = days.index(start_day)
        end_index = days.index(end_day)

        if start_index <= end_index:
            allowed = days[
                start_index:end_index + 1
            ]
        else:
            allowed = (
                days[start_index:] +
                days[:end_index + 1]
            )

        return day_name in allowed

    return day_name == availability_days


def query_patient_appointments(patient_id):
    """
    Get all appointments for a patient.
    """

    if not patient_id:
        return []

    response = requests.get(
        f"{DATABASE_SERVICE_URL}/appointments/patient/{patient_id}",
        timeout=5
    )

    response.raise_for_status()

    appointments = response.json()

    return [
        {
            "patient_id": appointment.get("patient_id"),
            "doctor_name": appointment.get("doctor_name"),
            "specialty": appointment.get("doctor_specialty"),
            "date": appointment.get("date"),
            "time": appointment.get("time"),
            "status": appointment.get("status")
        }
        for appointment in appointments
    ]


def search_appointments_by_patient(identifier):
    """
    Find appointments by patient ID.

    The appointments database currently exposes patient_id,
    not patient names, so this function searches by ID.
    """

    if not identifier:
        return []

    response = requests.get(
        f"{DATABASE_SERVICE_URL}/appointments",
        timeout=5
    )

    response.raise_for_status()

    appointments = response.json()

    identifier = str(identifier).strip().lower()

    results = []

    for appointment in appointments:

        patient_id = str(
            appointment.get("patient_id", "")
        ).strip().lower()

        if patient_id == identifier:

            results.append({
                "patient_id": appointment.get("patient_id"),
                "doctor_name": appointment.get("doctor_name"),
                "specialty": appointment.get("doctor_specialty"),
                "date": appointment.get("date"),
                "time": appointment.get("time"),
                "status": appointment.get("status")
            })

    return results


def query_next_scheduled_appointment():

    response = requests.get(
        f"{DATABASE_SERVICE_URL}/appointments",
        timeout=5
    )

    response.raise_for_status()

    appointments = response.json()

    today = date_cls.today().isoformat()

    upcoming = []

    for appointment in appointments:

        if appointment.get("status") != "scheduled":
            continue

        appointment_date = appointment.get("date")

        if not appointment_date:
            continue

        if appointment_date < today:
            continue

        upcoming.append(appointment)

    if not upcoming:
        return None

    upcoming.sort(
        key=lambda appointment: (
            appointment.get("date", ""),
            appointment.get("time", "")
        )
    )

    appointment = upcoming[0]

    return {
        "patient_id": appointment.get("patient_id"),
        "doctor_name": appointment.get("doctor_name"),
        "specialty": appointment.get("doctor_specialty"),
        "date": appointment.get("date"),
        "time": appointment.get("time"),
        "status": appointment.get("status")
    }


def query_appointments_count_for_date(requested_date):

    response = requests.get(
        f"{DATABASE_SERVICE_URL}/appointments/date/{requested_date}",
        timeout=5
    )

    response.raise_for_status()

    appointments = response.json()

    return len(appointments)


def act(plan_result, context):

    intent = plan_result["intent"]

    try:

        if intent == "check_availability":

            data = query_availability(
                plan_result.get("specialty"),
                plan_result.get("date")
            )

            return {
                "success": True,
                "data": data,
                "error": None,
                "intent": intent
            }

        if intent == "list_my_appointments":

            patient_id = context.get("patient_id")

            if not patient_id:
                return {
                    "success": False,
                    "data": None,
                    "error": "missing_patient_id",
                    "intent": intent
                }

            data = query_patient_appointments(
                patient_id
            )

            return {
                "success": True,
                "data": data,
                "error": None,
                "intent": intent
            }

        if intent == "recommend_specialty":

            reply = _llm_reply(
                "recommend_specialty_system_prompt.txt",
                plan_result["raw_message"]
            )

            return {
                "success": True,
                "data": reply,
                "error": None,
                "intent": intent
            }

        if intent == "get_appointment_status":

            role = context.get("role", "patient")
            appointment_id = plan_result.get("appointment_id")

            if not appointment_id:
                return {
                    "success": False,
                    "data": None,
                    "error": "missing_appointment_id",
                    "intent": intent
                }

            if role == "patient" and not context.get("patient_id"):
                return {
                    "success": False,
                    "data": None,
                    "error": "missing_patient_id",
                    "intent": intent
                }

            # The actual MCP call: this backend acting as an MCP client.
            result = asyncio.run(
                call_get_appointment(int(appointment_id))
            )

            if result.get("error") == "Appointment not found":
                result = None

            elif "error" in result:
                return {
                    "success": False,
                    "data": None,
                    "error": f"mcp_call_failed: {result['error']}",
                    "intent": intent
                }

            elif (
                role == "patient"
                and str(result.get("patient_id"))
                != str(context.get("patient_id"))
            ):
                # Patients may only view their own appointments. A wrong-owner
                # lookup looks identical to "not found" so it doesn't reveal
                # that the appointment exists.
                result = None

            return {
                "success": True,
                "data": result,
                "error": None,
                "intent": intent
            }

        if intent == "find_patient_appointment":

            identifier = plan_result.get(
                "patient_identifier"
            )

            if not identifier:
                return {
                    "success": False,
                    "data": None,
                    "error": "missing_patient_identifier",
                    "intent": intent
                }

            data = search_appointments_by_patient(
                identifier
            )

            return {
                "success": True,
                "data": data,
                "error": None,
                "intent": intent
            }

        if intent == "next_scheduled_appointment":

            data = query_next_scheduled_appointment()

            return {
                "success": True,
                "data": data,
                "error": None,
                "intent": intent
            }

        if intent == "appointments_today_count":

            target_date = (
                plan_result.get("date")
                or date_cls.today().isoformat()
            )

            count = query_appointments_count_for_date(
                target_date
            )

            return {
                "success": True,
                "data": {
                    "date": target_date,
                    "count": count
                },
                "error": None,
                "intent": intent
            }


        if intent == "unsupported_action":

            role = context.get(
                "role",
                "patient"
            )

            if role == "admin":

                msg = (
                    "I can't book, cancel, or edit appointments "
                    "through chat yet. Please use the admin dashboard "
                    "directly for that."
                )

            else:

                msg = (
                    "I can't book, cancel, or change appointments "
                    "through chat yet. Please use the booking form "
                    "or the My Appointments page for that."
                )

            return {
                "success": True,
                "data": msg,
                "error": None,
                "intent": intent
            }

        # general_question: knowledge base (RAG) first, plain LLM as fallback
        rag = call_rag_answer_question(plan_result["raw_message"])

        if rag is not None:

            return {
                "success": True,
                "data": rag.get("answer", ""),
                "error": None,
                "intent": intent,
                "rag": {
                    "confidence": rag.get("confidence_category"),
                    "citations": rag.get("citations", [])
                }
            }

        reply = _llm_reply(
            "general_question_system_prompt.txt",
            plan_result["raw_message"]
        )

        return {
            "success": True,
            "data": reply,
            "error": None,
            "intent": intent
        }

    except requests.RequestException as exc:

        return {
            "success": False,
            "data": None,
            "error": f"database_request_failed: {exc}",
            "intent": intent
        }

    except Exception as exc:

        return {
            "success": False,
            "data": None,
            "error": f"unexpected_error: {exc}",
            "intent": intent
        }


def _llm_reply(prompt_file, user_message, history=None):
    system_prompt = load_prompt(prompt_file)

    messages = [{"role": "system", "content": system_prompt}]
    messages.extend((history or [])[-4:]) 
    messages.append({"role": "user", "content": user_message})

    reply = create_chat_completion(
        messages,
        max_tokens=200,
        temperature=0.3,
        model=OLLAMA_MODEL,
    )
    return reply.strip()


LIST_RESULT_INTENTS = (
    "check_availability",
    "list_my_appointments",
    "find_patient_appointment"
)


SINGLE_RESULT_INTENTS = (
    "next_scheduled_appointment",
    "get_appointment_status",
)


def observe(action_result):

    flags = []

    if not action_result["success"]:

        error = action_result.get("error")

        if error == "missing_patient_id":

            flags.append(
                "missing_patient_id"
            )

        elif error == "missing_patient_identifier":

            flags.append(
                "missing_patient_identifier"
            )

        elif error == "missing_appointment_id":

            flags.append(
                "missing_appointment_id"
            )

        else:

            flags.append(
                "action_failed"
            )

    data = action_result.get("data")
    intent = action_result.get("intent")

    if action_result["success"]:

        if (
            intent in LIST_RESULT_INTENTS
            and (data is None or len(data) == 0)
        ):

            flags.append(
                "no_results"
            )

        elif (
            intent in SINGLE_RESULT_INTENTS
            and data is None
        ):

            flags.append(
                "no_results"
            )

    return {
        "flags": flags,
        "needs_adaptation": len(flags) > 0
    }

def adapt(
    plan_result,
    action_result,
    observation
):

    flags = observation["flags"]
    intent = action_result["intent"]

    if "missing_patient_id" in flags:

        return (
            "I'll need your patient ID to look that up. "
            "Please enter it above and ask me again."
        )

    if "missing_patient_identifier" in flags:

        return (
            "Please tell me the patient's patient ID "
            "so I can look up their appointment."
        )

    if "missing_appointment_id" in flags:

        return (
            "Please tell me the appointment ID, for example: "
            "status of appointment 102."
        )

    if "action_failed" in flags:

        return (
            "Sorry, I couldn't complete that just now. "
            "Please try again or check the dashboard/"
            "booking form directly."
        )

    if "no_results" in flags:

        if intent == "check_availability":

            specialty = (
                plan_result.get("specialty")
                or "that specialty"
            )

            requested_date = (
                plan_result.get("date")
                or "that date"
            )

            return (
                f"I couldn't find any open slots for "
                f"{specialty} on {requested_date}. "
                "Try a different date or check the full "
                "calendar on the booking form."
            )

        if intent == "list_my_appointments":

            return (
                "You don't have any upcoming appointments "
                "booked right now."
            )

        if intent == "find_patient_appointment":

            identifier = (
                plan_result.get(
                    "patient_identifier"
                )
                or "that patient"
            )

            return (
                f"I couldn't find any appointments "
                f"for patient {identifier}."
            )

        if intent == "next_scheduled_appointment":

            return (
                "There's no upcoming appointment "
                "scheduled right now."
            )

        if intent == "get_appointment_status":

            return (
                "I couldn't find an appointment with that ID "
                "for your account."
            )

    data = action_result.get("data")

    if intent == "check_availability":

        lines = [
            (
                f"- {slot['doctor_name']} — "
                f"{slot['date']} at {slot['time']}"
            )
            for slot in data
        ]

        return (
            "Here's what's available:\n"
            + "\n".join(lines)
        )

    if intent == "list_my_appointments":

        lines = [
            (
                f"- {appointment['doctor_name']} "
                f"({appointment['specialty']}) — "
                f"{appointment['date']} at "
                f"{appointment['time']}"
            )
            for appointment in data
        ]

        return (
            "Your upcoming appointments:\n"
            + "\n".join(lines)
        )

    if intent == "find_patient_appointment":

        lines = [
            (
                f"- Patient {appointment['patient_id']} "
                f"with {appointment['doctor_name']} "
                f"({appointment['specialty']}) — "
                f"{appointment['date']} at "
                f"{appointment['time']}"
            )
            for appointment in data
        ]

        return (
            "Found the following appointment(s):\n"
            + "\n".join(lines)
        )

    if intent == "next_scheduled_appointment":

        appointment = data

        return (
            f"The next scheduled appointment is "
            f"for patient {appointment['patient_id']} "
            f"with {appointment['doctor_name']} "
            f"on {appointment['date']} "
            f"at {appointment['time']}."
        )

    if intent == "get_appointment_status":

        return (
            f"Appointment #{data['id']}: {data['doctor_name']} "
            f"({data['doctor_specialty']}) on {data['date']} "
            f"at {data['time']}. Status: {data['status']}."
        )

    if intent == "appointments_today_count":

        return (
            f"There are {data['count']} appointment(s) "
            f"scheduled for {data['date']}."
        )

    if intent == "general_question":

        rag = action_result.get("rag")

        if rag and str(rag.get("confidence") or "").lower() == "insufficient":

            return (
                "I don't have enough information in the knowledge base "
                "to answer that confidently."
            )

    return data


# ---------- Confidence + sources ----------

# Intents answered by free-text LLM output with nothing verifiable behind them.
LLM_ONLY_INTENTS = (
    "general_question",
    "recommend_specialty",
)


INTENT_SOURCES = {
    "get_appointment_status": ["MCP: appointments_get_appointment"],
    "check_availability": ["appointments database"],
    "list_my_appointments": ["appointments database"],
    "find_patient_appointment": ["appointments database"],
    "next_scheduled_appointment": ["appointments database"],
    "appointments_today_count": ["appointments database"],
}


def score_confidence(action_result, observation):
    """
    HIGH / MEDIUM / LOW / INSUFFICIENT.
    Knowledge-base answers use the RAG server's own category; database and
    MCP answers are HIGH (straight from the source); free LLM text is LOW.
    """

    flags = observation["flags"]
    intent = action_result["intent"]

    if "action_failed" in flags or any(
        flag.startswith("missing_") for flag in flags
    ):
        return "INSUFFICIENT"

    if intent == "unsupported_action":
        return "HIGH"

    rag = action_result.get("rag")

    if rag:
        return str(rag.get("confidence") or "LOW").upper()

    if intent in LLM_ONLY_INTENTS:
        return "LOW"

    if "no_results" in flags:
        return "MEDIUM"

    return "HIGH"


def _sources_for(action_result):

    if not action_result["success"]:
        return []

    rag = action_result.get("rag")

    if rag:

        # nothing to cite when the answer is "not enough information"
        if str(rag.get("confidence") or "").lower() == "insufficient":
            return []

        seen = []

        for citation in rag.get("citations", []):
            source = (
                str(citation.get("source_id", citation))
                if isinstance(citation, dict)
                else str(citation)
            )
            if source not in seen:
                seen.append(source)

        return seen

    return INTENT_SOURCES.get(action_result["intent"], [])


def run(
    message,
    patient_id=None,
    history=None,
    role="patient"
):

    context = {
        "patient_id": patient_id,
        "history": history or [],
        "role": role
    }

    plan_result = plan(
        message,
        context
    )

    action_result = act(
        plan_result,
        context
    )

    observation = observe(
        action_result
    )

    reply = adapt(
        plan_result,
        action_result,
        observation
    )

    return {
        "reply": reply,
        "confidence": score_confidence(action_result, observation),
        "sources": _sources_for(action_result),
        "trace": {
            "plan": plan_result,
            "action": action_result,
            "observation": observation
        }
    }