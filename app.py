import os
import os
import subprocess
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
from pathlib import Path
from PIL import Image
from fpdf import FPDF
from openai import OpenAI
from dotenv import load_dotenv
from flask_cors import CORS
from werkzeug.utils import secure_filename
from rembg import remove  # Ensure you have this import at the top
import logging

from flask import (Flask, redirect, render_template, request,
                   send_from_directory, url_for)

load_dotenv()

ALLOWED_EXTENSIONS = set(['txt', 'pdf', 'png', 'jpg', 'jpeg', 'gif',
                          'doc', 'docx', 'xls', 'xlsx', 'ppt', 'pptx', 'csv', 'zip', 'rar', 'mp4',
                          'mp3', 'wav', 'avi', 'mkv', 'flv', 'mov', 'wmv'])



app = Flask(__name__)
CORS(app, resources={r"/*": {"origins": "http://localhost:3000", "methods": ["GET", "POST", "OPTIONS"]}})
UPLOAD_FOLDER = app.config['UPLOAD_FOLDER'] = os.path.join(os.getcwd(), 'uploads')

# Add error handling for OpenAI client initialization
try:
    api_key = os.getenv('OPENAI_API_KEY')
    if not api_key:
        raise ValueError("OpenAI API key not found in environment variables")
    client = OpenAI(api_key=api_key)
except Exception as e:
    logging.error(f"Failed to initialize OpenAI client: {str(e)}")
    client = None

@app.route('/')
def index():
   print('Request for index page received')
   if os.getenv('OPENAI_API_KEY'):
       print(f"OpenAI API Key is available: {os.getenv('OPENAI_API_KEY')}")
   else:
       print("OpenAI API Key is not available")
   return render_template('index.html')

@app.route('/favicon.ico')
def favicon():
    return send_from_directory(os.path.join(app.root_path, 'static'),
                               'favicon.ico', mimetype='image/vnd.microsoft.icon')

@app.route('/hello', methods=['POST'])
def hello():
   name = request.form.get('name')

   if name:
       print('Request for hello page received with name=%s' % name)
       return render_template('hello.html', name = name)
   else:
       print('Request for hello page received with no name or blank name -- redirecting')
       return redirect(url_for('index'))

@app.route('/health')
def health_check():
    return "listening"







if __name__ == '__main__':
   app.run(debug=True)
   
   
