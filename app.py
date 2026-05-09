<<<<<<< HEAD
from flask import Flask, render_template, request, redirect, url_for, flash, session, jsonify
from flask_mysqldb import MySQL
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename
import os
import pickle
import numpy as np
from PIL import Image
import tensorflow as tf
from tensorflow.keras.applications.densenet import preprocess_input
import cv2

app = Flask(__name__)
app.secret_key = 'your_secret_key_here'

# MySQL configurations
app.config['MYSQL_HOST'] = 'localhost'
app.config['MYSQL_USER'] = 'root'
app.config['MYSQL_PASSWORD'] = ''
app.config['MYSQL_DB'] = 'plant_disease_detection'

mysql = MySQL(app)

# Upload configuration
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
UPLOAD_FOLDER = os.path.join(BASE_DIR, 'static', 'uploads')
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif'}
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

# Create upload folder if not exists
os.makedirs(UPLOAD_FOLDER, exist_ok=True)


# Load the trained model
BASE_DIR = os.path.dirname(os.path.abspath(__file__))

try:
    model_path = os.path.join(BASE_DIR, 'model', 'xgb_densenet121_model.pkl')
    with open(model_path, 'rb') as f:
        model = pickle.load(f)
    print("Model loaded successfully")
except Exception as e:
    print(f"Error loading model: {e}")
    model = None

# Class labels
CLASS_LABELS = [
    'Apple___Apple_scab', 'Apple___Black_rot', 'Apple___Cedar_apple_rust', 'Apple___healthy',
    'Blueberry___healthy',
    'Cherry_(including_sour)___Powdery_mildew', 'Cherry_(including_sour)___healthy',
    'Corn_(maize)___Cercospora_leaf_spot_Gray_leaf_spot', 'Corn_(maize)___Common_rust', 
    'Corn_(maize)___Northern_Leaf_Blight', 'Corn_(maize)___healthy',
    'Grape___Black_rot', 'Grape___Esca_(Black_Measles)', 'Grape___Leaf_blight_(Isariopsis_Leaf_Spot)', 'Grape___healthy',
    'Orange___Haunglongbing_(Citrus_greening)',
    'Peach___Bacterial_spot', 'Peach___healthy',
    'Pepper,_bell___Bacterial_spot', 'Pepper,_bell___healthy',
    'Potato___Early_blight', 'Potato___Late_blight', 'Potato___healthy',
    'Raspberry___healthy',
    'Soybean___healthy',
    'Squash___Powdery_mildew',
    'Strawberry___Leaf_scorch', 'Strawberry___healthy',
    'Tomato___Bacterial_spot', 'Tomato___Early_blight', 'Tomato___Late_blight', 'Tomato___Leaf_Mold',
    'Tomato___Septoria_leaf_spot', 'Tomato___Spider_mites_Two-spotted_spider_mite', 'Tomato___Target_Spot',
    'Tomato___Tomato_mosaic_virus', 'Tomato___Tomato_Yellow_Leaf_Curl_Virus', 'Tomato___healthy'
]

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def preprocess_image(image_path):
    """Load → resize → DenseNet-preprocess → add batch dim (once)"""
    try:
        img = Image.open(image_path).convert('RGB')
        img = img.resize((224, 224))                 # DenseNet expects 224
        img_array = np.array(img)                    # (224, 224, 3)
        img_array = preprocess_input(img_array)      # DenseNet scaling
        img_array = np.expand_dims(img_array, axis=0)  # (1, 224, 224, 3)
        return img_array
    except Exception as e:
        print(f"Error preprocessing image: {e}")
        return None

@app.route('/')
def home():
    if 'user_id' in session:
        return render_template('home.html')
    return render_template('home.html')

@app.route('/about')
def about():
    return render_template('about.html')



@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        data = request.get_json()  # ← Get JSON data
        
        if not data:
            return jsonify({'success': False, 'message': 'Invalid JSON'}), 400

        username = data.get('username')
        email = data.get('email')
        password = data.get('password')
        confirm_password = data.get('confirm_password')

        # Validate passwords match
        if password != confirm_password:
            return jsonify({'success': False, 'message': 'Passwords do not match'}), 400

        hashed_password = generate_password_hash(password)

        try:
            cur = mysql.connection.cursor()
            cur.execute("SELECT * FROM users WHERE username = %s OR email = %s", (username, email))
            if cur.fetchone():
                cur.close()
                return jsonify({'success': False, 'message': 'Username or email already exists!'}), 400

            cur.execute("INSERT INTO users (username, email, password) VALUES (%s, %s, %s)", 
                       (username, email, hashed_password))
            mysql.connection.commit()
            cur.close()

            return jsonify({'success': True, 'message': 'Registration successful! Please login.'})

        except Exception as e:
            print(f"Database error: {e}")
            return jsonify({'success': False, 'message': 'Registration failed. Try again.'}), 500

    return render_template('register.html')


@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        data = request.get_json()
        if not data:
            return jsonify({'success': False, 'message': 'No data received'}), 400

        username = data.get('username')
        password = data.get('password')

        if not username or not password:
            return jsonify({'success': False, 'message': 'All fields are required'}), 400

        cur = mysql.connection.cursor()
        cur.execute("SELECT id, username, password FROM users WHERE username = %s", (username,))
        user = cur.fetchone()
        cur.close()

        if user and check_password_hash(user[2], password):
            session['user_id'] = user[0]
            session['username'] = user[1]
            return jsonify({'success': True, 'message': 'Login successful!'})
        else:
            return jsonify({'success': False, 'message': 'Invalid credentials'}), 401

    return render_template('login.html')

@app.route('/prediction')
def input_page():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    return render_template('prediction.html') 

