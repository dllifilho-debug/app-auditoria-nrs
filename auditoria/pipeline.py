"""O Gauntlet Loop da auditoria: executores, supervisor e critério de aceite.

A regra que organiza tudo: **o modelo escolhe, o código cita**. Nenhum agente
escreve um número de item de NR no laudo. Eles apenas apontam para entradas de
um dossiê (D1, D2, D3…) que o código montou a partir dos PDFs oficiais; na hora
de imprimir, o código troca o rótulo pelo número e pelo texto verbatim da norma.
Alucinar uma citação deixa de ser improvável e passa a ser impossível.

    Olho (visão)  →  Dossiê (código)  →  Analista  →  Aferição (código)
                                            ↑                ↓
                                            └──── Diretor ────┘
"""

import json
import re
from dataclasses import dataclass, field
from datetime import date
from typing import Callable

from . import dossie as mod_dossie
from .catalogo_nr import CATALOGO_NR
from .kb import BaseNormativa, Item
from .modelos import Conversador, ErroDeAuditoria
from .riscos import Risco, catalogo as catalogo_riscos

GRAVIDADE_ORDEM = {"critica": 0, "alta": 1, "media": 2, "baixa": 3}
PRAZO_SUGERIDO = {"critica": 1, "alta": 7, "media": 30, "baixa": 60}


# ---------------------------------------------------------------------------
# Resultados intermediários
# ---------------------------------------------------------------------------

@dataclass
class Achado:
    fato: str
    onde: str = ""
    confianca: str = "media"


@dataclass
class Visao:
    ambiente: str = ""
    pessoas_presentes: bool = False
    quantidade_pessoas: int = 0
    achados: list[Achado] = field(default_factory=list)
    bruto: str = ""

    def textos(self) -> list[str]:
        return [a.fato for a in self.achados]

    def resumo(self) -> str:
        pessoas = (
            f"{self.quantidade_pessoas} trabalhador(es) visível(is)"
            if self.pessoas_presentes else "nenhum trabalhador visível na cena"
        )
        linhas = [f"Ambiente: {self.ambiente or 'não caracterizado'}", f"Pessoas: {pessoas}"]
        linhas += [f"- {a.fato}" + (f" ({a.onde})" if a.onde else "") for a in self.achados]
        return "\n".join(linhas)


@dataclass
class NaoConformidade:
    item: Item
    constatacao: str
    consequencia: str
    gravidade: str
    acao_corretiva: str
    prazo_dias: int
    rotulo_risco: str = ""

    @property
    def prioridade(self) -> int:
        return GRAVIDADE_ORDEM.get(self.gravidade, 9)


@dataclass
class Laudo:
    visao: Visao
    nao_conformidades: list[NaoConformidade] = field(default_factory=list)
    sem_enquadramento: list[str] = field(default_factory=list)
    conformidades: list[str] = field(default_factory=list)
    nrs_sem_texto: list[str] = field(default_factory=list)
    parecer_diretor: str = ""
    ciclos: int = 1
    vetos: list[str] = field(default_factory=list)
    afericoes: list[str] = field(default_factory=list)
    data_referencia: date = field(default_factory=date.today)
    tokens: int = 0
    # O agente de visão devolveu resposta sem nenhum fato utilizável.
    visao_falhou: bool = False

    @property
    def aprovado(self) -> bool:
        return not self.vetos

    def quantidade_pessoas_texto(self) -> str:
        if not self.visao.pessoas_presentes:
            return "nenhum"
        n = self.visao.quantidade_pessoas
        return f"{n}" if n else "presentes"


# ---------------------------------------------------------------------------
# Utilidades
# ---------------------------------------------------------------------------

RE_BLOCO_JSON = re.compile(r"\{.*\}", re.DOTALL)


def _primeiro_objeto(texto: str) -> dict | None:
    """Extrai o primeiro objeto JSON completo do texto, contando chaves.

    Sem o modo JSON estrito o modelo pode devolver raciocínio em volta da
    resposta. Casar do primeiro "{" ao último "}" quebra quando há chaves na
    prosa; equilibrar as chaves — e ignorar as que estiverem dentro de string —
    acha o objeto de verdade.
    """
    for inicio, caractere in enumerate(texto):
        if caractere != "{":
            continue
        profundidade, em_texto, escapado = 0, False, False
        for fim in range(inicio, len(texto)):
            atual = texto[fim]
            if escapado:
                escapado = False
                continue
            if atual == "\\" and em_texto:
                escapado = True
            elif atual == '"':
                em_texto = not em_texto
            elif not em_texto and atual == "{":
                profundidade += 1
            elif not em_texto and atual == "}":
                profundidade -= 1
                if profundidade == 0:
                    try:
                        return json.loads(texto[inicio: fim + 1])
                    except json.JSONDecodeError:
                        break
    return None


