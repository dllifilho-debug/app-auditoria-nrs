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

# NRs cujo objeto é a máquina em si. Sem máquina nomeada na cena, nenhum item
# delas é candidato — ver `ha_maquina_na_cena`.
NRS_QUE_EXIGEM_MAQUINA = frozenset({"NR-12"})

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


# A lista acima cresceu um marcador de cada vez, atrás de um laudo ruim. Medir
# o dossiê da `foto (59)` mostrou que remendar frase a frase não alcança o
# problema: das 10 vagas do dossiê de um painel elétrico empoeirado, NOVE eram
# obrigação de papel — treinamento de eletricista, memorial descritivo do
# projeto, plano de emergência, ficha de dados de segurança de mistura química,
# e ainda a metodologia de estimativa da taxa metabólica da NR-09. Sobrava UM
# item físico, `NR-10 10.10.1` (sinalização), e foi nele que o Analista
# enquadrou a poeira — o enquadramento que a supervisão vetou.
#
# É a classe de erro 1 na sua forma pura: dossiê pobre força escolha ruim. O
# veto do Diretor limpa o laudo, mas não devolve ao Analista o item certo, que
# nunca chegou a caber.
#
# Estas famílias são o que o remendo frase a frase não pegava. Todas descrevem
# obrigação que uma fotografia não comprova nem desmente — nem para acusar, nem
# para inocentar. Valem, como os marcadores acima, SÓ para a recuperação
# textual: item documental mapeado à mão na taxonomia curada entra por
# `pipeline.montar_dossie` e não passa por aqui.
RE_OBRIGACAO_DE_PAPEL = re.compile(
    # 1) Treinamento e capacitação de pessoas. "certificado" sozinho fica de
    #    fora do padrão como particípio: "o dispositivo de ancoragem deve ser
    #    certificado" é condição do equipamento, que a etiqueta na foto
    #    evidencia. Só o substantivo ("O certificado deve ser disponibilizado")
    #    é papel, e é ele que entra.
    r"\btreinament|\bcapacitac|\breciclagem\b|\bcarga horaria|\b(o|os) certificados?\b"
    r"|\bavaliacao da aprendizagem|\binstrutor|\bqualificacao profissional"
    # 2) Documento, plano, programa, procedimento, registro. "planos de trabalho"
    #    fica de fora: na NR-17 é a superfície da bancada, não um documento.
    r"|\bmemorial descritivo|\bficha (com|de) dados de seguranca|\bordem de servico"
    r"|\bordens de servico|\bprontuario|\blaudo\b|\brelatorio\b|\bdocumentacao\b"
    r"|\binventario de risco|\bprograma de [a-z]|\bprojeto executivo"
    r"|\bdeve ser documentad|\bdeve constar do|\bregistro[s]? de [a-z]"
    r"|\bprocedimento[s]? de [a-z]|\bplanos? de\b(?! trabalho)|\bpgr\b|\bpcmso\b"
    r"|\bo projeto deve\b"
    # 3) Metodologia de avaliação de risco: como estimar probabilidade,
    #    severidade, nível de risco e taxa metabólica. Diz como medir, não o que
    #    a cena tem de errado.
    r"|\btaxa metabolica|\bprobabilidade deve|\bseveridade\b|\bnivel de risco"
    r"|\bgradacao\b|\bcomo criterio\b|\bdeve ser estimad"
    r"|\bprobabilidade de ocorrencia|\bavaliacao preliminar"
    # 4) Competência institucional e dever de comunicar: quem fiscaliza, quem
    #    emite CA, a quem avisar. Nada disso está na foto.
    r"|\bsecretaria de trabalho|\borgao de ambito nacional|\bcompetente em materia"
    r"|\bobservancia obrigatoria|\bcessao de uso|\bcanal de comunicacao"
    r"|\bdevem? comunicar|\bser divulgad|\bsesmt\b|\bdevem? orientar\b"
    r"|\brecebe[r]? informacoes\b|\bna ocorrencia de acidente"
)


def comprovavel_em_foto(item: Item) -> bool:
    """O item descreve condição física observável, e não obrigação de papel?"""
    texto = normalizar(item.texto)
    if any(marcador in texto for marcador in MARCADORES_DOCUMENTAIS):
        return False
    return not RE_OBRIGACAO_DE_PAPEL.search(texto)


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
    texto = normalizar(item.texto)
    if RE_ITEM_DE_ESCOPO.match(texto):
        return False
    # Quando o PDF não separa o cabeçalho do primeiro item, ele vem colado na
    # frente do texto: "Glossário Ambiente exclusivo: espaço físico…" é o
    # glossário da NR-01 Anexo II, extraído como se fosse item normativo.
    if normalizar(texto.split(" ")[0]).strip(" .:-") in SECOES_SEM_COMANDO:
        return False
    titulo = normalizar(base.titulo_da_secao(item)).strip(" .:-")
    titulo = re.sub(r"^(?:d[aeo]s)\s+", "", titulo)   # "Das disposições finais"
    titulo = re.sub(r"\s+\d+$", "", titulo)           # número de página colado
    return titulo not in SECOES_SEM_COMANDO


