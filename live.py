from flask import Blueprint, request, send_file, render_template_string
from markupsafe import escape
import json
import os
import subprocess
import sys
import glob

live_bp = Blueprint('live', __name__)

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

@live_bp.route('/')
def index():
    return '''
    <html>
    <head>
        <title>Auto Parser</title>
        <style>
            :root{
                --accent: #0077b5;
                --accent-dark: #005f8d;
                --text: #033047;
                --card-bg: rgba(255,255,255,0.85);
            }
            html,body {
                height: 100%;
                margin: 0;
            }
            body {
                font-family: 'Segoe UI', sans-serif;
                color: var(--text);
                display: flex;
                align-items: center;
                justify-content: center;
                min-height: 100vh;
                background-image:
                  repeating-linear-gradient(
                      135deg,
                      rgba(255,255,255,0.03) 0px,
                      rgba(255,255,255,0.03) 8px,
                      rgba(0,0,0,0.05) 8px,
                      rgba(0,0,0,0.05) 16px
                  ),
                  linear-gradient(135deg, #5ba9e5 0%, #3087cf 50%, #116cb7 100%);
                background-attachment: fixed;
            }
            .card {
                background: var(--card-bg);
                border-radius: 12px;
                box-shadow: 0 8px 28px rgba(4,23,39,0.25);
                padding: 34px;
                width: 420px;
                text-align: center;
                backdrop-filter: blur(5px);
            }
            h2 {
                color: var(--accent);
                margin: 0 0 18px 0;
            }
            input[type="text"] {
                width: calc(100% - 20px);
                padding: 12px 10px;
                border: 1px solid rgba(3,48,71,0.08);
                border-radius: 8px;
                margin-bottom: 12px;
                font-size: 14px;
                outline: none;
                background-color: rgba(255,255,255,0.7);
            }
            input[type="text"]::placeholder { color: rgba(3,48,71,0.4); }
            button {
                background-color: var(--accent);
                color: white;
                border: none;
                padding: 10px 18px;
                border-radius: 8px;
                cursor: pointer;
                font-weight: 600;
                transition: transform 120ms ease, box-shadow 120ms ease;
            }
            button:hover {
                transform: translateY(-2px);
                box-shadow: 0 8px 22px rgba(3,48,71,0.15);
                background-color: var(--accent-dark);
            }
            .tiny {
                font-size: 13px;
                color: rgba(3,48,71,0.8);
                margin-top: 10px;
            }
            /* BACK BUTTON STYLES */
            .back-btn {
                position: fixed;
                top: 20px;
                left: 20px;
                padding: 12px 20px;
                background: var(--accent);
                border: none;
                color: white;
                border-radius: 8px;
                cursor: pointer;
                text-decoration: none;
                display: inline-block;
                font-weight: 600;
                transition: background 0.3s, transform 0.2s;
                z-index: 1000;
            }
            .back-btn:hover {
                background: var(--accent-dark);
                transform: translateY(-2px);
            }
        </style>
    </head>
    <body>
        <!-- BACK BUTTON -->
        <a href="/dashboard" class="back-btn">⬅ Back</a>
        
        <div class="card">
            <h2>LinkedIn Profile Parser</h2>
            <form method="POST" action="/live/process">
                <input type="text" name="profile_url" placeholder="Enter LinkedIn URL" required />
                <br/>
                <button type="submit">Auto Parse</button>
            </form>
            <p class="tiny">Paste a public profile URL — we will do the rest.</p>
        </div>
    </body>
    </html>
    '''