def _ler_json(texto: str, onde: str) -> dict:
    """Extrai o objeto JSON da resposta, tolerando cercas de markdown."""
    limpo = texto.strip()
    limpo = re.sub(r"^```(?:json)?|```$", "", limpo, flags=re.MULTILINE).strip()
    try:
        return json.loads(limpo)
    except json.JSONDecodeError:
        pass
    if (objeto := _primeiro_objeto(limpo)) is not None:
        return objeto
    raise ErroDeAuditoria(
        f"O agente {onde} não devolveu JSON utilizável.",
        "Costuma ser resposta cortada por falta de cota. Tente de novo em um minuto.",
        recuperavel=True,
    )


# ---------------------------------------------------------------------------
# Etapa 1 — Agente Olho
# ---------------------------------------------------------------------------

PROMPT_OLHO = """Você é perito em documentação fotográfica de ambientes de trabalho. Descreva APENAS o que a imagem mostra.

PROIBIDO, sem exceção:
- citar norma, NR, lei ou item;
- julgar risco, dizer que algo é irregular, propor solução;
- afirmar material ou finalidade que você não consegue verificar (escreva "placa rígida clara", não "laje de concreto"; "tela plástica flexível de malha larga", não "rede de proteção");
- inventar pessoa, equipamento ou detalhe que não esteja visível.

Se não houver pessoa na imagem, "pessoas.presentes" é false — não invente ninguém.

Responda SOMENTE com este JSON:
{
  "ambiente": "<que tipo de local é, em uma frase>",
  "pessoas": {"presentes": <true|false>, "quantidade": <n>, "descricao": "<o que fazem, ou vazio>"},
  "achados": [
    {"fato": "<uma condição física concreta e verificável>", "onde": "<posição na imagem>", "confianca": "alta|media|baixa"}
  ]
}

Registre de 3 a 8 achados. Cada "fato" deve ser autossuficiente: descreva o objeto, seu estado
e sua relação com o entorno ("placa de madeira apoiada solta sobre abertura quadrada no piso,
sem fixação visível"), nunca só o nome do objeto ("uma placa").

Descrever atributo não é julgar: juízo é o que duas pessoas podem discordar vendo a mesma foto
("seguro", "adequado", "protege") — não escreva; atributo as duas veem igual — escreva sempre.
Barreira, tela, rede, lona, grade, corda ou fita em borda, vão ou abertura: diga material e
rigidez (metal/madeira rígidos ou pano/plástico flexíveis), como está presa (montante fixado,
pregada em ripa, amarrada, apoiada em cone, pendurada), se fecha o vão todo ou deixa trecho
aberto, altura ante o corpo (joelho, cintura, peito) e estado (íntegro, rasgado, frouxo, esgarçado).
Máquina, painel elétrico, andaime, escada, cinta, cabo ou gancho: diga o estado da superfície
(corroído, amassado, queimado, esfiapado, fios rompidos) e as peças que vê e as que não vê
(trava do gancho, guarda-corpo e rodapé do andaime, tampa do painel, proteção de partes móveis).
Só escreva "sem <peça> visível" quando o lugar dela aparece vazio na foto; senão, "não dá para ver"."""


def agente_olho(cliente: Conversador, imagem_b64: str, modelo: str, contexto: str = "") -> Visao:
    conteudo: list[dict] = [{"type": "text", "text": PROMPT_OLHO}]
    if contexto.strip():
        conteudo.append({
            "type": "text",
            "text": f"\nContexto informado pelo inspetor (use só para nomear o ambiente, "
                    f"nunca para inventar o que não está na foto): {contexto.strip()}",
        })
    conteudo.append({
        "type": "image_url",
        "image_url": {"url": f"data:image/jpeg;base64,{imagem_b64}"},
    })

    mensagens = [{"role": "user", "content": conteudo}]
    bruto = cliente.conversar(
        modelo=modelo, mensagens=mensagens, teto_saida=1600,
        temperatura=0.0, json_estrito=True,
    )

    # Resposta cortada no teto não é resposta: é meia frase. Quando a API diz
    # que foi isso que aconteceu, uma segunda tentativa com mais espaço é bem
    # mais barata do que um laudo perdido — e o sinal vem da própria API, não
    # de suposição nossa.
    if getattr(cliente, "ultimo_corte_por_limite", False):
        bruto = cliente.conversar(
            modelo=modelo, mensagens=mensagens, teto_saida=3200,
            temperatura=0.0, json_estrito=True,
        )

    try:
        dados = _ler_json(bruto, "Olho")
    except ErroDeAuditoria:
        # Guardamos o texto cru para a tela de diagnóstico antes de desistir.
        return Visao(bruto=bruto)
    pessoas = dados.get("pessoas") or {}
    achados = [
        Achado(
            fato=str(a.get("fato", "")).strip(),
            onde=str(a.get("onde", "")).strip(),
            confianca=str(a.get("confianca", "media")).strip().lower(),
        )
        for a in dados.get("achados", [])
        if str(a.get("fato", "")).strip()
    ]
    return Visao(
        ambiente=str(dados.get("ambiente", "")).strip(),
        pessoas_presentes=bool(pessoas.get("presentes")),
        quantidade_pessoas=int(pessoas.get("quantidade") or 0),
        achados=achados,
        bruto=bruto,
    )


# ---------------------------------------------------------------------------
# Etapa 2 — Roteamento e dossiê (100% determinístico)
# ---------------------------------------------------------------------------

