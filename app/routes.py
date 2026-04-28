import datetime
import os
import secrets
import uuid

from bson import ObjectId
from flask import Blueprint, abort, current_app, flash, make_response, redirect, render_template, request, session, url_for
from flask_login import current_user, login_required, login_user, logout_user
from werkzeug.security import check_password_hash, generate_password_hash
from werkzeug.utils import secure_filename
from app import ALLOWED_EXTENSIONS
from app.extensions import mongo
from datetime import datetime

from app.modal import Project, User, UserRole


bp = Blueprint('main', __name__)

#------------------------------------------
#---- Function: 1 | Func Allowed Files  ---
#------------------------------------------
def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS
 
def create_guest_session(mongo):
    if not session.get("guest_token"):

        token = secrets.token_hex(24)

        session["guest_token"] = token

        mongo.db.sessions.insert_one({
            "session_token": token,
            "user_id": None,   # guest
            "ip": request.remote_addr,
            "device": request.user_agent.string,
            "created_at": datetime.utcnow(),
            "expires_at": None,
            "routes": []   # store visited pages
        })



# 1. Index route: Wuxuu soo bandhigayaa page-ka iyo data-da projects-ka
@bp.route('/', methods=['GET'])
def index():
    # 1. Halkan ka hel tirada xogta (Counts)
    project_count = mongo.db.projects.count_documents({})
    user_count = mongo.db.users.count_documents({})
    contact_count = mongo.db.contacts.count_documents({})
    
    # 2. Hel xogta projects-ka sida aad hore u samaysay
    cursor = mongo.db.projects.find().sort("created_at", -1)
    projects = [Project(data) for data in cursor]
    
    # 3. U dir template-ka (index.html)
    return render_template("frontend/home/index.html", 
                           projects=projects,
                           project_count=project_count,
                           user_count=user_count,
                           contact_count=contact_count)

# 2. Contact Submit: Wuxuu qabanayaa kaliya POST request-ka
@bp.route('/contact-submit', methods=['POST'])
def contact_submit():
    # 1. Ka soo qaad xogta foomka
    name = request.form.get('name')
    email = request.form.get('email')
    subject = request.form.get('subject')
    message = request.form.get('message')

    # 2. Validation
    if not name or not email or not subject or not message:
        flash("Fadlan buuxi dhammaan meelaha bannaan!", "danger")
        return redirect(url_for('main.index') + "#contact-section")

    # 3. Diyaarinta Xogta
    contact_entry = {
        "user_id": current_user.id if current_user.is_authenticated else None,
        "name": name,
        "email": email,
        "subject": subject,
        "message": message,
        "status": "pending",
        "created_at": datetime.utcnow()
    }

    # 4. Save to MongoDB
    try:
        mongo.db.contact.insert_one(contact_entry)
        flash("Farriintaada waa la diray, mahadsanid!", "success")
    except Exception as e:
        flash("Cilad ayaa dhacday, fadlan isku day mar kale.", "danger")
        print(f"Database Error: {e}")

    # 5. Redirect ku samee home page-ka, kuna dar anchor tag (#contact-section)
    return redirect(url_for('main.index') + "#contact-section")




@bp.route('/project/<project_id>')
def single_project(project_id):
    try:
        # 1. Fetch project
        data = mongo.db.projects.find_one({"_id": ObjectId(project_id)})
        if not data:
            flash("Project-gan lama helin!", "danger")
            return redirect(url_for('main.index'))
        
        project = Project(data)
        
        # 2. Fetch owner data (Halkan ayaan ka soo helaynaa user-ka)
        owner = None
        if project.user_id:
            try:
                owner_data = mongo.db.users.find_one({"_id": ObjectId(project.user_id)})
                if owner_data:
                    owner = User(owner_data)
            except:
                owner = None # Haddii ID-gu khaldan yahay
        
        return render_template("frontend/pages/projects/single_project.html", project=project, owner=owner)
        
    except Exception as e:
        flash("Khalad ayaa dhacay.", "danger")
        return redirect(url_for('main.index'))


