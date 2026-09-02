"""Consulta e validação contra a base normativa.

Aqui mora a garantia central do produto: um laudo só passa se **toda** citação
que ele faz existir, palavra por palavra, num PDF oficial de NR e estiver
vigente na data da inspeção. Não é o modelo que decide isso — é código.
"""

import gzip
import json
import math
import re
import unicodedata
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import date
from functools import lru_cache
from pathlib import Path

CAMINHO_KB = Path(__file__).resolve().parent / "data" / "kb.json.gz"

# Hifens tipográficos que aparecem em texto gerado por LLM (NR‑18 com U+2011).
HIFENS = dict.fromkeys(map(ord, "‐‑‒–—―−"), "-")

PALAVRAS_VAZIAS = {
    "a", "o", "as", "os", "de", "da", "do", "das", "dos", "e", "ou", "em", "no",
    "na", "nos", "nas", "um", "uma", "para", "por", "com", "sem", "que", "ser",
    "deve", "devem", "seu", "sua", "ao", "aos", "as", "se", "sobre", "entre",
    "quando", "onde", "cada", "pelo", "pela", "este", "esta", "esse", "essa",
    "conforme", "desta", "nesta", "nr", "item", "subitem", "norma",
}


def desacentuar(texto: str) -> str:
    return "".join(
        c for c in unicodedata.normalize("NFKD", texto) if not unicodedata.combining(c)
    )


def normalizar(texto: str) -> str:
    return desacentuar(texto.translate(HIFENS)).lower()


RE_PALAVRA = re.compile(r"[a-z0-9]+")

PLURAIS = (("ais", "al"), ("eis", "el"), ("ois", "ol"), ("uis", "ul"),
           ("oes", "ao"), ("aes", "ao"), ("ns", "m"))


def radical(palavra: str) -> str:
    """Radical aproximado, só para casar singular com plural e masculino com feminino.

    Não é um stemmer de verdade — e nem precisa ser. Precisa apenas ser
    *consistente*: "materiais" e "material" têm de chegar ao mesmo radical, ou
    o roteador perde o risco. Era exatamente aí que ele falhava.
    """
    if len(palavra) > 4:
        for plural, singular in PLURAIS:
            if palavra.endswith(plural):
                palavra = palavra[: -len(plural)] + singular
                break
        else:
            if palavra.endswith("s"):
                palavra = palavra[:-1]
    elif len(palavra) == 4 and palavra.endswith("s"):
        # Plural de radical curto: "fios" tem 4 letras e a guarda de 5 o
        # deixava intacto, enquanto "fio" chegava como "fio" — dois radicais
        # diferentes para a mesma palavra. O sinal "fio desencapado" existe
        # justamente porque o Olho escreve "fios desencapados", e era esse o
        # par que não casava. Vale só para o "s" simples: aplicar PLURAIS aqui
        # transformaria "mais" em "mal".
        palavra = palavra[:-1]
    if len(palavra) > 4 and palavra[-1] in "aeo":
        palavra = palavra[:-1]
    return palavra


def radicais(texto: str) -> set[str]:
    return {radical(p) for p in RE_PALAVRA.findall(normalizar(texto)) if len(p) > 2}


def tokenizar(texto: str) -> list[str]:
    """Unigramas + bigramas.

    Em texto normativo o par de palavras é o que carrega o sentido: "abertura
    piso" e "abertura porta" compartilham o unigrama decisivo e significam
    coisas opostas. Indexar o bigrama, que tem IDF alto, separa os dois.
    """
    palavras = [
        t for t in re.findall(r"[a-z0-9]{3,}", normalizar(texto))
        if t not in PALAVRAS_VAZIAS
    ]
    bigramas = [f"{a}_{b}" for a, b in zip(palavras, palavras[1:])]
    return palavras + bigramas