RE_PALAVRA = re.compile(r"[a-z0-9]+")


PLURAIS = (("ais", "al"), ("eis", "el"), ("ois", "ol"), ("uis", "ul"),
           ("oes", "ao"), ("aes", "ao"), ("ns", "m"))


def _radical(palavra: str) -> str:
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
            if palavra.endswith("s") and len(palavra) > 4:
                palavra = palavra[:-1]
    if len(palavra) > 4 and palavra[-1] in "aeo":
        palavra = palavra[:-1]
    return palavra


def _radicais(texto: str) -> set[str]:
    from .kb import normalizar

    return {_radical(p) for p in RE_PALAVRA.findall(normalizar(texto)) if len(p) > 2}


def rotear_riscos(visao: Visao, contexto: str = "") -> list[Risco]:
    """Casa os fatos observados com a taxonomia curada de riscos.

    O casamento é por sobreposição de radicais, não por substring: quem descreve
    a foto escreve "Entulho, cacos e sobras de material espalhados", e o sinal
    cadastrado é "entulho espalhado". Exigir a frase literal perderia o risco.

    Cada achado é seu próprio pedaço (fragmento) para efeito de cobertura: um
    sinal de várias palavras só pontua se todas — ou quase todas — vierem do
    MESMO achado. Sem isso, "escada apoiada solta na parede" batia numa foto
    sem escada nenhuma porque "apoiada" e "solta" vinham do achado da placa sobre
    a abertura no piso e "parede" vinha de um achado totalmente diferente sobre
    madeira empilhada — três fatos sem relação nenhuma, somados por acaso.

    Ambiente e contexto não formam fragmento à parte: entram junto de CADA
    achado, porque descrevem a cena inteira e legitimamente completam um sinal
    ao lado de qualquer fato específico (ex.: ambiente "portão de acesso ao
    elevador" + achado "painel com fiação" formam "acesso ao elevador... com").
    """
    extra = _radicais(" | ".join(t for t in (visao.ambiente, contexto) if t))
    fragmentos = [f | extra for f in (_radicais(t) for t in visao.textos()) if f]
    if not fragmentos and extra:
        fragmentos = [extra]

    encontrados: list[tuple[float, Risco]] = []

    for risco in catalogo_riscos().values():
        pontos = 0.0
        for sinal in risco.sinais:
            termos = _radicais(sinal)
            if not termos:
                continue
            cobertura = max((len(termos & f) / len(termos) for f in fragmentos), default=0.0)
            # Sinal de uma palavra precisa bater inteiro; sinal composto aceita
            # que uma peça falte, desde que o essencial esteja lá.
            if cobertura == 1.0:
                pontos += 1.0 + 0.25 * (len(termos) - 1)
            elif len(termos) >= 3 and cobertura >= 0.7:
                pontos += 0.5
        if pontos:
            encontrados.append((pontos, risco))

    encontrados.sort(key=lambda p: (-p[0], GRAVIDADE_ORDEM.get(p[1].gravidade_base, 9)))
    return [r for _, r in encontrados]


def montar_dossie(
    base: BaseNormativa,
    visao: Visao,
    contexto: str,
    quando: date,
    teto: int = 22,
) -> tuple[mod_dossie.Dossie, dict[str, Risco]]:
    """Dossiê = itens dos riscos roteados (prioridade) + reforço por busca textual."""
    riscos = rotear_riscos(visao, contexto)

    curados: list[tuple[Item, Risco]] = []
    vistos: set[str] = set()
    for risco in riscos:
        if not risco.exige_pessoa or visao.pessoas_presentes:
            for ref in risco.itens:
                nr, _, num = ref.partition(" ")
                item = base.obter(nr, num)
                if item is not None and item.id not in vistos and item.vigente_em(quando):
                    vistos.add(item.id)
                    curados.append((item, risco))

    complemento = mod_dossie.montar(
        base, visao.textos(), contexto=contexto, quando=quando,
        teto=max(teto - len(curados), 4),
    )

    entradas: list[mod_dossie.Entrada] = []
    origem: dict[str, Risco] = {}
    for item, risco in curados[:teto]:
        rotulo = f"D{len(entradas) + 1}"
        entradas.append(mod_dossie.Entrada(rotulo, item, risco.rotulo))
        origem[rotulo] = risco
    for entrada in complemento.entradas:
        if len(entradas) >= teto:
            break
        if entrada.item.id in vistos:
            continue
        vistos.add(entrada.item.id)
        entradas.append(mod_dossie.Entrada(f"D{len(entradas) + 1}", entrada.item, entrada.origem))

    return (
        mod_dossie.Dossie(
            entradas=entradas,
            nrs_candidatas=sorted({e.item.nr for e in entradas}),
            nrs_sem_texto=complemento.nrs_sem_texto,
            data_referencia=quando,
        ),
        origem,
    )


# ---------------------------------------------------------------------------
# Etapa 3 — Agente Analista
# ---------------------------------------------------------------------------

