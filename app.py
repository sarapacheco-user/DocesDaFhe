from functools import wraps
from flask import Flask, render_template, request, redirect, url_for, flash
from flask_login import LoginManager, login_user, login_required, logout_user, current_user
from flask_mail import Mail, Message
from models import db, User, Product, Kit, KitProduct, EventoEspecial, ProdutoEspecial, CarrinhoItem, CarrosselItem, SiteConfig
import bcrypt
import re
import requests
import secrets
from werkzeug.utils import secure_filename
from datetime import datetime, timedelta
import time
import os
from dotenv import load_dotenv
load_dotenv()

app = Flask(__name__)
app.config['SECRET_KEY'] = 'supersecret'
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///users.db'

# Email Configuration
app.config['MAIL_SERVER'] = os.environ.get('MAIL_SERVER', 'smtp.gmail.com')
app.config['MAIL_PORT'] = int(os.environ.get('MAIL_PORT', 587))
app.config['MAIL_USE_TLS'] = os.environ.get('MAIL_USE_TLS', 'True') == 'True'
app.config['MAIL_USERNAME'] = os.environ.get('MAIL_USERNAME')
app.config['MAIL_PASSWORD'] = os.environ.get('MAIL_PASSWORD')
app.config['MAIL_DEFAULT_SENDER'] = os.environ.get('MAIL_DEFAULT_SENDER')

mail = Mail(app)

# ── UPLOAD FOLDERS ──
UPLOAD_FOLDER_CARROSSEL = os.path.join('static', 'uploads', 'carrossel')
UPLOAD_FOLDER_PRODUTOS  = os.path.join('static', 'uploads', 'produtos')
UPLOAD_FOLDER_KITS      = os.path.join('static', 'uploads', 'kits')
UPLOAD_FOLDER_ESPECIAIS = os.path.join('static', 'uploads', 'especiais')
UPLOAD_FOLDER_LOGO      = os.path.join('static', 'uploads', 'logo')
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'webp', 'gif'}

for folder in [UPLOAD_FOLDER_CARROSSEL, UPLOAD_FOLDER_PRODUTOS,
               UPLOAD_FOLDER_KITS, UPLOAD_FOLDER_ESPECIAIS, UPLOAD_FOLDER_LOGO]:
    os.makedirs(folder, exist_ok=True)


def darken_hex(hex_color, factor=0.82):
    try:
        hex_color = hex_color.lstrip('#')
        r, g, b = (int(hex_color[i:i+2], 16) for i in (0, 2, 4))
        r, g, b = max(0, int(r*factor)), max(0, int(g*factor)), max(0, int(b*factor))
        return f"#{r:02x}{g:02x}{b:02x}"
    except Exception:
        return f"#{hex_color}"


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
login_manager = LoginManager()
login_manager.login_view = 'login'
login_manager.login_message = 'Faça login para acessar essa página.'
login_manager.login_message_category = 'info'
login_manager.init_app(app)
db.init_app(app)
app.jinja_env.filters['darken'] = darken_hex


def admin_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not current_user.is_authenticated or not current_user.is_admin:
            flash("Acesso negado. São necessárias permissões de administrador.", "error")
            return redirect(url_for('dashboard'))
        return f(*args, **kwargs)
    return decorated_function

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))


with app.app_context():
    db.create_all()


def user_can_edit_kit(kit):
    if current_user.is_admin:
        return True
    return (not kit.is_admin_kit) and (kit.created_by == current_user.id)


# ── CONTEXT PROCESSOR ──
@app.context_processor
def inject_globals():
    if current_user.is_authenticated:
        total_itens = db.session.query(
            db.func.sum(CarrinhoItem.quantidade)
        ).filter_by(user_id=current_user.id).scalar() or 0
    else:
        total_itens = 0
    site_config = SiteConfig.query.first()
    return dict(carrinho_total=total_itens, site_config=site_config)


# ─────────────────────────────────────
# ROTAS GERAIS
# ─────────────────────────────────────

@app.route('/')
def home():
    return redirect(url_for('dashboard'))


