<<<<<<< HEAD
from functools import wraps
from flask import Flask, render_template, request, redirect, url_for, flash
from flask_login import LoginManager, login_user, login_required, logout_user, current_user
from flask_mail import Mail, Message
from models import db, User, Product, Kit, KitProduct, EventoEspecial, ProdutoEspecial, CarrinhoItem, CarrosselItem
import bcrypt
import re
import requests
import secrets
from werkzeug.utils import secure_filename
from datetime import datetime, timedelta
import time
=======
from flask import Flask, render_template, request, redirect, url_for, flash
from models import db, User, Product, Kit, KitProduct
from flask_login import LoginManager, login_user, login_required, logout_user, current_user
from flask_mail import Mail, Message
import bcrypt
import re 
import requests
import secrets
from datetime import datetime, timedelta
>>>>>>> 4a6ae9744af7949d4d8fc2a42b247b9eba546b0c
import os
from dotenv import load_dotenv
load_dotenv()

app = Flask(__name__)
app.config['SECRET_KEY'] = 'supersecret'
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///users.db'

<<<<<<< HEAD
# Email Configuration
=======




# Email Configuration : ver como fazer isso aqui pois precisa enviar para o usuario depois
>>>>>>> 4a6ae9744af7949d4d8fc2a42b247b9eba546b0c
app.config['MAIL_SERVER'] = os.environ.get('MAIL_SERVER', 'smtp.gmail.com')
app.config['MAIL_PORT'] = int(os.environ.get('MAIL_PORT', 587))
app.config['MAIL_USE_TLS'] = os.environ.get('MAIL_USE_TLS', 'True') == 'True'
app.config['MAIL_USERNAME'] = os.environ.get('MAIL_USERNAME')
app.config['MAIL_PASSWORD'] = os.environ.get('MAIL_PASSWORD')
app.config['MAIL_DEFAULT_SENDER'] = os.environ.get('MAIL_DEFAULT_SENDER')

<<<<<<< HEAD
mail = Mail(app)

# ── UPLOAD FOLDERS ──
UPLOAD_FOLDER_CARROSSEL = os.path.join('static', 'uploads', 'carrossel')
UPLOAD_FOLDER_PRODUTOS  = os.path.join('static', 'uploads', 'produtos')
UPLOAD_FOLDER_KITS      = os.path.join('static', 'uploads', 'kits')
UPLOAD_FOLDER_ESPECIAIS = os.path.join('static', 'uploads', 'especiais')
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'webp', 'gif'}

for folder in [UPLOAD_FOLDER_CARROSSEL, UPLOAD_FOLDER_PRODUTOS,
               UPLOAD_FOLDER_KITS, UPLOAD_FOLDER_ESPECIAIS]:
    os.makedirs(folder, exist_ok=True)


def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS


def salvar_imagem_produto(arquivo):
    if not arquivo or arquivo.filename == '':
        return None
    ext = arquivo.filename.rsplit('.', 1)[-1].lower()
    if ext not in ALLOWED_EXTENSIONS:
        return None
    filename = f"{int(time.time())}_{secure_filename(arquivo.filename)}"
    arquivo.save(os.path.join(UPLOAD_FOLDER_PRODUTOS, filename))
    return f"uploads/produtos/{filename}"


# ── LOGIN MANAGER ──
=======

mail = Mail(app)


# -------------------------
# LOGIN MANAGER
# -------------------------

>>>>>>> 4a6ae9744af7949d4d8fc2a42b247b9eba546b0c
login_manager = LoginManager()
login_manager.login_view = 'login'
login_manager.init_app(app)
db.init_app(app)
<<<<<<< HEAD


=======
from functools import wraps

# Admin required decorator
>>>>>>> 4a6ae9744af7949d4d8fc2a42b247b9eba546b0c
def admin_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not current_user.is_authenticated or not current_user.is_admin:
<<<<<<< HEAD
            flash("Acesso negado. São necessárias permissões de administrador.", "error")
=======
            flash("Acesso negado. Privilégios de adm são necessários.", "erro")
>>>>>>> 4a6ae9744af7949d4d8fc2a42b247b9eba546b0c
            return redirect(url_for('dashboard'))
        return f(*args, **kwargs)
    return decorated_function

<<<<<<< HEAD

=======
>>>>>>> 4a6ae9744af7949d4d8fc2a42b247b9eba546b0c
@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))


<<<<<<< HEAD
with app.app_context():
    db.create_all()


def user_can_edit_kit(kit):
=======
# -------------------------
# CRIA BANCO DE DADOS
# -------------------------
with app.app_context():
    db.create_all()

# Verdadeiro se o usuário pode editar o kit
def user_can_edit_kit(kit):
    """Return True if current_user can edit/delete the given kit."""
>>>>>>> 4a6ae9744af7949d4d8fc2a42b247b9eba546b0c
    if current_user.is_admin:
        return True
    return (not kit.is_admin_kit) and (kit.created_by == current_user.id)