PROMPT_ANALISTA = """Você é engenheiro de segurança do trabalho enquadrando os fatos de uma inspeção.

FATOS OBSERVADOS NA FOTO
{fatos}

CONTEXTO DA INSPEÇÃO: {contexto}
DATA DE REFERÊNCIA: {data}

DOSSIÊ NORMATIVO — os únicos enquadramentos disponíveis
{dossie}

REGRAS INEGOCIÁVEIS
1. Só existe uma não conformidade se um item do dossiê acima for descumprido POR UM FATO da lista.
   Referencie o item pelo rótulo (D1, D7…). Nunca escreva número de NR no texto: o sistema
   insere a citação correta sozinho.
2. Se um fato PREOCUPA mas nenhum item do dossiê o cobre, escreva-o em "sem_enquadramento".
   É melhor do que forçar um item que não se aplica. Mas isso não é inventário da
   foto: objeto em estado normal — uma tomada íntegra, um interruptor comum — não
   entra ali. Só entra o que você apontaria a um engenheiro para ele ir verificar.
3. LEIA o texto do item antes de usá-lo. Item sobre andaime não enquadra buraco no chão;
   item sobre guarda-corpo de periferia não enquadra abertura no piso.
4. {regra_pessoas}
5. "constatacao" descreve o que a foto mostra e por que aquilo descumpre o item — sem adjetivo
   dramático, sem "gravíssimo", sem "risco iminente de morte".
6. Um item, uma não conformidade. Não repita o mesmo item.

Responda SOMENTE com este JSON:
{{
  "nao_conformidades": [
    {{"dossie": "D<n>",
      "constatacao": "<o fato e o descumprimento, 1-2 frases>",
      "consequencia": "<o dano que pode ocorrer, 1 frase objetiva>",
      "gravidade": "critica|alta|media|baixa",
      "acao_corretiva": "<providência concreta e executável>",
      "prazo_dias": <inteiro>}}
  ],
  "sem_enquadramento": ["<fato preocupante sem item aplicável no dossiê>"],
  "conformidades": ["<boa prática visível na foto, se houver>"]
}}"""

REGRA_SEM_PESSOAS = (
    "NÃO há trabalhador na foto. É PROIBIDO apontar falta de EPI, de capacitação, "
    "de treinamento, de supervisão ou de conduta de pessoa. Restrinja-se às condições físicas do local."
)
REGRA_COM_PESSOAS = (
    "Há trabalhador na foto. Aponte falha de EPI ou de conduta apenas se a imagem mostrar isso "
    "claramente; ausência de documento (treinamento, ordem de serviço) não se enxerga em foto."
)


def agente_analista(
    cliente: Conversador,
    visao: Visao,
    dossie_atual: mod_dossie.Dossie,
    contexto: str,
    modelo: str,
    correcoes: str = "",
) -> dict:
    prompt = PROMPT_ANALISTA.format(
        fatos=visao.resumo(),
        contexto=contexto.strip() or "não informado",
        data=dossie_atual.data_referencia.strftime("%d/%m/%Y"),
        dossie=dossie_atual.texto(),
        regra_pessoas=REGRA_COM_PESSOAS if visao.pessoas_presentes else REGRA_SEM_PESSOAS,
    )
    if correcoes:
        prompt += (
            "\n\nO DIRETOR TÉCNICO REPROVOU A VERSÃO ANTERIOR. Corrija exatamente estes pontos "
            "e não repita os enquadramentos vetados:\n" + correcoes
        )
    bruto = cliente.conversar(
        modelo=modelo,
        mensagens=[{"role": "user", "content": prompt}],
        teto_saida=1800,
        temperatura=0.1,
        json_estrito=True,
    )
    return _ler_json(bruto, "Analista")


# ---------------------------------------------------------------------------
# Etapa 4 — Aferição determinística
# ---------------------------------------------------------------------------