@bp.route('/register', methods=['GET', 'POST'])
def register():
    if current_user.is_authenticated:
        return redirect(url_for('main.dashboard'))

    if request.method == 'POST':
        username = request.form.get('username')
        email = request.form.get('email')
        password = request.form.get('password')
        confirm_password = request.form.get('password_confirmation')

        # 1. Hubi haddii passwords-ku isku mid yihiin
        if password != confirm_password:
            flash("Passwords-ka isma laha!", "danger")
            return redirect(url_for('main.register'))

        # 2. Hubi haddii user-ku horey u jiray
        if mongo.db.users.find_one({"email": email}):
            flash("Email-kan horey ayaa loo isticmaalay!", "danger")
            return redirect(url_for('main.register'))

        # 3. Role Logic
        user_count = mongo.db.users.count_documents({})
        role = UserRole.superadmin.value if user_count == 0 else UserRole.user.value

        # 4. Save
        new_user = {
            "username": username,
            "email": email,
            "password": generate_password_hash(password),
            "role": role,
            "status": False,
            "created_at": datetime.utcnow()
        }
        mongo.db.users.insert_one(new_user)
        
        flash("Diiwaangelinta way guulaysatay!", "success")
        return redirect(url_for('main.login'))

    # Wadada saxda ah ee faylkaaga:
    return render_template("backend/auth/auth-register.html")


@bp.route('/login', methods=['GET', 'POST'])
def login():
    # Haddi uu user-ku horay u soo galay, u dir dashboard-ka
    if current_user.is_authenticated:
        return redirect(url_for('main.dashboard'))

    if request.method == 'POST':
        email = request.form.get('email')
        password = request.form.get('password')
        remember = True if request.form.get('remembr_me') else False

        # 1. Ka raadi user-ka database-ka
        user_data = mongo.db.users.find_one({"email": email})

        # 2. Hubi haddii password-ku sax yahay
        if user_data and check_password_hash(user_data.get('password'), password):
            # Samee User object
            user = User(user_data) 
            
            # 3. Login u samee
            login_user(user, remember=remember)
            
            flash("Si guul leh ayaad u gashay dashboard-ka!", "success")
            return redirect(url_for('main.dashboard')) 
        else:
            flash("Email ama Password khaldan!", "danger")
            # Waxaan u beddelay 'auth.login' si uu ugu laabto isla boggaas
            return redirect(url_for('auth.login')) 

    return render_template("backend/auth/auth-login.html")


@bp.route("/dashboard")
@login_required
def dashboard():
    if current_user.role != 'superadmin':
        return abort(403) # ama redirect(url_for('login'))
        
    return render_template("backend/home/dashbaord.html", user=current_user)


