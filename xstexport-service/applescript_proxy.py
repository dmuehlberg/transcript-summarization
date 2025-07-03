from flask import Flask, send_file, jsonify
import subprocess
from pathlib import Path

app = Flask(__name__)

@app.route('/run-applescript', methods=['POST'])
def run_applescript():
    script_path = Path.home() / 'export_calendar.scpt'
    xml_path = Path.home() / 'outlook_calendar_export_with_attendees.xml'
    result = subprocess.run(['osascript', str(script_path)], capture_output=True, text=True)
    if result.returncode != 0:
        return jsonify({'error': result.stderr}), 500
    if not xml_path.exists():
        return jsonify({'error': 'XML not found'}), 500
    return send_file(str(xml_path))

if __name__ == '__main__':
    app.run(port=5001) 