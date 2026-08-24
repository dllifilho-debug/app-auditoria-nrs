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

from __future__ import annotations

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


def rotulos_para_prompt() -> str:
    """Lista compacta dos riscos, para o modelo de visão etiquetar os achados."""
    return "\n".join(f"- {r.id}: {r.rotulo}" for r in catalogo().values())
