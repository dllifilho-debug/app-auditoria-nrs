"""Exportar e recarregar o progresso de um lote entre sessões do navegador.

`st.session_state.resultados` vive só na memória da sessão: um redeploy do
Streamlit Cloud (ou um F5) apaga o lote em andamento, e no plano gratuito um
lote de 100 fotos leva horas ou dias. Um banco local (SQLite) não resolveria
— o Streamlit Cloud reconstrói o container inteiro a cada redeploy, então o
disco também some junto. O que sobrevive é o que o navegador baixa: um botão
"Baixar progresso" grava o lote em JSON, e "Carregar progresso" o devolve ao
`session_state` depois do redeploy ou numa sessão nova.
"""

from __future__ import annotations

import base64
import dataclasses
import json
from datetime import date

from .kb import Item
from .pipeline import Achado, Laudo, NaoConformidade, Visao

VERSAO_FORMATO = 1


class ProgressoInvalido(ValueError):
    """O arquivo carregado não é um progresso salvo por este app."""


def _campos_de(cls: type, dados: dict) -> dict:
    """Filtra `dados` para as chaves que `cls` de fato declara.

    Protege contra um export de uma versão mais nova do app, com campo que
    esta versão não conhece — sem isto, `Laudo(**dados)` levantaria
    TypeError em vez de reconstruir com o padrão do campo que falta.
    """
    nomes = {f.name for f in dataclasses.fields(cls)}
    return {k: v for k, v in dados.items() if k in nomes}


def _item_de(dados: dict) -> Item:
    return Item(**_campos_de(Item, dados))


def _achado_de(dados: dict) -> Achado:
    return Achado(**_campos_de(Achado, dados))


def _visao_de(dados: dict) -> Visao:
    campos = _campos_de(Visao, dados)
    campos["achados"] = [_achado_de(a) for a in campos.get("achados", [])]
    return Visao(**campos)


def _nao_conformidade_de(dados: dict) -> NaoConformidade:
    campos = _campos_de(NaoConformidade, dados)
    campos["item"] = _item_de(campos["item"])
    campos["complementos"] = [_item_de(c) for c in campos.get("complementos", [])]
    return NaoConformidade(**campos)


def _laudo_de(dados: dict) -> Laudo:
    campos = _campos_de(Laudo, dados)
    campos["visao"] = _visao_de(campos["visao"])
    campos["nao_conformidades"] = [
        _nao_conformidade_de(nc) for nc in campos.get("nao_conformidades", [])
    ]
    if campos.get("data_referencia"):
        campos["data_referencia"] = date.fromisoformat(campos["data_referencia"])
    return Laudo(**campos)


def serializar(resultados: list[tuple[str, Laudo, bytes]]) -> str:
    """`st.session_state.resultados` → JSON para baixar.

    `default=str` cobre o único campo não serializável de outro jeito
    (`data_referencia`, um `date`); `str(date(...))` já é o formato ISO que
    `date.fromisoformat` lê de volta.
    """
    itens = [
        {
            "nome": nome,
            "laudo": dataclasses.asdict(laudo),
            "miniatura_b64": base64.b64encode(miniatura).decode("ascii"),
        }
        for nome, laudo, miniatura in resultados
    ]
    return json.dumps(
        {"versao": VERSAO_FORMATO, "resultados": itens},
        default=str, ensure_ascii=False, indent=2,
    )


def carregar(bruto: str | bytes) -> list[tuple[str, Laudo, bytes]]:
    """JSON baixado antes → lista pronta para `st.session_state.resultados`."""
    try:
        dados = json.loads(bruto)
    except json.JSONDecodeError as erro:
        raise ProgressoInvalido("O arquivo não é um JSON válido.") from erro

    if not isinstance(dados, dict) or not isinstance(dados.get("resultados"), list):
        raise ProgressoInvalido(
            "O arquivo não tem o formato de progresso deste app."
        )

    resultado = []
    for item in dados["resultados"]:
        try:
            nome = item["nome"]
            laudo = _laudo_de(item["laudo"])
            miniatura = base64.b64decode(item["miniatura_b64"])
        except (KeyError, TypeError) as erro:
            raise ProgressoInvalido(
                f"Registro incompleto no arquivo de progresso: {erro}"
            ) from erro
        resultado.append((nome, laudo, miniatura))
    return resultado
