"""Taxonomia de riscos observáveis em foto, mapeada para itens reais de NR.

A busca textual sozinha não dá conta: "abertura" na NR-18 é vão no piso, na
NR-23 é porta de saída de emergência, e o vocabulário de quem descreve uma foto
("fiação exposta", "gambiarra") não é o vocabulário da norma ("partes vivas",
"condutores"). Este módulo faz a ponte com um mapa curado — e o valida contra a
base normativa no import, de modo que um item que não exista, ou que deixe de
existir numa atualização de NR, quebra na hora em vez de virar laudo errado.

Cada domínio contribui com um dicionário `RISCOS`; aqui eles são unidos e
conferidos.
"""

from dataclasses import dataclass

GRAVIDADES = ("critica", "alta", "media", "baixa")

CAMPOS_OBRIGATORIOS = ("rotulo", "descricao", "sinais", "itens", "gravidade_base")


@dataclass(frozen=True)
class Risco:
    id: str
    rotulo: str
    dominio: str
    descricao: str
    sinais: tuple[str, ...]
    itens: tuple[str, ...]
    gravidade_base: str
    # Risco que só existe se houver pessoa na cena (EPI, conduta, capacitação).
    # É o que impede o laudo de cobrar capacete numa foto sem ninguém.
    exige_pessoa: bool = False
    # Itens que só entram no dossiê se houver máquina nomeada na cena. Mesmo
    # princípio do `exige_pessoa`, mas por item e não pelo risco inteiro: um
    # cabo de alimentação descascado é achado de verdade com ou sem máquina —
    # o que muda é se cabe citar o item que fala do condutor DE MÁQUINA
    # (NR-12 12.3.4) ou só o geral (NR-10 10.2.8.2). Sem esta distinção
    # sobravam duas saídas ruins: citar NR-12 sempre, que foi como entulho
    # virou 12.2.4 num canteiro sem máquina, ou nunca, que era perder a
    # citação certa justamente quando a máquina está lá.
    itens_so_com_maquina: tuple[str, ...] = ()


def _reunir() -> dict[str, dict]:
    from . import ambiental, construcao, industria

    reunido: dict[str, dict] = {}
    for modulo, dominio in (
        (construcao, "construcao"),
        (industria, "industria"),
        (ambiental, "ambiental"),
    ):
        for chave, dados in getattr(modulo, "RISCOS", {}).items():
            if chave in reunido:
                raise ValueError(f"risco duplicado entre domínios: {chave}")
            reunido[chave] = {**dados, "dominio": dominio}
    return reunido


def _validar(cru: dict[str, dict]) -> dict[str, Risco]:
    from ..kb import carregar_base

    base = carregar_base()
    problemas: list[str] = []
    riscos: dict[str, Risco] = {}

    for chave, dados in cru.items():
        for campo in CAMPOS_OBRIGATORIOS:
            if campo not in dados:
                problemas.append(f"{chave}: falta o campo '{campo}'")
        if problemas and chave not in riscos:
            continue
        if dados["gravidade_base"] not in GRAVIDADES:
            problemas.append(f"{chave}: gravidade_base '{dados['gravidade_base']}' inválida")
        if len(dados["sinais"]) < 3:
            problemas.append(f"{chave}: precisa de ao menos 3 sinais visuais")
        if not dados["itens"]:
            problemas.append(f"{chave}: nenhum item de NR mapeado")

        for ref in dados.get("itens_so_com_maquina", ()):
            if ref not in dados["itens"]:
                problemas.append(
                    f"{chave}: '{ref}' está em itens_so_com_maquina mas não em itens"
                )

        for ref in dados["itens"]:
            nr, _, item = ref.partition(" ")
            alvo = base.obter(nr, item)
            if alvo is None:
                problemas.append(f"{chave}: item inexistente na base → '{ref}'")
            elif alvo.tipo != "item":
                # Cabeçalho de seção e definição não impõem obrigação — citá-los
                # como não conformidade é erro de enquadramento.
                problemas.append(
                    f"{chave}: '{ref}' é {alvo.tipo}, não comando normativo"
                )

        riscos[chave] = Risco(
            id=chave,
            rotulo=dados["rotulo"],
            dominio=dados["dominio"],
            descricao=dados["descricao"],
            sinais=tuple(dados["sinais"]),
            itens=tuple(dados["itens"]),
            gravidade_base=dados["gravidade_base"],
            exige_pessoa=bool(dados.get("exige_pessoa", False)),
            itens_so_com_maquina=tuple(dados.get("itens_so_com_maquina", ())),
        )

    if problemas:
        raise ValueError(
            "Taxonomia de riscos inconsistente:\n  - " + "\n  - ".join(problemas)
        )
    return riscos


