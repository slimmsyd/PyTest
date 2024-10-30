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
CORS(app, resources={r"/*": {"origins": "http://localhost:3000"}})
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
    
    
def safe_makedirs(path, mode=0o777, exist_ok=True):
    """
    Create a directory if it doesn't exist, with enhanced error handling and logging.

    :param path: The directory path to create.
    :param mode: The mode (permissions) to set for the directory.
    :param exist_ok: If True, do not raise an exception if the directory already exists.
    """
    try:
        os.makedirs(path, mode=mode, exist_ok=exist_ok)
        logging.info(f"Directory created: {path}")
    except OSError as e:
        if not os.path.isdir(path):
            logging.error(f"Failed to create directory: {path}. Error: {e}")
            raise
        else:
            logging.info(f"Directory already exists: {path}")
    

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


# Function to convert an image to black and white
def convert_to_black_and_white(image):
    grayscale_image = image.convert('L')
    threshold = 128  # Adjust this threshold as needed
    bw_image = grayscale_image.point(lambda p: p > threshold and 255)
    return bw_image

# Function to convert JPG to SVG and upscale
def jpg_to_svg_and_upscale(jpg_filepath, output_dir):
    svg_filename = f"{Path(jpg_filepath).stem}.svg"
    svg_filepath = os.path.join(output_dir, svg_filename)

    # Open and convert the JPG image to black and white
    with Image.open(jpg_filepath) as img:
        bw_image = convert_to_black_and_white(img)
        pbm_filepath = jpg_filepath.rsplit('.', 1)[0] + '.pbm'
        bw_image.save(pbm_filepath)

    # Ensure the output directory exists
    safe_makedirs(output_dir)

    try:
        # Use potrace to convert the PBM to SVG
        subprocess.run(['potrace', '-s', pbm_filepath, '-o', svg_filepath], check=True)
        os.remove(pbm_filepath)  # Remove the temporary PBM file
        return svg_filepath
    except subprocess.CalledProcessError as e:
        print(f"Potrace returned a non-zero exit status: {e}")
        return None

# Function to sanitize text
def sanitize_text(text):
    replacements = {
        '\u201c': '"', '\u201d': '"',
        '\u2018': "'", '\u2019': "'",
        '\u2013': '-', '\u2014': '-',
        # Add more replacements as needed
    }
    for original, replacement in replacements.items():
        text = text.replace(original, replacement)
    return text

# Define the PDF class
class PDF(FPDF):
    def __init__(self, orientation='P', unit='mm', format='A4'):
        super().__init__(orientation, unit, format)
        self.background_image = None
        self.logo_image = None
        self.set_left_margin(35)
        self.set_top_margin(40)
        self.set_auto_page_break(auto=True, margin=10)

    def add_page(self, orientation=''):
        super().add_page(orientation=orientation)
        if self.background_image:
            self.image(self.background_image, x=0, y=0, w=self.w, h=self.h)
        if self.logo_image:
            # Calculate the logo size and position
            logo_max_width = 50  # Maximum width for the logo
            logo_max_height = 50  # Maximum height for the logo

            with Image.open(self.logo_image) as img:
                logo_width, logo_height = img.size
                aspect_ratio = logo_width / logo_height

                if logo_width > logo_max_width:
                    logo_width = logo_max_width
                    logo_height = logo_width / aspect_ratio

                if logo_height > logo_max_height:
                    logo_height = logo_max_height
                    logo_width = logo_height * aspect_ratio

                # Center the logo horizontally and position it
                logo_x = (self.w - logo_width) / 2
                logo_y = 20  # Adjust this value to bring the logo down or up

                self.image(self.logo_image, x=logo_x, y=logo_y, w=logo_width, h=logo_height)

    def header(self):
        self.set_y(65)  # Adjust this value to position text under the logo


# Function to upscale the image
def upscale_image(image_path, scale_factor):
    # Open the image file
    with Image.open(image_path) as img:
        # Calculate new dimensions
        new_width = int(img.width * scale_factor)
        new_height = int(img.height * scale_factor)
        
        # Resize the image
        upscaled_image = img.resize((new_width, new_height), Image.LANCZOS)
        
        # Save the upscaled image to a new file
        upscaled_image_path = os.path.splitext(image_path)[0] + '_upscaled.png'
        upscaled_image.save(upscaled_image_path)
        
        return upscaled_image_path
    
    
##Generating PDF code 
def generate_pdf(content, filename, background_image=None, logo_image=None):
    pdf = PDF()

    # Set background and logo if provided
    pdf.background_image = background_image
    pdf.logo_image = logo_image

    pdf.add_page()
    pdf.set_font("Arial", size=12)
    pdf.set_auto_page_break(auto=True, margin=15)

    lines = content.split('\n')
    for line in lines:
        line = sanitize_text(line)
        if pdf.get_y() > 240:
            pdf.add_page()
        if "**" in line:
            line = line.replace("**", "")
            pdf.set_font("Arial", style='B', size=12)
            pdf.multi_cell(0, 10, txt=line, align="L")
            pdf.set_font("Arial", size=12)
        else:
            pdf.multi_cell(0, 10, txt=line, align="L")

    # Save the PDF to the specified filename
    pdf.output(filename)
    
 # Separate route decorator and function