@live_bp.route('/process', methods=['POST'])
def process():
    url = request.form.get('profile_url')

    url_path = os.path.join(BASE_DIR, "url_input.json")
    with open(url_path, "w", encoding="utf-8") as f:
        json.dump({"url": url}, f)

    notebook_path = os.path.join(BASE_DIR, "linkedin_profile_saver.ipynb")

    try:
        result = subprocess.run(
            [
                sys.executable,
                "-m", "jupyter", "nbconvert",
                "--to", "notebook",
                "--execute",
                "--inplace",
                notebook_path
            ],
            cwd=BASE_DIR,
            capture_output=True,
            text=True,
            check=True
        )
        print("Notebook executed successfully.")
    except subprocess.CalledProcessError as e:
        return f"<h3>Notebook failed:</h3><pre>{escape(e.stderr)}</pre>"

    # ---- NEW: Get newest JSON from output/ folder directly ----
    output_dir = os.path.join(BASE_DIR, "output")
    candidates = glob.glob(os.path.join(output_dir, "*.json"))

    if not candidates:
        return "<h3>No JSON output found.</h3>"

    latest_json = max(candidates, key=os.path.getmtime)
    print("Latest JSON is:", latest_json)

    # ---- Upload directly (no copying, no renaming) ----
    try:
        subprocess.run(
            [sys.executable, os.path.join(BASE_DIR, "upload.py"), latest_json],
            cwd=BASE_DIR,
            capture_output=True,
            text=True,
            check=True
        )
        print("Uploaded to Firestore:", latest_json)
    except subprocess.CalledProcessError as e:
        return f"<h3>Upload failed:</h3><pre>{escape(e.stderr)}</pre>"

    safe_url = escape(url)
    return render_template_string(f"""
    <html>
    <head>
        <title>Parsing Complete</title>
        <style>
            :root{{
                --accent: #0077b5;
                --accent-dark: #005f8d;
                --text: #033047;
                --card-bg: rgba(255,255,255,0.85);
            }}
            body {{
                font-family: 'Segoe UI', sans-serif;
                color: var(--text);
                display: flex;
                align-items: center;
                justify-content: center;
                min-height: 100vh;
                margin: 0;
                background-image:
                  repeating-linear-gradient(
                      135deg,
                      rgba(255,255,255,0.03) 0px,
                      rgba(255,255,255,0.03) 8px,
                      rgba(0,0,0,0.05) 8px,
                      rgba(0,0,0,0.05) 16px
                  ),
                  linear-gradient(135deg, #5ba9e5 0%, #3087cf 50%, #116cb7 100%);
            }}
            .card {{
                background: var(--card-bg);
                padding: 34px;
                border-radius: 12px;
                text-align: center;
                width: 440px;
            }}
            a.button {{
                background-color: var(--accent);
                color: white;
                padding: 10px 18px;
                border-radius: 8px;
                text-decoration: none;
                font-weight: 600;
                margin: 8px;
            }}
            a.button:hover {{
                background-color: var(--accent-dark);
            }}
            /* BACK BUTTON STYLES */
            .back-btn {{
                position: fixed;
                top: 20px;
                left: 20px;
                padding: 12px 20px;
                background: var(--accent);
                border: none;
                color: white;
                border-radius: 8px;
                cursor: pointer;
                text-decoration: none;
                display: inline-block;
                font-weight: 600;
                transition: background 0.3s, transform 0.2s;
                z-index: 1000;
            }}
            .back-btn:hover {{
                background: var(--accent-dark);
                transform: translateY(-2px);
            }}
        </style>
    </head>
    <body>
        <!-- BACK BUTTON -->
        <a href="/dashboard" class="back-btn">⬅ Back</a>
        
        <div class="card">
            <h2>Parsing Complete</h2>
            <p>Profile parsed:</p>
            <p><strong>{safe_url}</strong></p>
            <a href="/live/download" class="button">⬇️ Download JSON</a>
            <a href="/live/view" class="button">👀 View JSON</a>
            <br/><br/>
            <a href="/live" style="font-size:13px;">Back</a>
        </div>
    </body>
    </html>
    """)

# ---------------------------
# DOWNLOAD NEWEST FILE
# ---------------------------
@live_bp.route('/download')
def download():
    output_dir = os.path.join(BASE_DIR, "output")
    candidates = glob.glob(os.path.join(output_dir, "*.json"))
    if not candidates:
        return "<h3>No JSON file available.</h3>"
    latest = max(candidates, key=os.path.getmtime)
    return send_file(latest, as_attachment=True)

# ---------------------------
# VIEW NEWEST FILE
# ---------------------------
@live_bp.route('/view')
def view_json():
    output_dir = os.path.join(BASE_DIR, "output")
    candidates = glob.glob(os.path.join(output_dir, "*.json"))
    if not candidates:
        return "<h3>No JSON file available.</h3>"
    latest = max(candidates, key=os.path.getmtime)
    with open(latest, "r", encoding="utf-8") as f:
        data = json.load(f)
    formatted = json.dumps(data, indent=4, ensure_ascii=False)
    return f"<pre>{escape(formatted)}</pre>"