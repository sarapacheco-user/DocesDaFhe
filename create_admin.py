# Script utilitário para criar o usuário administrador padrão no banco de dados.
# Execute uma única vez com: python3 create_admin.py
# Após criar o admin, troque a senha pelo painel de administração.

from app import app, db
from models import User
import bcrypt

with app.app_context():
    # Verifica se o admin já existe para não duplicar
    admin = User.query.filter_by(email="adm@example.com").first()

    if not admin:
        # Gera o hash seguro da senha antes de salvar no banco
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
        print("Usuário administrador criado com sucesso!")
        print("Email: adm@example.com")
        print("Password: adm")
    else:
        # Informa que o admin já está cadastrado sem sobrescrever
        print("Usuário administrador já existe!")
        print(f"Email: {admin.email}")
        print(f"Is Admin: {admin.is_admin}")