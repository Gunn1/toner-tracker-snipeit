# Toner Tracker with Snipe-IT Integration

A lightweight toner tracking and monitoring tool for schools.  
Built with FastAPI + SQLite + Snipe-IT integration.

## Features
- Track toner stock and replacements
- Pull printer and asset data from Snipe-IT
- Low stock alerts
- Simple web dashboard

## Setup

```bash
git clone https://github.com/Gunn1/toner-tracker-snipeit.git
cd toner-tracker-snipeit
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
cp .env.example .env  # Then fill in values
uvicorn app.main:app --reload
