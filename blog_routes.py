import os
import re
import time
from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify, session
from flask_login import current_user, login_required
from werkzeug.utils import secure_filename
from sqlalchemy import func

from models import (db, User, BlogPost, BlogCategoria, BlogTag, BlogComentario,
                    BlogCurtida, BlogSalvo, BlogNewsletter, UserPerfil, blog_post_tags)

blog_bp = Blueprint('blog', __name__, url_prefix='/blog')

# ── helpers ──────────────────────────────────────────────────────────────────

UPLOAD_FOLDER_BLOG    = os.path.join('static', 'uploads', 'blog')
UPLOAD_FOLDER_AVATARES = os.path.join('static', 'uploads', 'avatares')
UPLOAD_FOLDER_BANNERS  = os.path.join('static', 'uploads', 'banners')
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'webp', 'gif'}

for _f in [UPLOAD_FOLDER_BLOG, UPLOAD_FOLDER_AVATARES, UPLOAD_FOLDER_BANNERS]:
    os.makedirs(_f, exist_ok=True)


def _allowed(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS


def _save_file(arquivo, folder, prefix=''):
    if not arquivo or arquivo.filename == '':
        return None
    if not _allowed(arquivo.filename):
        return None
    ext = arquivo.filename.rsplit('.', 1)[-1].lower()
    fname = f"{prefix}{int(time.time())}_{secure_filename(arquivo.filename)}"
    arquivo.save(os.path.join(folder, fname))
    return fname


def _slugify(text):
    text = text.lower().strip()
    text = re.sub(r'[àáâãä]', 'a', text)
    text = re.sub(r'[èéêë]', 'e', text)
    text = re.sub(r'[ìíîï]', 'i', text)
    text = re.sub(r'[òóôõö]', 'o', text)
    text = re.sub(r'[ùúûü]', 'u', text)
    text = re.sub(r'[ç]', 'c', text)
    text = re.sub(r'[ñ]', 'n', text)
    text = re.sub(r'[^\w\s-]', '', text)
    text = re.sub(r'[\s_]+', '-', text)
    text = re.sub(r'-+', '-', text).strip('-')
    return text


def _unique_slug(base, model, exclude_id=None):
    slug = _slugify(base)
    candidate = slug
    n = 2
    while True:
        q = model.query.filter_by(slug=candidate)
        if exclude_id:
            q = q.filter(model.id != exclude_id)
        if not q.first():
            return candidate
        candidate = f"{slug}-{n}"
        n += 1


def _calc_tempo(conteudo):
    words = len(re.sub(r'<[^>]+>', '', conteudo or '').split())
    return max(1, words // 200 + (1 if words % 200 else 0))


def _admin_required(f):
    from functools import wraps
    @wraps(f)
    def decorated(*args, **kwargs):
        if not current_user.is_authenticated:
            flash('Faça login para continuar.', 'info')
            return redirect(url_for('login'))
        if not current_user.is_admin:
            flash('Acesso restrito a administradores.', 'error')
            return redirect(url_for('blog.index'))
        return f(*args, **kwargs)
    return decorated


def _get_sidebar_data():
    categorias = BlogCategoria.query.all()
    populares = (BlogPost.query
                 .filter_by(status='publicado')
                 .order_by(BlogPost.visualizacoes.desc())
                 .limit(5).all())
    return categorias, populares


# ── PUBLIC ROUTES ─────────────────────────────────────────────────────────────

@blog_bp.route('/')
def index():
    page = request.args.get('page', 1, type=int)
    q = request.args.get('q', '').strip()
    cat_slug = request.args.get('categoria', '').strip()

    query = BlogPost.query.filter_by(status='publicado')
    if q:
        query = query.filter(
            BlogPost.titulo.ilike(f'%{q}%') |
            BlogPost.resumo.ilike(f'%{q}%') |
            BlogPost.conteudo.ilike(f'%{q}%')
        )
    if cat_slug:
        cat = BlogCategoria.query.filter_by(slug=cat_slug).first()
        if cat:
            query = query.filter_by(categoria_id=cat.id)

    posts = query.order_by(BlogPost.created_at.desc()).paginate(page=page, per_page=12)
    categorias, populares = _get_sidebar_data()

    curtidas_user = set()
    salvos_user = set()
    if current_user.is_authenticated:
        curtidas_user = {c.post_id for c in BlogCurtida.query.filter_by(user_id=current_user.id).all()}
        salvos_user = {s.post_id for s in BlogSalvo.query.filter_by(user_id=current_user.id).all()}

    admin = User.query.filter_by(is_admin=True).first()
    admin_perfil = UserPerfil.query.filter_by(user_id=admin.id).first() if admin else None

    return render_template(
        'blog/blog_index.html',
        posts=posts,
        categorias=categorias,
        populares=populares,
        q=q,
        cat_slug=cat_slug,
        curtidas_user=curtidas_user,
        salvos_user=salvos_user,
        admin=admin,
        admin_perfil=admin_perfil,
    )


@blog_bp.route('/<slug>')
def post(slug):
    p = BlogPost.query.filter_by(slug=slug, status='publicado').first_or_404()

    # increment views once per session per post
    viewed_key = f'blog_viewed_{p.id}'
    if not session.get(viewed_key):
        p.visualizacoes = (p.visualizacoes or 0) + 1
        db.session.commit()
        session[viewed_key] = True

    # comments (top level only)
    comentarios = (BlogComentario.query
                   .filter_by(post_id=p.id, parent_id=None)
                   .order_by(BlogComentario.created_at.asc())
                   .all())

    # related posts — mesma categoria primeiro, depois os demais
    da_categoria = (BlogPost.query
                    .filter(BlogPost.status == 'publicado',
                            BlogPost.id != p.id,
                            BlogPost.categoria_id == p.categoria_id)
                    .order_by(BlogPost.created_at.desc()).all())
    outros = (BlogPost.query
              .filter(BlogPost.status == 'publicado',
                      BlogPost.id != p.id,
                      BlogPost.id.notin_([r.id for r in da_categoria]))
              .order_by(BlogPost.visualizacoes.desc()).all())
    relacionados = da_categoria + outros

    total_curtidas = BlogCurtida.query.filter_by(post_id=p.id).count()
    ja_curtiu = False
    ja_salvou = False
    if current_user.is_authenticated:
        ja_curtiu = BlogCurtida.query.filter_by(post_id=p.id, user_id=current_user.id).first() is not None
        ja_salvou = BlogSalvo.query.filter_by(post_id=p.id, user_id=current_user.id).first() is not None

    categorias, populares = _get_sidebar_data()
    return render_template(
        'blog/post.html',
        post=p,
        comentarios=comentarios,
        relacionados=relacionados,
        total_curtidas=total_curtidas,
        ja_curtiu=ja_curtiu,
        ja_salvou=ja_salvou,
        categorias=categorias,
        populares=populares,
    )


@blog_bp.route('/categoria/<slug>')
def categoria(slug):
    cat = BlogCategoria.query.filter_by(slug=slug).first_or_404()
    page = request.args.get('page', 1, type=int)
    posts = (BlogPost.query
             .filter_by(status='publicado', categoria_id=cat.id)
             .order_by(BlogPost.created_at.desc())
             .paginate(page=page, per_page=12))
    categorias, populares = _get_sidebar_data()
    return render_template('blog/blog_categoria.html',
                           categoria=cat, posts=posts,
                           categorias=categorias, populares=populares)


@blog_bp.route('/tag/<slug>')
def tag(slug):
    from models import BlogTag as BT
    t = BT.query.filter_by(slug=slug).first_or_404()
    page = request.args.get('page', 1, type=int)
    posts = (BlogPost.query
             .filter(BlogPost.status == 'publicado',
                     BlogPost.tags.any(id=t.id))
             .order_by(BlogPost.created_at.desc())
             .paginate(page=page, per_page=12))
    categorias, populares = _get_sidebar_data()
    return render_template('blog/tag.html',
                           tag=t, posts=posts,
                           categorias=categorias, populares=populares)


@blog_bp.route('/autor/<int:user_id>')
def perfil_autor(user_id):
    autor = User.query.get_or_404(user_id)
    perfil = UserPerfil.query.filter_by(user_id=user_id).first()
    posts = (BlogPost.query
             .filter_by(user_id=user_id, status='publicado')
             .order_by(BlogPost.created_at.desc())
             .all())
    total_curtidas = sum(BlogCurtida.query.filter_by(post_id=p.id).count() for p in posts)
    total_comentarios = sum(BlogComentario.query.filter_by(post_id=p.id).count() for p in posts)
    return render_template('blog/perfil_autor.html',
                           autor=autor, perfil=perfil, posts=posts,
                           total_curtidas=total_curtidas,
                           total_comentarios=total_comentarios)


@blog_bp.route('/perfil/editar', methods=['GET', 'POST'])
@login_required
def editar_perfil():
    perfil = UserPerfil.query.filter_by(user_id=current_user.id).first()
    if not perfil:
        perfil = UserPerfil(user_id=current_user.id)
        db.session.add(perfil)
        db.session.commit()

    if request.method == 'POST':
        # update user name
        novo_nome = request.form.get('nome', '').strip()
        if novo_nome:
            current_user.name = novo_nome

        # username
        username = request.form.get('username', '').strip() or None
        if username:
            existing = UserPerfil.query.filter_by(username=username).first()
            if existing and existing.user_id != current_user.id:
                flash('Este nome de usuário já está em uso.', 'error')
                return redirect(url_for('blog.editar_perfil'))

        perfil.username = username
        perfil.bio = request.form.get('bio', '').strip() or None
        perfil.email_contato = request.form.get('email_contato', '').strip() or None
        perfil.telefone = request.form.get('telefone', '').strip() or None
        perfil.cidade = request.form.get('cidade', '').strip() or None
        perfil.profissao = request.form.get('profissao', '').strip() or None
        perfil.site = request.form.get('site', '').strip() or None
        perfil.instagram = request.form.get('instagram', '').strip() or None
        perfil.tiktok = request.form.get('tiktok', '').strip() or None
        perfil.facebook = request.form.get('facebook', '').strip() or None
        perfil.linkedin = request.form.get('linkedin', '').strip() or None

        # avatar upload
        avatar = request.files.get('avatar')
        if avatar and avatar.filename:
            fname = _save_file(avatar, UPLOAD_FOLDER_AVATARES, 'avatar_')
            if fname:
                perfil.avatar_url = f'uploads/avatares/{fname}'

        # banner upload
        banner = request.files.get('banner')
        if banner and banner.filename:
            fname = _save_file(banner, UPLOAD_FOLDER_BANNERS, 'banner_')
            if fname:
                perfil.banner_url = f'uploads/banners/{fname}'

        db.session.commit()
        flash('Perfil atualizado com sucesso!', 'success')
        return redirect(url_for('blog.perfil_autor', user_id=current_user.id))

    return render_template('blog/editar_perfil.html', perfil=perfil)


# ── SOBRE (página especial do admin) ─────────────────────────────────────────

@blog_bp.route('/sobre')
def sobre():
    admin = User.query.filter_by(is_admin=True).first()
    perfil = UserPerfil.query.filter_by(user_id=admin.id).first() if admin else None
    posts_destaque = (BlogPost.query
                      .filter_by(status='publicado')
                      .order_by(BlogPost.visualizacoes.desc())
                      .limit(6).all()) if admin else []
    total_posts = BlogPost.query.filter_by(status='publicado').count()
    total_views = db.session.query(func.sum(BlogPost.visualizacoes)).scalar() or 0
    total_comentarios = BlogComentario.query.count()
    categorias, populares = _get_sidebar_data()
    return render_template('blog/sobre.html',
                           admin=admin, perfil=perfil,
                           posts_destaque=posts_destaque,
                           total_posts=total_posts,
                           total_views=total_views,
                           total_comentarios=total_comentarios,
                           categorias=categorias, populares=populares)


# ── INTERACTION ROUTES ────────────────────────────────────────────────────────

@blog_bp.route('/<int:id>/curtir', methods=['POST'])
@login_required
def curtir(id):
    p = BlogPost.query.get_or_404(id)
    existing = BlogCurtida.query.filter_by(post_id=p.id, user_id=current_user.id).first()
    if existing:
        db.session.delete(existing)
        db.session.commit()
        curtiu = False
    else:
        db.session.add(BlogCurtida(post_id=p.id, user_id=current_user.id))
        db.session.commit()
        curtiu = True
    total = BlogCurtida.query.filter_by(post_id=p.id).count()
    return jsonify({'curtiu': curtiu, 'total': total})


@blog_bp.route('/<int:id>/salvar', methods=['POST'])
@login_required
def salvar_post(id):
    p = BlogPost.query.get_or_404(id)
    existing = BlogSalvo.query.filter_by(post_id=p.id, user_id=current_user.id).first()
    if existing:
        db.session.delete(existing)
        db.session.commit()
        salvou = False
    else:
        db.session.add(BlogSalvo(post_id=p.id, user_id=current_user.id))
        db.session.commit()
        salvou = True
    return jsonify({'salvou': salvou})


@blog_bp.route('/<int:id>/comentar', methods=['POST'])
@login_required
def comentar(id):
    p = BlogPost.query.get_or_404(id)
    conteudo = request.form.get('conteudo', '').strip()
    parent_id = request.form.get('parent_id', type=int)
    if not conteudo:
        flash('O comentário não pode ser vazio.', 'error')
        return redirect(url_for('blog.post', slug=p.slug))
    comentario = BlogComentario(
        conteudo=conteudo,
        post_id=p.id,
        user_id=current_user.id,
        parent_id=parent_id or None
    )
    db.session.add(comentario)
    db.session.commit()
    flash('Comentário adicionado!', 'success')
    return redirect(url_for('blog.post', slug=p.slug) + '#comentarios')


@blog_bp.route('/comentario/<int:id>/excluir', methods=['POST'])
@login_required
def excluir_comentario(id):
    c = BlogComentario.query.get_or_404(id)
    post = BlogPost.query.get(c.post_id)
    if c.user_id != current_user.id and not current_user.is_admin:
        flash('Sem permissão para excluir este comentário.', 'error')
        return redirect(url_for('blog.post', slug=post.slug))
    db.session.delete(c)
    db.session.commit()
    flash('Comentário excluído.', 'success')
    return redirect(url_for('blog.post', slug=post.slug) + '#comentarios')


@blog_bp.route('/newsletter', methods=['POST'])
def newsletter():
    email = request.form.get('email', '').strip().lower()
    if not email or '@' not in email:
        flash('E-mail inválido.', 'error')
        return redirect(request.referrer or url_for('blog.index'))
    existing = BlogNewsletter.query.filter_by(email=email).first()
    if existing:
        flash('Este e-mail já está inscrito na newsletter.', 'info')
    else:
        db.session.add(BlogNewsletter(email=email))
        db.session.commit()
        flash('Inscrição realizada com sucesso! Obrigada.', 'success')
    return redirect(request.referrer or url_for('blog.index'))


# ── ADMIN ROUTES ──────────────────────────────────────────────────────────────

@blog_bp.route('/admin')
@_admin_required
def admin():
    page = request.args.get('page', 1, type=int)
    q = request.args.get('q', '').strip()
    status_filtro = request.args.get('status', '').strip()

    query = BlogPost.query
    if q:
        query = query.filter(BlogPost.titulo.ilike(f'%{q}%'))
    if status_filtro:
        query = query.filter_by(status=status_filtro)

    posts = query.order_by(BlogPost.created_at.desc()).paginate(page=page, per_page=20)

    total_posts = BlogPost.query.count()
    publicados = BlogPost.query.filter_by(status='publicado').count()
    rascunhos = BlogPost.query.filter_by(status='rascunho').count()
    total_views = db.session.query(func.sum(BlogPost.visualizacoes)).scalar() or 0
    total_curtidas = BlogCurtida.query.count()
    total_comentarios = BlogComentario.query.count()

    # top posts for chart — all published, sorted by views
    top_posts_views = (BlogPost.query
                       .filter_by(status='publicado')
                       .order_by(BlogPost.visualizacoes.desc())
                       .limit(7).all())

    # all published posts as JSON for client-side chart filtering
    import json as _json
    posts_chart_json = _json.dumps([
        {
            'titulo': p.titulo[:35],
            'views': p.visualizacoes,
            'data': p.created_at.strftime('%Y-%m-%d')
        }
        for p in BlogPost.query.filter_by(status='publicado')
                         .order_by(BlogPost.created_at.desc()).all()
    ])

    return render_template('blog/admin.html',
                           posts=posts, q=q, status_filtro=status_filtro,
                           total_posts=total_posts, publicados=publicados,
                           rascunhos=rascunhos, total_views=total_views,
                           total_curtidas=total_curtidas,
                           total_comentarios=total_comentarios,
                           top_posts_views=top_posts_views,
                           posts_chart_json=posts_chart_json)


@blog_bp.route('/admin/novo', methods=['GET', 'POST'])
@_admin_required
def admin_novo():
    categorias = BlogCategoria.query.all()
    tags = BlogTag.query.all()
    if request.method == 'POST':
        titulo = request.form.get('titulo', '').strip()
        if not titulo:
            flash('O título é obrigatório.', 'error')
            return redirect(url_for('blog.admin_novo'))

        slug_base = request.form.get('slug', '').strip() or titulo
        slug = _unique_slug(slug_base, BlogPost)

        conteudo = request.form.get('conteudo', '')
        resumo = request.form.get('resumo', '').strip() or None
        status = request.form.get('status', 'rascunho')
        cat_id = request.form.get('categoria_id', type=int) or None
        meta_titulo = request.form.get('meta_titulo', '').strip() or None
        meta_descricao = request.form.get('meta_descricao', '').strip() or None
        tempo_leitura = _calc_tempo(conteudo)

        # capa upload
        capa_url = None
        capa = request.files.get('capa')
        if capa and capa.filename:
            fname = _save_file(capa, UPLOAD_FOLDER_BLOG, 'capa_')
            if fname:
                capa_url = f'uploads/blog/{fname}'

        post = BlogPost(
            titulo=titulo,
            slug=slug,
            resumo=resumo,
            conteudo=conteudo,
            capa_url=capa_url,
            status=status,
            tempo_leitura=tempo_leitura,
            meta_titulo=meta_titulo,
            meta_descricao=meta_descricao,
            user_id=current_user.id,
            categoria_id=cat_id,
        )
        db.session.add(post)
        db.session.flush()

        # tags
        tag_ids = request.form.getlist('tags')
        for tid in tag_ids:
            t = BlogTag.query.get(int(tid))
            if t:
                post.tags.append(t)

        # new tags from text input
        novas_tags_raw = request.form.get('novas_tags', '').strip()
        if novas_tags_raw:
            for nome_tag in [x.strip() for x in novas_tags_raw.split(',') if x.strip()]:
                tag_slug = _slugify(nome_tag)
                t = BlogTag.query.filter_by(slug=tag_slug).first()
                if not t:
                    t = BlogTag(nome=nome_tag, slug=tag_slug)
                    db.session.add(t)
                    db.session.flush()
                if t not in post.tags:
                    post.tags.append(t)

        db.session.commit()
        flash(f'Post "{titulo}" criado com sucesso!', 'success')
        if status == 'publicado':
            return redirect(url_for('blog.post', slug=slug))
        return redirect(url_for('blog.admin'))

    return render_template('blog/editor.html',
                           post=None, categorias=categorias, tags=tags,
                           action=url_for('blog.admin_novo'))


@blog_bp.route('/admin/<int:id>/editar', methods=['GET', 'POST'])
@_admin_required
def admin_editar(id):
    post = BlogPost.query.get_or_404(id)
    categorias = BlogCategoria.query.all()
    tags = BlogTag.query.all()

    if request.method == 'POST':
        titulo = request.form.get('titulo', '').strip()
        if not titulo:
            flash('O título é obrigatório.', 'error')
            return redirect(url_for('blog.admin_editar', id=id))

        slug_base = request.form.get('slug', '').strip() or titulo
        post.slug = _unique_slug(slug_base, BlogPost, exclude_id=id)

        post.titulo = titulo
        post.conteudo = request.form.get('conteudo', '')
        post.resumo = request.form.get('resumo', '').strip() or None
        post.status = request.form.get('status', 'rascunho')
        post.categoria_id = request.form.get('categoria_id', type=int) or None
        post.meta_titulo = request.form.get('meta_titulo', '').strip() or None
        post.meta_descricao = request.form.get('meta_descricao', '').strip() or None
        post.tempo_leitura = _calc_tempo(post.conteudo)

        capa = request.files.get('capa')
        if capa and capa.filename:
            fname = _save_file(capa, UPLOAD_FOLDER_BLOG, 'capa_')
            if fname:
                post.capa_url = f'uploads/blog/{fname}'

        # update tags
        post.tags = []
        tag_ids = request.form.getlist('tags')
        for tid in tag_ids:
            t = BlogTag.query.get(int(tid))
            if t:
                post.tags.append(t)

        novas_tags_raw = request.form.get('novas_tags', '').strip()
        if novas_tags_raw:
            for nome_tag in [x.strip() for x in novas_tags_raw.split(',') if x.strip()]:
                tag_slug = _slugify(nome_tag)
                t = BlogTag.query.filter_by(slug=tag_slug).first()
                if not t:
                    t = BlogTag(nome=nome_tag, slug=tag_slug)
                    db.session.add(t)
                    db.session.flush()
                if t not in post.tags:
                    post.tags.append(t)

        db.session.commit()
        flash(f'Post "{titulo}" atualizado com sucesso!', 'success')
        return redirect(url_for('blog.admin'))

    return render_template('blog/editor.html',
                           post=post, categorias=categorias, tags=tags,
                           action=url_for('blog.admin_editar', id=id))


@blog_bp.route('/admin/<int:id>/excluir', methods=['POST'])
@_admin_required
def admin_excluir(id):
    post = BlogPost.query.get_or_404(id)
    titulo = post.titulo
    # delete related data
    BlogCurtida.query.filter_by(post_id=id).delete()
    BlogSalvo.query.filter_by(post_id=id).delete()
    BlogComentario.query.filter_by(post_id=id).delete()
    db.session.delete(post)
    db.session.commit()
    flash(f'Post "{titulo}" excluído.', 'success')
    return redirect(url_for('blog.admin'))


@blog_bp.route('/admin/<int:id>/status', methods=['POST'])
@_admin_required
def admin_toggle_status(id):
    post = BlogPost.query.get_or_404(id)
    post.status = 'publicado' if post.status == 'rascunho' else 'rascunho'
    db.session.commit()
    flash(f'Post {"publicado" if post.status == "publicado" else "movido para rascunho"} com sucesso!', 'success')
    return redirect(url_for('blog.admin'))


# ── CATEGORY ADMIN ────────────────────────────────────────────────────────────

@blog_bp.route('/admin/categorias', methods=['GET', 'POST'])
@_admin_required
def admin_categorias():
    if request.method == 'POST':
        nome = request.form.get('nome', '').strip()
        descricao = request.form.get('descricao', '').strip() or None
        cor = request.form.get('cor', '#5B6D3D').strip()
        if not nome:
            flash('Nome da categoria é obrigatório.', 'error')
            return redirect(url_for('blog.admin_categorias'))
        slug = _unique_slug(nome, BlogCategoria)
        cat = BlogCategoria(nome=nome, slug=slug, descricao=descricao, cor=cor)
        db.session.add(cat)
        db.session.commit()
        flash(f'Categoria "{nome}" criada!', 'success')
        return redirect(url_for('blog.admin_categorias'))

    categorias = BlogCategoria.query.all()
    return render_template('blog/categorias_admin.html', categorias=categorias)


@blog_bp.route('/admin/categorias/<int:id>/excluir', methods=['POST'])
@_admin_required
def admin_excluir_categoria(id):
    cat = BlogCategoria.query.get_or_404(id)
    # unlink posts
    BlogPost.query.filter_by(categoria_id=id).update({'categoria_id': None})
    db.session.delete(cat)
    db.session.commit()
    flash(f'Categoria "{cat.nome}" excluída.', 'success')
    return redirect(url_for('blog.admin_categorias'))
