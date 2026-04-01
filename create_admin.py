from app import app, db
from models import User
import bcrypt

with app.app_context():
    # Check if admin exists
    admin = User.query.filter_by(email="admin@example.com").first()
    
    if not admin:
        # Create admin user
        hashed_pw = bcrypt.hashpw("admin123".encode('utf-8'), bcrypt.gensalt())
        
        admin = User(
            email="admin@example.com",
            password=hashed_pw.decode('utf-8'),
            phone="11999999999",
            cep="12345678",
            is_admin=True
        )
        
        db.session.add(admin)
        db.session.commit()
        print("Admin user created successfully!")
        print("Email: admin@example.com")
        print("Password: admin123")
    else:
        print("Admin user already exists!")
        print(f"Email: {admin.email}")
        print(f"Is Admin: {admin.is_admin}")