"""Renderização do laudo.

Todas as citações normativas que aparecem no documento final são escritas aqui,
a partir dos objetos `Item` que vieram da base — nunca a partir de texto gerado
por modelo. É a última linha de defesa contra citação inventada.
"""

from __future__ import annotations

import html
from datetime import date

from .catalogo_nr import CATALOGO_NR
from .kb import BaseNormativa
from .pipeline import Laudo, NaoConformidade

# Rótulo de gravidade em texto. Não há símbolo aqui de propósito: o laudo é
# arquivado impresso, muitas vezes em preto e branco, onde bolinha colorida vira
# cinza indistinto — e num documento que pode chegar à fiscalização, figurinha
# lê como protótipo. Quem dá o peso é a tipografia.
SELOS = {
    "critica": "Crítica",
    "alta": "Alta",
    "media": "Média",
    "baixa": "Baixa",
}


def _resumir(texto: str, limite: int) -> str:
    """Encurta sem cortar palavra ao meio.

    O corte cru deixava a tabela com "…expondo partes internas d", que parece
    erro de geração num documento que se pretende pericial.
    """
    texto = texto.strip()
    if len(texto) <= limite:
        return texto
    corte = texto[:limite].rsplit(" ", 1)[0].rstrip(" ,;:.")
    return (corte or texto[:limite]) + "…"


def _contar(valores) -> list[tuple[str, int]]:
    from collections import Counter

    return list(Counter(valores).items())


def _titulo_nr(nr: str) -> str:
    return CATALOGO_NR.get(nr, {}).get("titulo", "")


def _vigencia(nc: NaoConformidade, quando: date) -> str:
    item = nc.item
    if item.vigencia_inicio:
        return f"redação em vigor desde {date.fromisoformat(item.vigencia_inicio):%d/%m/%Y}"
    if item.vigencia_fim:
        return f"redação vigente até {date.fromisoformat(item.vigencia_fim):%d/%m/%Y}"
    return "vigente"


