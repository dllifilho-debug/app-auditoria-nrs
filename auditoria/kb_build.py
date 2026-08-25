"""Constrói a base de conhecimento normativa a partir dos PDFs oficiais das NRs.

Uso:
    python -m auditoria.kb_build            # lê ./normas/*.pdf (ou ./*.pdf) e grava auditoria/data/kb.json.gz

O objetivo é simples e inegociável: o aplicativo só pode citar um item de NR que
exista, palavra por palavra, num PDF oficial. Tudo que o modelo escrever é
conferido contra o que sai daqui.
"""

import gzip
import json
import os
import re
import sys
import unicodedata
from collections import Counter
from dataclasses import asdict, dataclass, field
from datetime import date
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
DESTINO = Path(__file__).resolve().parent / "data" / "kb.json.gz"

RODAPES = (
    "Este texto não substitui o publicado no DOU",
    "Este texto não substitui o publicado no D.O.U",
)

MESES = {
    "janeiro": 1, "fevereiro": 2, "março": 3, "marco": 3, "abril": 4,
    "maio": 5, "junho": 6, "julho": 7, "agosto": 8, "setembro": 9,
    "outubro": 10, "novembro": 11, "dezembro": 12,
}

# Um item começa numa linha do tipo "18.9.4.2 A proteção..." ou "3.2.a) ..."
RE_ITEM = re.compile(r"^(\d{1,2}(?:\.\d{1,3})+)\.?\s+(\S.*)$")
# Os PDFs oficiais usam quatro grafias: "ANEXO I", "ANEXO Nº 13-A", "ANEXO "A""
# e "ANEXO (*)". Só a primeira era reconhecida, e por isso os itens dos demais
# anexos caíam no corpo da norma e colidiam entre si.
RE_ANEXO = re.compile(
    r"^\s*ANEXO\s*(?:N[º°.\s]*)?"
    r"(?:[\u201c\"']\s*([A-Z])\s*[\u201d\"']|([IVXLC]+(?:-[A-Z])?)|(\d+(?:-[A-Z])?)|(\(\*\)))"
    r"(?=\s|$|[-–—:.])",
    re.IGNORECASE,
)
RE_ALINEA = re.compile(r"^\s*([a-z])\)\s+(\S.*)$")

# Palavras curtas legítimas do português — nunca são fragmento de palavra quebrada.
STOPWORDS_CURTAS = {
    "a", "à", "às", "as", "ao", "aos", "o", "os", "e", "é", "em", "um", "uma",
    "de", "da", "do", "das", "dos", "na", "no", "nas", "nos", "por", "para",
    "com", "sem", "sob", "se", "que", "não", "já", "há", "ou", "ser", "ter",
    "seu", "sua", "até", "mas", "mais", "nem", "lhe", "ele", "ela", "seus",
    "seja", "são", "foi", "pelo", "pela", "isso", "este", "esta", "esse",
}


@dataclass
class ItemNorma:
    """Um item numerado de uma Norma Regulamentadora."""

    nr: str                      # "NR-18"
    item: str                    # "18.9.2" ou "Anexo II 3.2"
    id: str                      # "NR-18 18.9.2"  (chave canônica de citação)
    texto: str                   # texto verbatim do PDF
    anexo: str | None = None     # "II" quando o item vive num anexo
    capitulo: str = ""           # título da seção pai, ex.: "18.9"
    vigencia_inicio: str | None = None   # ISO date
    vigencia_fim: str | None = None      # ISO date
    revogado: bool = False
    tipo: str = "item"           # "item" (comando normativo) | "titulo" (cabeçalho de seção)
    fonte: str = ""              # nome do PDF de origem
    tags: list[str] = field(default_factory=list)

    def vigente_em(self, quando: date) -> bool:
        if self.revogado:
            return False
        if self.vigencia_inicio and quando < date.fromisoformat(self.vigencia_inicio):
            return False
        if self.vigencia_fim and quando > date.fromisoformat(self.vigencia_fim):
            return False
        return True


