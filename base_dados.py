"""
Tudo o que mexe na base de dados SQLite está neste ficheiro.

A ideia é o app.py nunca escrever SQL diretamente: pede as coisas
a estas funções (procurar temas, criar tema, etc.) e elas tratam do resto.
"""

import sqlite3
import unicodedata
from datetime import datetime
from pathlib import Path

from flask import g

# O ficheiro da base de dados fica na mesma pasta que este código.
CAMINHO_BD = Path(__file__).parent / "caderno.db"

# Categorias que existem logo de início (na Fase 2 vais poder criar mais).
CATEGORIAS_INICIAIS = ["Escola", "Loja", "Ideias", "Outros"]

# Esquema completo das tabelas.
# Já inclui o que a Fase 2 vai precisar (categorias, tarefas, "feito"),
# para não termos de alterar a estrutura da base de dados mais tarde.
# "IF NOT EXISTS" faz com que isto possa correr sempre que a aplicação
# arranca sem estragar o que já lá está.
ESQUEMA = """
CREATE TABLE IF NOT EXISTS categorias (
    id   INTEGER PRIMARY KEY AUTOINCREMENT,
    nome TEXT NOT NULL UNIQUE
);

CREATE TABLE IF NOT EXISTS temas (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    nome         TEXT NOT NULL UNIQUE,
    categoria_id INTEGER NOT NULL REFERENCES categorias(id),
    criado_em    TEXT NOT NULL,
    alterado_em  TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS entradas (
    id        INTEGER PRIMARY KEY AUTOINCREMENT,
    tema_id   INTEGER NOT NULL REFERENCES temas(id) ON DELETE CASCADE,
    texto     TEXT NOT NULL,
    tipo      TEXT NOT NULL DEFAULT 'nota' CHECK (tipo IN ('nota', 'tarefa')),
    feito     INTEGER NOT NULL DEFAULT 0,
    criado_em TEXT NOT NULL
);
"""


def normalizar(texto):
    """Tira acentos e põe tudo em minúsculas: 'Matemática' -> 'matematica'."""
    if texto is None:
        return ""
    # NFD separa cada letra do seu acento: 'á' passa a 'a' + '´'
    decomposto = unicodedata.normalize("NFD", texto)
    # Os acentos soltos são da categoria "Mn"; deitamo-los fora
    sem_acentos = "".join(c for c in decomposto if unicodedata.category(c) != "Mn")
    # casefold é um lower() mais completo (por exemplo 'ß' passa a 'ss')
    return sem_acentos.casefold()


def agora():
    """Data e hora atuais em texto, por exemplo '2026-10-21T14:30:00'."""
    return datetime.now().isoformat(timespec="seconds")


def obter_ligacao():
    """
    Devolve a ligação à base de dados para o pedido atual.

    O 'g' do Flask é uma caixa que só dura um pedido do browser.
    Abrimos a ligação na primeira vez que é precisa e reutilizamo-la
    até o pedido acabar.
    """
    if "bd" not in g:
        g.bd = sqlite3.connect(CAMINHO_BD)
        # Permite ler colunas pelo nome: linha["nome"] em vez de linha[1]
        g.bd.row_factory = sqlite3.Row
        # O SQLite só respeita as ligações entre tabelas se pedirmos
        g.bd.execute("PRAGMA foreign_keys = ON")
        # Ensinamos ao SQLite a nossa função normalizar(), para a usar no SQL
        g.bd.create_function("normalizar", 1, normalizar, deterministic=True)
    return g.bd


def fechar_ligacao(erro=None):
    """O Flask chama isto automaticamente no fim de cada pedido."""
    bd = g.pop("bd", None)
    if bd is not None:
        bd.close()


def iniciar_bd():
    """Cria as tabelas e as categorias iniciais, se ainda não existirem."""
    bd = sqlite3.connect(CAMINHO_BD)
    bd.executescript(ESQUEMA)
    # INSERT OR IGNORE: se a categoria já existir, não faz nada
    bd.executemany(
        "INSERT OR IGNORE INTO categorias (nome) VALUES (?)",
        [(nome,) for nome in CATEGORIAS_INICIAIS],
    )
    bd.commit()
    bd.close()


# ---------- Temas ----------

def procurar_temas(termo):
    """
    Temas cujo nome contém o termo, sem ligar a maiúsculas nem acentos.
    Sem termo, devolve todos.
    """
    bd = obter_ligacao()
    # instr(a, b) diz em que posição o texto b aparece dentro de a (0 = não aparece)
    return bd.execute(
        """
        SELECT temas.id, temas.nome, categorias.nome AS categoria
        FROM temas
        JOIN categorias ON categorias.id = temas.categoria_id
        WHERE instr(normalizar(temas.nome), ?) > 0
        ORDER BY normalizar(temas.nome)
        """,
        (normalizar(termo),),
    ).fetchall()


def procurar_tema_por_nome(nome):
    """O tema com exatamente este nome (ignorando acentos e maiúsculas), ou None."""
    bd = obter_ligacao()
    return bd.execute(
        "SELECT id, nome FROM temas WHERE normalizar(nome) = ?",
        (normalizar(nome),),
    ).fetchone()


def criar_tema(nome, categoria="Outros"):
    """Cria um tema novo e devolve o id que a base de dados lhe deu."""
    bd = obter_ligacao()
    momento = agora()
    cursor = bd.execute(
        """
        INSERT INTO temas (nome, categoria_id, criado_em, alterado_em)
        VALUES (?, (SELECT id FROM categorias WHERE nome = ?), ?, ?)
        """,
        (nome, categoria, momento, momento),
    )
    bd.commit()
    return cursor.lastrowid


def obter_tema(tema_id):
    """Um tema pelo id, com o nome da categoria, ou None se não existir."""
    bd = obter_ligacao()
    return bd.execute(
        """
        SELECT temas.*, categorias.nome AS categoria
        FROM temas
        JOIN categorias ON categorias.id = temas.categoria_id
        WHERE temas.id = ?
        """,
        (tema_id,),
    ).fetchone()


# ---------- Entradas ----------

def listar_entradas(tema_id):
    """Entradas de um tema, das mais recentes para as mais antigas."""
    bd = obter_ligacao()
    # Ordenamos também pelo id para desempatar entradas do mesmo segundo
    return bd.execute(
        "SELECT * FROM entradas WHERE tema_id = ? ORDER BY criado_em DESC, id DESC",
        (tema_id,),
    ).fetchall()


def acrescentar_entrada(tema_id, texto, tipo="nota"):
    """Guarda uma entrada nova e atualiza a data de alteração do tema."""
    bd = obter_ligacao()
    momento = agora()
    bd.execute(
        "INSERT INTO entradas (tema_id, texto, tipo, criado_em) VALUES (?, ?, ?, ?)",
        (tema_id, texto, tipo, momento),
    )
    bd.execute("UPDATE temas SET alterado_em = ? WHERE id = ?", (momento, tema_id))
    bd.commit()
