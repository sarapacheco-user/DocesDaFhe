from functools import wraps
from flask import Flask, render_template, request, redirect, url_for, flash, jsonify, Response
from flask_login import LoginManager, login_user, login_required, logout_user, current_user
from flask_mail import Mail, Message
from models import db, User, Product, Kit, KitProduct, EventoEspecial, ProdutoEspecial, CarrinhoItem, CarrosselItem, SiteConfig, Favorito, MovimentacaoEstoque, Pedido, PedidoItem, Brinde, Avaliacao, ConfigCorporativo, PedidoCorporativo, BlogPost, AgendaEvento
import bcrypt
import re
import requests
import secrets
from werkzeug.utils import secure_filename
from datetime import datetime, timedelta
from sqlalchemy import func, or_
import time
import os
import urllib.parse
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
UPLOAD_FOLDER_CORP      = os.path.join('static', 'uploads', 'corporativo')
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'webp', 'gif'}

for folder in [UPLOAD_FOLDER_CARROSSEL, UPLOAD_FOLDER_PRODUTOS,
               UPLOAD_FOLDER_KITS, UPLOAD_FOLDER_ESPECIAIS, UPLOAD_FOLDER_LOGO,
               UPLOAD_FOLDER_CORP]:
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
from datetime import datetime as _dt
app.jinja_env.globals['now'] = _dt.utcnow

from blog_routes import blog_bp
app.register_blueprint(blog_bp)


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
    # Migrações seguras
    with db.engine.connect() as conn:
        for tbl, col, typedef in [
            ('eventos_especiais', 'data_inicio',    'DATETIME'),
            ('eventos_especiais', 'data_fim',       'DATETIME'),
            ('site_config',       'auth_bg_color1', 'VARCHAR(20)'),
            ('site_config',       'auth_bg_color2', 'VARCHAR(20)'),
        ]:
            try:
                conn.execute(db.text(f'ALTER TABLE {tbl} ADD COLUMN {col} {typedef}'))
                conn.commit()
            except Exception:
                pass


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
# FAVORITOS
# ─────────────────────────────────────

def _fav_sets(user_id):
    favs = Favorito.query.filter_by(user_id=user_id).all()
    return (
        {f.produto_id  for f in favs if f.produto_id},
        {f.kit_id      for f in favs if f.kit_id},
        {f.especial_id for f in favs if f.especial_id},
    )


@app.route('/favoritar', methods=['POST'])
def favoritar():
    if not current_user.is_authenticated:
        return jsonify(redirect=url_for('login')), 401
    data = request.get_json()
    tipo = data.get('tipo')
    item_id = int(data.get('id', 0))
    fav = None
    if tipo == 'produto':
        fav = Favorito.query.filter_by(user_id=current_user.id, produto_id=item_id).first()
    elif tipo == 'kit':
        fav = Favorito.query.filter_by(user_id=current_user.id, kit_id=item_id).first()
    elif tipo == 'especial':
        fav = Favorito.query.filter_by(user_id=current_user.id, especial_id=item_id).first()
    if fav:
        db.session.delete(fav)
        db.session.commit()
        return jsonify(favorito=False)
    kwargs = {'user_id': current_user.id, f'{tipo}_id': item_id}
    db.session.add(Favorito(**kwargs))
    db.session.commit()
    return jsonify(favorito=True)


@app.route('/favoritos')
@login_required
def favoritos():
    fav_p, fav_k, fav_e = _fav_sets(current_user.id)
    produtos  = Product.query.filter(Product.id.in_(fav_p)).all()  if fav_p else []
    kits      = Kit.query.filter(Kit.id.in_(fav_k)).all()          if fav_k else []
    especiais = ProdutoEspecial.query.filter(ProdutoEspecial.id.in_(fav_e)).all() if fav_e else []
    return render_template('pedidos/favoritos.html',
                           produtos=produtos, kits=kits, especiais=especiais,
                           fav_p=fav_p, fav_k=fav_k, fav_e=fav_e)


# ─────────────────────────────────────
# DASHBOARD
# ─────────────────────────────────────

@app.route('/dashboard')
def dashboard():
    produtos      = Product.query.filter(Product.ativo == True, Product.category != 'corporativos').all()
    produtos_corp = Product.query.filter_by(ativo=True, category='corporativos').all()
    eventos   = [e for e in EventoEspecial.query.filter_by(ativo=True).all() if e.no_periodo]
    carrossel = CarrosselItem.query.filter_by(ativo=True).order_by(CarrosselItem.ordem).all()
    kits      = Kit.query.filter_by(is_admin_kit=True, ativo=True).all()
    fav_p, fav_k, fav_e = _fav_sets(current_user.id) if current_user.is_authenticated else (set(), set(), set())

    # médias de avaliação por produto e kit
    rows_p = db.session.query(Avaliacao.produto_id, func.avg(Avaliacao.estrelas), func.count(Avaliacao.id))\
               .filter(Avaliacao.produto_id.isnot(None)).group_by(Avaliacao.produto_id).all()
    rows_k = db.session.query(Avaliacao.kit_id, func.avg(Avaliacao.estrelas), func.count(Avaliacao.id))\
               .filter(Avaliacao.kit_id.isnot(None)).group_by(Avaliacao.kit_id).all()
    medias_p = {r[0]: (round(r[1], 1), r[2]) for r in rows_p}
    medias_k = {r[0]: (round(r[1], 1), r[2]) for r in rows_k}

    posts_recentes = BlogPost.query.filter_by(status='publicado')\
                        .order_by(BlogPost.created_at.desc()).limit(3).all()

    from datetime import datetime as dt
    agenda_proximos = AgendaEvento.query\
                        .filter(AgendaEvento.data_inicio >= dt.now())\
                        .order_by(AgendaEvento.data_inicio).limit(5).all()

    return render_template('dashboard.html',
                           user=current_user,
                           produtos=produtos,
                           produtos_corp=produtos_corp,
                           eventos=eventos,
                           carrossel=carrossel,
                           kits=kits,
                           fav_p=fav_p, fav_k=fav_k, fav_e=fav_e,
                           medias_p=medias_p, medias_k=medias_k,
                           posts_recentes=posts_recentes,
                           agenda_proximos=agenda_proximos)


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
        qtd_min = max(1, int(request.form.get('quantidade_minima', 1) or 1))
        qtd_max_raw = request.form.get('quantidade_maxima', '').strip()
        qtd_max = int(qtd_max_raw) if qtd_max_raw else None
        image_url = salvar_imagem_produto(arquivo)
        product = Product(name=name, description=description,
                          price=price, category=category, image_url=image_url,
                          quantidade_minima=qtd_min, quantidade_maxima=qtd_max)
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
        product.quantidade_minima = max(1, int(request.form.get('quantidade_minima', 1) or 1))
        qtd_max_raw = request.form.get('quantidade_maxima', '').strip()
        product.quantidade_maxima = int(qtd_max_raw) if qtd_max_raw else None
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
    if nome == 'corporativos':
        return redirect(url_for('corporativo'))
    produtos = Product.query.filter_by(category=nome, ativo=True).all()
    fav_p, fav_k, fav_e = _fav_sets(current_user.id) if current_user.is_authenticated else (set(), set(), set())
    return render_template('product/categoria.html', produtos=produtos, categoria=nome,
                           fav_p=fav_p, fav_k=fav_k, fav_e=fav_e)