DISEASE_GUIDELINES = {
    'Apple___Apple_scab': {
        'prevention': "Prevent Apple scab by choosing resistant apple varieties, pruning infected branches, and removing fallen leaves. Avoid overhead irrigation and water in the morning.",
        'medicines': "Fungicides containing copper, chlorothalonil, or myclobutanil are effective for controlling Apple Scab.",
        'fertilizers': [
            {"name": "Miracle-Gro Water Soluble All Purpose Plant Food", "link": "https://www.amazon.com/dp/B0000DG1PK"},
            {"name": "Jobe's Organics All Purpose Fertilizer", "link": "https://www.amazon.com/dp/B00VXQT7IE"}
        ]
    },
    'Apple___Black_rot': {
        'prevention': "Prune infected branches, remove fallen debris, and improve air circulation around the tree. Avoid planting in damp conditions.",
        'medicines': "Use fungicides like thiophanate-methyl, azoxystrobin, or copper-based treatments.",
        'fertilizers': [
            {"name": "Dr. Earth Organic 5 Tomato, Vegetable & Herb Fertilizer", "link": "https://www.amazon.com/dp/B000A7C9Z6"},
            {"name": "Espoma Organic All Purpose Plant Food", "link": "https://www.amazon.com/dp/B000P6GLK0"}
        ]
    },
    'Apple___Cedar_apple_rust': {
        'prevention': "Remove cedar trees from around apple trees, as they are the alternate host for this disease. Prune affected branches.",
        'medicines': "Apply fungicides containing myclobutanil or sulfur at bud break to prevent infection.",
        'fertilizers': [
            {"name": "Miracle-Gro Shake 'n Feed Flowering Trees and Shrubs Plant Food", "link": "https://www.amazon.com/dp/B0009QFHKC"},
            {"name": "Neptune's Harvest Organic Fish & Seaweed Fertilizer", "link": "https://www.amazon.com/dp/B001D8H2X4"}
        ]
    },
    'Apple___healthy': {
        'prevention': "Regularly prune and maintain apple trees to ensure good airflow and avoid diseases.",
        'medicines': "No treatments are needed for healthy plants.",
        'fertilizers': [
            {"name": "Miracle-Gro Water Soluble All Purpose Plant Food", "link": "https://www.amazon.com/dp/B0000DG1PK"},
            {"name": "Jobe's Organics All Purpose Fertilizer", "link": "https://www.amazon.com/dp/B00VXQT7IE"}
        ]
    },
    'Blueberry___healthy': {
        'prevention': "Ensure good soil drainage and avoid overwatering. Regularly prune to remove dead wood.",
        'medicines': "No treatments needed for healthy plants.",
        'fertilizers': [
            {"name": "Miracle-Gro Water Soluble Azalea, Camellia, Rhododendron Plant Food", "link": "https://www.amazon.com/dp/B0002IFJ7Q"},
            {"name": "Dr. Earth Organic 5 Tomato, Vegetable & Herb Fertilizer", "link": "https://www.amazon.com/dp/B000A7C9Z6"}
        ]
    },
    'Cherry_(including_sour)___Powdery_mildew': {
        'prevention': "Ensure proper spacing to allow airflow, prune infected leaves, and avoid overhead watering.",
        'medicines': "Use fungicides such as sulfur or myclobutanil for controlling Powdery mildew.",
        'fertilizers': [
            {"name": "Miracle-Gro Shake 'n Feed Flowering Trees and Shrubs Plant Food", "link": "https://www.amazon.com/dp/B0009QFHKC"},
            {"name": "Jobe's Organics Fertilizer Spikes for Flowering Trees", "link": "https://www.amazon.com/dp/B00V9WFT0C"}
        ]
    },
    'Cherry_(including_sour)___healthy': {
        'prevention': "Maintain tree health with regular pruning, and ensure soil is well-drained.",
        'medicines': "No treatments needed for healthy plants.",
        'fertilizers': [
            {"name": "Jobe's Organics All Purpose Fertilizer", "link": "https://www.amazon.com/dp/B00VXQT7IE"},
            {"name": "Dr. Earth Organic 5 Tomato, Vegetable & Herb Fertilizer", "link": "https://www.amazon.com/dp/B000A7C9Z6"}
        ]
    },
    'Corn_(maize)___Cercospora_leaf_spot_Gray_leaf_spot': {
        'prevention': "Practice crop rotation, use resistant varieties, and ensure proper spacing between plants.",
        'medicines': "Use fungicides like azoxystrobin or chlorothalonil for controlling gray leaf spot.",
        'fertilizers': [
            {"name": "Scotts Turf Builder Lawn Food", "link": "https://www.amazon.com/dp/B0002Y0QZS"},
            {"name": "Miracle-Gro Water Soluble All Purpose Plant Food", "link": "https://www.amazon.com/dp/B0000DG1PK"}
        ]
    },
    'Corn_(maize)___Common_rust': {
        'prevention': "Rotate crops to avoid rust buildup and remove infected leaves.",
        'medicines': "Apply fungicides containing chlorothalonil or tebuconazole for rust control.",
        'fertilizers': [
            {"name": "Miracle-Gro Water Soluble All Purpose Plant Food", "link": "https://www.amazon.com/dp/B0000DG1PK"},
            {"name": "Jobe's Organics Vegetable & Tomato Fertilizer", "link": "https://www.amazon.com/dp/B00V9WFT0C"}
        ]
    },
    'Corn_(maize)___Northern_Leaf_Blight': {
        'prevention': "Avoid planting in high-moisture areas. Use resistant corn varieties.",
        'medicines': "Use fungicides like propiconazole or azoxystrobin to manage Northern leaf blight.",
        'fertilizers': [
            {"name": "Miracle-Gro Water Soluble All Purpose Plant Food", "link": "https://www.amazon.com/dp/B0000DG1PK"},
            {"name": "Scotts Turf Builder Lawn Food", "link": "https://www.amazon.com/dp/B0002Y0QZS"}
        ]
    },
    'Corn_(maize)___healthy': {
        'prevention': "Healthy corn should have sufficient spacing, water, and regular pest management.",
        'medicines': "No treatments needed for healthy plants.",
        'fertilizers': [
            {"name": "Miracle-Gro Water Soluble All Purpose Plant Food", "link": "https://www.amazon.com/dp/B0000DG1PK"},
            {"name": "Jobe's Organics All Purpose Fertilizer", "link": "https://www.amazon.com/dp/B00VXQT7IE"}
        ]
    },
    'Grape___Black_rot': {
        'prevention': "Remove infected leaves and grapes, and improve air circulation. Avoid overhead irrigation.",
        'medicines': "Use copper-based fungicides or thiophanate-methyl to control Black rot.",
        'fertilizers': [
            {"name": "Miracle-Gro Shake 'n Feed Flowering Trees and Shrubs Plant Food", "link": "https://www.amazon.com/dp/B0009QFHKC"},
            {"name": "Neptune's Harvest Organic Fish & Seaweed Fertilizer", "link": "https://www.amazon.com/dp/B001D8H2X4"}
        ]
    },
    'Grape___Esca_(Black_Measles)': {
        'prevention': "Prune infected parts and avoid watering on leaves.",
        'medicines': "Fungicides containing pyraclostrobin or boscalid can help control Esca.",
        'fertilizers': [
            {"name": "Dr. Earth Organic 5 Tomato, Vegetable & Herb Fertilizer", "link": "https://www.amazon.com/dp/B000A7C9Z6"},
            {"name": "Jobe's Organics Vegetable & Tomato Fertilizer", "link": "https://www.amazon.com/dp/B00V9WFT0C"}
        ]
    },
    'Grape___Leaf_blight_(Isariopsis_Leaf_Spot)': {
        'prevention': "Remove fallen leaves, avoid overhead watering, and ensure proper airflow.",
        'medicines': "Use copper-based fungicides or myclobutanil.",
        'fertilizers': [
            {"name": "Scotts Turf Builder Lawn Food", "link": "https://www.amazon.com/dp/B0002Y0QZS"},
            {"name": "Jobe's Organics Vegetable & Tomato Fertilizer", "link": "https://www.amazon.com/dp/B00V9WFT0C"}
        ]
    },
    'Grape___healthy': {
        'prevention': "Keep grapevines healthy by pruning, avoiding water stress, and protecting against pests.",
        'medicines': "No treatments needed for healthy plants.",
        'fertilizers': [
            {"name": "Miracle-Gro Shake 'n Feed Flowering Trees and Shrubs Plant Food", "link": "https://www.amazon.com/dp/B0009QFHKC"},
            {"name": "Neptune's Harvest Organic Fish & Seaweed Fertilizer", "link": "https://www.amazon.com/dp/B001D8H2X4"}
        ]
    },
    'Orange___Haunglongbing_(Citrus_greening)': {
        'prevention': "Remove infected trees and control the psyllid vector spreading the disease.",
        'medicines': "No cure for Huanglongbing, but using systemic insecticides may control the psyllid vector.",
        'fertilizers': [
            {"name": "Miracle-Gro Shake 'n Feed Citrus, Avocado, & Mango Food", "link": "https://www.amazon.com/dp/B000RHX97S"},
            {"name": "Jobe's Organics Citrus Fertilizer", "link": "https://www.amazon.com/dp/B00T9RB5MA"}
        ]
    },
    'Peach___Bacterial_spot': {
        'prevention': "Plant resistant varieties, prune infected branches, remove fallen debris, and avoid overhead irrigation to improve air circulation.",
        'medicines': "Use copper-based bactericides or oxytetracycline for control.",
        'fertilizers': [
            {"name": "Farmer's Secret Fruit Tree Booster Fertilizer", "link": "https://www.amazon.com/dp/B0CP34NR8H"},
            {"name": "Fruit Tree Fertilizer for All Fruit Trees Peach, Apple, and Pear", "link": "https://www.amazon.com/dp/B0C73RMK5D"}
        ]
    },
    'Peach___healthy': {
        'prevention': "Maintain proper pruning, watering, soil drainage, and pest monitoring for healthy peach trees.",
        'medicines': "No treatments needed for healthy plants.",
        'fertilizers': [
            {"name": "Farmer's Secret Fruit Tree Booster Fertilizer", "link": "https://www.amazon.com/dp/B0CP34NR8H"},
            {"name": "Fruit Tree Fertilizer for All Fruit Trees Peach, Apple, and Pear", "link": "https://www.amazon.com/dp/B0C73RMK5D"}
        ]
    },
    'Pepper,_bell___Bacterial_spot': {
        'prevention': "Use resistant varieties, pathogen-free seeds and transplants, practice crop rotation, and avoid overhead watering.",
        'medicines': "Apply copper-based bactericides, possibly combined with mancozeb or Actigard.",
        'fertilizers': [
            {"name": "Big A Pepper Fertilizer", "link": "https://www.amazon.com/dp/B0BCXWDPLF"},
            {"name": "Greenway Biotech Pepper & Herb Fertilizer", "link": "https://www.amazon.com/dp/B0BTMNS7ZW"}
        ]
    },
    'Pepper,_bell___healthy': {
        'prevention': "Ensure good soil drainage, proper spacing, and regular pruning to maintain health.",
        'medicines': "No treatments needed for healthy plants.",
        'fertilizers': [
            {"name": "Big A Pepper Fertilizer", "link": "https://www.amazon.com/dp/B0BCXWDPLF"},
            {"name": "Greenway Biotech Pepper & Herb Fertilizer", "link": "https://www.amazon.com/dp/B0BTMNS7ZW"}
        ]
    },
    'Potato___Early_blight': {
        'prevention': "Practice crop rotation, use resistant varieties, remove plant debris, and avoid overhead irrigation.",
        'medicines': "Apply fungicides containing chlorothalonil or copper-based products.",
        'fertilizers': [
            {"name": "Old Cobblers Farm Wicked Growth Seed Potato Fertilizer", "link": "https://www.amazon.com/dp/B0F94FNNK8"},
            {"name": "Miracle-Gro Water Soluble All Purpose Plant Food", "link": "https://www.amazon.com/dp/B0000DG1PK"}
        ]
    },
    'Potato___Late_blight': {
        'prevention': "Use disease-free seed potatoes, destroy cull piles and volunteers, and practice crop rotation.",
        'medicines': "Apply fungicides like chlorothalonil or copper-based products preventatively.",
        'fertilizers': [
            {"name": "Old Cobblers Farm Wicked Growth Seed Potato Fertilizer", "link": "https://www.amazon.com/dp/B0F94FNNK8"},
            {"name": "Miracle-Gro Water Soluble All Purpose Plant Food", "link": "https://www.amazon.com/dp/B0000DG1PK"}
        ]
    },
    'Potato___healthy': {
        'prevention': "Maintain sufficient spacing, proper watering, and regular pest management for healthy potatoes.",
        'medicines': "No treatments needed for healthy plants.",
        'fertilizers': [
            {"name": "Old Cobblers Farm Wicked Growth Seed Potato Fertilizer", "link": "https://www.amazon.com/dp/B0F94FNNK8"},
            {"name": "Miracle-Gro Water Soluble All Purpose Plant Food", "link": "https://www.amazon.com/dp/B0000DG1PK"}
        ]
    },
    'Raspberry___healthy': {
        'prevention': "Ensure good soil drainage, regular pruning to remove dead wood, and avoid overwatering.",
        'medicines': "No treatments needed for healthy plants.",
        'fertilizers': [
            {"name": "Down To Earth Organic Acid Mix", "link": "https://www.amazon.com/dp/B011L3T10E"},
            {"name": "Espoma Organic Berry-Tone", "link": "https://www.amazon.com/dp/B08DYDS1GZ"}
        ]
    },
    'Soybean___healthy': {
        'prevention': "Maintain good soil drainage, practice crop rotation, and ensure proper spacing.",
        'medicines': "No treatments needed for healthy plants.",
        'fertilizers': [
            {"name": "Walt's Organic Soy Bean Meal", "link": "https://www.amazon.com/dp/B00RZR54D4"},
            {"name": "Supply Solutions 7-0-26 Organic Fertilizer", "link": "https://www.amazon.com/dp/B0CNBNQD8K"}
        ]
    },
    'Squash___Powdery_mildew': {
        'prevention': "Ensure good air circulation by proper spacing and pruning, avoid overhead watering, and plant resistant varieties.",
        'medicines': "Use fungicides containing sulfur or bicarbonate for control.",
        'fertilizers': [
            {"name": "Pumpkin Fertilizer Complete Liquid", "link": "https://www.amazon.com/dp/B0DQ85JPJT"},
            {"name": "Pumpkin Juice 11-8-5 Foliar Liquid Fertilizer", "link": "https://www.amazon.com/dp/B07GSGV18Z"}
        ]
    },
    'Strawberry___Leaf_scorch': {
        'prevention': "Use resistant varieties, improve air circulation, avoid overhead irrigation, and remove infected debris.",
        'medicines': "Apply fungicides like thiophanate-methyl or copper-based products.",
        'fertilizers': [
            {"name": "Espoma Organic Berry-Tone", "link": "https://www.amazon.com/dp/B08DYDS1GZ"},
            {"name": "Happy Strawberry Fertilizer", "link": "https://www.amazon.com/dp/B0DWVQ2J8W"}
        ]
    },
    'Strawberry___healthy': {
        'prevention': "Ensure good soil drainage, avoid overwatering, and regularly prune to remove dead leaves.",
        'medicines': "No treatments needed for healthy plants.",
        'fertilizers': [
            {"name": "Espoma Organic Berry-Tone", "link": "https://www.amazon.com/dp/B08DYDS1GZ"},
            {"name": "Happy Strawberry Fertilizer", "link": "https://www.amazon.com/dp/B0DWVQ2J8W"}
        ]
    },
    'Tomato___Bacterial_spot': {
        'prevention': "Use resistant varieties, pathogen-free seeds and transplants, practice crop rotation, and avoid overhead watering.",
        'medicines': "Apply copper-based bactericides, possibly combined with mancozeb or Actigard.",
        'fertilizers': [
            {"name": "Espoma Organic Tomato-Tone", "link": "https://www.amazon.com/dp/B01MAW3JYE"},
            {"name": "Dr. Earth Organic Tomato Fertilizer", "link": "https://www.amazon.com/dp/B01MXKBNGH"}
        ]
    },
    'Tomato___Early_blight': {
        'prevention': "Practice crop rotation, mulch soil to prevent splashing, stake plants for airflow, and use resistant varieties.",
        'medicines': "Apply fungicides containing chlorothalonil or copper-based products.",
        'fertilizers': [
            {"name": "Espoma Organic Tomato-Tone", "link": "https://www.amazon.com/dp/B01MAW3JYE"},
            {"name": "Dr. Earth Organic Tomato Fertilizer", "link": "https://www.amazon.com/dp/B01MXKBNGH"}
        ]
    },
    'Tomato___Late_blight': {
        'prevention': "Use resistant varieties, avoid overhead watering, remove plant debris, and ensure good airflow.",
        'medicines': "Apply fungicides like chlorothalonil or copper-based products preventatively.",
        'fertilizers': [
            {"name": "Espoma Organic Tomato-Tone", "link": "https://www.amazon.com/dp/B01MAW3JYE"},
            {"name": "Dr. Earth Organic Tomato Fertilizer", "link": "https://www.amazon.com/dp/B01MXKBNGH"}
        ]
    },
    'Tomato___Leaf_Mold': {
        'prevention': "Reduce humidity with good airflow and spacing, use drip irrigation, and remove lower leaves.",
        'medicines': "Apply fungicides containing chlorothalonil or copper.",
        'fertilizers': [
            {"name": "Espoma Organic Tomato-Tone", "link": "https://www.amazon.com/dp/B01MAW3JYE"},
            {"name": "Dr. Earth Organic Tomato Fertilizer", "link": "https://www.amazon.com/dp/B01MXKBNGH"}
        ]
    },
    'Tomato___Septoria_leaf_spot': {
        'prevention': "Practice crop rotation, remove plant debris, mulch to prevent splashing, and avoid overhead watering.",
        'medicines': "Apply fungicides containing chlorothalonil, mancozeb, or copper.",
        'fertilizers': [
            {"name": "Espoma Organic Tomato-Tone", "link": "https://www.amazon.com/dp/B01MAW3JYE"},
            {"name": "Dr. Earth Organic Tomato Fertilizer", "link": "https://www.amazon.com/dp/B01MXKBNGH"}
        ]
    },
    'Tomato___Spider_mites_Two-spotted_spider_mite': {
        'prevention': "Avoid dry, dusty conditions, use overhead watering to dislodge mites, and encourage natural predators.",
        'medicines': "Use insecticidal soaps, horticultural oils, or miticides like abamectin.",
        'fertilizers': [
            {"name": "Espoma Organic Tomato-Tone", "link": "https://www.amazon.com/dp/B01MAW3JYE"},
            {"name": "Dr. Earth Organic Tomato Fertilizer", "link": "https://www.amazon.com/dp/B01MXKBNGH"}
        ]
    },
    'Tomato___Target_Spot': {
        'prevention': "Improve air circulation, remove infected leaves, practice crop rotation, and avoid overhead watering.",
        'medicines': "Apply protectant fungicides like chlorothalonil or copper-based products.",
        'fertilizers': [
            {"name": "Espoma Organic Tomato-Tone", "link": "https://www.amazon.com/dp/B01MAW3JYE"},
            {"name": "Dr. Earth Organic Tomato Fertilizer", "link": "https://www.amazon.com/dp/B01MXKBNGH"}
        ]
    },
    'Tomato___Tomato_mosaic_virus': {
        'prevention': "Use resistant varieties, disinfect tools and hands, avoid tobacco products near plants, and use disease-free seeds.",
        'medicines': "No chemical treatments available; remove and destroy infected plants.",
        'fertilizers': [
            {"name": "Espoma Organic Tomato-Tone", "link": "https://www.amazon.com/dp/B01MAW3JYE"},
            {"name": "Dr. Earth Organic Tomato Fertilizer", "link": "https://www.amazon.com/dp/B01MXKBNGH"}
        ]
    },
    'Tomato___Tomato_Yellow_Leaf_Curl_Virus': {
        'prevention': "Use resistant varieties, control whiteflies with row covers or reflective mulches, and remove infected plants.",
        'medicines': "No cure for the virus; use insecticides to control whitefly vectors.",
        'fertilizers': [
            {"name": "Espoma Organic Tomato-Tone", "link": "https://www.amazon.com/dp/B01MAW3JYE"},
            {"name": "Dr. Earth Organic Tomato Fertilizer", "link": "https://www.amazon.com/dp/B01MXKBNGH"}
        ]
    },
    'Tomato___healthy': {
        'prevention': "Maintain good airflow with staking, avoid overhead watering, and practice crop rotation.",
        'medicines': "No treatments needed for healthy plants.",
        'fertilizers': [
            {"name": "Espoma Organic Tomato-Tone", "link": "https://www.amazon.com/dp/B01MAW3JYE"},
            {"name": "Dr. Earth Organic Tomato Fertilizer", "link": "https://www.amazon.com/dp/B01MXKBNGH"}
        ]
    }
}



