from flask import Flask, jsonify, request
import sqlite3

app = Flask(__name__)

##helper function
def query_db(sql, args=()):
    conn = sqlite3.connect("/app/data/labtests.db")
    conn.row_factory = sqlite3.Row
    cur = conn.execute(sql, args)
    rows = [dict(r) for r in cur.fetchall()]
    conn.close()
    return rows

@app.route("/orders", methods=["GET"])
def get_orders():
    return jsonify(query_db("SELECT * FROM lab_orders"))

@app.route("/orders/<int:order_id>", methods=["GET"])
def get_order(order_id):
    rows = query_db("SELECT * FROM lab_orders WHERE order_id=?", (order_id,))
    if not rows:
        return jsonify({"error": "Order not found"}), 404
    return jsonify(rows[0])

@app.route("/orders", methods=["POST"])
def create_order():
    data = request.get_json()
    conn = sqlite3.connect("/app/data/labtests.db")
    cur = conn.execute(
        "INSERT INTO lab_orders (patient_id, test_type, ordered_by, status) VALUES (?, ?, ?, ?)",
        (data["patient_id"], data["test_type"], data["ordered_by"], data.get("status", "pending"))
    )
    conn.commit()
    new_id = cur.lastrowid
    conn.close()
    return jsonify({"order_id": new_id}), 201

@app.route("/results/<int:order_id>", methods=["GET"])
def get_results(order_id):
    return jsonify(query_db("SELECT * FROM lab_results WHERE order_id=?", (order_id,)))

@app.route("/results", methods=["POST"])
def create_result():
    data = request.get_json()
    conn = sqlite3.connect("/app/data/labtests.db")
    cur = conn.execute(
        "INSERT INTO lab_results (order_id, result_value, reference_range, flagged, ai_notes) VALUES (?, ?, ?, ?, ?)",
        (data["order_id"], data["result_value"], data["reference_range"], data.get("flagged", 0), data.get("ai_notes", ""))
    )
    conn.commit()
    new_id = cur.lastrowid
    conn.close()
    return jsonify({"result_id": new_id}), 201

@app.route("/results/<int:result_id>", methods=["PUT"])
def update_result(result_id):
    data = request.get_json()
    conn = sqlite3.connect("/app/data/labtests.db")
    conn.execute(
        "UPDATE lab_results SET result_value=?, reference_range=?, flagged=?, ai_notes=? WHERE result_id=?",
        (data.get("result_value"), data.get("reference_range"), data.get("flagged", 0), data.get("ai_notes", ""), result_id)
    )
    conn.commit()
    conn.close()
    return jsonify({"status": "updated"})

@app.route("/results/<int:result_id>", methods=["DELETE"])
def delete_result(result_id):
    conn = sqlite3.connect("/app/data/labtests.db")
    conn.execute("DELETE FROM lab_results WHERE result_id=?", (result_id,))
    conn.commit()
    conn.close()
    return jsonify({"status": "deleted"})

@app.route("/orders/<int:order_id>", methods=["PUT"])
def update_order(order_id):
    data = request.get_json()
    conn = sqlite3.connect("/app/data/labtests.db")
    conn.execute(
        "UPDATE lab_orders SET status=? WHERE order_id=?",
        (data["status"], order_id)
    )
    conn.commit()
    conn.close()
    return jsonify({"status": "updated"})

@app.route("/orders/<int:order_id>", methods=["DELETE"])
def delete_order(order_id):
    conn = sqlite3.connect("/app/data/labtests.db")
    conn.execute("DELETE FROM lab_orders WHERE order_id=?", (order_id,))
    conn.commit()
    conn.close()
    return jsonify({"status": "deleted"})

@app.route("/results", methods=["GET"])
def get_all_results():
    return jsonify(query_db("SELECT * FROM lab_results"))

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=6005)