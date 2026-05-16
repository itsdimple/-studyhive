from flask import Flask, render_template, request, jsonify, send_from_directory
from werkzeug.utils import secure_filename
import datetime
from groq import Groq
from dotenv import load_dotenv
import json
import os
import fitz

load_dotenv()

app = Flask(__name__)
client = Groq(api_key=os.environ.get("GROQ_API_KEY"))

@app.route('/')
def home():
    return render_template('index.html')

@app.route('/generate', methods=['POST'])
def generate():
    notes = request.json['notes']

    chat_completion = client.chat.completions.create(
        messages=[{
            "role": "user",
            "content": f"""Read these notes and generate 8 flashcards.
Return ONLY a JSON array, no extra text, like this:
[{{"question": "...", "answer": "..."}}]

Notes:
{notes}"""
        }],
        model="llama-3.3-70b-versatile",
    )

    cards = json.loads(chat_completion.choices[0].message.content)
    return jsonify(cards)

@app.route('/quiz', methods=['POST'])
def quiz():
    notes = request.json['notes']

    chat_completion = client.chat.completions.create(
        messages=[{
            "role": "user",
            "content": f"""Read these notes and generate 5 multiple choice questions.
Return ONLY a JSON array, no extra text, like this:
[{{"question": "...", "options": ["A. ...", "B. ...", "C. ...", "D. ..."], "answer": "A"}}]

Notes:
{notes}"""
        }],
        model="llama-3.3-70b-versatile",
    )

    questions = json.loads(chat_completion.choices[0].message.content)
    return jsonify(questions)

import os

NOTES_FILE = "notes.json"

def load_notes():
    if not os.path.exists(NOTES_FILE):
        return []
    with open(NOTES_FILE) as f:
        return json.load(f)

@app.route('/library')
def library():
    return render_template('library.html')

@app.route('/get-notes')
def get_notes():
    notes = load_notes()
    subject = request.args.get('subject', '')
    if subject:
        notes = [n for n in notes if n['subject'].lower() == subject.lower()]
    return jsonify(sorted(notes, key=lambda x: x['views'], reverse=True))

@app.route('/share', methods=['POST'])
def share():
    data = request.json
    notes = load_notes()
    notes.append({
        "title": data['title'],
        "subject": data['subject'],
        "author": data['author'],
        "notes": data['notes'],
        "cards": data['cards'],
        "views": 0,
        "upvotes": 0
    })
    with open(NOTES_FILE, 'w') as f:
        json.dump(notes, f)
    return jsonify({"status": "shared"})

@app.route('/upvote', methods=['POST'])
def upvote():
    index = request.json['index']
    notes = load_notes()
    notes[index]['upvotes'] += 1
    with open(NOTES_FILE, 'w') as f:
        json.dump(notes, f)
    return jsonify({"status": "upvoted", "upvotes": notes[index]['upvotes']})

@app.route('/unupvote', methods=['POST'])
def unupvote():
    index = request.json['index']
    notes = load_notes()
    if notes[index]['upvotes'] > 0:
        notes[index]['upvotes'] -= 1
    with open(NOTES_FILE, 'w') as f:
        json.dump(notes, f)
    return jsonify({"status": "unupvoted", "upvotes": notes[index]['upvotes']})

@app.route('/delete-note', methods=['POST'])
def delete_note():
    index = request.json['index']
    notes = load_notes()
    if 0 <= index < len(notes):
        notes.pop(index)
        with open(NOTES_FILE, 'w') as f:
            json.dump(notes, f)
        return jsonify({"status": "deleted"})
    return jsonify({"status": "error"})

@app.route('/view/<int:index>')
def view_note(index):
    notes = load_notes()
    notes[index]['views'] += 1
    with open(NOTES_FILE, 'w') as f:
        json.dump(notes, f)
    return jsonify(notes[index])

COLLECTION_FILE = "collection.json"
UPLOAD_FOLDER = "uploads"
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

def load_collection():
    if not os.path.exists(COLLECTION_FILE):
        return []
    with open(COLLECTION_FILE) as f:
        return json.load(f)

@app.route('/collection')
def collection():
    return render_template('collection.html')

@app.route('/get-collection')
def get_collection():
    return jsonify(load_collection())

@app.route('/save-collection', methods=['POST'])
def save_collection():
    data = request.json
    collection = load_collection()
    collection.append({
        "title": data['title'],
        "subject": data['subject'],
        "notes": data['notes'],
        "cards": data['cards'],
        "pdf_filename": data.get('pdf_filename', ''),
        "date": datetime.datetime.now().strftime("%d %b %Y, %I:%M %p")
    })
    with open(COLLECTION_FILE, 'w') as f:
        json.dump(collection, f)
    return jsonify({"status": "saved"})

@app.route('/delete-collection', methods=['POST'])
def delete_collection():
    index = request.json['index']
    collection = load_collection()
    if 0 <= index < len(collection):
        # delete PDF file too if exists
        pdf = collection[index].get('pdf_filename', '')
        if pdf:
            pdf_path = os.path.join(UPLOAD_FOLDER, pdf)
            if os.path.exists(pdf_path):
                os.remove(pdf_path)
        collection.pop(index)
        with open(COLLECTION_FILE, 'w') as f:
            json.dump(collection, f)
    return jsonify({"status": "deleted"})

@app.route('/upload-pdf', methods=['POST'])
def upload_pdf():
    file = request.files['pdf']
    pdf_bytes = file.read()
    
    # save PDF to uploads folder
    filename = secure_filename(file.filename)
    filepath = os.path.join(UPLOAD_FOLDER, filename)
    with open(filepath, 'wb') as f:
        f.write(pdf_bytes)
    
    # extract text
    try:
        pdf = fitz.open(stream=pdf_bytes, filetype="pdf")
        text = ""
        for page in pdf:
            text += page.get_text()
        return jsonify({
            "text": text[:3000],
            "pdf_filename": filename
        })
    except Exception as e:
        return jsonify({
            "text": "",
            "pdf_filename": "",
            "error": str(e)
        }), 400

@app.route('/download-pdf/<filename>')
def download_pdf(filename):
    return send_from_directory(UPLOAD_FOLDER, filename, as_attachment=True)

@app.route('/share-with-pdf', methods=['POST'])
def share_with_pdf():
    data = request.json
    notes = load_notes()
    notes.append({
        "title": data['title'],
        "subject": data['subject'],
        "author": data['author'],
        "notes": data['notes'],
        "cards": data['cards'],
        "pdf_filename": data.get('pdf_filename', ''),
        "views": 0,
        "upvotes": 0
    })
    with open(NOTES_FILE, 'w') as f:
        json.dump(notes, f)
    return jsonify({"status": "shared"})

@app.route('/todo')
def todo():
    return render_template('todo.html')

if __name__ == '__main__':
    import os
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port, debug=False)