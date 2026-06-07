from functools import wraps
from flask import Flask, render_template, request, redirect, url_for, flash, jsonify, Response
from flask_login import LoginManager, login_user, login_required, logout_user, current_user
from flask_mail import Mail, Message
from models import db, User, Product, Kit, KitProduct, EventoEspecial, ProdutoEspecial, CarrinhoItem, CarrosselItem, SiteConfig, Favorito, MovimentacaoEstoque, Pedido, PedidoItem, Brinde, Promocao, Avaliacao, ConfigCorporativo, PedidoCorporativo, BlogPost, AgendaEvento, DesignPalette, ItemFoto, CategoriaBanner
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
UPLOAD_FOLDER_FOTOS     = os.path.join('static', 'uploads', 'fotos_extras')
UPLOAD_FOLDER_BANNERS   = os.path.join('static', 'uploads', 'banners_categoria')
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'webp', 'gif'}

for folder in [UPLOAD_FOLDER_CARROSSEL, UPLOAD_FOLDER_PRODUTOS,
               UPLOAD_FOLDER_KITS, UPLOAD_FOLDER_ESPECIAIS, UPLOAD_FOLDER_LOGO,
               UPLOAD_FOLDER_CORP, UPLOAD_FOLDER_FOTOS, UPLOAD_FOLDER_BANNERS]:
    os.makedirs(folder, exist_ok=True)


# ── FUNÇÕES AUXILIARES ──

# Escurece uma cor hex multiplicando cada canal RGB por um fator
# Escurece uma cor hexadecimal pelo fator informado (usado nos templates Jinja)
def darken_hex(hex_color, factor=0.82):
    try:
        hex_color = hex_color.lstrip('#')
        r, g, b = (int(hex_color[i:i+2], 16) for i in (0, 2, 4))
        r, g, b = max(0, int(r*factor)), max(0, int(g*factor)), max(0, int(b*factor))
        return f"#{r:02x}{g:02x}{b:02x}"
    except Exception:
        return f"#{hex_color}"


# Clareia uma cor misturando-a com branco (usado nos templates Jinja)
def tint_hex(hex_color, amount=0.80):
    try:
        hex_color = hex_color.lstrip('#')
        r, g, b = (int(hex_color[i:i+2], 16) for i in (0, 2, 4))
        r = int(r + (255 - r) * amount)
        g = int(g + (255 - g) * amount)
        b = int(b + (255 - b) * amount)
        return f"#{r:02x}{g:02x}{b:02x}"
    except Exception:
        return f"#{hex_color}"


# Verifica se a extensão do arquivo está na lista de formatos permitidos
def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS


# Salva imagem de produto enviada via formulário e retorna o caminho relativo
def salvar_imagem_produto(arquivo):
    if not arquivo or arquivo.filename == '':
        return None
    ext = arquivo.filename.rsplit('.', 1)[-1].lower()
    if ext not in ALLOWED_EXTENSIONS:
        return None
    filename = f"{int(time.time())}_{secure_filename(arquivo.filename)}"
    arquivo.save(os.path.join(UPLOAD_FOLDER_PRODUTOS, filename))
    return f"uploads/produtos/{filename}"


def salvar_imagem_produto_b64(data_url):
    """Salva imagem a partir de base64 dataURL (fallback para Safari/mobile)."""
    import base64, re
    m = re.match(r'data:(image/[\w+]+);base64,(.+)', data_url, re.DOTALL)
    if not m:
        return None
    mime_type, b64data = m.groups()
    ext_map = {'image/jpeg': 'jpg', 'image/png': 'png', 'image/webp': 'webp', 'image/gif': 'gif'}
    ext = ext_map.get(mime_type, 'jpg')
    filename = f"{int(time.time())}_crop.{ext}"
    filepath = os.path.join(UPLOAD_FOLDER_PRODUTOS, filename)
    try:
        with open(filepath, 'wb') as f:
            f.write(base64.b64decode(b64data))
        return f"uploads/produtos/{filename}"
    except Exception:
        return None


# Salva imagem de produto especial a partir de base64 dataURL e retorna o caminho relativo
def salvar_imagem_especial_b64(data_url):
    import base64, re
    m = re.match(r'data:(image/[\w+]+);base64,(.+)', data_url, re.DOTALL)
    if not m:
        return None
    mime_type, b64data = m.groups()
    ext_map = {'image/jpeg': 'jpg', 'image/png': 'png', 'image/webp': 'webp', 'image/gif': 'gif'}
    ext = ext_map.get(mime_type, 'jpg')
    filename = f"{int(time.time())}_crop.{ext}"
    filepath = os.path.join(UPLOAD_FOLDER_ESPECIAIS, filename)
    try:
        with open(filepath, 'wb') as f:
            f.write(base64.b64decode(b64data))
        return f"uploads/especiais/{filename}"
    except Exception:
        return None


# ── LOGIN MANAGER ──
login_manager = LoginManager()
login_manager.login_view = 'login'
login_manager.login_message = 'Faça login para acessar essa página.'
login_manager.login_message_category = 'info'
login_manager.init_app(app)
db.init_app(app)
app.jinja_env.filters['darken'] = darken_hex
app.jinja_env.filters['tint']   = tint_hex
from datetime import datetime as _dt
app.jinja_env.globals['now'] = _dt.utcnow

_MESES_PT       = ['janeiro','fevereiro','março','abril','maio','junho','julho','agosto','setembro','outubro','novembro','dezembro']
_MESES_ABREV_PT = ['jan','fev','mar','abr','mai','jun','jul','ago','set','out','nov','dez']

# Formata uma data no padrão brasileiro por extenso (ex: 01 de janeiro de 2025)
def data_pt(dt, fmt='%d de {mes} de %Y'):
    return dt.strftime(fmt.replace('{mes}', _MESES_PT[dt.month - 1]))

# Retorna a abreviação do mês em português (ex: jan, fev)
def mes_pt(dt):
    return _MESES_ABREV_PT[dt.month - 1]

app.jinja_env.filters['data_pt']   = data_pt
app.jinja_env.filters['mes_pt']    = mes_pt

import json as _json_mod
app.jinja_env.filters['from_json'] = _json_mod.loads

from blog_routes import blog_bp
app.register_blueprint(blog_bp)


# Decorador que restringe acesso a rotas apenas para administradores
def admin_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not current_user.is_authenticated or not current_user.is_admin:
            flash("Acesso negado. São necessárias permissões de administrador.", "error")
            return redirect(url_for('dashboard'))
        return f(*args, **kwargs)
    return decorated_function

# Carrega o usuário a partir do ID armazenado na sessão (requisito do Flask-Login)
# Carrega o usuário pelo ID para o gerenciador de sessão do Flask-Login
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
            ('site_config',       'auth_bg_color1',  'VARCHAR(20)'),
            ('site_config',       'auth_bg_color2',  'VARCHAR(20)'),
            ('site_config',       'auth_text_color', 'VARCHAR(20)'),
        ]:
            try:
                conn.execute(db.text(f'ALTER TABLE {tbl} ADD COLUMN {col} {typedef}'))
                conn.commit()
            except Exception:
                pass


# Verifica se o usuário atual tem permissão para editar ou excluir um kit
# Verifica se o usuário atual tem permissão para editar determinado kit
def user_can_edit_kit(kit):
    if current_user.is_admin:
        return True
    return (not kit.is_admin_kit) and (kit.created_by == current_user.id)


# ── CONTEXT PROCESSOR ──
# Injeta variáveis globais (total do carrinho e config do site) em todos os templates
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

# Redireciona a raiz do site para o dashboard
# Redireciona a raiz do site para o dashboard
@app.route('/')
def home():
    return redirect(url_for('dashboard'))


# Exibe e processa o formulário de cadastro de novo usuário
# Cadastro de novo usuário com validação de e-mail, CEP e telefone
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
        token = secrets.token_urlsafe(32)
        new_user = User(
            name=name, email=email,
            password=hashed_pw.decode('utf-8'),
            phone=phone, cep=cep,
            email_verified=False,
            email_verification_token=token,
            email_verification_expiry=datetime.utcnow() + timedelta(hours=24)
        )
        db.session.add(new_user)
        db.session.commit()
        verify_url = url_for('verificar_email', token=token, _external=True)
        enviado = send_verification_email(email, verify_url)
        if enviado:
            flash("Conta criada! Enviamos um e-mail de confirmação. Verifique sua caixa de entrada antes de fazer login.", 'info')
        else:
            flash("Conta criada! Não conseguimos enviar o e-mail de confirmação. Use o link abaixo para verificar sua conta.", 'warning')
            flash(f"Link de verificação: {verify_url}", 'info')
        return redirect(url_for('login'))

    return render_template('auth/signup.html')