@app.route('/predict', methods=['POST'])
def predict():
    if 'user_id' not in session:
        return jsonify({'error': 'Please login first'}), 401

    file = request.files.get('file')
    if not file or file.filename == '':
        return jsonify({'error': 'No file selected'}), 400

    if not allowed_file(file.filename):
        return jsonify({'error': 'Invalid file type'}), 400

    # ---- Save file ----
    filename = secure_filename(file.filename)
    filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
    file.save(filepath)

    # ---- Preprocess (returns (1,224,224,3)) ----
    processed = preprocess_image(filepath)
    if processed is None:
        return jsonify({'error': 'Image processing failed'}), 500

    if model is None:
        return jsonify({'error': 'Model not loaded'}), 500

    try:
        # ---- Feature extractor (cached globally for speed) ----
        if not hasattr(app, 'densenet_extractor'):
            from tensorflow.keras.applications import DenseNet121
            app.densenet_extractor = DenseNet121(
                weights='imagenet', include_top=False, pooling='avg'
            )
            print("DenseNet121 extractor ready")
        extractor = app.densenet_extractor

        features = extractor.predict(processed, verbose=0)   # (1, 1024)

        # ---- XGBoost prediction ----
        pred_idx = int(model.predict(features)[0])          # Python int
        proba = model.predict_proba(features)[0]
        max_proba = np.max(proba)

        # ---- Confidence threshold check for invalid images ----
        CONFIDENCE_THRESHOLD = 0.5  # 50% threshold
        if max_proba < CONFIDENCE_THRESHOLD:
            predicted_class = "Unknown"
            confidence = 0.0
        else:
            predicted_class = CLASS_LABELS[pred_idx]
            confidence = float(max_proba) * 100

        # ---- DB save ----
        cur = mysql.connection.cursor()
        cur.execute(
            """INSERT INTO predictions 
               (user_id, image_path, prediction_result, confidence) 
               VALUES (%s, %s, %s, %s)""",
            (session['user_id'], filename, predicted_class, confidence)
        )
        mysql.connection.commit()
        cur.close()

        # ---- Format result ----
        if predicted_class == "Unknown":
            plant = "Unknown"
            disease = "Invalid image - Please upload a clear plant leaf image"
            status = "Invalid"
            prevention = "Please upload a valid plant leaf image for accurate detection."
            medicines = "N/A"
            fertilizers_list = []
        else:
            parts = predicted_class.split('___')
            plant = parts[0].replace('_', ' ')
            disease = parts[1].replace('_', ' ') if len(parts) > 1 else "Unknown"
            status = "Healthy" if "healthy" in disease.lower() else "Diseased"

            # Fetch disease guidelines (prevention, medicines, and fertilizers)
            guidelines = DISEASE_GUIDELINES.get(predicted_class, None)
            if guidelines:
                prevention = guidelines['prevention']
                medicines = guidelines['medicines']
                fertilizers = guidelines['fertilizers'] if isinstance(guidelines['fertilizers'], list) else []
            else:
                prevention = "No specific prevention guidelines found."
                medicines = "No specific medicines recommended."
                fertilizers = []

            # Construct the fertilizers list with name and purchase links
            fertilizers_list = []
            for fertilizer in fertilizers:
                fertilizers_list.append({
                    'name': fertilizer.get('name', 'N/A'),
                    'link': fertilizer.get('link', '#')
                })

        result = {
            'plant': plant,
            'disease': disease,
            'status': status,
            'confidence': round(confidence, 2),
            'image_path': url_for('static', filename='uploads/' + filename),
            'prevention': prevention,
            'medicines': medicines,
            'fertilizers': fertilizers_list
        }
        return jsonify(result)

    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({'error': 'Prediction failed'}), 500


