from flask import Flask, render_template, request, redirect, url_for, session, flash  # added flash
import firebase_admin
from firebase_admin import credentials, firestore
from werkzeug.security import generate_password_hash, check_password_hash

# Import blueprints
from live import live_bp
from live_multiple import live_multiple_bp
from auto_connect import auto_connect_bp

# Initialize Firebase Admin SDK
cred = credentials.Certificate(r"C:\\Users\\USER\\linkedin\\test_code\\serviceAccountKey.json")
firebase_admin.initialize_app(cred)
db = firestore.client()

app = Flask(__name__)
app.secret_key = "supersecretkey"  # needed for sessions and flash messages

# Register blueprints
app.register_blueprint(live_bp, url_prefix='/live')
app.register_blueprint(live_multiple_bp, url_prefix='/live_multiple')
app.register_blueprint(auto_connect_bp, url_prefix='/auto_connect')

# -----------------------
# LOGIN ROUTE
# -----------------------
@app.route('/', methods=['GET', 'POST'])
def login():
    message = ""
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')

        user_doc = db.collection('users').document(username).get()
        if user_doc.exists:
            stored_hash = user_doc.to_dict()['password']
            if check_password_hash(stored_hash, password):
                session['user'] = username  # store username in session
                return redirect(url_for('dashboard'))
            else:
                message = "Invalid password"
        else:
            message = "User does not exist"

    return render_template('login.html', message=message)

# -----------------------
# SIGNUP ROUTE
# -----------------------
@app.route('/signup', methods=['GET', 'POST'])
def signup():
    message = ""
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        confirm_password = request.form.get('confirm_password')

        if password != confirm_password:
            message = "Passwords do not match"
        elif len(password) < 6:
            message = "Password must be at least 6 characters"
        else:
            user_ref = db.collection('users').document(username)
            if user_ref.get().exists:
                message = "Username already exists"
            else:
                hashed_password = generate_password_hash(password)
                user_ref.set({'username': username, 'password': hashed_password})
                message = "Account created successfully! <a href='/'>Login here</a>"

    return render_template('signup.html', message=message)

# -----------------------
# DASHBOARD ROUTE
# -----------------------
@app.route('/dashboard')
def dashboard():
    if 'user' not in session:
        return redirect(url_for('login'))
    username = session['user']
    return render_template('dashboard.html', username=username)

# -----------------------
# SEARCH ROUTE
# -----------------------
@app.route('/search', methods=['GET', 'POST'])
def search():
    if 'user' not in session:
        return redirect(url_for('login'))

    if request.method == 'POST':
        keyword = request.form.get('keyword')
        results = []

        for collection in db.collections():
            for doc in collection.stream():
                doc_data = doc.to_dict()
                if any(isinstance(value, str) and keyword.lower() in value.lower() for value in doc_data.values()):
                    results.append({
                        'collection': collection.id,
                        'doc_id': doc.id,
                        'data': doc_data
                    })

        return render_template('search.html', results=results, keyword=keyword)

    # For GET request (when user clicks Database Access)
    return render_template('search.html')

# -----------------------
# LOGOUT ROUTE
# -----------------------
@app.route('/logout')
def logout():
    session.pop('user', None)
    return redirect(url_for('login'))

# -----------------------
if __name__ == '__main__':
    # Make sure EMAIL_ADDRESS and EMAIL_PASSWORD are set as environment variables before running
    # Example (Windows CMD):
    # set EMAIL_ADDRESS=your_email@gmail.com
    # set EMAIL_PASSWORD=your_app_password
    app.run(debug=True)