<<<<<<< HEAD
# ── CONTEXT PROCESSOR ──
@app.context_processor
def carrinho_contador():
    if current_user.is_authenticated:
        total_itens = db.session.query(
            db.func.sum(CarrinhoItem.quantidade)
        ).filter_by(user_id=current_user.id).scalar() or 0
    else:
        total_itens = 0
    return dict(carrinho_total=total_itens)


# ─────────────────────────────────────
# ROTAS GERAIS
# ─────────────────────────────────────

@app.route('/')
def home():
    return redirect(url_for('dashboard'))

=======
# -------------------------
# ROTAS
# -------------------------

@app.route('/')
def home():
    return redirect(url_for('login'))
>>>>>>> 4a6ae9744af7949d4d8fc2a42b247b9eba546b0c

@app.route('/signup', methods=['GET', 'POST'])
def signup():
    if request.method == 'POST':
<<<<<<< HEAD
        name             = request.form['name']
        email            = request.form['email']
        password         = request.form['password']
        confirm_password = request.form['confirm-password']
        phone            = request.form['phone']
        cep              = request.form['cep']

        def validate_phone(phone):
            phone = re.sub(r'\D', '', phone)
            return re.match(r'^\d{10,11}$', phone)

=======
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
>>>>>>> 4a6ae9744af7949d4d8fc2a42b247b9eba546b0c
        def validate_cep_exists(cep):
            cep = ''.join(filter(str.isdigit, cep))
            if len(cep) != 8:
                return False
            try:
                response = requests.get(f'https://viacep.com.br/ws/{cep}/json/')
                data = response.json()
<<<<<<< HEAD
                return "erro" not in data
            except:
                return False

        if not name.strip():
            flash("O nome é obrigatório.")
            return redirect(url_for('signup'))
        if password != confirm_password:
            flash("As senhas não coincidem.")
            return redirect(url_for('signup'))
        if User.query.filter_by(email=email).first():
            flash("Usuário já existe.")
            return redirect(url_for('signup'))
        if len(cep) != 8 or not cep.isdigit():
            flash("Formato de CEP inválido (deve ter 8 dígitos).")
            return redirect(url_for('signup'))
        if not validate_cep_exists(cep):
            flash("CEP inválido - endereço não encontrado.")
            return redirect(url_for('signup'))
        if not validate_phone(phone):
            flash("Número de telefone inválido (deve ter 10-11 dígitos).")
            return redirect(url_for('signup'))

        hashed_pw = bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt())
        new_user = User(name=name, email=email,
                        password=hashed_pw.decode('utf-8'),
                        phone=phone, cep=cep)
        db.session.add(new_user)
        db.session.commit()
        flash("Conta criada! Por favor, faça login.")
=======
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
>>>>>>> 4a6ae9744af7949d4d8fc2a42b247b9eba546b0c
        return redirect(url_for('login'))

    return render_template('signup.html')

<<<<<<< HEAD

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email    = request.form['email']
        password = request.form['password']
        user     = User.query.filter_by(email=email).first()
=======
# LOGIN
@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = request.form['email']
        password = request.form['password']

        user = User.query.filter_by(email=email).first()

>>>>>>> 4a6ae9744af7949d4d8fc2a42b247b9eba546b0c
        if user and bcrypt.checkpw(password.encode('utf-8'), user.password.encode('utf-8')):
            login_user(user)
            return redirect(url_for('dashboard'))
        else:
<<<<<<< HEAD
            flash("Credenciais inválidas.")
    return render_template('login.html')


=======
            flash("Invalid credentials")

    return render_template('login.html')

# Caso esqueceu senha - Request de reset FAZER ISSO MAIS PARA FRENTE
>>>>>>> 4a6ae9744af7949d4d8fc2a42b247b9eba546b0c
@app.route('/forgot-password', methods=['GET', 'POST'])
def forgot_password():
    if request.method == 'POST':
        email = request.form['email']
<<<<<<< HEAD
        user  = User.query.filter_by(email=email).first()
        if user:
=======
        user = User.query.filter_by(email=email).first()
        
        if user:
            # Gera token de reset
>>>>>>> 4a6ae9744af7949d4d8fc2a42b247b9eba546b0c
            token = secrets.token_urlsafe(32)
            user.reset_token = token
            user.reset_token_expiry = datetime.utcnow() + timedelta(hours=24)
            db.session.commit()
<<<<<<< HEAD
            reset_url = url_for('reset_password', token=token, _external=True)
            flash(f'Link para redefinição de senha: {reset_url}', 'info')
            print(f"\n=== LINK PARA REDEFINIÇÃO DE SENHA ===\n{reset_url}\n==========================\n")
        else:
            flash('Se esse e-mail existir, um link de redefinição foi enviado.', 'info')
        return redirect(url_for('login'))
    return render_template('forgot_password.html')


