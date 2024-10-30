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
                   send_from_directory, url_for, jsonify)

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



# We are getting to read the system prompt
def read_system_prompt():
    try:
        with open("ycai_prompt.txt", "r") as file:
            return file.read()
    except FileNotFoundError:
        print("ycai_prompt.txt not found. Using default prompt.")
        return "Default prompt here"

SYSTEM_PROMPT = read_system_prompt()


#We are not routing to the Chat 
@app.route('/chat', methods=['GET', 'POST'])
def chat():

    print("Request data:", request.get_data(as_text=True))
    
    if request.method == 'GET':
        return jsonify({"message": "Hello from Flask!"}), 200
    
    if request.method == 'POST':
        try:
            data = request.get_json(force=True)
            print("Parsed JSON data:", data)
            
            if not data:
                return jsonify({"error": "No JSON data provided"}), 400

            message = data.get("message", "")
            user_id = data.get("userId", "")
            conversation_id = data.get("conversationId", "")

            # Call OpenAI API
            response = client.chat.completions.create(
                model="gpt-4",  # or "gpt-3.5-turbo" depending on your preference
                messages=[
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user", "content": message}
                ],
            )

            ai_response = response.choices[0].message.content
            print(ai_response)

            return jsonify({
                "response": ai_response,
                "userId": user_id,
                "conversationId": conversation_id
            }), 200

        except Exception as e:
            print(f"Error processing POST request: {str(e)}")
            return jsonify({"error": str(e)}), 500

    return jsonify({"error": "Method not allowed"}), 405


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
   
   
