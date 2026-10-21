"""
O servidor da aplicação.

Cada função com @app.route(...) responde a um endereço.
Por exemplo, quando abres http://localhost:5000/ o Flask chama inicio().
"""

import secrets
from datetime import datetime

from flask import Flask, abort, flash, redirect, render_template, request, url_for

import base_dados as bd

app = Flask(__name__)

# O flash() (as mensagens "Tema apagado", etc.) precisa de uma chave secreta.
# Como a app é só tua, basta uma chave nova sempre que arranca.
app.secret_key = secrets.token_hex(16)

# No fim de cada pedido, fecha a ligação à base de dados
app.teardown_appcontext(bd.fechar_ligacao)

# Garante que as tabelas existem antes de recebermos o primeiro pedido
bd.iniciar_bd()


# ---------- Ajudas para os templates ----------

@app.template_filter("data")
def formatar_data(texto_iso):
    """Nos templates, {{ x | data }} mostra '21/10/2026 14:30'."""
    return datetime.fromisoformat(texto_iso).strftime("%d/%m/%Y %H:%M")


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


def categoria_do_formulario():
    """
    Lê a categoria escolhida num formulário.
    Se escolheste "Nova categoria...", cria-a com o nome que escreveste.
    Se algo vier mal, usa "Outros".
    """
    escolha = request.form.get("categoria_id", "")
    if escolha == "nova":
        nome = request.form.get("nova_categoria", "").strip()
        if nome:
            return bd.obter_ou_criar_categoria(nome)
    elif escolha.isdigit() and bd.obter_categoria(int(escolha)):
        return int(escolha)
    return bd.obter_ou_criar_categoria("Outros")


def voltar_ao_tema(tema_id, entrada_id=None):
    """Redireciona para a página do tema; com entrada_id, salta para essa entrada."""
    ancora = f"entrada-{entrada_id}" if entrada_id else None
    return redirect(url_for("ver_tema", tema_id=tema_id, _anchor=ancora))


def dados_da_pesquisa(termo, categoria_id):
    """O que a página inicial precisa: temas, categorias e se mostra o botão Criar."""
    # Se o filtro apontar para uma categoria que não existe, ignoramo-lo
    if categoria_id is not None and bd.obter_categoria(categoria_id) is None:
        categoria_id = None
    return {
        "termo": termo,
        "categoria_atual": categoria_id,
        "categorias": bd.listar_categorias(),
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
    return render_template("inicio.html", **dados_da_pesquisa(termo, categoria_id))


@app.route("/pesquisa")
def pesquisa():
    """
    Devolve só o bloco dos resultados.
    É chamado pelo JavaScript enquanto escreves, para a página não recarregar.
    """
    termo = request.args.get("q", "").strip()
    categoria_id = request.args.get("cat", type=int)
    return render_template("_resultados.html", **dados_da_pesquisa(termo, categoria_id))


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
    """Página de um tema com todas as suas entradas."""
    tema = obter_tema_ou_404(tema_id)
    entradas = bd.listar_entradas(tema_id)
    por_fazer = sum(1 for e in entradas if e["tipo"] == "tarefa" and not e["feito"])
    return render_template(
        "tema.html",
        tema=tema,
        entradas=entradas,
        por_fazer=por_fazer,
        categorias=bd.listar_categorias(),
    )


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
    # debug=True recarrega o servidor sozinho quando alteras o código.
    # Por omissão o Flask só aceita ligações do teu próprio computador.
    app.run(port=5000, debug=True)
