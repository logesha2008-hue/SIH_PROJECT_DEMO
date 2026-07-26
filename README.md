# Community Hall Booking System

## Project Description
This project is a community hall booking system designed to replace the traditional paper register used by a panchayat office. It allows staff to book halls, prevent double bookings, track deposits, and view booking history through a simple web interface.

## Technology Stack
- Backend: Python with Flask
- Database: SQLite
- Frontend: HTML, CSS, and JavaScript
- Additional libraries: Requests (used for the concurrency test)

## Installation and Execution
1. Open the project folder.
2. Create and activate a Python virtual environment:
   - Windows:
     - `py -3 -m venv venv`
     - `venv\\Scripts\\activate`
3. Install the required packages:
   - `pip install -r backend/requirements.txt`
4. Seed the database and prepare sample data:
   - `python backend/seed.py`
5. Start the application:
   - `python backend/app.py`
6. Open your browser and visit:
   - `http://localhost:5050/`

The app also provides calendar and deposits pages through the same server.

## Demonstration Video Link
https://drive.google.com/file/d/1qeRflVi8F1IIr6gJ4uUC6ww-ZP6_HpKv/view
