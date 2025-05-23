import os
import logging
from flask import Flask, render_template, jsonify
import firebase_admin
from firebase_admin import credentials, firestore

# Get logger (basic logging for Flask interface)
logger = logging.getLogger(__name__)

# Initialize Flask app
app = Flask(__name__)
app.secret_key = os.environ.get("SESSION_SECRET", "crypto-trading-signals")

# Initialize Firebase Admin SDK with service account
try:
    cred = credentials.Certificate('service-account.json')
    firebase_admin.initialize_app(cred)
    db = firestore.client()
    logger.info("Firebase initialized successfully with service account")
except Exception as e:
    logger.error(f"Failed to initialize Firebase: {e}")
    db = None

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/api/status')
def status():
    return jsonify({
        'status': 'online',
        'firebase_connected': db is not None
    })

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)
