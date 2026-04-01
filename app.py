from flask import Flask, render_template, request, redirect, url_for, flash
from models import db, User, Product
from flask_login import LoginManager, login_user, login_required, logout_user, current_user
from flask_mail import Mail, Message
import bcrypt
import re 
import requests
import secrets
from datetime import datetime, timedelta
import os
from dotenv import load_dotenv
load_dotenv()

app = Flask(__name__)
app.config['SECRET_KEY'] = 'supersecret'
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///users.db'

db.init_app(app)



# Email Configuration
app.config['MAIL_SERVER'] = os.environ.get('MAIL_SERVER', 'smtp.gmail.com')
app.config['MAIL_PORT'] = int(os.environ.get('MAIL_PORT', 587))
app.config['MAIL_USE_TLS'] = os.environ.get('MAIL_USE_TLS', 'True') == 'True'
app.config['MAIL_USERNAME'] = os.environ.get('MAIL_USERNAME')
app.config['MAIL_PASSWORD'] = os.environ.get('MAIL_PASSWORD')
app.config['MAIL_DEFAULT_SENDER'] = os.environ.get('MAIL_DEFAULT_SENDER')

mail = Mail(app)
# -------------------------
# LOGIN MANAGER
# -------------------------
login_manager = LoginManager()
login_manager.login_view = 'login'
login_manager.init_app(app)
db.init_app(app)
from functools import wraps

# Admin required decorator
def admin_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not current_user.is_authenticated or not current_user.is_admin:
            flash("Access denied. Admin privileges required.", "error")
            return redirect(url_for('dashboard'))
        return f(*args, **kwargs)
    return decorated_function

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

@app.route('/signup', methods=['GET', 'POST'])
def signup():
    if request.method == 'POST':
        email = request.form['email']
        password = request.form['password']
        confirm_password = request.form['confirm-password']  # Moved this up
        phone = request.form['phone']
        cep = request.form['cep']

        # Define validation functions outside or at top of route
        def validate_phone(phone):
            # Brazilian pattern: (11) 91234-5678 or 11912345678
            phone = re.sub(r'\D', '', phone)  # remove symbols
            pattern = r'^\d{10,11}$'
            return re.match(pattern, phone)
        
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

        # Check password match
        if password != confirm_password:
            flash("Passwords do not match")
            return redirect(url_for('signup'))
        
        # Check existing user
        existing_user = User.query.filter_by(email=email).first()
        if existing_user:
            flash("User already exists")
            return redirect(url_for('signup'))
        
        # Validate CEP format
        if len(cep) != 8 or not cep.isdigit():
            flash("Invalid CEP format (must be 8 digits)")
            return redirect(url_for('signup'))
        
        # Validate CEP exists via API
        if not validate_cep_exists(cep):
            flash("Invalid CEP - address not found")
            return redirect(url_for('signup'))
        
        # Validate phone
        if not validate_phone(phone):
            flash("Invalid phone number (must be 10-11 digits)")
            return redirect(url_for('signup'))
        
        # Create user
        hashed_pw = bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt())
        
        new_user = User(
            email=email, 
            password=hashed_pw.decode('utf-8'), 
            phone=phone,
            cep=cep
        )
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

# FORGOT PASSWORD - Request reset
@app.route('/forgot-password', methods=['GET', 'POST'])
def forgot_password():
    if request.method == 'POST':
        email = request.form['email']
        user = User.query.filter_by(email=email).first()
        
        if user:
            # Generate reset token
            token = secrets.token_urlsafe(32)
            user.reset_token = token
            user.reset_token_expiry = datetime.utcnow() + timedelta(hours=24)
            db.session.commit()
            
            # In a real app, you would send an email here
            # For now, we'll show the token in a flash message
            reset_url = url_for('reset_password', token=token, _external=True)
            flash(f'Password reset link: {reset_url}', 'info')
            flash('Check your console for the reset link (in production, this would be emailed)', 'info')
            print(f"\n=== PASSWORD RESET LINK ===\n{reset_url}\n==========================\n")
        else:
            # Don't reveal if email exists or not for security
            flash('If that email exists, a reset link has been sent.', 'info')
        
        return redirect(url_for('login'))
    
    return render_template('forgot_password.html')

def send_reset_email(user_email, reset_url):
    """Send password reset email"""
    try:
        msg = Message(
            subject="Password Reset Request",
            recipients=[user_email],
            html=render_template('email_reset_password.html', reset_url=reset_url),
            body=f"""To reset your password, visit the following link:
{reset_url}

If you did not make this request, simply ignore this email.

This link will expire in 24 hours.
"""
        )
        mail.send(msg)
        return True
    except Exception as e:
        print(f"Error sending email: {e}")
        return False