@app.route('/signup', methods=['GET', 'POST'])
def signup():
    if request.method == 'POST':
        name             = request.form['name']
        email            = request.form['email']
        password         = request.form['password']
        confirm_password = request.form['confirm-password']
        phone            = request.form['phone']
        cep              = request.form['cep']

        def validate_phone(phone):
            phone = re.sub(r'\D', '', phone)
            return re.match(r'^\d{10,11}$', phone)

        def validate_cep_exists(cep):
            cep = ''.join(filter(str.isdigit, cep))
            if len(cep) != 8:
                return False
            try:
                response = requests.get(f'https://viacep.com.br/ws/{cep}/json/')
                data = response.json()
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
        return redirect(url_for('login'))

    return render_template('auth/signup.html')


@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email    = request.form['email']
        password = request.form['password']
        user     = User.query.filter_by(email=email).first()
        if user and bcrypt.checkpw(password.encode('utf-8'), user.password.encode('utf-8')):
            login_user(user)
            return redirect(url_for('dashboard'))
        else:
            flash("Credenciais inválidas.")
    return render_template('auth/login.html')


@app.route('/forgot-password', methods=['GET', 'POST'])
def forgot_password():
    if request.method == 'POST':
        email = request.form['email']
        user  = User.query.filter_by(email=email).first()
        if user:
            token = secrets.token_urlsafe(32)
            user.reset_token = token
            user.reset_token_expiry = datetime.utcnow() + timedelta(hours=24)
            db.session.commit()
            reset_url = url_for('reset_password', token=token, _external=True)
            flash(f'Link para redefinição de senha: {reset_url}', 'info')
            print(f"\n=== LINK PARA REDEFINIÇÃO DE SENHA ===\n{reset_url}\n==========================\n")
        else:
            flash('Se esse e-mail existir, um link de redefinição foi enviado.', 'info')
        return redirect(url_for('login'))
    return render_template('auth/forgot_password.html')


def send_reset_email(user_email, reset_url):
    try:
        msg = Message(
            subject="Solicitação de Redefinição de Senha",
            recipients=[user_email],
            html=render_template('auth/email_reset_password.html', reset_url=reset_url),
            body=f"Para redefinir sua senha, acesse: {reset_url}\n\nEste link expira em 24 horas."
        )
        mail.send(msg)
        return True
    except Exception as e:
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
    return render_template('auth/reset_password.html', token=token)


@app.route('/change-password', methods=['GET', 'POST'])
@login_required
def change_password():
    if request.method == 'POST':
        current_password = request.form['current_password']
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
    return render_template('auth/change_password.html')


@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('login'))


# ─────────────────────────────────────
# DASHBOARD
# ─────────────────────────────────────

@app.route('/dashboard')
def dashboard():
    produtos  = Product.query.filter_by(ativo=True).all()
    eventos   = EventoEspecial.query.filter_by(ativo=True).all()
    carrossel = CarrosselItem.query.filter_by(ativo=True).order_by(CarrosselItem.ordem).all()
    kits      = Kit.query.filter_by(is_admin_kit=True, ativo=True).all()
    return render_template('dashboard.html',
                           user=current_user,
                           produtos=produtos,
                           eventos=eventos,
                           carrossel=carrossel,
                           kits=kits)


# ─────────────────────────────────────
# PRODUCTS
# ─────────────────────────────────────

@app.route('/products')
def list_products():
    products = Product.query.all()
    return render_template('product/produtos.html', products=products)


@app.route('/products/create', methods=['GET', 'POST'])
@login_required
@admin_required
def create_product():
    if request.method == 'POST':
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
    return render_template('product/produto_form.html')


@app.route('/products/edit/<int:id>', methods=['GET', 'POST'])
@login_required
@admin_required
def edit_product(id):
    product = Product.query.get_or_404(id)
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
    return render_template('product/produto_form.html', product=product)


@app.route('/products/delete/<int:id>')
@login_required
@admin_required
def delete_product(id):
    product = Product.query.get_or_404(id)
    db.session.delete(product)
    db.session.commit()
    flash("Produto excluído com sucesso!")
    return redirect(url_for('list_products'))


@app.route('/products/<int:id>/toggle-ativo')
@login_required
@admin_required
def toggle_product_ativo(id):
    product = Product.query.get_or_404(id)
    product.ativo = not product.ativo
    db.session.commit()
    status = 'mostrado' if product.ativo else 'ocultado'
    flash(f'Produto "{product.name}" {status}!', 'success')
    return redirect(url_for('list_products'))


# ─────────────────────────────────────
# KITS
# ─────────────────────────────────────

