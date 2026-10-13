# Smart Task Assistant

A small Arabic task-management assistant built as an AI Engineering practical project. Employees send a message in Arabic, and the API identifies whether they want to create a task, view tasks, or ask about the company policy.

The project is intentionally kept simple: FastAPI handles requests, SQLite stores employees and tasks, and an OpenAI model extracts the intent from the message. Python code—not the model—checks permissions and handles dates.

## What it does

- Accepts messages through `POST /chat`.
- Recognizes task creation, task-list requests, and company-policy questions.
- Applies role-based assignment rules for managers, supervisors, and employees.
- Interprets supported Arabic date and time expressions using the `Asia/Riyadh` timezone and moves Friday tasks to Saturday at the same time.
- Answers policy questions using the policy supplied with the assignment and reports when the information is not available in that policy.
- Records requests and outcomes in an SQLite audit log.

## Requirements

- Python 3.11 or newer.
- An OpenAI API key with API access enabled.
- Internet access for calls to the OpenAI API.

Docker is not required for the standard Python setup. A local SQLite database is created in `data/database.db`.

## Setup

Open a terminal in the project folder and install the dependencies:

```bash
python -m pip install -r requirements.txt
```

Create your local environment file by copying the example:

**Windows Command Prompt:**

```bat
copy .env.example .env
```

**PowerShell:**

```powershell
Copy-Item .env.example .env
```

**macOS/Linux:**

```bash
cp .env.example .env
```

Open `.env` and add your own key:

```dotenv
OPENAI_API_KEY=your_actual_api_key_here
OPENAI_MODEL=gpt-4o-mini
```

Keep `.env` private and do not commit it to version control. `.env.example` should contain placeholders only.

## Initialize the database

Run this once when setting up a fresh checkout, or whenever you intentionally need to initialize the schema and seed the six fictional employees:

```bash
python init_db.py
```

The script creates the `data/` directory if needed, creates the tables, and inserts the assignment's employee records. It should not be necessary to delete the database to run the application.

## Run the API

Start the development server from the project root:

```bash
uvicorn main:app --reload
```

The API will be available at `http://127.0.0.1:8000`. Open `http://127.0.0.1:8000/docs` to send requests through FastAPI's interactive documentation.

Example request to `POST /chat`:

```json
{
  "user_id": 2,
  "message": "سجل مهمة لخالد بكرة الساعة 10 يراجع عرض السعر"
}
```

The `user_id` must match one of the seeded employees. The response includes the action taken, an optional task ID, and an Arabic reply.

## Tests

Run the component checks that are available in the project:

```bash
python auth.py
python dates.py
python policy.py
python llm.py
```

These scripts check authorization rules, date parsing and Friday rescheduling, policy answers, and LLM intent extraction. `llm.py` and `policy.py` make API calls, so they require a valid API key and may incur usage charges.

The API acceptance-test command is:

```bash
python test_api.py
```

Make sure `test_api.py` is included in the repository before running this command. Run the server in a separate terminal if your test script sends requests to the live API.

## Project files

- `main.py` — FastAPI application and `POST /chat` endpoint.
- `init_db.py` — creates the SQLite schema and seeds the fictional employees.
- `auth.py` — role-based task-assignment checks.
- `llm.py` — extracts the intent and fields from Arabic messages.
- `dates.py` — interprets supported Arabic date/time expressions and applies the Friday rule.
- `policy.py` — answers questions using the supplied company policy.
- `data/database.db` — local SQLite database, created during initialization.
- `.env.example` — template for required environment variables.

## Notes

The employee and task data in this assignment are fictional. The current prototype accepts `user_id` in the request body and checks that it exists in the database; a production system should identify the requester through an authenticated session or verified token instead. Keep the API key private, and do not use this prototype with real employee data without further security, privacy, and operational review.