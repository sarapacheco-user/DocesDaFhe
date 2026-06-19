# 🍬 DocesDaFhe

Aplicação web Flask para gerenciamento de produtos e kits de doces.

---

## 📁 Estrutura do Projeto

```
DocesDaFhe/
├── instance/
├── templates/
│   ├── kits/
│   │   ├── create.html
│   │   ├── edit.html
│   │   ├── list.html
│   │   ├── manage_products.html
│   │   └── view.html
│   ├── base.html
│   ├── change_password.html
│   ├── dashboard.html
│   ├── email_reset_password.html
│   ├── forgot_password.html
│   ├── login.html
│   ├── product_form.html
│   ├── products.html
│   ├── reset_password.html
│   └── signup.html
├── venv/
├── app.py
├── models.py
├── create_admin.py
├── update_db_password_reset.py
├── requirements.txt
├── .env
└── .gitignore
```

---

## 📂 Pastas

| Pasta | Descrição |
|-------|-----------|
| `instance/` | Instância do banco de dados SQLite. **Não edite manualmente** — é criada automaticamente ao rodar `app.py`. Contém os dados persistidos da aplicação. |
| `templates/` | Templates HTML das telas do site. Toda nova tela deve ser adicionada aqui. |
| `templates/kits/` | Sub-conjunto de telas relacionadas à funcionalidade de **kits**. |
| `venv/` | Ambiente virtual Python com as dependências instaladas. |

---

## 📄 Arquivos

### Templates — `templates/`

| Arquivo | Descrição |
|---------|-----------|
| `base.html` | Layout base com a **Navbar**. Todas as outras telas herdam deste template. |
| `dashboard.html` | Tela inicial após o login. |
| `login.html` | Tela de login. |
| `signup.html` | Tela de cadastro de novo usuário. |
| `change_password.html` | Tela para alteração de senha (usuário já autenticado). |
| `forgot_password.html` | Tela para usuários que esqueceram a senha. |
| `email_reset_password.html` | Tela de envio de e-mail para recuperação de senha. |
| `reset_password.html` | Tela de redefinição de senha via token. |
| `products.html` | Tela de listagem dos produtos cadastrados. |
| `product_form.html` | Formulário de criação/edição de produto. |

### Templates — `templates/kits/`

| Arquivo | Descrição |
|---------|-----------|
| `list.html` | Listagem de todos os kits cadastrados. |
| `create.html` | Formulário de criação de novo kit. |
| `edit.html` | Formulário de edição de um kit existente. |
| `view.html` | Visualização detalhada de um kit. |
| `manage_products.html` | Tela para gerenciar os produtos associados a um kit. |

### Arquivos raiz

| Arquivo | Descrição |
|---------|-----------|
| `app.py` | Ponto de entrada da aplicação. Contém as rotas e a lógica principal do Flask. |
| `models.py` | Definição dos modelos do banco de dados (SQLAlchemy). |
| `create_admin.py` | Script para criação do usuário administrador no banco de dados. |
| `update_db_password_reset.py` | Script de migração para atualização do campo de reset de senha no banco. |
| `requirements.txt` | Lista de dependências Python do projeto. |
| `.env` | Variáveis de ambiente (chaves de API, configurações sensíveis). **Nunca versionar.** |
| `.gitignore` | Arquivos e pastas ignorados pelo Git (ex: `venv/`, `instance/`, `.env`). |

---

## 🚀 Como rodar localmente

```bash
# 1. Clone o repositório
git clone <url-do-repo>
cd DocesDaFhe

# 2. Crie e ative o ambiente virtual
python -m venv venv
source venv/bin/activate  # Linux/Mac
venv\Scripts\activate     # Windows

# 3. Instale as dependências
pip install -r requirements.txt

# 4. Configure as variáveis de ambiente
cp .env.example .env  # edite com seus valores

# 5. Crie o admin inicial
python create_admin.py

# 6. Rode a aplicação
python app.py
```

O banco de dados (`instance/`) será criado automaticamente na primeira execução.

---

## 🛠️ Tecnologias

- **Python** + **Flask** — backend e rotas
- **SQLAlchemy** — ORM para o banco de dados
- **SQLite** — banco de dados local (arquivo em `instance/`)
- **Jinja2** — templating HTML