@bp.route('/add-user', methods=['GET', 'POST'])
@login_required
def add_user():
    if current_user.role != 'superadmin':
        return abort(403) # ama redirect(url_for('login'))
        
    # 1. Halkan waa liiska waddamada (Kala soo bax database ama API)
    countries = [
        {"code": "SO", "name": "Somalia", "flag_url": "https://flagcdn.com/so.svg"},
        {"code": "KE", "name": "Kenya", "flag_url": "https://flagcdn.com/ke.svg"},
        # Ku dar inta kale...
    ]

    if request.method == 'POST':
        # Xogta ka soo qaad form-ka
        fullname = request.form.get('fullname')
        username = request.form.get('username')
        email = request.form.get('email')
        password = request.form.get('password')
        confirm_password = request.form.get('confirm_password')
        role = request.form.get('role')
        country = request.form.get('country')
        phone = request.form.get('phone')
        state = request.form.get('state')
        city = request.form.get('city')
        status = True if request.form.get('status') == '1' else False
        address = request.form.get('address')

        # Validation
        if password != confirm_password:
            flash("Passwords-ka isma laha!", "danger")
            return redirect(url_for('main.add_user'))

        if mongo.db.users.find_one({"email": email}):
            flash("Email-kan horey ayaa loo isticmaalay!", "danger")
            return redirect(url_for('main.add_user'))

        # File Upload Logic
        photo_filename = "" # Default
        if 'photo' in request.files:
            file = request.files['photo']
            if file and file.filename != '':
                filename = secure_filename(file.filename)
                # Ku keydi folder-ka uploads (Hubi inaad folder-kaas samaysay)
                upload_path = os.path.join(current_app.root_path, 'static/backend/uploads/images')
                file.save(os.path.join(upload_path, filename))
                photo_filename = filename

        # 4. Save User
        new_user = {
            "fullname": fullname,
            "username": username,
            "email": email,
            "password": generate_password_hash(password),
            "role": role,
            "country": country,
            "phone": phone,
            "state": state,
            "city": city,
            "status": status,
            "address": address,
            "photo": photo_filename,
            "created_at": datetime.utcnow()
        }
        
        mongo.db.users.insert_one(new_user)
        flash(f"User {username} si guul leh ayaa loo diiwaangeliyey!", "success")
        return redirect(url_for('main.add_user')) # Ama u dir liiska users-ka

    return render_template("backend/pages/components/users/add_user.html", countries=countries)




@bp.route('/edit-user/<user_id>', methods=['GET', 'POST'])
@login_required
def edit_user(user_id):
    if current_user.role != 'superadmin':
        return abort(403) # ama redirect(url_for('login'))
        
    # 1. Soo hel user-ka
    raw_user = mongo.db.users.find_one({"_id": ObjectId(user_id)})
    if not raw_user:
        flash("User-ka lama helin!", "danger")
        return redirect(url_for('main.index'))

    # 2. U beddel User class-ka si aad u isticmaasho user.attribute
    user = User(raw_user)

    if request.method == 'POST':
        # 3. Ururi xogta cusub
        updated_data = {
            "fullname": request.form.get('fullname'),
            "username": request.form.get('username'),
            "email": request.form.get('email'),
            "role": request.form.get('role'),
            "country": request.form.get('country'),
            "phone": request.form.get('phone'),
            "address": request.form.get('address'),
            "bio": request.form.get('bio'),
            "status": True if request.form.get('status') == '1' else False,
            "updated_at": datetime.utcnow()
        }

        # 4. Handle Photo
        if 'photo' in request.files:
            file = request.files['photo']
            if file and file.filename != '':
                # Samee folder-ka haddii uusan jirin
                upload_dir = os.path.join(current_app.root_path, 'static', 'uploads', 'users')
                os.makedirs(upload_dir, exist_ok=True)
                
                # Magaca faylka oo la badbaadiyay (unique filename)
                filename = f"{uuid.uuid4().hex}_{secure_filename(file.filename)}"
                file_path = os.path.join(upload_dir, filename)
                file.save(file_path)
                
                # Ku kaydi relative path DB-ga
                updated_data["photo"] = f"uploads/users/{filename}"

        # 5. Save to MongoDB
        mongo.db.users.update_one({"_id": ObjectId(user_id)}, {"$set": updated_data})
        flash("Macluumaadka si guul leh ayaa loo cusbooneysiiyey!", "success")
        return redirect(url_for('main.edit_user', user_id=user_id))

    # GET Request: U gudbi object-ka template-ka
    return render_template("backend/pages/components/users/edit_user.html", user=user)




