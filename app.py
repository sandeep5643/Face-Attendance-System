# from flask import Flask, request, jsonify, send_from_directory, session, redirect, url_for
# from flask_sqlalchemy import SQLAlchemy
# from flask_cors import CORS
# from functools import wraps
# import os
# import base64
# import face_recognition
# import pickle
# import numpy as np
# from datetime import datetime, timedelta
# import hashlib

# # ========== PROJECT PATHS CONFIGURATION ==========
# BASE_DIR = os.path.dirname(os.path.abspath(__file__))
# SERVER_DIR = os.path.join(BASE_DIR, "server")
# STUDENTS_DIR = os.path.join(SERVER_DIR, "students")
# MODEL_PATH = os.path.join(SERVER_DIR, "trained_model.pkl")
# DATABASE_PATH = os.path.join(SERVER_DIR, "students.db")
# ADMIN_DB_PATH = os.path.join(SERVER_DIR, "admin_users.db")

# # Create necessary directories
# os.makedirs(STUDENTS_DIR, exist_ok=True)
# os.makedirs(SERVER_DIR, exist_ok=True)

# # ========== FLASK APP SETUP ==========
# app = Flask(__name__, static_folder='static', template_folder='static')
# app.config['SECRET_KEY'] = 'face-attendance-system-secret-key-2025'
# app.config['SESSION_TYPE'] = 'filesystem'
# app.config['PERMANENT_SESSION_LIFETIME'] = timedelta(hours=24)
# CORS(app, supports_credentials=True)

# # ========== DATABASE SETUP ==========
# # We'll use separate SQLAlchemy instances for different databases
# app.config["SQLALCHEMY_DATABASE_URI"] = f"sqlite:///{DATABASE_PATH}"
# app.config["SQLALCHEMY_BINDS"] = {
#     'admin': f"sqlite:///{ADMIN_DB_PATH}"
# }
# app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

# db = SQLAlchemy(app)

# # ========== DATABASE MODELS ==========
# # We'll handle admin user differently since bind might not work
# class AdminUser(db.Model):
#     __bind_key__ = 'admin'
#     __tablename__ = 'admin_users'
    
#     id = db.Column(db.Integer, primary_key=True)
#     username = db.Column(db.String(80), unique=True, nullable=False)
#     email = db.Column(db.String(120), unique=True, nullable=False)
#     password_hash = db.Column(db.String(200), nullable=False)
#     full_name = db.Column(db.String(200))
#     role = db.Column(db.String(50), default='admin')
#     is_active = db.Column(db.Boolean, default=True)
#     last_login = db.Column(db.DateTime)
#     created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
#     def set_password(self, password):
#         self.password_hash = hashlib.sha256(password.encode()).hexdigest()
    
#     def check_password(self, password):
#         return self.password_hash == hashlib.sha256(password.encode()).hexdigest()

# class Student(db.Model):
#     id = db.Column(db.Integer, primary_key=True)
#     name = db.Column(db.String(200), nullable=False)
#     enrollment_number = db.Column(db.String(100), unique=True, nullable=False)
#     created_at = db.Column(db.DateTime, default=datetime.utcnow)

# class FaceEncoding(db.Model):
#     id = db.Column(db.Integer, primary_key=True)
#     student_id = db.Column(db.Integer, db.ForeignKey("student.id"))
#     encoding = db.Column(db.PickleType, nullable=False)

# class Attendance(db.Model):
#     id = db.Column(db.Integer, primary_key=True)
#     student_id = db.Column(db.Integer, db.ForeignKey("student.id"), nullable=False)
#     subject = db.Column(db.String(100), nullable=False)
#     date = db.Column(db.String(20), nullable=False)
#     time = db.Column(db.String(20), nullable=False)
#     marked_at = db.Column(db.DateTime, default=datetime.utcnow)
#     confidence = db.Column(db.Float, nullable=False)
#     status = db.Column(db.String(20), default="Present")
    
#     student = db.relationship('Student', backref='attendances')


# # ========== AUTHENTICATION DECORATOR ==========
# def login_required(f):
#     @wraps(f)
#     def decorated_function(*args, **kwargs):
#         if 'user_id' not in session:
#             # Allow access to sign-in page
#             if request.endpoint == 'serve_sign_in':
#                 return f(*args, **kwargs)
#             return redirect(url_for('serve_sign_in'))
#         return f(*args, **kwargs)
#     return decorated_function


# # ========== SIMPLIFIED ADMIN USER MANAGEMENT ==========
# def initialize_admin_user():
#     """Create default admin user if not exists"""
#     with app.app_context():
#         try:
#             # First, create all tables (including admin_users in main database)
#             db.create_all()
            
#             # Check if admin user exists
#             admin_exists = AdminUser.query.filter_by(username='admin').first()
            
#             if not admin_exists:
#                 # Create default admin
#                 admin = AdminUser(
#                     username='admin',
#                     email='admin@faceattendance.com',
#                     full_name='System Administrator',
#                     role='super_admin',
#                     is_active=True
#                 )
#                 admin.set_password('admin123')
                
#                 db.session.add(admin)
#                 db.session.commit()
#                 print("✅ Default admin user created: admin/admin123")
#             else:
#                 print("✅ Admin user already exists")
                