# ---------------------------------------------------------------------------
# Máquina na cena, e parte setorial da norma fora de contexto
# ---------------------------------------------------------------------------

# A NR-12 tem 920 itens — quase um quarto de tudo que é indexável — e um
# vocabulário genérico o bastante ("áreas de circulação", "condutores de
# alimentação elétrica", "piso do local de trabalho") para casar com qualquer
# coisa de canteiro. Por isso ela virou a lixeira do dossiê: entulho no chão
# saiu como 12.2.4 e cabo pendurado na parede como 12.3.8, em fotos sem
# máquina nenhuma.
#
# O precedente está na taxonomia curada: `exige_pessoa` impede cobrar capacete
# numa foto sem ninguém. Este é o análogo — a NR-12 só entra no escopo da busca
# textual se a cena nomear uma máquina.
#
# A lista é de substantivos concretos de propósito. "Máquina" e "equipamento"
# sozinhos foram tirados do roteamento em `d2d92b2` justamente por casarem com
# quase tudo (equipamento de proteção individual, equipamento elétrico), e aqui
# seriam piores: como o portão só ABRE, uma frase de negação do Olho ("nenhuma
# máquina visível na cena") destrancaria exatamente o caso que se quer barrar.
# Nomear a máquina é o sinal que não se inverte.
MAQUINAS_NA_CENA = (
    # canteiro
    "betoneira", "argamassadeira", "masseira de argamassa", "bomba de concreto",
    "vibrador de concreto", "vibrador de imersao", "regua vibratoria",
    "placa vibratoria", "compactador", "rolo compactador", "bate-estaca",
    "cortadora de piso", "policorte", "serra circular", "serra de bancada",
    "serra marmore", "serra de disco", "serra de fita", "esmerilhadeira",
    "lixadeira", "furadeira", "martelete", "rompedor", "maquina de solda",
    "compressor", "motobomba", "bancada de corte e dobra",
    # transporte e elevação
    # "talha" e "gerador" sozinhos abrem em "madeira talhada" e em "gerador de
    # resíduos", que é vocabulário de PGR, não de máquina.
    "guincho", "guindaste", "grua", "munck", "talha eletrica",
    "talha de corrente", "talha manual", "grupo gerador",
    "gerador de energia", "elevador de carga",
    "elevador cremalheira", "cremalheira", "plataforma elevatoria",
    "cesta aerea", "empilhadeira", "retroescavadeira", "escavadeira",
    "pa carregadeira", "motoniveladora", "correia transportadora",
    "esteira transportadora", "transportador de correia",
    # industriais
    # "torno" sozinho não vai: casa com "em torno de", que é como um laudo
    # descreve a área ao redor de um pilar.
    "torno mecanico", "torno cnc", "fresadora", "prensa", "guilhotina",
    "dobradeira", "calandra",
    "injetora", "extrusora", "misturador industrial", "motosserra", "motopoda",
    # Máquinas dos ramos que a tabela `SETORES` trata logo abaixo. Sem elas
    # aqui o portão fecharia justamente nas fotos em que a NR-12 setorial é a
    # norma certa: uma masseira de padaria é tão máquina quanto uma betoneira,
    # e barrar a NR-12 inteira ali trocaria um erro de enquadramento por um
    # buraco de cobertura. O nome do ramo ("padaria", "açougue") fica de fora
    # de propósito — quem abre o portão é a máquina, não o lugar.
    "masseira", "amassadeira", "cilindro de massa", "divisora de massa",
    "modeladora", "laminadora", "fatiadora de pao", "batedeira planetaria",
    "forno de lastro", "moedor de carne", "serra fita", "amaciador de bife",
    "fatiador de frios", "cortador de frios", "descascador de legumes",
    "liquidificador industrial", "rebaixadeira", "colheitadeira", "plantadeira",
    "semeadora", "ensiladeira", "forrageira", "motocultivador",
)


