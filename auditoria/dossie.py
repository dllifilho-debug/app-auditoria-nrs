"""Montagem do dossiê normativo: dos fatos observados aos itens de NR candidatos.

O modelo analista nunca recebe "as NRs inteiras" nem uma bula escrita à mão.
Ele recebe um dossiê numerado — D1, D2, D3… — de itens reais, recuperados da
base a partir do que a foto de fato mostra, e só pode citar por esse rótulo.
É o que impede tanto a invenção de item quanto o enquadramento fora de tema.
"""

import re
from dataclasses import dataclass, field
from datetime import date

from .catalogo_nr import CATALOGO_NR, NRS_VIGENTES
from .kb import BaseNormativa, Item, normalizar

# Rede de segurança: NRs que praticamente sempre têm algo a dizer sobre um
# ambiente de trabalho, mesmo quando o roteamento por palavra-chave não pega.
NRS_TRANSVERSAIS = ["NR-01", "NR-06"]

# Obrigações puramente documentais ou de gestão: inventário de riscos, guarda e
# digitalização de documentos, carga horária de treinamento, registro de entrega
# de EPI, contrato com organizações contratadas. Uma fotografia não comprova nem
# desmente nenhuma delas.
#
# Por que isto existe: numa foto real de fiação desencapada, o roteamento curado
# não pegou o risco elétrico e a busca textual devolveu um dossiê inteiro de
# itens administrativos. O analista é obrigado a escolher do dossiê — escolheu
# "o inventário de riscos ocupacionais deve contemplar…" para enquadrar um fio
# exposto, e o laudo saiu com um item verdadeiro na situação errada.
#
# O filtro vale SÓ para a recuperação textual desta função. Os itens da taxonomia
# curada entram por outro caminho, em `pipeline.montar_dossie`, e nunca passam
# por aqui: alguns deles são deliberadamente documentais (o quadro de avisos da
# CIPA, a ficha de entrega de EPI) porque um humano decidiu que aquela foto
# específica os evidencia. Filtrá-los seria desfazer curadoria à mão.
MARCADORES_DOCUMENTAIS = (
    "inventario de riscos", "guarda de documentos", "processo de digitalizacao",
    "os treinamentos previstos", "modalidade de ensino", "carga horaria",
    "registro de fornecimento", "manual de instrucoes", "deve ser documentad",
    "prestacao de informacoes", "organizacoes contratadas", "adquirir somente",
    "programa de gerenciamento", "deve manter os originais",
    "que oferte as capacitacoes", "material didatico", "relatorio analitico",
    # Um laudo real enquadrou "documento de registro de empregado exibido na
    # tela do monitor" (uma foto de escritório, sem nenhum achado de campo)
    # neste item — que é sobre o FORMATO da prova de treinamento (presencial
    # x digital com senha), não sobre exposição de dado pessoal. NR-01 entra
    # sempre como rede de segurança (NRS_TRANSVERSAIS) mesmo quando a foto não
    # tem achado de segurança nenhum, e a busca textual ofereceu o item menos
    # ruim do cluster de avaliação de aprendizagem. Nenhuma foto prova ou
    # desmente o método de avaliação de um treinamento.
    "avaliacao da aprendizagem",
)


def comprovavel_em_foto(item: Item) -> bool:
    """O item descreve condição física observável, e não obrigação de papel?"""
    texto = normalizar(item.texto)
    return not any(marcador in texto for marcador in MARCADORES_DOCUMENTAIS)


# Seções que dizem para que a norma serve, a quem ela se aplica, o que cada
# palavra significa e quando ela deixa de valer. Nenhuma impõe conduta, e por
# isso nenhuma sustenta autuação.
#
# Por que isto existe: um laudo real enquadrou um ponto de ancoragem no item
# "Anexo II 1.1" da NR-35 — que é o OBJETIVO do anexo ("Estabelecer os
# requisitos e as medidas de prevenção para o emprego de sistemas de
# ancoragem"). O item existe, está vigente e fala de ancoragem, então o portão
# de emissão o aprovou; o que faltava era perceber que ele não manda fazer nada.
#
# Vale, como `comprovavel_em_foto`, SÓ para a recuperação textual: os itens da
# taxonomia curada entram por `pipeline.montar_dossie` e não passam por aqui.
# A distinção importa — a NR-09 9.6.1, mapeada à mão, é disposição transitória,
# e é justamente por ser curada que ela deve continuar valendo.
SECOES_SEM_COMANDO = frozenset((
    "objetivo", "objetivos", "objetivo e campo de aplicacao",
    "campo de aplicacao", "aplicacao", "abrangencia", "introducao",
    "definicoes", "termos e definicoes", "glossario", "conceitos",
    "referencias", "referencias normativas", "sumario", "disposicoes finais",
))

# Abertura de item que enuncia escopo. Serve para o caso em que o PDF não traz
# o cabeçalho da seção e `titulo_da_secao` volta vazio.
RE_ITEM_DE_ESCOPO = re.compile(
    r"^(estabelecer\b|este anexo (estabelece|se aplica|trata|tem)\b|"
    r"esta norma (estabelece|se aplica|trata|tem)\b|o presente anexo\b)",
    re.IGNORECASE,
)


def prescritivo(item: Item, base: BaseNormativa) -> bool:
    """O item impõe conduta, ou só diz do que a norma trata?"""
    if RE_ITEM_DE_ESCOPO.match(normalizar(item.texto)):
        return False
    titulo = normalizar(base.titulo_da_secao(item)).strip(" .:-")
    titulo = re.sub(r"^(?:d[aeo]s)\s+", "", titulo)   # "Das disposições finais"
    titulo = re.sub(r"\s+\d+$", "", titulo)           # número de página colado
    return titulo not in SECOES_SEM_COMANDO


