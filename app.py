"""
O servidor da aplicação.

Cada função com @app.route(...) responde a um endereço.
Por exemplo, quando abres http://localhost:5000/ o Flask chama inicio().
"""

import secrets
import time
from datetime import datetime

from flask import Flask, abort, flash, redirect, render_template, request, url_for

import base_dados as bd
import cofre
import web
from ligacoes import Mentalista

app = Flask(__name__)

# O flash() (as mensagens "Tema apagado", etc.) precisa de uma chave secreta.
# Como a app é só tua, basta uma chave nova sempre que arranca.
app.secret_key = secrets.token_hex(16)


# ---------- Ajudas para os templates ----------

@app.template_filter("data")
def formatar_data(texto_iso):
    """Nos templates, {{ x | data }} mostra '21/10/2026 14:30'."""
    return datetime.fromisoformat(texto_iso).strftime("%d/%m/%Y %H:%M")


@app.context_processor
def variaveis_globais():
    """Variáveis disponíveis em todos os templates."""
    return {"numero_cores": bd.NUMERO_CORES}


# ---------- O cadeado ----------

# Páginas que funcionam com o caderno bloqueado
ROTAS_LIVRES = {"desbloquear", "static"}
# Páginas para onde faz sentido voltar depois de desbloquear
ROTAS_DE_REGRESSO = {"inicio", "ver_tema", "categorias"}


@app.before_request
def exigir_desbloqueio():
    """
    Corre antes de cada pedido. Se o caderno estiver bloqueado,
    manda-te para a página da palavra-passe.
    """
    if request.endpoint in ROTAS_LIVRES:
        return None
    if not cofre.desbloqueado():
        seguinte = None
        if request.method == "GET" and request.endpoint in ROTAS_DE_REGRESSO:
            seguinte = request.full_path.rstrip("?")
        return redirect(url_for("desbloquear", seguinte=seguinte))
    cofre.marcar_uso()
    return None


def endereco_seguro(endereco):
    """Só aceita endereços desta aplicação (começam por / mas não por //)."""
    if endereco and endereco.startswith("/") and not endereco.startswith("//"):
        return endereco
    return url_for("inicio")


@app.route("/desbloquear", methods=["GET", "POST"])
def desbloquear():
    """Pede a palavra-passe. Na primeira vez, cria-a."""
    seguinte = endereco_seguro(request.args.get("seguinte"))
    if cofre.desbloqueado():
        return redirect(seguinte)

    primeira_vez = not cofre.existe_cofre()
    erro = None

    if request.method == "POST":
        palavra_passe = request.form.get("palavra_passe", "")
        if primeira_vez:
            if len(palavra_passe) < 8:
                erro = "A palavra-passe tem de ter pelo menos 8 caracteres."
            elif palavra_passe != request.form.get("confirmacao", ""):
                erro = "As duas palavras-passe não são iguais."
            else:
                tinha_antigo = cofre.existe_caderno_antigo()
                cofre.criar(palavra_passe)
                bd.preparar()
                if tinha_antigo:
                    flash("As tuas notas foram passadas para o cofre encriptado.")
                return redirect(seguinte)
        else:
            try:
                cofre.abrir(palavra_passe)
                bd.preparar()
                return redirect(seguinte)
            except cofre.PalavraPasseErrada:
                # Uma pequena espera torna mais lento quem tenta adivinhar
                time.sleep(1)
                erro = "Palavra-passe errada."

    return render_template(
        "desbloquear.html",
        primeira_vez=primeira_vez,
        tem_antigo=cofre.existe_caderno_antigo(),
        erro=erro,
    )


@app.post("/bloquear")
def bloquear():
    cofre.bloquear()
    return redirect(url_for("desbloquear"))


@app.post("/apagar-copia-antiga")
def apagar_copia_antiga():
    """Apaga o ficheiro não encriptado das fases anteriores, depois de confirmares."""
    cofre.CAMINHO_ANTIGO_RENOMEADO.unlink(missing_ok=True)
    flash("Cópia antiga apagada. Agora só existe o cofre encriptado.")
    return redirect(url_for("inicio"))


# ---------- Ajudas para as rotas ----------

def obter_tema_ou_404(tema_id):
    """Devolve o tema; se não existir, responde logo com a página 404."""
    tema = bd.obter_tema(tema_id)
    if tema is None:
        abort(404)
    return tema


def obter_entrada_ou_404(entrada_id):
    entrada = bd.obter_entrada(entrada_id)
    if entrada is None:
        abort(404)
    return entrada


def obter_categoria_ou_404(categoria_id):
    categoria = bd.obter_categoria(categoria_id)
    if categoria is None:
        abort(404)
    return categoria