def aferir(
    proposta: dict,
    dossie_atual: mod_dossie.Dossie,
    origem: dict[str, Risco],
    visao: Visao,
    quando: date,
) -> tuple[list[NaoConformidade], list[str]]:
    """Converte a proposta do analista em não conformidades citáveis.

    Tudo que não passa por aqui é descartado com motivo registrado: rótulo
    inexistente, item fora de vigência, cobrança de EPI sem gente na foto,
    item repetido. Esta função é o motivo de o laudo não poder mentir.
    """
    aprovadas: list[NaoConformidade] = []
    recusas: list[str] = []
    indice = dossie_atual.indice
    usados: set[str] = set()

    for cru in proposta.get("nao_conformidades", []):
        rotulo = str(cru.get("dossie", "")).strip().upper()
        item = indice.get(rotulo)

        if item is None:
            recusas.append(f"referência {rotulo or '(vazia)'} não existe no dossiê — descartada")
            continue
        if item.id in usados:
            recusas.append(f"{item.nr} {item.item} citado mais de uma vez — mantida a primeira")
            continue
        if not item.vigente_em(quando):
            recusas.append(f"{item.nr} {item.item} não está vigente em {quando:%d/%m/%Y} — descartada")
            continue

        risco = origem.get(rotulo)
        if risco is not None and risco.exige_pessoa and not visao.pessoas_presentes:
            recusas.append(
                f"{item.nr} {item.item} exige trabalhador na cena e não há nenhum — descartada"
            )
            continue

        gravidade = str(cru.get("gravidade", "")).strip().lower()
        if gravidade not in GRAVIDADE_ORDEM:
            gravidade = risco.gravidade_base if risco else "media"

        try:
            prazo = int(cru.get("prazo_dias") or 0)
        except (TypeError, ValueError):
            prazo = 0
        if prazo <= 0:
            prazo = PRAZO_SUGERIDO[gravidade]
        # O prazo do modelo é aceito, mas nunca acima do teto da gravidade que
        # ele mesmo atribuiu: um laudo real saiu com "crítica — ação imediata"
        # no sumário e "7 dias" na tabela, contradição que o inspetor leva para
        # a obra. Quem manda é a gravidade; prazo mais curto continua valendo.
        prazo = min(prazo, PRAZO_SUGERIDO[gravidade])

        usados.add(item.id)
        aprovadas.append(
            NaoConformidade(
                item=item,
                constatacao=_limpar_citacoes(str(cru.get("constatacao", "")).strip()),
                consequencia=_limpar_citacoes(str(cru.get("consequencia", "")).strip()),
                gravidade=gravidade,
                acao_corretiva=_limpar_citacoes(str(cru.get("acao_corretiva", "")).strip()),
                prazo_dias=prazo,
                rotulo_risco=risco.rotulo if risco else "",
            )
        )

    aprovadas.sort(key=lambda n: (n.prioridade, n.item.nr, n.item.item))
    return aprovadas, recusas


# Citação que o modelo escreveu por conta própria, incluindo o número do item
# que costuma vir logo atrás ("NR-35, item 35.2.1"). Deixar o número para trás
# seria pior que não limpar nada: o renderizador o releria como citação válida.
RE_CITACAO_SOLTA = re.compile(
    r"\s*[(\[]?\bNR[\s\-\u2011\u2013\u2014]?\d{1,2}\b"
    r"(?:\s*[-\u2013\u2014,;:]?\s*(?:sub)?ite(?:m|ns))?"
    r"(?:\s*\d{1,2}(?:\.\d{1,3})*(?:\s*(?:e|ou|,)\s*\d{1,2}(?:\.\d{1,3})*)*)?"
    # Cauda de lista abreviada de subitens ("18.9.4.1/2", "18.9.4.1 ou .2").
    # Sem ela a regex comia o miolo e deixava ".1/2." pendurado — visto em laudo real.
    r"(?:\s*(?:/|ou|e)\s*\.?\d{1,3}(?:\.\d{1,3})*)*"
    r"[)\]]?(?=[\s,.;:)\]]|$)",
    re.IGNORECASE,
)

# Preposição que fica órfã quando a citação some do meio da frase.
# O `\s*` (em vez de `\s+`) é essencial: quando a citação estava no fim da frase
# ("…sistema de proteção conforme NR-18 18.9.2."), a remoção encosta a preposição
# na pontuação e não sobra espaço nenhum — era assim que "conforme." vazava para
# o laudo. Exigir espaço aqui deixava passar justamente o caso mais comum.
RE_ORFA = re.compile(r"\b(?:na|no|da|do|de|a|o|em|com|conforme|segundo|pela|pelo)\s*(?=[,.;]|$)",
                     re.IGNORECASE)


def _limpar_citacoes(texto: str) -> str:
    """Remove citação escrita à mão pelo modelo — quem cita aqui é o renderizador.

    O laudo só pode conter as citações que o código emitiu a partir da base.
    Qualquer referência normativa que o modelo tenha digitado no meio da prosa
    é apagada aqui, junto com o número do item, antes de chegar ao documento.
    """
    limpo = RE_CITACAO_SOLTA.sub("", texto)
    if limpo == texto:
        return texto.strip()

    # Uma passada só não basta: tirar a citação de "conforme a NR-18, …" deixa
    # "conforme a," e, removido o "a", sobra o "conforme" — que só então fica
    # órfão. Repetimos até estabilizar, com teto para não girar à toa.
    for _ in range(4):
        antes = limpo
        limpo = RE_ORFA.sub("", limpo)
        limpo = re.sub(r"\s{2,}", " ", limpo)
        limpo = re.sub(r"\s+([,.;:])", r"\1", limpo)
        # Pontuação que ficou encostada na pontuação seguinte (", ." → ".").
        limpo = re.sub(r"[,;:]+(?=[.!?])", "", limpo)
        limpo = re.sub(r"([,;:])\s*\1+", r"\1", limpo)
        if limpo == antes:
            break

    limpo = re.sub(r"[\s,;:]+$", "", limpo).strip()
    # Citação que abria a frase ("Conforme a NR-18, a remoção…") deixa a vírgula
    # órfã na frente; a maiúscula perdida volta com a palavra que assumiu o início.
    if (sem_borda := re.sub(r"^[\s,;:.]+", "", limpo)) != limpo:
        limpo = sem_borda[:1].upper() + sem_borda[1:] if sem_borda else ""
    if not limpo:
        return texto.strip()
    return limpo if limpo[-1] in ".!?" else limpo + "."


