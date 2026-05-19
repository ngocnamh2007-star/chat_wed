from flask import Flask, render_template, request, redirect, session
import sqlite3
from werkzeug.security import generate_password_hash, check_password_hash

app = Flask(__name__)
app.secret_key = "chat_secret_key"


def get_db():
    return sqlite3.connect("chat.db")


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
        username = request.form["username"]
        password = request.form["password"]

        hashed_password = generate_password_hash(password, method="pbkdf2:sha256")

        try:
            db = get_db()
            cursor = db.cursor()
            cursor.execute(
                "INSERT INTO users (username, password) VALUES (?, ?)",
                (username, hashed_password)
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
        username = request.form["username"]
        password = request.form["password"]

        db = get_db()
        cursor = db.cursor()
        cursor.execute("SELECT * FROM users WHERE username = ?", (username,))
        user = cursor.fetchone()
        db.close()

        if user and check_password_hash(user[2], password):
            session["username"] = username
            return redirect("/chat")
        else:
            error = "Sai tài khoản hoặc mật khẩu!"

    return render_template("login.html", error=error)


@app.route("/chat", methods=["GET", "POST"])
def chat():
    if "username" not in session:
        return redirect("/login")

    current_user = session["username"]
    selected_user = request.args.get("user")

    db = get_db()
    cursor = db.cursor()

    cursor.execute("SELECT username FROM users WHERE username != ?", (current_user,))
    users = cursor.fetchall()

    if request.method == "POST":
        receiver = request.form["receiver"]
        message = request.form["message"]

        if receiver and message.strip():
            cursor.execute(
                "INSERT INTO messages (sender, receiver, message) VALUES (?, ?, ?)",
                (current_user, receiver, message)
            )
            db.commit()

        db.close()
        return redirect(f"/chat?user={receiver}")

    messages = []

    if selected_user:
        cursor.execute("""
            SELECT sender, receiver, message, created_at 
            FROM messages
            WHERE 
                (sender = ? AND receiver = ?)
                OR 
                (sender = ? AND receiver = ?)
            ORDER BY id ASC
        """, (current_user, selected_user, selected_user, current_user))

        messages = cursor.fetchall()

    db.close()

    return render_template(
        "chat.html",
        users=users,
        messages=messages,
        username=current_user,
        selected_user=selected_user
    )


@app.route("/logout")
def logout():
    session.clear()
    return redirect("/login")


if __name__ == "__main__":
    create_tables()
    app.run(host="0.0.0.0", port=5000, debug=True)