def send_reset_email(user_email, reset_url):
    try:
        msg = Message(
            subject="Solicitação de Redefinição de Senha",
            recipients=[user_email],
            html=render_template('email_reset_password.html', reset_url=reset_url),
            body=f"Para redefinir sua senha, acesse: {reset_url}\n\nEste link expira em 24 horas."
=======
            
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
>>>>>>> 4a6ae9744af7949d4d8fc2a42b247b9eba546b0c
        )
        mail.send(msg)
        return True
    except Exception as e:
<<<<<<< HEAD
        print(f"Erro ao enviar e-mail: {e}")
        return False


@app.route('/reset-password/<token>', methods=['GET', 'POST'])
def reset_password(token):
    user = User.query.filter_by(reset_token=token).first()
    if not user or user.reset_token_expiry < datetime.utcnow():
        flash('Link de redefinição inválido ou expirado.', 'error')
        return redirect(url_for('forgot_password'))
    if request.method == 'POST':
        password         = request.form['password']
        confirm_password = request.form['confirm-password']
        if len(password) < 6:
            flash('A senha deve ter no mínimo 6 caracteres.', 'error')
            return redirect(url_for('reset_password', token=token))
        if password != confirm_password:
            flash('As senhas não coincidem.', 'error')
            return redirect(url_for('reset_password', token=token))
        hashed_pw = bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt())
        user.password = hashed_pw.decode('utf-8')
        user.reset_token = None
        user.reset_token_expiry = None
        db.session.commit()
        flash('Senha redefinida com sucesso!', 'success')
        return redirect(url_for('login'))
    return render_template('reset_password.html', token=token)


=======
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
>>>>>>> 4a6ae9744af7949d4d8fc2a42b247b9eba546b0c
@app.route('/change-password', methods=['GET', 'POST'])
@login_required
def change_password():
    if request.method == 'POST':
        current_password = request.form['current_password']
<<<<<<< HEAD
        new_password     = request.form['new_password']
        confirm_password = request.form['confirm_password']
        if not bcrypt.checkpw(current_password.encode('utf-8'), current_user.password.encode('utf-8')):
            flash('A senha atual está incorreta.', 'error')
            return redirect(url_for('change_password'))
        if len(new_password) < 6:
            flash('A nova senha deve ter no mínimo 6 caracteres.', 'error')
            return redirect(url_for('change_password'))
        if new_password != confirm_password:
            flash('As senhas não coincidem.', 'error')
            return redirect(url_for('change_password'))
        hashed_pw = bcrypt.hashpw(new_password.encode('utf-8'), bcrypt.gensalt())
        current_user.password = hashed_pw.decode('utf-8')
        db.session.commit()
        flash('Senha alterada com sucesso!', 'success')
        return redirect(url_for('dashboard'))
    return render_template('change_password.html')


=======
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
>>>>>>> 4a6ae9744af7949d4d8fc2a42b247b9eba546b0c
@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('login'))
<<<<<<< HEAD


# ─────────────────────────────────────
# DASHBOARD
# ─────────────────────────────────────

@app.route('/dashboard')
@login_required
def dashboard():
    produtos  = Product.query.all()
    eventos   = EventoEspecial.query.filter_by(ativo=True).all()
    carrossel = CarrosselItem.query.filter_by(ativo=True).order_by(CarrosselItem.ordem).all()
    kits      = Kit.query.filter_by(is_admin_kit=True).all()
    return render_template('dashboard.html',
                           user=current_user,
                           produtos=produtos,
                           eventos=eventos,
                           carrossel=carrossel,
                           kits=kits)


# ─────────────────────────────────────
# PRODUCTS
# ─────────────────────────────────────

=======
# Rota de produtos
>>>>>>> 4a6ae9744af7949d4d8fc2a42b247b9eba546b0c
@app.route('/products')
def list_products():
    products = Product.query.all()
    return render_template('products.html', products=products)
<<<<<<< HEAD


=======
# Cria produtos
>>>>>>> 4a6ae9744af7949d4d8fc2a42b247b9eba546b0c
@app.route('/products/create', methods=['GET', 'POST'])
@login_required
@admin_required
def create_product():
    if request.method == 'POST':
<<<<<<< HEAD
        name        = request.form['name']
        description = request.form['description']
        price       = request.form['price']
        category    = request.form.get('category', 'geral')
        arquivo     = request.files.get('arquivo')
        try:
            price = float(price)
            if price <= 0:
                flash("O preço deve ser maior que 0.", 'error')
                return redirect(url_for('create_product'))
        except ValueError:
            flash("Formato de preço inválido.", 'error')
            return redirect(url_for('create_product'))
        image_url = salvar_imagem_produto(arquivo)
        product = Product(name=name, description=description,
                          price=price, category=category, image_url=image_url)
        db.session.add(product)
        db.session.commit()
        flash("Produto criado com sucesso!", 'success')
        return redirect(url_for('list_products'))
    return render_template('product_form.html')


=======
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
>>>>>>> 4a6ae9744af7949d4d8fc2a42b247b9eba546b0c
@app.route('/products/edit/<int:id>', methods=['GET', 'POST'])
@login_required
@admin_required
def edit_product(id):
    product = Product.query.get_or_404(id)
