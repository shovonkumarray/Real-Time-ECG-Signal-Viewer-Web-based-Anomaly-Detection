from flask import Flask, request, jsonify, render_template
from flask_cors import CORS
import sqlite3
import numpy as np
from scipy import signal
import csv
from io import StringIO

app = Flask(__name__)
CORS(app)

# Initialize SQLite database
def init_db():
    conn = sqlite3.connect('ecg_data.db')
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS ecg_signals
                 (id INTEGER PRIMARY KEY AUTOINCREMENT, time REAL, voltage REAL)''')
    conn.commit()
    conn.close()

# Simulate ECG signal (inspired by MIT-BIH)
def simulate_ecg():
    fs = 360  # Sampling frequency (Hz), typical for MIT-BIH
    t = np.linspace(0, 10, 10 * fs)  # 10 seconds
    # Generate synthetic ECG with QRS complexes
    ecg = np.zeros_like(t)
    for i in range(0, len(t), int(fs * 0.8)):  # Heartbeat every ~0.8s (75 BPM)
        ecg[i:i+int(fs*0.2)] += signal.gausspulse(t[i:i+int(fs*0.2)] - t[i], fc=5) * 1.5
    # Add noise
    noise = np.random.normal(0, 0.05, len(t))
    ecg += noise
    # Add occasional anomaly (e.g., high peak)
    if len(t) > int(fs * 2):
        ecg[int(fs * 2)] += 2  # Simulate abnormal peak
    return t.tolist(), ecg.tolist()

# Detect anomalies (threshold-based)
def detect_anomalies(signal_data):
    mean = np.mean(signal_data)
    std = np.std(signal_data)
    threshold = mean + 3 * std  # Detect peaks > 3 standard deviations
    anomalies = []
    for i, value in enumerate(signal_data):
        if abs(value) > threshold:
            anomalies.append({'index': i, 'value': value, 'type': 'High Peak (Potential Arrhythmia)'})
    return anomalies

# Store ECG data in database
def store_ecg_data(time, voltage):
    conn = sqlite3.connect('ecg_data.db')
    c = conn.cursor()
    c.execute('DELETE FROM ecg_signals')  # Clear previous data
    for t, v in zip(time, voltage):
        c.execute('INSERT INTO ecg_signals (time, voltage) VALUES (?, ?)', (t, v))
    conn.commit()
    conn.close()

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/get_ecg', methods=['GET'])
def get_ecg():
    try:
        # Simulate ECG data
        time, signal_data = simulate_ecg()
        store_ecg_data(time, signal_data)
        anomalies = detect_anomalies(signal_data)
        return jsonify({'time': time, 'signal': signal_data, 'anomalies': anomalies})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/upload_ecg', methods=['POST'])
def upload_ecg():
    try:
        file = request.files['file']
        if not file.filename.endswith('.csv'):
            return jsonify({'error': 'File must be CSV'}), 400
        content = file.read().decode('utf-8')
        csv_reader = csv.reader(StringIO(content))
        next(csv_reader)  # Skip header
        time, signal_data = [], []
        for row in csv_reader:
            if len(row) >= 2:
                time.append(float(row[0]))
                signal_data.append(float(row[1]))
        store_ecg_data(time, signal_data)
        anomalies = detect_anomalies(signal_data)
        return jsonify({'time': time, 'signal': signal_data, 'anomalies': anomalies})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

if __name__ == '__main__':
    init_db()
    app.run(debug=True, host='0.0.0.0', port=5000)