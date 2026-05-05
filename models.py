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

    def __repr__(self):
        return f"<User {self.email}>"


class Product(db.Model):
    __tablename__ = "products"
    id          = db.Column(db.Integer, primary_key=True)
    name        = db.Column(db.String(200), unique=True, nullable=False, index=True)
    description = db.Column(db.String(800), nullable=False)
    image_url   = db.Column(db.String(300))
    price       = db.Column(db.Numeric(10, 2), nullable=False)
    category    = db.Column(db.String(100), nullable=True, default='geral')  # ✅ NOVO
    ativo       = db.Column(db.Boolean, default=True, nullable=False)
    created_at  = db.Column(db.DateTime, default=datetime.utcnow)

    def __repr__(self):
        return f"<Product {self.name}>"


class Kit(db.Model):
    __tablename__ = 'kits'

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(200), nullable=False)
    description = db.Column(db.Text, nullable=True)
    created_by = db.Column(
        db.Integer, db.ForeignKey('users.id'), nullable=False)
    is_admin_kit = db.Column(db.Boolean, default=False)   # True = admin kit
    ativo = db.Column(db.Boolean, default=True, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(
        db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    image_url = db.Column(db.String(500), nullable=True)   # <-- add this line
    # Relationships
    products = db.relationship(
        'KitProduct', backref='kit', cascade='all, delete-orphan')
    creator = db.relationship('User', backref='kits')

    @property
    def total_price(self):
        """Calculate total price of all products in the kit."""
        return sum(kp.product.price * kp.quantity for kp in self.products)

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

# Adicione esses modelos no seu models.py

class EventoEspecial(db.Model):
    __tablename__ = "eventos_especiais"
    id         = db.Column(db.Integer, primary_key=True)
    nome       = db.Column(db.String(100), nullable=False, unique=True)  # ex: "Páscoa 2026"
    descricao  = db.Column(db.String(300), nullable=True)
    ativo      = db.Column(db.Boolean, default=True)   # mostrar/não mostrar na loja
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    # relacionamento com produtos especiais
    produtos   = db.relationship('ProdutoEspecial', backref='evento', lazy=True, cascade='all, delete-orphan')

    def __repr__(self):
        return f"<EventoEspecial {self.nome}>"


class ProdutoEspecial(db.Model):
    __tablename__ = "produtos_especiais"
    id           = db.Column(db.Integer, primary_key=True)
    evento_id    = db.Column(db.Integer, db.ForeignKey('eventos_especiais.id'), nullable=False)
    name         = db.Column(db.String(200), nullable=False)
    description  = db.Column(db.String(800), nullable=False)
    price        = db.Column(db.Numeric(10, 2), nullable=False)
    category     = db.Column(db.String(100), nullable=True, default='geral')
    image_url    = db.Column(db.String(300), nullable=True)
    mostrar      = db.Column(db.Boolean, default=True)   # mostrar/não mostrar na loja
    created_at   = db.Column(db.DateTime, default=datetime.utcnow)

    def __repr__(self):
        return f"<ProdutoEspecial {self.name}>"
    
    # Adicione esses modelos no seu models.py

class CarrinhoItem(db.Model):
    __tablename__ = "carrinho_itens"
    id          = db.Column(db.Integer, primary_key=True)
    user_id     = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    produto_id  = db.Column(db.Integer, db.ForeignKey('products.id'), nullable=True)
    kit_id      = db.Column(db.Integer, db.ForeignKey('kits.id'), nullable=True)
    especial_id = db.Column(db.Integer, db.ForeignKey('produtos_especiais.id'), nullable=True)
    quantidade  = db.Column(db.Integer, default=1, nullable=False)
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
    # Typography
    font_title   = db.Column(db.String(100), default='Playfair Display')
    font_body    = db.Column(db.String(100), default='Nunito')
    font_size    = db.Column(db.String(10), default='16')
    title_weight = db.Column(db.String(10), default='700')
    body_weight  = db.Column(db.String(10), default='400')
    # Layout
    layout_mode  = db.Column(db.String(20), default='spacious')
    layout_width = db.Column(db.String(20), default='centered')
    # Components
    btn_radius  = db.Column(db.String(10), default='12px')
    card_shadow = db.Column(db.String(10), default='medium')
    navbar_fixed = db.Column(db.Boolean, default=True)
    # Animations
    anim_enabled   = db.Column(db.Boolean, default=True)
    anim_intensity = db.Column(db.String(10), default='medium')
    # Identity
    site_name   = db.Column(db.String(100), default='Doces da Fhê')
    logo_url    = db.Column(db.String(255), nullable=True)
    logo_height     = db.Column(db.Integer, default=100)
    logo_fit        = db.Column(db.String(20), default='contain')
    carousel_height = db.Column(db.Integer, default=340)
    card_img_height = db.Column(db.Integer, default=200)
    card_radius     = db.Column(db.String(10), default='16px')
    flash_success   = db.Column(db.String(20), default='#d4edda')
    flash_error     = db.Column(db.String(20), default='#f8d7da')
    flash_info      = db.Column(db.String(20), default='#ffffff')
    updated_at      = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    def __repr__(self):
        return f"<SiteConfig {self.site_name}>"