<<<<<<< HEAD
    if request.method == 'POST':
        product.name        = request.form['name']
        product.description = request.form['description']
        product.category    = request.form.get('category', 'geral')
        arquivo             = request.files.get('arquivo')
        try:
            product.price = float(request.form['price'])
            if product.price <= 0:
                flash("O preço deve ser maior que 0.", 'error')
                return redirect(url_for('edit_product', id=id))
        except ValueError:
            flash("Formato de preço inválido.", 'error')
            return redirect(url_for('edit_product', id=id))
        nova_imagem = salvar_imagem_produto(arquivo)
        if nova_imagem:
            product.image_url = nova_imagem
        db.session.commit()
        flash("Produto atualizado com sucesso!", 'success')
        return redirect(url_for('list_products'))
    return render_template('product_form.html', product=product)


=======

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
>>>>>>> 4a6ae9744af7949d4d8fc2a42b247b9eba546b0c
@app.route('/products/delete/<int:id>')
@login_required
@admin_required
def delete_product(id):
    product = Product.query.get_or_404(id)
<<<<<<< HEAD
    db.session.delete(product)
    db.session.commit()
    flash("Produto excluído com sucesso!")
    return redirect(url_for('list_products'))


# ─────────────────────────────────────
# KITS
# ─────────────────────────────────────

=======
    
    db.session.delete(product)
    db.session.commit()

    flash("Produto deletado com sucesso!")
    return redirect(url_for('list_products'))
# Rotas de Kits
>>>>>>> 4a6ae9744af7949d4d8fc2a42b247b9eba546b0c
@app.route('/kits')
@login_required
def list_kits():
    if current_user.is_admin:
        kits = Kit.query.order_by(Kit.created_at.desc()).all()
    else:
<<<<<<< HEAD
        kits = Kit.query.filter(
            (Kit.created_by == current_user.id) | (Kit.is_admin_kit == True)
        ).order_by(Kit.created_at.desc()).all()
    return render_template('kits/list.html', kits=kits)


=======
        # Lista os kits do usuário e os do adm
        kits = Kit.query.filter(
            (Kit.created_by == current_user.id) | (Kit.is_admin_kit == True)
        ).order_by(Kit.created_at.desc()).all()
    
    return render_template('kits/list.html', kits=kits)

>>>>>>> 4a6ae9744af7949d4d8fc2a42b247b9eba546b0c
@app.route('/kits/<int:kit_id>')
@login_required
def view_kit(kit_id):
    kit = Kit.query.get_or_404(kit_id)
<<<<<<< HEAD
    if not (current_user.is_admin or kit.is_admin_kit or kit.created_by == current_user.id):
        flash("Você não tem permissão para visualizar este kit.", "error")
        return redirect(url_for('list_kits'))
    return render_template('kits/view.html', kit=kit)


=======
    
    # Checa visibilidade 
    if not (current_user.is_admin or kit.is_admin_kit or kit.created_by == current_user.id):
        flash("You don't have permission to view this kit.", "error")
        return redirect(url_for('list_kits'))
    
    return render_template('kits/view.html', kit=kit)

# Rota de criação de kit
>>>>>>> 4a6ae9744af7949d4d8fc2a42b247b9eba546b0c
@app.route('/kits/create', methods=['GET', 'POST'])
@login_required
def create_kit():
    if request.method == 'POST':
<<<<<<< HEAD
        name        = request.form.get('name', '').strip()
        description = request.form.get('description', '').strip()
        arquivo     = request.files.get('arquivo')
        if not name:
            flash("O nome do kit é obrigatório.", 'error')
            return redirect(url_for('create_kit'))
        image_url = None
        if arquivo and arquivo.filename != '':
            ext = arquivo.filename.rsplit('.', 1)[-1].lower()
            if ext in ALLOWED_EXTENSIONS:
                filename = f"{int(time.time())}_{secure_filename(arquivo.filename)}"
                arquivo.save(os.path.join(UPLOAD_FOLDER_KITS, filename))
                image_url = f"uploads/kits/{filename}"
        kit = Kit(name=name, description=description,
                  created_by=current_user.id, image_url=image_url,
                  is_admin_kit=current_user.is_admin)
        db.session.add(kit)
        db.session.commit()
        flash(f"Kit '{kit.name}' criado com sucesso!", 'success')
        return redirect(url_for('edit_kit_products', kit_id=kit.id))
    return render_template('kits/create.html')


=======
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

>>>>>>> 4a6ae9744af7949d4d8fc2a42b247b9eba546b0c
@app.route('/kits/<int:kit_id>/edit', methods=['GET', 'POST'])
@login_required
def edit_kit(kit_id):
    kit = Kit.query.get_or_404(kit_id)
