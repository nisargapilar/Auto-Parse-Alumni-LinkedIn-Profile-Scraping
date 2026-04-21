from flask import Blueprint, request, render_template_string, send_file
import subprocess
import os
import sys
from markupsafe import escape

# Create Blueprint
live_multiple_bp = Blueprint('live_multiple', __name__)

# ABSOLUTE path to NOTEBOOK
SCRIPT_PATH = r"C:\\Users\\USER\\linkedin\\test_code\\multiple_linkedin_profile_saver.ipynb"

# JSON Output Directory (UPDATED)
JSON_OUTPUT_DIR = r"C:\\Users\\USER\\linkedin\\test_code\\output"

# ---------------------------
# INDEX PAGE (UI)
# ---------------------------
@live_multiple_bp.route('/')
def index():
    return '''
    <html>
    <head>
        <title>Canara Alumni Scraper</title>
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
                margin-bottom: 18px;
            }
            input[type="text"] {
                width: calc(100% - 20px);
                padding: 12px 10px;
                border: 1px solid rgba(3,48,71,0.08);
                border-radius: 8px;
                margin-bottom: 14px;
                font-size: 14px;
                background-color: rgba(255,255,255,0.7);
            }
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
            <h2>Canara Alumni Scraper</h2>

            <form method="POST" action="/live_multiple/start_canara_alumni">
                <input type="text" name="count" placeholder="Enter count or search term" required />
                <br/>
                <button type="submit">Start</button>
            </form>
        </div>
    </body>
    </html>
    '''


# ---------------------------
# PROCESS ROUTE
# ---------------------------
@live_multiple_bp.route('/start_canara_alumni', methods=['POST'])
def start_canara_alumni():
    count = request.form.get('count')

    if not count:
        return "<h3>Error: No input provided.</h3>"

    try:
        env = os.environ.copy()
        env["LINKEDIN_LIMIT"] = count

        # -------------------------------
        # STEP 1 — Run Notebook
        # (This includes running parse_linkedin_02.py)
        # -------------------------------
        subprocess.run([
            "jupyter", "nbconvert",
            "--to", "notebook",
            "--execute",
            "--inplace",
            SCRIPT_PATH,
            "--ExecutePreprocessor.timeout=3600"
        ], check=True, env=env)

        # -------------------------------
        # STEP 2 — Upload JSONs AFTER everything is done
        # -------------------------------
        subprocess.run(
            ["python", r"C:\\Users\\USER\\linkedin\\test_code\\upload.py"],
            check=True
        )
        # -------------------------------

        safe_count = escape(count)

        return render_template_string(f"""
        <html>
        <head>
            <title>Started</title>
            <style>
                :root {{
                    --accent: #0077b5;
                    --accent-dark: #005f8d;
                    --text: #033047;
                    --card-bg: rgba(255,255,255,0.85);
                }}
                body {{
                    font-family: 'Segoe UI', sans-serif;
                    display:flex; align-items:center; justify-content:center;
                    min-height:100vh;
                    background-image:
                      repeating-linear-gradient(135deg,rgba(255,255,255,0.03) 0px,rgba(255,255,255,0.03) 8px,rgba(0,0,0,0.05) 8px,rgba(0,0,0,0.05) 16px),
                      linear-gradient(135deg,#5ba9e5,#3087cf,#116cb7);
                }}
                .card {{
                    background: var(--card-bg);
                    padding:34px;
                    width:420px;
                    text-align:center;
                    border-radius:12px;
                    box-shadow:0 8px 28px rgba(4,23,39,0.25);
                }}
                a {{
                    text-decoration:none;
                    color:var(--accent-dark);
                    display:block;
                    margin-top:12px;
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
                <h2>Scraper Finished</h2>
                <p>Input: <strong>{safe_count}</strong></p>

                <a href="/live_multiple/download_jsons">Download JSONs </a>
                <a href="/live_multiple/view_jsons">View JSONs</a>

                <a href="/live_multiple">Back</a>
            </div>
        </body>
        </html>
        """)

    except subprocess.CalledProcessError as e:
        return f"<h3>Error running script: {escape(str(e))}</h3>"


@live_multiple_bp.route('/download_jsons')
def download_jsons():
    import zipfile
    import time

    OUTPUT_DIR = JSON_OUTPUT_DIR  # uses the folder /output

    files = sorted(
        [f for f in os.listdir(OUTPUT_DIR) if f.endswith(".json")],
        key=lambda x: os.path.getmtime(os.path.join(OUTPUT_DIR, x)),
        reverse=True
    )[:10]

    if not files:
        return "<h3>No JSON files found in output/</h3>"

    zip_path = os.path.join(OUTPUT_DIR, f"latest_jsons_{int(time.time())}.zip")

    with zipfile.ZipFile(zip_path, 'w') as zipf:
        for f in files:
            zipf.write(os.path.join(OUTPUT_DIR, f), f)

    return send_file(zip_path, as_attachment=True)


# ---------------------------
# NEW ROUTE: View JSONs list
# ---------------------------
@live_multiple_bp.route('/view_jsons')
def view_jsons():
    files = sorted(
        [f for f in os.listdir(JSON_OUTPUT_DIR) if f.endswith(".json")],
        reverse=True
    )[:10]

    links = "".join([
        f'<li><a href="/live_multiple/json_file/{f}" style="color:var(--accent-dark); text-decoration:none;">{f}</a></li>'
        for f in files
    ])

    return f"""
    <html>
    <head>
        <title>Latest JSON Files</title>
        <style>
            :root {{
                --accent: #0077b5;
                --accent-dark: #005f8d;
                --text: #033047;
                --card-bg: rgba(255,255,255,0.85);
            }}
            body {{
                font-family: 'Segoe UI', sans-serif;
                display:flex; align-items:center; justify-content:center;
                min-height:100vh;
                background-image:
                  repeating-linear-gradient(
                      135deg,
                      rgba(255,255,255,0.03) 0px,
                      rgba(255,255,255,0.03) 8px,
                      rgba(0,0,0,0.05) 8px,
                      rgba(0,0,0,0.05) 16px
                  ),
                  linear-gradient(135deg,#5ba9e5,#3087cf,#116cb7);
                background-attachment: fixed;
            }}
            .card {{
                background: var(--card-bg);
                padding:34px;
                width:420px;
                text-align:left;
                border-radius:12px;
                box-shadow:0 8px 28px rgba(4,23,39,0.25);
            }}
            h2 {{
                color: var(--accent);
                margin-bottom: 18px;
                text-align:center;
            }}
            ul {{
                list-style:none;
                padding-left:0;
            }}
            li {{
                padding:8px 0;
                border-bottom:1px solid rgba(0,0,0,0.1);
            }}
            a:hover {{
                text-decoration:underline;
            }}
            .back {{
                margin-top:18px;
                display:block;
                text-align:center;
                color:var(--accent-dark);
                text-decoration:none;
                font-weight:600;
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
            <h2>Latest JSON Files</h2>
            <ul>{links}</ul>
            <a class="back" href="/live_multiple">← Back</a>
        </div>
    </body>
    </html>
    """


# ---------------------------
# NEW ROUTE: View a single JSON file
# ---------------------------
@live_multiple_bp.route('/json_file/<filename>')
def json_file(filename):
    return send_file(os.path.join(JSON_OUTPUT_DIR, filename))