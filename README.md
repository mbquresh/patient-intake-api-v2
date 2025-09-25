# Patient Intake API v2

Flask-based patient intake system with standard and comprehensive pediatric forms. HIPAA-conscious handling, tokenized access links, and Azure Logic Apps integration.

## Features
- Token-secured intake links (24h expiry)
- Standard and pediatric intake forms (WTForms)
- Azure Logic Apps webhook integration
- Optional SMS sending via Azure Communication Services

## Quickstart
```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
# Edit .env as needed
export FLASK_ENV=development
python app.py
```

Server starts on http://localhost:5001 by default.

## Environment Variables
See `.env.example` for all variables. Key ones:
- SECRET_KEY: Flask secret (required)
- LOGIC_APP_WEBHOOK_URL: Optional Logic Apps HTTP endpoint to receive submissions
- AZURE_COMMUNICATION_CONNECTION_STRING: Optional, for SMS
- AZURE_PHONE_NUMBER: Optional, for SMS
- PORT: Optional (default 5001)
- FLASK_ENV: development or production

## Endpoints
- GET `/` Health/info doc for the service
- GET `/intake/<token>` Standard intake form
- POST `/submit/<token>` Submit standard intake
- GET `/pediatric-intake/<token>` Pediatric intake form
- POST `/pediatric-submit/<token>` Submit pediatric intake
- POST `/admin/generate-link` Generate standard intake tokenized URL
- POST `/admin/generate-pediatric-link` Generate pediatric intake tokenized URL
- POST `/admin/send-intake-link` Send intake link via SMS (if configured)
- GET `/admin/sms-status` SMS connectivity test
- GET `/health` Health check

## Payloads Sent To Logic Apps
The app posts JSON to `LOGIC_APP_WEBHOOK_URL` with shape:

- Standard form:
```json
{
  "patient_information": { /* structured sections from MultipartConverter */ },
  "submission_metadata": {
    "clinic_id": "...",
    "patient_id": "...",
    "submitted_at": "2025-01-01T10:30:00Z",
    "form_version": "2.0",
    "data_hash": "..."
  }
}
```

- Pediatric form:
```json
{
  "patient_information": {
    "form_type": "pediatric_comprehensive",
    "patient_history": { /* name, age, sex, dob, ... */ },
    "birth_history": { /* delivery_type, birth_timing, ... */ },
    "medical_history": { /* child_conditions[], family_conditions[] */ },
    "social_history": { /* household_members, pets, ... */ },
    "parent_guardian_info": { /* mother{}, father{} */ },
    "insurance": { /* name, id, group, pharmacy_* */ },
    "consent": { /* treatment_consent, parent_guardian_name, signature_date */ },
    "siblings_info": "...",
    "address": { /* address, city, state, zip */ }
  },
  "submission_metadata": {
    "clinic_id": "...",
    "patient_id": "...",
    "submitted_at": "2025-01-01T10:30:00Z",
    "form_version": "2.0_pediatric",
    "data_hash": "..."
  }
}
```

Tip (Logic Apps): Use "Parse JSON" action with "Use sample payload to generate schema" for clean Dynamic Content.

## SMS (Optional)
- Requires Azure Communication Services connection string and a purchased phone number
- Controlled by env vars; if missing, the API disables SMS endpoints gracefully

## Development Notes
- CSRF is currently disabled for easier testing; enable in production
- Debug mode is controlled by `FLASK_ENV=development`

## License
MIT