@app.route('/history')
def history():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    
    cur = mysql.connection.cursor()
    cur.execute("""
        SELECT image_path, prediction_result, confidence, created_at 
        FROM predictions 
        WHERE user_id = %s 
        ORDER BY created_at DESC
    """, (session['user_id'],))
    
    predictions = cur.fetchall()
    cur.close()
    
    prediction_list = []
    for pred in predictions:
        if pred[1] == "Unknown":
            plant_name = "Unknown"
            disease_name = "Invalid image - Please upload a clear plant leaf image"
            status = "Invalid"
            conf = 0.0
        else:
            parts = pred[1].split('___')
            plant_name = parts[0].replace('_', ' ')
            disease_name = parts[1].replace('_', ' ') if len(parts) > 1 else "Unknown"
            status = "Healthy" if "healthy" in disease_name.lower() else "Diseased"
            conf = pred[2]
        
        prediction_list.append({
            'image_path': url_for('static', filename='uploads/' + pred[0]),
            'plant': plant_name,
            'disease': disease_name,
            'status': status,
            'confidence': round(conf, 2),
            'date': pred[3]
        })
    
    return render_template('history.html', predictions=prediction_list)

@app.route('/logout', methods=['GET', 'POST'])
def logout():
    session.clear()
    flash('You have been logged out!', 'info')
    return redirect(url_for('login'))