#         except Exception as e:
#             print(f"⚠️ Warning: Could not create admin table: {e}")
#             print("⚠️ Using simple session-based authentication instead")


# # ========== MODEL TRAINING FUNCTIONS ==========
# def load_existing_model():
#     """Load existing trained model if exists"""
#     if os.path.exists(MODEL_PATH):
#         try:
#             with open(MODEL_PATH, "rb") as f:
#                 model_data = pickle.load(f)
#             print(f"✅ Loaded existing model with {len(model_data.get('encodings', []))} encodings")
#             return model_data
#         except Exception as e:
#             print(f"❌ Error loading model: {e}")
#     return {"encodings": [], "names": [], "student_ids": []}


# def save_trained_model(model_data):
#     """Save trained model to file"""
#     with open(MODEL_PATH, "wb") as f:
#         pickle.dump(model_data, f)
#     print(f"💾 Model saved with {len(model_data['encodings'])} encodings")


# def update_model_with_new_student(student_id, enrollment_number, new_encodings):
#     """Update trained model with new student's encodings"""
#     model_data = load_existing_model()
    
#     for encoding in new_encodings:
#         model_data["encodings"].append(encoding)
#         model_data["names"].append(enrollment_number)
#         model_data["student_ids"].append(student_id)
    
#     save_trained_model(model_data)
#     return len(new_encodings)


# def retrain_complete_model():
#     """Retrain complete model from all students in database"""
#     with app.app_context():
#         students = Student.query.all()
#         model_data = {"encodings": [], "names": [], "student_ids": []}
        
#         total_encodings = 0
#         for student in students:
#             face_encodings = FaceEncoding.query.filter_by(student_id=student.id).all()
#             for face in face_encodings:
#                 model_data["encodings"].append(face.encoding)
#                 model_data["names"].append(student.enrollment_number)
#                 model_data["student_ids"].append(student.id)
#                 total_encodings += 1
        
#         save_trained_model(model_data)
#         return total_encodings


# # =======================================================
# #   AUTHENTICATION ROUTES
# # =======================================================
# @app.route("/api/login", methods=["POST"])
# def login():
#     """Authenticate user"""
#     try:
#         data = request.get_json()
#         username = data.get('username')
#         password = data.get('password')
        
#         if not username or not password:
#             return jsonify({
#                 "status": "error",
#                 "message": "Username and password are required"
#             }), 400
        
#         # SIMPLIFIED AUTHENTICATION - Using fixed admin credentials
#         # In production, you should use database-based authentication
        
#         # Check for default admin credentials
#         if username == 'admin' and password == 'admin123':
#             # Create session with admin data
#             session['user_id'] = 1
#             session['username'] = 'admin'
#             session['email'] = 'admin@faceattendance.com'
#             session['full_name'] = 'System Administrator'
#             session['role'] = 'super_admin'
#             session['logged_in'] = True
            
#             return jsonify({
#                 "status": "success",
#                 "message": "Login successful",
#                 "user": {
#                     "id": 1,
#                     "username": 'admin',
#                     "email": 'admin@faceattendance.com',
#                     "full_name": 'System Administrator',
#                     "role": 'super_admin'
#                 }
#             })
        
#         # Try to find user in database (if AdminUser table exists)
#         try:
#             user = AdminUser.query.filter(
#                 (AdminUser.username == username) | (AdminUser.email == username)
#             ).first()
            
#             if user and user.check_password(password):
#                 # Update last login
#                 user.last_login = datetime.utcnow()
#                 db.session.commit()
                
#                 # Create session
#                 session['user_id'] = user.id
#                 session['username'] = user.username
#                 session['email'] = user.email
#                 session['full_name'] = user.full_name
#                 session['role'] = user.role
#                 session['logged_in'] = True
                
#                 return jsonify({
#                     "status": "success",
#                     "message": "Login successful",
#                     "user": {
#                         "id": user.id,
#                         "username": user.username,
#                         "email": user.email,
#                         "full_name": user.full_name,
#                         "role": user.role
#                     }
#                 })
#         except:
#             pass  # If AdminUser table doesn't exist, fall back to default
        
#         # If no user found
#         return jsonify({
#             "status": "error",
#             "message": "Invalid username or password"
#         }), 401
        
#     except Exception as e:
#         print(f"❌ Login error: {str(e)}")
#         return jsonify({
#             "status": "error",
#             "message": "Internal server error"
#         }), 500


# @app.route("/api/check-session", methods=["GET"])
# def check_session():
#     """Check if user is logged in"""
#     if 'user_id' in session:
#         return jsonify({
#             "status": "success",
#             "logged_in": True,
#             "user": {
#                 "id": session.get('user_id'),
#                 "username": session.get('username'),
#                 "email": session.get('email'),
#                 "full_name": session.get('full_name'),
#                 "role": session.get('role')
#             }
#         })
#     else:
#         return jsonify({
#             "status": "success",
#             "logged_in": False
#         })


# @app.route("/logout")
# def logout():
#     """Logout user"""
#     session.clear()
#     return redirect(url_for('serve_sign_in'))


# # =======================================================
# #   FRONTEND ROUTES (PROTECTED)
# # =======================================================
# @app.route('/')
# @login_required
# def home():
#     """Serve main index page (protected)"""
#     return send_from_directory('static', 'index.html')


