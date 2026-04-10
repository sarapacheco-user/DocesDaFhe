from flask import Flask, render_template, request, redirect, url_for, flash
from models import db, User, Product, Kit, KitProduct
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





# Email Configuration : ver como fazer isso aqui pois precisa enviar para o usuario depois
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
            flash("Acesso negado. Privilégios de adm são necessários.", "erro")
            return redirect(url_for('dashboard'))
        return f(*args, **kwargs)
    return decorated_function

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))


# -------------------------
# CRIA BANCO DE DADOS
# -------------------------
with app.app_context():
    db.create_all()

# Verdadeiro se o usuário pode editar o kit
def user_can_edit_kit(kit):
    """Return True if current_user can edit/delete the given kit."""
    if current_user.is_admin:
        return True
    return (not kit.is_admin_kit) and (kit.created_by == current_user.id)


# -------------------------
# ROTAS
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
            # Valida se é padrão de telefone brasileiro
            phone = re.sub(r'\D', '', phone)  # remove símbolos
            pattern = r'^\d{10,11}$'
            return re.match(pattern, phone)
        # Validação de CEP
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

        # Checa se a senha e a confirme a senha são as mesmas
        if password != confirm_password:
            flash("Essas senhas não são as mesmas")
            return redirect(url_for('signup'))
        
        # Checa usuário existente
        existing_user = User.query.filter_by(email=email).first()
        if existing_user:
            flash("Usuário já registrado.")
            return redirect(url_for('signup'))
        
        # Valida CEP
        if len(cep) != 8 or not cep.isdigit():
            flash("Formato de CEP inválido (deve ser 8 dígitos)")
            return redirect(url_for('signup'))
        
        # Valida CEP pela API
        if not validate_cep_exists(cep):
            flash("CEP Inválido - endereço não encontrado")
            return redirect(url_for('signup'))
        
        # Valida Telefone
        if not validate_phone(phone):
            flash("Número de telefone inválido (deve ser de 10-11 dígitos)")
            return redirect(url_for('signup'))
        
        # Cria usuário
        hashed_pw = bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt())
        
        new_user = User(
            email=email, 
            password=hashed_pw.decode('utf-8'), 
            phone=phone,
            cep=cep
        )
        db.session.add(new_user)
        db.session.commit()

        flash("Conta Criada! Faça o login por favor.")
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

# Caso esqueceu senha - Request de reset FAZER ISSO MAIS PARA FRENTE
@app.route('/forgot-password', methods=['GET', 'POST'])
def forgot_password():
    if request.method == 'POST':
        email = request.form['email']
        user = User.query.filter_by(email=email).first()
        
        if user:
            # Gera token de reset
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
# RESET de senha - Entre nova senha
@app.route('/reset-password/<token>', methods=['GET', 'POST'])
def reset_password(token):
    # Encontre usuário com esse token
    user = User.query.filter_by(reset_token=token).first()
    
    # Checa se o token existe e não expirado
    if not user or user.reset_token_expiry < datetime.utcnow():
        flash('Invalid or expired reset link. Please request a new one.', 'error')
        return redirect(url_for('forgot_password'))
    
    if request.method == 'POST':
        password = request.form['password']
        confirm_password = request.form['confirm-password']
        
        # Valida senha
        if len(password) < 6:
            flash('Password must be at least 6 characters long.', 'error')
            return redirect(url_for('reset_password', token=token))
        
        if password != confirm_password:
            flash('Passwords do not match.', 'error')
            return redirect(url_for('reset_password', token=token))
        
        # Hasha a nova senha
        hashed_pw = bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt())
        user.password = hashed_pw.decode('utf-8')
        
        # Limpa o token de reset
        user.reset_token = None
        user.reset_token_expiry = None
        db.session.commit()
        
        flash('Password successfully reset! Please login with your new password.', 'success')
        return redirect(url_for('login'))
    
    return render_template('reset_password.html', token=token)


# MUDA SENHA PARA QUEM JÁ ESTÁ LOGADO
@app.route('/change-password', methods=['GET', 'POST'])
@login_required
def change_password():
    if request.method == 'POST':
        current_password = request.form['current_password']
        new_password = request.form['new_password']
        confirm_password = request.form['confirm_password']
        
        # Verifica senha atual
        if not bcrypt.checkpw(current_password.encode('utf-8'), current_user.password.encode('utf-8')):
            flash('Current password is incorrect.', 'error')
            return redirect(url_for('change_password'))
        
        # Valida senha atual
        if len(new_password) < 6:
            flash('New password must be at least 6 characters long.', 'error')
            return redirect(url_for('change_password'))
        
        if new_password != confirm_password:
            flash('New passwords do not match.', 'error')
            return redirect(url_for('change_password'))
        
        # Atualiza a senha
        hashed_pw = bcrypt.hashpw(new_password.encode('utf-8'), bcrypt.gensalt())
        current_user.password = hashed_pw.decode('utf-8')
        db.session.commit()
        
        flash('Password changed successfully!', 'success')
        return redirect(url_for('dashboard'))
    
    return render_template('change_password.html')

# DASHBOARD (Protegido)
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
# Rota de produtos
@app.route('/products')
def list_products():
    products = Product.query.all()
    return render_template('products.html', products=products)
# Cria produtos
@app.route('/products/create', methods=['GET', 'POST'])
@login_required
@admin_required
def create_product():
    if request.method == 'POST':
        name = request.form['name']
        description = request.form['description']
        price = request.form['price']
        image_url = request.form.get('image_url', '')  # Pega imagem image_url opcionalmente

        # Valida preço 
        try:
            price = float(price)
            if price <= 0:
                flash("Preço precisa ser maior que 0")
                return redirect(url_for('create_product'))
        except ValueError:
            flash("Formato inválido")
            return redirect(url_for('create_product'))

        product = Product(
            name=name,
            description=description,
            price=price,
            image_url=image_url if image_url else None
        )

        db.session.add(product)
        db.session.commit()

        flash("Produto Criado com Sucesso!")
        return redirect(url_for('list_products'))

    return render_template('product_form.html')

