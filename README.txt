WEATHER FORECASTING APP WITH FLASK + SQLITE

Files:
- app.py: Flask backend and REST API
- templates/index.html: weather dashboard
- static/style.css: dashboard styles
- requirements.txt: Python dependencies
- weather.db: created automatically when app.py starts

Run on Windows:
1. Extract this ZIP.
2. Open the extracted folder in VS Code.
3. Open Terminal > New Terminal.
4. Run: python -m venv venv
5. Run: .\venv\Scripts\Activate.ps1
   If PowerShell blocks activation, use Command Prompt and run:
   venv\Scripts\activate.bat
6. Run: python -m pip install -r requirements.txt
7. Run: python app.py
8. Open: http://127.0.0.1:5000/

API endpoints:
- GET /api/health
- GET /api/weather?city=Hyderabad
- GET /api/history
- DELETE /api/history

Weather requests require internet access. SQLite is included with Python;
no separate database installation is needed. Search results are saved in weather.db.

WEEK 3 - SOURCE CODE MANAGEMENT

Project: Weather Forecasting Application
Backend: Python Flask
Frontend: HTML and CSS
Database: SQLite
Weather API: Open-Meteo

Week 3 task: Practiced feature branches and GitHub source code management.