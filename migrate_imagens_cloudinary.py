# Script de migração única: envia as imagens já existentes (armazenadas localmente)
# para o Cloudinary, e atualiza o banco de dados em produção (Postgres) com as
# novas URLs públicas.
#
# Uso: python3 migrate_imagens_cloudinary.py "postgresql://usuario:senha@host/banco"

import os
import sys
from sqlalchemy import create_engine, text

from dotenv import load_dotenv
load_dotenv()

import cloudinary
import cloudinary.uploader
cloudinary.config(secure=True)

if len(sys.argv) != 2:
    print('Uso: python3 migrate_imagens_cloudinary.py "postgresql://usuario:senha@host/banco"')
    sys.exit(1)

postgres_url = sys.argv[1]
if postgres_url.startswith('postgres://'):
    postgres_url = postgres_url.replace('postgres://', 'postgresql://', 1)

engine = create_engine(postgres_url)

# (tabela, campo, pasta_no_cloudinary, prefixo_do_caminho_local)
# prefixo_do_caminho_local=None significa que o campo já guarda o caminho relativo completo
TAREFAS = [
    ('products',            'image_url',  'produtos',          None),
    ('kits',                'image_url',  'kits',               None),
    ('produtos_especiais',  'image_url',  'especiais',          None),
    ('categoria_banners',   'imagem_url', 'banners_categoria',  None),
    ('site_config',         'logo_url',   'logo',               None),
    ('user_perfis',         'avatar_url', 'avatares',           None),
    ('user_perfis',         'banner_url', 'banners',            None),
    ('blog_posts',          'capa_url',   'blog',               None),
    ('item_fotos',          'url',        'fotos_extras',       None),
    ('pedidos_corporativos','logo_url',   'corporativo',        None),
    ('carrossel_itens',     'imagem',     'carrossel',          'uploads/carrossel/'),
]

total_enviadas = 0
total_erros = 0

with engine.connect() as conn:
    for tabela, campo, pasta, prefixo in TAREFAS:
        rows = conn.execute(text(f'SELECT id, {campo} FROM {tabela} WHERE {campo} IS NOT NULL')).fetchall()
        for row_id, valor in rows:
            if not valor or valor.startswith('http'):
                continue  # já migrado ou vazio

            caminho_local = os.path.join('static', prefixo + valor if prefixo else valor)
            if not os.path.exists(caminho_local):
                print(f'  [FALTANDO] {tabela}.{campo} id={row_id}: {caminho_local}')
                total_erros += 1
                continue

            try:
                resultado = cloudinary.uploader.upload(caminho_local, folder=f'docesdafhe/{pasta}')
                nova_url = resultado['secure_url']
                conn.execute(text(f'UPDATE {tabela} SET {campo} = :url WHERE id = :id'),
                             {'url': nova_url, 'id': row_id})
                conn.commit()
                total_enviadas += 1
                print(f'  OK {tabela}.{campo} id={row_id} -> {nova_url}')
            except Exception as e:
                print(f'  [ERRO] {tabela}.{campo} id={row_id}: {type(e).__name__}: {e}')
                total_erros += 1

print(f'\nMigração de imagens concluída: {total_enviadas} enviada(s), {total_erros} erro(s)/faltando.')
