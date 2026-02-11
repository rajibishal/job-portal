import requests # Make sure to pip install requests
from flask import Flask, render_template, request, redirect, url_for, flash
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, login_user, logout_user, login_required, current_user
from werkzeug.security import generate_password_hash, check_password_hash
from models import db, User, Job, Application

app = Flask(__name__)

app.config['SECRET_KEY'] = 'mysecretkey'
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///jobportal.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db.init_app(app)
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

with app.app_context():
    db.create_all()

# --- 1. HOME & SEARCH FILTERS ---
@app.route("/")
def home():
    # Get Filter Parameters
    category = request.args.get('category')
    location = request.args.get('location')
    
    query = Job.query

    if category:
        query = query.filter(Job.category.ilike(f"%{category}%"))
    if location:
        query = query.filter(Job.location.ilike(f"%{location}%"))
        
    jobs = query.all()
    
    # Fetch External Jobs (API Integration)
    external_jobs = []
    if request.args.get('show_external'):
        try:
            # Using Remotive API (Free, No Key Required)
            response = requests.get('https://remotive.com/api/remote-jobs?limit=5')
            if response.status_code == 200:
                external_jobs = response.json().get('jobs', [])[:5] # Get top 5
        except:
            flash("Could not fetch external jobs.", "warning")

    return render_template("index.html", jobs=jobs, external_jobs=external_jobs)

# --- 2. AUTHENTICATION ---
@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        username = request.form.get("username")
        email = request.form.get("email")
        password = request.form.get("password")
        role = request.form.get("role")
        
        if User.query.filter_by(email=email).first():
            flash("Email already registered!", "danger")
            return redirect(url_for('register'))
            
        hashed_password = generate_password_hash(password, method='pbkdf2:sha256')
        new_user = User(username=username, email=email, password=hashed_password, role=role)
        db.session.add(new_user)
        db.session.commit()
        flash("Account created! Please login.", "success")
        return redirect(url_for('login'))
    return render_template("register.html")

@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        email = request.form.get("email")
        password = request.form.get("password")
        user = User.query.filter_by(email=email).first()
        
        if user and check_password_hash(user.password, password):
            login_user(user)
            return redirect(url_for('admin_dashboard') if user.role == 'admin' else url_for('home'))
        else:
            flash("Login failed.", "danger")
    return render_template("login.html")

@app.route("/logout")
@login_required
def logout():
    logout_user()
    return redirect(url_for('login'))

# --- 3. EMPLOYER ROUTES ---
@app.route("/dashboard")
@login_required
def dashboard():
    if current_user.role != 'employer':
        return redirect(url_for('home'))
    my_jobs = Job.query.filter_by(user_id=current_user.id).all()
    return render_template("dashboard.html", jobs=my_jobs)

@app.route("/post_job", methods=["GET", "POST"])
@login_required
def post_job():
    if current_user.role != 'employer':
        return redirect(url_for('home'))
        
    if request.method == "POST":
        title = request.form.get("title")
        company = request.form.get("company")
        category = request.form.get("category")
        location = request.form.get("location")
        salary = request.form.get("salary")
        description = request.form.get("description")
        
        new_job = Job(title=title, company=company, category=category, 
                      location=location, salary=salary, description=description, 
                      user_id=current_user.id)
        db.session.add(new_job)
        db.session.commit()
        flash("Job posted!", "success")
        return redirect(url_for('dashboard'))
    return render_template("post_job.html")

@app.route("/job/<int:job_id>/applicants")
@login_required
def view_applicants(job_id):
    job = Job.query.get_or_404(job_id)
    if job.user_id != current_user.id:
        return redirect(url_for('dashboard'))
    return render_template("view_applicants.html", job=job)

# --- 4. SEEKER ROUTES ---
@app.route("/apply/<int:job_id>")
@login_required
def apply_job(job_id):
    if current_user.role != 'seeker':
        flash("Only seekers can apply.", "warning")
        return redirect(url_for('home'))
        
    if not Application.query.filter_by(job_id=job_id, user_id=current_user.id).first():
        db.session.add(Application(job_id=job_id, user_id=current_user.id))
        db.session.commit()
        flash("Applied successfully!", "success")
    else:
        flash("Already applied.", "info")
    return redirect(url_for('home'))

@app.route("/my_applications")
@login_required
def my_applications():
    if current_user.role != 'seeker':
        return redirect(url_for('home'))
    apps = Application.query.filter_by(user_id=current_user.id).all()
    return render_template("my_applications.html", applications=apps)

# --- 5. ADMIN ROUTES (NEW) ---
@app.route("/admin")
@login_required
def admin_dashboard():
    if current_user.role != 'admin':
        flash("Access Denied.", "danger")
        return redirect(url_for('home'))
    users = User.query.all()
    jobs = Job.query.all()
    return render_template("admin.html", users=users, jobs=jobs)

@app.route("/admin/delete_user/<int:user_id>")
@login_required
def delete_user(user_id):
    if current_user.role == 'admin':
        user = User.query.get(user_id)
        if user: 
            db.session.delete(user)
            db.session.commit()
            flash("User deleted.", "success")
    return redirect(url_for('admin_dashboard'))

@app.route("/admin/delete_job/<int:job_id>")
@login_required
def delete_job(job_id):
    if current_user.role == 'admin':
        job = Job.query.get(job_id)
        if job:
            db.session.delete(job)
            db.session.commit()
            flash("Job deleted.", "success")
    return redirect(url_for('admin_dashboard'))

if __name__ == "__main__":
    app.run(debug=True)