# RESET PASSWORD - Enter new password
@app.route('/reset-password/<token>', methods=['GET', 'POST'])
def reset_password(token):
    # Find user with this token
    user = User.query.filter_by(reset_token=token).first()
    
    # Check if token exists and is not expired
    if not user or user.reset_token_expiry < datetime.utcnow():
        flash('Invalid or expired reset link. Please request a new one.', 'error')
        return redirect(url_for('forgot_password'))
    
    if request.method == 'POST':
        password = request.form['password']
        confirm_password = request.form['confirm-password']
        
        # Validate password
        if len(password) < 6:
            flash('Password must be at least 6 characters long.', 'error')
            return redirect(url_for('reset_password', token=token))
        
        if password != confirm_password:
            flash('Passwords do not match.', 'error')
            return redirect(url_for('reset_password', token=token))
        
        # Hash new password
        hashed_pw = bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt())
        user.password = hashed_pw.decode('utf-8')
        
        # Clear reset token
        user.reset_token = None
        user.reset_token_expiry = None
        db.session.commit()
        
        flash('Password successfully reset! Please login with your new password.', 'success')
        return redirect(url_for('login'))
    
    return render_template('reset_password.html', token=token)


# CHANGE PASSWORD - For logged-in users
@app.route('/change-password', methods=['GET', 'POST'])
@login_required
def change_password():
    if request.method == 'POST':
        current_password = request.form['current_password']
        new_password = request.form['new_password']
        confirm_password = request.form['confirm_password']
        
        # Verify current password
        if not bcrypt.checkpw(current_password.encode('utf-8'), current_user.password.encode('utf-8')):
            flash('Current password is incorrect.', 'error')
            return redirect(url_for('change_password'))
        
        # Validate new password
        if len(new_password) < 6:
            flash('New password must be at least 6 characters long.', 'error')
            return redirect(url_for('change_password'))
        
        if new_password != confirm_password:
            flash('New passwords do not match.', 'error')
            return redirect(url_for('change_password'))
        
        # Update password
        hashed_pw = bcrypt.hashpw(new_password.encode('utf-8'), bcrypt.gensalt())
        current_user.password = hashed_pw.decode('utf-8')
        db.session.commit()
        
        flash('Password changed successfully!', 'success')
        return redirect(url_for('dashboard'))
    
    return render_template('change_password.html')

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

@app.route('/products')
def list_products():
    products = Product.query.all()
    return render_template('products.html', products=products)

@app.route('/products/create', methods=['GET', 'POST'])
@login_required
@admin_required
def create_product():
    if request.method == 'POST':
        name = request.form['name']
        description = request.form['description']
        price = request.form['price']
        image_url = request.form.get('image_url', '')  # Get optional image_url

        # Validate price
        try:
            price = float(price)
            if price <= 0:
                flash("Price must be greater than 0")
                return redirect(url_for('create_product'))
        except ValueError:
            flash("Invalid price format")
            return redirect(url_for('create_product'))

        product = Product(
            name=name,
            description=description,
            price=price,
            image_url=image_url if image_url else None
        )

        db.session.add(product)
        db.session.commit()

        flash("Product created successfully!")
        return redirect(url_for('list_products'))

    return render_template('product_form.html')


@app.route('/products/edit/<int:id>', methods=['GET', 'POST'])
@login_required
@admin_required
def edit_product(id):
    product = Product.query.get_or_404(id)

    if request.method == 'POST':
        product.name = request.form['name']
        product.description = request.form['description']
        product.price = request.form['price']
        product.image_url = request.form.get('image_url', '') or None

        # Validate price
        try:
            product.price = float(product.price)
            if product.price <= 0:
                flash("Price must be greater than 0")
                return redirect(url_for('edit_product', id=id))
        except ValueError:
            flash("Invalid price format")
            return redirect(url_for('edit_product', id=id))

        db.session.commit()
        flash("Product updated successfully!")
        return redirect(url_for('list_products'))

    return render_template('product_form.html', product=product)


@app.route('/products/delete/<int:id>')
@login_required
@admin_required
def delete_product(id):
    product = Product.query.get_or_404(id)
    
    db.session.delete(product)
    db.session.commit()

    flash("Product deleted successfully!")
    return redirect(url_for('list_products'))

# -------------------------
# RUN
# -------------------------
if __name__ == '__main__':
    app.run(debug=True)