@dataclass(frozen=True)
class Setor:
    """Um ramo para o qual parte de uma NR vale, e só ele.

    Dois vocabulários, porque os dois lados correm riscos opostos:

    - `no_item` reconhece que o item é daquele ramo. Pode ser a palavra
      simples: dentro da NR-12, "calçado" só aparece em item de máquina
      calçadista.
    - `na_cena` decide se a foto é daquele ramo, e aí a palavra simples é
      perigosa — "calçado" é o que um laudo de segurança escreve o tempo todo
      ("calçado de segurança", EPI da NR-06). Aqui vale o nome da máquina.

    Confundir os dois lados é a armadilha do sinal escrito por extenso, vista
    de outro ângulo: o que discrimina de um lado não discrimina do outro.
    """

    nome: str
    anexos: tuple[str, ...]
    no_item: tuple[str, ...]
    na_cena: tuple[str, ...]


# Medido no dossiê antes deste filtro: uma betoneira de canteiro gastava os
# cinco lugares da NR-12 com o Anexo X (calçados — "máquina de pregar salto",
# "injetora rotativa de carrossel móvel"), e uma serra circular de bancada
# recebia três itens de serra fita de AÇOUGUE (Anexo VII) e dois de "máquina
# boca de sapo". Os itens certos — proteção de zona de perigo, 12.5.x — nem
# chegavam a caber. O filtro não serve só para tirar item errado: serve para
# devolver a cota da NR-12 ao item certo.
#
# O anexo é o critério principal, mas não basta: a extração do PDF deixou
# `12.1` ("máquinas de montar base de calçados") no corpo principal, sem marca
# de anexo, e ele apareceu no dossiê da betoneira. Por isso o texto do item
# também conta.
SETORES: dict[str, tuple[Setor, ...]] = {
    "NR-12": (
        Setor(
            nome="motosserras e motopodas",
            anexos=("V",),
            no_item=("motosserra", "motopoda"),
            na_cena=("motosserra", "motopoda"),
        ),
        Setor(
            nome="panificação e confeitaria",
            anexos=("VI",),
            no_item=(
                "panificacao", "confeitaria", "padaria", "masseira",
                "amassadeira", "cilindro de massa", "divisora de massa",
                "modeladora", "laminadora", "fatiadora de pao",
                "forno de lastro", "farinha de rosca",
            ),
            na_cena=(
                "panificacao", "confeitaria", "padaria", "masseira",
                "amassadeira", "cilindro de massa", "divisora de massa",
                "fatiadora de pao", "forno de lastro", "batedeira planetaria",
            ),
        ),
        Setor(
            nome="açougue, mercearia, bares e restaurantes",
            anexos=("VII",),
            no_item=(
                "acougue", "mercearia", "bares e restaurantes",
                "moedor de carne", "serra fita", "amaciador de bife",
                "fatiador de frios", "cortador de frios",
                "descascador de legumes", "liquidificador",
            ),
            na_cena=(
                "acougue", "mercearia", "restaurante", "lanchonete",
                "cozinha industrial", "moedor de carne", "serra fita",
                "amaciador de bife", "fatiador de frios",
                "descascador de legumes",
            ),
        ),
        Setor(
            nome="prensas e similares",
            anexos=("VIII",),
            no_item=(
                "prensa", "guilhotina", "dobradeira", "tesoura mecanica",
                "estampo", "martelo de queda",
            ),
            na_cena=(
                "prensa", "guilhotina", "dobradeira", "tesoura mecanica",
                "estampo", "zona de prensagem",
            ),
        ),
        Setor(
            nome="injetoras de material plástico",
            anexos=("IX",),
            no_item=(
                "injetora", "injecao de plastico", "molde de injecao",
                "termoplastico",
            ),
            na_cena=(
                "injetora", "injecao de plastico", "molde de injecao",
                "termoplastico",
            ),
        ),
        Setor(
            nome="fabricação de calçados",
            anexos=("X",),
            no_item=(
                "calcado", "solado", "palmilha", "curtume", "boca de sapo",
                "montar bicos", "pregar salto", "conformar traseiro",
            ),
            na_cena=(
                "fabricacao de calcados", "industria calcadista", "curtume",
                "solado", "palmilha", "boca de sapo", "montar bicos",
                "pregar salto", "conformar traseiro", "rebaixadeira",
            ),
        ),
        Setor(
            nome="máquinas agrícolas e florestais",
            anexos=("XI",),
            no_item=(
                "colheitadeira", "plantadeira", "semeadora", "ensiladeira",
                "forrageira", "motocultivador", "implemento agricola",
                "maquinas agricolas", "uso agricola", "agroflorest",
                "lavoura", "colheita",
            ),
            na_cena=(
                "colheitadeira", "plantadeira", "semeadora", "ensiladeira",
                "forrageira", "motocultivador", "implemento agricola",
                "trator agricola", "pulverizador agricola", "lavoura",
                "colheita",
            ),
        ),
    ),
}