# Exibe e processa o formulário de login do usuário
# Autenticação do usuário com e-mail e senha; bloqueia se o e-mail não foi verificado
@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email    = request.form['email']
        password = request.form['password']
        user     = User.query.filter_by(email=email).first()
        if user and bcrypt.checkpw(password.encode('utf-8'), user.password.encode('utf-8')):
            if not user.email_verified:
                flash("Você precisa confirmar seu e-mail antes de fazer login. Verifique sua caixa de entrada ou solicite um novo e-mail.", 'warning')
                return render_template('auth/login.html', email_nao_verificado=True, email_usuario=email)
            user.last_login = datetime.utcnow()
            db.session.commit()
            login_user(user)
            return redirect(url_for('dashboard'))
        else:
            flash("Credenciais inválidas.", 'error')
    return render_template('auth/login.html')


# Confirma o e-mail do usuário usando o token enviado por e-mail
# Confirma o e-mail do usuário através do token enviado no cadastro
@app.route('/verificar-email/<token>')
def verificar_email(token):
    user = User.query.filter_by(email_verification_token=token).first()
    if not user:
        flash("Link de verificação inválido ou já utilizado.", 'error')
        return redirect(url_for('login'))
    if user.email_verification_expiry and user.email_verification_expiry < datetime.utcnow():
        flash("Link de verificação expirado. Solicite um novo e-mail de confirmação.", 'warning')
        return redirect(url_for('login'))
    user.email_verified = True
    user.email_verification_token = None
    user.email_verification_expiry = None
    db.session.commit()
    return render_template('auth/email_verificado.html')


# Reenvia o e-mail de verificação de conta para o usuário solicitante
# Reenvia o e-mail de verificação para o usuário que ainda não confirmou a conta
@app.route('/reenviar-verificacao', methods=['POST'])
def reenviar_verificacao():
    email = request.form.get('email', '').strip()
    user = User.query.filter_by(email=email).first()
    if user and not user.email_verified:
        token = secrets.token_urlsafe(32)
        user.email_verification_token = token
        user.email_verification_expiry = datetime.utcnow() + timedelta(hours=24)
        db.session.commit()
        verify_url = url_for('verificar_email', token=token, _external=True)
        enviado = send_verification_email(email, verify_url)
        if enviado:
            flash("E-mail de confirmação reenviado! Verifique sua caixa de entrada.", 'success')
        else:
            flash(f"Não conseguimos enviar o e-mail. Link direto: {verify_url}", 'warning')
    else:
        flash("Se esse e-mail existir e não estiver verificado, um novo link foi enviado.", 'info')
    return redirect(url_for('login'))


# Exibe formulário e envia link de recuperação de senha por e-mail
# Solicita recuperação de senha; gera token e envia link por e-mail (ou exibe na tela como fallback)
@app.route('/forgot-password', methods=['GET', 'POST'])
def forgot_password():
    if request.method == 'POST':
        email = request.form.get('email', '').strip().lower()
        user  = User.query.filter_by(email=email).first()
        if user:
            # proteção anti-spam: só permite novo token após 5 minutos
            if (user.reset_token_expiry and
                    user.reset_token_expiry > datetime.utcnow() + timedelta(hours=23, minutes=55)):
                flash('Um link de recuperação já foi enviado recentemente. Aguarde alguns minutos antes de tentar novamente.', 'warning')
                return redirect(url_for('forgot_password'))

            token = secrets.token_urlsafe(32)
            user.reset_token        = token
            user.reset_token_expiry = datetime.utcnow() + timedelta(hours=24)
            db.session.commit()
            reset_url = url_for('reset_password', token=token, _external=True)
            enviado   = send_reset_email(email, reset_url)
            if enviado:
                flash('Enviamos um link de recuperação para o seu e-mail. Verifique sua caixa de entrada.', 'success')
            else:
                # fallback: exibe o link direto se o e-mail falhar
                flash('Não foi possível enviar o e-mail. Use o link abaixo para redefinir sua senha:', 'warning')
                flash(reset_url, 'info')
        else:
            # mensagem genérica para não vazar se o e-mail existe
            flash('Se esse e-mail estiver cadastrado, você receberá um link de recuperação.', 'info')
        return redirect(url_for('forgot_password'))
    return render_template('auth/forgot_password.html')


# Envia e-mail com link para redefinição de senha
# Envia o e-mail com link de redefinição de senha via Flask-Mail; retorna True se enviado
def send_reset_email(user_email, reset_url):
    try:
        msg = Message(
            subject="Solicitação de Redefinição de Senha",
            recipients=[user_email],
            html=render_template('auth/email_reset_password.html', reset_url=reset_url, cfg=SiteConfig.query.first()),
            body=f"Para redefinir sua senha, acesse: {reset_url}\n\nEste link expira em 24 horas."
        )
        mail.send(msg)
        return True
    except Exception as e:
        print(f"Erro ao enviar e-mail: {e}")
        return False


# Envia e-mail de confirmação de conta com link de verificação
# Envia o e-mail de confirmação de conta ao novo usuário; retorna True se enviado
def send_verification_email(user_email, verify_url):
    try:
        msg = Message(
            subject="Confirme seu e-mail — Doces da Fhê",
            recipients=[user_email],
            html=render_template('auth/email_verificacao.html', verify_url=verify_url, cfg=SiteConfig.query.first()),
            body=f"Acesse o link para confirmar sua conta: {verify_url}\n\nEste link expira em 24 horas."
        )
        mail.send(msg)
        return True
    except Exception as e:
        print(f"Erro ao enviar e-mail de verificação: {e}")
        return False


# Valida o token e permite ao usuário cadastrar uma nova senha
# Redefine a senha do usuário validando o token e as regras de complexidade
@app.route('/reset-password/<token>', methods=['GET', 'POST'])
def reset_password(token):
    user = User.query.filter_by(reset_token=token).first()
    # verifica token inválido ou expirado (trata None no expiry)
    if not user or not user.reset_token_expiry or user.reset_token_expiry < datetime.utcnow():
        flash('Link de redefinição inválido ou expirado. Solicite um novo link.', 'error')
        return redirect(url_for('forgot_password'))
    if request.method == 'POST':
        password         = request.form.get('password', '')
        confirm_password = request.form.get('confirm-password', '')
        erros = []
        if len(password) < 8:
            erros.append('A senha deve ter no mínimo 8 caracteres.')
        if not any(c.isdigit() for c in password):
            erros.append('A senha deve conter pelo menos um número.')
        if not any(c.isalpha() for c in password):
            erros.append('A senha deve conter pelo menos uma letra.')
        if password != confirm_password:
            erros.append('As senhas não coincidem.')
        if erros:
            for e in erros:
                flash(e, 'error')
            return redirect(url_for('reset_password', token=token))
        hashed_pw = bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt())
        user.password           = hashed_pw.decode('utf-8')
        user.reset_token        = None
        user.reset_token_expiry = None
        db.session.commit()
        flash('Senha redefinida com sucesso! Faça login com sua nova senha.', 'success')
        return redirect(url_for('login'))
    return render_template('auth/reset_password.html', token=token)


# Permite ao usuário autenticado alterar sua senha atual
# Permite ao usuário logado alterar sua própria senha informando a senha atual
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


# Encerra a sessão do usuário e redireciona para o login
# Encerra a sessão do usuário e redireciona para o login
@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('login'))


# ─────────────────────────────────────
# FAVORITOS
# ─────────────────────────────────────

# Retorna três conjuntos com os IDs de produtos, kits e especiais favoritados pelo usuário
# Retorna três conjuntos (sets) com os IDs dos produtos, kits e especiais favoritados pelo usuário
def _fav_sets(user_id):
    favs = Favorito.query.filter_by(user_id=user_id).all()
    return (
        {f.produto_id  for f in favs if f.produto_id},
        {f.kit_id      for f in favs if f.kit_id},
        {f.especial_id for f in favs if f.especial_id},
    )


# Adiciona ou remove um item dos favoritos do usuário via AJAX
# Adiciona ou remove um item dos favoritos do usuário (toggle via AJAX)
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


# Exibe a página com todos os itens favoritados pelo usuário logado
# Exibe a lista de produtos, kits e especiais salvos como favoritos pelo usuário
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

# Exibe a página principal da loja com produtos, kits, eventos ativos e carrossel
# Página principal da loja: carrega produtos, kits, carrossel, eventos, blog e promoções
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

    promocoes_loja = Promocao.query.filter_by(ativo=True, mostrar_na_faixa=True).order_by(Promocao.valor_minimo).all()

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
                           agenda_proximos=agenda_proximos,
                           promocoes_loja=promocoes_loja)


# ─────────────────────────────────────
# PRODUCTS
# ─────────────────────────────────────

# Lista todos os produtos cadastrados (painel administrativo)
# Lista todos os produtos cadastrados (painel admin)
@app.route('/products')
def list_products():
    products = Product.query.all()
    return render_template('product/produtos.html', products=products)