<<<<<<< HEAD
    if not user_can_edit_kit(kit):
        flash("Você não tem permissão para editar este kit.", 'error')
        return redirect(url_for('list_kits'))
    if request.method == 'POST':
        kit.name        = request.form.get('name', '').strip()
        kit.description = request.form.get('description', '').strip()
        arquivo         = request.files.get('arquivo')
        if arquivo and arquivo.filename != '':
            ext = arquivo.filename.rsplit('.', 1)[-1].lower()
            if ext in ALLOWED_EXTENSIONS:
                filename = f"{int(time.time())}_{secure_filename(arquivo.filename)}"
                arquivo.save(os.path.join(UPLOAD_FOLDER_KITS, filename))
                kit.image_url = f"uploads/kits/{filename}"
        db.session.commit()
        flash("Kit atualizado!", 'success')
        return redirect(url_for('view_kit', kit_id=kit.id))
=======
    
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
    
>>>>>>> 4a6ae9744af7949d4d8fc2a42b247b9eba546b0c
    return render_template('kits/edit.html', kit=kit)


@app.route('/kits/<int:kit_id>/delete', methods=['POST'])
@login_required
def delete_kit(kit_id):
    kit = Kit.query.get_or_404(kit_id)
<<<<<<< HEAD
    if not user_can_edit_kit(kit):
        flash("Você não tem permissão para excluir este kit.", "error")
        return redirect(url_for('list_kits'))
    db.session.delete(kit)
    db.session.commit()
    flash("Kit excluído com sucesso!", "success")
    return redirect(url_for('list_kits'))


=======
    
    if not user_can_edit_kit(kit):
        flash("Você não tem permissão para deletar o kit", "error")
        return redirect(url_for('list_kits'))
    
    db.session.delete(kit)
    db.session.commit()
    flash("Kit deleted.", "success")
    return redirect(url_for('list_kits'))

>>>>>>> 4a6ae9744af7949d4d8fc2a42b247b9eba546b0c
@app.route('/kits/<int:kit_id>/products', methods=['GET', 'POST'])
@login_required
def edit_kit_products(kit_id):
    kit = Kit.query.get_or_404(kit_id)
<<<<<<< HEAD
    if not user_can_edit_kit(kit):
        flash("Você não tem permissão para modificar este kit.", "error")
        return redirect(url_for('list_kits'))
    all_products = Product.query.order_by(Product.name).all()
    kit_products = {kp.product_id: kp for kp in kit.products}
    if request.method == 'POST':
        product_ids   = request.form.getlist('product_id')
        quantities    = request.form.getlist('quantity')
=======
    
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
>>>>>>> 4a6ae9744af7949d4d8fc2a42b247b9eba546b0c
        submitted_ids = set(int(pid) for pid in product_ids)
        for kp in kit.products:
            if kp.product_id not in submitted_ids:
                db.session.delete(kp)
<<<<<<< HEAD
=======
        
        # Adiciona ou atualiza produtos selecionados
>>>>>>> 4a6ae9744af7949d4d8fc2a42b247b9eba546b0c
        for pid, qty in zip(product_ids, quantities):
            pid = int(pid)
            qty = int(qty) if qty.isdigit() and int(qty) > 0 else 1
            existing = KitProduct.query.get((kit_id, pid))
            if existing:
                existing.quantity = qty
            else:
                new_kp = KitProduct(kit_id=kit_id, product_id=pid, quantity=qty)
                db.session.add(new_kp)
<<<<<<< HEAD
        db.session.commit()
        flash("Produtos do kit atualizados!", "success")
        return redirect(url_for('view_kit', kit_id=kit.id))
    return render_template('kits/manage_products.html',
                           kit=kit, all_products=all_products,
                           kit_products=kit_products)


# ─────────────────────────────────────
# LOJA PÚBLICA
# ─────────────────────────────────────

@app.route('/categoria/<nome>')
def categoria(nome):
    produtos = Product.query.filter_by(category=nome).all()
    return render_template('categoria.html', produtos=produtos, categoria=nome)


@app.route('/kits_loja')
def kits_loja():
    kits = Kit.query.filter_by(is_admin_kit=True).all()
    return render_template('kits_loja.html', kits=kits)


@app.route('/produto/<int:id>')
def produto_detalhe(id):
    produto = Product.query.get_or_404(id)
    relacionados = Product.query.filter(
        Product.category == produto.category,
        Product.id != produto.id
    ).limit(4).all()
    return render_template('produto_detalhe.html',
                           produto=produto,
                           relacionados=relacionados,
                           is_kit=False)


@app.route('/kit-detalhe/<int:kit_id>')
def kit_detalhe(kit_id):
    kit = Kit.query.get_or_404(kit_id)

    class KitAdapter:
        def __init__(self, k):
            self.id          = k.id
            self.name        = k.name
            self.category    = 'Kits'
            self.description = k.description or ''
            self.price       = k.total_price
            self.image_url   = k.image_url

    produto = KitAdapter(kit)

    outros_kits = Kit.query.filter(
        Kit.is_admin_kit == True,
        Kit.id != kit_id
    ).limit(4).all()

    class KitRelAdapter:
        def __init__(self, k):
            self.id        = k.id
            self.name      = k.name
            self.price     = k.total_price
            self.image_url = k.image_url

    relacionados = [KitRelAdapter(k) for k in outros_kits]

    return render_template('produto_detalhe.html',
                           produto=produto,
                           relacionados=relacionados,
                           is_kit=True,
                           kit=kit)