@app.route('/kits')
@login_required
def list_kits():
    if current_user.is_admin:
        kits = Kit.query.order_by(Kit.created_at.desc()).all()
    else:
        kits = Kit.query.filter(
            (Kit.created_by == current_user.id) | (Kit.is_admin_kit == True)
        ).order_by(Kit.created_at.desc()).all()
    return render_template('kits/list.html', kits=kits)


@app.route('/kits/<int:kit_id>')
@login_required
def view_kit(kit_id):
    kit = Kit.query.get_or_404(kit_id)
    if not (current_user.is_admin or kit.is_admin_kit or kit.created_by == current_user.id):
        flash("Você não tem permissão para visualizar este kit.", "error")
        return redirect(url_for('list_kits'))
    return render_template('kits/view.html', kit=kit)


@app.route('/kits/create', methods=['GET', 'POST'])
@login_required
def create_kit():
    if request.method == 'POST':
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


@app.route('/kits/<int:kit_id>/edit', methods=['GET', 'POST'])
@login_required
def edit_kit(kit_id):
    kit = Kit.query.get_or_404(kit_id)
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
    return render_template('kits/edit.html', kit=kit)


@app.route('/kits/<int:kit_id>/delete', methods=['POST'])
@login_required
def delete_kit(kit_id):
    kit = Kit.query.get_or_404(kit_id)
    if not user_can_edit_kit(kit):
        flash("Você não tem permissão para excluir este kit.", "error")
        return redirect(url_for('list_kits'))
    db.session.delete(kit)
    db.session.commit()
    flash("Kit excluído com sucesso!", "success")
    return redirect(url_for('list_kits'))


@app.route('/kits/<int:kit_id>/toggle-ativo', methods=['POST'])
@login_required
@admin_required
def toggle_kit_ativo(kit_id):
    kit = Kit.query.get_or_404(kit_id)
    kit.ativo = not kit.ativo
    db.session.commit()
    status = 'mostrado' if kit.ativo else 'ocultado'
    flash(f'Kit "{kit.name}" {status}!', 'success')
    return redirect(url_for('list_kits'))


@app.route('/kits/<int:kit_id>/products', methods=['GET', 'POST'])
@login_required
def edit_kit_products(kit_id):
    kit = Kit.query.get_or_404(kit_id)
    if not user_can_edit_kit(kit):
        flash("Você não tem permissão para modificar este kit.", "error")
        return redirect(url_for('list_kits'))
    all_products = Product.query.order_by(Product.name).all()
    kit_products = {kp.product_id: kp for kp in kit.products}
    if request.method == 'POST':
        product_ids   = request.form.getlist('product_id')
        quantities    = request.form.getlist('quantity')
        submitted_ids = set(int(pid) for pid in product_ids)
        for kp in kit.products:
            if kp.product_id not in submitted_ids:
                db.session.delete(kp)
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
        flash("Produtos do kit atualizados!", "success")
        return redirect(url_for('view_kit', kit_id=kit.id))
    return render_template('kits/manage_produtos.html',
                           kit=kit, all_products=all_products,
                           kit_products=kit_products)


# ─────────────────────────────────────
# LOJA PÚBLICA
# ─────────────────────────────────────

@app.route('/categoria/<nome>')
def categoria(nome):
    produtos = Product.query.filter_by(category=nome, ativo=True).all()
    return render_template('product/categoria.html', produtos=produtos, categoria=nome)


@app.route('/kits_loja')
def kits_loja():
    kits = Kit.query.filter_by(is_admin_kit=True, ativo=True).all()
    produtos = Product.query.filter_by(ativo=True).order_by(Product.category, Product.name).all()
    return render_template('kits/kits_loja.html', kits=kits, produtos=produtos)


@app.route('/montar-kit')
@login_required
def montar_kit():
    produtos = Product.query.filter_by(ativo=True).order_by(Product.category, Product.name).all()
    return render_template('kits/montar_kit.html', produtos=produtos)


@app.route('/montar-kit/adicionar', methods=['POST'])
@login_required
def montar_kit_adicionar():
    produto_ids = request.form.getlist('produto_id')
    adicionados = 0
    for pid in produto_ids:
        pid = int(pid)
        qty = request.form.get(f'qty_{pid}', 1, type=int)
        if qty < 1:
            continue
        item = CarrinhoItem.query.filter_by(
            user_id=current_user.id, produto_id=pid, kit_id=None, especial_id=None
        ).first()
        if item:
            item.quantidade += qty
        else:
            db.session.add(CarrinhoItem(user_id=current_user.id, produto_id=pid, quantidade=qty))
        adicionados += 1
    if adicionados:
        db.session.commit()
        flash(f'{adicionados} produto(s) adicionado(s) ao carrinho!', 'success')
    else:
        flash('Selecione pelo menos um produto para montar seu kit.', 'warning')
    return redirect(url_for('carrinho'))


