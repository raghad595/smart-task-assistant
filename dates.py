"""
This file main task is to the model recieves a date, time, and words that he understands to prevent hallucinations.
We change date & time to a standard format (ISO 8601) and we also return a boolean value to indicate if the date was shifted from Friday to Saturday.
The model will recieve the returned date and time in the standard format, and the arabic words that represent date & time will also be returned to the model as formatted ISO 8601 string, 
and the boolean value will be used to inform the model if the date was shifted from Friday to Saturday (never assign tasks on Friday, shift to Saturday at the same time).
"""

import re
from datetime import date, datetime, time, timedelta
from zoneinfo import ZoneInfo

# Initialize Riyadh timezone for consistent date/time calculations.
RIYADH_TZ = ZoneInfo("Asia/Riyadh")
# Create a translation table to convert Arabic numerals to English numerals.
ARABIC_DIGITS = str.maketrans("٠١٢٣٤٥٦٧٨٩", "0123456789")
# Define a regex pattern to match Arabic time expressions.
TIME_PATTERN = re.compile(
    r"(?<!\d)(\d{1,2})(?:\s*:\s*(\d{1,2}))?\s*"
    r"(بعد\s+الظهر|صباحًا|صباحا|الصباح|صباح|"
    r"الظهر|العصر|مساءً|مساء|المساء|ليلاً|ليلا|الليل)?"
)

# change unknown arabic words to standard arabic words.
def normalize_arabic(text: str) -> str:
    """Normalize common spelling variations and Arabic numerals."""

    return (
        text.translate(ARABIC_DIGITS)
        .replace("أ", "ا")
        .replace("إ", "ا")
        .replace("آ", "ا")
        .replace("ى", "ي")
        .replace("ـ", "")
        .strip()
    )


def get_target_date(expression: str, today: date) -> date:
    """Resolve the date portion of a supported Arabic expression."""

    # Check day-after-tomorrow BEFORE tomorrow because 'day after tomorrow' contains the word 'tomorrow'.
    # day after tomorrow = 2 days ahead, tomorrow = 1 day ahead, today = 0 days ahead.
    if any(
        phrase in expression
        for phrase in ("بعد بكرة", "بعد بكرا", "بعد غد")
    ):
        return today + timedelta(days=2)

    if any(
        phrase in expression
        for phrase in ("بكرة", "بكرا", "غدا", "غدًا")
    ):
        return today + timedelta(days=1)

    if "اليوم" in expression:
        return today

    # Python weekday numbers is set to match the american-style week. Starts at monday, their weekend is friday and saturday. 
    # We need to map the arabic weekdays to the correct weekday number (saudi & egypt).
    weekdays = [
        ("الاحد", 6),
        ("الاثنين", 0),
        ("الثلاثاء", 1),
        ("الاربعاء", 2),
        ("الخميس", 3),
        ("الجمعة", 4),
        ("السبت", 5),
    ]

    # What happens if the user says next Sunday? We need to find how many days ahead of that weekday.
    for arabic_name, weekday_number in weekdays:
        if arabic_name in expression:
            days_ahead = (weekday_number - today.weekday()) % 7

            # A weekday mentioned without 'today' means its
            # next occurrence, not today if it is that weekday.
            if days_ahead == 0:
                days_ahead = 7

            return today + timedelta(days=days_ahead)

    # No date specified: use today.
    return today


