import os
import json
import openai
import uuid
import aiohttp
from flask import Flask, render_template, request, jsonify, session
from concurrent.futures import ThreadPoolExecutor

BASE_DIR = os.path.abspath(os.path.dirname(__file__))

CONFIG_PATH = os.path.join(BASE_DIR, "settings", "config.json")
FIX_READING_PATH = os.path.join(BASE_DIR, "settings", "fix-reading.json")

AUDIO_DIR = os.path.join(BASE_DIR, 'static', 'audio')
os.makedirs(AUDIO_DIR, exist_ok=True)

with open(CONFIG_PATH) as f:
    config = json.load(f)

with open(FIX_READING_PATH, "r", encoding="utf-8") as f:
    fix_reading = json.load(f)

app = Flask(__name__, 
            static_folder=os.path.join(BASE_DIR, 'static'),
            template_folder=os.path.join(BASE_DIR, 'templates'))
app.secret_key = config["SECRET_KEY"]

openai.api_key = config["OPENAI_API_KEY"]

ELEVENLABS_API_KEY = config["ELEVENLABS_API_KEY"]
ELEVENLABS_VOICE_ID = config["ELEVENLABS_VOICE_ID"]

executor = ThreadPoolExecutor(max_workers=3)

def fix_reading_text(text):
    for key, value in fix_reading.items():
        text = text.replace(key, value)
    return text

@app.route("/")
def index():
    if 'messages' not in session:
        session['messages'] = [{"role": "system", "content": "あなたは可愛い女子高校生型のアシスタントAIです。"}]
    return render_template("index.html")

async def transcribe_audio(audio_file):
    with open(audio_file, "rb") as file:
        transcript = await openai.Audio.atranscribe("whisper-1", file)
    return transcript["text"]

async def generate_response(messages):
    response = await openai.ChatCompletion.acreate(
        model="gpt-4o",
        messages=messages
    )
    return response.choices[0].message['content'][:500]

async def generate_speech(text):
    url = f"https://api.elevenlabs.io/v1/text-to-speech/{ELEVENLABS_VOICE_ID}"
    headers = {
        "Accept": "audio/mpeg",
        "Content-Type": "application/json",
        "xi-api-key": ELEVENLABS_API_KEY
    }
    data = {
        "text": text,
        "model_id": "eleven_multilingual_v2",
        "voice_settings": {
            "stability": 0.5,
            "similarity_boost": 0.75,
            #"style": 0.3,
            "language": "ja",
            "use_speaker_boost": "True",
        }
    }
    async with aiohttp.ClientSession() as session:
        async with session.post(url, json=data, headers=headers) as response:
            return await response.read()

@app.route("/transcribe", methods=["POST"])
async def transcribe():
    audio_file = request.files["audio"]
    temp_file = os.path.join(AUDIO_DIR, f"temp_{uuid.uuid4()}.mp3")
    audio_file.save(temp_file)

    try:
        transcript_text = await transcribe_audio(temp_file)
        
        if not transcript_text.strip():
            return jsonify({
                "transcript": "", 
                "response": "",
                "audio_url": "",
                "error": "音声が検出されませんでした。"
            }), 400

        session['messages'].append({"role": "user", "content": transcript_text})
        
        response_text = await generate_response(session['messages'])
        session['messages'].append({"role": "assistant", "content": response_text})
        session.modified = True

        response_text_fixed = fix_reading_text(response_text)
        audio_content = await generate_speech(response_text_fixed)

        unique_filename = f"{uuid.uuid4()}.mp3"
        output_path = os.path.join(AUDIO_DIR, unique_filename)

        with open(output_path, "wb") as f:
            f.write(audio_content)

        return jsonify({
            "transcript": transcript_text, 
            "response": response_text, 
            "audio_url": f"/static/audio/{unique_filename}"
        })
    finally:
        if os.path.exists(temp_file):
            os.remove(temp_file)

@app.route("/delete_audio", methods=["POST"])
def delete_audio():
    audio_url = request.json["audio_url"]
    file_path = os.path.join(BASE_DIR, audio_url.lstrip('/'))
    if os.path.exists(file_path):
        os.remove(file_path)
    return jsonify({"status": "success"})

@app.route("/reset_conversation", methods=["POST"])
def reset_conversation():
    session['messages'] = [{"role": "system", "content": "あなたは可愛い女子高校生型のアシスタントAIです。"}]
    return jsonify({"status": "success"})

if __name__ == "__main__":
    app.run(port=5001, debug=True)
