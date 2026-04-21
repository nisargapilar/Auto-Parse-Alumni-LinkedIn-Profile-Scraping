from dotenv import load_dotenv
load_dotenv()

from flask import Blueprint, render_template, request, redirect, url_for, flash
from firebase_admin import firestore
import os
import smtplib
from email.message import EmailMessage
import mimetypes
import re

auto_connect_bp = Blueprint('auto_connect', __name__)

EMAIL_ADDRESS = os.environ.get("AC_EMAIL")
EMAIL_PASSWORD = os.environ.get("AC_PASSWORD")

print(f"🔐 AutoConnect - Email: {EMAIL_ADDRESS}")
print(f"🔐 AutoConnect - Password loaded: {'YES' if EMAIL_PASSWORD else 'NO'}")

if not EMAIL_ADDRESS or not EMAIL_PASSWORD:
    print("⚠️ WARNING: AC_EMAIL or AC_PASSWORD not loaded from .env file!")

ALLOWED_EXTENSIONS = {'pdf', 'doc', 'docx'}
MAX_FILE_SIZE = 5 * 1024 * 1024


def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS


def extract_email(profile):
    if profile.get('emails') and isinstance(profile['emails'], list) and profile['emails']:
        email = profile['emails'][0]
        if email and isinstance(email, str) and email.strip():
            return email.strip()

    about = profile.get('about', '')
    if about and '@' in about:
        email_pattern = r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b'
        emails_in_about = re.findall(email_pattern, about)
        if emails_in_about:
            return emails_in_about[0]

    return None


def has_email(profile):
    return extract_email(profile) is not None


def profile_matches_search(profile, keyword):
    keyword = keyword.lower()
    searchable_text = " ".join([
        str(profile.get('name', '')),
        str(profile.get('about', '')),
        str(profile.get('profile_name', '')),
        str(profile.get('extracted_email', ''))
    ]).lower()

    return keyword in searchable_text


@auto_connect_bp.route('/', methods=['GET'])
def auto_connect_home():
    db = firestore.client()
    profiles = []
    search_query = request.args.get('q', '').strip()

    try:
        all_collections = list(db.collections())

        for collection in all_collections:
            try:
                docs = list(collection.stream())

                for doc in docs:
                    profile_data = doc.to_dict()
                    if profile_data and has_email(profile_data):

                        profile_data['id'] = f"{collection.id}/{doc.id}"
                        profile_data['profile_name'] = collection.id
                        profile_data['extracted_email'] = extract_email(profile_data)

                        if search_query:
                            if profile_matches_search(profile_data, search_query):
                                profiles.append(profile_data)
                        else:
                            profiles.append(profile_data)

            except Exception as coll_error:
                print(f"⚠️ Error accessing {collection.id}: {coll_error}")
                continue

    except Exception as e:
        flash(f"Error fetching data from Firestore: {e}", "danger")

    return render_template(
        'auto_connect.html',
        profiles=profiles,
        search_query=search_query
    )


@auto_connect_bp.route('/send_email/<path:profile_id>', methods=['POST'])
def send_email(profile_id):

    if not EMAIL_ADDRESS or not EMAIL_PASSWORD:
        flash("Email credentials not configured. Contact admin.", "danger")
        return redirect(url_for('auto_connect.auto_connect_home'))

    db = firestore.client()

    try:
        collection_id, doc_id = profile_id.split('/')
    except ValueError:
        flash("Invalid profile identifier.", "danger")
        return redirect(url_for('auto_connect.auto_connect_home'))

    try:
        doc_ref = db.collection(collection_id).document(doc_id)
        profile = doc_ref.get().to_dict()
        if not profile:
            flash("Profile not found.", "danger")
            return redirect(url_for('auto_connect.auto_connect_home'))
    except Exception as e:
        flash(f"Failed to fetch profile: {e}", "danger")
        return redirect(url_for('auto_connect.auto_connect_home'))

    recipient_email = extract_email(profile)

    if not recipient_email:
        flash("No email found. Sending test email to your own address.", "warning")
        recipient_email = EMAIL_ADDRESS

    email_pattern = r'^[a-zA-Z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}$'
    if not re.match(email_pattern, recipient_email):
        flash("Invalid email format.", "danger")
        return redirect(url_for('auto_connect.auto_connect_home'))

    message_body = request.form.get('message') or "Hello, I'd like to connect with you regarding guidance."

    msg = EmailMessage()
    msg['Subject'] = 'Career Guidance Request'
    msg['From'] = EMAIL_ADDRESS
    msg['To'] = recipient_email

    msg.set_content(f"""
{message_body}

Best regards,
Aspiring Professional
""")

    resume = request.files.get('resume')
    if resume and resume.filename:

        if not allowed_file(resume.filename):
            flash("Only PDF, DOC, and DOCX files allowed.", "danger")
            return redirect(url_for('auto_connect.auto_connect_home'))

        resume.seek(0, 2)
        file_size = resume.tell()
        resume.seek(0)

        if file_size > MAX_FILE_SIZE:
            flash("File must be under 5MB.", "danger")
            return redirect(url_for('auto_connect.auto_connect_home'))

        resume_filename = resume.filename.replace(" ", "_")
        mime_type, _ = mimetypes.guess_type(resume_filename)
        maintype, subtype = (mime_type.split('/') if mime_type else ('application', 'octet-stream'))

        msg.add_attachment(
            resume.read(),
            maintype=maintype,
            subtype=subtype,
            filename=resume_filename
        )

    try:
        with smtplib.SMTP("smtp.gmail.com", 587, timeout=30) as smtp:
            smtp.starttls()
            smtp.login(EMAIL_ADDRESS, EMAIL_PASSWORD)
            smtp.send_message(msg)

        flash(f"Email sent to {recipient_email} successfully!", "success")

    except smtplib.SMTPException as e:
        flash(f"Email sending failed: {str(e)}", "danger")

    return redirect(url_for('auto_connect.auto_connect_home'))