# ---------------------------------------------------------------------------
# Etapa 5 — Agente Diretor (supervisor)
# ---------------------------------------------------------------------------

PROMPT_DIRETOR = """Você é o Diretor Técnico. Uma assinatura sua num laudo errado custa a sua credibilidade.
Audite o laudo abaixo INTEIRO com ceticismo. Seu trabalho não é elogiar: é derrubar o que não se sustenta.

FATOS DA FOTO
{fatos}

ENQUADRAMENTOS PROPOSTOS (com o texto oficial da norma citada)
{enquadramentos}

PONTOS DE ATENÇÃO PROPOSTOS (sem enquadramento normativo)
{pontos}

CONFORMIDADES PROPOSTAS
{conformidades}

PARTE 1 — CONFERÊNCIA OBRIGATÓRIA DOS ENQUADRAMENTOS
Para CADA [V<n>], antes de decidir qualquer coisa, copie o trecho LITERAL do fato
da lista acima que sustenta a constatação. Copiar, não resumir nem parafrasear.
Se você não encontrar um fato que sustente a constatação inteira, o enquadramento
está vetado — sem exceção. Esta conferência é o que separa o que a câmera
registrou do que soa plausível: "escada apoiada no piso" NÃO sustenta "sem sapata
antiderrapante", e "madeira empilhada" NÃO sustenta "sem retirada de pregos".

PARTE 2 — VETE um enquadramento quando:
a) o texto do item NÃO trata da situação descrita (o erro mais comum e o mais grave).
   Item que regula documento, inventário, treinamento ou registro NUNCA enquadra
   condição física de uma foto;
b) a conferência da Parte 1 não achou fato que sustente a constatação;
c) cobra EPI, treinamento ou conduta sem trabalhador visível na cena;
d) a linguagem é alarmista ou a gravidade está inflada frente ao que se vê.

A gravidade deve ser coerente entre os enquadramentos do mesmo laudo: se dois
enquadramentos descrevem o MESMO problema físico, devem ter a mesma gravidade e
o mesmo prazo. Ajuste quando divergirem.

APROVE o que estiver correto, mesmo que simples. Vetar o que está certo também é erro.

PARTE 3 — DESCARTE ponto de atenção [P<n>] quando:
- for inventário da foto, e não risco: objeto em estado normal para uma obra em
  andamento (parede sem reboco, marca de fôrma no concreto, tijolo aparente,
  ferramenta apoiada no chão, sujeira) não é ponto de atenção;
- disser a mesma coisa que um enquadramento que você aprovou — não repita;
- afirmar mais do que o fato registra, pela mesma régua da Parte 1.
Mantenha o que você apontaria a um engenheiro para ele ir verificar no local.

PARTE 4 — DESCARTE conformidade [C<n>] quando ela elogiar exatamente o que um
enquadramento ou um ponto de atenção critica. Um laudo não pode aprovar e reprovar
o mesmo objeto.

Responda SOMENTE com este JSON:
{{
  "conferencia": [{{"ref": "V<n>", "fato": "<trecho literal do fato que sustenta, ou vazio se não houver>"}}],
  "vetados": [{{"ref": "V<n>", "motivo": "<por que não se sustenta>"}}],
  "ajustes": [{{"ref": "V<n>", "constatacao": "<reescrita, ou omita>", "acao_corretiva": "<reescrita, ou omita>", "gravidade": "critica|alta|media|baixa"}}],
  "pontos_descartados": [{{"ref": "P<n>", "motivo": "<por que sai>"}}],
  "conformidades_descartadas": [{{"ref": "C<n>", "motivo": "<por que sai>"}}],
  "parecer": "<2-3 frases sobre o risco predominante, considerando APENAS o que você aprovou. Se vetou tudo, diga que nada se sustentou — não descreva achados que você mesmo derrubou. Escreva para o engenheiro que vai ler o laudo: nunca mencione os rótulos V, P ou C>"
}}"""

SEM_ITENS = "(nenhum)"


def _rotular(itens: list[str], letra: str) -> str:
    return "\n".join(f"[{letra}{n}] {t}" for n, t in enumerate(itens, start=1)) or SEM_ITENS


def agente_diretor(
    cliente: Conversador,
    visao: Visao,
    aprovadas: list[NaoConformidade],
    sem_enquadramento: list[str],
    conformidades: list[str],
    modelo: str,
) -> dict:
    """Audita o laudo inteiro numa única chamada.

    Os pontos de atenção e as conformidades entram aqui — antes iam do Analista
    direto para o documento, sem supervisão de ninguém. Era onde sobreviviam o
    inventário da foto ("parede sem reboco") e a contradição de elogiar e criticar
    o mesmo objeto. Alargar esta chamada custa poucos tokens de entrada; abrir uma
    quarta chamada custaria uma rodada inteira por foto.
    """
    blocos = []
    for n, nc in enumerate(aprovadas, start=1):
        blocos.append(
            f"[V{n}] {nc.item.nr} {nc.item.item}\n"
            f"  TEXTO OFICIAL: {nc.item.resumo(340)}\n"
            f"  CONSTATAÇÃO: {nc.constatacao}\n"
            f"  GRAVIDADE: {nc.gravidade} | AÇÃO: {nc.acao_corretiva}"
        )
    prompt = PROMPT_DIRETOR.format(
        fatos=visao.resumo(),
        enquadramentos="\n\n".join(blocos) or SEM_ITENS,
        pontos=_rotular(sem_enquadramento, "P"),
        conformidades=_rotular(conformidades, "C"),
    )
    bruto = cliente.conversar(
        modelo=modelo,
        mensagens=[{"role": "user", "content": prompt}],
        teto_saida=1600,
        temperatura=0.0,
        json_estrito=True,
    )
    return _ler_json(bruto, "Diretor")