def categoria_do_formulario():
    """
    Lê a categoria escolhida num formulário.
    "" = sem categoria; "nova" = cria-a com o nome que escreveste.
    Se algo vier mal, fica sem categoria (None).
    """
    escolha = request.form.get("categoria_id", "")
    if escolha == "nova":
        nome = request.form.get("nova_categoria", "").strip()
        if nome:
            return bd.criar_categoria(nome)
    elif escolha.isdigit() and bd.obter_categoria(int(escolha)):
        return int(escolha)
    return None


def cor_do_formulario():
    cor = request.form.get("cor", type=int)
    if cor is None or not 0 <= cor < bd.NUMERO_CORES:
        return None
    return cor


def voltar_ao_tema(tema_id, entrada_id=None):
    """Redireciona para a página do tema; com entrada_id, salta para essa entrada."""
    ancora = f"entrada-{entrada_id}" if entrada_id else None
    return redirect(url_for("ver_tema", tema_id=tema_id, _anchor=ancora))


def dados_da_pesquisa(termo, categoria_id):
    """O que a página inicial precisa: temas, categorias e se mostra o botão Criar."""
    # Se o filtro apontar para uma categoria que não existe, ignoramo-lo (0 = sem categoria)
    if categoria_id and bd.obter_categoria(categoria_id) is None:
        categoria_id = None
    return {
        "termo": termo,
        "categoria_atual": categoria_id,
        "categorias": bd.listar_categorias(),
        "sem_categoria": bd.contar_sem_categoria(),
        "temas": bd.procurar_temas(termo, categoria_id),
        # Só faz sentido oferecer "Criar tema" se escreveste algo
        # e ainda não há nenhum tema com exatamente esse nome
        "mostrar_criar": bool(termo) and bd.procurar_tema_por_nome(termo) is None,
    }


# ---------- Página inicial e pesquisa ----------

@app.route("/")
def inicio():
    """Página inicial com a barra de pesquisa."""
    # request.args são os parâmetros do endereço: /?q=escola&cat=2
    termo = request.args.get("q", "").strip()
    categoria_id = request.args.get("cat", type=int)
    return render_template(
        "inicio.html",
        copia_antiga=cofre.CAMINHO_ANTIGO_RENOMEADO.exists(),
        **dados_da_pesquisa(termo, categoria_id),
    )


@app.route("/pesquisa")
def pesquisa():
    """
    Devolve só o bloco dos resultados.
    É chamado pelo JavaScript enquanto escreves, para a página não recarregar.
    """
    termo = request.args.get("q", "").strip()
    categoria_id = request.args.get("cat", type=int)
    return render_template("_resultados.html", **dados_da_pesquisa(termo, categoria_id))


# ---------- Categorias ----------

@app.route("/categorias")
def categorias():
    return render_template(
        "categorias.html",
        categorias=bd.listar_categorias(),
        sem_categoria=bd.contar_sem_categoria(),
    )


@app.post("/categorias")
def criar_categoria():
    nome = request.form.get("nome", "").strip()
    if not nome:
        return redirect(url_for("categorias"))
    if bd.procurar_categoria_por_nome(nome):
        flash(f"Já existe a categoria \"{nome}\".", "erro")
    else:
        bd.criar_categoria(nome, cor_do_formulario())
        flash(f"Categoria \"{nome}\" criada.")
    return redirect(url_for("categorias"))


@app.post("/categoria/<int:categoria_id>/editar")
def editar_categoria(categoria_id):
    categoria = obter_categoria_ou_404(categoria_id)
    nome = request.form.get("nome", "").strip() or categoria["nome"]
    outra = bd.procurar_categoria_por_nome(nome)
    if outra and outra["id"] != categoria_id:
        flash(f"Já existe a categoria \"{outra['nome']}\".", "erro")
    else:
        cor = cor_do_formulario()
        bd.editar_categoria(categoria_id, nome, categoria["cor"] if cor is None else cor)
        flash("Categoria atualizada.")
    return redirect(url_for("categorias"))


@app.post("/categoria/<int:categoria_id>/apagar")
def apagar_categoria(categoria_id):
    categoria = obter_categoria_ou_404(categoria_id)
    bd.apagar_categoria(categoria_id)
    flash(f"Categoria \"{categoria['nome']}\" apagada. Os temas dela ficaram sem categoria.")
    return redirect(url_for("categorias"))


# ---------- Temas ----------

@app.post("/temas")
def criar_tema():
    """Recebe o formulário "Criar tema"."""
    nome = request.form.get("nome", "").strip()
    if not nome:
        return redirect(url_for("inicio"))

    # Se já existir (por exemplo criaste-o noutra janela), abre esse
    existente = bd.procurar_tema_por_nome(nome)
    if existente:
        return redirect(url_for("ver_tema", tema_id=existente["id"]))

    novo_id = bd.criar_tema(nome, categoria_do_formulario())
    flash(f"Tema \"{nome}\" criado.")
    return redirect(url_for("ver_tema", tema_id=novo_id))


