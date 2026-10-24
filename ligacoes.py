"""
O "mentalista": encontra ligações escondidas entre os teus temas.

Corre tudo no teu computador. Nenhuma nota sai daqui.

Como pensa:
1. Parte o texto de cada tema em palavras importantes (sem "para", "como", etc.).
2. Dá mais valor às palavras raras. Se "frasco" só aparece em dois temas,
   isso diz muito sobre eles; se "loja" aparece em todos, não diz nada.
   (Em informática chama-se a isto TF-IDF.)
3. Dois temas que partilham palavras raras estão provavelmente ligados.
4. Se um tema refere o nome de outro, a ligação é ainda mais forte.
"""

import math
import re
from collections import Counter, defaultdict

from markupsafe import Markup, escape

from base_dados import normalizar

# Palavras que aparecem em todo o lado e não dizem nada sobre o assunto
# (português, inglês e alemão; as de menos de 4 letras já são ignoradas)
PALAVRAS_VAZIAS = {normalizar(p) for p in """
    para pelo pela pelos pelas como mais menos muito muita muitos muitas isso isto
    esse essa esses essas este esta estes estas aquele aquela aquilo sobre entre
    também quando onde porque qual quais quem minha minhas meus teus tuas nosso nossa
    eles elas dele dela deles delas lhes foram sido estar estou está estão estava
    tenho tens temos têm tinha fazer feito pode podem posso ainda depois antes agora
    sempre nunca cada todo toda todos todas outro outra outros outras mesmo mesma
    apenas assim então porém contudo coisa coisas desde durante aqui hoje amanhã ontem
    vezes será seria serão deve devem preciso precisa dizer vamos neste nesta nesse
    nessa disso disto deste desta desse dessa numa nuns numas qualquer algum alguma
    alguns algumas nenhum nenhuma tanto tanta quanto quanta fica ficar falar ver
    with this that from have will your about they them there their what when which
    would could should been were also into more some than then only just like
    eine einer einen einem eines dass wenn auch noch schon sind sein wird werden
    wurde haben hatte für über unter nach durch diese dieser dieses sich sehr kann
    können muss müssen immer alle alles nur mehr dann hier dort oder aber nicht
""".split()}


def raiz(palavra):
    """Junta singular e plural de forma simples: 'frascos' e 'frasco' contam como a mesma."""
    if len(palavra) > 4 and palavra.endswith("s"):
        return palavra[:-1]
    return palavra


def palavras_importantes(texto):
    """
    Devolve pares (raiz, palavra original) das palavras que interessam.
    A raiz serve para comparar; a original serve para mostrar no ecrã.
    """
    resultado = []
    for original in re.findall(r"\w+", texto.lower()):
        simples = normalizar(original)
        if len(simples) < 4 or simples.isdigit() or simples in PALAVRAS_VAZIAS:
            continue
        resultado.append((raiz(simples), original))
    return resultado


