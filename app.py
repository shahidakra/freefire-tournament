import os
import sqlite3
import socket
from functools import wraps
from flask import Flask, render_template, request, redirect, url_for, session, flash, jsonify
from database import get_db, init_db

app = Flask(__name__)
app.secret_key = "freefire_tournament_super_secret_key_2026"

def get_current_user():
    if "user_id" in session:
        conn = get_db()
        user = conn.execute("SELECT * FROM users WHERE id = ?", (session["user_id"],)).fetchone()
        conn.close()
        return user
    return None

def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if "user_id" not in session:
            flash("Kripya pehle login karein!", "warning")
            return redirect(url_for("login"))
        return f(*args, **kwargs)
    return decorated_function

def admin_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        user = get_current_user()
        if not user or not user["is_admin"]:
            flash("Access Denied! Sirf Admin is page ko access kar sakta hai.", "danger")
            return redirect(url_for("index"))
        return f(*args, **kwargs)
    return decorated_function

@app.context_processor
def inject_user():
    return dict(current_user=get_current_user())

# Home - Upcoming Matches
@app.route("/")
def index():
    mode_filter = request.args.get("mode", "ALL").upper()
    conn = get_db()
    if mode_filter == "ALL":
        matches = conn.execute("SELECT * FROM matches ORDER BY id DESC").fetchall()
    else:
        matches = conn.execute("SELECT * FROM matches WHERE mode = ? ORDER BY id DESC", (mode_filter,)).fetchall()
    
    # Calculate joined counts
    match_list = []
    for m in matches:
        joined_count = conn.execute("SELECT COUNT(*) FROM participants WHERE match_id = ?", (m["id"],)).fetchone()[0]
        m_dict = dict(m)
        m_dict["joined_count"] = joined_count
        m_dict["is_full"] = joined_count >= m["total_slots"]
        match_list.append(m_dict)
        
    conn.close()
    return render_template("index.html", matches=match_list, selected_mode=mode_filter)

# Match Details
@app.route("/match/<int:match_id>")
def match_detail(match_id):
    conn = get_db()
    match = conn.execute("SELECT * FROM matches WHERE id = ?", (match_id,)).fetchone()
    if not match:
        flash("Match nahi mila!", "danger")
        return redirect(url_for("index"))
        
    participants = conn.execute("SELECT * FROM participants WHERE match_id = ? ORDER BY slot_number ASC", (match_id,)).fetchall()
    joined_count = len(participants)
    
    user = get_current_user()
    already_joined = False
    user_slot = None
    if user:
        p = conn.execute("SELECT * FROM participants WHERE match_id = ? AND user_id = ?", (match_id, user["id"])).fetchone()
        if p:
            already_joined = True
            user_slot = p["slot_number"]
            
    conn.close()
    return render_template(
        "match_detail.html",
        match=match,
        participants=participants,
        joined_count=joined_count,
        already_joined=already_joined,
        user_slot=user_slot
    )

# Join Match
@app.route("/match/<int:match_id>/join", methods=["POST"])
@login_required
def join_match(match_id):
    user = get_current_user()
    conn = get_db()
    match = conn.execute("SELECT * FROM matches WHERE id = ?", (match_id,)).fetchone()
    if not match:
        flash("Match exist nahi karta!", "danger")
        conn.close()
        return redirect(url_for("index"))
        
    # Check already joined
    existing = conn.execute("SELECT * FROM participants WHERE match_id = ? AND user_id = ?", (match_id, user["id"])).fetchone()
    if existing:
        flash("Aap pehle hi is match me join kar chuke hain!", "info")
        conn.close()
        return redirect(url_for("match_detail", match_id=match_id))
        
    # Check slots
    joined_count = conn.execute("SELECT COUNT(*) FROM participants WHERE match_id = ?", (match_id,)).fetchone()[0]
    if joined_count >= match["total_slots"]:
        flash("Sorry, yeh match poori tarah full ho chuka hai!", "danger")
        conn.close()
        return redirect(url_for("match_detail", match_id=match_id))
        
    # Check balance
    if user["balance"] < match["entry_fee"]:
        flash(f"Kam balance! Entry fee ₹{match['entry_fee']} hai, aapke wallet me sirf ₹{user['balance']} hain.", "danger")
        conn.close()
        return redirect(url_for("wallet"))
        
    # Deduct balance & join
    new_slot = joined_count + 1
    conn.execute("UPDATE users SET balance = balance - ?, matches_played = matches_played + 1 WHERE id = ?", (match["entry_fee"], user["id"]))
    conn.execute('''
        INSERT INTO participants (match_id, user_id, ff_name, ff_uid, slot_number)
        VALUES (?, ?, ?, ?, ?)
    ''', (match_id, user["id"], user["ff_name"], user["ff_uid"], new_slot))
    conn.commit()
    conn.close()
    
    flash(f"Mubarak ho! Aapne Match #{match_id} Slot #{new_slot} par successfully join kar liya!", "success")
    return redirect(url_for("my_matches"))

# My Matches (With Room ID & Pass reveal)
@app.route("/my-matches")
@login_required
def my_matches():
    user = get_current_user()
    conn = get_db()
    rows = conn.execute('''
        SELECT m.*, p.slot_number, p.joined_at
        FROM participants p
        JOIN matches m ON p.match_id = m.id
        WHERE p.user_id = ?
        ORDER BY m.id DESC
    ''', (user["id"],)).fetchall()
    conn.close()
    return render_template("my_matches.html", matches=rows)

