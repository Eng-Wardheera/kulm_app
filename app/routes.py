from collections import defaultdict
import datetime
import math
import os
import random
import secrets
import traceback
import uuid

from bson import ObjectId
from flask import Blueprint, abort, current_app, flash, make_response, redirect, render_template, request, session, url_for
from flask_login import current_user, login_required, login_user, logout_user
from werkzeug.security import check_password_hash, generate_password_hash
from werkzeug.utils import secure_filename
from app import ALLOWED_EXTENSIONS
from app.extensions import mongo
from datetime import datetime, timedelta

from app.modal import Contact, Project, User, UserRole


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

    project_count = mongo.db.projects.count_documents({})
    user_count = mongo.db.users.count_documents({})
    contact_count = mongo.db.contact.count_documents({})
    visits_count = mongo.db.sessions.count_documents({})

  # ================= LAST 7 DAYS VISITS =================
    today = datetime.utcnow()
    last_7_days = [(today - timedelta(days=i)).strftime("%Y-%m-%d") for i in range(6, -1, -1)]

    visits_map = defaultdict(int)

    sessions = mongo.db.sessions.find({
        "created_at": {
            "$gte": today - timedelta(days=7)
        }
    })

    for s in sessions:
        date_str = s.get("created_at").strftime("%Y-%m-%d")
        visits_map[date_str] += 1

    # 🔥 TOTAL ALL VISITS (e.g. 178)
    total_visits = mongo.db.sessions.count_documents({}) or 1

    visits_data = []

    for day in last_7_days:
        count = visits_map.get(day, 0)

        percent = round((count / total_visits) * 100)

        visits_data.append({
            "date": day,
            "count": count,
            "percent": percent
        })


    # Projects
    project_cursor = mongo.db.projects.find().sort("created_at", -1).limit(6)
    projects = [Project(data) for data in project_cursor]

    # Contacts
    colors = [
        "#FF6B6B", "#6BCB77", "#4D96FF", "#FFD93D",
        "#845EC2", "#FF9671", "#00C9A7", "#C34A36"
    ]

    contact_cursor = mongo.db.contact.find().sort("created_at", -1).limit(10)
    contacts = []

    for data in contact_cursor:
        contact = Contact(data)

        user = None
        photo = None

        if contact.user_id:
            user_data = mongo.db.users.find_one({"_id": ObjectId(contact.user_id)})
            if user_data:
                user = User(user_data)
                photo = user.photo

        if photo:
            contact.image = photo
            contact.initial = None
            contact.color = None
        else:
            contact.image = None
            contact.initial = (contact.name or "?")[0].upper()

            # 🎨 random color
            contact.color = random.choice(colors)

        contacts.append(contact)


    return render_template(
        "frontend/home/index.html",
        projects=projects,
        contacts=contacts,   # ✅ MUHIIM
        project_count=project_count,
        user_count=user_count,
        contact_count=contact_count,
        visits_count=visits_count,
        visits_data=visits_data
    )

@bp.route('/testimonial', methods=['POST'])
def create_testimonial():
    name = request.form.get("name")
    email = request.form.get("email")
    message = request.form.get("message")
    rating = int(request.form.get("rating", 5))

    mongo.db.contact.insert_one({
        "name": name,
        "email": email,
        "message": message,
        "rating": rating,
        "status": "pending",  # 🔥 muhiim
        "created_at": datetime.utcnow()
    })

    return redirect(url_for('bp.index'))




@bp.route('/contact-submit', methods=['POST'])
def contact_submit():

    name = request.form.get('name')
    email = request.form.get('email')
    subject = request.form.get('subject')
    message = request.form.get('message')

    # ⭐ NEW
    rating = int(request.form.get('rating', 5))

    if not all([name, email, subject, message]):
        flash("Fadlan buuxi dhammaan meelaha bannaan!", "danger")
        return redirect(url_for('main.index') + "#contact-section")

    contact_entry = {
        "user_id": current_user.id if current_user.is_authenticated else None,
        "name": name,
        "email": email,
        "subject": subject,
        "message": message,
        "rating": rating,  # ⭐ muhiim
        "status": "pending",
        "created_at": datetime.utcnow()
    }

    try:
        mongo.db.contact.insert_one(contact_entry)
        flash("Farriintaada waa la diray, mahadsanid!", "success")
    except Exception as e:
        print(e)
        flash("Cilad ayaa dhacday, fadlan isku day mar kale.", "danger")

    return redirect(url_for('main.index') + "#contact-section")