# Rótulo interno da conversa com o Diretor que vazou para o parecer de um laudo
# real: "a má fixação dos cabos … (V1)". É andaime de trabalho e não significa
# nada para quem lê o documento.
#
# Só a forma entre parênteses ou colchetes é removida, e é de propósito: em
# projeto estrutural brasileiro V1 é viga 1, P2 é pilar 2 e C1 é coluna 1. Apagar
# o rótulo solto mutilaria a frase de um engenheiro descrevendo a própria obra —
# a mesma armadilha de vocabulário que já custou caro em "carcaça" e "faca".
# Contra o rótulo solto age o prompt, que manda o Diretor nunca mencioná-lo.
RE_ROTULO_INTERNO = re.compile(r"\s*[(\[]\s*[VPC]\d{1,2}\s*[)\]]")


def _sem_rotulo_interno(texto: str) -> str:
    limpo = RE_ROTULO_INTERNO.sub("", texto)
    if limpo == texto:
        return texto
    limpo = re.sub(r"\s{2,}", " ", limpo)
    limpo = re.sub(r"\s+([,.;:])", r"\1", limpo)
    return limpo.strip()


def _descartar(itens: list[str], veredito: dict, chave: str, letra: str) -> list[str]:
    """Remove da lista os índices que o Diretor descartou, pelo rótulo P<n>/C<n>."""
    fora: set[int] = set()
    for registro in veredito.get(chave, []) or []:
        ref = str(registro.get("ref", "")).strip().upper()
        if ref.startswith(letra) and ref[1:].isdigit():
            fora.add(int(ref[1:]))
    return [t for n, t in enumerate(itens, start=1) if n not in fora]


def _parecer_coerente(parecer: str, sobreviventes: list, vetos: list) -> str:
    """Impede o parecer de descrever achados que o próprio supervisor derrubou.

    O parecer é escrito sobre a proposta que o Diretor recebeu, antes de os
    vetos dele serem aplicados. Quando ele veta tudo, o texto continua falando
    em "múltiplas não conformidades" ao lado de um laudo que não tem nenhuma —
    e um documento que se contradiz não se sustenta diante de quem o questione.
    """
    if sobreviventes:
        return parecer
    if not vetos:
        return parecer
    return (
        "Os enquadramentos propostos para esta imagem não se sustentaram na "
        "supervisão técnica e foram recusados, de modo que nenhuma não "
        "conformidade é caracterizada aqui. Isso não atesta conformidade do "
        "local: as condições registradas nos fatos seguem para verificação, "
        "listadas entre os pontos de atenção."
    )


# ---------------------------------------------------------------------------
# O laço
# ---------------------------------------------------------------------------

@dataclass
class Configuracao:
    modelo_visao: str
    modelo_texto: str
    max_ciclos: int = 2
    usar_diretor: bool = True
    teto_dossie: int = 22
    data_referencia: date = field(default_factory=date.today)