def markdown(
    laudo: Laudo,
    base: BaseNormativa,
    identificacao: str = "",
    obra: str = "",
    responsavel: str = "",
    numero: int = 1,
) -> str:
    quando = laudo.data_referencia
    p: list[str] = []

    p.append(f"# Relatório de Inspeção de Segurança do Trabalho — Registro fotográfico {numero}")
    p.append("")
    p.append(f"| | |\n|---|---|")
    p.append(f"| **Data de referência** | {quando:%d/%m/%Y} |")
    if obra:
        p.append(f"| **Obra / unidade** | {obra} |")
    if responsavel:
        p.append(f"| **Responsável pela inspeção** | {responsavel} |")
    if identificacao:
        p.append(f"| **Imagem** | {identificacao} |")
    p.append(f"| **Ambiente registrado** | {laudo.visao.ambiente or 'não caracterizado'} |")
    p.append(
        f"| **Trabalhadores na cena** | "
        f"{laudo.quantidade_pessoas_texto()} |"
    )
    p.append(f"| **Não conformidades** | {len(laudo.nao_conformidades)} |")
    p.append("")

    # 1. Fatos
    p.append("## 1. Fatos registrados")
    p.append("")
    p.append("*Descrição factual da imagem, sem juízo de valor.*")
    p.append("")
    if laudo.visao.achados:
        for a in laudo.visao.achados:
            onde = f" — *{a.onde}*" if a.onde else ""
            p.append(f"- {a.fato}{onde}")
    elif laudo.visao_falhou:
        p.append(
            "> **A leitura da imagem falhou.** O agente de visão não devolveu nenhum "
            "fato utilizável, então nenhum enquadramento foi feito a partir desta foto. "
            "Isto **não** atesta conformidade: a imagem apenas não pôde ser avaliada. "
            "Repita a análise, se possível com resolução de envio maior."
        )
    else:
        p.append("- Nenhum fato relevante foi extraído da imagem.")
    p.append("")

    # 2. Enquadramento
    p.append("## 2. Enquadramento normativo")
    p.append("")
    if not laudo.nao_conformidades:
        p.append(
            "Nenhuma não conformidade foi caracterizada com base nos itens normativos "
            "aplicáveis aos fatos registrados nesta imagem."
        )
        p.append("")
    else:
        p.append("| # | Não conformidade | Norma | Item | Gravidade | Prazo |")
        p.append("|---|---|---|---|---|---|")
        # Duas constatações distintas podem cair no mesmo risco catalogado. Repetir
        # o rótulo faria a tabela parecer ter linha duplicada, então nesse caso
        # quem identifica a linha é a própria constatação.
        repetidos = {
            r for r, n in _contar(x.rotulo_risco for x in laudo.nao_conformidades)
            if r and n > 1
        }
        for n, nc in enumerate(laudo.nao_conformidades, start=1):
            rotulo = SELOS.get(nc.gravidade, nc.gravidade)
            titulo = (
                _resumir(nc.constatacao, 80) if nc.rotulo_risco in repetidos
                else (nc.rotulo_risco or _resumir(nc.constatacao, 70))
            )
            p.append(
                f"| {n} | {titulo} | **{nc.item.nr}** | `{nc.item.item}` | "
                f"**{rotulo}** | {nc.prazo_dias} d |"
            )
        p.append("")

        p.append("### Detalhamento")
        p.append("")
        for n, nc in enumerate(laudo.nao_conformidades, start=1):
            rotulo = SELOS.get(nc.gravidade, nc.gravidade)
            # Sem rótulo de risco (item genérico disputado por mais de um),
            # quem nomeia a NC é a constatação — "Não conformidade constatada"
            # não diz nada a quem lê o laudo na obra.
            cabecalho = nc.rotulo_risco or _resumir(nc.constatacao, 70)
            if nc.rotulo_risco in repetidos:
                cabecalho += f" — {nc.item.item}"
            p.append(f"#### {n}. {cabecalho} — gravidade {rotulo.lower()}")
            p.append("")
            p.append(f"**Constatação.** {nc.constatacao}")
            p.append("")
            if nc.consequencia:
                p.append(f"**Consequência possível.** {nc.consequencia}")
                p.append("")
            p.append(
                f"**Base normativa.** {nc.item.nr} — {_titulo_nr(nc.item.nr)}, "
                f"item {nc.item.item} ({_vigencia(nc, quando)}):"
            )
            p.append("")
            p.append(f"> {nc.item.texto}")
            p.append("")
            # A mesma exigência em outra NR. Vale como reforço do enquadramento,
            # não como segunda não conformidade — é uma abertura só. O texto sai
            # da base, verbatim, como o da norma que encabeça.
            for extra in nc.complementos:
                p.append(
                    f"**Também alcançado por.** {extra.nr} — {_titulo_nr(extra.nr)}, "
                    f"item {extra.item}:"
                )
                p.append("")
                p.append(f"> {extra.texto}")
                p.append("")
            p.append(f"**Ação corretiva.** {nc.acao_corretiva}")
            p.append("")
            p.append(f"**Prazo sugerido.** {nc.prazo_dias} dia(s) — gravidade {rotulo.lower()}.")
            p.append("")

    # 3. Pontos sem enquadramento
    if laudo.sem_enquadramento:
        p.append("## 3. Pontos de atenção sem enquadramento direto")
        p.append("")
        p.append(
            "*Condições que merecem verificação, mas para as quais nenhum item normativo "
            "carregado se aplica com segurança. Registradas aqui em vez de forçadas numa "
            "citação imprópria.*"
        )
        p.append("")
        for s in laudo.sem_enquadramento:
            p.append(f"- {s}")
        p.append("")

    if laudo.nrs_sem_texto:
        faltantes = ", ".join(f"{nr} ({_titulo_nr(nr)})" for nr in laudo.nrs_sem_texto)
        p.append(
            f"> Os fatos sugerem possível aplicabilidade de {faltantes}, cujo texto integral "
            f"não está carregado nesta instalação. Nenhum item dessas normas foi citado — "
            f"recomenda-se verificação manual."
        )
        p.append("")

    if laudo.conformidades:
        p.append("## 4. Conformidades observadas")
        p.append("")
        # Ressalva de código, não de modelo: num laudo real esta lista atestou
        # "proteção coletiva contra quedas" para uma tela de sombreamento presa
        # numa ripa, na borda de laje de prédio alto. Enquanto quem escreve a
        # lista é um modelo, o documento precisa dizer o que ela não é.
        p.append(
            "*Registro do que a imagem sugere em ordem no instante da foto. Não é "
            "atestado de conformidade do sistema de proteção, cuja adequação depende "
            "de verificação em campo.*"
        )
        p.append("")
        for c in laudo.conformidades:
            p.append(f"- {c}")
        p.append("")

    # Parecer e trilha de auditoria
    if laudo.parecer_diretor:
        p.append("## Parecer da revisão técnica")
        p.append("")
        p.append(laudo.parecer_diretor)
        p.append("")

    p.append("---")
    p.append("")
    p.append("### Trilha de auditoria do laudo")
    p.append("")
    p.append(f"- Ciclos de análise e revisão executados: **{laudo.ciclos}**")
    p.append(
        f"- Veredito da revisão técnica: "
        f"**{'aprovado sem vetos' if laudo.aprovado else f'{len(laudo.vetos)} enquadramento(s) vetado(s)'}**"
        + (f", {len(laudo.aparos)} constatação(ões) aparada(s)" if laudo.aparos else "")
    )
    if laudo.vetos:
        for v in laudo.vetos:
            p.append(f"  - Vetado — {v}")
    for a in laudo.aparos:
        p.append(f"  - Aparada — {a}")
    if laudo.afericoes:
        p.append("- Descartes da aferição automática:")
        for a in laudo.afericoes:
            p.append(f"  - {a}")
    p.append(
        f"- Base normativa: {len(base.itens)} itens extraídos de "
        f"{len(base.por_nr)} NRs, edição consolidada em {base.gerado_em}."
    )
    # Toda NR cujo texto aparece no laudo declara sua edição aqui — inclusive a
    # que entrou só como citação complementar. Citar verbatim sem dizer de que
    # edição saiu desfaria a rastreabilidade que esta trilha existe para dar.
    citadas = sorted(
        {nc.item.nr for nc in laudo.nao_conformidades}
        | {e.nr for nc in laudo.nao_conformidades for e in nc.complementos}
    )
    for nr in citadas:
        linha = f"  - {nr}: edição `{base.edicoes.get(nr, '?')}`"
        if (futura := base.edicoes_futuras.get(nr)):
            arquivo, inicio = futura
            linha += (
                f" — há edição posterior (`{arquivo}`) que só entra em vigor em "
                f"{date.fromisoformat(inicio):%d/%m/%Y} e por isso não foi utilizada"
            )
        p.append(linha)
    p.append(
        "- Toda citação deste laudo foi conferida item a item contra o texto oficial "
        "publicado pelo MTE. Citação não localizada na base é removida antes da emissão."
    )
    p.append("")
    p.append(
        "*Documento gerado por sistema de apoio à inspeção. Não substitui laudo assinado "
        "por profissional legalmente habilitado.*"
    )
    return "\n".join(p)


