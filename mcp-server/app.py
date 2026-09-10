from flask import Flask, jsonify

from registry import discover_tools

app = Flask(__name__)


@app.route('/health', methods=['GET'])
def health():
    return jsonify({"status": "ok"}), 200


@app.route('/tools', methods=['GET'])
def list_tools():
    tools_list = discover_tools()
    response = [
        {"name": t["name"], "description": t["description"], "input_schema": t["input_schema"]}
        for t in tools_list
    ]
    return jsonify(response), 200


if __name__ == '__main__':
    app.run(port=7000, debug=True)