@app.route('/kits_loja')
def kits_loja():
    kits = Kit.query.filter_by(is_admin_kit=True, ativo=True).all()
    produtos = Product.query.filter_by(ativo=True).order_by(Product.category, Product.name).all()
    fav_p, fav_k, fav_e = _fav_sets(current_user.id) if current_user.is_authenticated else (set(), set(), set())
    return render_template('kits/kits_loja.html', kits=kits, produtos=produtos,
                           fav_p=fav_p, fav_k=fav_k, fav_e=fav_e)


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
    fav_p, _, _ = _fav_sets(current_user.id) if current_user.is_authenticated else (set(), set(), set())
    avaliacoes = Avaliacao.query.filter_by(produto_id=id).order_by(Avaliacao.created_at.desc()).all()
    media = round(sum(a.estrelas for a in avaliacoes) / len(avaliacoes), 1) if avaliacoes else 0
    ja_avaliou = any(a.user_id == current_user.id for a in avaliacoes) if current_user.is_authenticated else False
    return render_template('product/produto_detalhe.html',
                           produto=produto,
                           relacionados=relacionados,
                           is_kit=False,
                           fav_tipo='produto', fav_id=produto.id,
                           is_favorito=(produto.id in fav_p),
                           avaliacoes=avaliacoes, media=media, ja_avaliou=ja_avaliou)


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

    _, fav_k, _ = _fav_sets(current_user.id) if current_user.is_authenticated else (set(), set(), set())
    avaliacoes = Avaliacao.query.filter_by(kit_id=kit_id).order_by(Avaliacao.created_at.desc()).all()
    media = round(sum(a.estrelas for a in avaliacoes) / len(avaliacoes), 1) if avaliacoes else 0
    ja_avaliou = any(a.user_id == current_user.id for a in avaliacoes) if current_user.is_authenticated else False
    return render_template('product/produto_detalhe.html',
                           produto=produto,
                           relacionados=relacionados,
                           is_kit=True, kit=kit,
                           fav_tipo='kit', fav_id=kit.id,
                           is_favorito=(kit.id in fav_k),
                           avaliacoes=avaliacoes, media=media, ja_avaliou=ja_avaliou)


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
    _, _, fav_e = _fav_sets(current_user.id) if current_user.is_authenticated else (set(), set(), set())
    avaliacoes = Avaliacao.query.filter_by(especial_id=id).order_by(Avaliacao.created_at.desc()).all()
    media = round(sum(a.estrelas for a in avaliacoes) / len(avaliacoes), 1) if avaliacoes else 0
    ja_avaliou = any(a.user_id == current_user.id for a in avaliacoes) if current_user.is_authenticated else False
    return render_template('product/produto_detalhe.html',
                           produto=produto,
                           relacionados=relacionados,
                           is_kit=False,
                           fav_tipo='especial', fav_id=produto.id,
                           is_favorito=(produto.id in fav_e),
                           avaliacoes=avaliacoes, media=media, ja_avaliou=ja_avaliou)


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
    fav_p, fav_k, fav_e = _fav_sets(current_user.id) if current_user.is_authenticated else (set(), set(), set())
    return render_template('pedidos/busca.html', termo=termo,
                           produtos=produtos, especiais=especiais, kits=kits,
                           fav_p=fav_p, fav_k=fav_k, fav_e=fav_e)


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
        ini_d = request.form.get('data_inicio_date', '').strip()
        ini_t = request.form.get('data_inicio_time', '').strip() or '00:00'
        fim_d = request.form.get('data_fim_date', '').strip()
        fim_t = request.form.get('data_fim_time', '').strip() or '00:00'
        data_inicio = datetime.strptime(f'{ini_d}T{ini_t}', '%Y-%m-%dT%H:%M') if ini_d else None
        data_fim    = datetime.strptime(f'{fim_d}T{fim_t}', '%Y-%m-%dT%H:%M') if fim_d else None
        evento = EventoEspecial(nome=nome, descricao=descricao,
                                data_inicio=data_inicio, data_fim=data_fim)
        db.session.add(evento)
        db.session.commit()
        flash(f'Evento "{nome}" criado com sucesso!', 'success')
        return redirect(url_for('listar_eventos'))
    return render_template('special/criar_evento.html')