@app.route('/produto-especial/<int:id>')
def produto_especial_detalhe(id):
    produto = ProdutoEspecial.query.get_or_404(id)
    if not produto.mostrar:
        flash('Este produto não está disponível.', 'info')
        return redirect(url_for('dashboard'))
    relacionados = ProdutoEspecial.query.filter(
        ProdutoEspecial.evento_id == produto.evento_id,
        ProdutoEspecial.id != produto.id,
        ProdutoEspecial.mostrar == True
    ).limit(4).all()
    return render_template('produto_detalhe.html',
                           produto=produto,
                           relacionados=relacionados,
                           is_kit=False)


@app.route('/busca')
def busca():
    termo = request.args.get('q', '').strip()
    if not termo:
        return redirect(url_for('dashboard'))
    produtos  = Product.query.filter(Product.name.ilike(f'%{termo}%')).all()
    especiais = ProdutoEspecial.query.filter(
        ProdutoEspecial.name.ilike(f'%{termo}%'),
        ProdutoEspecial.mostrar == True
    ).all()
    kits = Kit.query.filter(
        Kit.name.ilike(f'%{termo}%'),
        Kit.is_admin_kit == True
    ).all()
    return render_template('busca.html', termo=termo,
                           produtos=produtos, especiais=especiais, kits=kits)


# ─────────────────────────────────────
# EVENTOS ESPECIAIS
# ─────────────────────────────────────

@app.route('/special/eventos')
@login_required
@admin_required
def listar_eventos():
    eventos = EventoEspecial.query.order_by(EventoEspecial.created_at.desc()).all()
    return render_template('special/eventos.html', eventos=eventos)


@app.route('/special/eventos/criar', methods=['GET', 'POST'])
@login_required
@admin_required
def criar_evento():
    if request.method == 'POST':
        nome      = request.form.get('nome', '').strip()
        descricao = request.form.get('descricao', '').strip()
        if not nome:
            flash('O nome do evento é obrigatório.', 'error')
            return redirect(url_for('criar_evento'))
        if EventoEspecial.query.filter_by(nome=nome).first():
            flash('Já existe um evento com esse nome.', 'error')
            return redirect(url_for('criar_evento'))
        evento = EventoEspecial(nome=nome, descricao=descricao)
        db.session.add(evento)
        db.session.commit()
        flash(f'Evento "{nome}" criado com sucesso!', 'success')
        return redirect(url_for('listar_eventos'))
    return render_template('special/criar_evento.html')


@app.route('/special/eventos/<int:id>/toggle-ativo')
@login_required
@admin_required
def toggle_evento_ativo(id):
    evento = EventoEspecial.query.get_or_404(id)
    evento.ativo = not evento.ativo
    db.session.commit()
    status = 'ativado' if evento.ativo else 'desativado'
    flash(f'Evento "{evento.nome}" {status}!', 'success')
    return redirect(url_for('listar_eventos'))


@app.route('/special/eventos/<int:id>/deletar', methods=['POST'])
@login_required
@admin_required
def deletar_evento(id):
    evento = EventoEspecial.query.get_or_404(id)
    db.session.delete(evento)
    db.session.commit()
    flash(f'Evento "{evento.nome}" deletado!', 'success')
    return redirect(url_for('listar_eventos'))


@app.route('/special/eventos/<int:evento_id>/produtos')
@login_required
@admin_required
def listar_produtos_especiais(evento_id):
    evento   = EventoEspecial.query.get_or_404(evento_id)
    produtos = ProdutoEspecial.query.filter_by(evento_id=evento_id).all()
    return render_template('special/produtos_especiais.html', evento=evento, produtos=produtos)


@app.route('/special/eventos/<int:evento_id>/produtos/criar', methods=['GET', 'POST'])
@login_required
@admin_required
def criar_produto_especial(evento_id):
    evento = EventoEspecial.query.get_or_404(evento_id)
    if request.method == 'POST':
        name        = request.form.get('name', '').strip()
        description = request.form.get('description', '').strip()
        price       = request.form.get('price')
        category    = request.form.get('category', 'geral')
        mostrar     = 'mostrar' in request.form   # ✅ sem disponivel
        arquivo     = request.files.get('arquivo')

        if not name or not description or not price:
            flash('Nome, descrição e preço são obrigatórios.', 'error')
            return redirect(url_for('criar_produto_especial', evento_id=evento_id))
        try:
            price = float(price)
            if price <= 0:
                raise ValueError
        except ValueError:
            flash('Preço inválido.', 'error')
            return redirect(url_for('criar_produto_especial', evento_id=evento_id))

        image_url = None
        if arquivo and arquivo.filename != '':
            ext = arquivo.filename.rsplit('.', 1)[-1].lower()
            if ext in ALLOWED_EXTENSIONS:
                filename = f"{int(time.time())}_{secure_filename(arquivo.filename)}"
                arquivo.save(os.path.join(UPLOAD_FOLDER_ESPECIAIS, filename))
                image_url = f"uploads/especiais/{filename}"

        produto = ProdutoEspecial(
            evento_id=evento_id,
            name=name,
            description=description,
            price=price,
            category=category,
            image_url=image_url,
            mostrar=mostrar    # ✅ sem disponivel
        )
        db.session.add(produto)
        db.session.commit()
        flash(f'Produto "{name}" criado!', 'success')
        return redirect(url_for('listar_produtos_especiais', evento_id=evento_id))
    return render_template('special/criar_produto_especial.html', evento=evento)


