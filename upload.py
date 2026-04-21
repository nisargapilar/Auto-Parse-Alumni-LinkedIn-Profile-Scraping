import firebase_admin
from firebase_admin import credentials, firestore
import os
import json
import sys

# ------- FIX: Force UTF-8 output on Windows -------
try:
    sys.stdout.reconfigure(encoding='utf-8')
except Exception:
    pass
# --------------------------------------------------

# Initialize Firebase
cred = credentials.Certificate(r"C:\\Users\\USER\\linkedin\\test_code\\serviceAccountKey.json")
firebase_admin.initialize_app(cred)
db = firestore.client()

OUTPUT_DIR = r"C:\\Users\\USER\\linkedin\\test_code\\output"


def upload_single(file_path):
    if not os.path.exists(file_path):
        print(f"⚠️ File not found: {file_path}")
        return

    print(f"\n🚀 Uploading SINGLE FILE → {file_path}")

    with open(file_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    # Firestore collection name = filename without extension
    collection_name = os.path.splitext(os.path.basename(file_path))[0]
    collection_ref = db.collection(collection_name)

    # Upload logic
    if isinstance(data, dict):
        if all(isinstance(v, dict) for v in data.values()):
            for doc_id, doc_data in data.items():
                collection_ref.document(doc_id).set(doc_data)
        else:
            collection_ref.document("doc1").set(data)

    elif isinstance(data, list):
        for idx, doc_data in enumerate(data):
            collection_ref.document(f"doc{idx+1}").set(doc_data)

    else:
        collection_ref.document("doc1").set({"value": data})

    print(f"✅ Uploaded to collection '{collection_name}'")


def upload_all():
    if not os.path.isdir(OUTPUT_DIR):
        print(f"⚠️ Output folder not found: {OUTPUT_DIR}")
        return

    json_files = [
        f for f in os.listdir(OUTPUT_DIR) if f.endswith(".json")
    ]

    if not json_files:
        print("⚠️ No JSON files found in output/")
        return

    print(f"\n📁 Uploading ALL {len(json_files)} JSON files...\n")

    for f in json_files:
        upload_single(os.path.join(OUTPUT_DIR, f))

    print("\n🎉 ALL FILES UPLOADED SUCCESSFULLY!")


if __name__ == "__main__":
    # If argument passed → upload only that file
    if len(sys.argv) > 1:
        upload_single(sys.argv[1])
    else:
        # No argument → upload all JSONs
        upload_all()

    print("\n✨ Upload script complete.")