# Edição de produtos
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

        # Valida preço
        try:
            product.price = float(product.price)
            if product.price <= 0:
                flash("Preço precisa ser maior que 0")
                return redirect(url_for('edit_product', id=id))
        except ValueError:
            flash("Formato de preço inválido")
            return redirect(url_for('edit_product', id=id))

        db.session.commit()
        flash("Produto atualizado com sucesso!")
        return redirect(url_for('list_products'))

    return render_template('product_form.html', product=product)

# Deleção de produtos 
@app.route('/products/delete/<int:id>')
@login_required
@admin_required
def delete_product(id):
    product = Product.query.get_or_404(id)
    
    db.session.delete(product)
    db.session.commit()

    flash("Produto deletado com sucesso!")
    return redirect(url_for('list_products'))
# Rotas de Kits
@app.route('/kits')
@login_required
def list_kits():
    if current_user.is_admin:
        kits = Kit.query.order_by(Kit.created_at.desc()).all()
    else:
        # Lista os kits do usuário e os do adm
        kits = Kit.query.filter(
            (Kit.created_by == current_user.id) | (Kit.is_admin_kit == True)
        ).order_by(Kit.created_at.desc()).all()
    
    return render_template('kits/list.html', kits=kits)

@app.route('/kits/<int:kit_id>')
@login_required
def view_kit(kit_id):
    kit = Kit.query.get_or_404(kit_id)
    
    # Checa visibilidade 
    if not (current_user.is_admin or kit.is_admin_kit or kit.created_by == current_user.id):
        flash("You don't have permission to view this kit.", "error")
        return redirect(url_for('list_kits'))
    
    return render_template('kits/view.html', kit=kit)

# Rota de criação de kit
@app.route('/kits/create', methods=['GET', 'POST'])
@login_required
def create_kit():
    if request.method == 'POST':
        name = request.form.get('name')
        description = request.form.get('description')
        image_url = request.form.get('image_url') or None  

        if not name:
            flash("Kit name is required.", "error")
            return redirect(url_for('create_kit'))
        
        kit = Kit(
            name=name,
            description=description,
            created_by=current_user.id,
            image_url=image_url, 
            is_admin_kit=current_user.is_admin   # Kit de adm ou de usuário
        )
        db.session.add(kit)
        db.session.commit()
        
        flash(f"Kit '{kit.name}' criado com sucesso!", "success")
        return redirect(url_for('edit_kit_products', kit_id=kit.id))
    
    return render_template('kits/create.html')

@app.route('/kits/<int:kit_id>/edit', methods=['GET', 'POST'])
@login_required
def edit_kit(kit_id):
    kit = Kit.query.get_or_404(kit_id)
    
    if not user_can_edit_kit(kit):
        flash("Você não tem permissão para editar esse kit", "error")
        return redirect(url_for('list_kits'))
    
    if request.method == 'POST':
        kit.name = request.form.get('name')
        kit.description = request.form.get('description')
        kit.image_url = request.form.get('image_url') or None
        db.session.commit()
        flash("Kit updated!", "success")
        return redirect(url_for('view_kit', kit_id=kit.id))
    
    return render_template('kits/edit.html', kit=kit)


@app.route('/kits/<int:kit_id>/delete', methods=['POST'])
@login_required
def delete_kit(kit_id):
    kit = Kit.query.get_or_404(kit_id)
    
    if not user_can_edit_kit(kit):
        flash("Você não tem permissão para deletar o kit", "error")
        return redirect(url_for('list_kits'))
    
    db.session.delete(kit)
    db.session.commit()
    flash("Kit deleted.", "success")
    return redirect(url_for('list_kits'))

@app.route('/kits/<int:kit_id>/products', methods=['GET', 'POST'])
@login_required
def edit_kit_products(kit_id):
    kit = Kit.query.get_or_404(kit_id)
    
    if not user_can_edit_kit(kit):
        flash("You don't have permission to modify this kit.", "error")
        return redirect(url_for('list_kits'))
    
    # Pega todos os produtos para a seleção
    all_products = Product.query.order_by(Product.name).all()
    
    # èga produtos no kit atualmente com a quantidade
    kit_products = {kp.product_id: kp for kp in kit.products}
    
    if request.method == 'POST':
        # Processa adição e remoção
        # The form will send a list of (product_id, quantity) pairs
        product_ids = request.form.getlist('product_id')
        quantities = request.form.getlist('quantity')
        
        # Primeiro, remove produtos não selecionados
        submitted_ids = set(int(pid) for pid in product_ids)
        for kp in kit.products:
            if kp.product_id not in submitted_ids:
                db.session.delete(kp)
        
        # Adiciona ou atualiza produtos selecionados
        for pid, qty in zip(product_ids, quantities):
            pid = int(pid)
            qty = int(qty) if qty.isdigit() and int(qty) > 0 else 1
            existing = KitProduct.query.get((kit_id, pid))
            if existing:
                existing.quantity = qty
            else:
                new_kp = KitProduct(kit_id=kit_id, product_id=pid, quantity=qty)
                db.session.add(new_kp)
        
        db.session.commit()
        flash("Kit products updated!", "success")
        return redirect(url_for('view_kit', kit_id=kit.id))
    
    return render_template('kits/manage_products.html',
                           kit=kit,
                           all_products=all_products,
                           kit_products=kit_products)




# -------------------------
# RUN
# -------------------------
if __name__ == '__main__':
    app.run(debug=True)