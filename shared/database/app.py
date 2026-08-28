from flask import Flask, jsonify
import sqlite3

app = Flask(__name__)

DATABASE_NAME = "/app/data/access.db"


def get_db_connection():
    conn = sqlite3.connect(DATABASE_NAME)
    conn.row_factory = sqlite3.Row
    return conn


@app.get("/")
def health():
    return jsonify({"service": "shared-database", "status": "running"})


@app.get("/users")
def get_users():
    conn = get_db_connection()
    users = conn.execute("SELECT * FROM users").fetchall()
    conn.close()
    return jsonify([dict(row) for row in users])


@app.get("/users/<int:user_id>")
def get_user(user_id):
    conn = get_db_connection()
    user = conn.execute(
        "SELECT * FROM users WHERE id = ?", (user_id,)
    ).fetchone()
    conn.close()

    if user is None:
        return jsonify({"error": "User not found"}), 404

    return jsonify(dict(user))


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=6000, debug=True)