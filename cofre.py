"""
Encriptação do caderno.

Como funciona:
- No disco só existe o ficheiro caderno.cofre, encriptado.
- Quando desbloqueias com a palavra-passe, o ficheiro é desencriptado para a
  memória (RAM) e a base de dados SQLite trabalha lá. A versão legível nunca
  é escrita no disco.
- Depois de cada alteração, a base de dados inteira volta a ser encriptada
  e gravada no disco.

A palavra-passe não é guardada em lado nenhum. Se a esqueceres, ninguém
(nem tu, nem eu) consegue recuperar os dados. É esse o objetivo.
"""

import base64
import os
import sqlite3
import time
from pathlib import Path

from cryptography.fernet import Fernet, InvalidToken
from cryptography.hazmat.primitives.kdf.scrypt import Scrypt

PASTA = Path(__file__).parent
CAMINHO_COFRE = PASTA / "caderno.cofre"
# Base de dados das fases anteriores, ainda sem encriptação
CAMINHO_ANTIGO = PASTA / "caderno.db"
CAMINHO_ANTIGO_RENOMEADO = PASTA / "caderno-antigo-NAO-ENCRIPTADO.db"

# Os primeiros bytes do ficheiro, para reconhecermos que é um cofre nosso
CABECALHO = b"CADERNO1"
TAMANHO_SAL = 16

# Bloqueia sozinho ao fim de 15 minutos sem usares a aplicação
MINUTOS_ATE_BLOQUEAR = 15


class PalavraPasseErrada(Exception):
    """Lançada quando a palavra-passe não abre o cofre."""


# Estado enquanto a aplicação corre. Só existe na memória.
_ligacao = None       # a base de dados desencriptada
_fernet = None        # a "chave" que encripta e desencripta
_sal = None           # valor aleatório guardado no ficheiro (explicado em _derivar_chave)
_ultimo_uso = 0.0


def _derivar_chave(palavra_passe, sal):
    """
    Transforma a palavra-passe numa chave de encriptação.

    O Scrypt é lento e gasta memória de propósito: para ti demora uma fração
    de segundo, mas para quem quiser experimentar milhões de palavras-passe
    torna-se caríssimo. O "sal" é aleatório e garante que a mesma palavra-passe
    dá chaves diferentes em ficheiros diferentes.
    """
    kdf = Scrypt(salt=sal, length=32, n=2**15, r=8, p=1)
    chave = kdf.derive(palavra_passe.encode("utf-8"))
    return Fernet(base64.urlsafe_b64encode(chave))


def _nova_ligacao_em_memoria(dados=None):
    """Cria a base de dados na RAM; se vierem dados, carrega-os."""
    ligacao = sqlite3.connect(":memory:", check_same_thread=False)
    if dados:
        ligacao.deserialize(dados)
    else:
        # Uma base de dados acabada de criar ainda não tem nenhuma página,
        # e o SQLite recusa-se a convertê-la em bytes. Isto escreve a primeira.
        ligacao.execute("PRAGMA user_version = 1")
    return ligacao


# ---------- O que o resto da aplicação usa ----------

def existe_cofre():
    return CAMINHO_COFRE.exists()


def existe_caderno_antigo():
    return CAMINHO_ANTIGO.exists()


def desbloqueado():
    """True se o cofre está aberto e ainda não passou o tempo de inatividade."""
    if _ligacao is None:
        return False
    if time.time() - _ultimo_uso > MINUTOS_ATE_BLOQUEAR * 60:
        bloquear()
        return False
    return True


def marcar_uso():
    global _ultimo_uso
    _ultimo_uso = time.time()


def ligacao():
    """A base de dados aberta. Só chamar depois de confirmar desbloqueado()."""
    return _ligacao


def criar(palavra_passe):
    """
    Cria um cofre novo. Se existir o caderno.db antigo, as notas passam para
    dentro do cofre e o ficheiro antigo é renomeado (não é apagado, por segurança).
    """
    global _ligacao, _fernet, _sal
    _sal = os.urandom(TAMANHO_SAL)
    _fernet = _derivar_chave(palavra_passe, _sal)
    _ligacao = _nova_ligacao_em_memoria()

    if CAMINHO_ANTIGO.exists():
        # backup() copia uma base de dados inteira para outra
        antiga = sqlite3.connect(CAMINHO_ANTIGO)
        antiga.backup(_ligacao)
        antiga.close()

    marcar_uso()
    gravar()
    if CAMINHO_ANTIGO.exists():
        CAMINHO_ANTIGO.replace(CAMINHO_ANTIGO_RENOMEADO)


def abrir(palavra_passe):
    """Desencripta o cofre para a memória. Se a palavra-passe estiver errada, lança PalavraPasseErrada."""
    global _ligacao, _fernet, _sal
    conteudo = CAMINHO_COFRE.read_bytes()
    if not conteudo.startswith(CABECALHO):
        raise ValueError("O ficheiro caderno.cofre não é um cofre válido.")

    sal = conteudo[len(CABECALHO):len(CABECALHO) + TAMANHO_SAL]
    encriptado = conteudo[len(CABECALHO) + TAMANHO_SAL:]
    fernet = _derivar_chave(palavra_passe, sal)
    try:
        # O Fernet verifica a integridade: palavra-passe errada ou ficheiro
        # alterado por alguém dão sempre erro, nunca dados trocados
        dados = fernet.decrypt(encriptado)
    except InvalidToken:
        raise PalavraPasseErrada() from None

    _sal, _fernet = sal, fernet
    _ligacao = _nova_ligacao_em_memoria(dados)
    marcar_uso()


def gravar():
    """Encripta a base de dados inteira e grava-a no disco."""
    dados = _ligacao.serialize()
    conteudo = CABECALHO + _sal + _fernet.encrypt(dados)
    # Escrevemos primeiro num ficheiro temporário e só depois trocamos.
    # Se o computador se desligar a meio, o cofre antigo continua inteiro.
    temporario = CAMINHO_COFRE.with_suffix(".tmp")
    temporario.write_bytes(conteudo)
    temporario.replace(CAMINHO_COFRE)


def bloquear():
    """Esquece a chave e a base de dados desencriptada."""
    global _ligacao, _fernet, _sal
    if _ligacao is not None:
        _ligacao.close()
    _ligacao = _fernet = _sal = None