@bp.route('/projects/view')
def all_projects_view():
    try:
        # ================= INPUTS =================
        page = request.args.get('page', 1, type=int)
        search = request.args.get('search', '').strip()

        per_page = 6
        skip = (page - 1) * per_page

        # ================= QUERY =================
        query = {}

        if search:
            query = {
                "$or": [
                    {"title": {"$regex": search, "$options": "i"}},
                    {"description": {"$regex": search, "$options": "i"}}
                ]
            }

        # ================= TOTAL COUNT =================
        total_projects = mongo.db.projects.count_documents(query)

        # ================= DATA FETCH =================
        cursor = (
            mongo.db.projects
            .find(query)
            .sort([("created_at", -1)])
            .skip(skip)
            .limit(per_page)
        )

        projects = []
        for p in cursor:
            try:
                projects.append(Project(p))
            except Exception as pe:
                print("❌ PROJECT PARSE ERROR:", pe)
                print(p)

        # ================= TOTAL PAGES =================
        total_pages = math.ceil(total_projects / per_page) if total_projects else 1

        # ================= RENDER =================
        return render_template(
            'frontend/pages/projects/all_projects.html',
            projects=projects,
            page=page,
            total_pages=total_pages,
            total_projects=total_projects,
            search=search   # 🔥 muhiim
        )

    except Exception as e:
        print("❌ ROUTE ERROR (all_projects_view):")
        print(str(e))
        traceback.print_exc()

        flash("Khalad ayaa dhacay marka projects la soo qaadayay.", "danger")
        return redirect(url_for('main.index'))
  


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


@bp.route('/privacy-policy')
def privacy_policy():
    return render_template('frontend/pages/privacy_policy.html')




@bp.route('/register', methods=['GET', 'POST'])
def register():
    if current_user.is_authenticated:
        return redirect(url_for('main.dashboard'))

    if request.method == 'POST':
        username = request.form.get('username')
        fullname = request.form.get('fullname')
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
            "fullname": fullname,
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
            return redirect(url_for('main.login')) 

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
        return abort(403)

    countries = [
        {"code": "SO", "name": "Somalia", "flag_url": "https://flagcdn.com/so.svg"},
        {"code": "KE", "name": "Kenya", "flag_url": "https://flagcdn.com/ke.svg"},
    ]

    if request.method == 'POST':

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

        # ================= VALIDATION =================
        if password != confirm_password:
            flash("Passwords-ka isma laha!", "danger")
            return redirect(url_for('main.add_user'))

        if mongo.db.users.find_one({"email": email}):
            flash("Email-kan horey ayaa loo isticmaalay!", "danger")
            return redirect(url_for('main.add_user'))

        # ================= PHOTO UPLOAD =================
        photo_path = ""

        file = request.files.get('photo')

        if file and file.filename:

            # ✔ PROJECT ROOT (NOT APP INTERNAL)
            project_root = os.path.abspath(os.getcwd())

            upload_dir = os.path.join(
                project_root,
                'static',
                'backend',
                'uploads',
                'users'
            )

            os.makedirs(upload_dir, exist_ok=True)

            filename = f"{uuid.uuid4().hex}_{secure_filename(file.filename)}"
            file_path = os.path.join(upload_dir, filename)

            file.save(file_path)

            # DB stores PUBLIC path
            photo_path = f"backend/uploads/users/{filename}"

        # ================= CREATE USER =================
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
            "photo": photo_path,
            "created_at": datetime.utcnow()
        }

        mongo.db.users.insert_one(new_user)

        flash(f"User {username} si guul leh ayaa loo diiwaangeliyey!", "success")
        return redirect(url_for('main.add_user'))

    return render_template(
        "backend/pages/components/users/add_user.html",
        countries=countries
    )



