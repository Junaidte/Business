# General Business Management Software

This is a Flask-based starter project for a multi-business ERP-style application.

## Features included
- Flask application factory setup
- SQLAlchemy models for businesses, users, roles, permissions, products, inventory, sales, purchases, customers, suppliers, expenses, and payments
- Login and registration flow
- Dashboard, reports, and stock monitoring
- Multi-business architecture foundation

## Setup

1. Open a terminal in the project folder.
2. Activate the virtual environment:
   - Windows: `.venv\Scripts\activate`
3. Install requirements if needed:
   - `pip install -r requirements.txt`
4. Copy `.env.example` to `.env` and update values if needed.
5. Run the app:
   - `python run.py`

## Environment configuration

The app reads `FLASK_ENV`, `SECRET_KEY`, `DATABASE_URL`, and `PORT` from the environment.

Example development settings:
- `FLASK_ENV=development`
- `DATABASE_URL=sqlite:///business_management.db`

Example production settings:
- `FLASK_ENV=production`
- `SECRET_KEY=your-long-random-secret`
- `DATABASE_URL=postgresql://postgres:password@localhost:5432/business_management`
- `PORT=5000`

## Notes
- SQLite remains the default for local development.
- PostgreSQL is supported through `psycopg2-binary` for production deployment.
- The application is configured to respect environment-based debug mode and deployment settings.