@bp.route('/delete-user/<user_id>', methods=['POST'])
@login_required
def delete_user(user_id):
    if current_user.role != 'superadmin':
        return abort(403) # ama redirect(url_for('login'))
        
    # 1. Soo hel user-ka si aad u tirtirto faylka haddii loo baahdo
    user = mongo.db.users.find_one({"_id": ObjectId(user_id)})
    
    if user and 'photo' in user:
        # Faylka tirtir (Optional - haddii aad rabto inaad booska server-ka u kaydiso)
        file_path = os.path.join(os.path.dirname(current_app.root_path), 'static', user['photo'])
        if os.path.exists(file_path):
            os.remove(file_path)

    # 2. Tirtir database-ka
    mongo.db.users.delete_one({"_id": ObjectId(user_id)})
    flash("User-ka si guul leh ayaa loo tirtiray!", "success")
    return redirect(url_for('main.all_users'))


@bp.route('/all-users', methods=['GET'])
@login_required
def all_users():
    if current_user.role != 'superadmin':
        return abort(403) # ama redirect(url_for('login'))
        
    # 1. Ka soo saar dhammaan users-ka database-ka
    # .sort('-created_at') waxaa loola jeedaa inuu ku kala sooco taariikhda (ugu dambeeyay ugu horreeya)
    users_cursor = mongo.db.users.find().sort('created_at', -1)
    
    # 2. U beddel document kasta (dictionary) inuu noqdo User object
    # Tani waxay isticmaaleysaa fasalkaaga User ee aan horey uga soo hadalnay
    users = [User(user_data) for user_data in users_cursor]
    
    # 3. U dir template-ka
    return render_template('backend/pages/components/users/all_users.html', users=users)



@bp.route('/add-project', methods=['GET', 'POST'])
@login_required
def add_project():
    if current_user.role != 'superadmin':
        return abort(403) # ama redirect(url_for('login'))
        
    if request.method == 'POST':
        # 1. Deji jidka 'static' (External static folder)
        # Waxaan isticmaalaynaa "static" toos ah si uu ula jaanqaado habkaaga site_settings
        base_dir = os.path.join("static", "backend", "uploads", "projects")
        
        # --- THUMBNAIL LOGIC ---
        # Default path
        thumb_db_path = "backend/uploads/projects/thumbnails/no_image.jpg"
        image = request.files.get('thumbnail')
        
        if image and image.filename != '':
            # Unique naming
            ext = os.path.splitext(image.filename)[1]
            unique_name = f"{uuid.uuid4().hex[:8]}{ext}"
            
            save_folder = os.path.join(base_dir, 'thumbnails')
            os.makedirs(save_folder, exist_ok=True)
            
            image_path = os.path.join(save_folder, unique_name)
            image.save(image_path)
            
            # Kaydso path-ka loo isticmaalo database-ka
            thumb_db_path = f"backend/uploads/projects/thumbnails/{unique_name}"

        # --- GALLERY LOGIC ---
        gallery_db_paths = []
        gallery_files = request.files.getlist('gallery')
        
        if gallery_files:
            save_gallery = os.path.join(base_dir, 'gallery')
            os.makedirs(save_gallery, exist_ok=True)
            
            for file in gallery_files:
                if file and file.filename != '':
                    unique_name = f"{uuid.uuid4().hex[:8]}_{secure_filename(file.filename)}"
                    file_path = os.path.join(save_gallery, unique_name)
                    file.save(file_path)
                    
                    # Kaydso path-ka database-ka
                    gallery_db_paths.append(f"backend/uploads/projects/gallery/{unique_name}")

        # --- VIDEO LOGIC ---
        video_db_path = ""
        video = request.files.get('video_file')
        
        if video and video.filename != '':
            ext = os.path.splitext(video.filename)[1]
            unique_name = f"{uuid.uuid4().hex[:8]}{ext}"
            
            save_video = os.path.join(base_dir, 'videos')
            os.makedirs(save_video, exist_ok=True)
            
            video_path = os.path.join(save_video, unique_name)
            video.save(video_path)
            
            # Kaydso path-ka database-ka
            video_db_path = f"backend/uploads/projects/videos/{unique_name}"

        # 2. Save Project to MongoDB
        new_project = {
            "user_id": current_user.id,
            "title": request.form.get('title'),
            "description": request.form.get('description'),
            "thumbnail": thumb_db_path,
            "gallery": gallery_db_paths,
            "video": {
                "url": request.form.get('video_url'),
                "path": video_db_path
            },
            "social_links": {
                "github": request.form.get('github'),
                "live_demo": request.form.get('live_demo'),
                "linkedin": request.form.get('linkedin'),
                "instagram": request.form.get('instagram'),
                "facebook": request.form.get('facebook'),
                "tiktok": request.form.get('tiktok')
            },
            "created_at": datetime.utcnow()
        }
        
        mongo.db.projects.insert_one(new_project)
        flash("Project-ga si guul leh ayaa loo kaydiyay!", "success")
        return redirect(url_for('main.add_project'))

    return render_template("backend/pages/components/projects/add_project.html")