@app.route('/special/eventos/<int:id>/editar', methods=['GET', 'POST'])
@login_required
@admin_required
def editar_evento(id):
    evento = EventoEspecial.query.get_or_404(id)
    if request.method == 'POST':
        nome      = request.form.get('nome', '').strip()
        descricao = request.form.get('descricao', '').strip()
        if not nome:
            flash('O nome do evento é obrigatório.', 'error')
            return redirect(url_for('editar_evento', id=id))
        duplicado = EventoEspecial.query.filter(
            EventoEspecial.nome == nome, EventoEspecial.id != id
        ).first()
        if duplicado:
            flash('Já existe outro evento com esse nome.', 'error')
            return redirect(url_for('editar_evento', id=id))
        ini_d = request.form.get('data_inicio_date', '').strip()
        ini_t = request.form.get('data_inicio_time', '').strip() or '00:00'
        fim_d = request.form.get('data_fim_date', '').strip()
        fim_t = request.form.get('data_fim_time', '').strip() or '00:00'
        evento.nome        = nome
        evento.descricao   = descricao
        evento.ativo       = bool(request.form.get('ativo'))
        evento.data_inicio = datetime.strptime(f'{ini_d}T{ini_t}', '%Y-%m-%dT%H:%M') if ini_d else None
        evento.data_fim    = datetime.strptime(f'{fim_d}T{fim_t}', '%Y-%m-%dT%H:%M') if fim_d else None
        db.session.commit()
        flash(f'Evento "{nome}" atualizado!', 'success')
        return redirect(url_for('listar_eventos'))
    return render_template('special/editar_evento.html', evento=evento)


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

        qtd_min = max(1, int(request.form.get('quantidade_minima', 1) or 1))
        qtd_max_raw = request.form.get('quantidade_maxima', '').strip()
        qtd_max = int(qtd_max_raw) if qtd_max_raw else None
        produto = ProdutoEspecial(
            evento_id=evento_id,
            name=name,
            description=description,
            price=price,
            category=category,
            image_url=image_url,
            mostrar=mostrar,
            quantidade_minima=qtd_min,
            quantidade_maxima=qtd_max
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
        produto.name              = request.form.get('name', '').strip()
        produto.description       = request.form.get('description', '').strip()
        produto.category          = request.form.get('category', 'geral')
        produto.mostrar           = 'mostrar' in request.form
        produto.quantidade_minima = max(1, int(request.form.get('quantidade_minima', 1) or 1))
        qtd_max_raw = request.form.get('quantidade_maxima', '').strip()
        produto.quantidade_maxima = int(qtd_max_raw) if qtd_max_raw else None
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
    brinde = (Brinde.query
                    .filter_by(ativo=True)
                    .filter(Brinde.valor_minimo <= total)
                    .order_by(Brinde.valor_minimo.desc())
                    .first())
    return render_template('pedidos/carrinho.html', itens=itens,
                           total=total, quantidade_total=quantidade_total,
                           brinde=brinde)


@app.route('/carrinho/adicionar', methods=['POST'])
@login_required
def adicionar_carrinho():
    produto_id  = request.form.get('produto_id', type=int)
    kit_id      = request.form.get('kit_id', type=int)
    especial_id = request.form.get('especial_id', type=int)
    quantidade  = request.form.get('quantidade', 1, type=int)
    proxima_url = request.form.get('next', url_for('carrinho'))

    # verifica quantidade mínima do produto
    qtd_min = 1
    if produto_id:
        p = Product.query.get(produto_id)
        if p:
            qtd_min = p.quantidade_minima
    elif especial_id:
        pe = ProdutoEspecial.query.get(especial_id)
        if pe:
            qtd_min = pe.quantidade_minima

    qtd_max = None
    if produto_id:
        p = Product.query.get(produto_id)
        if p:
            qtd_max = p.quantidade_maxima
    elif especial_id:
        pe = ProdutoEspecial.query.get(especial_id)
        if pe:
            qtd_max = pe.quantidade_maxima

    if quantidade < qtd_min:
        flash(f'A quantidade mínima para este produto é {qtd_min} unidade(s).', 'error')
        return redirect(proxima_url)
    if qtd_max and quantidade > qtd_max:
        flash(f'A quantidade máxima para este produto é {qtd_max} unidade(s).', 'error')
        return redirect(proxima_url)

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
    qtd_min    = item.quantidade_minima
    qtd_max    = item.quantidade_maxima
    if quantidade < 1:
        db.session.delete(item)
    elif quantidade < qtd_min:
        item.quantidade = qtd_min
        db.session.commit()
        flash(f'A quantidade mínima de "{item.nome}" é {qtd_min} unidade(s).', 'warning')
        return redirect(url_for('carrinho'))
    elif qtd_max and quantidade > qtd_max:
        item.quantidade = qtd_max
        db.session.commit()
        flash(f'A quantidade máxima de "{item.nome}" é {qtd_max} unidade(s).', 'warning')
        return redirect(url_for('carrinho'))
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

    tipo      = request.args.get('tipo', 'buscar')
    rua       = request.args.get('rua', '').strip()
    bairro    = request.args.get('bairro', '').strip()
    cidade    = request.args.get('cidade', '').strip()
    cep       = request.args.get('cep', '').strip()
    pagamento = request.args.get('pagamento', '').strip()
    endereco  = f"{rua} | {bairro} | {cidade} | CEP: {cep}" if rua else request.args.get('endereco', '').strip()

    linhas = ['*Ola! Quero fazer um pedido:*\n']

    # ── TIPO DE ENTREGA ──
    if tipo == 'entrega':
        linhas.append('*Tipo: Entrega*')
        if rua:
            linhas.append(f'Endereco de entrega: {rua}')
            if bairro: linhas.append(f'Bairro: {bairro}')
            if cidade: linhas.append(f'Cidade: {cidade}')
            if cep:    linhas.append(f'CEP: {cep}')
        elif endereco:
            linhas.append(f'Endereco: {endereco}')
    else:
        linhas.append('*Tipo: Buscar (motoboy/Uber)*')
    if pagamento:
        linhas.append(f'*Forma de pagamento: {pagamento}*')
    linhas.append('')

    # ── DADOS DO CLIENTE ──
    linhas.append('*Dados do Cliente:*')
    linhas.append(f'  Nome: {current_user.name or current_user.email}')
    linhas.append(f'  Email: {current_user.email}')
    linhas.append(f'  Telefone: {current_user.phone}')
    linhas.append('')

    # ── ITENS DO PEDIDO ──
    linhas.append('*Itens do Pedido:*')
    total = 0
    for item in itens:
        subtotal = item.subtotal
        total   += subtotal
        linhas.append(f'- *{item.nome}*')
        linhas.append(f'  Qtd: {item.quantidade} x R$ {item.preco_unit:.2f} = R$ {subtotal:.2f}')
        if item.notas_corp:
            detalhes = [l.strip() for l in item.notas_corp.split('\n')
                        if l.strip() and not l.strip().startswith('[')]
            if detalhes:
                linhas.append('  *Detalhes corporativos:*')
                for d in detalhes:
                    linhas.append(f'  • {d}')

    linhas.append(f'\n*Total: R$ {total:.2f}*')

    # ── LEMBRANCINHA ──
    brinde = (Brinde.query
                    .filter_by(ativo=True)
                    .filter(Brinde.valor_minimo <= total)
                    .order_by(Brinde.valor_minimo.desc())
                    .first())
    if brinde:
        linhas.append('')
        linhas.append(f'*Brinde:* {brinde.quantidade_brinde}x {brinde.produto_nome} (brinde em pedidos acima de R$ {float(brinde.valor_minimo):.2f})')

    # ── SALVAR PEDIDO ──
    pedido = Pedido(
        user_id  = current_user.id,
        tipo     = tipo,
        endereco = endereco if tipo == 'entrega' else None,
        total    = total,
        status   = 'pendente',
    )
    db.session.add(pedido)
    db.session.flush()  # gera pedido.id antes do commit

    for item in itens:
        db.session.add(PedidoItem(
            pedido_id  = pedido.id,
            nome       = item.nome,
            quantidade = item.quantidade,
            preco_unit = item.preco_unit,
            notas_corp = item.notas_corp,
        ))

    # ── BAIXA AUTOMÁTICA DE ESTOQUE ──
    for item in itens:
        qtd = item.quantidade
        obj = None
        kwargs = {'tipo': 'saida', 'quantidade': qtd,
                  'motivo': f'Pedido #{pedido.id} via loja'}

        if item.produto_id and item.produto:
            obj = item.produto
            kwargs['produto_id'] = item.produto_id
        elif item.kit_id and item.kit:
            obj = item.kit
            kwargs['kit_id'] = item.kit_id
        elif item.especial_id and item.especial:
            obj = item.especial
            kwargs['especial_id'] = item.especial_id

        if obj is not None:
            kwargs['estoque_anterior'] = obj.estoque
            obj.estoque = max(0, obj.estoque - qtd)
            kwargs['estoque_novo'] = obj.estoque
            db.session.add(MovimentacaoEstoque(**kwargs))

    msg_encoded  = urllib.parse.quote('\n'.join(linhas))
    whatsapp_url = f'https://wa.me/{WHATSAPP_NUMBER}?text={msg_encoded}'

    CarrinhoItem.query.filter_by(user_id=current_user.id).delete()
    db.session.commit()
    return redirect(whatsapp_url)


# ══════════════════════════════════════════════
#  PEDIDOS — CLIENTE
# ══════════════════════════════════════════════

@app.route('/meus-pedidos')
@login_required
def meus_pedidos():
    pedidos = Pedido.query.filter_by(user_id=current_user.id, oculto_cliente=False)\
                          .order_by(Pedido.created_at.desc()).all()
    pedidos_corp = PedidoCorporativo.query.filter_by(user_id=current_user.id, oculto_cliente=False)\
                                          .order_by(PedidoCorporativo.created_at.desc()).all()
    return render_template('pedidos/meus_pedidos.html', pedidos=pedidos,
                           pedidos_corp=pedidos_corp)


@app.route('/pedidos/<int:id>/cancelar', methods=['POST'])
@login_required
def cancelar_pedido(id):
    pedido = Pedido.query.get_or_404(id)
    if pedido.user_id != current_user.id:
        flash('Pedido não encontrado.', 'error')
        return redirect(url_for('meus_pedidos'))
    if pedido.status == 'pendente':
        pedido.status = 'cancelado'
        db.session.commit()
        flash('Pedido cancelado com sucesso.', 'success')
    else:
        flash('Não é possível cancelar este pedido.', 'error')
    return redirect(url_for('meus_pedidos'))


@app.route('/pedidos/apagar', methods=['POST'])
@login_required
def apagar_pedidos():
    ids      = request.form.getlist('ids')
    corp_ids = request.form.getlist('corp_ids')
    if not ids and not corp_ids:
        flash('Nenhum pedido selecionado.', 'error')
        return redirect(url_for('meus_pedidos'))
    apagados = 0
    for pid in ids:
        try:
            pedido = Pedido.query.get(int(pid))
        except (ValueError, TypeError):
            continue
        if not pedido or pedido.user_id != current_user.id:
            continue
        if pedido.status not in ('cancelado', 'entregue'):
            continue
        pedido.oculto_cliente = True
        apagados += 1
    for pid in corp_ids:
        try:
            pedido = PedidoCorporativo.query.get(int(pid))
        except (ValueError, TypeError):
            continue
        if not pedido or pedido.user_id != current_user.id:
            continue
        if pedido.status not in ('concluido', 'cancelado'):
            continue
        pedido.oculto_cliente = True
        apagados += 1
    db.session.commit()
    if apagados:
        flash(f'{apagados} pedido(s) removido(s) do seu histórico.', 'success')
    else:
        flash('Nenhum pedido pôde ser removido.', 'error')
    return redirect(url_for('meus_pedidos'))


# ══════════════════════════════════════════════
#  PEDIDOS — ADMIN
# ══════════════════════════════════════════════

@app.route('/admin/pedidos')
@login_required
@admin_required
def admin_pedidos():
    corp_ids = {r[0] for r in db.session.query(PedidoItem.pedido_id)
                                        .filter(PedidoItem.notas_corp.isnot(None))
                                        .distinct().all()}

    status_filter = request.args.get('status', '')
    q = Pedido.query.filter(~Pedido.id.in_(corp_ids)).order_by(Pedido.created_at.desc())
    if status_filter:
        q = q.filter_by(status=status_filter)
    pedidos = q.all()

    base = Pedido.query.filter(~Pedido.id.in_(corp_ids))
    stats = dict(
        total      = base.count(),
        pendente   = base.filter_by(status='pendente').count(),
        confirmado = base.filter_by(status='confirmado').count(),
        entregue   = base.filter_by(status='entregue').count(),
        cancelado  = base.filter_by(status='cancelado').count(),
        faturado   = float(db.session.query(db.func.sum(Pedido.total))
                          .filter(~Pedido.id.in_(corp_ids))
                          .filter(Pedido.status.in_(['confirmado', 'entregue']))
                          .scalar() or 0),
    )
    brindes = Brinde.query.filter_by(ativo=True).order_by(Brinde.valor_minimo).all()
    return render_template('admin/pedidos.html',
                           pedidos=pedidos, status_filter=status_filter, stats=stats,
                           brindes=brindes)


@app.route('/admin/pedidos/<int:id>/status', methods=['POST'])
@login_required
@admin_required
def admin_pedido_status(id):
    pedido = Pedido.query.get_or_404(id)
    novo   = request.form.get('status')
    if novo in ('pendente', 'confirmado', 'entregue', 'cancelado'):
        pedido.status = novo
        db.session.commit()
        flash(f'Pedido #{id} atualizado para "{novo}".', 'success')
    return redirect(url_for('admin_pedidos', status=request.args.get('status', '')))


# ══════════════════════════════════════════════
#  ESTOQUE
# ══════════════════════════════════════════════

@app.route('/admin/estoque')
@login_required
@admin_required
def estoque():
    produtos  = Product.query.filter_by(ativo=True).order_by(Product.name).all()
    kits      = Kit.query.filter_by(ativo=True, is_admin_kit=True).order_by(Kit.name).all()
    especiais = ProdutoEspecial.query.filter_by(mostrar=True).order_by(ProdutoEspecial.name).all()

    def _item(obj, tipo, nome, cat, preco):
        return {'id': obj.id, 'tipo': tipo, 'nome': nome,
                'categoria': cat or '—', 'preco': float(preco),
                'estoque': obj.estoque, 'estoque_minimo': obj.estoque_minimo,
                'status': obj.status_estoque}

    itens = (
        [_item(p, 'produto',  p.name, p.category,        p.price)       for p in produtos] +
        [_item(k, 'kit',      k.name, 'Kit',              k.total_price) for k in kits] +
        [_item(e, 'especial', e.name, e.category,         e.price)       for e in especiais]
    )
    itens.sort(key=lambda x: x['nome'].lower())

    categorias = sorted({i['categoria'] for i in itens if i['categoria'] != '—'})
    total_valor   = sum(i['preco'] * i['estoque'] for i in itens)
    sem_estoque   = sum(1 for i in itens if i['status'] == 'zerado')
    estoque_baixo = sum(1 for i in itens if i['status'] == 'baixo')

    return render_template('admin/estoque.html',
        itens=itens, categorias=categorias,
        total_valor=total_valor, sem_estoque=sem_estoque,
        estoque_baixo=estoque_baixo)


def _get_item_estoque(tipo, item_id):
    if tipo == 'produto':  return Product.query.get(item_id)
    if tipo == 'kit':      return Kit.query.get(item_id)
    if tipo == 'especial': return ProdutoEspecial.query.get(item_id)
    return None


@app.route('/admin/estoque/movimentar', methods=['POST'])
@login_required
@admin_required
def movimentar_estoque():
    data      = request.get_json()
    tipo_item = data.get('tipo_item', 'produto')
    item_id   = int(data.get('item_id', 0))
    tipo      = data.get('tipo', 'entrada')
    quantidade= int(data.get('quantidade', 0))
    motivo    = data.get('motivo', '').strip()

    if quantidade <= 0:
        return jsonify(ok=False, erro='Quantidade inválida'), 400

    item = _get_item_estoque(tipo_item, item_id)
    if not item:
        return jsonify(ok=False, erro='Item não encontrado'), 404

    anterior = item.estoque
    if tipo == 'saida':
        if quantidade > item.estoque:
            return jsonify(ok=False, erro='Estoque insuficiente para saída'), 400
        item.estoque -= quantidade
    else:
        item.estoque += quantidade

    kwargs = {'tipo': tipo, 'quantidade': quantidade, 'motivo': motivo,
              'estoque_anterior': anterior, 'estoque_novo': item.estoque}
    if tipo_item == 'produto':  kwargs['produto_id']  = item_id
    elif tipo_item == 'kit':    kwargs['kit_id']      = item_id
    elif tipo_item == 'especial': kwargs['especial_id'] = item_id

    db.session.add(MovimentacaoEstoque(**kwargs))
    db.session.commit()
    return jsonify(ok=True, estoque_novo=item.estoque, status=item.status_estoque)


@app.route('/admin/estoque/historico/<tipo_item>/<int:item_id>')
@login_required
@admin_required
def historico_estoque(tipo_item, item_id):
    filtro = {f'{tipo_item}_id': item_id}
    movs = (MovimentacaoEstoque.query
            .filter_by(**filtro)
            .order_by(MovimentacaoEstoque.created_at.desc())
            .limit(50).all())
    return jsonify(historico=[{
        'data': m.created_at.strftime('%d/%m/%Y %H:%M'),
        'tipo': m.tipo, 'quantidade': m.quantidade,
        'motivo': m.motivo or '—',
        'anterior': m.estoque_anterior, 'novo': m.estoque_novo,
    } for m in movs])


@app.route('/admin/estoque/relatorio')
@login_required
@admin_required
def relatorio_estoque():
    from datetime import datetime as _dt2, timedelta

    # parâmetros de filtro
    data_ini_str = request.args.get('data_ini', '')
    data_fim_str = request.args.get('data_fim', '')
    tipo_filtro  = request.args.get('tipo', '')   # produto / kit / especial / ''

    hoje = _dt2.utcnow().date()
    # defaults: mês atual
    try:
        data_ini = _dt2.strptime(data_ini_str, '%Y-%m-%d').date() if data_ini_str else hoje.replace(day=1)
        data_fim = _dt2.strptime(data_fim_str, '%Y-%m-%d').date() if data_fim_str else hoje
    except ValueError:
        data_ini = hoje.replace(day=1)
        data_fim = hoje

    dt_ini = _dt2(data_ini.year, data_ini.month, data_ini.day, 0, 0, 0)
    dt_fim = _dt2(data_fim.year, data_fim.month, data_fim.day, 23, 59, 59)

    q = MovimentacaoEstoque.query.filter(
        MovimentacaoEstoque.created_at >= dt_ini,
        MovimentacaoEstoque.created_at <= dt_fim,
    )
    if tipo_filtro == 'produto':
        q = q.filter(MovimentacaoEstoque.produto_id.isnot(None))
    elif tipo_filtro == 'kit':
        q = q.filter(MovimentacaoEstoque.kit_id.isnot(None))
    elif tipo_filtro == 'especial':
        q = q.filter(MovimentacaoEstoque.especial_id.isnot(None))

    movs = q.order_by(MovimentacaoEstoque.created_at.desc()).all()

    # agrupar por item
    from collections import defaultdict
    grupos = defaultdict(lambda: {'nome': '', 'tipo': '', 'entradas': 0, 'saidas': 0, 'movs': []})

    for m in movs:
        if m.produto_id:
            key = ('produto', m.produto_id)
            grupos[key]['nome'] = m.produto.name if m.produto else f'Produto #{m.produto_id}'
            grupos[key]['tipo'] = 'produto'
        elif m.kit_id:
            key = ('kit', m.kit_id)
            grupos[key]['nome'] = m.kit.name if m.kit else f'Kit #{m.kit_id}'
            grupos[key]['tipo'] = 'kit'
        elif m.especial_id:
            key = ('especial', m.especial_id)
            grupos[key]['nome'] = m.especial.name if m.especial else f'Especial #{m.especial_id}'
            grupos[key]['tipo'] = 'especial'
        else:
            continue

        if m.tipo == 'entrada':
            grupos[key]['entradas'] += m.quantidade
        else:
            grupos[key]['saidas'] += m.quantidade
        grupos[key]['movs'].append(m)

    itens_rel = sorted([
        {'nome': v['nome'], 'tipo': v['tipo'],
         'entradas': v['entradas'], 'saidas': v['saidas'],
         'saldo': v['entradas'] - v['saidas'], 'total_movs': len(v['movs'])}
        for v in grupos.values()
    ], key=lambda x: x['nome'])

    total_entradas = sum(i['entradas'] for i in itens_rel)
    total_saidas   = sum(i['saidas']   for i in itens_rel)

    # gráfico de pizza — saídas por motivo
    from collections import Counter
    motivo_counter = Counter()
    for m in movs:
        if m.tipo == 'saida':
            motivo_counter[m.motivo or 'Sem motivo'] += m.quantidade
    grafico_motivos   = list(motivo_counter.keys())
    grafico_quantidades = [motivo_counter[k] for k in grafico_motivos]

    # ── DADOS DE VENDAS (Pedidos) ──
    pedidos_periodo = Pedido.query.filter(
        Pedido.created_at >= dt_ini,
        Pedido.created_at <= dt_fim,
    ).order_by(Pedido.created_at.desc()).all()

    venda_stats = dict(
        total      = len(pedidos_periodo),
        pendente   = sum(1 for p in pedidos_periodo if p.status == 'pendente'),
        confirmado = sum(1 for p in pedidos_periodo if p.status == 'confirmado'),
        entregue   = sum(1 for p in pedidos_periodo if p.status == 'entregue'),
        cancelado  = sum(1 for p in pedidos_periodo if p.status == 'cancelado'),
        faturado   = float(sum(p.total for p in pedidos_periodo
                               if p.status in ('confirmado', 'entregue'))),
        itens_vendidos = sum(
            sum(it.quantidade for it in p.itens)
            for p in pedidos_periodo if p.status in ('confirmado', 'entregue')
        ),
    )

    # ── DADOS CORPORATIVOS ──
    corp_pedidos = PedidoCorporativo.query.filter(
        PedidoCorporativo.created_at >= dt_ini,
        PedidoCorporativo.created_at <= dt_fim,
    ).order_by(PedidoCorporativo.created_at.desc()).all()

    corp_stats = dict(
        total        = len(corp_pedidos),
        novo         = sum(1 for p in corp_pedidos if p.status == 'novo'),
        em_andamento = sum(1 for p in corp_pedidos if p.status == 'em_andamento'),
        concluido    = sum(1 for p in corp_pedidos if p.status == 'concluido'),
        cancelado    = sum(1 for p in corp_pedidos if p.status == 'cancelado'),
        personalizar = sum(1 for p in corp_pedidos if p.tipo == 'personalizar'),
        solicitar    = sum(1 for p in corp_pedidos if p.tipo == 'solicitar'),
    )

    # exportar CSV
    if request.args.get('export') == 'csv':
        import csv, io
        output = io.StringIO()
        w = csv.writer(output, delimiter=';')
        w.writerow(['--- ESTOQUE ---'])
        w.writerow(['Item', 'Tipo', 'Entradas', 'Saídas', 'Saldo', 'Movimentações'])
        for i in itens_rel:
            w.writerow([i['nome'], i['tipo'], i['entradas'], i['saidas'], i['saldo'], i['total_movs']])
        w.writerow([])
        w.writerow(['--- VENDAS ---'])
        w.writerow(['#', 'Data', 'Cliente', 'Tipo', 'Total (R$)', 'Status'])
        for p in pedidos_periodo:
            w.writerow([p.id, p.created_at.strftime('%d/%m/%Y %H:%M'),
                        p.user.name or p.user.email, p.tipo,
                        f'{float(p.total):.2f}', p.status])
        w.writerow([])
        w.writerow(['--- CORPORATIVOS ---'])
        w.writerow(['#', 'Data', 'Nome', 'Telefone', 'Tipo', 'Produto', 'Qtd', 'Status'])
        for p in corp_pedidos:
            w.writerow([p.id, p.created_at.strftime('%d/%m/%Y %H:%M'),
                        p.nome, p.telefone, p.tipo,
                        p.produto_nome or '', p.quantidade or '', p.status])
        return Response(
            '﻿' + output.getvalue(),
            mimetype='text/csv; charset=utf-8',
            headers={'Content-Disposition': f'attachment; filename=relatorio_{data_ini_str or "periodo"}.csv'}
        )

    return render_template('admin/relatorio.html',
        itens=itens_rel, movs=movs,
        total_entradas=total_entradas, total_saidas=total_saidas,
        grafico_motivos=grafico_motivos,
        grafico_quantidades=grafico_quantidades,
        pedidos_periodo=pedidos_periodo,
        venda_stats=venda_stats,
        corp_pedidos=corp_pedidos,
        corp_stats=corp_stats,
        data_ini=data_ini_str or data_ini.strftime('%Y-%m-%d'),
        data_fim=data_fim_str or data_fim.strftime('%Y-%m-%d'),
        tipo_filtro=tipo_filtro)


@app.route('/admin/estoque/editar-minimo/<tipo_item>/<int:item_id>', methods=['POST'])
@login_required
@admin_required
def editar_minimo_estoque(tipo_item, item_id):
    data = request.get_json()
    item = _get_item_estoque(tipo_item, item_id)
    if not item:
        return jsonify(ok=False, erro='Item não encontrado'), 404
    item.estoque_minimo = max(0, int(data.get('minimo', 5)))
    db.session.commit()
    return jsonify(ok=True, minimo=item.estoque_minimo)


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
        config.card_columns     = int(request.form.get('card_columns',  3) or 3)
        config.card_gap         = int(request.form.get('card_gap',     20) or 20)
        config.show_carousel    = request.form.get('show_carousel') == 'on'
        config.btn_radius       = request.form.get('btn_radius',       '12px')
        config.card_shadow      = request.form.get('card_shadow',      'medium')
        config.navbar_fixed     = request.form.get('navbar_fixed') == 'on'
        config.anim_enabled     = request.form.get('anim_enabled') == 'on'
        config.anim_intensity   = request.form.get('anim_intensity',   'medium')
        config.anim_duration    = int(request.form.get('anim_duration', 220) or 220)
        config.anim_hover_style = request.form.get('anim_hover_style', 'lift')
        config.site_name        = request.form.get('site_name',        'Doces da Fhê')
        config.logo_height      = int(request.form.get('logo_height', 100) or 100)
        config.logo_fit         = request.form.get('logo_fit', 'contain')
        config.carousel_height  = int(request.form.get('carousel_height', 340) or 340)
        config.card_img_height  = int(request.form.get('card_img_height', 200) or 200)
        config.card_radius      = request.form.get('card_radius', '16px')
        config.flash_success    = request.form.get('flash_success', '#ffffff')
        config.flash_error      = request.form.get('flash_error',  '#f8d7da')
        config.flash_info       = request.form.get('flash_info',   '#ffffff')
        config.new_badge_days   = int(request.form.get('new_badge_days', 7) or 7)
        config.new_badge_ativo  = request.form.get('new_badge_ativo') == '1'
        config.blog_primary     = request.form.get('blog_primary',  '#5B6D3D')
        config.blog_accent      = request.form.get('blog_accent',   '#932E50')
        config.blog_bg          = request.form.get('blog_bg',       '#f8fafc')
        config.blog_card_bg     = request.form.get('blog_card_bg',  '#ffffff')
        config.blog_text        = request.form.get('blog_text',     '#1e293b')
        config.auth_bg_color1   = request.form.get('auth_bg_color1', '#e8eed8')
        config.auth_bg_color2   = request.form.get('auth_bg_color2', '#8fa05a')

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


# ══════════════════════════════════════════════
#  AVALIAÇÕES
# ══════════════════════════════════════════════

@app.route('/avaliar', methods=['POST'])
@login_required
def avaliar():
    produto_id  = request.form.get('produto_id', type=int)
    kit_id      = request.form.get('kit_id', type=int)
    especial_id = request.form.get('especial_id', type=int)
    estrelas    = request.form.get('estrelas', type=int)
    comentario  = request.form.get('comentario', '').strip()
    next_url    = request.form.get('next', url_for('dashboard'))

    if not estrelas or not (1 <= estrelas <= 5):
        flash('Selecione uma nota de 1 a 5 estrelas.', 'error')
        return redirect(next_url)

    ja_existe = Avaliacao.query.filter_by(
        user_id=current_user.id,
        produto_id=produto_id,
        kit_id=kit_id,
        especial_id=especial_id
    ).first()
    if ja_existe:
        flash('Você já avaliou este produto.', 'warning')
        return redirect(next_url)

    av = Avaliacao(user_id=current_user.id, produto_id=produto_id,
                   kit_id=kit_id, especial_id=especial_id,
                   estrelas=estrelas, comentario=comentario or None)
    db.session.add(av)
    db.session.commit()
    flash('Avaliação enviada! Obrigada pelo feedback 💖', 'success')
    return redirect(next_url)


@app.route('/avaliar/<int:id>/deletar', methods=['POST'])
@login_required
@admin_required
def deletar_avaliacao(id):
    av = Avaliacao.query.get_or_404(id)
    next_url = request.form.get('next', url_for('dashboard'))
    db.session.delete(av)
    db.session.commit()
    flash('Avaliação removida.', 'info')
    return redirect(next_url)


# ══════════════════════════════════════════════
#  LEMBRANCINHAS
# ══════════════════════════════════════════════

@app.route('/admin/brindes', methods=['GET', 'POST'])
@login_required
@admin_required
def admin_brindes():
    if request.method == 'POST':
        acao = request.form.get('acao')

        if acao == 'criar':
            try:
                valor_min = float(request.form['valor_minimo'])
                qtd_brind = int(request.form.get('quantidade_brinde', 1))
                nome      = request.form['produto_nome'].strip()
                if not nome or valor_min <= 0 or qtd_brind < 1:
                    raise ValueError
                l = Brinde(valor_minimo=valor_min,
                                 produto_nome=nome,
                                 quantidade_brinde=qtd_brind)
                db.session.add(l)
                db.session.commit()
                flash('Brinde criado com sucesso!', 'success')
            except (ValueError, KeyError):
                flash('Preencha todos os campos corretamente.', 'error')

        elif acao == 'toggle':
            l = Brinde.query.get_or_404(int(request.form['id']))
            l.ativo = not l.ativo
            db.session.commit()
            flash('Status atualizado.', 'success')

        elif acao == 'deletar':
            l = Brinde.query.get_or_404(int(request.form['id']))
            db.session.delete(l)
            db.session.commit()
            flash('Brinde removido.', 'info')

        return redirect(url_for('admin_brindes'))

    itens = Brinde.query.order_by(Brinde.valor_minimo).all()
    return render_template('admin/brindes.html', brindes=itens)


# ─────────────────────────────────────
# CORPORATIVO
# ─────────────────────────────────────

def _corp_config():
    cfg = ConfigCorporativo.query.first()
    if not cfg:
        cfg = ConfigCorporativo()
        db.session.add(cfg)
        db.session.commit()
    return cfg


@app.route('/corporativo')
def corporativo():
    config = _corp_config()
    produtos = Product.query.filter_by(category='corporativos', ativo=True).all()
    fav_p, fav_k, fav_e = _fav_sets(current_user.id) if current_user.is_authenticated else (set(), set(), set())
    return render_template('corporativo/corporativo_index.html',
                           config=config, produtos=produtos,
                           fav_p=fav_p, fav_k=fav_k, fav_e=fav_e,
                           categoria='corporativos')


@app.route('/corporativo/personalizar', methods=['GET', 'POST'])
@login_required
def corporativo_personalizar():
    config = _corp_config()
    produtos = Product.query.filter_by(category='corporativos', ativo=True).all()
    produto_id = request.args.get('produto_id', type=int)
    produto_selecionado = Product.query.get(produto_id) if produto_id else None

    if request.method == 'POST':
        prod_id        = request.form.get('produto_id', type=int)
        prod_nome      = request.form.get('produto_nome', '').strip()
        quantidade     = request.form.get('quantidade', type=int) or 1
        personalizacao = request.form.get('personalizacao', '').strip()
        sabor          = request.form.get('sabor', '').strip()
        cor_fita       = request.form.get('cor_fita', '').strip()
        modelo_tag     = request.form.get('modelo_tag', '').strip()
        frase_tag      = request.form.get('frase_tag', '').strip()
        observacoes    = request.form.get('observacoes', '').strip()

        if not prod_id:
            flash('Selecione um produto.', 'error')
            return redirect(request.url)

        logo_url = None
        arquivo = request.files.get('logo')
        if arquivo and arquivo.filename and allowed_file(arquivo.filename):
            filename = f"{int(time.time())}_{secure_filename(arquivo.filename)}"
            arquivo.save(os.path.join(UPLOAD_FOLDER_CORP, filename))
            logo_url = f"uploads/corporativo/{filename}"

        partes = ['[Pedido Corporativo]']
        if personalizacao: partes.append(f'Personalização: {personalizacao}')
        if sabor:          partes.append(f'Sabor: {sabor}')
        if cor_fita:       partes.append(f'Cor da fita: {cor_fita}')
        if modelo_tag:     partes.append(f'Modelo de tag: {modelo_tag}')
        if frase_tag:      partes.append(f'Frase na tag: {frase_tag}')
        if logo_url:
            logo_link = url_for('static', filename=logo_url, _external=True)
            partes.append(f'Logo da empresa: {logo_link}')
        if observacoes:    partes.append(f'Observações: {observacoes}')
        notas = '\n'.join(partes)

        pedido = PedidoCorporativo(
            user_id=current_user.id,
            nome=current_user.name or '', email=current_user.email,
            telefone=current_user.phone or '', tipo='personalizar',
            produto_id=prod_id, produto_nome=prod_nome, quantidade=quantidade,
            personalizacao=personalizacao, sabor=sabor, logo_url=logo_url, cor_fita=cor_fita,
            modelo_tag=modelo_tag, frase_tag=frase_tag, observacoes=observacoes
        )
        db.session.add(pedido)

        item = CarrinhoItem.query.filter_by(
            user_id=current_user.id, produto_id=prod_id,
            kit_id=None, especial_id=None
        ).first()
        if item:
            item.quantidade += quantidade
            item.notas_corp = notas
        else:
            item = CarrinhoItem(user_id=current_user.id, produto_id=prod_id,
                                quantidade=quantidade, notas_corp=notas)
            db.session.add(item)

        db.session.commit()
        flash('Produto adicionado ao carrinho!', 'success')
        return redirect(url_for('carrinho'))

    user_data = {'nome': current_user.name or '', 'email': current_user.email,
                 'telefone': current_user.phone or ''} if current_user.is_authenticated else {}
    return render_template('corporativo/personalizar.html',
                           config=config, produtos=produtos,
                           produto_selecionado=produto_selecionado,
                           user_data=user_data, categoria='corporativos')


@app.route('/corporativo/solicitar', methods=['GET', 'POST'])
@login_required
def corporativo_solicitar():
    config = _corp_config()

    if request.method == 'POST':
        descricao     = request.form.get('descricao', '').strip()
        quantidade    = request.form.get('quantidade', '').strip()
        cor_fita      = request.form.get('cor_fita', '').strip()
        modelo_tag    = request.form.get('modelo_tag', '').strip()
        frase_tag     = request.form.get('frase_tag', '').strip()
        observacoes   = request.form.get('observacoes', '').strip()

        if not descricao:
            flash('Descreva o produto desejado.', 'error')
            return redirect(request.url)

        logo_url = None
        arquivo = request.files.get('logo')
        if arquivo and arquivo.filename and allowed_file(arquivo.filename):
            filename = f"{int(time.time())}_{secure_filename(arquivo.filename)}"
            arquivo.save(os.path.join(UPLOAD_FOLDER_CORP, filename))
            logo_url = f"uploads/corporativo/{filename}"

        qtd_int = int(quantidade) if quantidade.isdigit() else None
        pedido = PedidoCorporativo(
            user_id=current_user.id,
            nome=current_user.name or '', email=current_user.email,
            telefone=current_user.phone or '', tipo='solicitar',
            personalizacao=descricao, quantidade=qtd_int, logo_url=logo_url,
            cor_fita=cor_fita, modelo_tag=modelo_tag, frase_tag=frase_tag,
            observacoes=observacoes
        )
        db.session.add(pedido)
        db.session.commit()
        flash('Solicitação enviada! Nossa equipe entrará em contato em breve.', 'success')
        return redirect(url_for('meus_pedidos'))

    user_data = {'nome': current_user.name or '', 'email': current_user.email,
                 'telefone': current_user.phone or ''} if current_user.is_authenticated else {}
    return render_template('corporativo/solicitar.html', config=config,
                           user_data=user_data, categoria='corporativos')


@app.route('/admin/corporativo', methods=['GET', 'POST'])
@login_required
def admin_corporativo():
    if not current_user.is_admin:
        return redirect(url_for('dashboard'))
    config = _corp_config()

    if request.method == 'POST':
        acao = request.form.get('acao')
        if acao == 'config':
            config.prazo_texto  = request.form.get('prazo_texto', '15 dias uteis').strip()
            config.informacoes  = request.form.get('informacoes', '').strip()
            config.cor_hero_ini = request.form.get('cor_hero_ini', '#1e293b')
            config.cor_hero_fim = request.form.get('cor_hero_fim', '#334155')
            config.cor_destaque = request.form.get('cor_destaque', '#5B6D3D')
            db.session.commit()
            flash('Configuracoes atualizadas!', 'success')
        return redirect(url_for('admin_corporativo'))

    status_filter = request.args.get('status', '')
    q = PedidoCorporativo.query
    if status_filter:
        q = q.filter_by(status=status_filter)
    pedidos = q.order_by(PedidoCorporativo.created_at.desc()).all()

    stats = {
        'total':        PedidoCorporativo.query.count(),
        'novo':         PedidoCorporativo.query.filter_by(status='novo').count(),
        'em_andamento': PedidoCorporativo.query.filter_by(status='em_andamento').count(),
        'concluido':    PedidoCorporativo.query.filter_by(status='concluido').count(),
        'cancelado':    PedidoCorporativo.query.filter_by(status='cancelado').count(),
    }
    return render_template('admin/corporativo.html', config=config,
                           pedidos=pedidos, stats=stats, status_filter=status_filter)


@app.route('/admin/corporativo/<int:id>/status', methods=['POST'])
@login_required
def admin_corporativo_status(id):
    if not current_user.is_admin:
        return redirect(url_for('dashboard'))
    p = PedidoCorporativo.query.get_or_404(id)
    p.status = request.form.get('status', p.status)
    db.session.commit()
    flash('Status atualizado.', 'success')
    sf = request.form.get('status_filter', '')
    return redirect(url_for('admin_corporativo', status=sf))


# ─────────────────────────────────────
# AGENDA
# ─────────────────────────────────────

@app.route('/admin/agenda', methods=['GET', 'POST'])
@login_required
def admin_agenda():
    if not current_user.is_admin:
        return redirect(url_for('dashboard'))
    if request.method == 'POST':
        from datetime import datetime as dt
        titulo    = request.form.get('titulo', '').strip()
        descricao = request.form.get('descricao', '').strip()
        local     = request.form.get('local', '').strip()
        cor       = request.form.get('cor', '#5B6D3D')
        inicio_data = request.form.get('data_inicio_data', '')
        inicio_hora = request.form.get('data_inicio_hora', '00:00')
        fim_data    = request.form.get('data_fim_data', '')
        fim_hora    = request.form.get('data_fim_hora', '00:00')
        if titulo and inicio_data:
            data_inicio = dt.strptime(f'{inicio_data} {inicio_hora}', '%Y-%m-%d %H:%M')
            data_fim    = dt.strptime(f'{fim_data} {fim_hora}', '%Y-%m-%d %H:%M') if fim_data else None
            evento = AgendaEvento(titulo=titulo, descricao=descricao, local=local,
                                  data_inicio=data_inicio, data_fim=data_fim, cor=cor)
            db.session.add(evento)
            db.session.commit()
            flash('Evento adicionado!', 'success')
        return redirect(url_for('admin_agenda'))
    from datetime import datetime as dt
    eventos = AgendaEvento.query.order_by(AgendaEvento.data_inicio).all()
    return render_template('admin/agenda.html', eventos=eventos, hoje=dt.now())


@app.route('/admin/agenda/<int:id>/excluir', methods=['POST'])
@login_required
def admin_agenda_excluir(id):
    if not current_user.is_admin:
        return redirect(url_for('dashboard'))
    evento = AgendaEvento.query.get_or_404(id)
    db.session.delete(evento)
    db.session.commit()
    flash('Evento removido.', 'success')
    return redirect(url_for('admin_agenda'))


@app.route('/admin/agenda/<int:id>/editar', methods=['POST'])
@login_required
def admin_agenda_editar(id):
    if not current_user.is_admin:
        return redirect(url_for('dashboard'))
    from datetime import datetime as dt
    evento = AgendaEvento.query.get_or_404(id)
    evento.titulo    = request.form.get('titulo', evento.titulo).strip()
    evento.descricao = request.form.get('descricao', '').strip()
    evento.local     = request.form.get('local', '').strip()
    evento.cor       = request.form.get('cor', evento.cor)
    inicio_data = request.form.get('data_inicio_data', '')
    inicio_hora = request.form.get('data_inicio_hora', '00:00')
    fim_data    = request.form.get('data_fim_data', '')
    fim_hora    = request.form.get('data_fim_hora', '00:00')
    if inicio_data:
        evento.data_inicio = dt.strptime(f'{inicio_data} {inicio_hora}', '%Y-%m-%d %H:%M')
    evento.data_fim = dt.strptime(f'{fim_data} {fim_hora}', '%Y-%m-%d %H:%M') if fim_data else None
    db.session.commit()
    flash('Evento atualizado!', 'success')
    return redirect(url_for('admin_agenda'))


# ─────────────────────────────────────
# RUN
# ─────────────────────────────────────
if __name__ == '__main__':
    app.run(debug=True)