def consolidado(
    laudos: list[tuple[str, Laudo]],
    base: BaseNormativa,
    quando: date,
    nao_auditadas: list[tuple[str, str]] | None = None,
) -> str:
    """Sumário executivo de um lote de fotos.

    `nao_auditadas` são as imagens que entraram no lote e não produziram laudo,
    como (nome, motivo). Elas precisam aparecer no documento: um sumário que diz
    "14 imagens analisadas" quando o engenheiro enviou 17 deixa três fotos fora
    do laudo sem que ninguém perceba, e o silêncio se lê como ausência de achado.
    """
    total = sum(len(l.nao_conformidades) for _, l in laudos)
    por_gravidade: dict[str, int] = {}
    por_nr: dict[str, int] = {}
    for _, laudo in laudos:
        for nc in laudo.nao_conformidades:
            por_gravidade[nc.gravidade] = por_gravidade.get(nc.gravidade, 0) + 1
            por_nr[nc.item.nr] = por_nr.get(nc.item.nr, 0) + 1

    p: list[str] = []
    p.append("# Sumário executivo da inspeção")
    p.append("")
    p.append(f"**Data de referência:** {quando:%d/%m/%Y}  ")
    if nao_auditadas:
        enviadas = len(laudos) + len(nao_auditadas)
        p.append(
            f"**Imagens analisadas:** {len(laudos)} de {enviadas} enviadas "
            f"— {len(nao_auditadas)} não auditada(s), ver o fim deste sumário  "
        )
    else:
        p.append(f"**Imagens analisadas:** {len(laudos)}  ")
    p.append(f"**Não conformidades caracterizadas:** {total}")
    p.append("")

    if total:
        p.append("## Distribuição por gravidade")
        p.append("")
        p.append("| Gravidade | Ocorrências |")
        p.append("|---|---|")
        for chave in ("critica", "alta", "media", "baixa"):
            if chave in por_gravidade:
                p.append(f"| **{SELOS[chave]}** | {por_gravidade[chave]} |")
        p.append("")

        p.append("## Normas mais acionadas")
        p.append("")
        p.append("| Norma | Título | Ocorrências |")
        p.append("|---|---|---|")
        for nr, n in sorted(por_nr.items(), key=lambda kv: (-kv[1], kv[0])):
            p.append(f"| **{nr}** | {_titulo_nr(nr)} | {n} |")
        p.append("")

        p.append("## Plano de ação priorizado")
        p.append("")
        p.append("| Prazo | Imagem | Providência | Norma |")
        p.append("|---|---|---|---|")
        pendencias = [
            (nc, nome)
            for nome, laudo in laudos
            for nc in laudo.nao_conformidades
        ]
        pendencias.sort(key=lambda t: (t[0].prioridade, t[0].prazo_dias))
        for nc, nome in pendencias:
            p.append(
                f"| {nc.prazo_dias} d | {nome} | {nc.acao_corretiva} | "
                f"{nc.item.nr} `{nc.item.item}` |"
            )
        p.append("")
    else:
        p.append("Nenhuma não conformidade foi caracterizada no lote analisado.")
        p.append("")

    if nao_auditadas:
        p.append("## Imagens não auditadas")
        p.append("")
        p.append(
            "Estas imagens faziam parte do lote e não produziram laudo. "
            "**Não foram examinadas** — a ausência de constatação sobre elas não "
            "significa ausência de risco. Reprocessar antes de dar o lote por concluído."
        )
        p.append("")
        p.append("| Imagem | Motivo |")
        p.append("|---|---|")
        for nome, motivo in nao_auditadas:
            p.append(f"| {nome} | {motivo} |")
        p.append("")

    return "\n".join(p)