class Mentalista:
    """
    Lê o caderno inteiro uma vez e depois responde a perguntas sobre ligações.
    Uma "class" junta dados e as funções que trabalham com eles.
    """

    def __init__(self, dados):
        # dados vem de base_dados.todos_os_temas_com_entradas()
        self.por_id = {item["tema"]["id"]: item for item in dados}
        self.contadores = {}                 # tema_id -> Counter das raízes
        self.formas = defaultdict(Counter)   # raiz -> como a escreveste (para mostrar)

        for tema_id, item in self.por_id.items():
            contador = Counter()
            # O nome do tema conta a triplicar: diz mais do que uma nota solta
            for r, original in palavras_importantes(item["tema"]["nome"]):
                contador[r] += 3
                self.formas[r][original] += 1
            for entrada in item["entradas"]:
                for r, original in palavras_importantes(entrada["texto"]):
                    contador[r] += 1
                    self.formas[r][original] += 1
            self.contadores[tema_id] = contador

        # Raridade de cada palavra: quanto menos temas a usam, mais vale
        total = len(self.contadores)
        em_quantos = Counter()
        for contador in self.contadores.values():
            em_quantos.update(contador.keys())
        self.raridade = {r: math.log(1 + total / n) for r, n in em_quantos.items()}

    def forma_bonita(self, r):
        """A forma mais usada de uma palavra, com acentos: 'maca' -> 'maçã'."""
        return self.formas[r].most_common(1)[0][0] if self.formas[r] else r

    def _mencoes(self, de_id, para_id):
        """Entradas do tema de_id que escrevem o nome do tema para_id."""
        nome = normalizar(self.por_id[para_id]["tema"]["nome"])
        return [e for e in self.por_id[de_id]["entradas"] if nome in normalizar(e["texto"])]

    def ligacoes(self, tema_id, maximo=5):
        """Os temas mais ligados a este, do mais forte para o mais fraco."""
        meu = self.contadores[tema_id]
        meu_nome = {r for r, _ in palavras_importantes(self.por_id[tema_id]["tema"]["nome"])}
        resultado = []

        for outro_id, contador in self.contadores.items():
            if outro_id == tema_id:
                continue
            # Peso de cada palavra em comum: rara e repetida nos dois vale mais
            pesos = {
                r: self.raridade[r] * math.sqrt(min(meu[r], contador[r]))
                for r in meu.keys() & contador.keys()
            }
            mencoes = self._mencoes(outro_id, tema_id) + self._mencoes(tema_id, outro_id)
            pontuacao = sum(pesos.values()) + 4 * len(mencoes)
            if pontuacao == 0:
                continue

            # As pistas não incluem os nomes dos dois temas: isso já se vê no ecrã
            nomes = meu_nome | {r for r, _ in palavras_importantes(self.por_id[outro_id]["tema"]["nome"])}
            chave = sorted((r for r in pesos if r not in nomes), key=pesos.get, reverse=True)[:6]
            # Entradas do outro tema onde a ligação se vê
            exemplos = [
                e for e in self.por_id[outro_id]["entradas"]
                if {r for r, _ in palavras_importantes(e["texto"])} & set(chave)
            ][:2]

            resultado.append({
                "tema": self.por_id[outro_id]["tema"],
                "pontuacao": pontuacao,
                "palavras": [self.forma_bonita(r) for r in chave],
                "raizes": set(chave),
                "mencionado": bool(mencoes),
                "exemplos": exemplos,
            })

        resultado.sort(key=lambda l: l["pontuacao"], reverse=True)
        resultado = resultado[:maximo]

        # Força de 0 a 100 para desenhar a barra (o mais forte é a referência)
        if resultado:
            maior = resultado[0]["pontuacao"]
            for ligacao in resultado:
                ligacao["forca"] = max(8, round(100 * ligacao["pontuacao"] / maior))
        return resultado

    def ligar_texto_externo(self, texto, tema_id):
        """
        Para um texto de fora (um artigo da web) encontrado a partir de um tema:
        que palavras dele já existem no teu caderno, e em que OUTROS temas.
        Devolve o texto com essas palavras marcadas e a lista das ligações.
        """
        # O nome do tema não é pista: claro que o artigo fala dele
        ignoradas = {r for r, _ in palavras_importantes(self.por_id[tema_id]["tema"]["nome"])}
        marcadas = set()   # palavras que também estão nas tuas notas (ficam a amarelo)
        outros = {}        # palavra -> outros temas onde aparece (são as pistas)
        for r, _ in palavras_importantes(texto):
            if r in ignoradas or r in marcadas:
                continue
            ids = [i for i, c in self.contadores.items() if r in c]
            if ids:
                marcadas.add(r)
            temas = [self.por_id[i]["tema"] for i in ids if i != tema_id]
            if temas:
                outros[r] = temas

        # Ordena da palavra mais rara para a mais comum
        ordem = sorted(outros, key=lambda r: self.raridade.get(r, 0), reverse=True)
        ligacoes = [{"palavra": self.forma_bonita(r), "temas": outros[r]} for r in ordem[:5]]
        return destacar(texto, marcadas), ligacoes


def destacar(texto, raizes):
    """
    Devolve o texto em HTML com <mark> à volta das palavras cujas raízes estão no conjunto.
    escape() protege contra HTML escondido no texto; Markup diz ao Jinja que já é seguro.
    """
    partes = []
    for bocado in re.split(r"(\w+)", texto):
        if bocado and re.fullmatch(r"\w+", bocado) and raiz(normalizar(bocado)) in raizes:
            partes.append(Markup("<mark>{}</mark>").format(bocado))
        else:
            partes.append(escape(bocado))
    return Markup("").join(partes)
