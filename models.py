from flask_sqlalchemy import SQLAlchemy
from flask_login import UserMixin
from datetime import datetime
db = SQLAlchemy()


class User(db.Model, UserMixin):
    __tablename__ = "users"
    id       = db.Column(db.Integer, primary_key=True)

    # AUTH
    email    = db.Column(db.String(120), unique=True, nullable=False, index=True)
    password = db.Column(db.String(200), nullable=False)

    # PERSONAL DATA
    name     = db.Column(db.String(120), nullable=True)   # ✅ NOVO
    phone    = db.Column(db.String(20), nullable=False)
    cep      = db.Column(db.String(8), nullable=False)

    # CHECA SE É ADM
    is_admin = db.Column(db.Boolean, default=False, nullable=False)

    # PASSWORD RESET
    reset_token        = db.Column(db.String(100), unique=True, nullable=True)
    reset_token_expiry = db.Column(db.DateTime, nullable=True)

    # METADATA
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    last_login = db.Column(db.DateTime, nullable=True)

    def __repr__(self):
        return f"<User {self.email}>"


class Product(db.Model):
    __tablename__ = "products"
    id          = db.Column(db.Integer, primary_key=True)
    name        = db.Column(db.String(200), nullable=False, index=True)
    resumo      = db.Column(db.String(400), nullable=True)
    description = db.Column(db.String(800), nullable=False)
    image_url   = db.Column(db.String(300))
    price       = db.Column(db.Numeric(10, 2), nullable=False)
    category          = db.Column(db.String(100), nullable=True, default='geral')  # ✅ NOVO
    ativo             = db.Column(db.Boolean, default=True, nullable=False)
    estoque           = db.Column(db.Integer, default=0, nullable=False)
    estoque_minimo    = db.Column(db.Integer, default=5, nullable=False)
    quantidade_minima = db.Column(db.Integer, default=1, nullable=False)
    quantidade_maxima = db.Column(db.Integer, nullable=True)
    created_at     = db.Column(db.DateTime, default=datetime.utcnow)

    @property
    def status_estoque(self):
        if self.estoque == 0:
            return 'zerado'
        if self.estoque <= self.estoque_minimo:
            return 'baixo'
        return 'ok'

    def __repr__(self):
        return f"<Product {self.name}>"


