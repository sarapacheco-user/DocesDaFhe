from app import app, db
import sqlite3

with app.app_context():
    conn = sqlite3.connect('instance/users.db')
    cursor = conn.cursor()
    
    # Add reset_token column
    try:
        cursor.execute('ALTER TABLE users ADD COLUMN reset_token VARCHAR(100) UNIQUE')
        print("Added reset_token column")
    except sqlite3.OperationalError:
        print("reset_token column already exists")
    
    # Add reset_token_expiry column
    try:
        cursor.execute('ALTER TABLE users ADD COLUMN reset_token_expiry DATETIME')
        print("Added reset_token_expiry column")
    except sqlite3.OperationalError:
        print("reset_token_expiry column already exists")
    
    conn.commit()
    conn.close()
    print("Database updated successfully!")