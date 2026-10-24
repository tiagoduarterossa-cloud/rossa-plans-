"""
Pesquisa na Wikipédia.

Só o NOME do tema é enviado, e só quando carregas no botão.
As tuas notas nunca saem do computador.

Usa só a biblioteca padrão do Python (urllib): não é preciso instalar nada.
"""

import json
import urllib.error
import urllib.parse
import urllib.request

LINGUAS = {"pt": "Português", "en": "English", "de": "Deutsch"}

# A Wikipédia pede que cada programa se identifique
CABECALHOS = {"User-Agent": "CadernoPessoal/1.0 (aplicacao local de notas)"}

TAMANHO_MAXIMO_RESUMO = 450


class ErroWeb(Exception):
    """Sem internet, Wikipédia em baixo, ou resposta estranha."""


def _encurtar(texto):
    """Corta o texto no fim de uma frase (ou palavra) antes de TAMANHO_MAXIMO_RESUMO."""
    if len(texto) <= TAMANHO_MAXIMO_RESUMO:
        return texto
    corte = texto[:TAMANHO_MAXIMO_RESUMO]
    fim_frase = corte.rfind(". ")
    if fim_frase > TAMANHO_MAXIMO_RESUMO // 2:
        return corte[:fim_frase + 1]
    return corte[:corte.rfind(" ")] + "…"


def procurar(termo, lingua="pt", limite=5):
    """Devolve uma lista de artigos: título, resumo e endereço."""
    if lingua not in LINGUAS:
        lingua = "pt"

    # Um só pedido que pesquisa E traz o início de cada artigo
    parametros = {
        "action": "query",
        "format": "json",
        "formatversion": 2,
        "generator": "search",
        "gsrsearch": termo,
        "gsrlimit": limite,
        "prop": "extracts|info",
        "exintro": 1,
        "explaintext": 1,
        "exlimit": limite,
        "inprop": "url",
        "redirects": 1,
    }
    url = f"https://{lingua}.wikipedia.org/w/api.php?" + urllib.parse.urlencode(parametros)
    pedido = urllib.request.Request(url, headers=CABECALHOS)

    try:
        # timeout: se em 8 segundos não responder, desistimos
        with urllib.request.urlopen(pedido, timeout=8) as resposta:
            dados = json.load(resposta)
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as erro:
        raise ErroWeb("Não consegui falar com a Wikipédia. Tens internet?") from erro

    paginas = dados.get("query", {}).get("pages", [])
    # "index" é a ordem de relevância que a Wikipédia deu
    paginas.sort(key=lambda p: p.get("index", 0))
    return [
        {
            "titulo": p["title"],
            "resumo": _encurtar(p["extract"].strip()),
            "url": p.get("fullurl", ""),
        }
        for p in paginas
        if p.get("extract", "").strip()
    ]