if __name__ == '__main__':
=======
from flask import Flask, render_template, request, redirect, url_for, flash, session, jsonify
from flask_mysqldb import MySQL
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename
import os
import pickle
import numpy as np
from PIL import Image
import tensorflow as tf
from tensorflow.keras.applications.densenet import preprocess_input
import cv2

app = Flask(__name__)
app.secret_key = 'your_secret_key_here'

# MySQL configurations
app.config['MYSQL_HOST'] = 'localhost'
app.config['MYSQL_USER'] = 'root'
app.config['MYSQL_PASSWORD'] = ''
app.config['MYSQL_DB'] = 'plant_disease_detection'

mysql = MySQL(app)

# Upload configuration
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
UPLOAD_FOLDER = os.path.join(BASE_DIR, 'static', 'uploads')
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif'}
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

# Create upload folder if not exists
os.makedirs(UPLOAD_FOLDER, exist_ok=True)


# Load the trained model
BASE_DIR = os.path.dirname(os.path.abspath(__file__))

try:
    model_path = os.path.join(BASE_DIR, 'model', 'xgb_densenet121_model.pkl')
    with open(model_path, 'rb') as f:
        model = pickle.load(f)
    print("Model loaded successfully")
except Exception as e:
    print(f"Error loading model: {e}")
    model = None

# Class labels
CLASS_LABELS = [
    'Apple___Apple_scab', 'Apple___Black_rot', 'Apple___Cedar_apple_rust', 'Apple___healthy',
    'Blueberry___healthy',
    'Cherry_(including_sour)___Powdery_mildew', 'Cherry_(including_sour)___healthy',
    'Corn_(maize)___Cercospora_leaf_spot_Gray_leaf_spot', 'Corn_(maize)___Common_rust', 
    'Corn_(maize)___Northern_Leaf_Blight', 'Corn_(maize)___healthy',
    'Grape___Black_rot', 'Grape___Esca_(Black_Measles)', 'Grape___Leaf_blight_(Isariopsis_Leaf_Spot)', 'Grape___healthy',
    'Orange___Haunglongbing_(Citrus_greening)',
    'Peach___Bacterial_spot', 'Peach___healthy',
    'Pepper,_bell___Bacterial_spot', 'Pepper,_bell___healthy',
    'Potato___Early_blight', 'Potato___Late_blight', 'Potato___healthy',
    'Raspberry___healthy',
    'Soybean___healthy',
    'Squash___Powdery_mildew',
    'Strawberry___Leaf_scorch', 'Strawberry___healthy',
    'Tomato___Bacterial_spot', 'Tomato___Early_blight', 'Tomato___Late_blight', 'Tomato___Leaf_Mold',
    'Tomato___Septoria_leaf_spot', 'Tomato___Spider_mites_Two-spotted_spider_mite', 'Tomato___Target_Spot',
    'Tomato___Tomato_mosaic_virus', 'Tomato___Tomato_Yellow_Leaf_Curl_Virus', 'Tomato___healthy'
]

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def preprocess_image(image_path):
    """Load → resize → DenseNet-preprocess → add batch dim (once)"""
    try:
        img = Image.open(image_path).convert('RGB')
        img = img.resize((224, 224))                 # DenseNet expects 224
        img_array = np.array(img)                    # (224, 224, 3)
        img_array = preprocess_input(img_array)      # DenseNet scaling
        img_array = np.expand_dims(img_array, axis=0)  # (1, 224, 224, 3)
        return img_array
    except Exception as e:
        print(f"Error preprocessing image: {e}")
        return None

@app.route('/')
def home():
    if 'user_id' in session:
        return render_template('home.html')
    return render_template('home.html')

@app.route('/about')
def about():
    return render_template('about.html')



@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        data = request.get_json()  # ← Get JSON data
        
        if not data:
            return jsonify({'success': False, 'message': 'Invalid JSON'}), 400

        username = data.get('username')
        email = data.get('email')
        password = data.get('password')
        confirm_password = data.get('confirm_password')

        # Validate passwords match
        if password != confirm_password:
            return jsonify({'success': False, 'message': 'Passwords do not match'}), 400

        hashed_password = generate_password_hash(password)

        try:
            cur = mysql.connection.cursor()
            cur.execute("SELECT * FROM users WHERE username = %s OR email = %s", (username, email))
            if cur.fetchone():
                cur.close()
                return jsonify({'success': False, 'message': 'Username or email already exists!'}), 400

            cur.execute("INSERT INTO users (username, email, password) VALUES (%s, %s, %s)", 
                       (username, email, hashed_password))
            mysql.connection.commit()
            cur.close()

            return jsonify({'success': True, 'message': 'Registration successful! Please login.'})

        except Exception as e:
            print(f"Database error: {e}")
            return jsonify({'success': False, 'message': 'Registration failed. Try again.'}), 500

    return render_template('register.html')


@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        data = request.get_json()
        if not data:
            return jsonify({'success': False, 'message': 'No data received'}), 400

        username = data.get('username')
        password = data.get('password')

        if not username or not password:
            return jsonify({'success': False, 'message': 'All fields are required'}), 400

        cur = mysql.connection.cursor()
        cur.execute("SELECT id, username, password FROM users WHERE username = %s", (username,))
        user = cur.fetchone()
        cur.close()

        if user and check_password_hash(user[2], password):
            session['user_id'] = user[0]
            session['username'] = user[1]
            return jsonify({'success': True, 'message': 'Login successful!'})
        else:
            return jsonify({'success': False, 'message': 'Invalid credentials'}), 401

    return render_template('login.html')

@app.route('/prediction')
def input_page():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    return render_template('prediction.html') 

