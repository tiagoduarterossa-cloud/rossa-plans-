"""
O servidor da aplicação.

Cada função com @app.route(...) responde a um endereço.
Por exemplo, quando abres http://localhost:5000/ o Flask chama inicio().
"""

from datetime import datetime

from flask import Flask, abort, redirect, render_template, request, url_for

import base_dados as bd

app = Flask(__name__)

# No fim de cada pedido, fecha a ligação à base de dados
app.teardown_appcontext(bd.fechar_ligacao)

# Garante que as tabelas existem antes de recebermos o primeiro pedido
bd.iniciar_bd()


@app.template_filter("data")
def formatar_data(texto_iso):
    """Nos templates, {{ x | data }} mostra '21/10/2026 14:30'."""
    return datetime.fromisoformat(texto_iso).strftime("%d/%m/%Y %H:%M")


def dados_da_pesquisa(termo):
    """O que a lista de resultados precisa: os temas e se mostra o botão Criar."""
    temas = bd.procurar_temas(termo)
    # Só faz sentido oferecer "Criar tema" se escreveste algo
    # e ainda não há nenhum tema com exatamente esse nome
    mostrar_criar = bool(termo) and bd.procurar_tema_por_nome(termo) is None
    return {"termo": termo, "temas": temas, "mostrar_criar": mostrar_criar}


@app.route("/")
def inicio():
    """Página inicial com a barra de pesquisa."""
    # request.args são os parâmetros do endereço: /?q=escola -> "escola"
    termo = request.args.get("q", "").strip()
    return render_template("inicio.html", **dados_da_pesquisa(termo))


@app.route("/pesquisa")
def pesquisa():
    """
    Devolve só o bloco dos resultados.
    É chamado pelo JavaScript enquanto escreves, para a página não recarregar.
    """
    termo = request.args.get("q", "").strip()
    return render_template("_resultados.html", **dados_da_pesquisa(termo))


@app.post("/temas")
def criar_tema():
    """Recebe o formulário do botão "Criar tema"."""
    nome = request.form.get("nome", "").strip()
    if not nome:
        return redirect(url_for("inicio"))

    # Se já existir (por exemplo criaste-o noutra janela), abre esse
    existente = bd.procurar_tema_por_nome(nome)
    if existente:
        return redirect(url_for("ver_tema", tema_id=existente["id"]))

    novo_id = bd.criar_tema(nome)
    return redirect(url_for("ver_tema", tema_id=novo_id))


@app.route("/tema/<int:tema_id>")
def ver_tema(tema_id):
    """Página de um tema com todas as suas entradas."""
    tema = bd.obter_tema(tema_id)
    if tema is None:
        abort(404)  # página "não encontrado"
    entradas = bd.listar_entradas(tema_id)
    return render_template("tema.html", tema=tema, entradas=entradas)


@app.post("/tema/<int:tema_id>/entradas")
def acrescentar_entrada(tema_id):
    """Recebe o formulário da caixa de nova entrada."""
    if bd.obter_tema(tema_id) is None:
        abort(404)
    texto = request.form.get("texto", "").strip()
    if texto:
        bd.acrescentar_entrada(tema_id, texto)
    # Depois de gravar, voltamos à página do tema.
    # Assim, se carregares em F5, o browser não envia o formulário outra vez.
    return redirect(url_for("ver_tema", tema_id=tema_id))


if __name__ == "__main__":
    # debug=True recarrega o servidor sozinho quando alteras o código.
    # Por omissão o Flask só aceita ligações do teu próprio computador.
    app.run(port=5000, debug=True)