@bp.route('/edit-user/<user_id>', methods=['GET', 'POST'])
@login_required
def edit_user(user_id):
    if current_user.role != 'superadmin':
        return abort(403)

    raw_user = mongo.db.users.find_one({"_id": ObjectId(user_id)})
    if not raw_user:
        flash("User-ka lama helin!", "danger")
        return redirect(url_for('main.index'))

    user = User(raw_user)

    if request.method == 'POST':

        password = request.form.get('password')
        confirm_password = request.form.get('confirm_password')

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

        # ================= PASSWORD FIX =================
        if password:
            if password != confirm_password:
                flash("Passwords-ka isma laha!", "danger")
                return redirect(url_for('main.edit_user', user_id=user_id))

            updated_data["password"] = generate_password_hash(password)

        file = request.files.get('photo')

        if file and file.filename:

            # ================= DELETE OLD IMAGE =================
            old_photo = raw_user.get("photo")

            if old_photo:
                old_path = os.path.join(
                    os.path.abspath(os.getcwd()),
                    'static',
                    old_photo
                )

                if os.path.exists(old_path):
                    try:
                        os.remove(old_path)
                    except Exception as e:
                        print(f"Error deleting old image: {e}")

            # ================= SAVE NEW IMAGE =================
            project_root = os.path.abspath(os.getcwd())

            upload_dir = os.path.join(
                project_root,
                'static',
                'backend',
                'uploads',
                'users'
            )

            os.makedirs(upload_dir, exist_ok=True)

            filename = f"{uuid.uuid4().hex}_{secure_filename(file.filename)}"
            file_path = os.path.join(upload_dir, filename)

            file.save(file_path)

            # DB PATH
            updated_data["photo"] = f"backend/uploads/users/{filename}"

        mongo.db.users.update_one(
            {"_id": ObjectId(user_id)},
            {"$set": updated_data}
        )

        flash("Macluumaadka si guul leh ayaa loo cusbooneysiiyey!", "success")
        return redirect(url_for('main.edit_user', user_id=user_id))

    return render_template(
        "backend/pages/components/users/edit_user.html",
        user=user
    )