# Exibe o formulário e cria um novo produto no banco de dados
# Cria um novo produto com imagem (upload direto ou base64) e fotos extras
@app.route('/products/create', methods=['GET', 'POST'])
@login_required
@admin_required
def create_product():
    if request.method == 'POST':
        name        = request.form['name']
        resumo      = request.form.get('resumo', '').strip()
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
        imagem_b64 = request.form.get('imagem_b64', '').strip()
        if imagem_b64:
            image_url = salvar_imagem_produto_b64(imagem_b64)
        else:
            image_url = salvar_imagem_produto(arquivo)
        product = Product(name=name, resumo=resumo, description=description,
                          price=price, category=category, image_url=image_url,
                          quantidade_minima=qtd_min, quantidade_maxima=qtd_max)
        db.session.add(product)
        db.session.flush()  # gera o product.id antes do commit
        # fotos extras via base64 (crop)
        import base64 as _b64, re as _re
        for b64data in request.form.getlist('fotos_extras_b64'):
            if not b64data:
                continue
            m = _re.match(r'data:(image/[\w+]+);base64,(.+)', b64data, _re.DOTALL)
            if not m:
                continue
            mime, raw = m.groups()
            ext  = {'image/jpeg':'jpg','image/png':'png','image/webp':'webp'}.get(mime,'jpg')
            fname = f"{int(time.time())}_extra.{ext}"
            with open(os.path.join(UPLOAD_FOLDER_FOTOS, fname), 'wb') as fout:
                fout.write(_b64.b64decode(raw))
            db.session.add(ItemFoto(produto_id=product.id, url=f"uploads/fotos_extras/{fname}"))
        db.session.commit()
        flash("Produto criado com sucesso!", 'success')
        return redirect(url_for('list_products'))
    return render_template('product/produto_form.html')


# Exibe o formulário e salva as alterações de um produto existente
# Edita os dados de um produto existente, incluindo troca de imagem e fotos extras
@app.route('/products/edit/<int:id>', methods=['GET', 'POST'])
@login_required
@admin_required
def edit_product(id):
    product = Product.query.get_or_404(id)
    if request.method == 'POST':
        product.name        = request.form['name']
        product.resumo      = request.form.get('resumo', '').strip()
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
        imagem_b64 = request.form.get('imagem_b64', '').strip()
        if imagem_b64:
            nova_imagem = salvar_imagem_produto_b64(imagem_b64)
        else:
            nova_imagem = salvar_imagem_produto(arquivo)
        if nova_imagem:
            product.image_url = nova_imagem
        # fotos extras novas
        for arq in request.files.getlist('fotos_extras'):
            if not arq or arq.filename == '':
                continue
            ext = arq.filename.rsplit('.', 1)[-1].lower()
            if ext not in ALLOWED_EXTENSIONS:
                continue
            fname = f"{int(time.time())}_{secure_filename(arq.filename)}"
            arq.save(os.path.join(UPLOAD_FOLDER_FOTOS, fname))
            db.session.add(ItemFoto(produto_id=product.id, url=f"uploads/fotos_extras/{fname}"))
        db.session.commit()
        flash("Produto atualizado com sucesso!", 'success')
        return redirect(url_for('list_products'))
    fotos_extras = ItemFoto.query.filter_by(produto_id=product.id).order_by(ItemFoto.ordem).all()
    return render_template('product/produto_form.html', product=product, fotos_extras=fotos_extras)


# Remove permanentemente um produto do banco de dados
# Exclui permanentemente um produto do banco de dados
@app.route('/products/delete/<int:id>')
@login_required
@admin_required
def delete_product(id):
    product = Product.query.get_or_404(id)
    db.session.delete(product)
    db.session.commit()
    flash("Produto excluído com sucesso!")
    return redirect(url_for('list_products'))


# Alterna a visibilidade (ativo/oculto) de um produto na loja
# Alterna a visibilidade de um produto na loja (ativo/oculto)
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

# Lista os kits disponíveis para o usuário atual (admin vê todos, cliente vê os seus e os oficiais)
# Lista todos os kits (admin vê todos; cliente vê apenas os seus e os da loja)
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


# Exibe os detalhes de um kit específico para o usuário autorizado
# Exibe os detalhes de um kit específico (somente para quem tem permissão)
@app.route('/kits/<int:kit_id>')
@login_required
def view_kit(kit_id):
    kit = Kit.query.get_or_404(kit_id)
    if not (current_user.is_admin or kit.is_admin_kit or kit.created_by == current_user.id):
        flash("Você não tem permissão para visualizar este kit.", "error")
        return redirect(url_for('list_kits'))
    return render_template('kits/view.html', kit=kit)


# Cria um novo kit com nome, imagem e redireciona para adicionar produtos
@app.route('/kits/create', methods=['GET', 'POST'])
@login_required
def create_kit():
    if request.method == 'POST':
        name        = request.form.get('name', '').strip()
        resumo      = request.form.get('resumo', '').strip()
        description = request.form.get('description', '').strip()
        arquivo     = request.files.get('arquivo')
        if not name:
            flash("O nome do kit é obrigatório.", 'error')
            return redirect(url_for('create_kit'))
        image_url = None
        imagem_b64 = request.form.get('imagem_b64', '').strip()
        if imagem_b64:
            import base64, re as _re
            m = _re.match(r'data:(image/[\w+]+);base64,(.+)', imagem_b64, _re.DOTALL)
            if m:
                mime_type, b64data = m.groups()
                ext = {'image/jpeg':'jpg','image/png':'png','image/webp':'webp','image/gif':'gif'}.get(mime_type,'jpg')
                fname = f"{int(time.time())}_crop.{ext}"
                with open(os.path.join(UPLOAD_FOLDER_KITS, fname), 'wb') as f:
                    f.write(base64.b64decode(b64data))
                image_url = f"uploads/kits/{fname}"
        elif arquivo and arquivo.filename != '':
            ext = arquivo.filename.rsplit('.', 1)[-1].lower()
            if ext in ALLOWED_EXTENSIONS:
                filename = f"{int(time.time())}_{secure_filename(arquivo.filename)}"
                arquivo.save(os.path.join(UPLOAD_FOLDER_KITS, filename))
                image_url = f"uploads/kits/{filename}"
        kit = Kit(name=name, resumo=resumo, description=description,
                  created_by=current_user.id, image_url=image_url,
                  is_admin_kit=current_user.is_admin)
        db.session.add(kit)
        db.session.commit()
        flash(f"Kit '{kit.name}' criado com sucesso!", 'success')
        return redirect(url_for('edit_kit_products', kit_id=kit.id))
    return render_template('kits/create.html')


# Edita nome, descrição e imagem de um kit existente
@app.route('/kits/<int:kit_id>/edit', methods=['GET', 'POST'])
@login_required
def edit_kit(kit_id):
    kit = Kit.query.get_or_404(kit_id)
    if not user_can_edit_kit(kit):
        flash("Você não tem permissão para editar este kit.", 'error')
        return redirect(url_for('list_kits'))
    if request.method == 'POST':
        kit.name        = request.form.get('name', '').strip()
        kit.resumo      = request.form.get('resumo', '').strip()
        kit.description = request.form.get('description', '').strip()
        arquivo    = request.files.get('arquivo')
        imagem_b64 = request.form.get('imagem_b64', '').strip()
        if imagem_b64:
            import base64, re as _re
            m = _re.match(r'data:(image/[\w+]+);base64,(.+)', imagem_b64, _re.DOTALL)
            if m:
                mime_type, b64data = m.groups()
                ext = {'image/jpeg':'jpg','image/png':'png','image/webp':'webp','image/gif':'gif'}.get(mime_type,'jpg')
                fname = f"{int(time.time())}_crop.{ext}"
                with open(os.path.join(UPLOAD_FOLDER_KITS, fname), 'wb') as f:
                    f.write(base64.b64decode(b64data))
                kit.image_url = f"uploads/kits/{fname}"
        elif arquivo and arquivo.filename != '':
            ext = arquivo.filename.rsplit('.', 1)[-1].lower()
            if ext in ALLOWED_EXTENSIONS:
                filename = f"{int(time.time())}_{secure_filename(arquivo.filename)}"
                arquivo.save(os.path.join(UPLOAD_FOLDER_KITS, filename))
                kit.image_url = f"uploads/kits/{filename}"
        db.session.commit()
        flash("Kit atualizado!", 'success')
        return redirect(url_for('view_kit', kit_id=kit.id))
    fotos_extras = ItemFoto.query.filter_by(kit_id=kit.id).order_by(ItemFoto.ordem).all()
    return render_template('kits/edit.html', kit=kit, fotos_extras=fotos_extras)


# Exclui um kit do banco de dados
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


# Alterna a visibilidade de um kit na loja (ativo/oculto)
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


