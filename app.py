from flask import Flask, render_template, request, redirect, url_for, flash
from models import db, User
from flask_login import LoginManager, login_user, login_required, logout_user, current_user
import bcrypt
import re 
import requests
app = Flask(__name__)
app.config['SECRET_KEY'] = 'supersecret'
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///users.db'

db.init_app(app)

# -------------------------
# LOGIN MANAGER
# -------------------------
login_manager = LoginManager()
login_manager.login_view = 'login'
login_manager.init_app(app)

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

# -------------------------
# CREATE DB
# -------------------------
with app.app_context():
    db.create_all()

# -------------------------
# ROUTES
# -------------------------

@app.route('/')
def home():
    return redirect(url_for('login'))

# SIGN UP
@app.route('/signup', methods=['GET', 'POST'])
def signup():
    if request.method == 'POST':
        email = request.form['email']
        password = request.form['password']
        phone = request.form['phone']
        cep = request.form['cep']

        if password != confirm_password:
            flash("Passwords do not match")
            return redirect(url_for('signup'))
        existing_user = User.query.filter_by(email=email).first()
        if existing_user:
            flash("User already exists")
            return redirect(url_for('signup'))
        
        if len(cep) != 8 or not cep.isdigit():
            flash("Invalid CEP format")
            return redirect(url_for('signup'))
        
        def validate_phone(phone):
        # Brazilian pattern: (11) 91234-5678 or 11912345678
            pattern = r'^\d{10,11}$'
            phone = re.sub(r'\D', '', phone)  # remove symbols
    
            return re.match(pattern, phone)
        
        
        hashed_pw = bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt())
        
        confirm_password = request.form['confirm-password']

        if password != confirm_password:
            flash("Passwords do not match")
            return redirect(url_for('signup'))
        
        phone = request.form['phone']

        if not validate_phone(phone):
            flash("Invalid phone number")
            return redirect(url_for('signup'))
        
        def validate_cep_exists(cep):
            cep = ''.join(filter(str.isdigit, cep))

            if len(cep) != 8:
                return False

            try:
                response = requests.get(f'https://viacep.com.br/ws/{cep}/json/')
                data = response.json()

                if "erro" in data:
                    return False

                return True
            except:
                return False
            
        new_user = User(email=email, password=hashed_pw.decode('utf-8'), phone=phone,cep=cep)
        db.session.add(new_user)
        db.session.commit()

        flash("Account created! Please login.")
        return redirect(url_for('login'))

    return render_template('signup.html')

# LOGIN
@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = request.form['email']
        password = request.form['password']

        user = User.query.filter_by(email=email).first()

        if user and bcrypt.checkpw(password.encode('utf-8'), user.password.encode('utf-8')):
            login_user(user)
            return redirect(url_for('dashboard'))
        else:
            flash("Invalid credentials")

    return render_template('login.html')

# DASHBOARD (Protected)
@app.route('/dashboard')
@login_required
def dashboard():
    return render_template('dashboard.html', user=current_user)

# LOGOUT
@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('login'))

# -------------------------
# RUN
# -------------------------
if __name__ == '__main__':
    app.run(debug=True)