def para_html(markdown_texto: str, titulo: str = "Relatório de Inspeção") -> str:
    """HTML autocontido e imprimível, para arquivar ou virar PDF pelo navegador."""
    corpo = _markdown_simples(markdown_texto)
    return f"""<!doctype html>
<html lang="pt-BR"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{html.escape(titulo)}</title>
<style>
  :root {{ color-scheme: light; }}
  body {{ font-family: -apple-system, "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
         max-width: 900px; margin: 0 auto; padding: 40px 24px; line-height: 1.6;
         color: #1a1d21; background: #fff; }}
  h1 {{ font-size: 1.7rem; border-bottom: 3px solid #0b5fff; padding-bottom: .4em; }}
  h2 {{ font-size: 1.25rem; margin-top: 2em; border-bottom: 1px solid #dfe3e8; padding-bottom: .3em; }}
  h3 {{ font-size: 1.05rem; margin-top: 1.6em; }}
  h4 {{ font-size: 1rem; margin-top: 1.4em; color: #0b3d91; }}
  table {{ border-collapse: collapse; width: 100%; margin: 1em 0; font-size: .92rem; }}
  th, td {{ border: 1px solid #d8dde3; padding: 8px 10px; text-align: left; vertical-align: top; }}
  th {{ background: #f2f5f9; font-weight: 600; }}
  blockquote {{ border-left: 4px solid #0b5fff; background: #f6f9ff; margin: 1em 0;
                padding: .8em 1.1em; font-size: .93rem; color: #2a3138; }}
  code {{ background: #eef1f5; padding: 1px 5px; border-radius: 3px; font-size: .9em; }}
  hr {{ border: 0; border-top: 1px solid #dfe3e8; margin: 2.4em 0; }}
  @media print {{ body {{ padding: 0; max-width: none; }} h2 {{ page-break-after: avoid; }} }}
</style></head><body>
{corpo}
</body></html>"""


