from flask import Flask, request, jsonify, send_from_directory, session, redirect, url_for
from flask_sqlalchemy import SQLAlchemy
from flask_cors import CORS
from functools import wraps
import os
import base64
import face_recognition
import pickle
import numpy as np
from datetime import datetime, timedelta
import hashlib
import pytz  # ✅ ADD THIS LINE

# ========== PROJECT PATHS CONFIGURATION ==========
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
SERVER_DIR = os.path.join(BASE_DIR, "server")
STUDENTS_DIR = os.path.join(SERVER_DIR, "students")
MODEL_PATH = os.path.join(SERVER_DIR, "trained_model.pkl")
DATABASE_PATH = os.path.join(SERVER_DIR, "students.db")
ADMIN_DB_PATH = os.path.join(SERVER_DIR, "admin_users.db")

# Create necessary directories
os.makedirs(STUDENTS_DIR, exist_ok=True)
os.makedirs(SERVER_DIR, exist_ok=True)

# ========== FLASK APP SETUP ==========
app = Flask(__name__, static_folder='static', template_folder='static')
app.config['SECRET_KEY'] = 'face-attendance-system-secret-key-2025'
app.config['SESSION_TYPE'] = 'filesystem'
app.config['PERMANENT_SESSION_LIFETIME'] = timedelta(hours=24)
CORS(app, supports_credentials=True)

# ========== DATABASE SETUP ==========
app.config["SQLALCHEMY_DATABASE_URI"] = f"sqlite:///{DATABASE_PATH}"
app.config["SQLALCHEMY_BINDS"] = {
    'admin': f"sqlite:///{ADMIN_DB_PATH}"
}
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

db = SQLAlchemy(app)

# ========== DATABASE MODELS ==========
class AdminUser(db.Model):
    __bind_key__ = 'admin'
    __tablename__ = 'admin_users'
    
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(200), nullable=False)
    full_name = db.Column(db.String(200))
    role = db.Column(db.String(50), default='admin')
    is_active = db.Column(db.Boolean, default=True)
    last_login = db.Column(db.DateTime)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    def set_password(self, password):
        self.password_hash = hashlib.sha256(password.encode()).hexdigest()
    
    def check_password(self, password):
        return self.password_hash == hashlib.sha256(password.encode()).hexdigest()