@dataclass(frozen=True)
class Entrada:
    """Um item do dossiê, com o rótulo pelo qual o analista deve referenciá-lo."""

    rotulo: str          # "D7"
    item: Item
    origem: str = ""     # achado que puxou este item, para depuração

    def linha(self, limite: int = 300) -> str:
        return f"[{self.rotulo}] {self.item.nr} {self.item.item} — {self.item.resumo(limite)}"


@dataclass
class Dossie:
    entradas: list[Entrada] = field(default_factory=list)
    nrs_candidatas: list[str] = field(default_factory=list)
    nrs_sem_texto: list[str] = field(default_factory=list)
    data_referencia: date = field(default_factory=date.today)

    @property
    def indice(self) -> dict[str, Item]:
        return {e.rotulo: e.item for e in self.entradas}

    def texto(self, limite: int = 300) -> str:
        return "\n".join(e.linha(limite) for e in self.entradas)

    def __len__(self) -> int:
        return len(self.entradas)


def _pontuar_nrs(descricao: str) -> dict[str, int]:
    """Roteia a descrição da foto para as NRs prováveis pelas palavras-chave do catálogo."""
    alvo = normalizar(descricao)
    pontos: dict[str, int] = {}
    for nr, meta in CATALOGO_NR.items():
        if meta["status"] != "vigente":
            continue
        acertos = sum(
            1
            for chave in meta["palavras_chave"]
            if (termo := normalizar(chave))
            and re.search(r"\b" + re.escape(termo).replace(r"\ ", r"\s+") + r"\w{0,3}\b", alvo)
        )
        if acertos:
            pontos[nr] = acertos
    return pontos


def montar(
    base: BaseNormativa,
    achados: list[str],
    contexto: str = "",
    quando: date | None = None,
    por_achado: int = 4,
    teto: int = 22,
    teto_por_nr: int = 5,
    nrs_forcadas: list[str] | None = None,
) -> Dossie:
    """Constrói o dossiê a partir dos achados factuais do Agente Olho.

    A recuperação é feita achado a achado, e não sobre um bloco único de texto:
    buscar "abertura no piso sem travamento" separadamente de "entulho acumulado"
    devolve o item certo para cada um, em vez de uma média morna dos dois.
    """
    quando = quando or date.today()
    achados = [a.strip() for a in achados if a and a.strip()]
    blob = "\n".join(achados + [contexto])

    pontos = _pontuar_nrs(blob)
    for nr in nrs_forcadas or []:
        pontos[nr] = pontos.get(nr, 0) + 10
    ordenadas = sorted(pontos, key=lambda n: (-pontos[n], n))
    candidatas = [n for n in ordenadas if n in base.por_nr]
    sem_texto = [n for n in ordenadas if n in NRS_VIGENTES and n not in base.por_nr]

    escopo = candidatas + [n for n in NRS_TRANSVERSAIS if n in base.por_nr and n not in candidatas]

    # NR bem roteada pelas palavras-chave puxa seus itens para cima; a rede de
    # segurança entra com peso menor, para reforçar sem dominar.
    maximo = max(pontos.values(), default=1) or 1
    prior = {nr: 1.0 + 0.6 * (pontos.get(nr, 0) / maximo) for nr in escopo}

    melhor: dict[str, tuple[float, Item, str]] = {}

    def util(item: Item) -> bool:
        """Item que uma fotografia pode evidenciar e que impõe conduta."""
        return comprovavel_em_foto(item) and prescritivo(item, base)

    def registrar(item: Item, score: float, origem: str) -> None:
        score *= prior.get(item.nr, 1.0)
        atual = melhor.get(item.id)
        if atual is None or score > atual[0]:
            melhor[item.id] = (score, item, origem)

    # 1) Um recorte nítido por achado — o núcleo da precisão.
    for achado in achados:
        for item, score in base.buscar_pontuado(
            f"{achado} {contexto}", nrs=escopo or None, k=por_achado,
            quando=quando, minimo_relativo=0.45, aceitar=util,
        ):
            registrar(item, score, achado[:60])

    # 2) Uma varredura ampla de reforço, para não perder enquadramento
    #    que só aparece quando os achados são lidos em conjunto.
    for item, score in base.buscar_pontuado(
        blob, nrs=escopo or None, k=8, quando=quando, minimo_relativo=0.55,
        aceitar=util,
    ):
        registrar(item, score * 0.9, "visão geral")

    # Teto por NR: impede que uma única norma inunde o dossiê e esconda o
    # enquadramento certo de outra.
    por_nr: dict[str, int] = {}
    ranqueado: list[tuple[float, Item, str]] = []
    for entrada in sorted(melhor.values(), key=lambda t: -t[0]):
        nr = entrada[1].nr
        if por_nr.get(nr, 0) >= teto_por_nr:
            continue
        por_nr[nr] = por_nr.get(nr, 0) + 1
        ranqueado.append(entrada)
        if len(ranqueado) >= teto:
            break
    ranqueado.sort(key=lambda t: (t[1].nr, t[1].item))

    entradas = [
        Entrada(f"D{n}", item, origem)
        for n, (_, item, origem) in enumerate(ranqueado, start=1)
    ]

    return Dossie(
        entradas=entradas,
        nrs_candidatas=[n for n in candidatas[:8]],
        nrs_sem_texto=[n for n in sem_texto if pontos.get(n, 0) >= 2][:5],
        data_referencia=quando,
    )