@app.route('/generate_pdf', methods=['POST'])
def generate_pdf_endpoint():
    try:
        # Get form data
        filename = request.form.get('filename', 'output.pdf')
        background_image = request.form.get('background_image')
        prompt = request.form.get('content', '')
        
        # Handle logo file upload
        logo_image_path = None
        if 'logo_image' in request.files:
            logo_file = request.files['logo_image']
            if logo_file.filename:
                # Create the logos directory if it doesn't exist
                logos_dir = os.path.join(current_app.root_path, 'public', 'images', 'logos')
                safe_makedirs(logos_dir)
                
                # Secure the filename and save the file
                secure_name = secure_filename(logo_file.filename)
                logo_image_path = os.path.join(logos_dir, secure_name)
                logo_file.save(logo_image_path)

        # Convert relative paths to absolute paths within your project directory
        if background_image:
            background_image = os.path.join(current_app.root_path, background_image)
            if not os.path.exists(background_image):
                return jsonify({'error': f'Background image not found: {background_image}'}), 404

        # Create output directory if it doesn't exist
        output_dir = os.path.join(current_app.root_path, 'generated_pdfs')
        safe_makedirs(output_dir)
        output_path = os.path.join(output_dir, filename)

        # Generate content using ChatGPT
        response = client.chat.completions.create(
            model="gpt-4",
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": f"Generate content for a PDF on the topic: {prompt}"}
            ],
        )
        content = response.choices[0].message.content

        # Generate PDF with absolute paths
        generate_pdf(content, output_path, background_image, logo_image_path)
        
        # Clean up the temporary logo file if it was created
        if logo_image_path and os.path.exists(logo_image_path):
            os.remove(logo_image_path)
            
        return send_file(output_path, as_attachment=True)
        
    except Exception as e:
        print(f"Error during PDF generation: {str(e)}")
        # Clean up any temporary files in case of error
        if logo_image_path and os.path.exists(logo_image_path):
            os.remove(logo_image_path)
        return jsonify({'error': f'Failed to generate PDF: {str(e)}'}), 500


def allowedFile(filename):
       return '.' in filename and \
              filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS
              
def generate_pdf_from_data(pdf_data):
    # Specify the directory to save PDFs
    output_dir = 'pdf_collection'  # Change this to your desired directory
    safe_makedirs(output_dir)  # Create the directory if it doesn't exist

    print("pdf_data:", pdf_data)
    filename = pdf_data.get('filename', 'output.pdf')
    background_image = pdf_data.get('background_image')
    logo_image = pdf_data.get('logo_image')
    prompt = pdf_data.get('content', '')

    # Check if the background image is a PNG, JPEG, or JPG file
    if background_image and not (background_image.lower().endswith('.png') or 
                                 background_image.lower().endswith('.jpg') or 
                                 background_image.lower().endswith('.jpeg')):
        return jsonify({'error': 'Background image must be a PNG, JPEG, or JPG file.'}), 400

    # Update the filename to include the output directory
    output_filepath = os.path.join(output_dir, filename)

    try:
        # Generate content using ChatGPT
        response = client.chat.completions.create(
            model="gpt-4",
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": f"Generate content for a PDF on the topic: {prompt}"}
            ],
        )
        content = response.choices[0].message.content

        # Generate PDF and save it to the specified directory
        generate_pdf(content, output_filepath, background_image, logo_image)

        # Return the file path for the generated PDF
        return output_filepath  # Return the file path as a string
    except Exception as e:
        print(f"Error during PDF generation: {str(e)}")  # Log the error
        return jsonify({'error': f'Failed to generate PDF: {str(e)}'}), 500       
    
    
 #removing the Background
 # Function to process images (e.g., upscale, remove background)
@app.route('/process_image', methods=['POST'])
def process_image():
    # Step 1: Log the incoming request files
    print("Request files:", request.files)  
    
    # Step 2: Ensure an image file is provided
    if 'file' not in request.files:
        return jsonify({"error": "No image file provided"}), 400

    image_file = request.files['file']
    if image_file.filename == '':
        return jsonify({"error": "No selected file"}), 400

    # Step 3: Define the output directory
    output_dir = 'outputImages'
    safe_makedirs(output_dir)

    # Step 4: Process the image (e.g., save it)
    try:
        # Save the original image to the output directory
        output_path = os.path.join(output_dir, secure_filename(image_file.filename))
        image_file.save(output_path)

        # Step 5: Remove the background from the image
        with open(output_path, 'rb') as input_file:
            input_image = input_file.read()
            output_image = remove(input_image)  # Remove background

        # Save the processed image with background removed
        bg_removed_path = os.path.join(output_dir, 'bg_removed_' + secure_filename(image_file.filename))
        with open(bg_removed_path, 'wb') as output_file:
            output_file.write(output_image)

        # Step 6: Upscale the image
        upscaled_image_path = upscale_image(bg_removed_path, scale_factor=3)  # You can adjust the scale factor

        # Step 7: Generate the URL to access the upscaled image
        upscaled_image_url = url_for('display_image', filename=os.path.basename(upscaled_image_path), _external=True)

        # Step 8: Return the output directory and image URL
        return jsonify({
            "message": "Image processed, background removed, and upscaled successfully.",
            "output_directory": output_dir,
            "image_url": upscaled_image_url
        }), 200

    except Exception as e:
        print(f"Error processing image: {str(e)}")
        return jsonify({"error": str(e)}), 500
    
        

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
   
   