def get_target_time(expression: str) -> time:
    """Resolve a supported Arabic time expression."""

    match = TIME_PATTERN.search(expression)

    if match is None:
        # Assumptions for expressions containing no numeric hour.
        if "العصر" in expression:
            return time(15, 0)

        if "بعد الظهر" in expression:
            return time(15, 0)

        if "الظهر" in expression:
            return time(12, 0)

        # Assignment default when no time is specified.
        return time(9, 0)

    hour = int(match.group(1))
    minute = int(match.group(2) or 0)
    period = match.group(3) or ""

    if not 0 <= minute <= 59:
        raise ValueError("Invalid minute in time expression.")

    morning = ("صباحًا", "صباحا", "الصباح", "صباح")
    afternoon = (
        "بعد الظهر",
        "الظهر",
        "العصر",
        "مساءً",
        "مساء",
        "المساء",
        "ليلاً",
        "ليلا",
        "الليل",
    )

    if period in morning:
        if not 1 <= hour <= 12:
            raise ValueError("Invalid morning hour.")

        # 12 AM is midnight.
        if hour == 12:
            hour = 0

    elif period in afternoon:
        if not 1 <= hour <= 23:
            raise ValueError("Invalid afternoon/evening hour.")

        # Convert 1-11 PM into 24-hour time.
        # Keep 12 PM as 12, and leave 13-23 unchanged.
        if hour < 12:
            hour += 12

    elif not 0 <= hour <= 23:
        raise ValueError("Hour must be between 0 and 23.")

    return time(hour, minute)


def parse_arabic_datetime(
    time_expression: str,
) -> tuple[str, bool]:
    """
    Parse a supported Arabic date/time expression.

    Returns:
        (ISO 8601 datetime string, was_shifted)

    The returned datetime uses the Asia/Riyadh timezone.
    Friday tasks are moved to Saturday at the same local time.
    """

    if not isinstance(time_expression, str) or not time_expression.strip():
        return "", False

    expression = normalize_arabic(time_expression)

    # Always determine 'today' using the Riyadh timezone.
    now = datetime.now(RIYADH_TZ)

    target_date = get_target_date(expression, now.date())
    target_time = get_target_time(expression)

    final_dt = datetime.combine(
        target_date,
        target_time,
        tzinfo=RIYADH_TZ,
    )

    # Friday = 4, Saturday = 5.
    was_shifted = False

    # If the final date falls on a Friday, shift it to Saturday at the same time.
    if final_dt.weekday() == 4:
        final_dt += timedelta(days=1)
        was_shifted = True

    return final_dt.isoformat(timespec="seconds"), was_shifted


if __name__ == "__main__":
    # Test the phrases specified in the assignment. Only manually verify the output, future output will come from the FastAPI backend (test_api.py or telegram).
    tests = [
        ("T01", "بكرة الساعة 10"),
        ("T02", "الأحد الجاي"),
        ("T03", "الجمعة الساعة 9"),
        ("T04", "العصر"),
        ("T09", "بعد بكرة 1 الظهر"),
        ("Extra", "بعد بكرة ١ الظهر"),
    ]

    for test_id, expression in tests:
        result, shifted = parse_arabic_datetime(expression)
        print(
            f"{test_id}: {expression!r} -> "
            f"{result}, was_shifted={shifted}"
        )

    # Verify the important requirements.
    t01, _ = parse_arabic_datetime("بكرة الساعة 10")
    dt01 = datetime.fromisoformat(t01)
    assert dt01.hour == 10
    assert dt01.utcoffset() == timedelta(hours=3)
    assert dt01.weekday() != 4

    t02, shifted02 = parse_arabic_datetime("الأحد الجاي")
    dt02 = datetime.fromisoformat(t02)
    assert dt02.weekday() == 6
    assert shifted02 is False

    t03, shifted03 = parse_arabic_datetime("الجمعة الساعة 9")
    dt03 = datetime.fromisoformat(t03)
    assert shifted03 is True
    assert dt03.weekday() == 5
    assert dt03.hour == 9

    t04, _ = parse_arabic_datetime("العصر")
    dt04 = datetime.fromisoformat(t04)
    assert dt04.hour == 15

    t09, _ = parse_arabic_datetime("بعد بكرة 1 الظهر")
    dt09 = datetime.fromisoformat(t09)
    assert dt09.hour == 13
    assert dt09.weekday() != 4

    assert parse_arabic_datetime("")[0] == ""

    print("\nAll date parsing tests passed!")
