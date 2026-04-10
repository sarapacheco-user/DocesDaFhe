from flask_sqlalchemy import SQLAlchemy
from flask_login import UserMixin
from datetime import datetime
db = SQLAlchemy()



class User(db.Model, UserMixin):
    __tablename__ = "users"

    id = db.Column(db.Integer, primary_key=True)

    # AUTH
    email = db.Column(db.String(120), unique=True, nullable=False, index=True)
    password = db.Column(db.String(200), nullable=False)

    # PERSONAL DATA
    phone = db.Column(db.String(20), nullable=False)
    cep = db.Column(db.String(8), nullable=False)
    # CHECA SE É A ADM
    is_admin = db.Column(db.Boolean, default=False, nullable=False)
    # PASSWORD RESET FIELDS
    reset_token = db.Column(db.String(100), unique=True, nullable=True)
    reset_token_expiry = db.Column(db.DateTime, nullable=True)


    # METADATA (boa prática)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    def __repr__(self):
        return f"<User {self.email}>"



class Product(db.Model):
    __tablename__ = "products"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(200), unique=True, nullable=False, index=True)
    description = db.Column(db.String(800), nullable=False)
    image_url = db.Column(db.String(300))  # This field exists
    price = db.Column(db.Numeric(10, 2), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    def __repr__(self):
        return f"<Product {self.name}>"

from datetime import datetime

class Kit(db.Model):
    __tablename__ = 'kits'
    
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(200), nullable=False)
    description = db.Column(db.Text, nullable=True)
    created_by = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    is_admin_kit = db.Column(db.Boolean, default=False)   # True = admin kit
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    image_url = db.Column(db.String(500), nullable=True)   # <-- adiciona essa linha
    # Relacionamentos
    products = db.relationship('KitProduct', backref='kit', cascade='all, delete-orphan')
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
    product_id = db.Column(db.Integer, db.ForeignKey('products.id'), primary_key=True)
    quantity = db.Column(db.Integer, default=1)
    added_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    # Relacionamentos
    product = db.relationship('Product')