# @app.route('/dashboard')
# @login_required
# def serve_dashboard():
#     """Serve dashboard page (protected)"""
#     return send_from_directory('static', 'index.html')


# @app.route('/mark-attendance')
# @login_required
# def serve_mark_attendance():
#     """Serve mark attendance page (protected)"""
#     return send_from_directory('static', 'mark-attendance.html')


# @app.route('/register-student')
# @login_required
# def serve_register_student():
#     """Serve register student page (protected)"""
#     return send_from_directory('static', 'register-student.html')


# @app.route('/sign-in')
# def serve_sign_in():
#     """Serve sign in page (public)"""
#     # If already logged in, redirect to dashboard
#     if 'user_id' in session:
#         return redirect(url_for('serve_dashboard'))
#     return send_from_directory('static', 'sign-in.html')


# @app.route('/view-students')
# @login_required
# def serve_view_students():
#     """Serve view students page (protected)"""
#     return send_from_directory('static', 'view-student.html')


# @app.route('/<path:filename>')
# def serve_static_files(filename):
#     """Serve all static files (CSS, JS, images)"""
#     return send_from_directory('static', filename)


# # =======================================================
# #   API: REGISTER STUDENT (WITH AUTO TRAINING)
# # =======================================================
# @app.route("/api/register-student", methods=["POST"])
# @login_required
# def register_student():
#     data = request.get_json()

#     name = data.get("name")
#     enrollment = data.get("enrollment_number")
#     images = data.get("face_images")

#     if not name or not enrollment:
#         return jsonify({"success": False, "message": "Missing name or enrollment number"}), 400

#     if not images or len(images) < 15:
#         return jsonify({"success": False, "message": "At least 15 images are required"}), 400

#     try:
#         existing_student = Student.query.filter_by(enrollment_number=enrollment).first()
#         if existing_student:
#             return jsonify({"success": False, "message": "Enrollment already exists"}), 400

#         student = Student(name=name, enrollment_number=enrollment)
#         db.session.add(student)
#         db.session.commit()

#         student_folder = os.path.join(STUDENTS_DIR, enrollment)
#         os.makedirs(student_folder, exist_ok=True)

#         new_encodings = []
#         successful_encodings = 0
        
#         for i, img in enumerate(images):
#             try:
#                 img_data = img.split(",")[1] if "," in img else img
#                 img_bytes = base64.b64decode(img_data)

#                 img_path = os.path.join(student_folder, f"{i+1}.jpg")
#                 with open(img_path, "wb") as f:
#                     f.write(img_bytes)

#                 image_np = face_recognition.load_image_file(img_path)
#                 encodings = face_recognition.face_encodings(image_np)

#                 if len(encodings) == 0:
#                     print(f"⚠️ No face found in image {i+1}")
#                     continue

#                 encoding = encodings[0]
#                 new_encodings.append(encoding)
#                 successful_encodings += 1

#                 face_encoding = FaceEncoding(student_id=student.id, encoding=encoding)
#                 db.session.add(face_encoding)

#             except Exception as e:
#                 print(f"❌ Error processing image {i+1}: {str(e)}")
#                 continue

#         db.session.commit()
        
#         if successful_encodings == 0:
#             db.session.delete(student)
#             db.session.commit()
#             return jsonify({"success": False, "message": "No faces detected in any images"}), 400
        
#         trained_count = update_model_with_new_student(student.id, enrollment, new_encodings)
        
#         return jsonify({
#             "success": True,
#             "message": f"Student registered successfully. Model updated with {successful_encodings} face encodings.",
#             "student_id": student.id,
#             "encodings_added": successful_encodings,
#             "model_updated": True
#         })
        
#     except Exception as e:
#         db.session.rollback()
#         print(f"🔥 Registration error: {str(e)}")
#         return jsonify({"success": False, "message": f"Registration failed: {str(e)}"}), 500


# # =======================================================
# #   ADDITIONAL APIs FOR MODEL MANAGEMENT (PROTECTED)
# # =======================================================
# @app.route("/api/retrain-model", methods=["POST"])
# @login_required
# def retrain_model():
#     try:
#         total_encodings = retrain_complete_model()
#         return jsonify({
#             "success": True,
#             "message": f"Model retrained successfully with {total_encodings} encodings",
#             "total_encodings": total_encodings
#         })
#     except Exception as e:
#         return jsonify({"success": False, "message": f"Retraining failed: {str(e)}"}), 500


# @app.route("/api/model-status", methods=["GET"])
# @login_required
# def model_status():
#     try:
#         model_data = load_existing_model()
#         with app.app_context():
#             student_count = Student.query.count()
        
#         return jsonify({
#             "success": True,
#             "model_exists": len(model_data["encodings"]) > 0,
#             "total_students": student_count,
#             "total_encodings": len(model_data["encodings"]),
#             "unique_students_in_model": len(set(model_data["student_ids"])) if model_data.get("student_ids") else 0
#         })
#     except Exception as e:
#         return jsonify({"success": False, "message": f"Error checking model: {str(e)}"}), 500


# @app.route("/api/test-recognition", methods=["POST"])
# @login_required
# def test_recognition():
#     try:
#         model_data = load_existing_model()
        
#         if len(model_data["encodings"]) == 0:
#             return jsonify({"success": False, "message": "No trained model found"}), 400
        