def executar(
    cliente: Conversador,
    base: BaseNormativa,
    imagem_b64: str,
    contexto: str,
    config: Configuracao,
    progresso: Callable[[str], None] | None = None,
) -> Laudo:
    """Roda o loop completo para uma foto e devolve o laudo aferido."""
    avisar = progresso or (lambda _m: None)
    quando = config.data_referencia

    avisar("Leitura da imagem — registrando os fatos materiais…")
    visao = agente_olho(cliente, imagem_b64, config.modelo_visao, contexto)
    laudo = Laudo(visao=visao, data_referencia=quando)

    # Sem fato extraído da imagem não existe laudo possível. Deixar o Analista
    # seguir aqui faria o enquadramento nascer do texto que o inspetor digitou,
    # e não do que a câmera registrou — uma não conformidade sem evidência
    # visual, que é exatamente o que este pipeline existe para impedir.
    if not visao.achados:
        laudo.visao_falhou = True
        laudo.parecer_diretor = (
            "O agente de visão não extraiu nenhum fato desta imagem, de modo que "
            "não há evidência visual sobre a qual enquadrar. Nenhuma não "
            "conformidade foi caracterizada — o que não significa que o local "
            "esteja conforme, e sim que esta imagem não permitiu avaliação."
        )
        return laudo

    avisar("Montando o dossiê normativo a partir dos PDFs oficiais…")
    dossie_atual, origem = montar_dossie(base, visao, contexto, quando, config.teto_dossie)

    laudo.nrs_sem_texto = dossie_atual.nrs_sem_texto

    if not dossie_atual.entradas:
        laudo.sem_enquadramento = visao.textos()
        laudo.parecer_diretor = (
            "Nenhum item normativo carregado se aplica aos fatos registrados. "
            "A imagem exige avaliação presencial."
        )
        return laudo

    correcoes = ""
    for ciclo in range(1, max(config.max_ciclos, 1) + 1):
        laudo.ciclos = ciclo
        avisar(f"Enquadramento normativo dos fatos (ciclo {ciclo})…")
        proposta = agente_analista(
            cliente, visao, dossie_atual, contexto, config.modelo_texto, correcoes
        )

        aprovadas, recusas = aferir(proposta, dossie_atual, origem, visao, quando)
        laudo.afericoes = recusas
        laudo.sem_enquadramento = [
            str(s).strip() for s in proposta.get("sem_enquadramento", []) if str(s).strip()
        ]
        laudo.conformidades = [
            str(s).strip() for s in proposta.get("conformidades", []) if str(s).strip()
        ]

        # O Diretor roda mesmo sem nenhuma não conformidade: um laudo com zero
        # enquadramentos e cinco pontos de atenção continua sendo um laudo, e
        # antes saía sem passar por supervisor nenhum. Só pulamos quando não há
        # absolutamente nada para auditar.
        ha_o_que_auditar = bool(aprovadas or laudo.sem_enquadramento or laudo.conformidades)
        if not config.usar_diretor or not ha_o_que_auditar:
            laudo.nao_conformidades = aprovadas
            laudo.vetos = []
            break

        avisar(f"Revisão técnica do laudo (ciclo {ciclo})…")
        veredito = agente_diretor(
            cliente, visao, aprovadas,
            laudo.sem_enquadramento, laudo.conformidades, config.modelo_texto,
        )

        # Descartes do supervisor sobre as duas listas que antes ninguém auditava.
        # Aplicados antes do laço de vetos porque os enquadramentos derrubados são
        # acrescentados aos pontos de atenção logo em seguida, e esses não passam
        # pelo crivo do Diretor — ele não os viu.
        laudo.sem_enquadramento = _descartar(
            laudo.sem_enquadramento, veredito, "pontos_descartados", "P"
        )
        laudo.conformidades = _descartar(
            laudo.conformidades, veredito, "conformidades_descartadas", "C"
        )

        # O motivo do veto é prosa do modelo e sai impresso no laudo, tanto nos
        # pontos de atenção quanto na trilha de auditoria. Passa pela mesma
        # limpeza das constatações: a citação que acompanha o veto é a que o
        # código emite ao lado, nunca a que o supervisor digitou.
        vetados = {
            str(v.get("ref", "")).strip().upper():
                _limpar_citacoes(str(v.get("motivo", "")).strip())
            for v in veredito.get("vetados", [])
        }
        ajustes = {
            str(a.get("ref", "")).strip().upper(): a for a in veredito.get("ajustes", [])
        }

        sobreviventes: list[NaoConformidade] = []
        motivos: list[str] = []
        for n, nc in enumerate(aprovadas, start=1):
            ref = f"V{n}"
            if ref in vetados:
                motivos.append(f"{nc.item.nr} {nc.item.item}: {vetados[ref]}")
                # O veto derruba o enquadramento, não a observação. Um botão de
                # emergência solto continua sendo um problema mesmo quando o item
                # citado para ele estava errado — deixá-lo evaporar seria perder
                # a informação que mais importa ao inspetor.
                laudo.sem_enquadramento.append(
                    f"{nc.constatacao} (enquadramento proposto em "
                    f"{nc.item.nr} {nc.item.item} foi recusado na supervisão: "
                    f"{vetados[ref].rstrip('.')})"
                )
                continue
            if (ajuste := ajustes.get(ref)):
                if (novo := str(ajuste.get("constatacao", "")).strip()):
                    nc.constatacao = _limpar_citacoes(novo)
                if (novo := str(ajuste.get("acao_corretiva", "")).strip()):
                    nc.acao_corretiva = _limpar_citacoes(novo)
                if str(ajuste.get("gravidade", "")).lower() in GRAVIDADE_ORDEM:
                    nc.gravidade = str(ajuste["gravidade"]).lower()
            sobreviventes.append(nc)

        sobreviventes.sort(key=lambda x: (x.prioridade, x.item.nr, x.item.item))
        laudo.nao_conformidades = sobreviventes
        laudo.vetos = motivos
        laudo.parecer_diretor = _parecer_coerente(
            _limpar_citacoes(_sem_rotulo_interno(str(veredito.get("parecer", "")).strip())),
            sobreviventes, motivos,
        )

        if not motivos:
            avisar(f"Revisão técnica aprovou sem vetos no ciclo {ciclo}.")
            break
        if ciclo >= config.max_ciclos:
            avisar(f"Ciclos esgotados; {len(motivos)} enquadramento(s) vetado(s) e removido(s).")
            break

        avisar(f"{len(motivos)} veto(s). Devolvendo para novo ciclo de enquadramento…")
        correcoes = "\n".join(f"- {m}" for m in motivos)

    return laudo