@app.route('/special/produtos-especiais/<int:id>/editar', methods=['GET', 'POST'])
@login_required
@admin_required
def editar_produto_especial(id):
    produto = ProdutoEspecial.query.get_or_404(id)
    if request.method == 'POST':
        produto.name        = request.form.get('name', '').strip()
        produto.description = request.form.get('description', '').strip()
        produto.category    = request.form.get('category', 'geral')
        produto.mostrar     = 'mostrar' in request.form   # ✅ sem disponivel
        arquivo             = request.files.get('arquivo')

        try:
            produto.price = float(request.form.get('price'))
            if produto.price <= 0:
                raise ValueError
        except ValueError:
            flash('Preço inválido.', 'error')
            return redirect(url_for('editar_produto_especial', id=id))

        if arquivo and arquivo.filename != '':
            ext = arquivo.filename.rsplit('.', 1)[-1].lower()
            if ext in ALLOWED_EXTENSIONS:
                filename = f"{int(time.time())}_{secure_filename(arquivo.filename)}"
                arquivo.save(os.path.join(UPLOAD_FOLDER_ESPECIAIS, filename))
                produto.image_url = f"uploads/especiais/{filename}"

        db.session.commit()
        flash(f'Produto "{produto.name}" atualizado!', 'success')
        return redirect(url_for('listar_produtos_especiais', evento_id=produto.evento_id))
    return render_template('special/editar_produto_especial.html', produto=produto)


@app.route('/special/produtos-especiais/<int:id>/deletar', methods=['POST'])
@login_required
@admin_required
def deletar_produto_especial(id):
    produto   = ProdutoEspecial.query.get_or_404(id)
    evento_id = produto.evento_id
    db.session.delete(produto)
    db.session.commit()
    flash(f'Produto "{produto.name}" deletado!', 'success')
    return redirect(url_for('listar_produtos_especiais', evento_id=evento_id))


@app.route('/special/produtos-especiais/<int:id>/toggle-mostrar')
@login_required
@admin_required
def toggle_mostrar(id):
    produto = ProdutoEspecial.query.get_or_404(id)
    produto.mostrar = not produto.mostrar
    db.session.commit()
    return redirect(url_for('listar_produtos_especiais', evento_id=produto.evento_id))


@app.route('/evento/<int:id>')
def pagina_evento(id):
    evento = EventoEspecial.query.get_or_404(id)
    if not evento.ativo:
        flash('Este evento não está disponível.', 'info')
        return redirect(url_for('dashboard'))
    produtos = ProdutoEspecial.query.filter_by(evento_id=id, mostrar=True).all()
    return render_template('special/evento.html', evento=evento, produtos=produtos)


# ─────────────────────────────────────
# CARRINHO
# ─────────────────────────────────────

WHATSAPP_NUMBER = '5511967630831'


@app.route('/carrinho')
@login_required
def carrinho():
    itens            = CarrinhoItem.query.filter_by(user_id=current_user.id).all()
    total            = sum(item.subtotal for item in itens)
    quantidade_total = sum(item.quantidade for item in itens)
    return render_template('carrinho.html', itens=itens,
                           total=total, quantidade_total=quantidade_total)


@app.route('/carrinho/adicionar', methods=['POST'])
@login_required
def adicionar_carrinho():
    produto_id  = request.form.get('produto_id', type=int)
    kit_id      = request.form.get('kit_id', type=int)
    especial_id = request.form.get('especial_id', type=int)
    quantidade  = request.form.get('quantidade', 1, type=int)
    proxima_url = request.form.get('next', url_for('carrinho'))

    item = CarrinhoItem.query.filter_by(
        user_id=current_user.id,
        produto_id=produto_id,
        kit_id=kit_id,
        especial_id=especial_id
    ).first()

    if item:
        item.quantidade += quantidade
    else:
        item = CarrinhoItem(user_id=current_user.id,
                            produto_id=produto_id, kit_id=kit_id,
                            especial_id=especial_id, quantidade=quantidade)
        db.session.add(item)

    db.session.commit()
    flash('Produto adicionado ao carrinho!', 'success')
    return redirect(proxima_url)


@app.route('/carrinho/remover/<int:item_id>', methods=['POST'])
@login_required
def remover_carrinho(item_id):
    item = CarrinhoItem.query.filter_by(id=item_id, user_id=current_user.id).first_or_404()
    db.session.delete(item)
    db.session.commit()
    flash('Item removido do carrinho.', 'info')
    return redirect(url_for('carrinho'))