@app.route("/tema/<int:tema_id>")
def ver_tema(tema_id):
    """Página de um tema com todas as suas entradas e as ligações a outros temas."""
    tema = obter_tema_ou_404(tema_id)
    entradas = bd.listar_entradas(tema_id)
    por_fazer = sum(1 for e in entradas if e["tipo"] == "tarefa" and not e["feito"])
    mentalista = Mentalista(bd.todos_os_temas_com_entradas())
    return render_template(
        "tema.html",
        tema=tema,
        entradas=entradas,
        por_fazer=por_fazer,
        categorias=bd.listar_categorias(),
        ligacoes=mentalista.ligacoes(tema_id),
        linguas=web.LINGUAS,
    )


@app.route("/tema/<int:tema_id>/web")
def pesquisa_web(tema_id):
    """
    Pesquisa o nome do tema na Wikipédia e liga os resultados ao teu caderno.
    É chamado pelo JavaScript quando carregas no botão; devolve só um bloco de HTML.
    """
    tema = obter_tema_ou_404(tema_id)
    lingua = request.args.get("lingua", "pt")
    try:
        artigos = web.procurar(tema["nome"], lingua)
    except web.ErroWeb as erro:
        return render_template("_web.html", erro=str(erro), artigos=[])

    mentalista = Mentalista(bd.todos_os_temas_com_entradas())
    for artigo in artigos:
        artigo["resumo_html"], artigo["ligacoes"] = mentalista.ligar_texto_externo(
            artigo["resumo"], tema_id
        )
    return render_template("_web.html", erro=None, artigos=artigos)


@app.post("/tema/<int:tema_id>/editar")
def editar_tema(tema_id):
    """Muda o nome e a categoria do tema."""
    tema = obter_tema_ou_404(tema_id)
    nome = request.form.get("nome", "").strip() or tema["nome"]

    # Não deixamos ficar dois temas com o mesmo nome
    outro = bd.procurar_tema_por_nome(nome)
    if outro and outro["id"] != tema_id:
        flash(f"Já existe um tema chamado \"{outro['nome']}\".", "erro")
        return voltar_ao_tema(tema_id)

    bd.editar_tema(tema_id, nome, categoria_do_formulario())
    flash("Tema atualizado.")
    return voltar_ao_tema(tema_id)


@app.post("/tema/<int:tema_id>/apagar")
def apagar_tema(tema_id):
    """Apaga o tema e todas as suas entradas. A confirmação é feita no browser."""
    tema = obter_tema_ou_404(tema_id)
    bd.apagar_tema(tema_id)
    flash(f"Tema \"{tema['nome']}\" apagado.")
    return redirect(url_for("inicio"))


# ---------- Entradas ----------

@app.post("/tema/<int:tema_id>/entradas")
def acrescentar_entrada(tema_id):
    """Recebe o formulário da caixa de nova entrada."""
    obter_tema_ou_404(tema_id)
    texto = request.form.get("texto", "").strip()
    # Se vier um tipo estranho, fica nota
    tipo = "tarefa" if request.form.get("tipo") == "tarefa" else "nota"
    if texto:
        bd.acrescentar_entrada(tema_id, texto, tipo)
    # Depois de gravar, voltamos à página do tema.
    # Assim, se carregares em F5, o browser não envia o formulário outra vez.
    return voltar_ao_tema(tema_id)


@app.post("/entrada/<int:entrada_id>/editar")
def editar_entrada(entrada_id):
    entrada = obter_entrada_ou_404(entrada_id)
    texto = request.form.get("texto", "").strip()
    if texto:
        bd.editar_entrada(entrada, texto)
    return voltar_ao_tema(entrada["tema_id"], entrada_id)


@app.post("/entrada/<int:entrada_id>/feito")
def alternar_feito(entrada_id):
    """Risca ou desrisca uma tarefa."""
    entrada = obter_entrada_ou_404(entrada_id)
    if entrada["tipo"] == "tarefa":
        bd.alternar_feito(entrada)
    return voltar_ao_tema(entrada["tema_id"], entrada_id)


@app.post("/entrada/<int:entrada_id>/apagar")
def apagar_entrada(entrada_id):
    entrada = obter_entrada_ou_404(entrada_id)
    bd.apagar_entrada(entrada)
    flash("Entrada apagada.")
    return voltar_ao_tema(entrada["tema_id"])


if __name__ == "__main__":
    # debug=True recarrega o servidor sozinho quando alteras o código
    # (e volta a pedir a palavra-passe, porque a chave só vive na memória).
    # threaded=False: um pedido de cada vez, porque há uma só base de dados na memória.
    # Por omissão o Flask só aceita ligações do teu próprio computador.
    app.run(port=5000, debug=True, threaded=False)