DISEASE_GUIDELINES = {
    'Apple___Apple_scab': {
        'prevention': "Prevent Apple scab by choosing resistant apple varieties, pruning infected branches, and removing fallen leaves. Avoid overhead irrigation and water in the morning.",
        'medicines': "Fungicides containing copper, chlorothalonil, or myclobutanil are effective for controlling Apple Scab.",
        'fertilizers': [
            {"name": "Miracle-Gro Water Soluble All Purpose Plant Food", "link": "https://www.amazon.com/dp/B0000DG1PK"},
            {"name": "Jobe's Organics All Purpose Fertilizer", "link": "https://www.amazon.com/dp/B00VXQT7IE"}
        ]
    },
    'Apple___Black_rot': {
        'prevention': "Prune infected branches, remove fallen debris, and improve air circulation around the tree. Avoid planting in damp conditions.",
        'medicines': "Use fungicides like thiophanate-methyl, azoxystrobin, or copper-based treatments.",
        'fertilizers': [
            {"name": "Dr. Earth Organic 5 Tomato, Vegetable & Herb Fertilizer", "link": "https://www.amazon.com/dp/B000A7C9Z6"},
            {"name": "Espoma Organic All Purpose Plant Food", "link": "https://www.amazon.com/dp/B000P6GLK0"}
        ]
    },
    'Apple___Cedar_apple_rust': {
        'prevention': "Remove cedar trees from around apple trees, as they are the alternate host for this disease. Prune affected branches.",
        'medicines': "Apply fungicides containing myclobutanil or sulfur at bud break to prevent infection.",
        'fertilizers': [
            {"name": "Miracle-Gro Shake 'n Feed Flowering Trees and Shrubs Plant Food", "link": "https://www.amazon.com/dp/B0009QFHKC"},
            {"name": "Neptune's Harvest Organic Fish & Seaweed Fertilizer", "link": "https://www.amazon.com/dp/B001D8H2X4"}
        ]
    },
    'Apple___healthy': {
        'prevention': "Regularly prune and maintain apple trees to ensure good airflow and avoid diseases.",
        'medicines': "No treatments are needed for healthy plants.",
        'fertilizers': [
            {"name": "Miracle-Gro Water Soluble All Purpose Plant Food", "link": "https://www.amazon.com/dp/B0000DG1PK"},
            {"name": "Jobe's Organics All Purpose Fertilizer", "link": "https://www.amazon.com/dp/B00VXQT7IE"}
        ]
    },
    'Blueberry___healthy': {
        'prevention': "Ensure good soil drainage and avoid overwatering. Regularly prune to remove dead wood.",
        'medicines': "No treatments needed for healthy plants.",
        'fertilizers': [
            {"name": "Miracle-Gro Water Soluble Azalea, Camellia, Rhododendron Plant Food", "link": "https://www.amazon.com/dp/B0002IFJ7Q"},
            {"name": "Dr. Earth Organic 5 Tomato, Vegetable & Herb Fertilizer", "link": "https://www.amazon.com/dp/B000A7C9Z6"}
        ]
    },
    'Cherry_(including_sour)___Powdery_mildew': {
        'prevention': "Ensure proper spacing to allow airflow, prune infected leaves, and avoid overhead watering.",
        'medicines': "Use fungicides such as sulfur or myclobutanil for controlling Powdery mildew.",
        'fertilizers': [
            {"name": "Miracle-Gro Shake 'n Feed Flowering Trees and Shrubs Plant Food", "link": "https://www.amazon.com/dp/B0009QFHKC"},
            {"name": "Jobe's Organics Fertilizer Spikes for Flowering Trees", "link": "https://www.amazon.com/dp/B00V9WFT0C"}
        ]
    },
    'Cherry_(including_sour)___healthy': {
        'prevention': "Maintain tree health with regular pruning, and ensure soil is well-drained.",
        'medicines': "No treatments needed for healthy plants.",
        'fertilizers': [
            {"name": "Jobe's Organics All Purpose Fertilizer", "link": "https://www.amazon.com/dp/B00VXQT7IE"},
            {"name": "Dr. Earth Organic 5 Tomato, Vegetable & Herb Fertilizer", "link": "https://www.amazon.com/dp/B000A7C9Z6"}
        ]
    },
    'Corn_(maize)___Cercospora_leaf_spot_Gray_leaf_spot': {
        'prevention': "Practice crop rotation, use resistant varieties, and ensure proper spacing between plants.",
        'medicines': "Use fungicides like azoxystrobin or chlorothalonil for controlling gray leaf spot.",
        'fertilizers': [
            {"name": "Scotts Turf Builder Lawn Food", "link": "https://www.amazon.com/dp/B0002Y0QZS"},
            {"name": "Miracle-Gro Water Soluble All Purpose Plant Food", "link": "https://www.amazon.com/dp/B0000DG1PK"}
        ]
    },
    'Corn_(maize)___Common_rust': {
        'prevention': "Rotate crops to avoid rust buildup and remove infected leaves.",
        'medicines': "Apply fungicides containing chlorothalonil or tebuconazole for rust control.",
        'fertilizers': [
            {"name": "Miracle-Gro Water Soluble All Purpose Plant Food", "link": "https://www.amazon.com/dp/B0000DG1PK"},
            {"name": "Jobe's Organics Vegetable & Tomato Fertilizer", "link": "https://www.amazon.com/dp/B00V9WFT0C"}
        ]
    },
    'Corn_(maize)___Northern_Leaf_Blight': {
        'prevention': "Avoid planting in high-moisture areas. Use resistant corn varieties.",
        'medicines': "Use fungicides like propiconazole or azoxystrobin to manage Northern leaf blight.",
        'fertilizers': [
            {"name": "Miracle-Gro Water Soluble All Purpose Plant Food", "link": "https://www.amazon.com/dp/B0000DG1PK"},
            {"name": "Scotts Turf Builder Lawn Food", "link": "https://www.amazon.com/dp/B0002Y0QZS"}
        ]
    },
    'Corn_(maize)___healthy': {
        'prevention': "Healthy corn should have sufficient spacing, water, and regular pest management.",
        'medicines': "No treatments needed for healthy plants.",
        'fertilizers': [
            {"name": "Miracle-Gro Water Soluble All Purpose Plant Food", "link": "https://www.amazon.com/dp/B0000DG1PK"},
            {"name": "Jobe's Organics All Purpose Fertilizer", "link": "https://www.amazon.com/dp/B00VXQT7IE"}
        ]
    },
    'Grape___Black_rot': {
        'prevention': "Remove infected leaves and grapes, and improve air circulation. Avoid overhead irrigation.",
        'medicines': "Use copper-based fungicides or thiophanate-methyl to control Black rot.",
        'fertilizers': [
            {"name": "Miracle-Gro Shake 'n Feed Flowering Trees and Shrubs Plant Food", "link": "https://www.amazon.com/dp/B0009QFHKC"},
            {"name": "Neptune's Harvest Organic Fish & Seaweed Fertilizer", "link": "https://www.amazon.com/dp/B001D8H2X4"}
        ]
    },
    'Grape___Esca_(Black_Measles)': {
        'prevention': "Prune infected parts and avoid watering on leaves.",
        'medicines': "Fungicides containing pyraclostrobin or boscalid can help control Esca.",
        'fertilizers': [
            {"name": "Dr. Earth Organic 5 Tomato, Vegetable & Herb Fertilizer", "link": "https://www.amazon.com/dp/B000A7C9Z6"},
            {"name": "Jobe's Organics Vegetable & Tomato Fertilizer", "link": "https://www.amazon.com/dp/B00V9WFT0C"}
        ]
    },
    'Grape___Leaf_blight_(Isariopsis_Leaf_Spot)': {
        'prevention': "Remove fallen leaves, avoid overhead watering, and ensure proper airflow.",
        'medicines': "Use copper-based fungicides or myclobutanil.",
        'fertilizers': [
            {"name": "Scotts Turf Builder Lawn Food", "link": "https://www.amazon.com/dp/B0002Y0QZS"},
            {"name": "Jobe's Organics Vegetable & Tomato Fertilizer", "link": "https://www.amazon.com/dp/B00V9WFT0C"}
        ]
    },
    'Grape___healthy': {
        'prevention': "Keep grapevines healthy by pruning, avoiding water stress, and protecting against pests.",
        'medicines': "No treatments needed for healthy plants.",
        'fertilizers': [
            {"name": "Miracle-Gro Shake 'n Feed Flowering Trees and Shrubs Plant Food", "link": "https://www.amazon.com/dp/B0009QFHKC"},
            {"name": "Neptune's Harvest Organic Fish & Seaweed Fertilizer", "link": "https://www.amazon.com/dp/B001D8H2X4"}
        ]
    },
    'Orange___Haunglongbing_(Citrus_greening)': {
        'prevention': "Remove infected trees and control the psyllid vector spreading the disease.",
        'medicines': "No cure for Huanglongbing, but using systemic insecticides may control the psyllid vector.",
        'fertilizers': [
            {"name": "Miracle-Gro Shake 'n Feed Citrus, Avocado, & Mango Food", "link": "https://www.amazon.com/dp/B000RHX97S"},
            {"name": "Jobe's Organics Citrus Fertilizer", "link": "https://www.amazon.com/dp/B00T9RB5MA"}
        ]
    },
    'Peach___Bacterial_spot': {
        'prevention': "Plant resistant varieties, prune infected branches, remove fallen debris, and avoid overhead irrigation to improve air circulation.",
        'medicines': "Use copper-based bactericides or oxytetracycline for control.",
        'fertilizers': [
            {"name": "Farmer's Secret Fruit Tree Booster Fertilizer", "link": "https://www.amazon.com/dp/B0CP34NR8H"},
            {"name": "Fruit Tree Fertilizer for All Fruit Trees Peach, Apple, and Pear", "link": "https://www.amazon.com/dp/B0C73RMK5D"}
        ]
    },
    'Peach___healthy': {
        'prevention': "Maintain proper pruning, watering, soil drainage, and pest monitoring for healthy peach trees.",
        'medicines': "No treatments needed for healthy plants.",
        'fertilizers': [
            {"name": "Farmer's Secret Fruit Tree Booster Fertilizer", "link": "https://www.amazon.com/dp/B0CP34NR8H"},
            {"name": "Fruit Tree Fertilizer for All Fruit Trees Peach, Apple, and Pear", "link": "https://www.amazon.com/dp/B0C73RMK5D"}
        ]
    },
    'Pepper,_bell___Bacterial_spot': {
        'prevention': "Use resistant varieties, pathogen-free seeds and transplants, practice crop rotation, and avoid overhead watering.",
        'medicines': "Apply copper-based bactericides, possibly combined with mancozeb or Actigard.",
        'fertilizers': [
            {"name": "Big A Pepper Fertilizer", "link": "https://www.amazon.com/dp/B0BCXWDPLF"},
            {"name": "Greenway Biotech Pepper & Herb Fertilizer", "link": "https://www.amazon.com/dp/B0BTMNS7ZW"}
        ]
    },
    'Pepper,_bell___healthy': {
        'prevention': "Ensure good soil drainage, proper spacing, and regular pruning to maintain health.",
        'medicines': "No treatments needed for healthy plants.",
        'fertilizers': [
            {"name": "Big A Pepper Fertilizer", "link": "https://www.amazon.com/dp/B0BCXWDPLF"},
            {"name": "Greenway Biotech Pepper & Herb Fertilizer", "link": "https://www.amazon.com/dp/B0BTMNS7ZW"}
        ]
    },
    'Potato___Early_blight': {
        'prevention': "Practice crop rotation, use resistant varieties, remove plant debris, and avoid overhead irrigation.",
        'medicines': "Apply fungicides containing chlorothalonil or copper-based products.",
        'fertilizers': [
            {"name": "Old Cobblers Farm Wicked Growth Seed Potato Fertilizer", "link": "https://www.amazon.com/dp/B0F94FNNK8"},
            {"name": "Miracle-Gro Water Soluble All Purpose Plant Food", "link": "https://www.amazon.com/dp/B0000DG1PK"}
        ]
    },
    'Potato___Late_blight': {
        'prevention': "Use disease-free seed potatoes, destroy cull piles and volunteers, and practice crop rotation.",
        'medicines': "Apply fungicides like chlorothalonil or copper-based products preventatively.",
        'fertilizers': [
            {"name": "Old Cobblers Farm Wicked Growth Seed Potato Fertilizer", "link": "https://www.amazon.com/dp/B0F94FNNK8"},
            {"name": "Miracle-Gro Water Soluble All Purpose Plant Food", "link": "https://www.amazon.com/dp/B0000DG1PK"}
        ]
    },
    'Potato___healthy': {
        'prevention': "Maintain sufficient spacing, proper watering, and regular pest management for healthy potatoes.",
        'medicines': "No treatments needed for healthy plants.",
        'fertilizers': [
            {"name": "Old Cobblers Farm Wicked Growth Seed Potato Fertilizer", "link": "https://www.amazon.com/dp/B0F94FNNK8"},
            {"name": "Miracle-Gro Water Soluble All Purpose Plant Food", "link": "https://www.amazon.com/dp/B0000DG1PK"}
        ]
    },
    'Raspberry___healthy': {
        'prevention': "Ensure good soil drainage, regular pruning to remove dead wood, and avoid overwatering.",
        'medicines': "No treatments needed for healthy plants.",
        'fertilizers': [
            {"name": "Down To Earth Organic Acid Mix", "link": "https://www.amazon.com/dp/B011L3T10E"},
            {"name": "Espoma Organic Berry-Tone", "link": "https://www.amazon.com/dp/B08DYDS1GZ"}
        ]
    },
    'Soybean___healthy': {
        'prevention': "Maintain good soil drainage, practice crop rotation, and ensure proper spacing.",
        'medicines': "No treatments needed for healthy plants.",
        'fertilizers': [
            {"name": "Walt's Organic Soy Bean Meal", "link": "https://www.amazon.com/dp/B00RZR54D4"},
            {"name": "Supply Solutions 7-0-26 Organic Fertilizer", "link": "https://www.amazon.com/dp/B0CNBNQD8K"}
        ]
    },
    'Squash___Powdery_mildew': {
        'prevention': "Ensure good air circulation by proper spacing and pruning, avoid overhead watering, and plant resistant varieties.",
        'medicines': "Use fungicides containing sulfur or bicarbonate for control.",
        'fertilizers': [
            {"name": "Pumpkin Fertilizer Complete Liquid", "link": "https://www.amazon.com/dp/B0DQ85JPJT"},
            {"name": "Pumpkin Juice 11-8-5 Foliar Liquid Fertilizer", "link": "https://www.amazon.com/dp/B07GSGV18Z"}
        ]
    },
    'Strawberry___Leaf_scorch': {
        'prevention': "Use resistant varieties, improve air circulation, avoid overhead irrigation, and remove infected debris.",
        'medicines': "Apply fungicides like thiophanate-methyl or copper-based products.",
        'fertilizers': [
            {"name": "Espoma Organic Berry-Tone", "link": "https://www.amazon.com/dp/B08DYDS1GZ"},
            {"name": "Happy Strawberry Fertilizer", "link": "https://www.amazon.com/dp/B0DWVQ2J8W"}
        ]
    },
    'Strawberry___healthy': {
        'prevention': "Ensure good soil drainage, avoid overwatering, and regularly prune to remove dead leaves.",
        'medicines': "No treatments needed for healthy plants.",
        'fertilizers': [
            {"name": "Espoma Organic Berry-Tone", "link": "https://www.amazon.com/dp/B08DYDS1GZ"},
            {"name": "Happy Strawberry Fertilizer", "link": "https://www.amazon.com/dp/B0DWVQ2J8W"}
        ]
    },
    'Tomato___Bacterial_spot': {
        'prevention': "Use resistant varieties, pathogen-free seeds and transplants, practice crop rotation, and avoid overhead watering.",
        'medicines': "Apply copper-based bactericides, possibly combined with mancozeb or Actigard.",
        'fertilizers': [
            {"name": "Espoma Organic Tomato-Tone", "link": "https://www.amazon.com/dp/B01MAW3JYE"},
            {"name": "Dr. Earth Organic Tomato Fertilizer", "link": "https://www.amazon.com/dp/B01MXKBNGH"}
        ]
    },
    'Tomato___Early_blight': {
        'prevention': "Practice crop rotation, mulch soil to prevent splashing, stake plants for airflow, and use resistant varieties.",
        'medicines': "Apply fungicides containing chlorothalonil or copper-based products.",
        'fertilizers': [
            {"name": "Espoma Organic Tomato-Tone", "link": "https://www.amazon.com/dp/B01MAW3JYE"},
            {"name": "Dr. Earth Organic Tomato Fertilizer", "link": "https://www.amazon.com/dp/B01MXKBNGH"}
        ]
    },
    'Tomato___Late_blight': {
        'prevention': "Use resistant varieties, avoid overhead watering, remove plant debris, and ensure good airflow.",
        'medicines': "Apply fungicides like chlorothalonil or copper-based products preventatively.",
        'fertilizers': [
            {"name": "Espoma Organic Tomato-Tone", "link": "https://www.amazon.com/dp/B01MAW3JYE"},
            {"name": "Dr. Earth Organic Tomato Fertilizer", "link": "https://www.amazon.com/dp/B01MXKBNGH"}
        ]
    },
    'Tomato___Leaf_Mold': {
        'prevention': "Reduce humidity with good airflow and spacing, use drip irrigation, and remove lower leaves.",
        'medicines': "Apply fungicides containing chlorothalonil or copper.",
        'fertilizers': [
            {"name": "Espoma Organic Tomato-Tone", "link": "https://www.amazon.com/dp/B01MAW3JYE"},
            {"name": "Dr. Earth Organic Tomato Fertilizer", "link": "https://www.amazon.com/dp/B01MXKBNGH"}
        ]
    },
    'Tomato___Septoria_leaf_spot': {
        'prevention': "Practice crop rotation, remove plant debris, mulch to prevent splashing, and avoid overhead watering.",
        'medicines': "Apply fungicides containing chlorothalonil, mancozeb, or copper.",
        'fertilizers': [
            {"name": "Espoma Organic Tomato-Tone", "link": "https://www.amazon.com/dp/B01MAW3JYE"},
            {"name": "Dr. Earth Organic Tomato Fertilizer", "link": "https://www.amazon.com/dp/B01MXKBNGH"}
        ]
    },
    'Tomato___Spider_mites_Two-spotted_spider_mite': {
        'prevention': "Avoid dry, dusty conditions, use overhead watering to dislodge mites, and encourage natural predators.",
        'medicines': "Use insecticidal soaps, horticultural oils, or miticides like abamectin.",
        'fertilizers': [
            {"name": "Espoma Organic Tomato-Tone", "link": "https://www.amazon.com/dp/B01MAW3JYE"},
            {"name": "Dr. Earth Organic Tomato Fertilizer", "link": "https://www.amazon.com/dp/B01MXKBNGH"}
        ]
    },
    'Tomato___Target_Spot': {
        'prevention': "Improve air circulation, remove infected leaves, practice crop rotation, and avoid overhead watering.",
        'medicines': "Apply protectant fungicides like chlorothalonil or copper-based products.",
        'fertilizers': [
            {"name": "Espoma Organic Tomato-Tone", "link": "https://www.amazon.com/dp/B01MAW3JYE"},
            {"name": "Dr. Earth Organic Tomato Fertilizer", "link": "https://www.amazon.com/dp/B01MXKBNGH"}
        ]
    },
    'Tomato___Tomato_mosaic_virus': {
        'prevention': "Use resistant varieties, disinfect tools and hands, avoid tobacco products near plants, and use disease-free seeds.",
        'medicines': "No chemical treatments available; remove and destroy infected plants.",
        'fertilizers': [
            {"name": "Espoma Organic Tomato-Tone", "link": "https://www.amazon.com/dp/B01MAW3JYE"},
            {"name": "Dr. Earth Organic Tomato Fertilizer", "link": "https://www.amazon.com/dp/B01MXKBNGH"}
        ]
    },
    'Tomato___Tomato_Yellow_Leaf_Curl_Virus': {
        'prevention': "Use resistant varieties, control whiteflies with row covers or reflective mulches, and remove infected plants.",
        'medicines': "No cure for the virus; use insecticides to control whitefly vectors.",
        'fertilizers': [
            {"name": "Espoma Organic Tomato-Tone", "link": "https://www.amazon.com/dp/B01MAW3JYE"},
            {"name": "Dr. Earth Organic Tomato Fertilizer", "link": "https://www.amazon.com/dp/B01MXKBNGH"}
        ]
    },
    'Tomato___healthy': {
        'prevention': "Maintain good airflow with staking, avoid overhead watering, and practice crop rotation.",
        'medicines': "No treatments needed for healthy plants.",
        'fertilizers': [
            {"name": "Espoma Organic Tomato-Tone", "link": "https://www.amazon.com/dp/B01MAW3JYE"},
            {"name": "Dr. Earth Organic Tomato Fertilizer", "link": "https://www.amazon.com/dp/B01MXKBNGH"}
        ]
    }
}