#         data = request.get_json()
#         test_image = data.get("face_image")
        
#         if not test_image:
#             return jsonify({"success": False, "message": "No test image provided"}), 400
        
#         img_data = test_image.split(",")[1] if "," in test_image else test_image
#         img_bytes = base64.b64decode(img_data)
        
#         temp_path = os.path.join(BASE_DIR, "temp_test.jpg")
#         with open(temp_path, "wb") as f:
#             f.write(img_bytes)
        
#         test_image_np = face_recognition.load_image_file(temp_path)
#         test_encodings = face_recognition.face_encodings(test_image_np)
        
#         if len(test_encodings) == 0:
#             if os.path.exists(temp_path):
#                 os.remove(temp_path)
#             return jsonify({"success": False, "message": "No face found in test image"}), 400
        
#         test_encoding = test_encodings[0]
        
#         face_distances = face_recognition.face_distance(model_data["encodings"], test_encoding)
        
#         best_match_index = np.argmin(face_distances)
#         best_distance = face_distances[best_match_index]
#         best_match_name = model_data["names"][best_match_index]
#         best_match_student_id = model_data["student_ids"][best_match_index]
        
#         student = None
#         with app.app_context():
#             student = Student.query.get(best_match_student_id)
        
#         if os.path.exists(temp_path):
#             os.remove(temp_path)
        
#         return jsonify({
#             "success": True,
#             "recognized": best_distance < 0.6,
#             "student_name": student.name if student else None,
#             "enrollment_number": best_match_name,
#             "confidence": 1 - best_distance,
#             "distance": float(best_distance),
#             "threshold": 0.6
#         })
        
#     except Exception as e:
#         temp_path = os.path.join(BASE_DIR, "temp_test.jpg")
#         if os.path.exists(temp_path):
#             os.remove(temp_path)
#         print(f"❌ Recognition error: {str(e)}")
#         return jsonify({"success": False, "message": f"Recognition test failed: {str(e)}"}), 500


# # =======================================================
# #   API: MARK ATTENDANCE (REAL-TIME FACE RECOGNITION)
# # =======================================================
# @app.route("/api/mark-attendance", methods=["POST"])
# @login_required
# def mark_attendance():
#     try:
#         data = request.get_json()
        
#         subject = data.get("subject", "General")
#         date = data.get("date", datetime.now().strftime("%Y-%m-%d"))
#         time = data.get("time", datetime.now().strftime("%H:%M:%S"))
#         face_image = data.get("face_image")
        
#         if not face_image:
#             return jsonify({"success": False, "message": "No face image provided"}), 400
        
#         model_data = load_existing_model()
        
#         if len(model_data["encodings"]) == 0:
#             return jsonify({"success": False, "message": "No trained model found. Please register students first."}), 400
        
#         img_data = face_image.split(",")[1] if "," in face_image else face_image
#         img_bytes = base64.b64decode(img_data)
        
#         temp_filename = f"temp_attendance_{datetime.now().timestamp()}.jpg"
#         temp_path = os.path.join(BASE_DIR, temp_filename)
#         with open(temp_path, "wb") as f:
#             f.write(img_bytes)
        
#         test_image = face_recognition.load_image_file(temp_path)
#         test_encodings = face_recognition.face_encodings(test_image)
        
#         if len(test_encodings) == 0:
#             if os.path.exists(temp_path):
#                 os.remove(temp_path)
#             return jsonify({"success": False, "message": "No face detected in image"}), 400
        
#         test_encoding = test_encodings[0]
        
#         face_distances = face_recognition.face_distance(model_data["encodings"], test_encoding)
#         best_match_index = np.argmin(face_distances)
#         best_distance = face_distances[best_match_index]
        
#         recognition_threshold = 0.6
        
#         if best_distance < recognition_threshold:
#             recognized_enrollment = model_data["names"][best_match_index]
#             student_id = model_data["student_ids"][best_match_index]
            
#             with app.app_context():
#                 student = Student.query.get(student_id)
                
#                 if student:
#                     attendance = Attendance(
#                         student_id=student.id,
#                         subject=subject,
#                         date=date,
#                         time=time,
#                         confidence=float(1 - best_distance),
#                         status="Present"
#                     )
#                     db.session.add(attendance)
#                     db.session.commit()
                    
#                     attendance_record = {
#                         "student_id": student.id,
#                         "student_name": student.name,
#                         "enrollment_number": student.enrollment_number,
#                         "subject": subject,
#                         "date": date,
#                         "time": time,
#                         "confidence": float(1 - best_distance),
#                         "distance": float(best_distance),
#                         "status": "Present"
#                     }
                    
#                     if os.path.exists(temp_path):
#                         os.remove(temp_path)
                    
#                     return jsonify({
#                         "success": True,
#                         "recognized": True,
#                         "message": f"Attendance marked for {student.name}",
#                         "attendance_record": attendance_record
#                     })
        
#         if os.path.exists(temp_path):
#             os.remove(temp_path)
            
#         return jsonify({
#             "success": True,
#             "recognized": False,
#             "message": "Face not recognized. Please register first.",
#             "distance": float(best_distance) if 'best_distance' in locals() else 1.0,
#             "threshold": recognition_threshold
#         })
        