# --------------------------------------------------------------------------
# Limpeza do texto extraído do PDF
# --------------------------------------------------------------------------

def _remover_rodapes(linhas: list[str]) -> list[str]:
    return [ln for ln in linhas if not any(r in ln for r in RODAPES)]


def _vocabulario(texto: str) -> Counter:
    return Counter(re.findall(r"[a-zà-úA-ZÀ-Ú]{2,}", texto.lower()))


def _corrigir_quebras(texto: str, vocab: Counter) -> str:
    """Junta palavras que o extrator de PDF partiu ao meio ("instalaçã o" -> "instalação").

    Heurística movida a dados: só junta quando (a) a forma unida é uma palavra
    de fato recorrente no corpus da própria norma, (b) é bem mais frequente que
    o lado mais raro do par, e (c) esse lado raro quase não existe sozinho —
    sinal de que é fragmento, não palavra. Assim "instalaçã o" vira "instalação"
    mas "de acordo" nunca vira "deacordo".
    """

    def junta(m: re.Match) -> str:
        w1, w2 = m.group(1), m.group(2)
        b1, b2 = w1.lower(), w2.lower()
        if b1 in STOPWORDS_CURTAS and b2 in STOPWORDS_CURTAS:
            return m.group(0)
        f1, f2, f_unido = vocab[b1], vocab[b2], vocab[b1 + b2]
        raro = min(f1, f2)
        if f_unido >= 3 and raro <= 3 and f_unido > 3 * raro:
            return w1 + w2
        return m.group(0)

    # Pares alfabéticos adjacentes em que pelo menos um lado é curto o bastante
    # para ser um fragmento de palavra.
    padrao = re.compile(r"\b([a-zà-ÿ]{1,6})\s([a-zà-ÿ]{1,20})\b|\b([a-zà-ÿ]{1,20})\s([a-zà-ÿ]{1,6})\b")

    def despacha(m: re.Match) -> str:
        g = m.groups()
        w1, w2 = (g[0], g[1]) if g[0] is not None else (g[2], g[3])
        return junta(re.match(r"(\S+) (\S+)", f"{w1} {w2}"))

    anterior = None
    while anterior != texto:
        anterior = texto
        texto = padrao.sub(despacha, texto)
    return texto


def _normalizar(texto: str) -> str:
    texto = texto.replace("­", "").replace("﻿", "")
    texto = re.sub(r"-\s*\n\s*", "", texto)          # hifenização de fim de linha
    texto = re.sub(r"[ \t]+", " ", texto)
    # Pronome enclítico que o extrator separa do verbo ("apresentar -se").
    texto = re.sub(
        r"(\w)\s+-\s*(se|lo|la|los|las|me|te|nos|vos|lhe|lhes|o|a|os|as)\b",
        r"\1-\2", texto,
    )
    texto = re.sub(r"\s+([,.;:)])", r"\1", texto)
    # Número de página que o extrator cola no fim do item: "…antiderrapantes. 2".
    texto = re.sub(r"(?<=[.;:])\s+\d{1,3}\s*$", "", texto)
    return texto.strip()


# --------------------------------------------------------------------------
# Vigência
# --------------------------------------------------------------------------