@app.route('/predict', methods=['POST'])
def predict():
    if 'user_id' not in session:
        return jsonify({'error': 'Please login first'}), 401

    file = request.files.get('file')
    if not file or file.filename == '':
        return jsonify({'error': 'No file selected'}), 400

    if not allowed_file(file.filename):
        return jsonify({'error': 'Invalid file type'}), 400

    # ---- Save file ----
    filename = secure_filename(file.filename)
    filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
    file.save(filepath)

    # ---- Preprocess (returns (1,224,224,3)) ----
    processed = preprocess_image(filepath)
    if processed is None:
        return jsonify({'error': 'Image processing failed'}), 500

    if model is None:
        return jsonify({'error': 'Model not loaded'}), 500

    try:
        # ---- Feature extractor (cached globally for speed) ----
        if not hasattr(app, 'densenet_extractor'):
            from tensorflow.keras.applications import DenseNet121
            app.densenet_extractor = DenseNet121(
                weights='imagenet', include_top=False, pooling='avg'
            )
            print("DenseNet121 extractor ready")
        extractor = app.densenet_extractor

        features = extractor.predict(processed, verbose=0)   # (1, 1024)

        # ---- XGBoost prediction ----
        pred_idx = int(model.predict(features)[0])          # Python int
        proba = model.predict_proba(features)[0]
        max_proba = np.max(proba)

        # ---- Confidence threshold check for invalid images ----
        CONFIDENCE_THRESHOLD = 0.5  # 50% threshold
        if max_proba < CONFIDENCE_THRESHOLD:
            predicted_class = "Unknown"
            confidence = 0.0
        else:
            predicted_class = CLASS_LABELS[pred_idx]
            confidence = float(max_proba) * 100

        # ---- DB save ----
        cur = mysql.connection.cursor()
        cur.execute(
            """INSERT INTO predictions 
               (user_id, image_path, prediction_result, confidence) 
               VALUES (%s, %s, %s, %s)""",
            (session['user_id'], filename, predicted_class, confidence)
        )
        mysql.connection.commit()
        cur.close()

        # ---- Format result ----
        if predicted_class == "Unknown":
            plant = "Unknown"
            disease = "Invalid image - Please upload a clear plant leaf image"
            status = "Invalid"
            prevention = "Please upload a valid plant leaf image for accurate detection."
            medicines = "N/A"
            fertilizers_list = []
        else:
            parts = predicted_class.split('___')
            plant = parts[0].replace('_', ' ')
            disease = parts[1].replace('_', ' ') if len(parts) > 1 else "Unknown"
            status = "Healthy" if "healthy" in disease.lower() else "Diseased"

            # Fetch disease guidelines (prevention, medicines, and fertilizers)
            guidelines = DISEASE_GUIDELINES.get(predicted_class, None)
            if guidelines:
                prevention = guidelines['prevention']
                medicines = guidelines['medicines']
                fertilizers = guidelines['fertilizers'] if isinstance(guidelines['fertilizers'], list) else []
            else:
                prevention = "No specific prevention guidelines found."
                medicines = "No specific medicines recommended."
                fertilizers = []

            # Construct the fertilizers list with name and purchase links
            fertilizers_list = []
            for fertilizer in fertilizers:
                fertilizers_list.append({
                    'name': fertilizer.get('name', 'N/A'),
                    'link': fertilizer.get('link', '#')
                })

        result = {
            'plant': plant,
            'disease': disease,
            'status': status,
            'confidence': round(confidence, 2),
            'image_path': url_for('static', filename='uploads/' + filename),
            'prevention': prevention,
            'medicines': medicines,
            'fertilizers': fertilizers_list
        }
        return jsonify(result)

    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({'error': 'Prediction failed'}), 500


