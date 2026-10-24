"""
Tudo o que mexe na base de dados SQLite está neste ficheiro.

A ideia é o app.py nunca escrever SQL diretamente: pede as coisas
a estas funções (procurar temas, criar tema, etc.) e elas tratam do resto.

A base de dados vive na memória, aberta pelo cofre.py. Sempre que algo muda,
guardar() encripta-a e grava-a no disco.
"""

import sqlite3
import unicodedata
from datetime import datetime

import cofre

# Número de cores disponíveis para as categorias (definidas no estilo.css)
NUMERO_CORES = 8

# Esquema completo das tabelas.
# "IF NOT EXISTS" faz com que isto possa correr sempre que o cofre abre
# sem estragar o que já lá está.
# ON DELETE SET NULL: se apagares uma categoria, os temas ficam "sem categoria".
ESQUEMA = """
CREATE TABLE IF NOT EXISTS categorias (
    id   INTEGER PRIMARY KEY AUTOINCREMENT,
    nome TEXT NOT NULL UNIQUE,
    cor  INTEGER NOT NULL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS temas (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    nome         TEXT NOT NULL UNIQUE,
    categoria_id INTEGER REFERENCES categorias(id) ON DELETE SET NULL,
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
    """A base de dados aberta pelo cofre."""
    return cofre.ligacao()


def guardar():
    """Confirma as alterações e grava o cofre encriptado no disco."""
    obter_ligacao().commit()
    cofre.gravar()


def preparar():
    """
    Chamado uma vez, logo a seguir a abrir o cofre.
    Configura a ligação, cria as tabelas e atualiza bases de dados antigas.
    """
    bd = obter_ligacao()
    # Permite ler colunas pelo nome: linha["nome"] em vez de linha[1]
    bd.row_factory = sqlite3.Row
    # Ensinamos ao SQLite a nossa função normalizar(), para a usar no SQL
    bd.create_function("normalizar", 1, normalizar, deterministic=True)
    bd.executescript(ESQUEMA)
    _atualizar_estrutura_antiga(bd)
    # O SQLite só respeita as ligações entre tabelas se pedirmos
    bd.execute("PRAGMA foreign_keys = ON")
    guardar()


def _atualizar_estrutura_antiga(bd):
    """
    As fases 1 e 2 criaram as tabelas de forma um pouco diferente.
    Isto chama-se "migração": muda a estrutura sem perder os dados.
    """
    colunas_categorias = [c["name"] for c in bd.execute("PRAGMA table_info(categorias)")]
    if "cor" not in colunas_categorias:
        bd.execute("ALTER TABLE categorias ADD COLUMN cor INTEGER NOT NULL DEFAULT 0")
        bd.execute("UPDATE categorias SET cor = id % ?", (NUMERO_CORES,))

    # Antes, todos os temas tinham de ter categoria (NOT NULL).
    # O SQLite não deixa mudar isso numa coluna, por isso criamos a tabela
    # outra vez, copiamos os dados e trocamos. É o método que a documentação do SQLite recomenda.
    coluna = [c for c in bd.execute("PRAGMA table_info(temas)") if c["name"] == "categoria_id"][0]
    if coluna["notnull"]:
        bd.executescript(
            """
            PRAGMA foreign_keys = OFF;
            BEGIN;
            CREATE TABLE temas_nova (
                id           INTEGER PRIMARY KEY AUTOINCREMENT,
                nome         TEXT NOT NULL UNIQUE,
                categoria_id INTEGER REFERENCES categorias(id) ON DELETE SET NULL,
                criado_em    TEXT NOT NULL,
                alterado_em  TEXT NOT NULL
            );
            INSERT INTO temas_nova SELECT id, nome, categoria_id, criado_em, alterado_em FROM temas;
            DROP TABLE temas;
            ALTER TABLE temas_nova RENAME TO temas;
            COMMIT;
            """
        )


# ---------- Categorias ----------

def listar_categorias():
    """Todas as categorias por ordem alfabética, com o total de temas de cada uma."""
    bd = obter_ligacao()
    # LEFT JOIN para aparecerem também as categorias que ainda não têm temas
    return bd.execute(
        """
        SELECT categorias.id, categorias.nome, categorias.cor, COUNT(temas.id) AS total
        FROM categorias
        LEFT JOIN temas ON temas.categoria_id = categorias.id
        GROUP BY categorias.id
        ORDER BY normalizar(categorias.nome)
        """
    ).fetchall()


def contar_sem_categoria():
    bd = obter_ligacao()
    return bd.execute("SELECT COUNT(*) FROM temas WHERE categoria_id IS NULL").fetchone()[0]


def obter_categoria(categoria_id):
    """Uma categoria pelo id, ou None."""
    bd = obter_ligacao()
    return bd.execute("SELECT * FROM categorias WHERE id = ?", (categoria_id,)).fetchone()


def procurar_categoria_por_nome(nome):
    bd = obter_ligacao()
    return bd.execute(
        "SELECT * FROM categorias WHERE normalizar(nome) = ?", (normalizar(nome),)
    ).fetchone()


def criar_categoria(nome, cor=None):
    """Cria uma categoria e devolve o id. Se já existir com este nome, devolve a existente."""
    existente = procurar_categoria_por_nome(nome)
    if existente:
        return existente["id"]
    bd = obter_ligacao()
    if cor is None:
        # Sem cor escolhida, vai rodando pelas cores disponíveis
        total = bd.execute("SELECT COUNT(*) FROM categorias").fetchone()[0]
        cor = total % NUMERO_CORES
    cursor = bd.execute("INSERT INTO categorias (nome, cor) VALUES (?, ?)", (nome, cor))
    guardar()
    return cursor.lastrowid


def editar_categoria(categoria_id, nome, cor):
    bd = obter_ligacao()
    bd.execute("UPDATE categorias SET nome = ?, cor = ? WHERE id = ?", (nome, cor, categoria_id))
    guardar()


def apagar_categoria(categoria_id):
    """Apaga a categoria. Os temas ficam sem categoria por causa do ON DELETE SET NULL."""
    bd = obter_ligacao()
    bd.execute("DELETE FROM categorias WHERE id = ?", (categoria_id,))
    guardar()


# ---------- Temas ----------

# Parte comum a várias consultas de temas: junta a categoria (que pode não existir)
_SELECIONAR_TEMAS = """
    SELECT temas.*,
           categorias.nome AS categoria,
           categorias.cor  AS categoria_cor
    FROM temas
    LEFT JOIN categorias ON categorias.id = temas.categoria_id