@bp.route('/delete-user/<user_id>', methods=['POST'])
@login_required
def delete_user(user_id):
    if current_user.role != 'superadmin':
        return abort(403)

    # 1. Get user
    user = mongo.db.users.find_one({"_id": ObjectId(user_id)})

    # 2. Delete image file if exists
    if user and user.get('photo'):

        # correct project root
        project_root = os.path.abspath(os.getcwd())

        file_path = os.path.join(
            project_root,
            'static',
            user['photo']  # example: backend/uploads/users/xxx.jpg
        )

        if os.path.exists(file_path):
            os.remove(file_path)

    # 3. Delete user from DB
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

    # 🔒 Only superadmin allowed
    if current_user.role != 'superadmin':
        return abort(403)

    if request.method == 'POST':

        # Base upload directory
        base_dir = os.path.join("static", "backend", "uploads", "projects")

        # =========================
        # THUMBNAIL UPLOAD
        # =========================
        thumb_db_path = "backend/uploads/projects/thumbnails/no_image.jpg"
        image = request.files.get('thumbnail')

        if image and image.filename != '':

            ext = os.path.splitext(image.filename)[1]
            unique_name = f"{uuid.uuid4().hex[:8]}{ext}"

            save_folder = os.path.join(base_dir, 'thumbnails')
            os.makedirs(save_folder, exist_ok=True)

            image_path = os.path.join(save_folder, unique_name)
            image.save(image_path)

            thumb_db_path = f"backend/uploads/projects/thumbnails/{unique_name}"

        # =========================
        # GALLERY UPLOAD
        # =========================
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

                    gallery_db_paths.append(
                        f"backend/uploads/projects/gallery/{unique_name}"
                    )

        # =========================
        # VIDEO UPLOAD (FILE)
        # =========================
        video_db_path = ""
        video = request.files.get('video_file')

        if video and video.filename != '':

            ext = os.path.splitext(video.filename)[1]
            unique_name = f"{uuid.uuid4().hex[:8]}{ext}"

            save_video = os.path.join(base_dir, 'videos')
            os.makedirs(save_video, exist_ok=True)

            video_path = os.path.join(save_video, unique_name)
            video.save(video_path)

            video_db_path = f"backend/uploads/projects/videos/{unique_name}"

        # =========================
        # VIDEO URL (YOUTUBE / EXTERNAL)
        # =========================
        video_url = request.form.get('video_url', '').strip()

        # =========================
        # SAVE TO MONGODB
        # =========================
        new_project = {
            "user_id": current_user.id,
            "title": request.form.get('title'),
            "description": request.form.get('description'),

            "thumbnail": thumb_db_path,
            "gallery": gallery_db_paths,

            "video": {
                "url": video_url,
                "path": video_db_path
            },

            # 🔥 optional fallback (extra safety)
            "video_url": video_url,
            "video_path": video_db_path,

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

    return render_template(
        "backend/pages/components/projects/add_project.html"
    )


@bp.route('/edit-project/<project_id>', methods=['GET', 'POST'])
@login_required
def edit_project(project_id):

    # 🔒 Only superadmin allowed
    if current_user.role != 'superadmin':
        return abort(403)

    # =========================
    # GET PROJECT
    # =========================
    project = mongo.db.projects.find_one({"_id": ObjectId(project_id)})

    if not project:
        flash("Project-ga lama helin!", "danger")
        return redirect(url_for('main.all_projects'))

    base_dir = os.path.join("static", "backend", "uploads", "projects")

    if request.method == 'POST':

        # =====================================================
        # THUMBNAIL (REPLACE + DELETE OLD)
        # =====================================================
        new_thumb_path = project.get('thumbnail')
        image = request.files.get('thumbnail')

        if image and image.filename:

            if project.get('thumbnail') and 'no_image' not in project.get('thumbnail'):
                old_thumb = os.path.join(os.getcwd(), project['thumbnail'])
                if os.path.exists(old_thumb):
                    os.remove(old_thumb)

            ext = os.path.splitext(image.filename)[1]
            unique_name = f"{uuid.uuid4().hex[:10]}{ext}"

            save_folder = os.path.join(base_dir, 'thumbnails')
            os.makedirs(save_folder, exist_ok=True)

            image_path = os.path.join(save_folder, unique_name)
            image.save(image_path)

            new_thumb_path = f"backend/uploads/projects/thumbnails/{unique_name}"

        # =====================================================
        # GALLERY (REPLACE MODE + DELETE OLD)
        # =====================================================
        gallery_files = request.files.getlist('gallery')

        if gallery_files and gallery_files[0].filename:

            # DELETE OLD GALLERY FILES
            for old_img in project.get('gallery', []):
                old_path = os.path.join(os.getcwd(), old_img)
                if os.path.exists(old_path):
                    os.remove(old_path)

            gallery_paths = []

            save_gallery = os.path.join(base_dir, 'gallery')
            os.makedirs(save_gallery, exist_ok=True)

            for file in gallery_files:
                if file and file.filename:

                    unique_name = f"{uuid.uuid4().hex[:10]}_{secure_filename(file.filename)}"
                    file_path = os.path.join(save_gallery, unique_name)
                    file.save(file_path)

                    gallery_paths.append(
                        f"backend/uploads/projects/gallery/{unique_name}"
                    )
        else:
            gallery_paths = project.get('gallery', [])

        # =====================================================
        # VIDEO (FILE OR URL SWITCH CLEAN)
        # =====================================================
        video_data = project.get('video', {"url": "", "path": ""})

        video_file = request.files.get('video_file')
        video_url = request.form.get('video_url')

        # -------------------------
        # IF FILE UPLOADED
        # -------------------------
        if video_file and video_file.filename:

            # delete old file
            if video_data.get('path'):
                old_video = os.path.join(os.getcwd(), video_data['path'])
                if os.path.exists(old_video):
                    os.remove(old_video)

            ext = os.path.splitext(video_file.filename)[1]
            unique_name = f"{uuid.uuid4().hex[:10]}{ext}"

            save_video = os.path.join(base_dir, 'videos')
            os.makedirs(save_video, exist_ok=True)

            video_path = os.path.join(save_video, unique_name)
            video_file.save(video_path)

            video_data = {
                "path": f"backend/uploads/projects/videos/{unique_name}",
                "url": ""
            }

        # -------------------------
        # IF URL ONLY
        # -------------------------
        elif video_url:
            if video_data.get('path'):
                old_video = os.path.join(os.getcwd(), video_data['path'])
                if os.path.exists(old_video):
                    os.remove(old_video)

            video_data = {
                "path": "",
                "url": video_url
            }

        # =====================================================
        # FINAL UPDATE
        # =====================================================
        updated_data = {
            "title": request.form.get('title'),
            "description": request.form.get('description'),

            "thumbnail": new_thumb_path,
            "gallery": gallery_paths,

            "video": video_data,

            "video_url": video_data.get('url', ''),
            "video_path": video_data.get('path', ''),

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

        flash("Project si guul leh ayaa loo update gareeyay!", "success")
        return redirect(url_for('main.all_projects'))

    return render_template(
        "backend/pages/components/projects/edit_project.html",
        project=project
    )



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
    resp = make_response(redirect(url_for("main.index")))
    resp.set_cookie("remember_token", "", expires=0)
    return resp