class Kit(db.Model):
    __tablename__ = 'kits'

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(200), nullable=False)
    resumo = db.Column(db.String(400), nullable=True)
    description = db.Column(db.Text, nullable=True)
    created_by = db.Column(
        db.Integer, db.ForeignKey('users.id'), nullable=False)
    is_admin_kit = db.Column(db.Boolean, default=False)   # True = admin kit
    ativo = db.Column(db.Boolean, default=True, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(
        db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    image_url      = db.Column(db.String(500), nullable=True)
    estoque        = db.Column(db.Integer, default=0, nullable=False)
    estoque_minimo = db.Column(db.Integer, default=5, nullable=False)
    # Relationships
    products = db.relationship(
        'KitProduct', backref='kit', cascade='all, delete-orphan')
    creator = db.relationship('User', backref='kits')

    @property
    def total_price(self):
        return sum(kp.product.price * kp.quantity for kp in self.products)

    @property
    def status_estoque(self):
        if self.estoque == 0:       return 'zerado'
        if self.estoque <= self.estoque_minimo: return 'baixo'
        return 'ok'

    def __repr__(self):
        return f'<Kit {self.name}>'


class KitProduct(db.Model):
    __tablename__ = 'kit_products'

    kit_id = db.Column(db.Integer, db.ForeignKey('kits.id'), primary_key=True)
    product_id = db.Column(db.Integer, db.ForeignKey(
        'products.id'), primary_key=True)
    quantity = db.Column(db.Integer, default=1)
    added_at = db.Column(db.DateTime, default=datetime.utcnow)

    # Relationships
    product = db.relationship('Product')


class EventoEspecial(db.Model):
    __tablename__ = "eventos_especiais"
    id          = db.Column(db.Integer, primary_key=True)
    nome        = db.Column(db.String(100), nullable=False, unique=True)
    descricao   = db.Column(db.String(300), nullable=True)
    ativo       = db.Column(db.Boolean, default=True)
    data_inicio = db.Column(db.DateTime, nullable=True)  # None = sem restrição de início
    data_fim    = db.Column(db.DateTime, nullable=True)  # None = sem restrição de fim
    created_at  = db.Column(db.DateTime, default=datetime.utcnow)

    produtos = db.relationship('ProdutoEspecial', backref='evento', lazy=True, cascade='all, delete-orphan')

    @property
    def no_periodo(self):
        """Verifica se o evento está dentro do período agendado."""
        agora = datetime.now()
        if self.data_inicio and agora < self.data_inicio:
            return False
        if self.data_fim and agora > self.data_fim:
            return False
        return True

    @property
    def deve_aparecer(self):
        return self.ativo and self.no_periodo

    @property
    def status_agendamento(self):
        """Retorna o status visual para o admin."""
        if not self.ativo:
            return 'inativo'
        agora = datetime.now()
        if self.data_inicio and agora < self.data_inicio:
            return 'programado'
        if self.data_fim and agora > self.data_fim:
            return 'encerrado'
        return 'ativo'

    def __repr__(self):
        return f"<EventoEspecial {self.nome}>"


class ProdutoEspecial(db.Model):
    __tablename__ = "produtos_especiais"
    id           = db.Column(db.Integer, primary_key=True)
    evento_id    = db.Column(db.Integer, db.ForeignKey('eventos_especiais.id'), nullable=False)
    name         = db.Column(db.String(200), nullable=False)
    resumo       = db.Column(db.String(400), nullable=True)
    description  = db.Column(db.String(800), nullable=False)
    price        = db.Column(db.Numeric(10, 2), nullable=False)
    category          = db.Column(db.String(100), nullable=True, default='geral')
    image_url         = db.Column(db.String(300), nullable=True)
    mostrar           = db.Column(db.Boolean, default=True)
    estoque           = db.Column(db.Integer, default=0, nullable=False)
    estoque_minimo    = db.Column(db.Integer, default=5, nullable=False)
    quantidade_minima = db.Column(db.Integer, default=1, nullable=False)
    quantidade_maxima = db.Column(db.Integer, nullable=True)
    created_at     = db.Column(db.DateTime, default=datetime.utcnow)

    @property
    def status_estoque(self):
        if self.estoque == 0:       return 'zerado'
        if self.estoque <= self.estoque_minimo: return 'baixo'
        return 'ok'

    def __repr__(self):
        return f"<ProdutoEspecial {self.name}>"

class MovimentacaoEstoque(db.Model):
    __tablename__ = "movimentacoes_estoque"
    id               = db.Column(db.Integer, primary_key=True)
    produto_id       = db.Column(db.Integer, db.ForeignKey('products.id'),          nullable=True)
    kit_id           = db.Column(db.Integer, db.ForeignKey('kits.id'),              nullable=True)
    especial_id      = db.Column(db.Integer, db.ForeignKey('produtos_especiais.id'), nullable=True)
    tipo             = db.Column(db.String(10), nullable=False)  # 'entrada' | 'saida'
    quantidade       = db.Column(db.Integer, nullable=False)
    motivo           = db.Column(db.String(200), nullable=True)
    estoque_anterior = db.Column(db.Integer, nullable=False)
    estoque_novo     = db.Column(db.Integer, nullable=False)
    created_at       = db.Column(db.DateTime, default=datetime.utcnow)
    produto  = db.relationship('Product',        backref='movimentacoes')
    kit      = db.relationship('Kit',            backref='movimentacoes')
    especial = db.relationship('ProdutoEspecial', backref='movimentacoes')

    def __repr__(self):
        return f"<Movimentacao {self.tipo} {self.quantidade} - {self.produto_id}>"


class CarrinhoItem(db.Model):
    __tablename__ = "carrinho_itens"
    id          = db.Column(db.Integer, primary_key=True)
    user_id     = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    produto_id  = db.Column(db.Integer, db.ForeignKey('products.id'), nullable=True)
    kit_id      = db.Column(db.Integer, db.ForeignKey('kits.id'), nullable=True)
    especial_id = db.Column(db.Integer, db.ForeignKey('produtos_especiais.id'), nullable=True)
    quantidade  = db.Column(db.Integer, default=1, nullable=False)
    notas_corp  = db.Column(db.Text, nullable=True)
    created_at  = db.Column(db.DateTime, default=datetime.utcnow)

    # relacionamentos
    user     = db.relationship('User', backref='carrinho_itens')
    produto  = db.relationship('Product', backref='carrinho_itens')
    kit      = db.relationship('Kit', backref='carrinho_itens')
    especial = db.relationship('ProdutoEspecial', backref='carrinho_itens')

    @property
    def nome(self):
        if self.produto:
            return self.produto.name
        if self.kit:
            return self.kit.name
        if self.especial:
            return self.especial.name
        return 'Produto'

    @property
    def preco_unit(self):
        if self.produto:
            return float(self.produto.price)
        if self.kit:
            return float(self.kit.total_price)
        if self.especial:
            return float(self.especial.price)
        return 0.0

    @property
    def imagem(self):
        if self.produto:
            return self.produto.image_url
        if self.kit:
            return self.kit.image_url
        if self.especial:
            return self.especial.image_url
        return None

    @property
    def quantidade_minima(self):
        if self.produto:
            return self.produto.quantidade_minima
        if self.especial:
            return self.especial.quantidade_minima
        return 1

    @property
    def quantidade_maxima(self):
        if self.produto:
            return self.produto.quantidade_maxima
        if self.especial:
            return self.especial.quantidade_maxima
        return None

    @property
    def subtotal(self):
        return self.preco_unit * self.quantidade

    def __repr__(self):
        return f"<CarrinhoItem {self.nome} x{self.quantidade}>"




class Favorito(db.Model):
    __tablename__ = "favoritos"
    id          = db.Column(db.Integer, primary_key=True)
    user_id     = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    produto_id  = db.Column(db.Integer, db.ForeignKey('products.id'),          nullable=True)
    kit_id      = db.Column(db.Integer, db.ForeignKey('kits.id'),              nullable=True)
    especial_id = db.Column(db.Integer, db.ForeignKey('produtos_especiais.id'), nullable=True)
    created_at  = db.Column(db.DateTime, default=datetime.utcnow)

    user    = db.relationship('User',            backref='favoritos')
    produto = db.relationship('Product',         backref='favoritos')
    kit     = db.relationship('Kit',             backref='favoritos')
    especial= db.relationship('ProdutoEspecial', backref='favoritos')

    def __repr__(self):
        return f"<Favorito user={self.user_id}>"


class CarrosselItem(db.Model):
    __tablename__ = "carrossel_itens"
    id         = db.Column(db.Integer, primary_key=True)
    titulo     = db.Column(db.String(200), nullable=True)
    subtitulo  = db.Column(db.String(300), nullable=True)
    imagem     = db.Column(db.String(300), nullable=False)  # nome do arquivo
    ordem      = db.Column(db.Integer, default=0)
    ativo      = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    def __repr__(self):
        return f"<CarrosselItem {self.titulo}>"


class SiteConfig(db.Model):
    __tablename__ = "site_config"
    id               = db.Column(db.Integer, primary_key=True)
    # Colors
    color_primary    = db.Column(db.String(20), default='#5B6D3D')
    color_secondary  = db.Column(db.String(20), default='#D67155')
    color_accent     = db.Column(db.String(20), default='#F3B651')
    color_dark       = db.Column(db.String(20), default='#932E50')
    color_bg         = db.Column(db.String(20), default='#FAF9F6')
    color_text       = db.Column(db.String(20), default='#2B2B2B')
    color_text_light = db.Column(db.String(20), default='#6B6B6B')
    auth_bg_color1   = db.Column(db.String(20), default='#e8eed8')
    auth_bg_color2   = db.Column(db.String(20), default='#8fa05a')
    # Typography
    font_title   = db.Column(db.String(100), default='Playfair Display')
    font_body    = db.Column(db.String(100), default='Nunito')
    font_size    = db.Column(db.String(10), default='16')
    title_weight = db.Column(db.String(10), default='700')
    body_weight  = db.Column(db.String(10), default='400')
    # Layout
    layout_mode   = db.Column(db.String(20), default='spacious')
    layout_width  = db.Column(db.String(20), default='centered')
    card_columns  = db.Column(db.Integer,    default=3)
    card_gap      = db.Column(db.Integer,    default=20)
    show_carousel = db.Column(db.Boolean,    default=True)
    # Components
    btn_radius  = db.Column(db.String(10), default='12px')
    card_shadow = db.Column(db.String(10), default='medium')
    navbar_fixed = db.Column(db.Boolean, default=True)
    # Animations
    anim_enabled     = db.Column(db.Boolean, default=True)
    anim_intensity   = db.Column(db.String(10), default='medium')
    anim_duration    = db.Column(db.Integer,    default=220)
    anim_hover_style = db.Column(db.String(20), default='lift')
    # Identity
    site_name   = db.Column(db.String(100), default='Doces da Fhê')
    logo_url    = db.Column(db.String(255), nullable=True)
    logo_height     = db.Column(db.Integer, default=100)
    logo_fit        = db.Column(db.String(20), default='contain')
    carousel_height = db.Column(db.Integer, default=340)
    card_img_height = db.Column(db.Integer, default=200)
    card_radius     = db.Column(db.String(10), default='16px')
    flash_success      = db.Column(db.String(20), default='#ffffff')
    flash_error        = db.Column(db.String(20), default='#f8d7da')
    flash_info         = db.Column(db.String(20), default='#ffffff')
    flash_success_text = db.Column(db.String(20), default='#155724')
    flash_error_text   = db.Column(db.String(20), default='#721c24')
    flash_info_text    = db.Column(db.String(20), default='#0c5460')
    new_badge_days  = db.Column(db.Integer, default=7)
    new_badge_ativo = db.Column(db.Boolean, default=True)
    new_badge_color = db.Column(db.String(20), default='#cc0000')
    # Blog colors
    blog_primary    = db.Column(db.String(20), default='#5B6D3D')
    blog_accent     = db.Column(db.String(20), default='#932E50')
    blog_bg         = db.Column(db.String(20), default='#f8fafc')
    blog_card_bg    = db.Column(db.String(20), default='#ffffff')
    blog_text       = db.Column(db.String(20), default='#1e293b')
    agenda_dias_arquivar = db.Column(db.Integer, default=30)
    updated_at      = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    def __repr__(self):
        return f"<SiteConfig {self.site_name}>"


class Pedido(db.Model):
    __tablename__ = "pedidos"
    id         = db.Column(db.Integer, primary_key=True)
    user_id    = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    tipo       = db.Column(db.String(20), nullable=False)   # 'buscar' | 'entrega'
    endereco   = db.Column(db.String(500), nullable=True)
    total      = db.Column(db.Numeric(10, 2), nullable=False)
    status          = db.Column(db.String(20), default='pendente', nullable=False)
    # pendente → confirmado → entregue  |  cancelado
    oculto_cliente  = db.Column(db.Boolean, default=False, nullable=False)
    created_at      = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    user  = db.relationship('User', backref='pedidos')
    itens = db.relationship('PedidoItem', backref='pedido', cascade='all, delete-orphan')

    def __repr__(self):
        return f"<Pedido #{self.id} {self.status}>"


class PedidoItem(db.Model):
    __tablename__ = "pedido_itens"
    id         = db.Column(db.Integer, primary_key=True)
    pedido_id  = db.Column(db.Integer, db.ForeignKey('pedidos.id'), nullable=False)
    nome       = db.Column(db.String(200), nullable=False)
    quantidade = db.Column(db.Integer, nullable=False)
    preco_unit = db.Column(db.Numeric(10, 2), nullable=False)
    notas_corp = db.Column(db.Text, nullable=True)

    @property
    def subtotal(self):
        return float(self.preco_unit) * self.quantidade

    def __repr__(self):
        return f"<PedidoItem {self.nome} x{self.quantidade}>"


class Brinde(db.Model):
    __tablename__ = "brindes"
    id                = db.Column(db.Integer, primary_key=True)
    valor_minimo      = db.Column(db.Numeric(10, 2), nullable=False)
    produto_nome      = db.Column(db.String(200), nullable=False)
    quantidade_brinde = db.Column(db.Integer, default=1, nullable=False)
    ativo             = db.Column(db.Boolean, default=True)

    def __repr__(self):
        return f"<Brinde {self.produto_nome} a partir de R${self.valor_minimo}>"


class Promocao(db.Model):
    __tablename__ = "promocoes"
    id           = db.Column(db.Integer, primary_key=True)
    nome         = db.Column(db.String(200), nullable=False)
    descricao    = db.Column(db.String(500), default='')
    tipo         = db.Column(db.String(20), nullable=False)   # 'percentual' | 'fixo' | 'leve_pague'
    valor        = db.Column(db.Numeric(10, 2), nullable=False, default=0)
    valor_minimo = db.Column(db.Numeric(10, 2), default=0)
    # campos para tipo leve_pague
    leve         = db.Column(db.Integer, nullable=True)   # ex: 2
    pague        = db.Column(db.Integer, nullable=True)   # ex: 1
    produto_id   = db.Column(db.Integer, db.ForeignKey('products.id'), nullable=True)
    ativo            = db.Column(db.Boolean, default=True)
    mostrar_na_faixa = db.Column(db.Boolean, default=False)
    criado_em        = db.Column(db.DateTime, default=datetime.utcnow)

    produto = db.relationship('Product', backref='promocoes_leve_pague', lazy=True)

    def desconto_para(self, total):
        if float(self.valor_minimo) > total:
            return 0.0
        if self.tipo == 'percentual':
            return round(float(total) * float(self.valor) / 100, 2)
        return min(float(self.valor), float(total))

    def __repr__(self):
        return f"<Promocao {self.nome}>"


class Avaliacao(db.Model):
    __tablename__ = "avaliacoes"
    id          = db.Column(db.Integer, primary_key=True)
    user_id     = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    produto_id  = db.Column(db.Integer, db.ForeignKey('products.id'), nullable=True)
    kit_id      = db.Column(db.Integer, db.ForeignKey('kits.id'), nullable=True)
    especial_id = db.Column(db.Integer, db.ForeignKey('produtos_especiais.id'), nullable=True)
    estrelas    = db.Column(db.Integer, nullable=False)
    comentario  = db.Column(db.String(1000), nullable=True)
    created_at  = db.Column(db.DateTime, default=datetime.utcnow)

    user    = db.relationship('User', backref='avaliacoes')
    produto = db.relationship('Product', backref='avaliacoes')
    kit     = db.relationship('Kit', backref='avaliacoes')
    especial = db.relationship('ProdutoEspecial', backref='avaliacoes')

    @property
    def media(self):
        avs = Avaliacao.query.filter_by(produto_id=self.produto_id).all() if self.produto_id else []
        return round(sum(a.estrelas for a in avs) / len(avs), 1) if avs else 0

    def __repr__(self):
        return f"<Avaliacao {self.estrelas}★ by user {self.user_id}>"


class ConfigCorporativo(db.Model):
    __tablename__ = "config_corporativo"
    id          = db.Column(db.Integer, primary_key=True)
    prazo_texto = db.Column(db.String(200), default="15 dias úteis")
    informacoes = db.Column(db.Text, default="")
    cor_hero_ini  = db.Column(db.String(20), default="#1e293b")
    cor_hero_fim  = db.Column(db.String(20), default="#334155")
    cor_destaque  = db.Column(db.String(20), default="#5B6D3D")
    updated_at  = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    def __repr__(self):
        return f"<ConfigCorporativo prazo={self.prazo_texto}>"


class PedidoCorporativo(db.Model):
    __tablename__ = "pedidos_corporativos"
    id             = db.Column(db.Integer, primary_key=True)
    user_id        = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)
    nome           = db.Column(db.String(200), nullable=False)
    email          = db.Column(db.String(200), nullable=False)
    telefone       = db.Column(db.String(50), nullable=False)
    tipo           = db.Column(db.String(20), default='personalizar')  # 'personalizar' | 'solicitar'
    produto_id     = db.Column(db.Integer, db.ForeignKey('products.id'), nullable=True)
    produto_nome   = db.Column(db.String(200), nullable=True)
    quantidade     = db.Column(db.Integer, nullable=True)
    personalizacao = db.Column(db.Text, nullable=True)
    logo_url       = db.Column(db.String(300), nullable=True)
    sabor          = db.Column(db.String(200), nullable=True)
    cor_fita       = db.Column(db.String(100), nullable=True)
    modelo_tag     = db.Column(db.String(30), nullable=True)   # quadrada | redonda | retangular
    frase_tag      = db.Column(db.String(300), nullable=True)
    data_desejada  = db.Column(db.String(100), nullable=True)
    observacoes    = db.Column(db.Text, nullable=True)
    valor           = db.Column(db.Numeric(10, 2), nullable=True)
    status          = db.Column(db.String(20), default='novo')  # novo | em_andamento | concluido | cancelado
    oculto_cliente  = db.Column(db.Boolean, default=False, nullable=False)
    created_at      = db.Column(db.DateTime, default=datetime.utcnow)

    produto = db.relationship('Product', backref='pedidos_corporativos', lazy=True)

    def __repr__(self):
        return f"<PedidoCorporativo #{self.id} {self.tipo} {self.status}>"


# ─────────────────────────────────────
# BLOG MODELS
# ─────────────────────────────────────

class BlogCategoria(db.Model):
    __tablename__ = 'blog_categorias'
    id = db.Column(db.Integer, primary_key=True)
    nome = db.Column(db.String(100), unique=True, nullable=False)
    slug = db.Column(db.String(100), unique=True, nullable=False)
    descricao = db.Column(db.String(300), nullable=True)
    cor = db.Column(db.String(20), default='#5B6D3D')

    def __repr__(self):
        return f"<BlogCategoria {self.nome}>"


class BlogTag(db.Model):
    __tablename__ = 'blog_tags'
    id = db.Column(db.Integer, primary_key=True)
    nome = db.Column(db.String(50), unique=True, nullable=False)
    slug = db.Column(db.String(50), unique=True, nullable=False)

    def __repr__(self):
        return f"<BlogTag {self.nome}>"


blog_post_tags = db.Table(
    'blog_post_tags',
    db.Column('post_id', db.Integer, db.ForeignKey('blog_posts.id')),
    db.Column('tag_id', db.Integer, db.ForeignKey('blog_tags.id'))
)


class BlogPost(db.Model):
    __tablename__ = 'blog_posts'
    id = db.Column(db.Integer, primary_key=True)
    titulo = db.Column(db.String(300), nullable=False)
    slug = db.Column(db.String(300), unique=True, nullable=False)
    resumo = db.Column(db.String(500), nullable=True)
    conteudo = db.Column(db.Text, nullable=False, default='')
    capa_url = db.Column(db.String(300), nullable=True)
    status = db.Column(db.String(20), default='rascunho')  # rascunho | publicado
    visualizacoes = db.Column(db.Integer, default=0)
    tempo_leitura = db.Column(db.Integer, default=1)  # minutos
    meta_titulo = db.Column(db.String(200), nullable=True)
    meta_descricao = db.Column(db.String(300), nullable=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    categoria_id = db.Column(db.Integer, db.ForeignKey('blog_categorias.id'), nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    autor = db.relationship('User', backref='blog_posts')
    categoria = db.relationship('BlogCategoria', backref='posts')
    tags = db.relationship('BlogTag', secondary=blog_post_tags, backref='posts')

    def __repr__(self):
        return f"<BlogPost {self.titulo[:40]}>"


class BlogComentario(db.Model):
    __tablename__ = 'blog_comentarios'
    id = db.Column(db.Integer, primary_key=True)
    conteudo = db.Column(db.Text, nullable=False)
    post_id = db.Column(db.Integer, db.ForeignKey('blog_posts.id'), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    parent_id = db.Column(db.Integer, db.ForeignKey('blog_comentarios.id'), nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    autor = db.relationship('User', backref='comentarios')
    respostas = db.relationship('BlogComentario',
                                backref=db.backref('parent', remote_side='BlogComentario.id'),
                                lazy='dynamic')

    def __repr__(self):
        return f"<BlogComentario post={self.post_id} user={self.user_id}>"


class BlogCurtida(db.Model):
    __tablename__ = 'blog_curtidas'
    id = db.Column(db.Integer, primary_key=True)
    post_id = db.Column(db.Integer, db.ForeignKey('blog_posts.id'), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    __table_args__ = (db.UniqueConstraint('post_id', 'user_id'),)

    def __repr__(self):
        return f"<BlogCurtida post={self.post_id} user={self.user_id}>"


class BlogSalvo(db.Model):
    __tablename__ = 'blog_salvos'
    id = db.Column(db.Integer, primary_key=True)
    post_id = db.Column(db.Integer, db.ForeignKey('blog_posts.id'), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    __table_args__ = (db.UniqueConstraint('post_id', 'user_id'),)

    def __repr__(self):
        return f"<BlogSalvo post={self.post_id} user={self.user_id}>"


class BlogNewsletter(db.Model):
    __tablename__ = 'blog_newsletter'
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(200), unique=True, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    def __repr__(self):
        return f"<BlogNewsletter {self.email}>"


class UserPerfil(db.Model):
    __tablename__ = 'user_perfis'
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), unique=True, nullable=False)
    bio = db.Column(db.Text, nullable=True)
    avatar_url = db.Column(db.String(300), nullable=True)
    banner_url = db.Column(db.String(300), nullable=True)
    username = db.Column(db.String(50), unique=True, nullable=True)
    email_contato = db.Column(db.String(200), nullable=True)
    telefone = db.Column(db.String(30), nullable=True)
    cidade = db.Column(db.String(100), nullable=True)
    profissao = db.Column(db.String(100), nullable=True)
    site = db.Column(db.String(200), nullable=True)
    instagram = db.Column(db.String(100), nullable=True)
    tiktok = db.Column(db.String(100), nullable=True)
    facebook = db.Column(db.String(100), nullable=True)
    linkedin = db.Column(db.String(100), nullable=True)
    threads = db.Column(db.String(100), nullable=True)
    usuario = db.relationship('User', backref=db.backref('perfil', uselist=False))

    def __repr__(self):
        return f"<UserPerfil user={self.user_id}>"


class DesignPalette(db.Model):
    __tablename__ = 'design_palettes'
    id         = db.Column(db.Integer, primary_key=True)
    nome       = db.Column(db.String(100), nullable=False)
    cores      = db.Column(db.Text, nullable=False)  # JSON blob of color fields
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    def __repr__(self):
        return f"<DesignPalette {self.nome}>"


class AgendaEvento(db.Model):
    __tablename__ = 'agenda_eventos'
    id          = db.Column(db.Integer, primary_key=True)
    titulo      = db.Column(db.String(150), nullable=False)
    descricao   = db.Column(db.Text, nullable=True)
    local       = db.Column(db.String(200), nullable=True)
    data_inicio = db.Column(db.DateTime, nullable=False)
    data_fim    = db.Column(db.DateTime, nullable=True)
    cor         = db.Column(db.String(7), default='#5B6D3D')
    created_at  = db.Column(db.DateTime, default=datetime.utcnow)

    @property
    def passou(self):
        fim = self.data_fim or self.data_inicio
        return fim < datetime.now()

    def __repr__(self):
        return f"<AgendaEvento {self.titulo}>"