# ---------------------------------------------------------------------------
# Modelo de dados
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class Item:
    nr: str
    item: str
    id: str
    texto: str
    anexo: str | None
    capitulo: str
    vigencia_inicio: str | None
    vigencia_fim: str | None
    revogado: bool
    tipo: str
    fonte: str

    def vigente_em(self, quando: date) -> bool:
        if self.revogado:
            return False
        if self.vigencia_inicio and quando < date.fromisoformat(self.vigencia_inicio):
            return False
        if self.vigencia_fim and quando > date.fromisoformat(self.vigencia_fim):
            return False
        return True

    def citacao(self) -> str:
        return f"{self.nr}, item {self.item}"

    def resumo(self, limite: int = 320) -> str:
        t = self.texto
        return t if len(t) <= limite else t[: limite - 1].rstrip() + "…"


@dataclass
class Problema:
    """Uma reprovação encontrada pelo validador."""

    tipo: str            # "citacao_inexistente" | "fora_de_vigencia" | ...
    detalhe: str
    trecho: str = ""
    sugestao: str = ""

    def __str__(self) -> str:
        base = f"[{self.tipo}] {self.detalhe}"
        return f"{base} → {self.sugestao}" if self.sugestao else base


# ---------------------------------------------------------------------------
# Base
# ---------------------------------------------------------------------------