# Wallet
@app.route("/wallet")
@login_required
def wallet():
    user = get_current_user()
    return render_template("wallet.html", user=user)

# Add Demo Coins
@app.route("/wallet/add", methods=["POST"])
@login_required
def wallet_add():
    amount = int(request.form.get("amount", 100))
    user = get_current_user()
    conn = get_db()
    conn.execute("UPDATE users SET balance = balance + ? WHERE id = ?", (amount, user["id"]))
    conn.commit()
    conn.close()
    flash(f"₹{amount} successfully aapke wallet me add ho gaye!", "success")
    return redirect(url_for("wallet"))

# Leaderboard
@app.route("/leaderboard")
def leaderboard():
    conn = get_db()
    players = conn.execute("SELECT * FROM users ORDER BY total_kills DESC, matches_played DESC LIMIT 20").fetchall()
    conn.close()
    return render_template("leaderboard.html", players=players)

# Auth: Register
@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "").strip()
        ff_name = request.form.get("ff_name", "").strip()
        ff_uid = request.form.get("ff_uid", "").strip()
        
        if not username or not password or not ff_name or not ff_uid:
            flash("Kripya saare fields bharein!", "danger")
            return redirect(url_for("register"))
            
        conn = get_db()
        try:
            cur = conn.cursor()
            cur.execute('''
                INSERT INTO users (username, password, ff_name, ff_uid, balance)
                VALUES (?, ?, ?, ?, 100)
            ''', (username, password, ff_name, ff_uid))
            conn.commit()
            session["user_id"] = cur.lastrowid
            flash("Account successfully create ho gaya! Bonus ₹100 add kiya gaya hai.", "success")
            conn.close()
            return redirect(url_for("index"))
        except sqlite3.IntegrityError:
            conn.close()
            flash("Yeh username pehle se registered hai!", "danger")
            return redirect(url_for("register"))
            
    return render_template("register.html")

# Auth: Login
@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "").strip()
        
        conn = get_db()
        user = conn.execute("SELECT * FROM users WHERE username = ? AND password = ?", (username, password)).fetchone()
        conn.close()
        
        if user:
            session["user_id"] = user["id"]
            flash(f"Welcome back, {user['ff_name']}!", "success")
            return redirect(url_for("index"))
        else:
            flash("Galat username ya password!", "danger")
            return redirect(url_for("login"))
            
    return render_template("login.html")

# Auth: Logout
@app.route("/logout")
def logout():
    session.clear()
    flash("Aap logout ho chuke hain.", "info")
    return redirect(url_for("index"))

# --- ADMIN PANEL ---
@app.route("/admin")
@admin_required
def admin():
    conn = get_db()
    matches = conn.execute("SELECT * FROM matches ORDER BY id DESC").fetchall()
    
    matches_data = []
    for m in matches:
        participants = conn.execute("SELECT * FROM participants WHERE match_id = ?", (m["id"],)).fetchall()
        m_dict = dict(m)
        m_dict["participants"] = participants
        m_dict["joined_count"] = len(participants)
        matches_data.append(m_dict)
        
    total_users = conn.execute("SELECT COUNT(*) FROM users").fetchone()[0]
    conn.close()
    return render_template("admin.html", matches=matches_data, total_users=total_users)

@app.route("/admin/create-match", methods=["POST"])
@admin_required
def admin_create_match():
    title = request.form.get("title")
    map_name = request.form.get("map_name")
    mode = request.form.get("mode")
    entry_fee = int(request.form.get("entry_fee", 0))
    per_kill = int(request.form.get("per_kill", 0))
    win_prize = int(request.form.get("win_prize", 0))
    match_time = request.form.get("match_time")
    total_slots = int(request.form.get("total_slots", 48))
    
    conn = get_db()
    conn.execute('''
        INSERT INTO matches (title, map_name, mode, entry_fee, per_kill, win_prize, match_time, total_slots)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
    ''', (title, map_name, mode, entry_fee, per_kill, win_prize, match_time, total_slots))
    conn.commit()
    conn.close()
    
    flash("Naya tournament match successfully create ho gaya!", "success")
    return redirect(url_for("admin"))

@app.route("/admin/set-room/<int:match_id>", methods=["POST"])
@admin_required
def admin_set_room(match_id):
    room_id = request.form.get("room_id", "").strip()
    room_pass = request.form.get("room_pass", "").strip()
    
    conn = get_db()
    conn.execute("UPDATE matches SET room_id = ?, room_pass = ? WHERE id = ?", (room_id, room_pass, match_id))
    conn.commit()
    conn.close()
    
    flash(f"Match #{match_id} ke liye Room ID & Password update ho gaye! Players ko ab unke phone par dikhai denge.", "success")
    return redirect(url_for("admin"))

def get_local_ip():
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except Exception:
        return "127.0.0.1"

if __name__ == "__main__":
    init_db()
    ip = get_local_ip()
    print("==================================================")
    print("🔥 FREE FIRE TOURNAMENT APP IS READY!")
    print(f"📱 Mobile access URL: http://{ip}:8080")
    print(f"💻 Local PC access URL: http://localhost:8080")
    print("👑 Default Admin: username: admin | password: admin123")
    print("==================================================")
    app.run(host="0.0.0.0", port=8080, debug=False)
