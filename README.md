# Free Fire Tournament App

A web-based Free Fire tournament platform with player registration, match booking, wallet system, and admin panel.

## Tech Stack
- Python 3.12 + Flask
- SQLite database
- Gunicorn (production server)

## Local Run
```bash
pip install -r requirements.txt
python app.py
```

## Deploy to Railway
1. Push this folder to a GitHub repository
2. Go to https://railway.app → New Project → Deploy from GitHub
3. Select the repo → Railway auto-detects Procfile and deploys

## Features
- Player registration & login
- Tournament listing (Solo/Duo/Squad)
- Slot booking with wallet balance
- Room ID & Password reveal
- Admin panel (match creation, results)
