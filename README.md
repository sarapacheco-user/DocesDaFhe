# DocesDaFhe

## Estrutura do Projeto

### Pastas
* **instance** *Aqui é a instancia do Banco de Dados,não precisa ser alterada automaticamente, ela é automaticamente criada quando se roda app.py. É literalmente o armazenamento dos dados atuais*
* **templates** *Aqui é o conjunto de html de telas para o site.Toda vez que preciso de uma nova tela, preciso adicionar aqui*
    * **kits** *Aqui é o conjunto de telas relacionadas funcionalidade de kits dentro do conjunto de telas*
* venv

### Arquivos
* **instance** *Aqui é a instancia do Banco de Dados,não precisa ser alterada automaticamente, ela é automaticamente criada quando se roda app.py. É literalmente o armazenamento dos dados atuais*
* **templates** *Aqui é o conjunto de html de telas para o site.Toda vez que preciso de uma nova tela, preciso adicionar aqui*
    * **kits** *Aqui é o conjunto de telas relacionadas funcionalidade de kits dentro do conjunto de telas*
            - **create.html** *Tela de criação de kit*
            - **edit.html**   *Tela de edição de kit*
            - **list.html**    *Tela de Listagem de todos os kits*
            - **manage_products.html** *Tela de edição dos produtos do kit*
            - **view.html** *Tela de visualização do kit em sí*
    * **base.html** *Contém o código da Navbar, é só a base lógica de design para as outras telas*
    * **change_password.html** *Tela de mudança de senha para o usuário*
    * **dashboard.html** *Tela de início*
    * **email_reset_password.html** *Tela de recuperação de senha*
    * **forgot_password** *Tela caso o usuário tenha esquecido a senha*
    * **login.html** *Tela de login*
    * **product_form** *Tela do formulário do Produto, usada para criação de produto, por exemplo*
    * **products.html** *Tela de visualização do*
* venv