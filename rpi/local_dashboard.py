#!/usr/bin/env python3
from flask import Flask, render_template, jsonify
import threading
import time
import random

app = Flask(__name__, template_folder='templates')

# Simulated data
data = {
    "decibels": 0, "light": 0, "indoorTemp": 0, "humidity": 0,
    "song": "None", "comfort": 0
}

def update_data():
    global data
    while True:
        data = {
            "decibels": round(random.uniform(60, 85), 1),
            "light": random.randint(200, 800),
            "indoorTemp": round(random.uniform(68, 76), 1),
            "humidity": random.randint(40, 60),
            "song": random.choice(["Sweet Caroline", "Bohemian Rhapsody", "Don't Stop Believin'"]),
            "comfort": random.randint(90, 100)
        }
        time.sleep(2)

threading.Thread(target=update_data, daemon=True).start()

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/data')
def get_data():
    return jsonify(data)

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=8080)
