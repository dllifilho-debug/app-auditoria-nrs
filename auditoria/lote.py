"""Sincronização entre as fotos do lote e os laudos já emitidos.

O app guarda o laudo de cada foto para poder retomar um lote interrompido sem
refazer — e gastar de novo — o que já saiu. O efeito colateral é que uma foto
retirada do seletor continuaria contando no sumário e no plano de ação. Aqui
mora a regra que resolve isso, fora da interface para poder ser testada.
"""

from typing import Iterable, Sequence, TypeVar

T = TypeVar("T")


def sincronizar(
    resultados: Sequence[tuple],
    nomes_no_lote: Iterable[str],
) -> tuple[list[tuple], list[str]]:
    """Descarta os laudos cujas fotos saíram do lote.

    Devolve (mantidos, nomes_descartados). Um lote vazio nunca descarta nada:
    o seletor pode devolver lista vazia por um instante durante a interação, e
    apagar o trabalho da sessão por causa disso seria caro demais. Para zerar
    de propósito existe o botão de limpar.
    """
    no_lote = set(nomes_no_lote)
    if not no_lote:
        return list(resultados), []

    mantidos = [r for r in resultados if r[0] in no_lote]
    descartados = [r[0] for r in resultados if r[0] not in no_lote]
    return mantidos, descartados


def pendentes(arquivos: Sequence[T], ja_auditados: Iterable[str]) -> list[T]:
    """As fotos do lote que ainda não têm laudo, na ordem em que foram enviadas."""
    prontos = set(ja_auditados)
    return [a for a in arquivos if a.name not in prontos]