# Os demais anexos da NR-12 valem para qualquer máquina e ficam de fora da
# tabela de propósito: I (distâncias de segurança e cortina de luz), II
# (capacitação do operador), III (meios de acesso a máquinas) e sobretudo
# XII (equipamentos de guindar, transportar e descarregar — cesta aérea, grua,
# elevador de carga), que é justamente o que uma obra tem. A contraparte a
# vigiar é essa: NR-12 Anexo XII e NR-35 Anexo III (escadas) devem passar.


def _menciona(alvo: str, termos) -> bool:
    """Algum dos termos aparece no texto já normalizado, como palavra inteira?

    Mesmo casamento do roteamento por palavra-chave: tolera sufixo curto
    (plural, "prensagem" para "prensa") sem deixar "imprensado" contar como
    prensa.
    """
    return any(
        re.search(r"\b" + re.escape(termo).replace(r"\ ", r"\s+") + r"\w{0,3}\b", alvo)
        for termo in map(normalizar, termos)
        if termo
    )


def ha_maquina_na_cena(texto: str) -> bool:
    """A cena nomeia alguma máquina, ou equipamento de guindar e transportar?"""
    return _menciona(normalizar(texto), MAQUINAS_NA_CENA)


def setor_do_item(item: Item) -> Setor | None:
    """Ramo ao qual o item pertence exclusivamente, se houver.

    O anexo decide antes do texto, e a ordem importa: os anexos setoriais se
    citam entre si ("as disposições deste Anexo não se aplicam às máquinas
    dispostas no Anexo X"), e itens do Anexo X — calçados — falam de prensa.
    Pelo texto, eles passariam como se fossem do Anexo VIII, que uma foto de
    estamparia legitimamente destranca.
    """
    setores = SETORES.get(item.nr, ())
    if item.anexo:
        for setor in setores:
            if item.anexo in setor.anexos:
                return setor
    for setor in setores:
        if _menciona(normalizar(item.texto), setor.no_item):
            return setor
    return None


def setor_pertinente(item: Item, cena: str) -> bool:
    """O item não é de um ramo alheio ao que a foto mostra?"""
    setor = setor_do_item(item)
    return setor is None or _menciona(normalizar(cena), setor.na_cena)


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
    cena: str = "",
) -> Dossie:
    """Constrói o dossiê a partir dos achados factuais do Agente Olho.

    A recuperação é feita achado a achado, e não sobre um bloco único de texto:
    buscar "abertura no piso sem travamento" separadamente de "entulho acumulado"
    devolve o item certo para cada um, em vez de uma média morna dos dois.
    """
    quando = quando or date.today()
    achados = [a.strip() for a in achados if a and a.strip()]
    blob = "\n".join(achados + [contexto])

    # `cena` (na prática, o ambiente que o Olho caracterizou) não entra na
    # busca: ela descreve o lugar, não o achado, e diluiria o recorte de cada
    # fato. Mas entra nos portões, e faz falta lá — é em "açougue, área de
    # manipulação" ou "central de corte do canteiro" que o ramo e a máquina
    # costumam estar nomeados, não no achado.
    texto_da_cena = "\n".join(t for t in (blob, cena) if t.strip())

    pontos = _pontuar_nrs(blob)
    for nr in nrs_forcadas or []:
        pontos[nr] = pontos.get(nr, 0) + 10
    ordenadas = sorted(pontos, key=lambda n: (-pontos[n], n))
    candidatas = [n for n in ordenadas if n in base.por_nr]
    sem_texto = [n for n in ordenadas if n in NRS_VIGENTES and n not in base.por_nr]

    if not ha_maquina_na_cena(texto_da_cena):
        candidatas = [n for n in candidatas if n not in NRS_QUE_EXIGEM_MAQUINA]

    escopo = candidatas + [n for n in NRS_TRANSVERSAIS if n in base.por_nr and n not in candidatas]

    # NR bem roteada pelas palavras-chave puxa seus itens para cima; a rede de
    # segurança entra com peso menor, para reforçar sem dominar.
    maximo = max(pontos.values(), default=1) or 1
    prior = {nr: 1.0 + 0.6 * (pontos.get(nr, 0) / maximo) for nr in escopo}

    melhor: dict[str, tuple[float, Item, str]] = {}

    def util(item: Item) -> bool:
        """Item que a foto pode evidenciar, que impõe conduta e cujo anexo
        pertence ao ramo que a foto mostra.

        Vai como `aceitar` para `buscar_pontuado`, e não como peneira depois:
        o `minimo_relativo` é calculado sobre o topo bruto, então um item ruim
        no topo levantaria a régua e derrubaria os bons abaixo dele.
        """
        return (
            comprovavel_em_foto(item)
            and prescritivo(item, base)
            and setor_pertinente(item, texto_da_cena)
        )

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