class Student(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(200), nullable=False)
    enrollment_number = db.Column(db.String(100), unique=True, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

class FaceEncoding(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    student_id = db.Column(db.Integer, db.ForeignKey("student.id"))
    encoding = db.Column(db.PickleType, nullable=False)

class Attendance(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    student_id = db.Column(db.Integer, db.ForeignKey("student.id"), nullable=False)
    subject = db.Column(db.String(100), nullable=False)
    date = db.Column(db.String(20), nullable=False)
    time = db.Column(db.String(20), nullable=False)
    marked_at = db.Column(db.DateTime, default=datetime.utcnow)
    confidence = db.Column(db.Float, nullable=False)
    status = db.Column(db.String(20), default="Present")
    
    student = db.relationship('Student', backref='attendances')


# ========== AUTHENTICATION DECORATOR ==========
def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            if request.endpoint == 'serve_sign_in':
                return f(*args, **kwargs)
            return redirect(url_for('serve_sign_in'))
        return f(*args, **kwargs)
    return decorated_function


# ========== SIMPLIFIED ADMIN USER MANAGEMENT ==========
def initialize_admin_user():
    """Create default admin user if not exists"""
    with app.app_context():
        try:
            db.create_all()
            
            admin_exists = AdminUser.query.filter_by(username='admin').first()
            
            if not admin_exists:
                admin = AdminUser(
                    username='admin',
                    email='admin@faceattendance.com',
                    full_name='System Administrator',
                    role='super_admin',
                    is_active=True
                )
                admin.set_password('admin123')
                
                db.session.add(admin)
                db.session.commit()
                print("✅ Default admin user created: admin/admin123")
            else:
                print("✅ Admin user already exists")
                
        except Exception as e:
            print(f"⚠️ Warning: Could not create admin table: {e}")
            print("⚠️ Using simple session-based authentication instead")


# ========== DATE & TIME UTILITY FUNCTIONS ==========
def get_indian_time():
    """Get current time in Indian timezone (IST)"""
    try:
        # Set to Indian timezone
        ist = pytz.timezone('Asia/Kolkata')
        now_utc = datetime.now(pytz.utc)
        now_ist = now_utc.astimezone(ist)
        return now_ist
    except:
        # Fallback to system time if pytz not available
        return datetime.now()

def get_current_date():
    """Get current date in YYYY-MM-DD format (IST)"""
    now_ist = get_indian_time()
    return now_ist.strftime("%Y-%m-%d")

def get_current_time():
    """Get current time in HH:MM:SS format (IST)"""
    now_ist = get_indian_time()
    return now_ist.strftime("%H:%M:%S")

def parse_date(date_str):
    """Parse date string to YYYY-MM-DD format"""
    if not date_str:
        return get_current_date()
    
    try:
        date_str = str(date_str).strip()
        print(f"🔍 Parsing date string: '{date_str}'")
        
        # Try common date formats
        date_formats = [
            "%Y-%m-%d",        # 2025-03-12
            "%d-%m-%Y",        # 12-03-2025
            "%m-%d-%Y",        # 03-12-2025
            "%d/%m/%Y",        # 12/03/2025
            "%m/%d/%Y",        # 03/12/2025
            "%d-%m-%y",        # 12-03-25
            "%m-%d-%y",        # 03-12-25
            "%d/%m/%y",        # 12/03/25
            "%m/%d/%y",        # 03/12/25
            "%Y/%m/%d",        # 2025/03/12
        ]
        
        for fmt in date_formats:
            try:
                parsed_date = datetime.strptime(date_str, fmt)
                # Ensure 4-digit year
                if parsed_date.year < 100:
                    if parsed_date.year < 50:
                        parsed_date = parsed_date.replace(year=parsed_date.year + 2000)
                    else:
                        parsed_date = parsed_date.replace(year=parsed_date.year + 1900)
                
                result = parsed_date.strftime("%Y-%m-%d")
                print(f"✅ Parsed '{date_str}' as '{result}' using format '{fmt}'")
                return result
            except ValueError:
                continue
        
        # If no format matches, check if it's already in correct format
        if len(date_str) == 10 and date_str[4] == '-' and date_str[7] == '-':
            # Already in YYYY-MM-DD format
            print(f"✅ Date already in YYYY-MM-DD format: {date_str}")
            return date_str
        
        print(f"❌ Could not parse date: '{date_str}'")
        return get_current_date()
    except Exception as e:
        print(f"❌ Error parsing date '{date_str}': {e}")
        return get_current_date()


# ========== MODEL TRAINING FUNCTIONS ==========
def load_existing_model():
    """Load existing trained model if exists"""
    if os.path.exists(MODEL_PATH):
        try:
            with open(MODEL_PATH, "rb") as f:
                model_data = pickle.load(f)
            print(f"✅ Loaded existing model with {len(model_data.get('encodings', []))} encodings")
            return model_data
        except Exception as e:
            print(f"❌ Error loading model: {e}")
    return {"encodings": [], "names": [], "student_ids": []}


def save_trained_model(model_data):
    """Save trained model to file"""
    try:
        print(f"💾 Saving model to: {MODEL_PATH}")
        print(f"   Model has {len(model_data['encodings'])} encodings")
        
        with open(MODEL_PATH, "wb") as f:
            pickle.dump(model_data, f)
        
        if os.path.exists(MODEL_PATH):
            file_size = os.path.getsize(MODEL_PATH)
            print(f"✅ Model saved successfully ({file_size} bytes)")
            return True
        else:
            print("❌ Model file not found after saving")
            return False
            
    except Exception as e:
        print(f"❌ Error saving model: {e}")
        raise


def update_model_with_new_student(student_id, enrollment_number, new_encodings):
    """Update trained model with new student's encodings"""
    print(f"🔄 Updating model with new student: {enrollment_number}")
    
    model_data = load_existing_model()
    
    for encoding in new_encodings:
        model_data["encodings"].append(encoding)
        model_data["names"].append(enrollment_number)
        model_data["student_ids"].append(student_id)
    
    if save_trained_model(model_data):
        print(f"✅ Model updated with {len(new_encodings)} new encodings")
        return len(new_encodings)
    return 0


def retrain_complete_model():
    """Retrain complete model from all students in database"""
    print("\n" + "="*50)
    print("🔄 STARTING COMPLETE MODEL RETRAINING")
    print("="*50)
    
    try:
        with app.app_context():
            students = Student.query.all()
            print(f"📊 Found {len(students)} students in database")
            
            model_data = {"encodings": [], "names": [], "student_ids": []}
            total_encodings = 0
            students_with_faces = 0
            
            for idx, student in enumerate(students, 1):
                print(f"\n[{idx}/{len(students)}] Processing: {student.name} ({student.enrollment_number})")
                
                face_encodings = FaceEncoding.query.filter_by(student_id=student.id).all()
                print(f"   📸 Found {len(face_encodings)} face encodings")
                
                if len(face_encodings) > 0:
                    students_with_faces += 1
                    
                    for face_encoding in face_encodings:
                        model_data["encodings"].append(face_encoding.encoding)
                        model_data["names"].append(student.enrollment_number)
                        model_data["student_ids"].append(student.id)
                        total_encodings += 1
                else:
                    print(f"   ⚠️ No face encodings found for this student")
            
            print(f"\n📈 RETRAINING SUMMARY:")
            print(f"   • Total students processed: {len(students)}")
            print(f"   • Students with face data: {students_with_faces}")
            print(f"   • Total face encodings collected: {total_encodings}")
            
            if total_encodings > 0:
                if save_trained_model(model_data):
                    print(f"✅ Model retraining completed successfully!")
                else:
                    print(f"❌ Failed to save model file")
            else:
                print(f"⚠️ No encodings found - model not saved")
            
            print("="*50)
            return total_encodings
            
    except Exception as e:
        print(f"\n❌ ERROR in retrain_complete_model: {str(e)}")
        import traceback
        traceback.print_exc()
        return 0


# =======================================================
#   AUTHENTICATION ROUTES
# =======================================================
@app.route("/api/login", methods=["POST"])
def login():
    """Authenticate user"""
    try:
        data = request.get_json()
        username = data.get('username')
        password = data.get('password')
        
        if not username or not password:
            return jsonify({
                "status": "error",
                "message": "Username and password are required"
            }), 400
        
        if username == 'admin' and password == 'admin123':
            session['user_id'] = 1
            session['username'] = 'admin'
            session['email'] = 'admin@faceattendance.com'
            session['full_name'] = 'System Administrator'
            session['role'] = 'super_admin'
            session['logged_in'] = True
            
            return jsonify({
                "status": "success",
                "message": "Login successful",
                "user": {
                    "id": 1,
                    "username": 'admin',
                    "email": 'admin@faceattendance.com',
                    "full_name": 'System Administrator',
                    "role": 'super_admin'
                }
            })
        
        try:
            user = AdminUser.query.filter(
                (AdminUser.username == username) | (AdminUser.email == username)
            ).first()
            
            if user and user.check_password(password):
                user.last_login = datetime.utcnow()
                db.session.commit()
                
                session['user_id'] = user.id
                session['username'] = user.username
                session['email'] = user.email
                session['full_name'] = user.full_name
                session['role'] = user.role
                session['logged_in'] = True
                
                return jsonify({
                    "status": "success",
                    "message": "Login successful",
                    "user": {
                        "id": user.id,
                        "username": user.username,
                        "email": user.email,
                        "full_name": user.full_name,
                        "role": user.role
                    }
                })
        except:
            pass
        
        return jsonify({
            "status": "error",
            "message": "Invalid username or password"
        }), 401
        
    except Exception as e:
        print(f"❌ Login error: {str(e)}")
        return jsonify({
            "status": "error",
            "message": "Internal server error"
        }), 500


@app.route("/api/check-session", methods=["GET"])
def check_session():
    """Check if user is logged in"""
    if 'user_id' in session:
        return jsonify({
            "status": "success",
            "logged_in": True,
            "user": {
                "id": session.get('user_id'),
                "username": session.get('username'),
                "email": session.get('email'),
                "full_name": session.get('full_name'),
                "role": session.get('role')
            }
        })
    else:
        return jsonify({
            "status": "success",
            "logged_in": False
        })


@app.route("/logout")
def logout():
    """Logout user"""
    session.clear()
    return redirect(url_for('serve_sign_in'))


# =======================================================
#   FRONTEND ROUTES (PROTECTED)
# =======================================================
@app.route('/')
@login_required
def home():
    return send_from_directory('static', 'index.html')

@app.route('/dashboard')
@login_required
def serve_dashboard():
    return send_from_directory('static', 'index.html')

@app.route('/mark-attendance')
@login_required
def serve_mark_attendance():
    return send_from_directory('static', 'mark-attendance.html')

@app.route('/register-student')
@login_required
def serve_register_student():
    return send_from_directory('static', 'register-student.html')

@app.route('/sign-in')
def serve_sign_in():
    if 'user_id' in session:
        return redirect(url_for('serve_dashboard'))
    return send_from_directory('static', 'sign-in.html')

@app.route('/view-students')
@login_required
def serve_view_students():
    return send_from_directory('static', 'view-student.html')

@app.route('/<path:filename>')
def serve_static_files(filename):
    return send_from_directory('static', filename)


# =======================================================
#   API: REGISTER STUDENT (WITH AUTO TRAINING) - FIXED
# =======================================================
@app.route("/api/register-student", methods=["POST"])
@login_required
def register_student():
    data = request.get_json()

    name = data.get("name")
    enrollment = data.get("enrollment_number")
    images = data.get("face_images")

    if not name or not enrollment:
        return jsonify({"success": False, "message": "Missing name or enrollment number"}), 400

    if not images or len(images) < 15:
        return jsonify({"success": False, "message": "At least 15 images are required"}), 400

    try:
        existing_student = Student.query.filter_by(enrollment_number=enrollment).first()
        if existing_student:
            return jsonify({"success": False, "message": "Enrollment already exists"}), 400

        # ✅ FIXED: Use Indian time for created_at
        current_time = get_indian_time()
        student = Student(
            name=name, 
            enrollment_number=enrollment,
            created_at=current_time  # ✅ Indian time
        )
        db.session.add(student)
        db.session.commit()

        print(f"✅ Student registered: {name} ({enrollment}) at {current_time}")

        student_folder = os.path.join(STUDENTS_DIR, enrollment)
        os.makedirs(student_folder, exist_ok=True)

        new_encodings = []
        successful_encodings = 0
        
        for i, img in enumerate(images):
            try:
                img_data = img.split(",")[1] if "," in img else img
                img_bytes = base64.b64decode(img_data)

                img_path = os.path.join(student_folder, f"{i+1}.jpg")
                with open(img_path, "wb") as f:
                    f.write(img_bytes)

                image_np = face_recognition.load_image_file(img_path)
                encodings = face_recognition.face_encodings(image_np)

                if len(encodings) == 0:
                    print(f"⚠️ No face found in image {i+1}")
                    continue

                encoding = encodings[0]
                new_encodings.append(encoding)
                successful_encodings += 1

                face_encoding = FaceEncoding(student_id=student.id, encoding=encoding)
                db.session.add(face_encoding)

            except Exception as e:
                print(f"❌ Error processing image {i+1}: {str(e)}")
                continue

        db.session.commit()
        
        if successful_encodings == 0:
            db.session.delete(student)
            db.session.commit()
            return jsonify({"success": False, "message": "No faces detected in any images"}), 400
        
        trained_count = update_model_with_new_student(student.id, enrollment, new_encodings)
        
        return jsonify({
            "success": True,
            "message": f"Student registered successfully. Model updated with {successful_encodings} face encodings.",
            "student_id": student.id,
            "encodings_added": successful_encodings,
            "model_updated": True,
            "registration_time": current_time.strftime("%Y-%m-%d %H:%M:%S")  # ✅ Send back time for debugging
        })
        
    except Exception as e:
        db.session.rollback()
        print(f"🔥 Registration error: {str(e)}")
        return jsonify({"success": False, "message": f"Registration failed: {str(e)}"}), 500


# =======================================================
#   ADDITIONAL APIs FOR MODEL MANAGEMENT (PROTECTED)
# =======================================================
@app.route("/api/retrain-model", methods=["POST"])
@login_required
def retrain_model():
    """Retrain the complete face recognition model"""
    print("\n🎯 MANUAL MODEL RETRAINING REQUESTED")
    print("="*40)
    
    try:
        with app.app_context():
            total_students = Student.query.count()
            total_encodings_db = FaceEncoding.query.count()
            
            print(f"📊 Database Status:")
            print(f"   • Total students: {total_students}")
            print(f"   • Total face encodings in DB: {total_encodings_db}")
            
            if total_encodings_db == 0:
                return jsonify({
                    "success": False, 
                    "message": "No face encodings found in database. Please register students first."
                }), 400
        
        print(f"\n🔄 Starting model retraining...")
        total_encodings = retrain_complete_model()
        
        if os.path.exists(MODEL_PATH):
            model_data = load_existing_model()
            print(f"\n✅ VERIFICATION:")
            print(f"   • Model file exists: {os.path.exists(MODEL_PATH)}")
            print(f"   • Encodings in model: {len(model_data['encodings'])}")
            
            return jsonify({
                "success": True,
                "message": f"✅ Model retrained successfully with {total_encodings} encodings",
                "total_encodings": total_encodings,
                "model_file_exists": True,
                "encodings_count": len(model_data['encodings'])
            })
        else:
            print(f"❌ Model file not created")
            return jsonify({
                "success": False,
                "message": "Model file was not created"
            }), 500
            
    except Exception as e:
        print(f"\n❌ ERROR in retrain_model API: {str(e)}")
        import traceback
        traceback.print_exc()
        return jsonify({"success": False, "message": f"Retraining failed: {str(e)}"}), 500


@app.route("/api/model-status", methods=["GET"])
@login_required
def model_status():
    """Check current model status"""
    try:
        model_data = load_existing_model()
        
        with app.app_context():
            student_count = Student.query.count()
            encoding_count_db = FaceEncoding.query.count()
        
        return jsonify({
            "success": True,
            "model_exists": os.path.exists(MODEL_PATH),
            "model_has_data": len(model_data["encodings"]) > 0,
            "total_students": student_count,
            "total_encodings": len(model_data["encodings"]),
            "encodings_in_database": encoding_count_db,
            "unique_students_in_model": len(set(model_data["student_ids"])) if model_data.get("student_ids") else 0,
            "model_file_size": os.path.getsize(MODEL_PATH) if os.path.exists(MODEL_PATH) else 0
        })
    except Exception as e:
        return jsonify({"success": False, "message": f"Error checking model: {str(e)}"}), 500


# =======================================================
#   API: MARK ATTENDANCE (REAL-TIME FACE RECOGNITION) - FIXED
# =======================================================
@app.route("/api/mark-attendance", methods=["POST"])
@login_required
def mark_attendance():
    try:
        data = request.get_json()
        
        subject = data.get("subject", "General")
        date = data.get("date")
        time = data.get("time")
        face_image = data.get("face_image")
        
        if not face_image:
            return jsonify({"success": False, "message": "No face image provided"}), 400
        
        # ✅ FIXED: Always use Indian time
        if not date:
            date = get_current_date()  # Indian date
        else:
            date = parse_date(date)
        
        if not time:
            time = get_current_time()  # Indian time
        
        print(f"📅 Marking attendance: date={date}, time={time}, subject={subject}")
        
        model_data = load_existing_model()
        
        if len(model_data["encodings"]) == 0:
            return jsonify({"success": False, "message": "No trained model found. Please register students first."}), 400
        
        img_data = face_image.split(",")[1] if "," in face_image else face_image
        img_bytes = base64.b64decode(img_data)
        
        temp_filename = f"temp_attendance_{datetime.now().timestamp()}.jpg"
        temp_path = os.path.join(BASE_DIR, temp_filename)
        with open(temp_path, "wb") as f:
            f.write(img_bytes)
        
        test_image = face_recognition.load_image_file(temp_path)
        test_encodings = face_recognition.face_encodings(test_image)
        
        if len(test_encodings) == 0:
            if os.path.exists(temp_path):
                os.remove(temp_path)
            return jsonify({"success": False, "message": "No face detected in image"}), 400
        
        test_encoding = test_encodings[0]
        
        face_distances = face_recognition.face_distance(model_data["encodings"], test_encoding)
        best_match_index = np.argmin(face_distances)
        best_distance = face_distances[best_match_index]
        
        recognition_threshold = 0.6
        
        if best_distance < recognition_threshold:
            recognized_enrollment = model_data["names"][best_match_index]
            student_id = model_data["student_ids"][best_match_index]
            
            with app.app_context():
                student = Student.query.get(student_id)
                
                if student:
                    # Check if attendance already marked for today for this subject
                    existing_attendance = Attendance.query.filter(
                        Attendance.student_id == student.id,
                        Attendance.date == date,
                        Attendance.subject == subject
                    ).first()
                    
                    if existing_attendance:
                        if os.path.exists(temp_path):
                            os.remove(temp_path)
                        return jsonify({
                            "success": True,
                            "recognized": True,
                            "already_marked": True,
                            "message": f"Attendance already marked for {student.name} today in {subject}",
                            "attendance_record": {
                                "student_id": student.id,
                                "student_name": student.name,
                                "enrollment_number": student.enrollment_number,
                                "subject": subject,
                                "date": date,
                                "time": time,
                                "confidence": float(1 - best_distance),
                                "distance": float(best_distance),
                                "status": "Present"
                            }
                        })
                    
                    # ✅ FIXED: Use current Indian time for marked_at
                    current_time_ist = get_indian_time()
                    
                    attendance = Attendance(
                        student_id=student.id,
                        subject=subject,
                        date=date,
                        time=time,
                        marked_at=current_time_ist,  # ✅ Indian time
                        confidence=float(1 - best_distance),
                        status="Present"
                    )
                    db.session.add(attendance)
                    db.session.commit()
                    
                    print(f"✅ Attendance marked: {student.name} at {time} on {date}")
                    
                    attendance_record = {
                        "student_id": student.id,
                        "student_name": student.name,
                        "enrollment_number": student.enrollment_number,
                        "subject": subject,
                        "date": date,
                        "time": time,
                        "confidence": float(1 - best_distance),
                        "distance": float(best_distance),
                        "status": "Present",
                        "marked_at": current_time_ist.strftime("%Y-%m-%d %H:%M:%S")  # ✅ Add for debugging
                    }
                    
                    if os.path.exists(temp_path):
                        os.remove(temp_path)
                    
                    return jsonify({
                        "success": True,
                        "recognized": True,
                        "already_marked": False,
                        "message": f"Attendance marked for {student.name}",
                        "attendance_record": attendance_record
                    })
        
        if os.path.exists(temp_path):
            os.remove(temp_path)
            
        return jsonify({
            "success": True,
            "recognized": False,
            "message": "Face not recognized. Please register first.",
            "distance": float(best_distance) if 'best_distance' in locals() else 1.0,
            "threshold": recognition_threshold
        })
        
    except Exception as e:
        import glob
        temp_pattern = os.path.join(BASE_DIR, "temp_attendance_*.jpg")
        for f in glob.glob(temp_pattern):
            if os.path.exists(f):
                os.remove(f)
                
        print(f"❌ Attendance marking error: {str(e)}")
        return jsonify({"success": False, "message": f"Attendance marking failed: {str(e)}"}), 500


# =======================================================
#   API: GET ATTENDANCE RECORDS (FOR DASHBOARD) - FIXED
# =======================================================
@app.route("/api/get-attendance", methods=["GET"])
@login_required
def get_attendance():
    """Get attendance records for dashboard"""
    try:
        # Get query parameters
        limit = request.args.get('limit', default=10, type=int)
        date_filter = request.args.get('date')
        student_id = request.args.get('student_id')
        
        # ✅ FIXED: Always parse date to YYYY-MM-DD format
        if date_filter:
            date_filter = parse_date(date_filter)
            print(f"🔍 Getting attendance for date: {date_filter}")
        
        # Build query
        query = Attendance.query.join(Student).order_by(Attendance.marked_at.desc())
        
        # Apply filters if provided
        if date_filter:
            query = query.filter(Attendance.date == date_filter)
        
        if student_id:
            query = query.filter(Attendance.student_id == student_id)
        
        # Get limited records
        attendance_records = query.limit(limit).all()
        
        # Format response
        attendance_list = []
        for record in attendance_records:
            # ✅ FIXED: Convert marked_at to Indian time for display
            marked_at_local = None
            if record.marked_at:
                try:
                    # Convert UTC to IST
                    utc_time = record.marked_at.replace(tzinfo=pytz.utc)
                    ist = pytz.timezone('Asia/Kolkata')
                    marked_at_local = utc_time.astimezone(ist)
                except:
                    marked_at_local = record.marked_at
            
            attendance_list.append({
                'id': record.id,
                'student_id': record.student_id,
                'student_name': record.student.name,
                'enrollment_number': record.student.enrollment_number,
                'subject': record.subject,
                'date': record.date,
                'time': record.time,
                'confidence': record.confidence,
                'status': record.status,
                'marked_at': marked_at_local.isoformat() if marked_at_local else None,
                'marked_at_local': marked_at_local.strftime("%Y-%m-%d %H:%M:%S") if marked_at_local else None
            })
        
        # Get today's attendance count (always in YYYY-MM-DD)
        today = get_current_date()
        today_count = Attendance.query.filter(Attendance.date == today).count()
        
        print(f"📊 Today's attendance ({today}): {today_count} records")
        
        return jsonify({
            'success': True,
            'attendance': attendance_list,
            'total_records': len(attendance_list),
            'today_records': today_count,
            'today_date': today
        })
        
    except Exception as e:
        print(f"❌ Error in get_attendance: {str(e)}")
        return jsonify({
            'success': False,
            'error': str(e),
            'attendance': [],
            'today_records': 0
        }), 500


# =======================================================
#   API: GET STUDENTS LIST - FIXED
# =======================================================
@app.route("/api/get-students", methods=["GET"])
@login_required
def get_students():
    """Get all registered students"""
    try:
        students = Student.query.all()
        
        students_list = []
        for student in students:
            face_count = FaceEncoding.query.filter_by(student_id=student.id).count()
            attendance_count = Attendance.query.filter_by(student_id=student.id).count()
            
            # ✅ FIXED: Convert created_at to Indian time
            created_at_local = None
            if student.created_at:
                try:
                    utc_time = student.created_at.replace(tzinfo=pytz.utc)
                    ist = pytz.timezone('Asia/Kolkata')
                    created_at_local = utc_time.astimezone(ist)
                except:
                    created_at_local = student.created_at
            
            students_list.append({
                'id': student.id,
                'name': student.name,
                'enrollment_number': student.enrollment_number,
                'created_at': student.created_at.isoformat() if student.created_at else None,
                'created_at_local': created_at_local.strftime("%Y-%m-%d %H:%M:%S") if created_at_local else None,
                'created_at_display': created_at_local.strftime("%d/%m/%Y %I:%M %p") if created_at_local else None,
                'has_face_images': face_count > 0,
                'face_encodings_count': face_count,
                'total_attendance': attendance_count,
                'total_attendance_records': attendance_count
            })
        
        return jsonify({
            'success': True,
            'students': students_list,
            'total': len(students_list)
        })
        
    except Exception as e:
        print(f"❌ Error in get_students: {str(e)}")
        return jsonify({
            'success': False,
            'error': str(e),
            'students': []
        }), 500


# =======================================================
#   API: GET SINGLE STUDENT DETAILS - FIXED
# =======================================================
@app.route("/api/get-student/<int:student_id>", methods=["GET"])
@login_required
def get_student(student_id):
    """Get detailed information about a specific student"""
    try:
        student = Student.query.get_or_404(student_id)
        
        face_count = FaceEncoding.query.filter_by(student_id=student.id).count()
        attendance_count = Attendance.query.filter_by(student_id=student.id).count()
        
        # ✅ FIXED: Convert created_at to Indian time
        created_at_local = None
        if student.created_at:
            try:
                utc_time = student.created_at.replace(tzinfo=pytz.utc)
                ist = pytz.timezone('Asia/Kolkata')
                created_at_local = utc_time.astimezone(ist)
            except:
                created_at_local = student.created_at
        
        student_folder = os.path.join(STUDENTS_DIR, student.enrollment_number)
        folder_exists = os.path.exists(student_folder)
        
        face_images_preview = []
        if folder_exists:
            try:
                for i in range(1, min(4, face_count) + 1):
                    img_path = os.path.join(student_folder, f"{i}.jpg")
                    if os.path.exists(img_path):
                        with open(img_path, "rb") as img_file:
                            img_data = base64.b64encode(img_file.read()).decode('utf-8')
                            face_images_preview.append(f"data:image/jpeg;base64,{img_data}")
            except:
                pass
        
        student_data = {
            'id': student.id,
            'name': student.name,
            'enrollment_number': student.enrollment_number,
            'created_at': student.created_at.isoformat() if student.created_at else None,
            'created_at_local': created_at_local.strftime("%Y-%m-%d %H:%M:%S") if created_at_local else None,
            'created_at_display': created_at_local.strftime("%d/%m/%Y %I:%M %p") if created_at_local else None,
            'face_encodings_count': face_count,
            'total_attendance_records': attendance_count,
            'folder_exists': folder_exists,
            'face_images_preview': face_images_preview[:3]
        }
        
        return jsonify({
            'success': True,
            'student': student_data
        })
        
    except Exception as e:
        print(f"❌ Error in get_student: {str(e)}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 404


# =======================================================
#   API: UPDATE STUDENT
# =======================================================
@app.route("/api/update-student/<int:student_id>", methods=["PUT"])
@login_required
def update_student(student_id):
    """Update student information"""
    try:
        data = request.get_json()
        student = Student.query.get_or_404(student_id)
        
        if 'name' in data:
            student.name = data['name']
        
        db.session.commit()
        
        return jsonify({
            'success': True,
            'message': 'Student updated successfully',
            'student': {
                'id': student.id,
                'name': student.name,
                'enrollment_number': student.enrollment_number
            }
        })
        
    except Exception as e:
        db.session.rollback()
        print(f"❌ Error updating student: {str(e)}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


# =======================================================
#   API: DELETE STUDENT
# =======================================================
@app.route("/api/delete-student/<int:student_id>", methods=["DELETE"])
@login_required
def delete_student(student_id):
    """Delete a student and all related data"""
    try:
        student = Student.query.get_or_404(student_id)
        enrollment_number = student.enrollment_number
        
        FaceEncoding.query.filter_by(student_id=student_id).delete()
        Attendance.query.filter_by(student_id=student_id).delete()
        db.session.delete(student)
        db.session.commit()
        
        student_folder = os.path.join(STUDENTS_DIR, enrollment_number)
        if os.path.exists(student_folder):
            import shutil
            shutil.rmtree(student_folder)
            print(f"🗑️ Deleted student folder: {student_folder}")
        
        retrain_complete_model()
        
        return jsonify({
            'success': True,
            'message': f'Student {enrollment_number} deleted successfully'
        })
        
    except Exception as e:
        db.session.rollback()
        print(f"❌ Error deleting student: {str(e)}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


# =======================================================
#   API: VERIFY MODEL
# =======================================================
@app.route("/api/verify-model", methods=["GET"])
@login_required
def verify_model():
    """Verify model integrity"""
    try:
        model_exists = os.path.exists(MODEL_PATH)
        model_size = os.path.getsize(MODEL_PATH) if model_exists else 0
        
        model_data = None
        encodings_count = 0
        if model_exists:
            try:
                with open(MODEL_PATH, "rb") as f:
                    model_data = pickle.load(f)
                encodings_count = len(model_data.get('encodings', []))
            except:
                pass
        
        with app.app_context():
            db_students = Student.query.count()
            db_encodings = FaceEncoding.query.count()
        
        return jsonify({
            "success": True,
            "model": {
                "file_exists": model_exists,
                "file_size": model_size,
                "encodings_count": encodings_count,
                "is_valid": model_data is not None
            },
            "database": {
                "students_count": db_students,
                "encodings_count": db_encodings
            },
            "paths": {
                "model_path": MODEL_PATH,
                "server_dir": SERVER_DIR,
                "students_dir": STUDENTS_DIR
            },
            "current_time_ist": get_indian_time().strftime("%Y-%m-%d %H:%M:%S")
        })
        
    except Exception as e:
        return jsonify({"success": False, "message": str(e)}), 500


# =======================================================
#   INITIALIZE SYSTEM
# =======================================================
def initialize_system():
    """Initialize database and check model status"""
    print("=" * 50)
    print("🎯 FACE ATTENDANCE MANAGEMENT SYSTEM")
    print("=" * 50)
    
    # Install pytz if not available
    try:
        import pytz
        print("✅ pytz timezone library loaded")
    except ImportError:
        print("⚠️ pytz not installed. Installing...")
        import subprocess
        import sys
        subprocess.check_call([sys.executable, "-m", "pip", "install", "pytz"])
        import pytz
        print("✅ pytz installed successfully")
    
    with app.app_context():
        db.create_all()
        initialize_admin_user()
        
        model_data = load_existing_model()
        student_count = Student.query.count()
        encoding_count = FaceEncoding.query.count()
        
        current_time_ist = get_indian_time()
        
        print(f"📊 System Initialization:")
        print(f"   • Base Directory: {BASE_DIR}")
        print(f"   • Server Directory: {SERVER_DIR}")
        print(f"   • Database: {'✅ Connected' if student_count >= 0 else '❌ Error'}")
        print(f"   • Total Students in DB: {student_count}")
        print(f"   • Total Face Encodings in DB: {encoding_count}")
        print(f"   • Total Encodings in Model: {len(model_data['encodings'])}")
        print(f"   • Model File: {'✅ Exists' if os.path.exists(MODEL_PATH) else '⚠️ Not found'}")
        print(f"   • Authentication: ✅ Ready (admin/admin123)")
        print(f"   • Current Time (IST): {current_time_ist.strftime('%Y-%m-%d %H:%M:%S')}")
        
        if encoding_count > 0 and len(model_data['encodings']) == 0:
            print(f"\n🔄 Initial model training needed...")
            try:
                total_encodings = retrain_complete_model()
                print(f"✅ Initial model trained with {total_encodings} encodings")
            except Exception as e:
                print(f"❌ Initial model training failed: {e}")
    
    print("\n🔐 Login required to access the system")
    print("📌 Default credentials: admin / admin123")
    print("🌐 Sign in at: http://127.0.0.1:5000/sign-in")
    print("=" * 50)


# =======================================================
#   RUN SERVER
# =======================================================
if __name__ == "__main__":
    initialize_system()
    app.run(debug=True, host='127.0.0.1', port=5000)