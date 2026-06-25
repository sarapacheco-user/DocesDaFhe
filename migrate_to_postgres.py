# Script de migração única: copia todos os dados do SQLite local para o PostgreSQL.
# Uso: python3 migrate_to_postgres.py "postgresql://usuario:senha@host/banco"
#
# 1. Cria as tabelas no Postgres (a partir dos models atuais)
# 2. Copia todas as linhas de cada tabela do SQLite para o Postgres, na ordem
#    correta de dependência (chaves estrangeiras)
# 3. Corrige as sequences (auto-incremento) do Postgres para continuar a
#    partir do maior ID já existente

import sys
from sqlalchemy import create_engine, MetaData, select, text

if len(sys.argv) != 2:
    print('Uso: python3 migrate_to_postgres.py "postgresql://usuario:senha@host/banco"')
    sys.exit(1)

postgres_url = sys.argv[1]
if postgres_url.startswith('postgres://'):
    postgres_url = postgres_url.replace('postgres://', 'postgresql://', 1)

sqlite_url = 'sqlite:///instance/users.db'

src_engine = create_engine(sqlite_url)
dst_engine = create_engine(postgres_url)

print('Criando tabelas no Postgres (a partir dos models atuais)...')
from app import db
db.metadata.create_all(bind=dst_engine)
print('Tabelas criadas/confirmadas no Postgres.\n')

src_metadata = MetaData()
src_metadata.reflect(bind=src_engine)

dst_metadata = MetaData()
dst_metadata.reflect(bind=dst_engine)

with src_engine.connect() as src_conn, dst_engine.connect() as dst_conn:
    for table in src_metadata.sorted_tables:
        dst_table = dst_metadata.tables.get(table.name)
        if dst_table is None:
            print(f'{table.name}: não existe no esquema atual, pulando')
            continue
        # ignora colunas antigas que existem no SQLite mas não no esquema atual
        colunas_validas = set(dst_table.columns.keys())
        rows = src_conn.execute(select(table)).fetchall()
        if not rows:
            print(f'{table.name}: vazio, pulando')
            continue
        linhas = [
            {k: v for k, v in dict(row._mapping).items() if k in colunas_validas}
            for row in rows
        ]
        dst_conn.execute(dst_table.delete())
        dst_conn.execute(dst_table.insert(), linhas)
        dst_conn.commit()
        print(f'{table.name}: {len(rows)} linha(s) copiada(s)')

    print('\nAjustando sequences de auto-incremento...')
    for table in dst_metadata.sorted_tables:
        if 'id' in table.columns:
            dst_conn.execute(text(
                f"SELECT setval(pg_get_serial_sequence('{table.name}', 'id'), "
                f"COALESCE((SELECT MAX(id) FROM {table.name}), 1))"
            ))
    dst_conn.commit()

print('\nMigração concluída com sucesso!')
