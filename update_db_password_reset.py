# Script de migração manual: adiciona as colunas de recuperação de senha à tabela users.
# Execute uma única vez com: python3 update_db_password_reset.py
# As colunas já são criadas automaticamente pelo app.py via db.create_all(),
# mas este script serve como fallback para bancos criados antes dessa feature.

from app import app, db
import sqlite3

with app.app_context():
    conn = sqlite3.connect('instance/users.db')
    cursor = conn.cursor()

    # Adiciona coluna para armazenar o token de redefinição de senha
    try:
        cursor.execute('ALTER TABLE users ADD COLUMN reset_token VARCHAR(100) UNIQUE')
        print("Added reset_token column")
    except sqlite3.OperationalError:
        print("reset_token column already exists")

    # Adiciona coluna para armazenar a data de expiração do token (24 horas)
    try:
        cursor.execute('ALTER TABLE users ADD COLUMN reset_token_expiry DATETIME')
        print("Added reset_token_expiry column")
    except sqlite3.OperationalError:
        print("reset_token_expiry column already exists")

    conn.commit()
    conn.close()
    print("Banco de dados atualizado com sucesso!")
    