#     except Exception as e:
#         import glob
#         temp_pattern = os.path.join(BASE_DIR, "temp_attendance_*.jpg")
#         for f in glob.glob(temp_pattern):
#             if os.path.exists(f):
#                 os.remove(f)
                
#         print(f"❌ Attendance marking error: {str(e)}")
#         return jsonify({"success": False, "message": f"Attendance marking failed: {str(e)}"}), 500


# # =======================================================
# #   API: GET ATTENDANCE RECORDS (FOR DASHBOARD)
# # =======================================================
# @app.route("/api/get-attendance", methods=["GET"])
# @login_required
# def get_attendance():
#     """Get attendance records for dashboard"""
#     try:
#         # Get query parameters
#         limit = request.args.get('limit', default=10, type=int)
#         date_filter = request.args.get('date')
#         student_id = request.args.get('student_id')
        
#         # Build query
#         query = Attendance.query.join(Student).order_by(Attendance.marked_at.desc())
        
#         # Apply filters if provided
#         if date_filter:
#             query = query.filter(Attendance.date == date_filter)
        
#         if student_id:
#             query = query.filter(Attendance.student_id == student_id)
        
#         # Get limited records
#         attendance_records = query.limit(limit).all()
        
#         # Format response
#         attendance_list = []
#         for record in attendance_records:
#             attendance_list.append({
#                 'id': record.id,
#                 'student_id': record.student_id,
#                 'student_name': record.student.name,
#                 'enrollment_number': record.student.enrollment_number,
#                 'subject': record.subject,
#                 'date': record.date,
#                 'time': record.time,
#                 'confidence': record.confidence,
#                 'status': record.status,
#                 'marked_at': record.marked_at.isoformat() if record.marked_at else None
#             })
        
#         # Get today's attendance count
#         today = datetime.now().strftime("%Y-%m-%d")
#         today_count = Attendance.query.filter(Attendance.date == today).count()
        
#         return jsonify({
#             'success': True,
#             'attendance': attendance_list,
#             'total_records': len(attendance_list),
#             'today_records': today_count
#         })
        
#     except Exception as e:
#         print(f"❌ Error in get_attendance: {str(e)}")
#         return jsonify({
#             'success': False,
#             'error': str(e),
#             'attendance': [],
#             'today_records': 0
#         }), 500


# # =======================================================
# #   API: GET STUDENTS LIST
# # =======================================================
# @app.route("/api/get-students", methods=["GET"])
# @login_required
# def get_students():
#     """Get all registered students"""
#     try:
#         students = Student.query.all()
        
#         students_list = []
#         for student in students:
#             # Count face encodings for this student
#             face_count = FaceEncoding.query.filter_by(student_id=student.id).count()
            
#             # Count attendance records
#             attendance_count = Attendance.query.filter_by(student_id=student.id).count()
            
#             students_list.append({
#                 'id': student.id,
#                 'name': student.name,
#                 'enrollment_number': student.enrollment_number,
#                 'created_at': student.created_at.isoformat() if student.created_at else None,
#                 'has_face_images': face_count > 0,
#                 'face_encodings_count': face_count,
#                 'total_attendance': attendance_count,
#                 'total_attendance_records': attendance_count
#             })
        
#         return jsonify({
#             'success': True,
#             'students': students_list,
#             'total': len(students_list)
#         })
        
#     except Exception as e:
#         print(f"❌ Error in get_students: {str(e)}")
#         return jsonify({
#             'success': False,
#             'error': str(e),
#             'students': []
#         }), 500


# # =======================================================
# #   API: GET SINGLE STUDENT DETAILS
# # =======================================================
# @app.route("/api/get-student/<int:student_id>", methods=["GET"])
# @login_required
# def get_student(student_id):
#     """Get detailed information about a specific student"""
#     try:
#         student = Student.query.get_or_404(student_id)
        
#         # Get face encodings count
#         face_count = FaceEncoding.query.filter_by(student_id=student.id).count()
        
#         # Get attendance count
#         attendance_count = Attendance.query.filter_by(student_id=student.id).count()
        
#         # Check if student folder exists
#         student_folder = os.path.join(STUDENTS_DIR, student.enrollment_number)
#         folder_exists = os.path.exists(student_folder)
        
#         # Get preview of face images
#         face_images_preview = []
#         if folder_exists:
#             try:
#                 for i in range(1, min(4, face_count) + 1):
#                     img_path = os.path.join(student_folder, f"{i}.jpg")
#                     if os.path.exists(img_path):
#                         with open(img_path, "rb") as img_file:
#                             img_data = base64.b64encode(img_file.read()).decode('utf-8')
#                             face_images_preview.append(f"data:image/jpeg;base64,{img_data}")
#             except:
#                 pass
        
#         student_data = {
#             'id': student.id,
#             'name': student.name,
#             'enrollment_number': student.enrollment_number,
#             'created_at': student.created_at.isoformat() if student.created_at else None,
#             'face_encodings_count': face_count,
#             'total_attendance_records': attendance_count,
#             'folder_exists': folder_exists,
#             'face_images_preview': face_images_preview[:3]  # Limit to 3 preview images
#         }
        
#         return jsonify({
#             'success': True,
#             'student': student_data
#         })
        