"""


def procurar_temas(termo, categoria_id=None):
    """
    Temas cujo nome contém o termo, sem ligar a maiúsculas nem acentos.
    categoria_id: None = todas, 0 = só os temas sem categoria, outro = essa categoria.
    """
    bd = obter_ligacao()
    if categoria_id == 0:
        filtro, valores = "AND temas.categoria_id IS NULL", ()
    elif categoria_id:
        filtro, valores = "AND temas.categoria_id = ?", (categoria_id,)
    else:
        filtro, valores = "", ()

    # As duas subconsultas (SELECT COUNT...) contam as entradas e as tarefas por fazer de cada tema.
    # instr(a, b) diz em que posição o texto b aparece dentro de a (0 = não aparece).
    return bd.execute(
        f"""
        SELECT temas.*,
               categorias.nome AS categoria,
               categorias.cor  AS categoria_cor,
               (SELECT COUNT(*) FROM entradas WHERE tema_id = temas.id) AS total_entradas,
               (SELECT COUNT(*) FROM entradas
                 WHERE tema_id = temas.id AND tipo = 'tarefa' AND feito = 0) AS por_fazer
        FROM temas
        LEFT JOIN categorias ON categorias.id = temas.categoria_id
        WHERE instr(normalizar(temas.nome), ?) > 0 {filtro}
        ORDER BY normalizar(temas.nome)
        """,
        (normalizar(termo), *valores),
    ).fetchall()


def procurar_tema_por_nome(nome):
    """O tema com exatamente este nome (ignorando acentos e maiúsculas), ou None."""
    bd = obter_ligacao()
    return bd.execute(
        "SELECT id, nome FROM temas WHERE normalizar(nome) = ?",
        (normalizar(nome),),
    ).fetchone()


def criar_tema(nome, categoria_id):
    """Cria um tema novo e devolve o id que a base de dados lhe deu."""
    bd = obter_ligacao()
    momento = agora()
    cursor = bd.execute(
        "INSERT INTO temas (nome, categoria_id, criado_em, alterado_em) VALUES (?, ?, ?, ?)",
        (nome, categoria_id, momento, momento),
    )
    guardar()
    return cursor.lastrowid


def obter_tema(tema_id):
    """Um tema pelo id, com o nome e a cor da categoria, ou None se não existir."""
    bd = obter_ligacao()
    return bd.execute(_SELECIONAR_TEMAS + " WHERE temas.id = ?", (tema_id,)).fetchone()


def editar_tema(tema_id, nome, categoria_id):
    """Muda o nome e a categoria de um tema."""
    bd = obter_ligacao()
    bd.execute(
        "UPDATE temas SET nome = ?, categoria_id = ?, alterado_em = ? WHERE id = ?",
        (nome, categoria_id, agora(), tema_id),
    )
    guardar()


def apagar_tema(tema_id):
    """Apaga o tema. As entradas vão com ele por causa do ON DELETE CASCADE."""
    bd = obter_ligacao()
    bd.execute("DELETE FROM temas WHERE id = ?", (tema_id,))
    guardar()


def todos_os_temas_com_entradas():
    """
    Todos os temas, cada um com a lista das suas entradas.
    É o que o ligacoes.py precisa para comparar temas entre si.
    """
    bd = obter_ligacao()
    temas = {t["id"]: {"tema": t, "entradas": []} for t in bd.execute(_SELECIONAR_TEMAS)}
    for entrada in bd.execute("SELECT * FROM entradas ORDER BY criado_em DESC, id DESC"):
        temas[entrada["tema_id"]]["entradas"].append(entrada)
    return list(temas.values())


# ---------- Entradas ----------

def listar_entradas(tema_id):
    """Entradas de um tema, das mais recentes para as mais antigas."""
    bd = obter_ligacao()
    # Ordenamos também pelo id para desempatar entradas do mesmo segundo
    return bd.execute(
        "SELECT * FROM entradas WHERE tema_id = ? ORDER BY criado_em DESC, id DESC",
        (tema_id,),
    ).fetchall()


def obter_entrada(entrada_id):
    """Uma entrada pelo id, ou None."""
    bd = obter_ligacao()
    return bd.execute("SELECT * FROM entradas WHERE id = ?", (entrada_id,)).fetchone()


def _marcar_tema_alterado(bd, tema_id):
    """Qualquer mudança numa entrada conta como alteração do tema."""
    bd.execute("UPDATE temas SET alterado_em = ? WHERE id = ?", (agora(), tema_id))


def acrescentar_entrada(tema_id, texto, tipo="nota"):
    """Guarda uma entrada nova e atualiza a data de alteração do tema."""
    bd = obter_ligacao()
    bd.execute(
        "INSERT INTO entradas (tema_id, texto, tipo, criado_em) VALUES (?, ?, ?, ?)",
        (tema_id, texto, tipo, agora()),
    )
    _marcar_tema_alterado(bd, tema_id)
    guardar()


def editar_entrada(entrada, texto):
    """Muda o texto de uma entrada (recebe a linha que veio de obter_entrada)."""
    bd = obter_ligacao()
    bd.execute("UPDATE entradas SET texto = ? WHERE id = ?", (texto, entrada["id"]))
    _marcar_tema_alterado(bd, entrada["tema_id"])
    guardar()


def alternar_feito(entrada):
    """Tarefa feita passa a por fazer e vice-versa. "1 - feito" troca 0 por 1 e 1 por 0."""
    bd = obter_ligacao()
    bd.execute("UPDATE entradas SET feito = 1 - feito WHERE id = ?", (entrada["id"],))
    _marcar_tema_alterado(bd, entrada["tema_id"])
    guardar()


def apagar_entrada(entrada):
    """Apaga uma entrada."""
    bd = obter_ligacao()
    bd.execute("DELETE FROM entradas WHERE id = ?", (entrada["id"],))
    _marcar_tema_alterado(bd, entrada["tema_id"])
    guardar()