RE_DATA = re.compile(r"(\d{1,2})\s+de\s+([a-zç]+)\s+de\s+(\d{4})", re.IGNORECASE)
RE_VIGENTE_ATE = re.compile(r"reda[çc][ãa]o\s+vigente\s+at[ée]\s+(?:o\s+dia\s+)?(.{0,40}?\d{4})", re.IGNORECASE)
RE_ENTRA_VIGOR = re.compile(r"entra\s+em\s+vigor\s+(?:no\s+dia\s+|em\s+)?(.{0,40}?\d{4})", re.IGNORECASE)
RE_REVOGADO = re.compile(r"\(\s*revogad[oa]\b", re.IGNORECASE)
# Cláusula que difere a vigência da norma inteira, e não de um item:
# "(Vigência a partir de 01 de junho de 2027 - art. 5º, da Portaria MTE nº 737…)"
RE_TITULO_NORMA = re.compile(r"^\s*NR\s*-?\s*\d{1,2}\s*[-\u2013\u2014]\s*\S", re.MULTILINE)
RE_VIGENCIA_NORMA = re.compile(
    r"(?:vig[êe]ncia\s+a\s+partir\s+de|entra\s+em\s+vigor\s+(?:a\s+partir\s+)?(?:de|em)?)\s*(.{0,45}?\d{4})",
    re.IGNORECASE,
)


def _extrair_data(trecho: str) -> str | None:
    m = RE_DATA.search(trecho)
    if not m:
        return None
    dia, mes_txt, ano = int(m.group(1)), m.group(2).lower(), int(m.group(3))
    mes = MESES.get(unicodedata.normalize("NFKD", mes_txt).encode("ascii", "ignore").decode())
    if mes is None:
        mes = MESES.get(mes_txt)
    if mes is None:
        return None
    try:
        return date(ano, mes, dia).isoformat()
    except ValueError:
        return None


def _ler_vigencia(texto: str) -> tuple[str | None, str | None, bool]:
    inicio = fim = None
    if (m := RE_VIGENTE_ATE.search(texto)):
        fim = _extrair_data(m.group(1))
    if (m := RE_ENTRA_VIGOR.search(texto)):
        inicio = _extrair_data(m.group(1))
    return inicio, fim, bool(RE_REVOGADO.search(texto))


# --------------------------------------------------------------------------
# Parsing
# --------------------------------------------------------------------------

RE_NR_ARQUIVO = re.compile(r"nr[-_ ]?0?(\d{1,2})", re.IGNORECASE)
RE_ANO_ARQUIVO = re.compile(r"(20\d{2})")


def identificar_nr(nome_arquivo: str) -> tuple[str | None, int]:
    """Deduz o código da NR e o ano da edição a partir do nome do arquivo."""
    m = RE_NR_ARQUIVO.search(nome_arquivo)
    if not m:
        return None, 0
    numero = int(m.group(1))
    if not 1 <= numero <= 38:
        return None, 0
    anos = [int(a) for a in RE_ANO_ARQUIVO.findall(nome_arquivo)]
    # o primeiro número já foi consumido pelo código da NR; anos plausíveis só
    ano = max((a for a in anos if 2000 <= a <= 2100), default=0)
    return f"NR-{numero:02d}", ano


def ler_vigencia_da_norma(bruto: str) -> str | None:
    """Data em que a edição inteira passa a valer, quando a portaria a difere.

    A NR-10 de 2026, por exemplo, só vigora a partir de 01/06/2027 — e renumerou
    a norma. Citar seus itens antes disso daria número certo com texto de outra
    época, que é o pior tipo de erro que este projeto existe para evitar.
    """
    # A cláusula da norma vem colada ao título ("NR 10 - SEGURANÇA … (Vigência a
    # partir de 01 de junho de 2027)"). Procurar no cabeçalho inteiro pegaria,
    # por engano, a cláusula de um subitem citada no sumário — foi o que
    # aconteceu com a NR-13, cuja data pertence ao subitem 13.5.1.1.1.
    titulo = RE_TITULO_NORMA.search(bruto)
    if titulo is None:
        return None
    janela = bruto[titulo.start(): titulo.start() + 400]
    if (m := RE_VIGENCIA_NORMA.search(janela)):
        return _extrair_data(m.group(1))
    return None


def extrair_texto_pdf(caminho: Path) -> str:
    from pypdf import PdfReader

    leitor = PdfReader(str(caminho))
    return "\n".join((p.extract_text() or "") for p in leitor.pages)