#     except Exception as e:
#         print(f"❌ Error in get_student: {str(e)}")
#         return jsonify({
#             'success': False,
#             'error': str(e)
#         }), 404


# # =======================================================
# #   API: UPDATE STUDENT
# # =======================================================
# @app.route("/api/update-student/<int:student_id>", methods=["PUT"])
# @login_required
# def update_student(student_id):
#     """Update student information"""
#     try:
#         data = request.get_json()
#         student = Student.query.get_or_404(student_id)
        
#         if 'name' in data:
#             student.name = data['name']
        
#         db.session.commit()
        
#         return jsonify({
#             'success': True,
#             'message': 'Student updated successfully',
#             'student': {
#                 'id': student.id,
#                 'name': student.name,
#                 'enrollment_number': student.enrollment_number
#             }
#         })
        
#     except Exception as e:
#         db.session.rollback()
#         print(f"❌ Error updating student: {str(e)}")
#         return jsonify({
#             'success': False,
#             'error': str(e)
#         }), 500


# # =======================================================
# #   API: DELETE STUDENT
# # =======================================================
# @app.route("/api/delete-student/<int:student_id>", methods=["DELETE"])
# @login_required
# def delete_student(student_id):
#     """Delete a student and all related data"""
#     try:
#         student = Student.query.get_or_404(student_id)
#         enrollment_number = student.enrollment_number
        
#         # Delete face encodings from database
#         FaceEncoding.query.filter_by(student_id=student_id).delete()
        
#         # Delete attendance records
#         Attendance.query.filter_by(student_id=student_id).delete()
        
#         # Delete student from database
#         db.session.delete(student)
#         db.session.commit()
        
#         # Delete student folder
#         student_folder = os.path.join(STUDENTS_DIR, enrollment_number)
#         if os.path.exists(student_folder):
#             import shutil
#             shutil.rmtree(student_folder)
#             print(f"🗑️ Deleted student folder: {student_folder}")
        
#         # Retrain model to remove student's encodings
#         retrain_complete_model()
        
#         return jsonify({
#             'success': True,
#             'message': f'Student {enrollment_number} deleted successfully'
#         })
        
#     except Exception as e:
#         db.session.rollback()
#         print(f"❌ Error deleting student: {str(e)}")
#         return jsonify({
#             'success': False,
#             'error': str(e)
#         }), 500




# # =======================================================
# #   OTHER PROTECTED APIs
# # =======================================================
# # [Your existing API routes...]

# # =======================================================
# #   INITIALIZE SYSTEM
# # =======================================================
# def initialize_system():
#     """Initialize database and check model status"""
#     print("=" * 50)
#     print("🎯 FACE ATTENDANCE MANAGEMENT SYSTEM")
#     print("=" * 50)
    
#     with app.app_context():
#         # Create all tables
#         db.create_all()
        
#         # Initialize admin user (simplified)
#         initialize_admin_user()
        
#         # Check model status
#         model_data = load_existing_model()
#         student_count = Student.query.count()
        
#         print(f"📊 System Initialization:")
#         print(f"   • Base Directory: {BASE_DIR}")
#         print(f"   • Server Directory: {SERVER_DIR}")
#         print(f"   • Database: {'✅ Connected' if student_count >= 0 else '❌ Error'}")
#         print(f"   • Total Students in DB: {student_count}")
#         print(f"   • Total Encodings in Model: {len(model_data['encodings'])}")
#         print(f"   • Model File: {'✅ Exists' if os.path.exists(MODEL_PATH) else '⚠️ Not found'}")
#         print(f"   • Authentication: ✅ Ready (admin/admin123)")
    
#     print("\n🔐 Login required to access the system")
#     print("📌 Default credentials: admin / admin123")
#     print("🌐 Sign in at: http://127.0.0.1:5000/sign-in")
#     print("=" * 50)


# # =======================================================
# #   RUN SERVER
# # =======================================================
# if __name__ == "__main__":
#     initialize_system()
#     app.run(debug=True, host='127.0.0.1', port=5000)




import sys
print(f"Python version: {sys.version}")

try:
    import numpy as np
    print("NumPy imported successfully")
except ImportError:
    print("NumPy not available - using dummy")
    # Create dummy numpy functions if needed

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
# We'll use separate SQLAlchemy instances for different databases
app.config["SQLALCHEMY_DATABASE_URI"] = f"sqlite:///{DATABASE_PATH}"
app.config["SQLALCHEMY_BINDS"] = {
    'admin': f"sqlite:///{ADMIN_DB_PATH}"
}
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

db = SQLAlchemy(app)

# ========== DATABASE MODELS ==========
# We'll handle admin user differently since bind might not work
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
            # Allow access to sign-in page
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
            # First, create all tables (including admin_users in main database)
            db.create_all()
            
            # Check if admin user exists
            admin_exists = AdminUser.query.filter_by(username='admin').first()
            
            if not admin_exists:
                # Create default admin
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
    with open(MODEL_PATH, "wb") as f:
        pickle.dump(model_data, f)
    print(f"💾 Model saved with {len(model_data['encodings'])} encodings")


def update_model_with_new_student(student_id, enrollment_number, new_encodings):
    """Update trained model with new student's encodings"""
    model_data = load_existing_model()
    
    for encoding in new_encodings:
        model_data["encodings"].append(encoding)
        model_data["names"].append(enrollment_number)
        model_data["student_ids"].append(student_id)
    
    save_trained_model(model_data)
    return len(new_encodings)


