import os
from database import init_db

# Ensure DB exists on startup (for Railway/cloud)
if not os.path.exists('app_tournament.db'):
    init_db()
