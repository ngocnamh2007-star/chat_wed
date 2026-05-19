from flask import Flask, render_template, request, redirect, session, jsonify
import sqlite3
from werkzeug.security import generate_password_hash, check_password_hash

app = Flask(__name__)
app.secret_key = "chat_secret_key"


def get_db():
    db = sqlite3.connect("chat.db")
    db.row_factory = sqlite3.Row
    return db


def create_tables():
    db = get_db()
    cursor = db.cursor()

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            password TEXT NOT NULL
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS messages (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            sender TEXT NOT NULL,
            receiver TEXT NOT NULL,
            message TEXT NOT NULL,
            deleted_by_sender INTEGER DEFAULT 0,
            deleted_by_receiver INTEGER DEFAULT 0,
            recalled INTEGER DEFAULT 0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    db.commit()
    db.close()


@app.route("/")
def home():
    if "username" in session:
        return redirect("/chat")
    return redirect("/login")


@app.route("/register", methods=["GET", "POST"])
def register():
    error = ""

    if request.method == "POST":
        username = request.form["username"].strip()
        password = request.form["password"]

        try:
            db = get_db()
            cursor = db.cursor()
            cursor.execute(
                "INSERT INTO users (username, password) VALUES (?, ?)",
                (username, generate_password_hash(password, method="pbkdf2:sha256"))
            )
            db.commit()
            db.close()
            return redirect("/login")
        except:
            error = "Tên tài khoản đã tồn tại!"

    return render_template("register.html", error=error)


@app.route("/login", methods=["GET", "POST"])
def login():
    error = ""

    if request.method == "POST":
        username = request.form["username"].strip()
        password = request.form["password"]

        db = get_db()
        cursor = db.cursor()
        cursor.execute("SELECT * FROM users WHERE username = ?", (username,))
        user = cursor.fetchone()
        db.close()

        if user and check_password_hash(user["password"], password):
            session["username"] = username
            return redirect("/chat")
        else:
            error = "Sai tài khoản hoặc mật khẩu!"

    return render_template("login.html", error=error)


@app.route("/chat")
def chat():
    if "username" not in session:
        return redirect("/login")

    current_user = session["username"]
    selected_user = request.args.get("user")

    db = get_db()
    cursor = db.cursor()
    cursor.execute("SELECT username FROM users WHERE username != ? ORDER BY username", (current_user,))
    users = cursor.fetchall()
    db.close()

    return render_template(
        "chat.html",
        users=users,
        username=current_user,
        selected_user=selected_user
    )


@app.route("/send_message", methods=["POST"])
def send_message():
    if "username" not in session:
        return jsonify({"status": "error"})

    sender = session["username"]
    receiver = request.form["receiver"]
    message = request.form["message"].strip()

    if message:
        db = get_db()
        cursor = db.cursor()
        cursor.execute(
            "INSERT INTO messages (sender, receiver, message) VALUES (?, ?, ?)",
            (sender, receiver, message)
        )
        db.commit()
        db.close()

    return jsonify({"status": "success"})


@app.route("/get_messages")
def get_messages():
    if "username" not in session:
        return jsonify([])

    current_user = session["username"]
    selected_user = request.args.get("user")
    keyword = request.args.get("keyword", "").strip()

    db = get_db()
    cursor = db.cursor()

    query = """
        SELECT id, sender, receiver, message, recalled, created_at
        FROM messages
        WHERE 
            (
                (sender = ? AND receiver = ? AND deleted_by_sender = 0)
                OR
                (sender = ? AND receiver = ? AND deleted_by_receiver = 0)
            )
    """

    params = [current_user, selected_user, selected_user, current_user]

    if keyword:
        query += " AND message LIKE ?"
        params.append(f"%{keyword}%")

    query += " ORDER BY id ASC"

    cursor.execute(query, params)
    messages = cursor.fetchall()
    db.close()

    return jsonify([
        {
            "id": msg["id"],
            "sender": msg["sender"],
            "receiver": msg["receiver"],
            "message": "Tin nhắn đã được thu hồi" if msg["recalled"] else msg["message"],
            "recalled": msg["recalled"],
            "created_at": msg["created_at"]
        }
        for msg in messages
    ])


@app.route("/delete_message", methods=["POST"])
def delete_message():
    if "username" not in session:
        return jsonify({"status": "error"})

    current_user = session["username"]
    message_id = request.form["message_id"]

    db = get_db()
    cursor = db.cursor()
    cursor.execute("SELECT sender, receiver FROM messages WHERE id = ?", (message_id,))
    msg = cursor.fetchone()

    if msg:
        if msg["sender"] == current_user:
            cursor.execute("UPDATE messages SET deleted_by_sender = 1 WHERE id = ?", (message_id,))
        elif msg["receiver"] == current_user:
            cursor.execute("UPDATE messages SET deleted_by_receiver = 1 WHERE id = ?", (message_id,))

        db.commit()

    db.close()
    return jsonify({"status": "success"})


@app.route("/recall_message", methods=["POST"])
def recall_message():
    if "username" not in session:
        return jsonify({"status": "error"})

    current_user = session["username"]
    message_id = request.form["message_id"]

    db = get_db()
    cursor = db.cursor()
    cursor.execute("SELECT sender FROM messages WHERE id = ?", (message_id,))
    msg = cursor.fetchone()

    if msg and msg["sender"] == current_user:
        cursor.execute(
            "UPDATE messages SET recalled = 1, message = ? WHERE id = ?",
            ("Tin nhắn đã được thu hồi", message_id)
        )
        db.commit()

    db.close()
    return jsonify({"status": "success"})


@app.route("/delete_account", methods=["POST"])
def delete_account():
    if "username" not in session:
        return redirect("/login")

    username = session["username"]

    db = get_db()
    cursor = db.cursor()
    cursor.execute("DELETE FROM messages WHERE sender = ? OR receiver = ?", (username, username))
    cursor.execute("DELETE FROM users WHERE username = ?", (username,))
    db.commit()
    db.close()

    session.clear()
    return redirect("/register")


@app.route("/logout")
def logout():
    session.clear()
    return redirect("/login")


create_tables()

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)