def parsear_norma(nr: str, bruto: str, fonte: str) -> list[ItemNorma]:
    vocab = _vocabulario(bruto)
    linhas = _remover_rodapes(bruto.splitlines())

    numero_nr = int(nr.split("-")[1])

    itens: dict[str, ItemNorma] = {}
    anexo_atual: str | None = None
    numero_atual: str | None = None
    buffer: list[str] = []

    def fechar() -> None:
        nonlocal numero_atual, buffer
        if numero_atual is None:
            return
        texto = _normalizar(_corrigir_quebras(_normalizar(" ".join(buffer)), vocab))
        if len(texto) < 8:
            numero_atual, buffer = None, []
            return
        # Regra estrutural: no corpo da norma todo item começa pelo número da NR
        # (18.9.2 na NR-18). Dentro de um anexo a numeração recomeça do 1. Isso
        # torna a classificação imune a "ANEXO ..." aparecendo no sumário.
        raiz = int(numero_atual.split(".")[0])
        no_corpo = raiz == numero_nr and (anexo_atual is None or raiz != _numero_anexo(anexo_atual))
        anexo_do_item = None if no_corpo else anexo_atual
        rotulo = f"Anexo {anexo_do_item} {numero_atual}" if anexo_do_item else numero_atual
        chave = f"{nr} {rotulo}"
        inicio, fim, revogado = _ler_vigencia(texto)
        novo = ItemNorma(
            nr=nr, item=rotulo, id=chave, texto=texto, anexo=anexo_do_item,
            capitulo=numero_atual.rsplit(".", 1)[0] if "." in numero_atual else numero_atual,
            vigencia_inicio=inicio, vigencia_fim=fim, revogado=revogado,
            tipo=_classificar(texto), fonte=fonte,
        )
        anterior = itens.get(chave)
        # Sumário perde para o corpo: fica sempre a redação mais longa.
        if anterior is None or len(novo.texto) > len(anterior.texto):
            itens[chave] = novo
        numero_atual, buffer = None, []

    for linha in linhas:
        if (m := RE_ANEXO.match(linha)):
            fechar()
            rotulo = next(g for g in m.groups() if g)
            anexo_atual = "*" if rotulo == "(*)" else rotulo.upper()
            continue
        if (m := RE_ITEM.match(linha.strip())):
            # Texto legal começa em maiúscula. Uma linha como "18.9.4.1 ou
            # 18.9.4.2 desta NR;" é continuação de uma alínea da página
            # anterior, não a abertura de um item — o minúsculo denuncia.
            if _abre_item(m.group(2)):
                fechar()
                numero_atual, buffer = m.group(1), [m.group(2)]
                continue
            if numero_atual is not None:
                buffer.append(linha.strip())
            continue
        if numero_atual is not None:
            if (m := RE_ALINEA.match(linha)):
                buffer.append(f"{m.group(1)}) {m.group(2)}")
            else:
                buffer.append(linha.strip())
    fechar()

    return sorted(itens.values(), key=lambda i: (i.anexo or "", _chave_ordem(i.item)))


RE_CONTINUACAO = re.compile(r"^(ou|e|de|da|do|das|dos|desta|deste|conforme|que|com|a|o|em|no|na|para|por|ao|à)\b", re.IGNORECASE)


def _numero_anexo(rotulo: str) -> int | None:
    return int(rotulo) if rotulo.isdigit() else None


def _abre_item(corpo: str) -> bool:
    """Decide se o texto após o número inicia de fato um item normativo."""
    corpo = corpo.lstrip("–-— ")
    if not corpo:
        return False
    primeira = corpo.split()[0]
    if RE_CONTINUACAO.match(primeira) and primeira[0].islower():
        return False
    return corpo[0].isupper() or corpo[0].isdigit() or corpo[0] in "(\u201c\""


