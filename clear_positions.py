#!/usr/bin/env python3
"""
Script to clear all open positions from Firestore
This will allow the signal generator to start fresh
"""

import firebase_admin
from firebase_admin import credentials, firestore
import os

# Initialize Firebase Admin SDK
if not firebase_admin._apps:
    # Use default credentials in Cloud environment
    firebase_admin.initialize_app()

# Get Firestore client
db = firestore.client()

# Determine mode from environment or default
MODE = os.environ.get('MODE', 'LIVE')
print(f"Operating in {MODE} mode")

# Collection names based on mode
positions_collection = f'crypto_positions_{MODE.lower()}'
cooldown_collection = f'crypto_signals_cooldown_{MODE.lower()}'

print(f"\nClearing positions from: {positions_collection}")
print(f"Clearing cooldowns from: {cooldown_collection}")

# Clear all open positions
try:
    positions_ref = db.collection(positions_collection)
    open_positions = positions_ref.where('status', '==', 'OPEN').stream()
    
    count = 0
    for doc in open_positions:
        print(f"Deleting open position: {doc.id} - {doc.to_dict().get('symbol')}")
        doc.reference.delete()
        count += 1
    
    print(f"\n✅ Deleted {count} open positions")
except Exception as e:
    print(f"❌ Error clearing positions: {e}")

# Clear all cooldown records
try:
    cooldown_ref = db.collection(cooldown_collection)
    cooldowns = cooldown_ref.stream()
    
    count = 0
    for doc in cooldowns:
        print(f"Deleting cooldown: {doc.id}")
        doc.reference.delete()
        count += 1
    
    print(f"\n✅ Deleted {count} cooldown records")
except Exception as e:
    print(f"❌ Error clearing cooldowns: {e}")

print("\n🎉 All positions and cooldowns cleared! Signal generation can now start fresh.") 