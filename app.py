import os
import json
import time
import queue
import threading
from concurrent.futures import ThreadPoolExecutor
from flask import Flask, render_template, request, jsonify, redirect, url_for, send_file, flash
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename
from pdf_processor import process_pdf, get_pdf_metadata
from config import logger, MAX_QUEUE_SIZE, DOCUMENT_PROCESSING_DELAY, API_USAGE_LOG_PATH
import openai
from openai import OpenAI
from openpyxl import Workbook
import io
import csv
from diskcache import Cache
from rag_system import initialize_rag_system, get_relevant_chunks

app = Flask(__name__)
app.config.from_object('config')
app.config['SECRET_KEY'] = os.urandom(24)

login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'

class User(UserMixin):
    def __init__(self, id, username, password_hash):
        self.id = id
        self.username = username
        self.password_hash = password_hash

users = {}

@login_manager.user_loader
def load_user(user_id):
    return users.get(int(user_id))

processing_queue = queue.Queue(maxsize=MAX_QUEUE_SIZE)
documents = {}
api_semaphore = threading.Semaphore(2)
api_queue = queue.Queue()

MAX_RETRIES = 5

cache = Cache('./cache')

executor = ThreadPoolExecutor(max_workers=4)

client = OpenAI()

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() == 'pdf'

@app.errorhandler(Exception)
def handle_exception(e):
    logger.error(f"Unhandled exception: {str(e)}", exc_info=True)
    return jsonify(error="An unexpected error occurred. Please try again later."), 500

@app.route('/')
@login_required
def index():
    return render_template('index.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        user = next((u for u in users.values() if u.username == username), None)
        if user and check_password_hash(user.password_hash, password):
            login_user(user)
            return redirect(url_for('index'))
        flash('Invalid username or password')
    return render_template('login.html')

@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('login'))

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        if username in [u.username for u in users.values()]:
            flash('Username already exists')
        else:
            user_id = len(users) + 1
            users[user_id] = User(user_id, username, generate_password_hash(password))
            flash('Registration successful. Please log in.')
            return redirect(url_for('login'))
    return render_template('register.html')

@app.route('/upload', methods=['POST'])
@login_required
def upload_file():
    if 'files' not in request.files:
        return jsonify(error="No file part"), 400
    files = request.files.getlist('files')
    if not files or all(file.filename == '' for file in files):
        return jsonify(error="No selected file"), 400

    for file in files:
        if file and allowed_file(file.filename):
            filename = secure_filename(file.filename)
            file_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
            file.save(file_path)
            document = {
                'filename': filename,
                'path': file_path,
                'status': 'Uploaded',
                'processing': False,
                'retry_count': 0
            }
            documents[filename] = document
            processing_queue.put(filename)
        else:
            return jsonify(error="Invalid file type. Only PDF files are allowed."), 400

    return jsonify(message="Files uploaded successfully"), 200

def process_document(filename):
    document = documents[filename]
    document['processing'] = True
    document['status'] = 'Processing'

    try:
        text = get_pdf_metadata(document['path'])
        result = process_pdf(text)
        
        if not result:
            raise ValueError("Generated result is empty")
        
        document['result'] = result
        document['status'] = 'Completed'
        logger.info(f"Successfully processed document: {filename}")

        # Initialize RAG system with processed documents
        initialize_rag_system({filename: {'content': text}})
    except Exception as e:
        logger.error(f"Error processing document {filename}: {str(e)}")
        document['status'] = 'Failed'
        document['error'] = str(e)
    finally:
        document['processing'] = False

def document_processing_worker():
    while True:
        try:
            filename = processing_queue.get(timeout=1)
            process_document(filename)
        except queue.Empty:
            time.sleep(1)
        except Exception as e:
            logger.error(f"Error in document processing worker: {str(e)}")

threading.Thread(target=document_processing_worker, daemon=True).start()

@app.route('/get_checklists', methods=['GET'])
@login_required
def get_checklists():
    results = {}
    processing = {}
    errors = {}

    for filename, doc in documents.items():
        if 'result' in doc:
            results[filename] = doc['result']
        elif doc['processing']:
            processing[filename] = doc['status']
        elif 'error' in doc:
            errors[filename] = doc['error']

    return jsonify({
        'results': results,
        'processing': processing,
        'errors': errors,
        'total_documents': len(documents),
        'completed': len(results)
    })

@app.route('/list_documents')
@login_required
def list_documents():
    return render_template('documents.html', documents=documents)

@app.route('/view_document/<filename>')
@login_required
def view_document(filename):
    if filename not in documents:
        flash('Document not found')
        return redirect(url_for('list_documents'))
    return render_template('document_details.html', document=documents[filename])