_CACHE: dict[str, Risco] | None = None


def catalogo() -> dict[str, Risco]:
    """Taxonomia validada. Levanta erro se algum item mapeado não existir na base."""
    global _CACHE
    if _CACHE is None:
        _CACHE = _validar(_reunir())
    return _CACHE


_COMPARTILHADOS: frozenset[str] | None = None


def itens_compartilhados() -> frozenset[str]:
    """Itens que mais de um risco reivindica — 22 dos 228 mapeados.

    São os genéricos: `NR-06 6.5.1` (EPI, oito riscos), `NR-26 26.3.1`
    (sinalização, cinco), `NR-18 18.9.1` ("proteção coletiva onde houver risco
    de queda", dois). Para eles o rótulo do risco não serve de nome da não
    conformidade: quem escolheu o item foi o Analista, olhando a situação, e
    qual risco o trouxe ao dossiê é acidente do roteamento.

    Um laudo real saiu com a NC intitulada "Andaime sem guarda-corpo e rodapé"
    para uma constatação sobre a tela frouxa na borda da laje, enquanto o fato
    registrado dizia que o andaime TINHA guarda-corpo. Dois modelos de texto
    diferentes erraram igual — é o mapa, não o modelo.
    """
    global _COMPARTILHADOS
    if _COMPARTILHADOS is None:
        contagem: dict[str, int] = {}
        for risco in catalogo().values():
            for ref in risco.itens:
                contagem[ref] = contagem.get(ref, 0) + 1
        _COMPARTILHADOS = frozenset(r for r, n in contagem.items() if n > 1)
    return _COMPARTILHADOS


# Itens de NRs diferentes que impõem a MESMA exigência sobre o mesmo objeto
# físico. Não são sinônimos: cada um vale no seu âmbito — a NR-18 é a norma da
# indústria da construção, a NR-08 vale para edificação em geral. Mas diante de
# uma única abertura no piso, os dois dizem a mesma coisa, e o Analista enquadra
# os dois: num lote real de 15 fotos, 6 das 21 não conformidades eram 3 aberturas
# contadas duas vezes, inflando a contagem em 29%.
#
# Um auditor não escreve duas não conformidades para uma abertura: escreve uma,
# pela norma mais específica, e menciona a outra. É o que o código faz aqui — a
# primeira ref de cada grupo é a que encabeça a NC, as demais viram citação
# complementar impressa ao lado. Quem cita continua sendo o código: o texto da
# norma complementar sai da base, verbatim, nunca da escrita de um agente.
#
# Ordem = precedência. NR-18 primeiro por ser a específica do ramo em que este
# app é usado; quando o Analista enquadra só a NR-08 (uma abertura de piso em
# escritório, onde a NR-18 não alcança), nada é descartado e é a NR-08 que
# encabeça, com a NR-18 de complemento.
ITENS_EQUIVALENTES: tuple[tuple[str, ...], ...] = (
    ("NR-18 18.9.2", "NR-08 8.3.2.2"),
)


def grupo_equivalente(ref: str) -> tuple[str, ...]:
    """O grupo de mesma exigência a que o item pertence, ou vazio."""
    for grupo in ITENS_EQUIVALENTES:
        if ref in grupo:
            return grupo
    return ()


def rotulos_para_prompt() -> str:
    """Lista compacta dos riscos, para o modelo de visão etiquetar os achados."""
    return "\n".join(f"- {r.id}: {r.rotulo}" for r in catalogo().values())