def retrain_complete_model():
    """Retrain complete model from all students in database"""
    with app.app_context():
        students = Student.query.all()
        model_data = {"encodings": [], "names": [], "student_ids": []}
        
        total_encodings = 0
        for student in students:
            face_encodings = FaceEncoding.query.filter_by(student_id=student.id).all()
            for face in face_encodings:
                model_data["encodings"].append(face.encoding)
                model_data["names"].append(student.enrollment_number)
                model_data["student_ids"].append(student.id)
                total_encodings += 1
        
        save_trained_model(model_data)
        return total_encodings


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
        
        # SIMPLIFIED AUTHENTICATION - Using fixed admin credentials
        # In production, you should use database-based authentication
        
        # Check for default admin credentials
        if username == 'admin' and password == 'admin123':
            # Create session with admin data
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
        
        # Try to find user in database (if AdminUser table exists)
        try:
            user = AdminUser.query.filter(
                (AdminUser.username == username) | (AdminUser.email == username)
            ).first()
            
            if user and user.check_password(password):
                # Update last login
                user.last_login = datetime.utcnow()
                db.session.commit()
                
                # Create session
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
            pass  # If AdminUser table doesn't exist, fall back to default
        
        # If no user found
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
    """Serve main index page (protected)"""
    return send_from_directory('static', 'index.html')


@app.route('/dashboard')
@login_required
def serve_dashboard():
    """Serve dashboard page (protected)"""
    return send_from_directory('static', 'index.html')


@app.route('/mark-attendance')
@login_required
def serve_mark_attendance():
    """Serve mark attendance page (protected)"""
    return send_from_directory('static', 'mark-attendance.html')


@app.route('/register-student')
@login_required
def serve_register_student():
    """Serve register student page (protected)"""
    return send_from_directory('static', 'register-student.html')


@app.route('/sign-in')
def serve_sign_in():
    """Serve sign in page (public)"""
    # If already logged in, redirect to dashboard
    if 'user_id' in session:
        return redirect(url_for('serve_dashboard'))
    return send_from_directory('static', 'sign-in.html')


@app.route('/view-students')
@login_required
def serve_view_students():
    """Serve view students page (protected)"""
    return send_from_directory('static', 'view-student.html')


@app.route('/<path:filename>')
def serve_static_files(filename):
    """Serve all static files (CSS, JS, images)"""
    return send_from_directory('static', filename)


# =======================================================
#   API: REGISTER STUDENT (WITH AUTO TRAINING)
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

        student = Student(name=name, enrollment_number=enrollment)
        db.session.add(student)
        db.session.commit()

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
            "model_updated": True
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
    try:
        total_encodings = retrain_complete_model()
        return jsonify({
            "success": True,
            "message": f"Model retrained successfully with {total_encodings} encodings",
            "total_encodings": total_encodings
        })
    except Exception as e:
        return jsonify({"success": False, "message": f"Retraining failed: {str(e)}"}), 500


@app.route("/api/model-status", methods=["GET"])
@login_required
def model_status():
    try:
        model_data = load_existing_model()
        with app.app_context():
            student_count = Student.query.count()
        
        return jsonify({
            "success": True,
            "model_exists": len(model_data["encodings"]) > 0,
            "total_students": student_count,
            "total_encodings": len(model_data["encodings"]),
            "unique_students_in_model": len(set(model_data["student_ids"])) if model_data.get("student_ids") else 0
        })
    except Exception as e:
        return jsonify({"success": False, "message": f"Error checking model: {str(e)}"}), 500


@app.route("/api/test-recognition", methods=["POST"])
@login_required
def test_recognition():
    try:
        model_data = load_existing_model()
        
        if len(model_data["encodings"]) == 0:
            return jsonify({"success": False, "message": "No trained model found"}), 400
        
        data = request.get_json()
        test_image = data.get("face_image")
        
        if not test_image:
            return jsonify({"success": False, "message": "No test image provided"}), 400
        
        img_data = test_image.split(",")[1] if "," in test_image else test_image
        img_bytes = base64.b64decode(img_data)
        
        temp_path = os.path.join(BASE_DIR, "temp_test.jpg")
        with open(temp_path, "wb") as f:
            f.write(img_bytes)
        
        test_image_np = face_recognition.load_image_file(temp_path)
        test_encodings = face_recognition.face_encodings(test_image_np)
        
        if len(test_encodings) == 0:
            if os.path.exists(temp_path):
                os.remove(temp_path)
            return jsonify({"success": False, "message": "No face found in test image"}), 400
        
        test_encoding = test_encodings[0]
        
        face_distances = face_recognition.face_distance(model_data["encodings"], test_encoding)
        
        best_match_index = np.argmin(face_distances)
        best_distance = face_distances[best_match_index]
        best_match_name = model_data["names"][best_match_index]
        best_match_student_id = model_data["student_ids"][best_match_index]
        
        student = None
        with app.app_context():
            student = Student.query.get(best_match_student_id)
        
        if os.path.exists(temp_path):
            os.remove(temp_path)
        
        return jsonify({
            "success": True,
            "recognized": best_distance < 0.6,
            "student_name": student.name if student else None,
            "enrollment_number": best_match_name,
            "confidence": 1 - best_distance,
            "distance": float(best_distance),
            "threshold": 0.6
        })
        
    except Exception as e:
        temp_path = os.path.join(BASE_DIR, "temp_test.jpg")
        if os.path.exists(temp_path):
            os.remove(temp_path)
        print(f"❌ Recognition error: {str(e)}")
        return jsonify({"success": False, "message": f"Recognition test failed: {str(e)}"}), 500