# Gerencia os produtos dentro de um kit (adicionar, remover e definir quantidades)
@app.route('/kits/<int:kit_id>/products', methods=['GET', 'POST'])
@login_required
def edit_kit_products(kit_id):
    kit = Kit.query.get_or_404(kit_id)
    if not user_can_edit_kit(kit):
        flash("Você não tem permissão para modificar este kit.", "error")
        return redirect(url_for('list_kits'))
    all_products = Product.query.filter(Product.category != 'corporativos').order_by(Product.name).all()
    kit_products = {kp.product_id: kp for kp in kit.products}
    if request.method == 'POST':
        product_ids   = request.form.getlist('product_id')
        submitted_ids = set(int(pid) for pid in product_ids)
        for kp in list(kit.products):
            if kp.product_id not in submitted_ids:
                db.session.delete(kp)
        for pid_str in product_ids:
            pid = int(pid_str)
            qty_raw = request.form.get(f'qty_{pid}', '1')
            qty = int(qty_raw) if qty_raw.isdigit() and int(qty_raw) > 0 else 1
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

# Exibe os produtos ativos de uma categoria com banner personalizado (se configurado)
@app.route('/categoria/<nome>')
def categoria(nome):
    if nome == 'corporativos':
        return redirect(url_for('corporativo'))
    produtos = Product.query.filter_by(category=nome, ativo=True).all()
    fav_p, fav_k, fav_e = _fav_sets(current_user.id) if current_user.is_authenticated else (set(), set(), set())
    banner = CategoriaBanner.query.filter_by(nome=nome).first()
    return render_template('product/categoria.html', produtos=produtos, categoria=nome,
                           fav_p=fav_p, fav_k=fav_k, fav_e=fav_e, banner=banner)


# Página pública de kits da loja com banner e lista de produtos para montar kit
@app.route('/kits_loja')
def kits_loja():
    kits = Kit.query.filter_by(is_admin_kit=True, ativo=True).all()
    produtos = Product.query.filter_by(ativo=True).order_by(Product.category, Product.name).all()
    fav_p, fav_k, fav_e = _fav_sets(current_user.id) if current_user.is_authenticated else (set(), set(), set())
    banner = CategoriaBanner.query.filter_by(nome='kits').first()
    return render_template('kits/kits_loja.html', kits=kits, produtos=produtos,
                           fav_p=fav_p, fav_k=fav_k, fav_e=fav_e, banner=banner)


# Página para o cliente montar seu próprio kit escolhendo produtos
@app.route('/montar-kit')
@login_required
def montar_kit():
    produtos = Product.query.filter_by(ativo=True).order_by(Product.category, Product.name).all()
    return render_template('kits/montar_kit.html', produtos=produtos)


# Adiciona os produtos selecionados no "montar kit" direto ao carrinho do usuário
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


# Exibe a página de detalhe de um produto com avaliações, fotos extras e relacionados
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
    fotos_extras = ItemFoto.query.filter_by(produto_id=id).order_by(ItemFoto.ordem).all()
    return render_template('product/produto_detalhe.html',
                           produto=produto,
                           relacionados=relacionados,
                           is_kit=False,
                           fav_tipo='produto', fav_id=produto.id,
                           is_favorito=(produto.id in fav_p),
                           avaliacoes=avaliacoes, media=media, ja_avaliou=ja_avaliou,
                           fotos_extras=fotos_extras)


# Exibe a página de detalhe de um kit adaptando-o ao template de produto
@app.route('/kit-detalhe/<int:kit_id>')
def kit_detalhe(kit_id):
    kit = Kit.query.get_or_404(kit_id)

    class KitAdapter:
        def __init__(self, k):
            self.id          = k.id
            self.name        = k.name
            self.category    = 'Kits'
            self.resumo      = k.resumo or ''
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
    fotos_extras = ItemFoto.query.filter_by(kit_id=kit_id).order_by(ItemFoto.ordem).all()
    return render_template('product/produto_detalhe.html',
                           produto=produto,
                           relacionados=relacionados,
                           is_kit=True, kit=kit,
                           fav_tipo='kit', fav_id=kit.id,
                           is_favorito=(kit.id in fav_k),
                           avaliacoes=avaliacoes, media=media, ja_avaliou=ja_avaliou,
                           fotos_extras=fotos_extras)


# Exibe a página de detalhe de um produto especial (vinculado a evento)
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
    fotos_extras = ItemFoto.query.filter_by(especial_id=id).order_by(ItemFoto.ordem).all()
    return render_template('product/produto_detalhe.html',
                           produto=produto,
                           relacionados=relacionados,
                           is_kit=False,
                           fav_tipo='especial', fav_id=produto.id,
                           is_favorito=(produto.id in fav_e),
                           avaliacoes=avaliacoes, media=media, ja_avaliou=ja_avaliou,
                           fotos_extras=fotos_extras)


# Busca global por nome em produtos, kits e especiais ativos
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

# Lista todos os eventos especiais cadastrados no painel admin
@app.route('/special/eventos')
@login_required
@admin_required
def listar_eventos():
    eventos = EventoEspecial.query.order_by(EventoEspecial.created_at.desc()).all()
    return render_template('special/eventos.html', eventos=eventos)


# Cria um novo evento especial com nome, período e descrição
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


# Edita os dados de um evento especial existente
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
    fotos_extras = ItemFoto.query.filter_by(evento_id=evento.id).order_by(ItemFoto.ordem).all()
    return render_template('special/editar_evento.html', evento=evento, fotos_extras=fotos_extras)


# Ativa ou desativa um evento especial (controla a exibição na loja)
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


# Exclui permanentemente um evento e todos os seus produtos especiais
@app.route('/special/eventos/<int:id>/deletar', methods=['POST'])
@login_required
@admin_required
def deletar_evento(id):
    evento = EventoEspecial.query.get_or_404(id)
    db.session.delete(evento)
    db.session.commit()
    flash(f'Evento "{evento.nome}" deletado!', 'success')
    return redirect(url_for('listar_eventos'))


# Lista os produtos especiais vinculados a um evento
@app.route('/special/eventos/<int:evento_id>/produtos')
@login_required
@admin_required
def listar_produtos_especiais(evento_id):
    evento   = EventoEspecial.query.get_or_404(evento_id)
    produtos = ProdutoEspecial.query.filter_by(evento_id=evento_id).all()
    return render_template('special/produtos_especiais.html', evento=evento, produtos=produtos)


# Cria um produto especial vinculado a um evento com imagem e quantidades
@app.route('/special/eventos/<int:evento_id>/produtos/criar', methods=['GET', 'POST'])
@login_required
@admin_required
def criar_produto_especial(evento_id):
    evento = EventoEspecial.query.get_or_404(evento_id)
    if request.method == 'POST':
        name        = request.form.get('name', '').strip()
        resumo      = request.form.get('resumo', '').strip()
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

        imagem_b64 = request.form.get('imagem_b64', '').strip()
        image_url = None
        if imagem_b64:
            image_url = salvar_imagem_especial_b64(imagem_b64)
        elif arquivo and arquivo.filename != '':
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
            resumo=resumo,
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


# Edita os dados de um produto especial existente
@app.route('/special/produtos-especiais/<int:id>/editar', methods=['GET', 'POST'])
@login_required
@admin_required
def editar_produto_especial(id):
    produto = ProdutoEspecial.query.get_or_404(id)
    if request.method == 'POST':
        produto.name              = request.form.get('name', '').strip()
        produto.resumo            = request.form.get('resumo', '').strip()
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

        imagem_b64 = request.form.get('imagem_b64', '').strip()
        if imagem_b64:
            nova = salvar_imagem_especial_b64(imagem_b64)
            if nova:
                produto.image_url = nova
        elif arquivo and arquivo.filename != '':
            ext = arquivo.filename.rsplit('.', 1)[-1].lower()
            if ext in ALLOWED_EXTENSIONS:
                filename = f"{int(time.time())}_{secure_filename(arquivo.filename)}"
                arquivo.save(os.path.join(UPLOAD_FOLDER_ESPECIAIS, filename))
                produto.image_url = f"uploads/especiais/{filename}"

        db.session.commit()
        flash(f'Produto "{produto.name}" atualizado!', 'success')
        return redirect(url_for('listar_produtos_especiais', evento_id=produto.evento_id))
    fotos_extras = ItemFoto.query.filter_by(especial_id=produto.id).order_by(ItemFoto.ordem).all()
    return render_template('special/editar_produto_especial.html', produto=produto, fotos_extras=fotos_extras)


# Exclui permanentemente um produto especial
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


# Alterna a visibilidade de um produto especial na página do evento
@app.route('/special/produtos-especiais/<int:id>/toggle-mostrar')
@login_required
@admin_required
def toggle_mostrar(id):
    produto = ProdutoEspecial.query.get_or_404(id)
    produto.mostrar = not produto.mostrar
    db.session.commit()
    return redirect(url_for('listar_produtos_especiais', evento_id=produto.evento_id))


# Página pública de um evento especial com seus produtos disponíveis
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

WHATSAPP_NUMBER = '5511952734219'