class BaseNormativa:
    """Índice em memória dos itens das NRs, com busca BM25.

    Uma NR pode ter mais de uma edição no acervo. Qual delas vale não é a mais
    recente, e sim a que está em vigor na data da inspeção: a NR-10 publicada em
    2026 só vigora a partir de 01/06/2027 e renumerou a norma, de modo que citar
    seus itens hoje daria número certo com o texto errado.
    """

    def __init__(self, dados: dict, referencia: date | None = None):
        self.gerado_em: str = dados.get("gerado_em", "")
        self.impressao_digital: str = dados.get("impressao_digital", "")
        self.pdfs_ignorados: list[str] = list(dados.get("pdfs_ignorados", []))
        self.referencia: date = referencia or date.today()
        self.itens: dict[str, Item] = {}
        self.por_nr: dict[str, list[Item]] = {}
        self.edicoes: dict[str, str] = {}
        self.edicoes_futuras: dict[str, tuple[str, str]] = {}

        for nr, bloco in dados["normas"].items():
            escolhida, futura = self._escolher_edicao(bloco["edicoes"], self.referencia)
            if escolhida is None:
                continue
            self.edicoes[nr] = escolhida["fonte"]
            if futura is not None:
                self.edicoes_futuras[nr] = (futura["fonte"], futura["vigencia_inicio"])
            lista: list[Item] = []
            for cru in escolhida["itens"]:
                item = Item(**{k: cru[k] for k in Item.__dataclass_fields__ if k in cru})
                self.itens[self._chave(item.nr, item.item)] = item
                lista.append(item)
            self.por_nr[nr] = lista

        self._construir_indice()

    @staticmethod
    def _escolher_edicao(
        edicoes: list[dict], quando: date
    ) -> tuple[dict | None, dict | None]:
        """A edição em vigor na data, e a próxima que ainda vai entrar em vigor."""
        def inicio(edicao: dict) -> date:
            bruto = edicao.get("vigencia_inicio")
            return date.fromisoformat(bruto) if bruto else date.min

        ordenadas = sorted(edicoes, key=inicio)
        vigentes = [e for e in ordenadas if inicio(e) <= quando]
        futuras = [e for e in ordenadas if inicio(e) > quando]
        # Se todas ainda são futuras, usamos a mais próxima: melhor a norma que
        # vem por aí do que nenhuma norma.
        escolhida = vigentes[-1] if vigentes else (futuras[0] if futuras else None)
        proxima = futuras[0] if (vigentes and futuras) else None
        return escolhida, proxima

    # -- infraestrutura de busca -------------------------------------------

    def _construir_indice(self) -> None:
        self._docs: list[Item] = [i for i in self.itens.values() if i.tipo == "item"]
        self._tokens: list[list[str]] = [tokenizar(i.texto) for i in self._docs]
        self._tam_medio = (sum(len(t) for t in self._tokens) / len(self._tokens)) if self._tokens else 1.0
        self._df: dict[str, int] = {}
        for toks in self._tokens:
            for t in set(toks):
                self._df[t] = self._df.get(t, 0) + 1
        self._n = max(len(self._docs), 1)

    @staticmethod
    def _chave(nr: str, item: str) -> str:
        return f"{nr}|{normalizar(item).replace(' ', '')}"

    # -- consulta -----------------------------------------------------------

    def obter(self, nr: str, item: str) -> Item | None:
        return self.itens.get(self._chave(nr, item))

    def titulo_da_secao(self, item: Item) -> str:
        """Cabeçalho da seção que contém o item, ou "" se a norma não o trouxer.

        O rótulo é hierárquico ("18.9.4.2", "Anexo II 3.2.1"): subir um nível de
        cada vez e perguntar à base devolve o cabeçalho mais próximo. É o que
        permite saber que o Anexo II 1.1 da NR-35 mora em "Objetivo" — e que,
        portanto, ele diz do que o anexo trata em vez de impor conduta.
        """
        prefixo, _, numero = (
            item.item.rpartition(" ") if item.anexo else ("", "", item.item)
        )
        partes = numero.split(".")
        for corte in range(len(partes) - 1, 0, -1):
            rotulo = f"{prefixo} {'.'.join(partes[:corte])}".strip()
            pai = self.obter(item.nr, rotulo)
            # Cabeçalho é curto; ancestral longo é item normativo de verdade e a
            # busca continua subindo.
            if pai is not None and len(pai.texto) <= 90:
                return pai.texto
        return ""

    def nrs_carregadas(self) -> list[str]:
        return sorted(self.por_nr)

    def buscar(self, consulta, nrs=None, k=8, quando=None, minimo_relativo=0.0):
        return [item for item, _ in self.buscar_pontuado(consulta, nrs, k, quando, minimo_relativo)]

    def buscar_pontuado(
        self,
        consulta: str,
        nrs: list[str] | None = None,
        k: int = 8,
        quando: date | None = None,
        minimo_relativo: float = 0.0,
        aceitar: Callable[[Item], bool] | None = None,
    ) -> list[tuple[Item, float]]:
        """Recupera os `k` itens mais pertinentes à consulta (BM25 Okapi).

        `minimo_relativo` descarta o que pontuar abaixo dessa fração do melhor
        resultado — é o que impede o dossiê de encher de item vagamente parecido.

        `aceitar` peneira os candidatos **antes** do corte relativo. A ordem
        importa: um item recusado que ficasse no topo levantaria a régua e
        derrubaria, junto consigo, os itens bons abaixo dele — foi o que
        aconteceu com o objetivo do Anexo II da NR-35, que sozinho pontuava mais
        que o dobro do item de ancoragem que devia ter sido oferecido.
        """
        termos = tokenizar(consulta)
        if not termos:
            return []
        permitidas = set(nrs) if nrs else None
        k1, b = 1.4, 0.45
        pontuados: list[tuple[float, Item]] = []

        for doc, toks in zip(self._docs, self._tokens):
            if permitidas is not None and doc.nr not in permitidas:
                continue
            if quando is not None and not doc.vigente_em(quando):
                continue
            if aceitar is not None and not aceitar(doc):
                continue
            if not toks:
                continue
            freq: dict[str, int] = {}
            for t in toks:
                freq[t] = freq.get(t, 0) + 1
            score = 0.0
            for termo in termos:
                f = freq.get(termo, 0)
                if not f:
                    continue
                idf = math.log(1 + (self._n - self._df.get(termo, 0) + 0.5) / (self._df.get(termo, 0) + 0.5))
                score += idf * (f * (k1 + 1)) / (f + k1 * (1 - b + b * len(toks) / self._tam_medio))
            if score > 0:
                pontuados.append((score, doc))

        pontuados.sort(key=lambda p: (-p[0], p[1].id))
        if not pontuados:
            return []
        corte = pontuados[0][0] * minimo_relativo
        return [(item, s) for s, item in pontuados[:k] if s >= corte]