@app.route('/produto/<int:id>')
def produto_detalhe(id):
    produto = Product.query.get_or_404(id)
    relacionados = Product.query.filter(
        Product.category == produto.category,
        Product.id != produto.id,
        Product.ativo == True
    ).limit(4).all()
    return render_template('product/produto_detalhe.html',
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
        Kit.id != kit_id,
        Kit.ativo == True
    ).limit(4).all()

    class KitRelAdapter:
        def __init__(self, k):
            self.id        = k.id
            self.name      = k.name
            self.price     = k.total_price
            self.image_url = k.image_url

    relacionados = [KitRelAdapter(k) for k in outros_kits]

    return render_template('product/produto_detalhe.html',
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
    return render_template('product/produto_detalhe.html',
                           produto=produto,
                           relacionados=relacionados,
                           is_kit=False)


@app.route('/busca')
def busca():
    termo = request.args.get('q', '').strip()
    if not termo:
        return redirect(url_for('dashboard'))
    produtos  = Product.query.filter(Product.name.ilike(f'%{termo}%'), Product.ativo == True).all()
    especiais = ProdutoEspecial.query.filter(
        ProdutoEspecial.name.ilike(f'%{termo}%'),
        ProdutoEspecial.mostrar == True
    ).all()
    kits = Kit.query.filter(
        Kit.name.ilike(f'%{termo}%'),
        Kit.is_admin_kit == True,
        Kit.ativo == True
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
 
    # ── DADOS DO CLIENTE ──
    linhas.append('👤 *Dados do Cliente:*')
    linhas.append(f'  Nome: {current_user.name or current_user.email}')
    linhas.append(f'  📧 Email: {current_user.email}')
    linhas.append(f'  📍 CEP: {current_user.cep}')
    linhas.append(f'  📱 Telefone: {current_user.phone}')
    linhas.append('')
 
    # ── ITENS DO PEDIDO ──
    linhas.append('🛒 *Itens do Pedido:*')
    total = 0
    for item in itens:
        subtotal = item.subtotal
        total   += subtotal
        linhas.append(f'• *{item.nome}*')
        linhas.append(f'  Qtd: {item.quantidade} x R$ {item.preco_unit:.2f} = R$ {subtotal:.2f}')
 
    linhas.append(f'\n💰 *Total: R$ {total:.2f}*')
 
    import urllib.parse
    msg_encoded  = urllib.parse.quote('\n'.join(linhas))
    whatsapp_url = f'https://wa.me/{WHATSAPP_NUMBER}?text={msg_encoded}'
 
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
    return render_template('carrossel/carrossel_form.html')


@app.route('/carrossel/listar')
@login_required
@admin_required
def carrossel_listar():
    itens = CarrosselItem.query.order_by(CarrosselItem.ordem).all()
    return render_template('carrossel/listar_carrossel.html', itens=itens)


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


@app.route('/carrossel/<int:id>/editar', methods=['GET', 'POST'])
@login_required
@admin_required
def carrossel_editar(id):
    item = CarrosselItem.query.get_or_404(id)
    if request.method == 'POST':
        item.titulo    = request.form.get('titulo', '').strip() or None
        item.subtitulo = request.form.get('subtitulo', '').strip() or None
        item.ordem     = request.form.get('ordem', 0, type=int)

        arquivo = request.files.get('imagem')
        if arquivo and arquivo.filename and allowed_file(arquivo.filename):
            caminho_antigo = os.path.join(UPLOAD_FOLDER_CARROSSEL, item.imagem)
            if os.path.exists(caminho_antigo):
                os.remove(caminho_antigo)
            ext      = arquivo.filename.rsplit('.', 1)[1].lower()
            filename = f"{int(time.time())}_{secure_filename(arquivo.filename)}"
            arquivo.save(os.path.join(UPLOAD_FOLDER_CARROSSEL, filename))
            item.imagem = filename

        db.session.commit()
        flash('Carrossel atualizado!', 'success')
        return redirect(url_for('carrossel_listar'))

    return render_template('carrossel/editar_carrossel.html', item=item)


# ─────────────────────────────────────
# DESIGN / PERSONALIZAÇÃO
# ─────────────────────────────────────

@app.route('/dynamic-styles.css')
def dynamic_styles():
    config = SiteConfig.query.first()
    css = render_template('dynamic_styles.jinja2', config=config)
    return css, 200, {'Content-Type': 'text/css; charset=utf-8', 'Cache-Control': 'no-cache'}

@app.route('/admin/design', methods=['GET', 'POST'])
@login_required
@admin_required
def admin_design():
    config = SiteConfig.query.first()
    if not config:
        config = SiteConfig()
        db.session.add(config)
        db.session.commit()

    if request.method == 'POST':
        action = request.form.get('action', 'save')

        if action == 'reset':
            db.session.delete(config)
            db.session.commit()
            config = SiteConfig()
            db.session.add(config)
            db.session.commit()
            flash('Design resetado para o padrão!', 'success')
            return redirect(url_for('admin_design'))

        config.color_primary    = request.form.get('color_primary',    '#5B6D3D')
        config.color_secondary  = request.form.get('color_secondary',  '#D67155')
        config.color_accent     = request.form.get('color_accent',     '#F3B651')
        config.color_dark       = request.form.get('color_dark',       '#932E50')
        config.color_bg         = request.form.get('color_bg',         '#FAF9F6')
        config.color_text       = request.form.get('color_text',       '#2B2B2B')
        config.color_text_light = request.form.get('color_text_light', '#6B6B6B')
        config.font_title       = request.form.get('font_title',       'Playfair Display')
        config.font_body        = request.form.get('font_body',        'Nunito')
        config.font_size        = request.form.get('font_size',        '16')
        config.title_weight     = request.form.get('title_weight',     '700')
        config.body_weight      = request.form.get('body_weight',      '400')
        config.layout_mode      = request.form.get('layout_mode',      'spacious')
        config.layout_width     = request.form.get('layout_width',     'centered')
        config.btn_radius       = request.form.get('btn_radius',       '12px')
        config.card_shadow      = request.form.get('card_shadow',      'medium')
        config.navbar_fixed     = request.form.get('navbar_fixed') == 'on'
        config.anim_enabled     = request.form.get('anim_enabled') == 'on'
        config.anim_intensity   = request.form.get('anim_intensity',   'medium')
        config.site_name        = request.form.get('site_name',        'Doces da Fhê')
        config.logo_height      = int(request.form.get('logo_height', 100) or 100)
        config.logo_fit         = request.form.get('logo_fit', 'contain')
        config.carousel_height  = int(request.form.get('carousel_height', 340) or 340)
        config.card_img_height  = int(request.form.get('card_img_height', 200) or 200)
        config.card_radius      = request.form.get('card_radius', '16px')
        config.flash_success    = request.form.get('flash_success', '#d4edda')
        config.flash_error      = request.form.get('flash_error',  '#f8d7da')
        config.flash_info       = request.form.get('flash_info',   '#d1ecf1')

        logo_file = request.files.get('logo_file')
        if logo_file and logo_file.filename != '':
            if not allowed_file(logo_file.filename):
                flash('Formato de imagem não suportado. Use PNG, JPG, JPEG ou WebP.', 'error')
                return redirect(url_for('admin_design'))
            ext = logo_file.filename.rsplit('.', 1)[-1].lower()
            logo_name = f"logo_{int(time.time())}.{ext}"
            logo_dir  = os.path.join(app.root_path, 'static', 'uploads', 'logo')
            os.makedirs(logo_dir, exist_ok=True)
            logo_path = os.path.join(logo_dir, logo_name)
            logo_file.save(logo_path)
            # apaga logo anterior se não for o padrão
            if config.logo_url and config.logo_url != f'uploads/logo/{logo_name}':
                old_path = os.path.join(app.root_path, 'static', config.logo_url)
                if os.path.exists(old_path) and 'logo.png' not in old_path:
                    os.remove(old_path)
            config.logo_url = f'uploads/logo/{logo_name}'

        db.session.commit()
        flash('Design salvo com sucesso!', 'success')
        return redirect(url_for('admin_design'))

    return render_template('admin/design.html', config=config)


# ─────────────────────────────────────
# RUN
# ─────────────────────────────────────
if __name__ == '__main__':
    app.run(debug=True)