@bp.route('/edit-project/<project_id>', methods=['GET', 'POST'])
@login_required
def edit_project(project_id):
    if current_user.role != 'superadmin':
        return abort(403) # ama redirect(url_for('login'))
        
    # 1. Soo hel project-ga
    project = mongo.db.projects.find_one({"_id": ObjectId(project_id)})
    
    if not project:
        flash("Project-ga lama helin!", "danger")
        return redirect(url_for('main.all_projects'))

    if request.method == 'POST':
        base_dir = os.path.join("static", "backend", "uploads", "projects")
        
        # --- A. THUMBNAIL LOGIC ---
        new_thumb_path = project.get('thumbnail')
        image = request.files.get('thumbnail')
        
        if image and image.filename != '':
            # Tirtir kii hore
            if project.get('thumbnail') and 'no_image' not in project.get('thumbnail'):
                old_path = os.path.join(os.getcwd(), project.get('thumbnail'))
                if os.path.exists(old_path):
                    os.remove(old_path)
            
            # Kaydi kan cusub
            ext = os.path.splitext(image.filename)[1]
            unique_name = f"{uuid.uuid4().hex[:8]}{ext}"
            save_folder = os.path.join(base_dir, 'thumbnails')
            os.makedirs(save_folder, exist_ok=True)
            image_path = os.path.join(save_folder, unique_name)
            image.save(image_path)
            new_thumb_path = f"backend/uploads/projects/thumbnails/{unique_name}"

        # --- B. GALLERY LOGIC ---
        # Waxaan ka helaynaa list-ka hore, haddii ay jiraan kuwo cusub ayaan ku darnaa
        gallery_paths = project.get('gallery', [])
        gallery_files = request.files.getlist('gallery')
        
        if gallery_files and gallery_files[0].filename != '':
            save_gallery = os.path.join(base_dir, 'gallery')
            os.makedirs(save_gallery, exist_ok=True)
            
            for file in gallery_files:
                if file and file.filename != '':
                    unique_name = f"{uuid.uuid4().hex[:8]}_{secure_filename(file.filename)}"
                    file_path = os.path.join(save_gallery, unique_name)
                    file.save(file_path)
                    gallery_paths.append(f"backend/uploads/projects/gallery/{unique_name}")

        # --- C. VIDEO LOGIC ---
        video_data = project.get('video', {"url": "", "path": ""})
        video = request.files.get('video_file')
        
        if video and video.filename != '':
            # Tirtir kii hore haddii uu jiro
            if video_data.get('path'):
                old_video = os.path.join(os.getcwd(), video_data.get('path'))
                if os.path.exists(old_video):
                    os.remove(old_video)
            
            # Kaydi kan cusub
            ext = os.path.splitext(video.filename)[1]
            unique_name = f"{uuid.uuid4().hex[:8]}{ext}"
            save_video = os.path.join(base_dir, 'videos')
            os.makedirs(save_video, exist_ok=True)
            video_path = os.path.join(save_video, unique_name)
            video.save(video_path)
            video_data['path'] = f"backend/uploads/projects/videos/{unique_name}"
        
        # Update video URL haddii uu cusub yahay
        if request.form.get('video_url'):
            video_data['url'] = request.form.get('video_url')

        # --- UPDATE DATABASE ---
        updated_data = {
            "title": request.form.get('title'),
            "description": request.form.get('description'),
            "thumbnail": new_thumb_path,
            "gallery": gallery_paths,
            "video": video_data,
            "social_links": {
                "github": request.form.get('github'),
                "live_demo": request.form.get('live_demo'),
                "linkedin": request.form.get('linkedin'),
                "instagram": request.form.get('instagram'),
                "facebook": request.form.get('facebook'),
                "tiktok": request.form.get('tiktok')
            }
        }
        
        mongo.db.projects.update_one(
            {"_id": ObjectId(project_id)},
            {"$set": updated_data}
        )
        
        flash("Project-ga si guul leh ayaa loo cusboonaysiiyay!", "success")
        return redirect(url_for('main.all_projects'))

    return render_template("backend/pages/components/projects/edit_project.html", project=project)