@app.route('/delete_document/<filename>', methods=['POST'])
@login_required
def delete_document(filename):
    if filename in documents:
        file_path = documents[filename]['path']
        if os.path.exists(file_path):
            os.remove(file_path)
        del documents[filename]
        flash(f'Document {filename} deleted successfully')
    else:
        flash('Document not found')
    return redirect(url_for('list_documents'))

@app.route('/api_usage')
@login_required
def api_usage():
    api_usage = {}
    with open(API_USAGE_LOG_PATH, 'r') as f:
        for line in f:
            timestamp, api_name = line.strip().split(',')
            api_usage[api_name] = api_usage.get(api_name, 0) + 1
    return jsonify(api_usage)

@app.route('/export_checklist/<filename>/<format>')
@login_required
def export_checklist(filename, format):
    if filename not in documents or 'result' not in documents[filename]:
        flash('Result not found')
        return redirect(url_for('view_document', filename=filename))

    result = documents[filename]['result']

    if format == 'csv':
        output = io.StringIO()
        writer = csv.writer(output)
        writer.writerow(['Item', 'Value'])
        for key, value in result.items():
            writer.writerow([key, value])
        output.seek(0)
        return send_file(io.BytesIO(output.getvalue().encode()), mimetype='text/csv', as_attachment=True, download_name=f'{filename}_result.csv')
    elif format == 'excel':
        wb = Workbook()
        ws = wb.active
        ws.append(['Item', 'Value'])
        for key, value in result.items():
            ws.append([key, value])
        output = io.BytesIO()
        wb.save(output)
        output.seek(0)
        return send_file(output, mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet', as_attachment=True, download_name=f'{filename}_result.xlsx')
    else:
        flash('Invalid export format')
        return redirect(url_for('view_document', filename=filename))

def generate_api_usage_report():
    api_usage = {}
    first_call_timestamp = float('inf')
    last_call_timestamp = 0
    
    with open(API_USAGE_LOG_PATH, 'r') as f:
        for line in f:
            timestamp, api_name = line.strip().split(',')
            timestamp = float(timestamp)
            api_usage[api_name] = api_usage.get(api_name, 0) + 1
            
            if timestamp < first_call_timestamp:
                first_call_timestamp = timestamp
            if timestamp > last_call_timestamp:
                last_call_timestamp = timestamp
    
    total_calls = sum(api_usage.values())
    
    report = {
        'total_api_calls': total_calls,
        'api_usage_breakdown': api_usage,
        'first_call_timestamp': first_call_timestamp if first_call_timestamp != float('inf') else None,
        'last_call_timestamp': last_call_timestamp if last_call_timestamp != 0 else None,
    }
    
    return report

@app.route('/api_usage_report')
@login_required
def api_usage_report():
    report = generate_api_usage_report()
    return jsonify(report)

@app.route('/chatbot', methods=['POST'])
@login_required
def chatbot():
    data = request.json
    user_message = data.get('message')
    
    if not user_message:
        return jsonify(error="No message provided"), 400

    try:
        # Use RAG system to retrieve relevant chunks
        relevant_chunks = get_relevant_chunks(user_message)
        
        if not relevant_chunks:
            return jsonify(response="I'm sorry, I couldn't find any relevant information in the processed documents. Can you please rephrase your question or ask about a different topic?")

        # Construct prompt with relevant chunks
        prompt = f"""Based on the following information from processed documents:

{' '.join(relevant_chunks)}

User question: {user_message}

Please provide a concise and informative answer:"""
        
        try:
            response = client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[
                    {"role": "system", "content": "You are a helpful assistant for a compliance checklist generator application. Provide concise and accurate information based on the processed documents."},
                    {"role": "user", "content": prompt}
                ]
            )
            
            chatbot_response = response.choices[0].message.content
            return jsonify(response=chatbot_response)
        except openai.error.APIError as api_error:
            logger.error(f"OpenAI API error: {str(api_error)}")
            return jsonify(error="An error occurred while processing your request. Please try again later."), 500
        except openai.error.RateLimitError:
            logger.error("OpenAI API rate limit exceeded")
            return jsonify(error="The service is currently busy. Please try again in a few moments."), 429
        except Exception as e:
            logger.error(f"Unexpected error in OpenAI API call: {str(e)}")
            return jsonify(error="An unexpected error occurred. Please try again later."), 500
    except Exception as e:
        logger.error(f"Error in chatbot: {str(e)}")
        return jsonify(error="An error occurred while processing your request. Please try again."), 500

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)