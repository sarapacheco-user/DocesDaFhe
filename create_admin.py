from app import app, db
from models import User
import bcrypt

with app.app_context():
    # Check if admin exists
    admin = User.query.filter_by(email="adm@example.com").first()
    
    if not admin:
        # Create admin user
        hashed_pw = bcrypt.hashpw("adm".encode('utf-8'), bcrypt.gensalt())
        
        admin = User(
            email="adm@example.com",
            password=hashed_pw.decode('utf-8'),
            phone="11999999999",
            cep="70673040",
            is_admin=True
        )
        
        db.session.add(admin)
        db.session.commit()
<<<<<<< HEAD
        print("Usuário administrador criado com sucesso!")
        print("Email: adm@example.com")
        print("Password: adm")
    else:
        print("Usuário administrador já existe!")
=======
        print("Admin user created successfully!")
        print("Email: adm@example.com")
        print("Password: adm")
    else:
        print("Admin user already exists!")
>>>>>>> 4a6ae9744af7949d4d8fc2a42b247b9eba546b0c
        print(f"Email: {admin.email}")
        print(f"Is Admin: {admin.is_admin}")