@app.route('/history')
def history():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    
    cur = mysql.connection.cursor()
    cur.execute("""
        SELECT image_path, prediction_result, confidence, created_at 
        FROM predictions 
        WHERE user_id = %s 
        ORDER BY created_at DESC
    """, (session['user_id'],))
    
    predictions = cur.fetchall()
    cur.close()
    
    prediction_list = []
    for pred in predictions:
        if pred[1] == "Unknown":
            plant_name = "Unknown"
            disease_name = "Invalid image - Please upload a clear plant leaf image"
            status = "Invalid"
            conf = 0.0
        else:
            parts = pred[1].split('___')
            plant_name = parts[0].replace('_', ' ')
            disease_name = parts[1].replace('_', ' ') if len(parts) > 1 else "Unknown"
            status = "Healthy" if "healthy" in disease_name.lower() else "Diseased"
            conf = pred[2]
        
        prediction_list.append({
            'image_path': url_for('static', filename='uploads/' + pred[0]),
            'plant': plant_name,
            'disease': disease_name,
            'status': status,
            'confidence': round(conf, 2),
            'date': pred[3]
        })
    
    return render_template('history.html', predictions=prediction_list)

@app.route('/logout', methods=['GET', 'POST'])
def logout():
    session.clear()
    flash('You have been logged out!', 'info')
    return redirect(url_for('login'))

if __name__ == '__main__':
>>>>>>> d9093859607244c1a1565ceb16a4e89321885cda
    app.run(host='0.0.0.0', port=5000, debug=True)