# =======================================================
#   API: MARK ATTENDANCE (REAL-TIME FACE RECOGNITION)
# =======================================================
@app.route("/api/mark-attendance", methods=["POST"])
@login_required
def mark_attendance():
    try:
        data = request.get_json()
        
        subject = data.get("subject", "General")
        date = data.get("date", datetime.now().strftime("%Y-%m-%d"))
        time = data.get("time", datetime.now().strftime("%H:%M:%S"))
        face_image = data.get("face_image")
        
        if not face_image:
            return jsonify({"success": False, "message": "No face image provided"}), 400
        
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
                    attendance = Attendance(
                        student_id=student.id,
                        subject=subject,
                        date=date,
                        time=time,
                        confidence=float(1 - best_distance),
                        status="Present"
                    )
                    db.session.add(attendance)
                    db.session.commit()
                    
                    attendance_record = {
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
                    
                    if os.path.exists(temp_path):
                        os.remove(temp_path)
                    
                    return jsonify({
                        "success": True,
                        "recognized": True,
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
#   API: GET ATTENDANCE RECORDS (FOR DASHBOARD)
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
                'marked_at': record.marked_at.isoformat() if record.marked_at else None
            })
        
        # Get today's attendance count
        today = datetime.now().strftime("%Y-%m-%d")
        today_count = Attendance.query.filter(Attendance.date == today).count()
        
        return jsonify({
            'success': True,
            'attendance': attendance_list,
            'total_records': len(attendance_list),
            'today_records': today_count
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
#   API: GET STUDENTS LIST
# =======================================================
@app.route("/api/get-students", methods=["GET"])
@login_required
def get_students():
    """Get all registered students"""
    try:
        students = Student.query.all()
        
        students_list = []
        for student in students:
            # Count face encodings for this student
            face_count = FaceEncoding.query.filter_by(student_id=student.id).count()
            
            # Count attendance records
            attendance_count = Attendance.query.filter_by(student_id=student.id).count()
            
            students_list.append({
                'id': student.id,
                'name': student.name,
                'enrollment_number': student.enrollment_number,
                'created_at': student.created_at.isoformat() if student.created_at else None,
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
#   API: GET SINGLE STUDENT DETAILS
# =======================================================
@app.route("/api/get-student/<int:student_id>", methods=["GET"])
@login_required
def get_student(student_id):
    """Get detailed information about a specific student"""
    try:
        student = Student.query.get_or_404(student_id)
        
        # Get face encodings count
        face_count = FaceEncoding.query.filter_by(student_id=student.id).count()
        
        # Get attendance count
        attendance_count = Attendance.query.filter_by(student_id=student.id).count()
        
        # Check if student folder exists
        student_folder = os.path.join(STUDENTS_DIR, student.enrollment_number)
        folder_exists = os.path.exists(student_folder)
        
        # Get preview of face images
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
            'face_encodings_count': face_count,
            'total_attendance_records': attendance_count,
            'folder_exists': folder_exists,
            'face_images_preview': face_images_preview[:3]  # Limit to 3 preview images
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
        
        # Delete face encodings from database
        FaceEncoding.query.filter_by(student_id=student_id).delete()
        
        # Delete attendance records
        Attendance.query.filter_by(student_id=student_id).delete()
        
        # Delete student from database
        db.session.delete(student)
        db.session.commit()
        
        # Delete student folder
        student_folder = os.path.join(STUDENTS_DIR, enrollment_number)
        if os.path.exists(student_folder):
            import shutil
            shutil.rmtree(student_folder)
            print(f"🗑️ Deleted student folder: {student_folder}")
        
        # Retrain model to remove student's encodings
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
#   OTHER PROTECTED APIs
# =======================================================
# [Your existing API routes...]

# =======================================================
#   INITIALIZE SYSTEM
# =======================================================
def initialize_system():
    """Initialize database and check model status"""
    print("=" * 50)
    print("🎯 FACE ATTENDANCE MANAGEMENT SYSTEM")
    print("=" * 50)
    
    with app.app_context():
        # Create all tables
        db.create_all()
        
        # Initialize admin user (simplified)
        initialize_admin_user()
        
        # Check model status
        model_data = load_existing_model()
        student_count = Student.query.count()
        
        print(f"📊 System Initialization:")
        print(f"   • Base Directory: {BASE_DIR}")
        print(f"   • Server Directory: {SERVER_DIR}")
        print(f"   • Database: {'✅ Connected' if student_count >= 0 else '❌ Error'}")
        print(f"   • Total Students in DB: {student_count}")
        print(f"   • Total Encodings in Model: {len(model_data['encodings'])}")
        print(f"   • Model File: {'✅ Exists' if os.path.exists(MODEL_PATH) else '⚠️ Not found'}")
        print(f"   • Authentication: ✅ Ready (admin/admin123)")
    
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