RE_DEFINICAO = re.compile(
    r"^(denomina-se|considera-se|para os (fins|efeitos)|para efeito|entende-se|"
    r"para fins d|conceitua-se|define-se|aplica-se o disposto|esta norma|"
    r"o objetivo desta|as disposi[çc][õo]es desta)",
    re.IGNORECASE,
)


def _classificar(texto: str) -> str:
    """Distingue comando normativo de cabeçalho de seção e de mera definição.

    Um item que só define um termo nunca é uma não conformidade — deixá-lo fora
    da busca limpa muito ruído do dossiê.
    """
    if len(texto) < 70 and not texto.rstrip().endswith((".", ":", ";")):
        return "titulo"
    if RE_DEFINICAO.match(texto.strip()):
        return "definicao"
    return "item"


def _chave_ordem(item: str) -> tuple:
    numeros = re.findall(r"\d+", item)
    return tuple(int(n) for n in numeros)


# --------------------------------------------------------------------------
# Construção
# --------------------------------------------------------------------------

def localizar_pdfs() -> list[Path]:
    pastas = [RAIZ / "normas", RAIZ]
    vistos: dict[str, Path] = {}
    for pasta in pastas:
        if not pasta.is_dir():
            continue
        for pdf in sorted(pasta.glob("*.pdf")):
            vistos.setdefault(pdf.name, pdf)
    return list(vistos.values())


def construir(verboso: bool = True) -> dict:
    edicoes: dict[str, list[dict]] = {}
    ignorados: list[str] = []

    for pdf in localizar_pdfs():
        nr, ano = identificar_nr(pdf.name)
        if nr is None:
            ignorados.append(pdf.name)
            continue
        bruto = extrair_texto_pdf(pdf)
        itens = parsear_norma(nr, bruto, pdf.name)
        edicoes.setdefault(nr, []).append({
            "fonte": pdf.name,
            "ano": ano or None,
            # Sem cláusula explícita, a edição vale desde 1º de janeiro do ano
            # do arquivo — suficiente para ordenar edições entre si.
            "vigencia_inicio": ler_vigencia_da_norma(bruto) or (f"{ano}-01-01" if ano else None),
            "itens": [asdict(i) for i in itens],
        })

    normas: dict[str, dict] = {}
    for nr, lista in sorted(edicoes.items()):
        lista.sort(key=lambda e: (e["vigencia_inicio"] or "", e["ano"] or 0))
        normas[nr] = {"nr": nr, "edicoes": lista}
        if verboso:
            resumo = ", ".join(
                f"{e['fonte']} (desde {e['vigencia_inicio'] or '?'}, {len(e['itens'])} itens)"
                for e in lista
            )
            print(f"{nr}: {resumo}", file=sys.stderr)

    return {
        "versao": 3,
        "gerado_em": date.today().isoformat(),
        "impressao_digital": impressao_digital(),
        "normas": normas,
        "pdfs_ignorados": ignorados,
    }


def impressao_digital() -> str:
    """Resume o conjunto de PDFs de origem, para detectar quando a base envelheceu."""
    import hashlib

    marca = hashlib.sha256()
    for pdf in sorted(localizar_pdfs(), key=lambda p: p.name):
        marca.update(pdf.name.encode())
        marca.update(str(pdf.stat().st_size).encode())
    return marca.hexdigest()[:16]


def gravar(kb: dict, destino: Path = DESTINO) -> None:
    destino.parent.mkdir(parents=True, exist_ok=True)
    with gzip.open(destino, "wt", encoding="utf-8") as fh:
        json.dump(kb, fh, ensure_ascii=False, separators=(",", ":"))
    tamanho = destino.stat().st_size / 1024
    print(f"\n✅ {destino} gravado ({tamanho:.0f} KB)", file=sys.stderr)


if __name__ == "__main__":
    kb = construir()
    total = sum(len(e["itens"]) for n in kb["normas"].values() for e in n["edicoes"])
    print(f"\n{len(kb['normas'])} normas, {total} itens", file=sys.stderr)
    gravar(kb)