@bp.route('/delete-project/<project_id>', methods=['POST'])
@login_required
def delete_project(project_id):
    if current_user.role != 'superadmin':
        return abort(403) # ama redirect(url_for('login'))
        
    # 1. Soo hel project-ga
    project = mongo.db.projects.find_one({"_id": ObjectId(project_id)})
    
    if not project:
        flash("Project-ga lama helin!", "danger")
        return redirect(url_for('main.all_projects'))

    # 2. Function-ka tirtirida faylasha (Helper)
    def remove_file(file_path):
        if file_path:
            # U beddel path-ka mid buuxa (absolute path)
            full_path = os.path.join(os.getcwd(), file_path)
            if os.path.exists(full_path):
                try:
                    os.remove(full_path)
                except Exception as e:
                    print(f"Error deleting file: {e}")

    # 3. Nadiifi faylasha Thumbnail-ka
    remove_file(project.get('thumbnail'))

    # 4. Nadiifi Gallery-ga
    for img_path in project.get('gallery', []):
        remove_file(img_path)

    # 5. Nadiifi Video-ga
    video_path = project.get('video', {}).get('path')
    remove_file(video_path)

    # 6. Tirtir record-ka database-ka
    mongo.db.projects.delete_one({"_id": ObjectId(project_id)})

    flash("Project-ga iyo faylashiisii waa la tirtiray!", "success")
    return redirect(url_for('main.all_projects'))



@bp.route('/all-projects', methods=['GET'])
@login_required
def all_projects():
    if current_user.role != 'superadmin':
        return abort(403) # ama redirect(url_for('login'))
        
    # 1. Ka soo saar dhammaan projects-ka database-ka, adigoo ku kala soocaya taariikhda (ugu dambeeyay ugu horreeya)
    projects_cursor = mongo.db.projects.find().sort('created_at', -1)
    
    # 2. U beddel document kasta inuu noqdo Project object
    projects = [Project(proj_data) for proj_data in projects_cursor]
    
    # 3. U dir template-ka
    return render_template('backend/pages/components/projects/all_projects.html', projects=projects)


#---------------------------------------------------
#---- Route: 70 | Dashboard - Backend Template -----
#---------------------------------------------------
@bp.route("/logout")
def logout():
    if current_user.is_authenticated:

        # Log the logout action
       

        # Only log out from Flask-Login
        logout_user()

        # ✅ Do NOT clear session or delete DB session yet
        # session.clear()  <-- remove this
        # db.session.delete(user_session)  <-- remove this

        # Flash message
        flash("You have been logged out! Your session record remains for inspection.", "success")

    # Clear remember_token cookie to prevent auto-login
    resp = make_response(redirect(url_for("main.login")))
    resp.set_cookie("remember_token", "", expires=0)
    return resp








