import os
import json
import time
from datetime import datetime
from flask import Flask, request, send_from_directory, jsonify
from flask_cors import CORS
from pymongo import MongoClient
from dotenv import load_dotenv

load_dotenv()

app = Flask(__name__, static_folder='agent_ui')
CORS(app)

DATA_FOLDER = 'data'
os.makedirs(DATA_FOLDER, exist_ok=True)

# DB SETUP
mongo_uri = os.getenv("MONGO_URI")
client = MongoClient(mongo_uri)
collection = client["voice_authentication"]["voice_prints"]

# INITIALIZE VERIFIER
from voice_verification_system import VoiceVerifier
verifier = VoiceVerifier()


@app.route('/')
def index():
    return send_from_directory('agent_ui', 'index.html')

@app.route('/<path:path>')
def serve_static(path):
    return send_from_directory('agent_ui', path)

@app.route('/login', methods=['POST'])
def login():
    data = request.json
    user_id = data.get('user_id')
    
    if not user_id:
        return jsonify({"error": "User ID required"}), 400
        
    user = collection.find_one({"user_id": user_id})
    if user:
        return jsonify({"message": "Login successful"}), 200
    else:
        return jsonify({"error": "User ID not found"}), 401

@app.route('/upload', methods=['POST'])
def upload_audio():
    if 'audio' not in request.files:
        return jsonify({"error": "No audio file provided"}), 400
    
    audio_file = request.files['audio']
    user_id = request.form.get('user_id', 'unknown') # Get ID from form
    
    if audio_file.filename == '':
        return jsonify({"error": "No selected file"}), 400

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    # Save with USER_ID in filename
    filename = f"voice_{user_id}_{timestamp}.wav"
    save_path = os.path.join(DATA_FOLDER, filename)
    
    audio_file.save(save_path)
    print(f"[SUCCESS] Audio saved for {user_id}: {save_path}")
    
    return jsonify({"message": "File uploaded successfully", "filename": filename}), 200

@app.route('/enroll', methods=['POST'])
def enroll():
    if 'audio' not in request.files:
        return jsonify({"error": "No audio file provided"}), 400
    
    audio_file = request.files['audio']
    user_id = request.form.get('user_id')
    
    if not user_id:
        return jsonify({"error": "User ID required"}), 400
        
    if audio_file.filename == '':
        return jsonify({"error": "No selected file"}), 400

    temp_path = os.path.join(DATA_FOLDER, f"enroll_temp_{user_id}.wav")
    audio_file.save(temp_path)
    
    success, message = verifier.enroll_user(temp_path, user_id)
    
    # Cleanup temp file (DISABLED FOR DEBUGGING)
    # if os.path.exists(temp_path):
    #    os.remove(temp_path)
        
    if success:
        return jsonify({"message": message}), 200
    else:
        return jsonify({"error": message}), 500


import json
import time

@app.route('/check_status', methods=['GET'])
def check_status():
    result_path = os.path.join(DATA_FOLDER, 'result.json')
    if not os.path.exists(result_path):
        return jsonify({"status": "waiting"}), 200
    
    try:
        with open(result_path, 'r') as f:
            data = json.load(f)
        
        # Check if result is recent (within last 10 seconds)
        if time.time() - data.get('timestamp', 0) > 10:
             return jsonify({"status": "waiting"}), 200
             
        return jsonify(data), 200
    except:
        return jsonify({"status": "waiting"}), 200

@app.errorhandler(Exception)
def handle_exception(e):
    # Pass through HTTP errors
    if hasattr(e, 'code'):
        return jsonify({"error": str(e)}), e.code
    # Handle non-HTTP exceptions only
    import traceback
    print(f"[ERROR] UNHANDLED SERVER ERROR: {str(e)}")
    print(traceback.format_exc())
    return jsonify({"error": f"Internal Server Error: {str(e)}"}), 500

if __name__ == '__main__':
    print(f"[START] Server running at http://localhost:5000")
    print(f"[INFO] Saving audio to: {os.path.abspath(DATA_FOLDER)}")
    app.run(port=5000, debug=False)