@lru_cache(maxsize=8)
def carregar_base(caminho: str | None = None, referencia: date | None = None) -> BaseNormativa:
    """Base normativa em vigor na data de referência (por padrão, hoje)."""
    alvo = Path(caminho) if caminho else CAMINHO_KB
    if not alvo.exists():
        # Numa implantação limpa a base pode não ter vindo junto; se os PDFs
        # oficiais estiverem no repositório, reconstruímos em vez de falhar.
        from .kb_build import construir, gravar, localizar_pdfs

        if caminho is None and localizar_pdfs():
            gravar(construir(verboso=False), alvo)
        else:
            raise FileNotFoundError(
                f"Base normativa não encontrada em {alvo} e nenhum PDF de NR disponível. "
                "Coloque os PDFs oficiais em `normas/` e rode `python -m auditoria.kb_build`."
            )
    with gzip.open(alvo, "rt", encoding="utf-8") as fh:
        dados = json.load(fh)

    # Acervo mudou desde a última construção? Reconstrói, para que subir um PDF
    # novo baste — sem ninguém precisar lembrar de rodar o kb_build.
    if caminho is None:
        from .kb_build import construir, gravar, impressao_digital

        if dados.get("impressao_digital") and dados["impressao_digital"] != impressao_digital():
            dados = construir(verboso=False)
            try:
                gravar(dados, alvo)
            except OSError:
                # Em hospedagem com disco somente-leitura não dá para persistir;
                # a base reconstruída em memória serve para esta execução.
                pass

    return BaseNormativa(dados, referencia)


# ---------------------------------------------------------------------------
# Extração de citações do texto do laudo
# ---------------------------------------------------------------------------

RE_ANEXO_CIT = re.compile(
    r"NR[\s\-]?(\d{1,2})[^\n]{0,40}?anexo\s+([ivxlc]+|\d{1,2})"
    r"[\s,;:–-]*(?:sub)?(?:item\s*)?(\d{1,2}(?:\.\d{1,3})*)",
    re.IGNORECASE,
)
RE_ITEM_CIT = re.compile(r"(?<![\d,.])(\d{1,2}(?:\.\d{1,3}){1,4})(?![\d.])")
RE_UNIDADE = re.compile(r"^\s*(m|mm|cm|km|kg|kgf|%|°|h|min|s|v|kv|a|w|mpa)\b", re.IGNORECASE)
RE_NR_MENCIONADA = re.compile(r"NR[\s\-]?(\d{1,2})\b", re.IGNORECASE)


@dataclass(frozen=True)
class Citacao:
    nr: str
    item: str
    bruto: str

    @property
    def id(self) -> str:
        return f"{self.nr} {self.item}"


def extrair_citacoes(texto: str) -> list[Citacao]:
    """Encontra toda referência normativa que o laudo faz.

    A raiz do número identifica a NR sem ambiguidade (18.9.2 pertence à NR-18),
    então não dependemos de o modelo escrever "NR-18" grudado no item.
    """
    limpo = texto.translate(HIFENS)
    achadas: dict[str, Citacao] = {}

    for m in RE_ANEXO_CIT.finditer(limpo):
        nr = f"NR-{int(m.group(1)):02d}"
        item = f"Anexo {m.group(2).upper()} {m.group(3)}"
        c = Citacao(nr, item, m.group(0))
        achadas[c.id] = c

    consumidos = {m.span(3) for m in RE_ANEXO_CIT.finditer(limpo)}

    for m in RE_ITEM_CIT.finditer(limpo):
        if m.span() in consumidos:
            continue
        numero = m.group(1)
        raiz = int(numero.split(".")[0])
        if not 1 <= raiz <= 38:
            continue
        if RE_UNIDADE.match(limpo[m.end(): m.end() + 8]):
            continue                                  # "1.20 m" é medida, não item
        if limpo[max(0, m.start() - 2): m.start()].strip().endswith(("R$", "$")):
            continue
        c = Citacao(f"NR-{raiz:02d}", numero, m.group(0))
        achadas.setdefault(c.id, c)

    return sorted(achadas.values(), key=lambda c: (c.nr, c.item))


def nrs_mencionadas(texto: str) -> set[str]:
    return {
        f"NR-{int(m.group(1)):02d}"
        for m in RE_NR_MENCIONADA.finditer(texto.translate(HIFENS))
        if 1 <= int(m.group(1)) <= 38
    }