def _markdown_simples(texto: str) -> str:
    """Conversor mínimo: só o subconjunto de markdown que este módulo emite."""
    import re

    saida: list[str] = []
    tabela: list[str] = []

    def descarregar_tabela() -> None:
        if not tabela:
            return
        linhas = [l.strip().strip("|").split("|") for l in tabela]
        corpo = [l for l in linhas if not all(set(c.strip()) <= set("-: ") for c in l)]
        if not corpo:
            tabela.clear()
            return
        cab, *resto = corpo
        saida.append("<table><thead><tr>" + "".join(
            f"<th>{_inline(c.strip())}</th>" for c in cab) + "</tr></thead><tbody>")
        for linha in resto:
            saida.append("<tr>" + "".join(f"<td>{_inline(c.strip())}</td>" for c in linha) + "</tr>")
        saida.append("</tbody></table>")
        tabela.clear()

    em_lista = False
    for linha in texto.splitlines():
        crua = linha.rstrip()
        if crua.lstrip().startswith("|"):
            if em_lista:
                saida.append("</ul>"); em_lista = False
            tabela.append(crua)
            continue
        descarregar_tabela()

        if (m := re.match(r"^(#{1,6})\s+(.*)$", crua)):
            if em_lista:
                saida.append("</ul>"); em_lista = False
            n = len(m.group(1))
            saida.append(f"<h{n}>{_inline(m.group(2))}</h{n}>")
        elif crua.startswith("> "):
            if em_lista:
                saida.append("</ul>"); em_lista = False
            saida.append(f"<blockquote>{_inline(crua[2:])}</blockquote>")
        elif (m := re.match(r"^(\s*)[-*]\s+(.*)$", crua)):
            if not em_lista:
                saida.append("<ul>"); em_lista = True
            saida.append(f"<li>{_inline(m.group(2))}</li>")
        elif crua.strip() == "---":
            if em_lista:
                saida.append("</ul>"); em_lista = False
            saida.append("<hr>")
        elif not crua.strip():
            if em_lista:
                saida.append("</ul>"); em_lista = False
        else:
            if em_lista:
                saida.append("</ul>"); em_lista = False
            saida.append(f"<p>{_inline(crua)}</p>")

    descarregar_tabela()
    if em_lista:
        saida.append("</ul>")
    return "\n".join(saida)


def _inline(texto: str) -> str:
    import re

    escapado = html.escape(texto)
    escapado = re.sub(r"`([^`]+)`", r"<code>\1</code>", escapado)
    escapado = re.sub(r"\*\*([^*]+)\*\*", r"<strong>\1</strong>", escapado)
    escapado = re.sub(r"\*([^*]+)\*", r"<em>\1</em>", escapado)
    return escapado
