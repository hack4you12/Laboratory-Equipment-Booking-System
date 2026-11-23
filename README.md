# Laboratory Equipment Booking System

A Flask starter application for the AIA-8 Final Jury project.

## Current starter features
- Login for Student, Faculty, Lab Assistant and Administrator demo roles
- Role-protected equipment management
- Equipment catalogue
- Lab assistant/admin equipment condition and status updates
- SQLite database created automatically on first run

## Setup
1. Install Python 3.10 or newer.
2. Open a terminal in this project folder.
3. Create and activate a virtual environment:

### Windows
```bash
py -m venv venv
venv\Scripts\activate
```

### macOS/Linux
```bash
python3 -m venv venv
source venv/bin/activate
```

4. Install dependencies:
```bash
pip install -r requirements.txt
```

5. Start the app:
```bash
python app.py
```

6. Open http://127.0.0.1:5000 in your browser.

## Demo logins
| Role | Email | Password |
|---|---|---|
| Student | student@lab.com | Student@123 |
| Faculty | faculty@lab.com | Faculty@123 |
| Lab Assistant | assistant@lab.com | Assistant@123 |
| Administrator | admin@lab.com | Admin@123 |

## Important
This is Phase 1, not the completed jury application. Booking requests, calendar/free-slot discovery, faculty approval, cancellation, conflict prevention and utilization reports are planned for the next implementation phases. Change the Flask secret key and demo passwords before any public deployment. Do not use the Flask development server for production.

## Phase 2 additions
Student booking requests, overlap prevention for pending/approved bookings, cancellation, faculty approval/rejection, and administrator summary report.

Stop your existing Flask server with Ctrl+C, replace your app.py and templates folder with these files, and restart using `py -3.14 app.py`. Keep your existing `lab_booking.db` file. The new bookings table is created automatically.

This is a local demo, not production-ready. Availability is checked on submission rather than shown in a calendar. Do not publish the demo credentials.