# Exibe o carrinho com itens, total, brindes e promoções aplicáveis
@app.route('/carrinho')
@login_required
def carrinho():
    from flask import session as flask_session
    itens            = CarrinhoItem.query.filter_by(user_id=current_user.id).all()
    total            = sum(item.subtotal for item in itens)
    quantidade_total = sum(item.quantidade for item in itens)
    brinde = (Brinde.query
                    .filter_by(ativo=True)
                    .filter(Brinde.valor_minimo <= total)
                    .order_by(Brinde.valor_minimo.desc())
                    .first())
    # promoções manuais (percentual/fixo) — cliente escolhe uma; leve_pague é automático
    todas_promocoes = Promocao.query.filter(
        Promocao.ativo == True,
        Promocao.tipo != 'leve_pague'
    ).order_by(Promocao.valor_minimo).all()

    # aplicar promoções leve_pague automáticas para os produtos no carrinho
    desconto_leve_pague = 0.0
    leve_pague_info = []
    promo_lp = Promocao.query.filter_by(ativo=True, tipo='leve_pague').all()
    for promo in promo_lp:
        if not promo.produto_id or not promo.leve or not promo.pague:
            continue
        item_cart = next((i for i in itens if i.produto_id == promo.produto_id), None)
        if not item_cart:
            continue
        qtd      = item_cart.quantidade
        leve     = promo.leve
        pague    = promo.pague
        gratuitos = (qtd // leve) * (leve - pague)
        if gratuitos > 0:
            preco_unit = float(item_cart.preco_unit)
            valor_desc = round(gratuitos * preco_unit, 2)
            desconto_leve_pague += valor_desc
            leve_pague_info.append({
                'nome': promo.nome,
                'produto': item_cart.nome,
                'gratuitos': gratuitos,
                'desconto': valor_desc,
            })

    # promoção manual escolhida pelo cliente
    promocao_aplicada = None
    desconto_manual = 0.0
    pid = flask_session.get('promocao_id')
    if pid:
        p = Promocao.query.get(pid)
        if p and p.ativo and p.tipo != 'leve_pague' and float(p.valor_minimo) <= total:
            desconto_manual = p.desconto_para(total)
            promocao_aplicada = p
        else:
            flask_session.pop('promocao_id', None)

    desconto    = round(desconto_manual + desconto_leve_pague, 2)
    total_final = round(total - desconto, 2)
    return render_template('pedidos/carrinho.html', itens=itens,
                           total=total, quantidade_total=quantidade_total,
                           brinde=brinde, todas_promocoes=todas_promocoes,
                           promocao=promocao_aplicada,
                           desconto=desconto_manual, total_final=total_final,
                           leve_pague_info=leve_pague_info)


# Salva o ID da promoção escolhida pelo cliente na sessão para aplicar no carrinho
@app.route('/carrinho/aplicar-promocao', methods=['POST'])
@login_required
def aplicar_promocao():
    from flask import session as flask_session
    pid = request.form.get('promocao_id', type=int)
    if pid:
        flask_session['promocao_id'] = pid
    else:
        flask_session.pop('promocao_id', None)
    return redirect(url_for('carrinho'))


# Adiciona um produto, kit ou especial ao carrinho respeitando quantidade mínima e máxima
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
        flash(f'Quantidade mínima por pedido: {qtd_min} unidade(s). Por favor, ajuste a quantidade.', 'error')
        return redirect(proxima_url)
    if qtd_max and quantidade > qtd_max:
        flash(f'Quantidade máxima por pedido: {qtd_max} unidade(s). Por favor, ajuste a quantidade.', 'error')
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


# Remove um item do carrinho do usuário
@app.route('/carrinho/remover/<int:item_id>', methods=['POST'])
@login_required
def remover_carrinho(item_id):
    item = CarrinhoItem.query.filter_by(id=item_id, user_id=current_user.id).first_or_404()
    db.session.delete(item)
    db.session.commit()
    flash('Item removido do carrinho.', 'info')
    return redirect(url_for('carrinho'))


# Atualiza a quantidade de um item no carrinho respeitando os limites do produto
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
        flash(f'Quantidade mínima por pedido de "{item.nome}": {qtd_min} unidade(s).', 'warning')
        return redirect(url_for('carrinho'))
    elif qtd_max and quantidade > qtd_max:
        item.quantidade = qtd_max
        db.session.commit()
        flash(f'Quantidade máxima por pedido de "{item.nome}": {qtd_max} unidade(s).', 'warning')
        return redirect(url_for('carrinho'))
    else:
        item.quantidade = quantidade
    db.session.commit()
    return redirect(url_for('carrinho'))


# Remove todos os itens do carrinho e limpa a promoção da sessão
@app.route('/carrinho/esvaziar', methods=['POST'])
@login_required
def esvaziar_carrinho():
    from flask import session as flask_session
    CarrinhoItem.query.filter_by(user_id=current_user.id).delete()
    db.session.commit()
    flask_session.pop('promocao_id', None)
    flash('Carrinho esvaziado.', 'info')
    return redirect(url_for('carrinho'))


# Finaliza o pedido: salva no banco, baixa estoque e redireciona para o WhatsApp com resumo
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

    # ── PROMOÇÃO LEVE/PAGUE (automática por produto) ──
    from flask import session as flask_session
    desconto_lp = 0.0
    for promo in Promocao.query.filter_by(ativo=True, tipo='leve_pague').all():
        if not promo.produto_id or not promo.leve or not promo.pague:
            continue
        item_cart = next((i for i in itens if i.produto_id == promo.produto_id), None)
        if not item_cart:
            continue
        gratuitos = (item_cart.quantidade // promo.leve) * (promo.leve - promo.pague)
        if gratuitos > 0:
            desconto_lp += round(gratuitos * float(item_cart.preco_unit), 2)

    # ── PROMOÇÃO DE DESCONTO (escolhida pelo cliente) ──
    promocao_aplicada = None
    desconto_manual = 0.0
    pid = flask_session.get('promocao_id')
    if pid:
        p = Promocao.query.get(pid)
        if p and p.ativo and p.tipo != 'leve_pague' and float(p.valor_minimo) <= total:
            desconto_manual = p.desconto_para(total)
            promocao_aplicada = p
    desconto = round(desconto_manual + desconto_lp, 2)
    total_final = round(total - desconto, 2)
    flask_session.pop('promocao_id', None)

    linhas.append(f'\n*Subtotal: R$ {total:.2f}*')
    if desconto_lp > 0:
        linhas.append(f'*Desconto Leve/Pague: -R$ {desconto_lp:.2f}*')
    if promocao_aplicada:
        linhas.append(f'*Promoção "{promocao_aplicada.nome}": -R$ {desconto_manual:.2f}*')
    linhas.append(f'*Total: R$ {total_final:.2f}*')

    # ── LEMBRANCINHA ──
    brinde = (Brinde.query
                    .filter_by(ativo=True)
                    .filter(Brinde.valor_minimo <= total)
                    .order_by(Brinde.valor_minimo.desc())
                    .first())
    if brinde:
        linhas.append('')
        linhas.append(f'*Brinde:* {brinde.quantidade_brinde}x {brinde.produto_nome} (pedidos acima de R$ {float(brinde.valor_minimo):.2f})')

    # ── SALVAR PEDIDO ──
    pedido = Pedido(
        user_id  = current_user.id,
        tipo     = tipo,
        endereco = endereco if tipo == 'entrega' else None,
        total    = total_final,
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

# Exibe o histórico de pedidos normais e corporativos do cliente logado
@app.route('/meus-pedidos')
@login_required
def meus_pedidos():
    pedidos = Pedido.query.filter_by(user_id=current_user.id, oculto_cliente=False)\
                          .order_by(Pedido.created_at.desc()).all()
    pedidos_corp = PedidoCorporativo.query.filter_by(user_id=current_user.id, oculto_cliente=False)\
                                          .order_by(PedidoCorporativo.created_at.desc()).all()
    return render_template('pedidos/meus_pedidos.html', pedidos=pedidos,
                           pedidos_corp=pedidos_corp)


# Cancela um pedido do cliente se ainda estiver com status pendente
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


# Oculta pedidos concluídos ou cancelados do histórico visível do cliente
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

# Painel admin de pedidos com filtro por status, estatísticas e gráfico por dia
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

    from collections import OrderedDict
    _dias: dict = OrderedDict()
    for p in sorted(pedidos, key=lambda x: x.created_at):
        d = p.created_at.strftime('%Y-%m-%d')
        if d not in _dias:
            _dias[d] = {'label': p.created_at.strftime('%d/%m'), 'pedidos': [], 'faturado': 0.0}
        _dias[d]['pedidos'].append(p)
        if p.status in ('confirmado', 'entregue'):
            _dias[d]['faturado'] += float(p.total)
    pedidos_por_dia = list(_dias.items())

    return render_template('admin/pedidos.html',
                           pedidos=pedidos, status_filter=status_filter, stats=stats,
                           brindes=brindes, pedidos_por_dia=pedidos_por_dia)


# Atualiza o status de um pedido (pendente, confirmado, entregue, cancelado)
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

# Exibe painel de estoque com todos os produtos, kits e especiais com status de quantidade
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


# Retorna o objeto (produto, kit ou especial) pelo tipo e ID para operações de estoque
def _get_item_estoque(tipo, item_id):
    if tipo == 'produto':  return Product.query.get(item_id)
    if tipo == 'kit':      return Kit.query.get(item_id)
    if tipo == 'especial': return ProdutoEspecial.query.get(item_id)
    return None


# Registra uma entrada ou saída manual de estoque para um produto/kit/especial
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


# Retorna as últimas 50 movimentações de estoque de um item em formato JSON
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


# Relatório completo de estoque, vendas e pedidos corporativos por período; suporta exportação CSV
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

    # Agrupa pedidos por dia para o filtro de dias
    from collections import OrderedDict
    _dias: dict = OrderedDict()
    for p in sorted(pedidos_periodo, key=lambda x: x.created_at):
        d = p.created_at.strftime('%Y-%m-%d')
        if d not in _dias:
            _dias[d] = {'label': p.created_at.strftime('%d/%m'), 'pedidos': [], 'faturado': 0.0}
        _dias[d]['pedidos'].append(p)
        if p.status in ('confirmado', 'entregue'):
            _dias[d]['faturado'] += float(p.total)
    pedidos_por_dia = list(_dias.items())

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
        faturado     = float(sum(p.valor for p in corp_pedidos if p.valor and p.status == 'concluido') or 0),
    )

    _dias_corp2: dict = {}
    for p in sorted(corp_pedidos, key=lambda x: x.created_at):
        d = p.created_at.strftime('%Y-%m-%d')
        if d not in _dias_corp2:
            _dias_corp2[d] = {'label': p.created_at.strftime('%d/%m'), 'pedidos': [], 'faturado': 0.0}
        _dias_corp2[d]['pedidos'].append(p)
        if p.valor and p.status == 'concluido':
            _dias_corp2[d]['faturado'] += float(p.valor)
    corp_por_dia = list(_dias_corp2.items())

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
        pedidos_por_dia=pedidos_por_dia,
        venda_stats=venda_stats,
        corp_pedidos=corp_pedidos,
        corp_por_dia=corp_por_dia,
        corp_stats=corp_stats,
        data_ini=data_ini_str or data_ini.strftime('%Y-%m-%d'),
        data_fim=data_fim_str or data_fim.strftime('%Y-%m-%d'),
        tipo_filtro=tipo_filtro)


# Apaga todo o histórico de pedidos e movimentações de estoque (ação irreversível)
@app.route('/admin/relatorio/limpar-historico', methods=['POST'])
@login_required
@admin_required
def limpar_historico_vendas():
    PedidoItem.query.delete()
    Pedido.query.delete()
    PedidoCorporativo.query.delete()
    MovimentacaoEstoque.query.delete()
    db.session.commit()
    flash('Histórico de vendas e movimentações apagado com sucesso.', 'success')
    return redirect(url_for('relatorio_estoque'))


# Atualiza o estoque mínimo de alerta de um produto/kit/especial via AJAX
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

# Exibe o formulário de adição de imagem ao carrossel da página inicial
@app.route('/carrossel')
@login_required
@admin_required
def carrossel_admin():
    return render_template('carrossel/carrossel_form.html')


# Lista todas as imagens do carrossel com opções de editar, reordenar e ativar/desativar
@app.route('/carrossel/listar')
@login_required
@admin_required
def carrossel_listar():
    itens = CarrosselItem.query.order_by(CarrosselItem.ordem).all()
    return render_template('carrossel/listar_carrossel.html', itens=itens)


CATEGORIAS_LOJA = ['bolos', 'brigadeiros', 'chocolates', 'trufas', 'brownie', 'kits']

# Gerencia os banners de topo de cada categoria (upload, título, descrição e ponto focal)
@app.route('/admin/banners-categoria', methods=['GET', 'POST'])
@login_required
@admin_required
def admin_banners_categoria():
    if request.method == 'POST':
        nome     = request.form.get('nome', '').strip()
        titulo   = request.form.get('titulo', '').strip()
        descricao = request.form.get('descricao', '').strip()
        arquivo  = request.files.get('imagem')

        banner = CategoriaBanner.query.filter_by(nome=nome).first()
        if not banner:
            banner = CategoriaBanner(nome=nome)
            db.session.add(banner)

        banner.titulo    = titulo or None
        banner.descricao = descricao or None
        banner.posicao   = request.form.get('posicao', 'center center')

        if arquivo and arquivo.filename:
            ext = arquivo.filename.rsplit('.', 1)[-1].lower()
            if ext in ALLOWED_EXTENSIONS:
                filename = f"{int(time.time())}_{secure_filename(arquivo.filename)}"
                arquivo.save(os.path.join(UPLOAD_FOLDER_BANNERS, filename))
                banner.imagem_url = f"uploads/banners_categoria/{filename}"

        db.session.commit()
        flash(f'Banner da categoria "{nome}" salvo com sucesso!', 'success')
        return redirect(url_for('admin_banners_categoria'))

    banners = {b.nome: b for b in CategoriaBanner.query.all()}
    return render_template('admin/banners_categoria.html',
                           categorias=CATEGORIAS_LOJA, banners=banners)


# Remove o banner de uma categoria do banco de dados
@app.route('/admin/banners-categoria/remover/<int:bid>', methods=['POST'])
@login_required
@admin_required
def admin_banner_remover(bid):
    banner = CategoriaBanner.query.get_or_404(bid)
    db.session.delete(banner)
    db.session.commit()
    flash('Banner removido.', 'info')
    return redirect(url_for('admin_banners_categoria'))


# Faz upload de uma nova imagem e adiciona ao carrossel com título e ordem
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


# Ativa ou desativa uma imagem do carrossel sem removê-la
@app.route('/carrossel/<int:id>/toggle')
@login_required
@admin_required
def carrossel_toggle(id):
    item = CarrosselItem.query.get_or_404(id)
    item.ativo = not item.ativo
    db.session.commit()
    return redirect(url_for('carrossel_listar'))


# Remove uma imagem do carrossel e apaga o arquivo físico do servidor
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


# Atualiza a ordem de exibição de uma imagem no carrossel
@app.route('/carrossel/<int:id>/ordem', methods=['POST'])
@login_required
@admin_required
def carrossel_ordem(id):
    item       = CarrosselItem.query.get_or_404(id)
    item.ordem = request.form.get('ordem', 0, type=int)
    db.session.commit()
    return redirect(url_for('carrossel_listar'))


# Edita o título, ordem e imagem de um item do carrossel
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

# Gera dinamicamente o arquivo CSS do site com base nas configurações de design salvas
@app.route('/dynamic-styles.css')
def dynamic_styles():
    config = SiteConfig.query.first()
    css = render_template('dynamic_styles.jinja2', config=config)
    return css, 200, {'Content-Type': 'text/css; charset=utf-8', 'Cache-Control': 'no-cache'}

# Painel de personalização do site: cores, fontes, layout, logo e animações
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
        config.flash_success      = request.form.get('flash_success',      '#ffffff')
        config.flash_error        = request.form.get('flash_error',        '#f8d7da')
        config.flash_info         = request.form.get('flash_info',         '#ffffff')
        config.flash_success_text = request.form.get('flash_success_text', '#155724')
        config.flash_error_text   = request.form.get('flash_error_text',   '#721c24')
        config.flash_info_text    = request.form.get('flash_info_text',    '#0c5460')
        config.new_badge_days   = int(request.form.get('new_badge_days', 7) or 7)
        config.new_badge_ativo  = request.form.get('new_badge_ativo') == '1'
        config.new_badge_color  = request.form.get('new_badge_color', '#cc0000')
        config.blog_primary     = request.form.get('blog_primary',  '#5B6D3D')
        config.blog_accent      = request.form.get('blog_accent',   '#932E50')
        config.blog_bg          = request.form.get('blog_bg',       '#f8fafc')
        config.blog_card_bg     = request.form.get('blog_card_bg',  '#ffffff')
        config.blog_text        = request.form.get('blog_text',     '#1e293b')
        config.auth_bg_color1   = request.form.get('auth_bg_color1',  '#e8eed8')
        config.auth_bg_color2   = request.form.get('auth_bg_color2',  '#8fa05a')
        config.auth_text_color  = request.form.get('auth_text_color', '#ffffff')

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

    palettes = DesignPalette.query.order_by(DesignPalette.created_at.desc()).all()
    return render_template('admin/design.html', config=config, palettes=palettes)


_PALETTE_FIELDS = [
    'color_primary', 'color_secondary', 'color_accent', 'color_dark',
    'color_bg', 'color_text', 'color_text_light',
    'auth_bg_color1', 'auth_bg_color2', 'auth_text_color',
    'flash_success', 'flash_error', 'flash_info',
    'flash_success_text', 'flash_error_text', 'flash_info_text',
    'blog_primary', 'blog_accent', 'blog_bg', 'blog_card_bg', 'blog_text',
]


# Salva a paleta de cores atual do site com um nome para reutilização futura
@app.route('/admin/design/paleta/salvar', methods=['POST'])
@login_required
@admin_required
def admin_paleta_salvar():
    import json as _json
    nome = request.form.get('nome', '').strip()
    if not nome:
        flash('Informe um nome para a paleta.', 'error')
        return redirect(url_for('admin_design') + '#tab-paletas')
    config = SiteConfig.query.first()
    cores = {f: getattr(config, f, '') for f in _PALETTE_FIELDS}
    paleta = DesignPalette(nome=nome, cores=_json.dumps(cores))
    db.session.add(paleta)
    db.session.commit()
    flash(f'Paleta "{nome}" salva com sucesso!', 'success')
    return redirect(url_for('admin_design') + '#tab-paletas')


# Exclui uma paleta de cores salva
@app.route('/admin/design/paleta/<int:id>/excluir', methods=['POST'])
@login_required
@admin_required
def admin_paleta_excluir(id):
    paleta = DesignPalette.query.get_or_404(id)
    db.session.delete(paleta)
    db.session.commit()
    flash('Paleta excluída.', 'success')
    return redirect(url_for('admin_design') + '#tab-paletas')



# ══════════════════════════════════════════════
#  AVALIAÇÕES
# ══════════════════════════════════════════════

# Registra a avaliação de estrelas e comentário de um cliente para produto, kit ou especial
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


# Remove uma avaliação do banco de dados (somente admin)
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

# Redireciona para a página de promoções (brindes e promoções são gerenciados juntos)
@app.route('/admin/brindes')
@login_required
@admin_required
def admin_brindes():
    return redirect(url_for('admin_promocoes'))


# Gerencia brindes, promoções de desconto (percentual/fixo) e promoções leve/pague
@app.route('/admin/promocoes', methods=['GET', 'POST'])
@login_required
@admin_required
def admin_promocoes():
    if request.method == 'POST':
        acao     = request.form.get('acao')
        secao    = request.form.get('secao', 'brinde')

        if secao == 'brinde':
            if acao == 'criar':
                try:
                    valor_min = float(request.form['valor_minimo'])
                    qtd_brind = int(request.form.get('quantidade_brinde', 1))
                    nome      = request.form['produto_nome'].strip()
                    if not nome or valor_min <= 0 or qtd_brind < 1:
                        raise ValueError
                    db.session.add(Brinde(valor_minimo=valor_min,
                                         produto_nome=nome,
                                         quantidade_brinde=qtd_brind))
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

        elif secao == 'promocao':
            if acao == 'criar':
                try:
                    nome      = request.form['nome'].strip()
                    descricao = request.form.get('descricao', '').strip()
                    tipo      = request.form['tipo']
                    valor     = float(request.form['valor'])
                    valor_min = float(request.form.get('valor_minimo', 0) or 0)
                    if not nome or valor <= 0 or tipo not in ('percentual', 'fixo'):
                        raise ValueError
                    if tipo == 'percentual' and valor > 100:
                        raise ValueError
                    db.session.add(Promocao(nome=nome, descricao=descricao,
                                            tipo=tipo, valor=valor,
                                            valor_minimo=valor_min))
                    db.session.commit()
                    flash('Promoção criada com sucesso!', 'success')
                except (ValueError, KeyError):
                    flash('Preencha todos os campos corretamente.', 'error')
            elif acao == 'toggle':
                p = Promocao.query.get_or_404(int(request.form['id']))
                p.ativo = not p.ativo
                db.session.commit()
                flash('Status atualizado.', 'success')
            elif acao == 'toggle_faixa':
                p = Promocao.query.get_or_404(int(request.form['id']))
                p.mostrar_na_faixa = not p.mostrar_na_faixa
                db.session.commit()
            elif acao == 'deletar':
                p = Promocao.query.get_or_404(int(request.form['id']))
                db.session.delete(p)
                db.session.commit()
                flash('Promoção removida.', 'info')

        elif secao == 'leve_pague':
            if acao == 'toggle_faixa':
                p = Promocao.query.get_or_404(int(request.form['id']))
                p.mostrar_na_faixa = not p.mostrar_na_faixa
                db.session.commit()
            elif acao == 'criar':
                try:
                    nome       = request.form.get('nome', '').strip()
                    produto_id = int(request.form['produto_id'])
                    leve_v     = int(request.form['leve'])
                    pague_v    = int(request.form['pague'])
                    if not produto_id or leve_v < 2 or pague_v < 1 or pague_v >= leve_v:
                        raise ValueError
                    prod = Product.query.get_or_404(produto_id)
                    if not nome:
                        nome = f'Leve {leve_v} Pague {pague_v} — {prod.name}'
                    db.session.add(Promocao(nome=nome, tipo='leve_pague', valor=0,
                                            valor_minimo=0, leve=leve_v, pague=pague_v,
                                            produto_id=produto_id))
                    db.session.commit()
                    flash('Promoção Leve/Pague criada!', 'success')
                except (ValueError, KeyError):
                    flash('Preencha todos os campos corretamente.', 'error')
            elif acao == 'toggle':
                p = Promocao.query.get_or_404(int(request.form['id']))
                p.ativo = not p.ativo
                db.session.commit()
                flash('Status atualizado.', 'success')
            elif acao == 'deletar':
                p = Promocao.query.get_or_404(int(request.form['id']))
                db.session.delete(p)
                db.session.commit()
                flash('Promoção removida.', 'info')

        dest = url_for('admin_promocoes') + ('#leve-pague' if secao == 'leve_pague' else '')
        return redirect(dest)

    brindes      = Brinde.query.order_by(Brinde.valor_minimo).all()
    promocoes    = Promocao.query.filter(Promocao.tipo != 'leve_pague').order_by(Promocao.valor_minimo).all()
    leve_pague   = Promocao.query.filter_by(tipo='leve_pague').order_by(Promocao.id).all()
    produtos_ativos = Product.query.filter_by(ativo=True).order_by(Product.name).all()
    return render_template('admin/promocoes.html', brindes=brindes, promocoes=promocoes,
                           leve_pague=leve_pague, produtos_ativos=produtos_ativos)


# ─────────────────────────────────────
# CORPORATIVO
# ─────────────────────────────────────

# Retorna a configuração corporativa; cria um registro padrão se ainda não existir
def _corp_config():
    cfg = ConfigCorporativo.query.first()
    if not cfg:
        cfg = ConfigCorporativo()
        db.session.add(cfg)
        db.session.commit()
    return cfg


# Página pública da seção corporativa com produtos e informações de personalização
@app.route('/corporativo')
def corporativo():
    config = _corp_config()
    produtos = Product.query.filter_by(category='corporativos', ativo=True).all()
    fav_p, fav_k, fav_e = _fav_sets(current_user.id) if current_user.is_authenticated else (set(), set(), set())
    return render_template('corporativo/corporativo_index.html',
                           config=config, produtos=produtos,
                           fav_p=fav_p, fav_k=fav_k, fav_e=fav_e,
                           categoria='corporativos')


# Formulário de personalização corporativa: cliente escolhe produto, sabor, fita, tag e logo
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


# Formulário de solicitação livre de produto corporativo; gera pedido para contato posterior
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


# Painel admin de pedidos corporativos com filtro de status, estatísticas e configurações
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
    from collections import OrderedDict
    _dias_corp: dict = OrderedDict()
    for p in sorted(pedidos, key=lambda x: x.created_at):
        d = p.created_at.strftime('%Y-%m-%d')
        if d not in _dias_corp:
            _dias_corp[d] = {'label': p.created_at.strftime('%d/%m'), 'pedidos': [], 'faturado': 0.0}
        _dias_corp[d]['pedidos'].append(p)
        if p.valor and p.status in ('concluido',):
            _dias_corp[d]['faturado'] += float(p.valor)
    pedidos_por_dia = list(_dias_corp.items())

    stats['faturado_corp'] = float(sum(
        p.valor for p in pedidos if p.valor and p.status == 'concluido'
    ) or 0)

    return render_template('admin/corporativo.html', config=config,
                           pedidos=pedidos, stats=stats, status_filter=status_filter,
                           pedidos_por_dia=pedidos_por_dia)


# Atualiza o status e o valor de um pedido corporativo
@app.route('/admin/corporativo/<int:id>/status', methods=['POST'])
@login_required
def admin_corporativo_status(id):
    if not current_user.is_admin:
        return redirect(url_for('dashboard'))
    p = PedidoCorporativo.query.get_or_404(id)
    p.status = request.form.get('status', p.status)
    valor_str = request.form.get('valor', '').strip().replace(',', '.')
    if valor_str:
        try:
            p.valor = float(valor_str)
        except ValueError:
            pass
    db.session.commit()
    flash('Pedido atualizado.', 'success')
    sf = request.form.get('status_filter', '')
    return redirect(url_for('admin_corporativo', status=sf))


# ─────────────────────────────────────
# AGENDA
# ─────────────────────────────────────

# Gerencia a agenda de eventos internos; faz auto-limpeza de eventos expirados
@app.route('/admin/agenda', methods=['GET', 'POST'])
@login_required
def admin_agenda():
    if not current_user.is_admin:
        return redirect(url_for('dashboard'))
    from datetime import datetime as dt
    config = SiteConfig.query.first()

    if request.method == 'POST':
        acao = request.form.get('acao', 'novo_evento')

        # ── salvar configuração de dias ──
        if acao == 'salvar_config':
            dias = request.form.get('agenda_dias_arquivar', 30, type=int)
            config.agenda_dias_arquivar = max(1, dias)
            db.session.commit()
            flash(f'Configuração salva: eventos serão apagados após {config.agenda_dias_arquivar} dias.', 'success')
            return redirect(url_for('admin_agenda'))

        # ── novo evento ──
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

    # ── auto-limpeza: apaga eventos passados há mais de X dias ──
    dias_arquivar = (config.agenda_dias_arquivar or 30) if config else 30
    limite        = dt.now() - timedelta(days=dias_arquivar)
    expirados = AgendaEvento.query.filter(
        db.func.coalesce(AgendaEvento.data_fim, AgendaEvento.data_inicio) < limite
    ).all()
    if expirados:
        for ev in expirados:
            db.session.delete(ev)
        db.session.commit()

    # ── separa próximos e passados (ainda dentro do prazo) ──
    agora    = dt.now()
    proximos = AgendaEvento.query.filter(
        db.func.coalesce(AgendaEvento.data_fim, AgendaEvento.data_inicio) >= agora
    ).order_by(AgendaEvento.data_inicio).all()
    passados = AgendaEvento.query.filter(
        db.func.coalesce(AgendaEvento.data_fim, AgendaEvento.data_inicio) < agora
    ).order_by(AgendaEvento.data_inicio.desc()).all()

    return render_template('admin/agenda.html',
                           proximos=proximos, passados=passados,
                           hoje=agora, config=config,
                           dias_arquivar=dias_arquivar)


# Remove um evento da agenda
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


# Edita os dados de um evento da agenda (título, data, local e cor)
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
# ADMIN — USUÁRIOS
# ─────────────────────────────────────
# Lista todos os usuários cadastrados ordenados pelo último acesso
@app.route('/admin/usuarios')
@login_required
@admin_required
def admin_usuarios():
    usuarios = User.query.order_by(User.last_login.desc().nullslast(), User.created_at.desc()).all()
    return render_template('admin/usuarios.html', usuarios=usuarios)


# Promove ou rebaixa um usuário para admin; restrito à proprietária da conta
@app.route('/admin/usuarios/<int:uid>/toggle-admin', methods=['POST'])
@login_required
@admin_required
def admin_toggle_admin(uid):
    if current_user.email != 'docesdafhe@gmail.com':
        flash('Apenas a proprietária pode alterar níveis de acesso.', 'error')
        return redirect(url_for('admin_usuarios'))
    u = User.query.get_or_404(uid)
    if u.id == current_user.id:
        flash('Você não pode alterar seu próprio nível de acesso.', 'error')
        return redirect(url_for('admin_usuarios'))
    u.is_admin = not u.is_admin
    db.session.commit()
    acao = 'promovido a admin' if u.is_admin else 'rebaixado para cliente'
    flash(f'{u.name or u.email} foi {acao}.', 'success')
    return redirect(url_for('admin_usuarios'))


# ─────────────────────────────────────
# FOTOS EXTRAS (admin)
# ─────────────────────────────────────

# Faz upload de uma ou mais fotos extras para produto, kit, especial ou evento
@app.route('/admin/foto/add', methods=['POST'])
@login_required
@admin_required
def admin_foto_add():
    tipo     = request.form.get('tipo')          # produto | kit | especial | evento
    item_id  = request.form.get('item_id', type=int)
    arquivos = request.files.getlist('fotos')
    redirect_url = request.form.get('next', url_for('dashboard'))

    for arq in arquivos:
        if not arq or arq.filename == '':
            continue
        ext = arq.filename.rsplit('.', 1)[-1].lower()
        if ext not in ALLOWED_EXTENSIONS:
            continue
        fname = f"{int(time.time())}_{secure_filename(arq.filename)}"
        arq.save(os.path.join(UPLOAD_FOLDER_FOTOS, fname))
        url = f"uploads/fotos_extras/{fname}"

        kwargs = {'url': url}
        if tipo == 'produto':   kwargs['produto_id']  = item_id
        elif tipo == 'kit':     kwargs['kit_id']      = item_id
        elif tipo == 'especial':kwargs['especial_id'] = item_id
        elif tipo == 'evento':  kwargs['evento_id']   = item_id
        else:
            continue

        ordem = ItemFoto.query.filter_by(**{f'{tipo}_id': item_id}).count()
        kwargs['ordem'] = ordem
        db.session.add(ItemFoto(**kwargs))

    db.session.commit()
    flash('Foto(s) adicionada(s) com sucesso!', 'success')
    return redirect(redirect_url)


# Recebe uma foto em base64 via AJAX, salva no servidor e retorna id + URL em JSON
@app.route('/admin/foto/add-ajax', methods=['POST'])
@login_required
@admin_required
def admin_foto_add_ajax():
    import base64 as _b64, re as _re
    data    = request.get_json(force=True)
    tipo    = data.get('tipo')
    item_id = data.get('item_id')
    b64data = data.get('data', '')

    m = _re.match(r'data:(image/[\w+]+);base64,(.+)', b64data, _re.DOTALL)
    if not m:
        return jsonify(error='Dados inválidos'), 400

    mime, raw = m.groups()
    ext  = {'image/jpeg':'jpg','image/png':'png','image/webp':'webp','image/gif':'gif'}.get(mime,'jpg')
    fname = f"{int(time.time())}_extra.{ext}"
    try:
        with open(os.path.join(UPLOAD_FOLDER_FOTOS, fname), 'wb') as f:
            f.write(_b64.b64decode(raw))
    except Exception as e:
        return jsonify(error=str(e)), 500

    url    = f"uploads/fotos_extras/{fname}"
    kwargs = {'url': url}
    if   tipo == 'produto':   kwargs['produto_id']  = item_id
    elif tipo == 'kit':       kwargs['kit_id']      = item_id
    elif tipo == 'especial':  kwargs['especial_id'] = item_id
    elif tipo == 'evento':    kwargs['evento_id']   = item_id
    else:
        return jsonify(error='tipo inválido'), 400

    foto = ItemFoto(**kwargs)
    db.session.add(foto)
    db.session.commit()
    return jsonify(id=foto.id, url=url)


# Substitui a imagem de uma foto existente por uma nova versão em base64 via AJAX
@app.route('/admin/foto/<int:foto_id>/atualizar-ajax', methods=['POST'])
@login_required
@admin_required
def admin_foto_atualizar_ajax(foto_id):
    import base64 as _b64, re as _re
    data    = request.get_json(force=True)
    b64data = data.get('data', '')
    m = _re.match(r'data:(image/[\w+]+);base64,(.+)', b64data, _re.DOTALL)
    if not m:
        return jsonify(error='Dados inválidos'), 400
    foto = ItemFoto.query.get_or_404(foto_id)
    # remove arquivo antigo
    caminho_antigo = os.path.join('static', foto.url)
    if os.path.exists(caminho_antigo):
        os.remove(caminho_antigo)
    mime, raw = m.groups()
    ext  = {'image/jpeg':'jpg','image/png':'png','image/webp':'webp'}.get(mime,'jpg')
    fname = f"{int(time.time())}_extra.{ext}"
    with open(os.path.join(UPLOAD_FOLDER_FOTOS, fname), 'wb') as f:
        f.write(_b64.b64decode(raw))
    foto.url = f"uploads/fotos_extras/{fname}"
    db.session.commit()
    return jsonify(ok=True, url=foto.url)


# Remove uma foto extra e apaga o arquivo do servidor via AJAX
@app.route('/admin/foto/<int:foto_id>/excluir-ajax', methods=['POST'])
@login_required
@admin_required
def admin_foto_excluir_ajax(foto_id):
    foto = ItemFoto.query.get_or_404(foto_id)
    caminho = os.path.join('static', foto.url)
    if os.path.exists(caminho):
        os.remove(caminho)
    db.session.delete(foto)
    db.session.commit()
    return jsonify(ok=True)


# Remove uma foto extra via formulário (redirect) e apaga o arquivo do servidor
@app.route('/admin/foto/<int:foto_id>/excluir', methods=['POST'])
@login_required
@admin_required
def admin_foto_excluir(foto_id):
    foto = ItemFoto.query.get_or_404(foto_id)
    redirect_url = request.form.get('next', url_for('dashboard'))
    # remove o arquivo físico
    caminho = os.path.join('static', foto.url)
    if os.path.exists(caminho):
        os.remove(caminho)
    db.session.delete(foto)
    db.session.commit()
    flash('Foto removida.', 'info')
    return redirect(redirect_url)


# ─────────────────────────────────────
# RUN
# ─────────────────────────────────────
if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=False)