@app.route('/carrinho/atualizar/<int:item_id>', methods=['POST'])
@login_required
def atualizar_carrinho(item_id):
    item       = CarrinhoItem.query.filter_by(id=item_id, user_id=current_user.id).first_or_404()
    quantidade = request.form.get('quantidade', 1, type=int)
    if quantidade < 1:
        db.session.delete(item)
    else:
        item.quantidade = quantidade
    db.session.commit()
    return redirect(url_for('carrinho'))


@app.route('/carrinho/esvaziar', methods=['POST'])
@login_required
def esvaziar_carrinho():
    CarrinhoItem.query.filter_by(user_id=current_user.id).delete()
    db.session.commit()
    flash('Carrinho esvaziado.', 'info')
    return redirect(url_for('carrinho'))


@app.route('/carrinho/finalizar')
@login_required
def finalizar_pedido():
    itens = CarrinhoItem.query.filter_by(user_id=current_user.id).all()
    if not itens:
        flash('Seu carrinho está vazio!', 'error')
        return redirect(url_for('carrinho'))

    linhas = ['🛍️ *Olá! Quero fazer um pedido:*\n']
    total  = 0
    for item in itens:
        subtotal = item.subtotal
        total   += subtotal
        linhas.append(f'• *{item.nome}*')
        linhas.append(f'  Qtd: {item.quantidade} x R$ {item.preco_unit:.2f} = R$ {subtotal:.2f}')

    linhas.append(f'\n💰 *Total: R$ {total:.2f}*')
    linhas.append(f'\n📧 Email: {current_user.email}')

    import urllib.parse
    msg_encoded   = urllib.parse.quote('\n'.join(linhas))
    whatsapp_url  = f'https://wa.me/{WHATSAPP_NUMBER}?text={msg_encoded}'

    CarrinhoItem.query.filter_by(user_id=current_user.id).delete()
    db.session.commit()
    return redirect(whatsapp_url)


# ─────────────────────────────────────
# CARROSSEL ADMIN
# ─────────────────────────────────────

@app.route('/carrossel')
@login_required
@admin_required
def carrossel_admin():
    return render_template('carrossel_form.html')


@app.route('/carrossel/listar')
@login_required
@admin_required
def carrossel_listar():
    itens = CarrosselItem.query.order_by(CarrosselItem.ordem).all()
    return render_template('listar_carrossel.html', itens=itens)


@app.route('/carrossel/adicionar', methods=['POST'])
@login_required
@admin_required
def carrossel_adicionar():
    titulo    = request.form.get('titulo', '').strip()
    subtitulo = request.form.get('subtitulo', '').strip()
    ordem     = request.form.get('ordem', 0, type=int)
    arquivo   = request.files.get('imagem')

    if not arquivo or arquivo.filename == '':
        flash('Selecione uma imagem.', 'error')
        return redirect(url_for('carrossel_admin'))
    if not allowed_file(arquivo.filename):
        flash('Formato inválido. Use PNG, JPG, JPEG ou WEBP.', 'error')
        return redirect(url_for('carrossel_admin'))

    filename = f"{int(time.time())}_{secure_filename(arquivo.filename)}"
    arquivo.save(os.path.join(UPLOAD_FOLDER_CARROSSEL, filename))

    item = CarrosselItem(titulo=titulo or None, subtitulo=subtitulo or None,
                         imagem=filename, ordem=ordem)
    db.session.add(item)
    db.session.commit()
    flash('Imagem adicionada ao carrossel!', 'success')
    return redirect(url_for('carrossel_listar'))


@app.route('/carrossel/<int:id>/toggle')
@login_required
@admin_required
def carrossel_toggle(id):
    item = CarrosselItem.query.get_or_404(id)
    item.ativo = not item.ativo
    db.session.commit()
    return redirect(url_for('carrossel_listar'))


@app.route('/carrossel/<int:id>/deletar', methods=['POST'])
@login_required
@admin_required
def carrossel_deletar(id):
    item    = CarrosselItem.query.get_or_404(id)
    caminho = os.path.join(UPLOAD_FOLDER_CARROSSEL, item.imagem)
    if os.path.exists(caminho):
        os.remove(caminho)
    db.session.delete(item)
    db.session.commit()
    flash('Imagem removida do carrossel!', 'success')
    return redirect(url_for('carrossel_listar'))


@app.route('/carrossel/<int:id>/ordem', methods=['POST'])
@login_required
@admin_required
def carrossel_ordem(id):
    item       = CarrosselItem.query.get_or_404(id)
    item.ordem = request.form.get('ordem', 0, type=int)
    db.session.commit()
    return redirect(url_for('carrossel_listar'))


# ─────────────────────────────────────
# RUN
# ─────────────────────────────────────
=======
        
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
>>>>>>> 4a6ae9744af7949d4d8fc2a42b247b9eba546b0c
if __name__ == '__main__':
    app.run(debug=True)