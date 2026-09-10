"""Testes das garantias que o produto promete.

O foco não é cobertura de linha: é travar os comportamentos cuja quebra faria o
app voltar a emitir laudo errado — citação inexistente, item fora de vigência,
cobrança de EPI sem gente na foto, enquadramento fora de tema.
"""

from __future__ import annotations

import json
import re
import sys
from datetime import date
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from auditoria import dossie, kb_build, relatorio
from auditoria.catalogo_nr import CATALOGO_NR, NRS_REVOGADAS, NRS_VIGENTES
from auditoria.demo import ClienteDemonstracao, _texto_do_prompt
from auditoria.kb import carregar_base, extrair_citacoes, tokenizar
from auditoria.pipeline import (
    Achado, Configuracao, Visao, aferir, executar, montar_dossie, rotear_riscos,
)
from auditoria.riscos import (
    GRAVIDADES,
    catalogo as catalogo_riscos,
    riscos_marcaveis,
)

HOJE = date(2026, 8, 23)


@pytest.fixture(scope="module")
def base():
    return carregar_base()


# ---------------------------------------------------------------------------
# Catálogo das 38 NRs
# ---------------------------------------------------------------------------

def test_catalogo_cobre_nr01_a_nr38():
    assert len(CATALOGO_NR) == 38
    assert {f"NR-{n:02d}" for n in range(1, 39)} == set(CATALOGO_NR)


def test_revogadas_marcadas_e_fora_das_vigentes():
    assert NRS_REVOGADAS == {"NR-02", "NR-27"}
    assert not (NRS_REVOGADAS & NRS_VIGENTES)
    for nr in NRS_REVOGADAS:
        assert CATALOGO_NR[nr]["revogada_por"], f"{nr} sem portaria de revogação"


# ---------------------------------------------------------------------------
# Base normativa
# ---------------------------------------------------------------------------

def test_base_traz_itens_conhecidos_com_texto_correto(base):
    abertura = base.obter("NR-18", "18.9.2")
    assert abertura is not None
    assert "aberturas no piso" in abertura.texto.lower()
    assert "travado ou fixado" in abertura.texto.lower()

    altura = base.obter("NR-35", "35.2.1")
    assert altura is not None and "2,0m" in altura.texto.replace(" ", "")


def test_item_inexistente_devolve_none(base):
    assert base.obter("NR-18", "18.99.99") is None
    assert base.obter("NR-99", "1.1") is None


def test_todo_item_da_base_tem_texto_e_nr_coerente(base):
    for item in base.itens.values():
        assert item.texto.strip(), item.id
        assert item.nr in CATALOGO_NR, item.id
        raiz = item.item.split()[-1].split(".")[0]
        if not item.anexo:
            assert raiz == str(int(item.nr.split("-")[1])), item.id


def test_vigencia_diferida_e_respeitada(base):
    """18.9.1.1 entrou em vigor em 29/06/2026 — antes disso não pode ser citado."""
    item = base.obter("NR-18", "18.9.1.1")
    assert item is not None and item.vigencia_inicio == "2026-06-29"
    assert not item.vigente_em(date(2026, 6, 1))
    assert item.vigente_em(date(2026, 7, 1))


def test_busca_encontra_item_certo_para_abertura_no_piso(base):
    achados = base.buscar(
        "abertura no piso com fechamento provisorio travado", nrs=["NR-18"], k=3
    )
    assert "NR-18 18.9.2" in [i.id for i in achados]


def test_tokenizar_gera_bigramas():
    assert "abertura_piso" in tokenizar("abertura no piso")


# ---------------------------------------------------------------------------
# Extração de citações
# ---------------------------------------------------------------------------

def test_extrai_citacao_com_hifen_tipografico():
    # O relatório antigo usava NR‑18 com hífen não separável (U+2011).
    citacoes = {c.id for c in extrair_citacoes("Conforme **NR‑18** – 18.12.5 do canteiro")}
    assert "NR-18 18.12.5" in citacoes


def test_nao_confunde_medida_com_item():
    citacoes = {c.id for c in extrair_citacoes("guarda-corpo de 1.20 m e rodapé de 0.15 m")}
    assert citacoes == set()


def test_extrai_citacao_de_anexo():
    citacoes = {c.id for c in extrair_citacoes("ver NR-35, Anexo II, item 3.2 sobre ancoragem")}
    assert "NR-35 Anexo II 3.2" in citacoes


# ---------------------------------------------------------------------------
# Taxonomia de riscos
# ---------------------------------------------------------------------------

def test_todo_item_da_taxonomia_existe_e_e_normativo(base):
    for risco in catalogo_riscos().values():
        for ref in risco.itens:
            nr, _, item = ref.partition(" ")
            alvo = base.obter(nr, item)
            assert alvo is not None, f"{risco.id} cita item inexistente: {ref}"
            assert alvo.tipo == "item", f"{risco.id} cita {ref}, que é {alvo.tipo}"


def test_roteamento_acha_o_risco_certo_para_abertura_no_piso():
    visao = Visao(
        ambiente="canteiro de obra",
        achados=[Achado("placa de madeira apoiada solta sobre abertura no piso, sem travamento")],
    )
    ids = [r.id for r in rotear_riscos(visao)]
    assert "abertura_piso_desprotegida" in ids


def test_roteamento_tolera_variacao_de_plural_e_pontuacao():
    visao = Visao(achados=[Achado("Entulho, cacos e sobras de materiais espalhados pelo piso")])
    assert "entulho_sobras_acumulados" in [r.id for r in rotear_riscos(visao)]


def test_roteamento_nao_combina_palavras_de_achados_diferentes():
    """Bug visto em foto real: nenhuma escada na cena, mas "apoiada"/"solta" (do
    achado da placa sobre a abertura) somadas a "parede" (de um achado sobre
    madeira empilhada, sem relação) bastavam para acionar um risco de escada.
    """
    visao = Visao(achados=[
        Achado("Abertura quadrada no piso, coberta por uma placa apoiada solta "
               "sobre o vão, sem fixação nem travamento visível"),
        Achado("Monte de sobras de madeira e um tubo de PVC empilhados próximos à parede"),
    ])
    ids = [r.id for r in rotear_riscos(visao)]
    assert "abertura_piso_desprotegida" in ids
    assert not any("escada" in i for i in ids)


def test_roteamento_nao_deixa_o_ambiente_carregar_o_sinal_sozinho():
    """Bug medido no lote de 01/09: o ambiente completa, mas não pode carregar.

    A foto (61) mostra uma máquina — nenhuma abertura de piso em lugar nenhum.
    O achado deu "abertura" (do tambor) e o ambiente deu "piso" (de concreto,
    do galpão), e o sinal "abertura no piso" casou inteiro com um radical de
    cada lado. Como quase todo ambiente de obra menciona "piso", o falso
    positivo era sistemático, não acidental.

    O par abaixo é o que importa: nenhum dos dois textos dispara o sinal
    sozinho, e a soma também não deve.
    """
    maquina = Visao(
        ambiente="Interior de um galpão ou oficina com piso de concreto e "
                 "estruturas metálicas ao fundo.",
        achados=[Achado("Abertura circular na extremidade do tambor, com borda "
                        "metálica visível e interior escuro.")],
    )
    assert not any(
        r.id == "abertura_piso_desprotegida" for r in rotear_riscos(maquina)
    )

    # A contraparte que DEVE continuar disparando: os dois radicais no achado.
    piso = Visao(
        ambiente="Interior de um galpão ou oficina com piso de concreto.",
        achados=[Achado("Abertura retangular no piso, sem tampa nem guarda-corpo.")],
    )
    assert any(r.id == "abertura_piso_desprotegida" for r in rotear_riscos(piso))


def test_uma_abertura_gera_uma_nc_com_a_outra_norma_de_complemento(base):
    """NR-18 18.9.2 e NR-08 8.3.2.2 dizem a mesma coisa sobre a mesma abertura.
    No lote de 01/09, 6 das 21 não conformidades eram 3 aberturas contadas duas
    vezes — 29% da contagem. Um auditor escreve uma e menciona a outra.
    """
    from auditoria.pipeline import NaoConformidade, _fundir_equivalentes

    def nc(nr, item):
        return NaoConformidade(base.obter(nr, item), "Abertura no piso sem proteção.",
                               "Queda.", "critica", "Fechar.", 1, "")

    fundidas = _fundir_equivalentes([nc("NR-08", "8.3.2.2"), nc("NR-18", "18.9.2")])
    assert len(fundidas) == 1, "a abertura continuou contando duas vezes"
    assert fundidas[0].item.item == "18.9.2", "a norma específica deve encabeçar"
    assert [c.item for c in fundidas[0].complementos] == ["8.3.2.2"]

    # A precedência não depende da ordem em que o Analista enquadrou.
    invertido = _fundir_equivalentes([nc("NR-18", "18.9.2"), nc("NR-08", "8.3.2.2")])
    assert invertido[0].item.item == "18.9.2"
    assert [c.item for c in invertido[0].complementos] == ["8.3.2.2"]


def test_nr08_sozinha_nao_ganha_nr18_de_complemento(base):
    """Abertura de piso fora de obra — escritório, galpão — é da NR-08. A fusão
    não pode injetar a NR-18, que é norma da indústria da construção.
    """
    from auditoria.pipeline import NaoConformidade, _fundir_equivalentes

    so_nr08 = [NaoConformidade(base.obter("NR-08", "8.3.2.2"), "Abertura no piso elevado.",
                               "Queda.", "alta", "Fechar.", 1, "")]
    fundidas = _fundir_equivalentes(so_nr08)
    assert len(fundidas) == 1
    assert fundidas[0].item.nr == "NR-08"
    assert fundidas[0].complementos == []


def test_norma_complementar_e_citada_e_declara_a_edicao(base):
    """O texto da norma complementar sai da base, verbatim, e sua edição entra
    na trilha: citar sem declarar de que edição saiu desfaria a rastreabilidade.
    """
    from auditoria.pipeline import Laudo, NaoConformidade, _fundir_equivalentes

    def nc(nr, item):
        return NaoConformidade(base.obter(nr, item), "Abertura no piso sem proteção.",
                               "Queda.", "critica", "Fechar.", 1, "")

    laudo = Laudo(visao=Visao(ambiente="obra"), data_referencia=HOJE)
    laudo.nao_conformidades = _fundir_equivalentes(
        [nc("NR-08", "8.3.2.2"), nc("NR-18", "18.9.2")]
    )
    md = relatorio.markdown(laudo, base, numero=1)
    assert "**Também alcançado por.** NR-08" in md
    assert "As aberturas nos pisos e nas paredes" in md, "texto verbatim ausente"
    assert "NR-08: edição" in md, "a edição da norma complementar não foi declarada"


def test_abertura_em_parede_nao_vira_abertura_de_piso():
    """A NR-08 8.3.2.2 cobre "aberturas nos pisos E NAS PAREDES"; a NR-18 18.9.2,
    só piso. Num laudo real a abertura vertical foi enquadrada nas duas, o
    Diretor vetou a de piso — certo — e a NC sobrou intitulada "Abertura no
    piso", porque o rótulo vinha do único risco que reivindicava o item.
    """
    parede = Visao(
        ambiente="Interior de estrutura em construção, com paredes de alvenaria "
                 "de tijolo aparente e piso de madeira.",
        achados=[Achado("Abertura vertical sem fechamento visível, delimitada por "
                        "uma borda de tijolo à esquerda e uma parede lisa à direita.")],
    )
    ids = [r.id for r in rotear_riscos(parede)]
    assert "abertura_parede_desprotegida" in ids
    assert "abertura_piso_desprotegida" not in ids

    # E a recíproca: abertura de piso não passa a acionar o risco de parede.
    piso = Visao(
        ambiente="Laje de construção civil em fase de estruturação.",
        achados=[Achado("Abertura retangular no piso da laje, com bordas de "
                        "concreto aparente, sem cobertura ou fechamento visível.")],
    )
    ids_piso = [r.id for r in rotear_riscos(piso)]
    assert "abertura_piso_desprotegida" in ids_piso
    assert "abertura_parede_desprotegida" not in ids_piso


def test_sinal_de_parede_nao_casa_com_vao_estrutural():
    """"vão" e "parede" no mesmo achado descrevem estrutura o tempo todo — é a
    armadilha do vocabulário de engenharia, e foi por isso que "vao na parede"
    não entrou na lista de sinais.
    """
    visao = Visao(
        ambiente="Interior de obra com paredes de alvenaria.",
        achados=[Achado("Vigas de concreto apoiadas no vão entre as paredes, "
                        "com armadura exposta na extremidade.")],
    )
    assert not any(
        r.id == "abertura_parede_desprotegida" for r in rotear_riscos(visao)
    )


def test_rotulo_de_abertura_cai_por_ser_item_compartilhado():
    """8.3.2.2 passou a ter dois donos (piso e parede), então o rótulo do risco
    deixa de nomear a NC — quem nomeia é a constatação do Analista.
    """
    from auditoria.riscos import itens_compartilhados

    assert "NR-08 8.3.2.2" in itens_compartilhados()


def test_betoneira_com_transmissao_exposta_aciona_a_nr12(base):
    """Medido na foto (61) do acervo — uma betoneira inequívoca, tambor amarelo
    descascado sobre chassi. O laudo real saiu com ZERO não conformidades, e a
    causa era dupla: o Olho não nomeou a máquina (portão fechado) e, mesmo
    nomeando e descrevendo o defeito clássico, nenhum sinal casava.

    "correia sem protecao" contra "correia … sem carenagem" cobre 2 de 3
    radicais, e 0,67 não passa do corte de 0,7 — o vocabulário curado era de
    máquina industrial, e um laudo de canteiro escreve outra coisa.
    """
    visao = Visao(
        ambiente="Área de preparo de concreto em canteiro, com betoneira sob cobertura.",
        achados=[
            Achado("Betoneira com coroa e pinhão expostos, sem proteção sobre a "
                   "engrenagem de acionamento do tambor."),
            Achado("Correia de transmissão da betoneira aparente, sem carenagem."),
        ],
    )
    ids = [r.id for r in rotear_riscos(visao)]
    assert "maquina_sem_protecao_zona_perigo" in ids

    dossie = _dossie_da_cena(
        base, visao.ambiente, [a.fato for a in visao.achados]
    )
    citados = {f"{e.item.nr} {e.item.item}" for e in dossie.entradas}
    assert "NR-12 12.5.1" in citados, "a NR-12 não chegou ao dossiê"


def test_tambor_sem_tampa_nao_vira_vao_no_piso():
    """Medido no laudo real da foto (61), depois que o Olho passou a nomear a
    betoneira: o sinal "vao no piso sem tampa" tinha QUATRO radicais e casava
    três — "sem" e "tampa" vinham de "Abertura circular do tambor da betoneira
    SEM TAMPA ou proteção visível", e "piso" vinha do ambiente. Faltava só
    "vao", o único discriminante, e 0,75 passa do corte de 0,7.

    A âncora no achado não bastou porque um dos dois radicais ancorados era
    "sem", que não discrimina nada. A correção foi encurtar o sinal, não mexer
    no limiar: onde nenhum radical pode faltar, não há o que explorar.
    """
    betoneira = Visao(
        ambiente="Interior de um galpão ou oficina com piso de concreto e "
                 "estruturas metálicas ao fundo.",
        achados=[
            Achado("Betoneira com tambor cilíndrico metálico de cor escura, com "
                   "extensas áreas de corrosão."),
            Achado("Abertura circular do tambor da betoneira sem tampa ou proteção "
                   "visível, revelando o interior escuro e a haste central."),
            Achado("Piso de concreto com manchas escuras e resíduos espalhados ao "
                   "redor da base da máquina."),
        ],
    )
    ids = [r.id for r in rotear_riscos(betoneira)]
    assert "abertura_piso_desprotegida" not in ids

    # A contraparte: um vão de verdade no piso continua acionando.
    vao = Visao(
        ambiente="Laje em construção.",
        achados=[Achado("Vão no piso sem tampa, junto à área de circulação.")],
    )
    assert "abertura_piso_desprotegida" in [r.id for r in rotear_riscos(vao)]


def test_maquina_protegida_nao_aciona_o_risco_de_zona_de_perigo():
    """A contraparte de cada sinal novo. A terceira é a que pegou "sem
    carenagem" sozinho: "sem" conta como radical e não discrimina nada, então o
    sinal casava com uma carenagem ÍNTEGRA — o oposto do risco.
    """
    protegidas = [
        "Betoneira com proteção metálica instalada sobre a coroa e o pinhão.",
        "Correia de transmissão protegida por carenagem metálica fixada com parafusos.",
        "Carenagem do motor íntegra e fixada, sem folgas visíveis.",
        "Linha de transmissão aérea exposta sobre o canteiro.",
    ]
    for fato in protegidas:
        visao = Visao(ambiente="Canteiro de obra com betoneira.", achados=[Achado(fato)])
        ids = [r.id for r in rotear_riscos(visao)]
        assert "maquina_sem_protecao_zona_perigo" not in ids, fato


def test_prompt_do_olho_pede_o_nome_da_maquina():
    """A regra que proíbe "afirmar finalidade que não se verifica" existe por
    bom motivo — foi ela que tirou "rede de proteção" de uma tela de plástico.
    Mas ela também fazia o Olho descrever uma betoneira como "tambor cilíndrico
    metálico", e sem o nome o portão da NR-12 nunca abre. O prompt precisa
    separar nomear (descrição) de atribuir função de segurança (conclusão).
    """
    from auditoria.pipeline import PROMPT_OLHO

    assert "betoneira" in PROMPT_OLHO.lower()
    assert "rede de proteção" in PROMPT_OLHO, "a contraparte precisa continuar no prompt"


def test_prompt_do_olho_pede_tambem_o_nome_do_elemento_de_canteiro():
    """A regra de nomear valia só para máquina, e a cancela não é máquina.

    No lote de içamento o Olho descreveu a cancela de uma torre de elevador como
    "Grade metálica … pintada de vermelho, aberta" — e estava OBEDECENDO: o
    parágrafo da barreira lista "grade" e manda qualificar material, rigidez e
    fixação, enquanto o parágrafo de nomear falava de "equipamento" e não
    mencionava cancela. Duas regras competindo, e o Olho seguiu a mais
    específica. A grua saiu igual: "Estrutura metálica elevada de cor amarela,
    com cabine e contrapesos".

    O conserto é dizer que as duas se SOMAM — nome mais atributos — e estender a
    lista ao vocabulário de canteiro de que o roteamento depende.
    """
    from auditoria.pipeline import PROMPT_OLHO

    for nome in ("cancela", "grua", "torre de elevador", "tapume", "bandeja"):
        assert nome in PROMPT_OLHO.lower(), nome
    assert "NÃO dispensa os atributos" in PROMPT_OLHO
    # A cláusula de escape continua existindo, mas com o critério apertado.
    assert "ambígua de verdade" in PROMPT_OLHO
    assert "tambor cilíndrico" in PROMPT_OLHO


def test_o_nome_do_elemento_de_canteiro_e_o_que_faz_a_cancela_rotear():
    """Por que mexer no prompt do Olho vale a mudança: medido sem rede.

    O risco `torre_elevador_sem_cancela` e o item `NR-18 18.11.13` ("Em todos os
    acessos de entrada à torre do elevador deve ser instalada barreira
    (cancela)…") já existiam quando o lote de içamento rodou. Faltava só o nome:
    os sete sinais do risco dependem de `elevador`, `cancela` ou `tapume`, e
    nenhuma das duas fotos de cancela produziu qualquer um deles.

    Este teste trava o ganho nos dois sentidos — o fato como o Olho escreveu
    não routeia; o mesmo fato com o nome routeia o risco certo.
    """
    ambiente = ("Canteiro de obras em edificação de múltiplos pavimentos, "
                "laje de concreto")
    sem_nome = Visao(ambiente=ambiente, achados=[
        Achado("Grade metálica vermelha, aberta, apoiada no piso, sem fechamento lateral"),
        Achado("Estrutura metálica de grande porte, com configuração de torre, junto à fachada"),
    ])
    com_nome = Visao(ambiente=ambiente, achados=[
        Achado("Cancela metálica vermelha na entrada da torre do elevador de obra, "
               "aberta, presa por uma dobradiça"),
        Achado("Torre de elevador de obra de cremalheira junto à fachada, com "
               "estrutura metálica treliçada"),
    ])

    assert "torre_elevador_sem_cancela" not in [r.id for r in rotear_riscos(sem_nome)]
    assert "torre_elevador_sem_cancela" in [r.id for r in rotear_riscos(com_nome)]


def test_protecao_instalada_nao_aciona_o_risco_de_protecao_ausente():
    """A contraparte que o prompt novo tornou obrigatória, e o falso positivo
    que ela achou.

    Ensinar o Olho a nomear o elemento de canteiro faz os fatos passarem a
    conter `cancela`, `elevador`, `torre` e `tapume` — que é o que estes dois
    riscos casam. Antes disso o defeito era latente; depois, seria o caso comum,
    e o próximo lote é justamente o de poço de elevador.

    Medido antes da correção: 5 de 5 fatos com a proteção INSTALADA acionavam o
    risco de proteção ausente, e 3 de 6 no risco do vão da caixa. Sempre a 0,75,
    sempre por sinal de quatro radicais em que o que faltava era só o negador —
    "caixa do elevador COM fechamento de madeira" cobrindo "caixa do elevador
    sem fechamento". É a armadilha dos quatro radicais somada à do `sem`.

    Uma contraparte só vale se ela PUDER falhar: os fatos abaixo trazem as
    palavras dos sinais de propósito. Uma lista de fatos sem `elevador` nem
    `cancela` passaria com qualquer taxonomia, inclusive a defeituosa.
    """
    ambiente = "Canteiro de obras em edificação de múltiplos pavimentos"
    instaladas = (
        "Cancela metálica fechada e travada na entrada da torre do elevador de obra",
        "Base da torre do elevador fechada com tapume de madeira compensada, íntegro",
        "Acesso ao elevador fechado com porta metálica de correr, com trava",
        "Torre do elevador de obra com cancela instalada em todos os acessos, fechada",
        "Vão da torre do elevador fechado por chapa metálica aparafusada",
        "Caixa do elevador com fechamento de madeira compensada em toda a abertura, travado",
        "Poço de elevador fechado por tapume de madeira em toda a altura, íntegro",
        "Buraco do elevador fechado com tapume aparafusado à estrutura",
        "Porta do elevador instalada e travada no pavimento",
        # `corrente` de elo e `corrente` elétrica têm o mesmo radical: foi por
        # aqui que a primeira tentativa de encurtar o sinal vazou.
        "Quadro elétrico com corrente de alimentação exposta junto ao acesso da obra",
        # E estes cinco são a SEGUNDA tentativa vazando: encurtar para "sem
        # cancela" mantinha o `sem` como radical obrigatório, e `sem` não nega
        # nada. Pior, o PROMPT_OLHO manda escrever "sem <peça> visível" quando o
        # lugar dela aparece vazio — este é o formato de fato mais provável que
        # o Olho produz, e ele casava com a cancela INSTALADA.
        "Cancela metálica vermelha, fechada e travada, sem sinalização de advertência visível",
        "Cancela instalada e fechada, sem placa de aviso no acesso",
        "Caixa do elevador com fechamento de madeira travado, sem sinalização",
        "Poço de elevador fechado com tapume, sem placa de identificação",
        "Torre do elevador com cancela fechada, sem trava de intertravamento visível",
        # No canteiro há OUTRA torre: a da grua. "base da torre aberta" e "vao
        # da torre aberto" não pediam `elevador`, e a foto `19 PAV. POÇO GRUA
        # SEM PROTEÇÃO` do lote de içamento sairia enquadrada em cancela de
        # elevador — item verdadeiro, equipamento errado.
        "Base da torre da grua aberta, delimitada apenas por cones",
        "Poço da grua aberto no piso, junto à base da torre",
        "Torre da grua aberta na base, com a fundação exposta",
        "Base da torre da grua com o poço aberto, sem fechamento lateral",
        # Proteção rígida instalada COM fita ou corrente ao lado — cena comum de
        # canteiro, e o que derrubou os sinais de proteção inadequada: o `com`
        # deles é cola, e sobravam dois discriminantes.
        "Vão do elevador fechado com chapa metálica aparafusada e fita zebrada de sinalização",
        "Caixa do elevador fechada com tapume de madeira e fita zebrada colada na borda",
        "Acesso à torre do elevador com porta metálica travada e corrente de segurança adicional",
    )
    for fato in instaladas:
        ids = [r.id for r in rotear_riscos(
            Visao(ambiente=ambiente, achados=[Achado(fato)]))]
        assert "torre_elevador_sem_cancela" not in ids, fato
        assert "vao_caixa_elevador_sem_fechamento" not in ids, fato


def test_protecao_ausente_continua_acionando_o_risco_certo():
    """O outro lado do encurtamento: cada caso tem de cair no risco certo dos
    dois — a cancela e a base da torre são o `NR-18 18.11.13`/`18.11.14`; o vão
    da caixa é o `18.9.3`.

    Duas perdas aceitas e deliberadas. A segunda é a proteção INADEQUADA — "vão
    fechado só com fita", "acesso só com corrente": esses sinais precisam do
    conceito de substituição, o que sobra dele em radicais é a cola `com`, e o
    preço eram os três últimos negativos da lista acima. A foto que os motivava
    dispara os sinais de abertura, porque um vão isolado só por fita é um vão
    aberto e o Olho o descreve assim.

    A primeira: "entrada da torre SEM CANCELA instalada" não
    casa mais pela letra, porque nenhum sinal depende de `sem`. Não há como
    manter esse caso sem trazer de volta "cancela fechada, SEM sinalização", que
    é o mesmo par de radicais. A perda é pequena — sem cancela, o acesso está
    aberto, e "torre do elevador aberta" o pega —, e a troca é a certa: falso
    negativo custa cobertura, falso positivo é a classe de erro 1 e vai ao
    cliente com um item verdadeiro descrevendo a situação oposta.
    """
    ambiente = "Canteiro de obras em edificação de múltiplos pavimentos"
    casos = [
        ("torre_elevador_sem_cancela",
         "Cancela metálica vermelha na entrada da torre do elevador de obra, "
         "aberta, presa por uma dobradiça"),
        ("torre_elevador_sem_cancela",
         "Cancela ausente na entrada da torre do elevador de obra"),
        ("torre_elevador_sem_cancela",
         "Cancela faltando no acesso ao elevador de obra"),
        ("torre_elevador_sem_cancela",
         "Cancela quebrada, pendurada por uma dobradiça, na entrada da torre"),
        ("torre_elevador_sem_cancela",
         "Torre do elevador de obra aberta no décimo segundo pavimento"),
        ("torre_elevador_sem_cancela",
         "Base da torre do elevador aberta, sem qualquer fechamento lateral"),
        ("torre_elevador_sem_cancela",
         "Vão da torre do elevador aberto no décimo segundo pavimento"),
        ("vao_caixa_elevador_sem_fechamento",
         "Poço de elevador aberto no quinto pavimento, sem qualquer barreira"),
        ("vao_caixa_elevador_sem_fechamento",
         "Caixa do elevador aberta, vão livre para o poço"),
        ("vao_caixa_elevador_sem_fechamento",
         "Vão do elevador aberto na altura do peito"),
        ("vao_caixa_elevador_sem_fechamento",
         "Tapume do elevador faltando no pavimento"),
        ("vao_caixa_elevador_sem_fechamento",
         "Porta do elevador faltando no pavimento, vão aberto"),
        ("vao_caixa_elevador_sem_fechamento",
         "Shaft do elevador aberto, sem tampa"),
        # A prova da segunda perda aceita: a foto que motivava "vao do elevador
        # so com fita" continua routeando, pelo sinal de abertura.
        ("vao_caixa_elevador_sem_fechamento",
         "Vão do elevador aberto, delimitado apenas por fita zebrada"),
    ]
    for esperado, fato in casos:
        ids = [r.id for r in rotear_riscos(
            Visao(ambiente=ambiente, achados=[Achado(fato)]))]
        assert esperado in ids, fato


def test_prompt_do_olho_separa_a_grua_do_elevador_pelo_que_esta_no_recorte():
    """O risco simétrico do #27 aconteceu na primeira medição.

    Ensinar o Olho a nomear o elemento de canteiro pôs "torre de elevador de
    obra" na lista de nomes a escrever, e ele passou a aplicá-la a toda torre
    amarela: no lote de 05/09 saíram 2 das 3 fotos da GRUA como "Torre de
    elevador de obra", e a terceira como "grua" — o mesmo equipamento, e o
    engenheiro confirmou que é grua.

    O conserto não é ensiná-lo a distinguir melhor: é a regra da MOLDURA
    aplicada ao nome. Numa foto da base, nem a lança nem a cremalheira aparecem,
    e escolher entre os dois é adivinhar. O nome só se escreve quando o que
    distingue está dentro do recorte; fora dele, "torre metálica treliçada",
    que é verdadeiro nos dois casos.
    """
    from auditoria.pipeline import PROMPT_OLHO

    # Os dois discriminantes, um de cada equipamento.
    for marca in ("lança horizontal", "contrapesos", "cremalheira"):
        assert marca in PROMPT_OLHO, marca
    # O nome de recuo, que não escolhe entre os dois.
    assert "torre metálica treliçada" in PROMPT_OLHO
    # E a razão, que é o que impede o modelo de tratar isto como preferência de
    # estilo: nome errado não é nome pobre, é fato falso.
    assert "nome errado é fato falso" in PROMPT_OLHO
    # A regra vale para a torre de canteiro; o poço dentro da edificação é outro
    # elemento e continua a ser nomeado. Sem esta ressalva, a mesma frase
    # calaria `vao_caixa_elevador_sem_fechamento`, que é o risco que o lote de
    # poço de elevador existe para validar.
    assert "shaft" in PROMPT_OLHO
    assert "não para o poço" in PROMPT_OLHO

    # E `cabine` não pode ficar nas DUAS colunas. O parágrafo anterior — que é
    # anterior a esta mudança — usa "com cabine e contrapesos" como exemplo de
    # GRUA, e essa é justamente a frase que o modelo escreveu para a grua em
    # produção. Listar a cabine como marca do elevador sem resolver o conflito
    # seria duas regras competindo no mesmo prompt, que é exatamente como o
    # defeito do #27 nasceu. O que decide é ONDE ela fica.
    assert "A cabine sozinha não decide nada" in PROMPT_OLHO
    assert "com cabine e contrapesos" in PROMPT_OLHO


def test_nome_errado_da_torre_leva_item_de_elevador_para_foto_de_grua(base):
    """O que o nome errado custou, medido — e por qual caminho.

    O laudo 7 do lote de 05/09 saiu com `NR-18 18.11.14` (fechamento da base da
    torre do ELEVADOR) numa foto de grua: item verdadeiro, situação errada, a
    classe de erro 1. E o risco curado `torre_elevador_sem_cancela` teve ZERO
    disparos nas 9 fotos — ou seja, o item não chegou lá pela taxonomia.

    Chegou pela BUSCA TEXTUAL: a palavra "torre de elevador" no fato basta para
    a seção 18.11 da NR-18 (elevadores de obra) ocupar o dossiê inteiro, com ou
    sem risco roteado. Por isso este teste mede o dossiê, não o roteamento — o
    roteamento sozinho não veria o defeito que produziu o laudo errado.
    """
    ambiente = ("Canteiro de obra de edificação em construção, com estrutura "
                "de concreto aparente")

    def refs(fatos):
        d = _dossie_da_cena(base, ambiente, fatos)
        return [f"{e.item.nr} {e.item.item}" for e in d.entradas]

    # Hoje: o nome errado leva os itens de elevador de obra para a foto de grua.
    errado = refs(["Torre de elevador de obra em estrutura metálica treliçada "
                   "amarela, com a base aberta, sem fechamento no perímetro"])
    assert "NR-18 18.11.14" in errado

    # Pelo caminho textual, sem risco nenhum roteado, o efeito é o mesmo: cinco
    # vagas do dossiê vão para a seção 18.11 por causa de uma palavra.
    so_texto = ["Estrutura vertical treliçada amarela identificada como torre "
                "de elevador de obra, montada junto à fachada"]
    assert not rotear_riscos(Visao(ambiente=ambiente,
                                   achados=[Achado(so_texto[0])]))
    assert [r for r in refs(so_texto) if r.startswith("NR-18 18.11")]

    # Depois: recusado o nome, nem o risco nem a busca textual alcançam o 18.11.
    for fato in (
        "Torre metálica treliçada amarela de canteiro, com a base aberta, "
        "sem fechamento no perímetro",
        "Estrutura vertical treliçada amarela de canteiro, montada junto à fachada",
    ):
        assert not [r for r in refs([fato]) if r.startswith("NR-18 18.11")], fato


def test_o_elevador_de_verdade_continua_chegando_ao_item_certo(base):
    """O outro lado: a regra da moldura não pode custar o caso verdadeiro.

    Quando o discriminante está no recorte — a cabine que sobe pela própria
    torre, a cremalheira, a cancela do pavimento — o nome se escreve, e o
    `18.11.13`/`18.11.14` continua chegando. Sem este teste, calar a torre
    ambígua e calar o elevador de verdade seriam indistinguíveis.
    """
    ambiente = ("Canteiro de obra de edificação em construção, com estrutura "
                "de concreto aparente")
    cenas = [
        ["Torre de elevador de obra com cabine que corre pela própria torre e "
         "cremalheira dentada na face",
         "Cancela metálica vermelha na entrada do pavimento, aberta, presa por "
         "uma dobradiça"],
        ["Torre de elevador de obra com cabine que sobe pela própria torre, "
         "base aberta sem tapume no perímetro"],
    ]
    for fatos in cenas:
        refs = [f"{e.item.nr} {e.item.item}"
                for e in _dossie_da_cena(base, ambiente, fatos).entradas]
        assert "NR-18 18.11.14" in refs, fatos


def test_o_vocabulario_novo_do_olho_nao_aciona_risco_nenhum():
    """A contraparte que a armadilha registrada torna obrigatória: ao pôr
    vocabulário novo no prompt de um agente, rodar os sinais que casam esse
    vocabulário contra fatos em que a condição NÃO existe.

    As palavras novas são `lança`, `contrapesos`, `cremalheira` e `treliçada`.
    UMA delas tem vizinho de radical na taxonomia: `contrapes`, que vive em
    "andaime suspenso com contrapeso de tijolo". `lanc` é o caso que parecia
    perigoso e não é — `radical("lança")` e `radical("lance")` são ambos `lanc`,
    e "lance de escada" é vocabulário corrente de obra, mas nenhum sinal da
    taxonomia usa o radical.

    Os fatos abaixo trazem também `torre`, que NÃO é palavra nova (o #27 já a
    pusera no prompt) e tem vizinho em "torre de andaime bamba": é o par mais
    provável de vazar, porque os fatos de torre o carregam sempre.
    """
    ambiente = ("Canteiro de obra de edificação em construção, com estrutura "
                "de concreto aparente")
    neutros = (
        "Grua com torre metálica treliçada amarela, lança horizontal no topo e "
        "contrapesos na contralança",
        "Grua com lança horizontal e contrapesos de concreto empilhados na "
        "contralança, sem andaime na cena",
        "Torre metálica treliçada amarela de canteiro, apoiada em base de "
        "concreto, sem oscilação visível",
        "Torre de elevador de obra com cabine que corre pela própria torre e "
        "cremalheira dentada na face, íntegra",
    )
    for fato in neutros:
        ids = [r.id for r in rotear_riscos(
            Visao(ambiente=ambiente, achados=[Achado(fato)]))]
        assert "andaime_suspenso_irregular" not in ids, fato
        assert "andaime_base_instavel" not in ids, fato
        assert "plataforma_cavalete_irregular" not in ids, fato


def test_prompt_do_diretor_veta_a_constatacao_hipotetica():
    """Duas das seis NCs do lote de 05/09 não afirmavam um fato: afirmavam uma
    possibilidade sobre uma proteção que EXISTE.

    "a malha PODE NÃO impedir a queda de objetos pequenos", sobre a grade que
    fecha o vão, e "manchas de oxidação INDICANDO POSSÍVEL comprometimento da
    integridade estrutural". O Diretor aprovou as duas, e não errou a
    conferência: o fato-âncora existe mesmo — a grade existe, a ferrugem existe.
    O que passa é o SALTO do fato para a hipótese, e nada no pipeline olhava
    para ele. A regra da moldura cobre afirmar que algo NÃO existe; não cobria
    afirmar que algo que existe PODE falhar.

    A cláusula tem de trazer junto a sua própria fronteira: a CONSEQUÊNCIA é
    legítima e tem campo próprio. "Abertura no piso, que pode causar queda" tem
    por núcleo a abertura, que é estado — vetá-la seria trocar um falso positivo
    por um falso negativo em todo laudo do app.
    """
    from auditoria.pipeline import PROMPT_DIRETOR

    assert "POSSIBILIDADE" in PROMPT_DIRETOR
    # O teste mecânico que o Diretor aplica: risque a hipótese e leia o resto.
    for palavra in ("pode", "possível", "indicando"):
        assert palavra in PROMPT_DIRETOR, palavra
    assert "proteção instalada em" in PROMPT_DIRETOR
    # A fronteira, sem a qual a cláusula viraria um veto geral.
    assert "NÃO alcança a consequência" in PROMPT_DIRETOR
    assert "pode causar queda" in PROMPT_DIRETOR
    # A segunda fronteira, e a mais cara. O passo decisivo da cláusula — "o que
    # sobra é proteção em estado normal?" — é o único julgamento dentro de uma
    # regra que se anuncia mecânica, e o caso que ele erraria já custou caro a
    # este projeto: a tela plástica frouxa na borda da laje é o falso negativo
    # mais caro do lote de 29/08. Sem esta linha, "a tela pode não resistir"
    # viraria veto, e o achado evaporaria — a classe de erro 5 pela porta que a
    # própria correção abriria.
    assert "tela plástica frouxa na borda da laje" in PROMPT_DIRETOR
    assert "do tipo certo e no lugar certo" in PROMPT_DIRETOR
    # E ela é veto, não aparo: aparada, a constatação vira "a grade existe", que
    # não descumpre item nenhum — o que a Parte 1 já trata como veto.
    assert "PARTE 2 — VETE também quando:" in PROMPT_DIRETOR


def test_roteamento_deixa_o_ambiente_nomear_o_equipamento():
    """A isenção do sinal de um radical: são nomes inequívocos, e é do ambiente
    que se espera o nome do equipamento quando o achado fala só do defeito.
    """
    visao = Visao(
        ambiente="Casa de máquinas com uma caldeira a vapor",
        achados=[Achado("Manômetro com o visor trincado e leitura ilegível")],
    )
    assert any("caldeira" in r.id for r in rotear_riscos(visao))


def _dossie_da_cena(base, ambiente, fatos, quando=HOJE):
    visao = Visao(ambiente=ambiente, achados=[Achado(f) for f in fatos])
    return montar_dossie(base, visao, "", quando)[0]


def _nr12(dossie):
    return [e.item.item for e in dossie.entradas if e.item.nr == "NR-12"]


def test_item_de_equipamento_ausente_da_cena_nao_entra_no_dossie_da_nr18(base):
    """O falso positivo do lote de 08/09, e o que ele revelou.

    A foto `GRUA.jpg` — topo de uma grua, com contrapesos e um ar-condicionado —
    routeia risco NENHUM. Sem taxonomia curada o dossiê vira busca textual pura,
    e a NR-18 ofereceu `18.12.22` (contrapeso de ANDAIME SUSPENSO) e `18.10.1.5`
    (SERRA CIRCULAR). O Analista escolheu o primeiro, e saiu no laudo do cliente
    uma não conformidade de andaime sobre uma grua: item verdadeiro, equipamento
    errado — a classe de erro 1.

    Diagnóstico medido, e não o que se supunha: fazer um risco de guindar
    disparar NÃO expulsa o `18.12.22`, só o empurra para D3. O problema não é
    alcançabilidade da taxonomia, é a NR-18 oferecer item de equipamento que não
    está na cena — o mesmo que `setor_pertinente` já resolvia na NR-12, por um
    caminho que a NR-18 não usava.
    """
    cena_grua = (
        "Vista do topo de uma estrutura metálica elevada, possivelmente uma grua",
        [
            "Conjunto de contrapesos metálicos retangulares, de cor ferrugem, com a "
            "inscrição '1000' visível em alguns blocos, empilhados sobre a lança horizontal",
            "Treliça metálica de cor amarela formando a coluna vertical de sustentação",
        ],
    )
    refs = [f"{e.item.nr} {e.item.item}"
            for e in _dossie_da_cena(base, *cena_grua).entradas]
    assert "NR-18 18.12.22" not in refs, "contrapeso de andaime suspenso numa foto de grua"
    assert "NR-18 18.10.1.5" not in refs, "serra circular numa foto de grua"


def test_o_portao_da_nr18_nao_alcanca_o_item_generico(base):
    """O que o portão NÃO pode tirar, e é onde o app acerta.

    `18.9.2` (abertura no piso), `18.9.4.2` (guarda-corpo rígido) e `18.9.1`
    (proteção coletiva) não nomeiam equipamento nenhum no próprio texto, então
    `setor_do_item` devolve None para eles e eles passam livres. Sem esta
    garantia o portão derrubaria os 6 de 6 enquadramentos de abertura que o
    lote de 08/09 acertou.

    Medido: aplicado às 15 fotos daquele lote, nenhum enquadramento verdadeiro
    perdeu o seu item — o único que saiu foi o falso positivo acima.
    """
    from auditoria.dossie import setor_do_item

    for ref in ("18.9.2", "18.9.4.2", "18.9.1", "18.9.3", "18.16.4.1"):
        item = base.obter("NR-18", ref)
        assert setor_do_item(item) is None, (
            f"NR-18 {ref} é genérico e não pode ficar atrás de portão de equipamento"
        )

    # O `18.16.4.1` é o caso que mostrou por que o ramo da NR-18 é a SEÇÃO e não
    # o texto: ele diz "as madeiras retiradas de ANDAIMES, tapumes, fôrmas e
    # escoramentos devem ser empilhadas após retirados ou rebatidos os pregos",
    # mas é o item dos PREGOS EXPOSTOS e vale para madeira empilhada sem andaime
    # nenhum. Com `no_item=("andaime",)` ele ficava preso — o mesmo defeito do
    # `18.9.3`, na família que a primeira versão não testou.
    from auditoria.dossie import setor_pertinente

    pregos = base.obter("NR-18", "18.16.4.1")
    assert setor_pertinente(pregos, "madeira empilhada com pregos expostos no piso")


def test_o_portao_da_nr18_abre_quando_o_equipamento_esta_na_cena(base):
    """A contraparte que faz o portão valer: ele filtra por ausência, não por
    tema. Com o andaime na cena, o item de andaime volta a ser candidato — senão
    isto não seria um portão, seria um veto permanente à seção 18.12.
    """
    from auditoria.dossie import setor_pertinente

    andaime = base.obter("NR-18", "18.12.22")
    assert not setor_pertinente(andaime, "topo de uma grua com contrapesos")
    assert setor_pertinente(andaime, "andaime suspenso na fachada, com contrapesos")

    serra = base.obter("NR-18", "18.10.1.5")
    assert not setor_pertinente(serra, "poço de elevador sem proteção")
    assert setor_pertinente(serra, "serra circular de bancada na central de corte")

    # `_menciona` tolera três letras de sufixo, então `serra` solto no `na_cena`
    # abriria em "madeira serrada", "tábua serrada" e "pó de serragem" — nenhum
    # deles uma máquina, todos vocabulário corrente de canteiro. Como é o
    # `18.10.1.5` que ocupava vaga em 8 dossiês de 15, `serra` solto desfaria em
    # silêncio o principal ganho deste portão. Por isso `na_cena` traz o NOME DA
    # MÁQUINA, que é o que o docstring do `Setor` sempre pediu.
    for madeira in ("madeira serrada empilhada no piso",
                    "tábua serrada apoiada na parede",
                    "pó de serragem acumulado no canto"):
        assert not setor_pertinente(serra, madeira), madeira

    # E a simétrica, que é a mais perigosa das três: `contrapeso` é o objeto que
    # CONFUNDE os dois equipamentos — o `18.12.22` regula o contrapeso do
    # andaime suspenso, e foi ele que virou não conformidade na foto da grua.
    # Usá-lo no `na_cena` do guindar recriaria a mesma confusão no sentido
    # inverso: uma foto legítima de andaime suspenso, que menciona contrapesos
    # porque eles fazem parte dele, abriria o portão dos equipamentos de
    # guindar. `grua` e `guindaste` cobrem o caso sem esse risco.
    guindar = base.obter("NR-18", "18.10.1.24")
    assert not setor_pertinente(
        guindar, "andaime suspenso na fachada, com contrapesos de concreto"
    ), "o contrapeso do andaime suspenso não pode destrancar item de grua"
    assert setor_pertinente(
        guindar, "vista do topo de estrutura metálica elevada, possivelmente uma grua"
    )


def test_o_portao_de_elevador_reforca_em_codigo_o_prompt_do_olho(base):
    """O #32 ensinou o Olho a escrever "torre metálica treliçada" quando não dá
    para saber se a torre é de grua ou de elevador. O portão fecha o mesmo
    caminho pelo outro lado: sem o nome na cena, a seção 18.11 dos elevadores de
    obra não é candidata nem pela busca textual.

    Era por ali que o `NR-18 18.11.14` chegou ao laudo de uma grua em 05/09 —
    com risco curado nenhum disparando, medido na época.
    """
    from auditoria.dossie import setor_pertinente

    item = base.obter("NR-18", "18.11.14")
    assert not setor_pertinente(item, "torre metálica treliçada amarela de canteiro")
    assert setor_pertinente(item, "torre do elevador de obra, com cabine e cremalheira")


def test_eletrica_predial_generica_nao_cita_nr12_sem_maquina_na_cena(base):
    """Lote real: cabo danificado e caixa de distribuição aberta em obra civil,
    sem nenhuma máquina na cena, chegavam ao dossiê com NR-12 12.3.4/12.3.8 —
    itens que falam de condutor e parte energizada DE MÁQUINA.

    A verificação é sobre o dossiê, e não sobre `rotear_riscos`: o item de
    NR-12 continua mapeado no risco, e é o portão de máquina que decide se ele
    entra. Testar o roteamento diria que o mapeamento existe, não que o laudo
    fica limpo."""
    casos = [
        ("Parede interna de alvenaria em obra, pavimento em acabamento", [
            "Cabo elétrico preto grosso com isolamento danificado e fios internos "
            "expostos pendurado na estrutura metálica.",
        ]),
        ("Canteiro de obra, área externa junto ao tapume", [
            "Caixa de distribuição elétrica com tampa frontal aberta, sem proteção "
            "de tampa visível, expondo os componentes internos.",
        ]),
        ("Laje de concreto em obra de edificação, área de circulação", [
            "Entulho de construção e restos de fôrma de madeira acumulados sobre o "
            "piso da área de circulação.",
        ]),
    ]
    for ambiente, fatos in casos:
        citados = _nr12(_dossie_da_cena(base, ambiente, fatos))
        assert not citados, f"{fatos[0]!r} citou NR-12 sem máquina na cena: {citados}"


def test_a_mesma_eletrica_cita_nr12_quando_a_maquina_esta_na_cena(base):
    """A contraparte do teste acima, e a razão de o portão ser por item e não
    uma remoção seca: com a máquina de fato na foto, o item que fala do cabo
    de alimentação DE MÁQUINA é o enquadramento certo, não um exagero."""
    dossie = _dossie_da_cena(
        base, "Canteiro de obra, área de preparo de concreto",
        ["Betoneira com o cabo de alimentação de isolamento danificado e fios "
         "internos expostos, estendido sobre o piso."],
    )
    assert "12.3.4" in _nr12(dossie), _nr12(dossie)


def test_maquina_na_cena_e_reconhecida_pelo_nome_e_nao_pela_palavra_maquina():
    """O portão só ABRE, então um sinal que aparece em frase de negação seria
    pior que inútil: "nenhuma máquina visível" destrancaria justamente a foto
    que se quer barrar. Por isso vale o substantivo concreto."""
    assert dossie.ha_maquina_na_cena("Betoneira em operação junto à laje")
    assert dossie.ha_maquina_na_cena("Serra circular de bancada com disco exposto")
    assert dossie.ha_maquina_na_cena("Grua fixa com cabo de aço desfiado")
    assert dossie.ha_maquina_na_cena("Masseira espiral com a grade levantada")

    assert not dossie.ha_maquina_na_cena("Nenhuma máquina visível na cena")
    assert not dossie.ha_maquina_na_cena(
        "Trabalhador sem equipamento de proteção individual"
    )
    assert not dossie.ha_maquina_na_cena(
        "Entulho acumulado sobre o piso da área de circulação"
    )
    # "torno" sozinho abriria o portão em "em torno de", que é como um laudo
    # descreve a área ao redor de um pilar; "prensa" não pode vir de
    # "imprensado". Substantivo é o critério, substring não.
    assert not dossie.ha_maquina_na_cena("Material empilhado em torno da coluna")
    assert not dossie.ha_maquina_na_cena("Risco de trabalhador imprensado na carga")
    assert dossie.ha_maquina_na_cena("Torno mecânico com placa exposta")
    # Varridas contra frases reais de canteiro: "talha" abria em "madeira
    # talhada" e "gerador" em "gerador de resíduos", que é vocabulário de PGR.
    assert not dossie.ha_maquina_na_cena("Madeira talhada empilhada junto ao tapume")
    assert not dossie.ha_maquina_na_cena("Gerador de resíduos identificado no canteiro")
    assert dossie.ha_maquina_na_cena("Grupo gerador a diesel junto ao tapume")


def test_anexo_setorial_de_outro_ramo_nao_entra_no_dossie(base):
    """Uma betoneira de canteiro gastava os cinco lugares da NR-12 com o Anexo X
    (calçados: "máquina de pregar salto", "injetora rotativa de carrossel"), e
    uma serra circular de bancada recebia três itens de serra fita de AÇOUGUE.
    Item verdadeiro, situação errada — e foi por aí que a betoneira do lote
    anterior saiu no laudo como prensa."""
    setoriais = {"V", "VI", "VII", "VIII", "IX", "X", "XI"}
    cenas = [
        ("Canteiro de obra, área de preparo de concreto", [
            "Betoneira em operação com o conjunto de coroa e pinhão exposto, sem "
            "proteção fixa sobre a engrenagem.",
        ]),
        ("Central de corte de madeira do canteiro", [
            "Serra circular de bancada com o disco exposto, sem coifa protetora "
            "sobre a lâmina.",
        ]),
    ]
    for ambiente, fatos in cenas:
        dossie_ = _dossie_da_cena(base, ambiente, fatos)
        intrusos = [
            f"{e.item.nr} {e.item.item}"
            for e in dossie_.entradas
            if e.item.nr == "NR-12" and e.item.anexo in setoriais
        ]
        assert not intrusos, f"{ambiente!r} recebeu anexo de outro ramo: {intrusos}"


def test_anexo_setorial_entra_quando_a_cena_e_daquele_ramo(base):
    """A contraparte que impede o filtro de virar remoção: numa foto de açougue
    o Anexo VII é a norma certa, e o app existe para citá-la."""
    dossie_ = _dossie_da_cena(
        base, "Açougue de supermercado, sala de desossa",
        ["Serra fita de açougue com a lâmina exposta acima da mesa, sem proteção "
         "regulável.",
         "Moedor de carne sem proteção contra alcance das mãos no funil."],
    )
    anexos = {e.item.anexo for e in dossie_.entradas if e.item.nr == "NR-12"}
    assert "VII" in anexos, sorted(a for a in anexos if a)


def test_anexo_geral_de_maquina_e_de_altura_continuam_passando(base):
    """A contraparte registrada no CLAUDE.md: NR-12 Anexo XII (equipamentos de
    guindar — cesta aérea, grua, elevador de carga) e NR-35 Anexo III (escadas)
    são o pão de cada dia de um canteiro e não podem ser confundidos com anexo
    setorial."""
    cena = "canteiro de obra, laje, escada de mão apoiada, entulho no piso"
    for nr, num in (("NR-12", "Anexo XII 2.1"), ("NR-12", "Anexo III 1"),
                    ("NR-12", "Anexo I 1"), ("NR-35", "Anexo III 5.2.2.5"),
                    ("NR-12", "12.5.1"), ("NR-12", "12.2.4")):
        item = base.obter(nr, num)
        assert item is not None, f"{nr} {num}"
        assert dossie.setor_pertinente(item, cena), f"{nr} {num} barrado"


def test_item_setorial_deixado_fora_do_anexo_pela_extracao_tambem_e_barrado(base):
    """O anexo é o critério principal, mas não basta: a extração do PDF deixou
    `12.1` ("máquinas de montar base de calçados") no corpo principal, sem
    marca de anexo nenhuma, e ele apareceu no dossiê de uma betoneira."""
    item = base.obter("NR-12", "12.1")
    assert item is not None and item.anexo is None
    assert not dossie.setor_pertinente(item, "canteiro de obra com betoneira")
    assert dossie.setor_pertinente(item, "fábrica de calçados, setor de montagem do solado")


def test_anexo_vence_o_texto_ao_classificar_o_ramo(base):
    """Os anexos setoriais se citam entre si, e item do Anexo X (calçados) fala
    de prensa. Se o texto decidisse, ele passaria como se fosse do Anexo VIII
    numa foto de estamparia — que legitimamente destranca prensas."""
    item = base.obter("NR-12", "Anexo X 10.1")
    assert item is not None
    assert not dossie.setor_pertinente(item, "setor de estamparia com prensa excêntrica")


def test_item_generico_entra_no_dossie_sem_rotulo_de_risco(base):
    """Laudo real de 30/08: a NC saiu intitulada "Andaime sem guarda-corpo e
    rodapé no perímetro da plataforma" para uma constatação sobre a tela frouxa
    na borda da laje — enquanto o fato registrado dizia que o andaime TINHA
    guarda-corpo. Dois modelos de texto diferentes erraram igual, o que mostra
    que é o mapa e não o modelo: `NR-18 18.9.1` ("proteção coletiva onde houver
    risco de queda") é reivindicado por mais de um risco, então o rótulo que
    sobra depende de qual deles roteou primeiro."""
    visao = Visao(
        ambiente="Laje de construção civil em fase de estruturação",
        achados=[Achado(t) for t in (
            "Tela plástica flexível de malha larga esticada sobre tubos metálicos "
            "finos, cobrindo a borda da laje.",
            "Trecho da tela plástica está frouxo e descaído, acumulando-se no piso "
            "da laje em vez de permanecer esticado na borda.",
            "Abertura retangular no piso da laje, com bordas de concreto aparente, "
            "sem cobertura ou fechamento visível.",
            "Estrutura metálica de andaime suspensa, com guarda-corpo de tubos e "
            "pneus pretos presos na lateral externa.",
        )],
    )
    dossie, origem = montar_dossie(base, visao, "", HOJE)
    por_item = {
        e.item.id: origem[e.rotulo].rotulo
        for e in dossie.entradas if e.rotulo in origem
    }
    assert por_item.get("NR-18 18.9.1") == "", por_item
    # O item específico de andaime continua nomeando a NC: só o genérico perde.
    assert por_item.get("NR-18 18.12.15.2"), por_item
    assert por_item.get("NR-18 18.9.2"), por_item


def test_rotulo_perdido_nao_apaga_o_portao_de_pessoa_nem_a_gravidade(base):
    """Só o rótulo cai. O risco continua inteiro para o que depende dele de
    verdade — senão o item genérico deixaria de exigir pessoa na cena."""
    from auditoria.riscos import catalogo as catalogo_riscos, itens_compartilhados

    compartilhados = itens_compartilhados()
    assert "NR-06 6.5.1" in compartilhados, "EPI genérico deveria ser disputado"

    donos = [r for r in catalogo_riscos().values() if "NR-06 6.5.1" in r.itens]
    assert any(r.exige_pessoa for r in donos), "o teste perdeu o sentido"

    visao = Visao(
        ambiente="Frente de serviço em obra",
        achados=[Achado("Trabalhador sem capacete de segurança, com a cabeça "
                        "descoberta, junto à alvenaria.")],
        pessoas_presentes=True, quantidade_pessoas=1,
    )
    dossie, origem = montar_dossie(base, visao, "", HOJE)
    for entrada in dossie.entradas:
        risco = origem.get(entrada.rotulo)
        if risco is not None and entrada.item.id in compartilhados:
            assert risco.rotulo == ""
            assert risco.gravidade_base, "gravidade base não pode se perder"


def test_glossario_extraido_como_item_nao_entra_no_dossie(base):
    """Laudo real: "Glossário Ambiente exclusivo: espaço físico…" da NR-01
    ocupava vaga do dossiê. O PDF não separou o cabeçalho do primeiro item,
    então `titulo_da_secao` volta vazio e o cabeçalho vem colado no texto."""
    item = base.obter("NR-01", "Anexo II 6")
    assert item is not None
    assert not dossie.prescritivo(item, base)


# ---------------------------------------------------------------------------
# Aferição — o coração da garantia
# ---------------------------------------------------------------------------

def _dossie_de(base, refs):
    from auditoria.dossie import Dossie, Entrada

    entradas = []
    for n, ref in enumerate(refs, start=1):
        nr, _, item = ref.partition(" ")
        entradas.append(Entrada(f"D{n}", base.obter(nr, item)))
    return Dossie(entradas=entradas, data_referencia=HOJE)


def _proposta(dossie_ref, **extra):
    base_nc = {
        "dossie": dossie_ref,
        "constatacao": "Condição observada em desacordo com o item.",
        "consequencia": "Exposição a risco.",
        "gravidade": "alta",
        "acao_corretiva": "Regularizar.",
        "prazo_dias": 7,
    }
    base_nc.update(extra)
    return {"nao_conformidades": [base_nc]}


def test_afericao_descarta_rotulo_inexistente(base):
    dossie = _dossie_de(base, ["NR-18 18.9.2"])
    visao = Visao()
    aprovadas, recusas = aferir(_proposta("D99"), dossie, {}, visao, HOJE)
    assert aprovadas == []
    assert any("não existe no dossiê" in r for r in recusas)


def test_afericao_descarta_item_repetido(base):
    dossie = _dossie_de(base, ["NR-18 18.9.2"])
    proposta = _proposta("D1")
    proposta["nao_conformidades"].append(dict(proposta["nao_conformidades"][0]))
    aprovadas, recusas = aferir(proposta, dossie, {}, Visao(), HOJE)
    assert len(aprovadas) == 1
    assert any("mais de uma vez" in r for r in recusas)


def test_afericao_descarta_item_fora_de_vigencia(base):
    dossie = _dossie_de(base, ["NR-18 18.9.1.1"])       # vigente só a partir de 29/06/2026
    aprovadas, recusas = aferir(_proposta("D1"), dossie, {}, Visao(), date(2026, 1, 10))
    assert aprovadas == []
    assert any("não está vigente" in r for r in recusas)


def test_afericao_barra_cobranca_de_epi_sem_pessoa_na_foto(base):
    """O bug original: laudo cobrando EPI numa foto sem ninguém."""
    riscos = catalogo_riscos()
    com_pessoa = next(r for r in riscos.values() if r.exige_pessoa)
    ref = com_pessoa.itens[0]
    dossie = _dossie_de(base, [ref])
    origem = {"D1": com_pessoa}

    vazia = Visao(pessoas_presentes=False)
    aprovadas, recusas = aferir(_proposta("D1"), dossie, origem, vazia, HOJE)
    assert aprovadas == []
    assert any("exige trabalhador" in r for r in recusas)

    com_gente = Visao(pessoas_presentes=True, quantidade_pessoas=2)
    aprovadas, _ = aferir(_proposta("D1"), dossie, origem, com_gente, HOJE)
    assert len(aprovadas) == 1


def test_afericao_normaliza_gravidade_e_prazo_invalidos(base):
    dossie = _dossie_de(base, ["NR-18 18.9.2"])
    aprovadas, _ = aferir(
        _proposta("D1", gravidade="apocaliptica", prazo_dias="amanhã"),
        dossie, {}, Visao(), HOJE,
    )
    assert aprovadas[0].gravidade in {"critica", "alta", "media", "baixa"}
    assert aprovadas[0].prazo_dias > 0


@pytest.mark.parametrize(
    "escrito",
    [
        "Viola a NR-35 item 35.2.1 e também outra coisa.",
        "Descumpre NR-18, itens 18.9.2 e 18.9.4.1, conforme observado.",
        "Situação irregular (NR-12 12.5.1) na zona de perigo.",
        "Contraria a NR‑10 subitem 10.2.3 no painel.",
    ],
)
def test_afericao_remove_citacao_escrita_pelo_modelo(base, escrito):
    """O modelo não pode contrabandear citação pela prosa: só o código cita.

    E o número do item tem de sair junto — deixá-lo para trás seria pior, porque
    o renderizador voltaria a lê-lo como citação legítima.
    """
    dossie = _dossie_de(base, ["NR-18 18.9.2"])
    aprovadas, _ = aferir(
        _proposta("D1", constatacao=escrito), dossie, {}, Visao(), HOJE
    )
    limpo = aprovadas[0].constatacao
    assert "NR" not in limpo.upper().replace("NR-18 18.9.2", "")
    assert extrair_citacoes(limpo) == [], f"sobrou citação em {limpo!r}"


def test_constatacao_limpa_mantem_pontuacao_final(base):
    dossie = _dossie_de(base, ["NR-18 18.9.2"])
    aprovadas, _ = aferir(
        _proposta("D1", constatacao="Placa solta sobre o vão, contrariando a NR-18 18.9.2"),
        dossie, {}, Visao(), HOJE,
    )
    assert aprovadas[0].constatacao.endswith(".")


# ---------------------------------------------------------------------------
# Ponta a ponta
# ---------------------------------------------------------------------------

@pytest.fixture(scope="module")
def laudo_demo(base):
    return executar(
        ClienteDemonstracao(), base, "imagem-falsa",
        "Vistoria em canteiro de obra de edificação",
        Configuracao(modelo_visao="demo", modelo_texto="demo",
                     data_referencia=HOJE, max_ciclos=3),
    )


def test_pipeline_completo_enquadra_a_abertura_no_piso(laudo_demo):
    citados = {f"{nc.item.nr} {nc.item.item}" for nc in laudo_demo.nao_conformidades}
    assert "NR-18 18.9.2" in citados, "perdeu o enquadramento correto da abertura no piso"
    assert laudo_demo.aprovado


def test_pipeline_nao_cobra_epi_em_foto_sem_pessoas(laudo_demo):
    assert not laudo_demo.visao.pessoas_presentes
    assert "NR-06" not in {nc.item.nr for nc in laudo_demo.nao_conformidades}


def test_toda_citacao_do_laudo_existe_e_esta_vigente(base, laudo_demo):
    texto = relatorio.markdown(laudo_demo, base, numero=1)
    for citacao in extrair_citacoes(texto):
        item = base.obter(citacao.nr, citacao.item)
        assert item is not None, f"laudo citou item inexistente: {citacao.id}"
        assert item.vigente_em(HOJE), f"laudo citou item fora de vigência: {citacao.id}"


def test_laudo_transcreve_o_texto_oficial_do_item(base, laudo_demo):
    texto = relatorio.markdown(laudo_demo, base, numero=1)
    for nc in laudo_demo.nao_conformidades:
        assert nc.item.texto[:60] in texto, f"faltou o texto verbatim de {nc.item.id}"


def test_html_do_laudo_e_autocontido(base, laudo_demo):
    html = relatorio.para_html(relatorio.markdown(laudo_demo, base, numero=1))
    assert html.startswith("<!doctype html>")
    assert "<table>" in html and "<blockquote>" in html
    assert "http://" not in html and "https://" not in html      # nada externo


def test_consolidado_lista_plano_de_acao(base, laudo_demo):
    texto = relatorio.consolidado([("foto_1.jpg", laudo_demo)], base, HOJE)
    assert "Plano de ação priorizado" in texto
    assert "NR-18" in texto


# ---------------------------------------------------------------------------
# Edição vigente — a NR-10 de 2026 só vale a partir de 01/06/2027
# ---------------------------------------------------------------------------

def test_usa_a_edicao_em_vigor_e_nao_a_mais_recente():
    """Publicada não é o mesmo que vigente.

    A NR-10 de 2026 renumerou a norma inteira e só entra em vigor em 01/06/2027.
    Citá-la antes disso daria número certo com o texto de outra redação — o erro
    mais difícil de detectar, porque o item existe.
    """
    antes = carregar_base(referencia=date(2026, 8, 24))
    depois = carregar_base(referencia=date(2027, 7, 1))

    assert antes.edicoes["NR-10"] != depois.edicoes["NR-10"]
    assert "2019" in antes.edicoes["NR-10"]
    assert "2026" in depois.edicoes["NR-10"]

    # Mesmo número, redações diferentes: é justamente o que torna o erro perigoso.
    assert antes.obter("NR-10", "10.10.1").texto != depois.obter("NR-10", "10.10.1").texto


def test_avisa_sobre_edicao_publicada_ainda_nao_vigente():
    base = carregar_base(referencia=date(2026, 8, 24))
    assert "NR-10" in base.edicoes_futuras
    _, inicio = base.edicoes_futuras["NR-10"]
    assert inicio == "2027-06-01"


def test_taxonomia_valida_contra_a_edicao_em_vigor_hoje(base):
    """Guarda contra o erro que o portão de existência não pega.

    Um item pode existir nas duas edições com textos totalmente diferentes. Este
    teste garante ao menos que nenhuma referência aponte para item ausente ou
    revogado na redação que o app realmente vai citar.
    """
    for risco in catalogo_riscos().values():
        for ref in risco.itens:
            nr, _, item = ref.partition(" ")
            alvo = base.obter(nr, item)
            assert alvo is not None, f"{risco.id}: {ref} não existe na edição vigente"
            assert not alvo.revogado, f"{risco.id}: {ref} está revogado"


def test_novas_normas_carregadas_e_mapeadas(base):
    """NR-13 e NR-20, acrescentadas ao acervo, entraram na base e na taxonomia."""
    assert "NR-13" in base.por_nr and "NR-20" in base.por_nr
    assert "vaso de pressão" in base.obter("NR-13", "13.5.1.3").texto.lower()
    assert "ignição" in base.obter("NR-20", "20.13.4").texto.lower()

    mapeadas = {ref.split()[0] for r in catalogo_riscos().values() for ref in r.itens}
    assert {"NR-13", "NR-20"} <= mapeadas


def test_roteamento_acha_riscos_das_normas_novas():
    compressor = Visao(achados=[Achado("compressor de ar com reservatório sem placa de identificação")])
    assert "vaso_pressao_sem_placa_identificacao" in [r.id for r in rotear_riscos(compressor)]

    diesel = Visao(achados=[Achado("tambor de diesel apoiado no chão sem bacia de contenção")])
    assert "tanque_inflamavel_sem_contencao" in [r.id for r in rotear_riscos(diesel)]


def test_base_se_reconstroi_quando_o_acervo_muda(tmp_path):
    """Subir um PDF novo deve bastar; ninguém precisa lembrar de rodar o kb_build."""
    from auditoria.kb_build import impressao_digital

    base = carregar_base()
    assert base.impressao_digital, "base sem impressão digital do acervo"
    assert base.impressao_digital == impressao_digital()


# ---------------------------------------------------------------------------
# Resiliência do cliente — caminhos que só aparecem contra a API real
# ---------------------------------------------------------------------------

def _resposta_http(status: int):
    """Resposta httpx mínima, como a que o SDK da Groq embrulha nos seus erros."""
    import httpx

    return httpx.Response(status, request=httpx.Request("POST", "https://api.groq.com/x"))

MENSAGENS_DE_RECUSA_JSON = [
    # O modelo não suporta o parâmetro.
    "Error code: 400 - response_format is not supported for this model",
    # O modelo suporta, aceita, e falha em produzir JSON válido — foi este que
    # apareceu em produção com o modelo de visão, cujos tokens de raciocínio
    # não passam pelo validador da Groq.
    "Error code: 400 - {'error': {'message': \"Failed to validate JSON. Please adjust "
    "your prompt. See 'failed_generation' for more details.\", 'type': "
    "'invalid_request_error', 'code': 'json_validate_failed', 'failed_generation': ''}}",
]


@pytest.mark.parametrize("mensagem", MENSAGENS_DE_RECUSA_JSON)
def test_cliente_segue_sem_json_estrito_quando_o_modelo_recusa(monkeypatch, mensagem):
    """As duas formas de a Groq recusar o modo JSON não podem derrubar o laudo."""
    import groq

    from auditoria.modelos import ClienteGroq

    cliente = ClienteGroq(api_key="falsa")
    tentativas: list[dict] = []

    class RespostaFalsa:
        headers: dict = {}
        usage = None
        choices = [type("C", (), {"message": type("M", (), {"content": '{"ok": true}'})()})()]

        def parse(self):
            return self

    def falso_create(**parametros):
        tentativas.append(parametros)
        if "response_format" in parametros:
            raise groq.BadRequestError(mensagem, response=_resposta_http(400), body=None)
        return RespostaFalsa()

    monkeypatch.setattr(cliente.cliente.chat.completions.with_raw_response, "create", falso_create)

    saida = cliente.conversar("modelo-x", [{"role": "user", "content": "oi"}], json_estrito=True)

    assert saida == '{"ok": true}'
    assert len(tentativas) == 2, "deveria ter tentado de novo sem response_format"
    assert "response_format" in tentativas[0] and "response_format" not in tentativas[1]
    # E não insiste na exigência com esse modelo nas chamadas seguintes.
    assert "modelo-x" in cliente.sem_json_estrito


def test_erros_da_api_viram_mensagem_acionavel():
    """O usuário precisa saber o que fazer, não ver o traceback cru da biblioteca."""
    import groq

    from auditoria.modelos import traduzir

    traduzido = traduzir(
        groq.RateLimitError("429", response=_resposta_http(429), body=None)
    )
    assert "cota" in traduzido.mensagem.lower()
    assert traduzido.sugestao and traduzido.recuperavel


def test_leitor_de_json_atravessa_raciocinio_e_cercas():
    """Sem o modo estrito, o modelo devolve o objeto embrulhado em prosa."""
    from auditoria.pipeline import _ler_json

    casos = {
        "<think>Preciso de {chaves} aqui.</think> {\"ambiente\": \"quadro\"}": "ambiente",
        "Claro!\n```json\n{\"a\": 1}\n```\nEspero ter ajudado.": "a",
        "prosa com { chave solta e depois {\"ok\": true} de verdade": "ok",
        '{"texto": "tem { chave } dentro da string", "n": 2}': "texto",
    }
    for bruto, esperado in casos.items():
        assert esperado in _ler_json(bruto, "teste"), bruto[:40]


def test_erro_de_json_vira_mensagem_recuperavel():
    """O 400 de JSON não deve mais sugerir reduzir a imagem — não é essa a causa."""
    import groq

    from auditoria.modelos import traduzir

    erro = traduzir(
        groq.BadRequestError(
            MENSAGENS_DE_RECUSA_JSON[1], response=_resposta_http(400), body=None
        )
    )
    assert erro.recuperavel
    assert "resolução" not in erro.sugestao.lower()


def test_sem_fato_extraido_nao_ha_enquadramento(base):
    """Se a visão falha, o laudo não pode nascer do texto que o inspetor digitou.

    Este foi um erro observado em produção: o agente de visão voltou vazio, o
    analista enquadrou assim mesmo a partir do contexto escrito, e só o veto do
    supervisor impediu uma não conformidade sem nenhuma evidência visual.
    """
    from auditoria.demo import ClienteDemonstracao

    class VisaoVazia(ClienteDemonstracao):
        def conversar(self, modelo, mensagens, teto_saida=1200, temperatura=0.0,
                      json_estrito=False):
            texto = " ".join(
                p.get("text", "")
                for m in mensagens for p in (m["content"] if isinstance(m["content"], list) else [])
            )
            if "perito em documentação fotográfica" in texto:
                return '{"ambiente": "", "pessoas": {"presentes": false}, "achados": []}'
            raise AssertionError("o analista não deveria ter sido chamado")

    laudo = executar(
        VisaoVazia(), base, "imagem-falsa",
        "O botão de emergência do painel está quebrado",   # contexto tentador
        Configuracao(modelo_visao="demo", modelo_texto="demo", data_referencia=HOJE),
    )
    assert laudo.visao_falhou
    assert laudo.nao_conformidades == []


def test_laudo_avisa_que_falha_de_visao_nao_atesta_conformidade(base):
    from auditoria.pipeline import Laudo, Visao

    laudo = Laudo(visao=Visao(), visao_falhou=True, data_referencia=HOJE)
    texto = relatorio.markdown(laudo, base, numero=1)
    assert "leitura da imagem falhou" in texto.lower()
    assert "não** atesta conformidade" in texto


def test_visao_repete_quando_a_resposta_foi_cortada_no_limite():
    """Truncamento não é resposta vazia: é meia frase, e merece nova tentativa.

    Observado em produção: o modelo de raciocínio consumia todo o orçamento de
    saída pensando e era cortado antes de escrever o JSON, devolvendo um laudo
    sem nenhum fato.
    """
    from auditoria.pipeline import agente_olho

    tentativas: list[int] = []

    class CortaNaPrimeira:
        ultimo_corte_por_limite = False

        def conversar(self, modelo, mensagens, teto_saida=1200, temperatura=0.0,
                      json_estrito=False):
            tentativas.append(teto_saida)
            if len(tentativas) == 1:
                self.ultimo_corte_por_limite = True
                return '{"ambiente": "canteiro", "achados": [{"fato": "trunc'
            self.ultimo_corte_por_limite = False
            return (
                '{"ambiente": "canteiro de obra", "pessoas": {"presentes": false},'
                ' "achados": [{"fato": "painel elétrico sem tampa", "onde": "centro"}]}'
            )

    visao = agente_olho(CortaNaPrimeira(), "imagem", "modelo-x")
    assert len(tentativas) == 2 and tentativas[1] > tentativas[0]
    assert [a.fato for a in visao.achados] == ["painel elétrico sem tampa"]


def test_visao_repete_quando_o_json_nao_parseia_sem_a_api_sinalizar():
    """O caso que faltava no Olho, e que já estava fechado no Analista e no Diretor.

    A primeira correção só refazia a chamada quando a API confirmava
    truncamento (`finish_reason == "length"`). Um lote real perdeu três fotos
    de novo com "não devolveu JSON utilizável" SEM esse sinal — JSON inválido
    por outro motivo. A segunda correção cobriu isso em `_conversar_sem_cortar`,
    mas o Olho tinha retentativa própria e ficou de fora por meses.

    A falha do Olho é a mais cara do pipeline: nada segue sem os fatos, então a
    foto sai sem laudo nenhum, e não com um laudo pior.
    """
    from auditoria.pipeline import agente_olho

    tentativas: list[int] = []

    class QuebraOJsonSemAvisar:
        # A API não sinaliza nada: do ponto de vista dela, a resposta terminou.
        ultimo_corte_por_limite = False

        def conversar(self, modelo, mensagens, teto_saida=1200, temperatura=0.0,
                      json_estrito=False):
            tentativas.append(teto_saida)
            if len(tentativas) == 1:
                return '{"ambiente": "canteiro", "achados": [{"fato": "aspa " nao escapada"}]}'
            return (
                '{"ambiente": "canteiro de obra", "pessoas": {"presentes": false},'
                ' "achados": [{"fato": "poço de elevador aberto", "onde": "centro"}]}'
            )

    visao = agente_olho(QuebraOJsonSemAvisar(), "imagem", "modelo-x")
    assert len(tentativas) == 2, "o Olho não refez a chamada"
    # O teto dobra porque a temperatura é 0,0: repetir a chamada idêntica
    # devolveria a mesma resposta, e portanto o mesmo JSON quebrado.
    assert tentativas[1] == tentativas[0] * 2
    assert [a.fato for a in visao.achados] == ["poço de elevador aberto"]


def test_erro_de_cota_no_olho_nao_vira_laudo_de_leitura_falhada():
    """A foto que não chegou à Groq NÃO pode sair como foto examinada.

    Regressão real, medida num lote de 12 em 04/09: ao migrar o Olho para
    `_conversar_sem_cortar`, o `try/except` passou a envolver a CHAMADA inteira
    em vez de só o parse. `ClienteGroq.conversar` levanta `ErroDeAuditoria` para
    qualquer falha da API — cota esgotada inclusive —, então 8 fotos de 12
    saíram com laudo de "a leitura da imagem falhou · 0s" (`0s` porque o erro de
    cota volta na hora, sem chamada) e foram CONTADAS COMO AUDITADAS: o sumário
    disse "9 de 12 analisadas" e listou só 3 em "Imagens não auditadas".

    Um laudo que diz "nenhuma não conformidade" sobre uma foto que ninguém olhou
    é pior que nenhum laudo. Erro de chamada tem de subir.
    """
    from auditoria.pipeline import agente_olho
    from auditoria.modelos import ErroDeAuditoria

    class CotaEsgotada:
        ultimo_corte_por_limite = False

        def conversar(self, modelo, mensagens, teto_saida=1200, temperatura=0.0,
                      json_estrito=False):
            raise ErroDeAuditoria(
                "Cota da Groq esgotada (limite de tokens por minuto ou por dia).",
                recuperavel=True,
            )

    with pytest.raises(ErroDeAuditoria, match="Cota da Groq"):
        agente_olho(CotaEsgotada(), "imagem", "modelo-x")


def test_visao_guarda_o_bruto_tambem_quando_o_json_e_valido():
    """O `bruto` do caminho de SUCESSO não é decoração.

    Quando o Olho devolve JSON válido sem achado nenhum, `visao_falhou` também
    fica verdadeiro, e a tela mostra a resposta crua. É o que distingue "o
    modelo não viu nada" de "o modelo respondeu num formato que não soubemos
    ler" — dois consertos opostos. Ao migrar o Olho para
    `_conversar_sem_cortar`, que devolvia só o dicionário, esse texto quase se
    perdeu; por isso a função devolve o par.
    """
    from auditoria.pipeline import agente_olho

    resposta = '{"ambiente": "escritório", "pessoas": {"presentes": false}, "achados": []}'

    class SemAchados:
        ultimo_corte_por_limite = False

        def conversar(self, modelo, mensagens, teto_saida=1200, temperatura=0.0,
                      json_estrito=False):
            return resposta

    visao = agente_olho(SemAchados(), "imagem", "modelo-x")
    assert visao.achados == []
    assert visao.bruto == resposta


def test_visao_preserva_resposta_crua_quando_nao_da_para_ler():
    """Sem o texto cru na mão, não dá para distinguir os modos de falha."""
    from auditoria.pipeline import agente_olho

    class Tagarela:
        ultimo_corte_por_limite = False

        def conversar(self, modelo, mensagens, **kwargs):
            return "Desculpe, não consigo analisar esta imagem."

    visao = agente_olho(Tagarela(), "imagem", "modelo-x")
    assert visao.achados == []
    assert "não consigo analisar" in visao.bruto


def test_texto_da_norma_nao_carrega_numero_de_pagina(base):
    """O extrator colava o número da página no fim do item, e ele saía no laudo."""
    import re

    assert base.obter("NR-08", "8.3.2.4").texto.endswith("antiderrapantes.")
    sujos = [i.id for i in base.itens.values() if re.search(r"[.;:]\s+\d{1,3}\s*$", i.texto)]
    assert sujos == [], f"paginação remanescente em {sujos[:5]}"


def test_palavra_chave_ambigua_nao_roteia_para_norma_setorial():
    """"carcaça" de frigorífico casava com a carcaça de um alarme, e a NR-36
    aparecia como aplicável num laudo de painel elétrico."""
    from auditoria.dossie import _pontuar_nrs

    pontos = _pontuar_nrs(
        "dispositivo de alarme sonoro com a carcaça frontal deslocada e danificada; "
        "chave tipo faca no quadro elétrico"
    )
    assert "NR-36" not in pontos


def test_maquina_e_equipamento_sozinhos_nao_roteiam_para_nr12():
    """"máquina" e "equipamento" sozinhos casavam com quase qualquer achado
    (EPI, quadro elétrico, máquina de lavar) e a NR-12 virava lixeira do
    dossiê, enchendo o complemento textual de itens fora de tema."""
    from auditoria.dossie import _pontuar_nrs

    casos = [
        "trabalhador sem uso de equipamento de proteção individual (capacete)",
        "andaime sem proteção lateral em altura",
        "escada de mão sem proteção antiderrapante nos degraus",
        "máquina de lavar roupa na área de vivência sem manutenção",
        "operador da máquina fotográfica sem crachá",
    ]
    for caso in casos:
        assert "NR-12" not in _pontuar_nrs(caso), caso

    # mas o achado genuíno de máquina continua roteando
    assert "NR-12" in _pontuar_nrs("serra circular sem proteção no disco")
    assert "NR-12" in _pontuar_nrs(
        "zona de prensagem de prensa hidráulica sem enclausuramento"
    )


def test_item_de_formato_de_avaliacao_nao_e_comprovavel_em_foto(base):
    """Laudo real: uma foto de escritório (monitor exibindo documento de RH,
    sem nenhum achado de campo) enquadrou "documento exposto na tela" no
    item que trata do FORMATO da prova de treinamento (presencial x digital
    com senha) — item verdadeiro, situação completamente errada. Nenhuma
    foto prova ou desmente o método de avaliação de um treinamento."""
    from auditoria.dossie import comprovavel_em_foto

    item = base.obter("NR-01", "Anexo II 4.6.1")
    assert not comprovavel_em_foto(item)


def test_tabela_desambigua_constatacoes_sob_o_mesmo_risco(base):
    """Dois achados distintos no mesmo risco não podem virar linhas idênticas."""
    from auditoria.pipeline import Laudo, NaoConformidade, Visao

    def nc(item, constatacao):
        return NaoConformidade(
            item=base.obter("NR-12", item), constatacao=constatacao,
            consequencia="", gravidade="media", acao_corretiva="Corrigir.",
            prazo_dias=5, rotulo_risco="Dispositivo de segurança danificado",
        )

    laudo = Laudo(
        visao=Visao(ambiente="oficina"),
        nao_conformidades=[
            nc("12.11.5", "Alarme sonoro com a carcaça deslocada."),
            nc("12.5.16", "Abertura circular vazia no painel."),
        ],
        data_referencia=HOJE,
    )
    linhas = [l for l in relatorio.markdown(laudo, base, numero=1).splitlines()
              if l.startswith("| 1 |") or l.startswith("| 2 |")]
    assert len(linhas) == 2 and linhas[0] != linhas[1]


def test_modulos_com_dataclass_nao_usam_anotacoes_adiadas():
    """Guarda contra um erro que só aparece em produção, nunca aqui.

    Com `from __future__ import annotations` toda anotação vira string, e o
    módulo `dataclasses` passa a resolvê-la por `sys.modules.get(cls.__module__)`.
    Quando o recarregador do servidor tira o módulo de `sys.modules` no momento
    errado, esse `get` devolve None e a criação da classe estoura com
    AttributeError — foi o que derrubou o app no Python 3.14 do Streamlit Cloud.

    As anotações do projeto (`str | None`, `tuple[str, ...]`) são válidas
    nativamente desde o Python 3.10, então o import adiado não faz falta.
    """
    raiz = Path(__file__).resolve().parent.parent / "auditoria"
    culpados = [
        arquivo.relative_to(raiz.parent).as_posix()
        for arquivo in sorted(raiz.rglob("*.py"))
        if "@dataclass" in (texto := arquivo.read_text(encoding="utf-8"))
        and "from __future__ import annotations" in texto
    ]
    assert culpados == [], (
        "estes módulos definem dataclass com anotações adiadas: " + ", ".join(culpados)
    )


# ---------------------------------------------------------------------------
# Contabilidade de consumo diário
# ---------------------------------------------------------------------------

def test_consumo_soma_execucoes_do_mesmo_dia():
    from auditoria.consumo import Consumo

    c = Consumo(dia="2026-08-25")
    c.registrar(7_000, 1, 3, hoje=date(2026, 8, 25))
    c.registrar(14_000, 2, 6, hoje=date(2026, 8, 25))
    assert (c.tokens, c.imagens, c.chamadas) == (21_000, 3, 9)
    assert c.media_por_imagem == 7_000


def test_consumo_zera_na_virada_do_dia():
    """A regra que ninguém percebe estar quebrada até a meia-noite."""
    from auditoria.consumo import Consumo

    c = Consumo(dia="2026-08-25")
    c.registrar(150_000, 20, 60, hoje=date(2026, 8, 25))
    c.registrar(7_000, 1, 3, hoje=date(2026, 8, 26))
    assert c.dia == "2026-08-26"
    assert (c.tokens, c.imagens) == (7_000, 1)


def test_consumo_projeta_quantas_imagens_ainda_cabem():
    from auditoria.consumo import Consumo, ORCAMENTO_GRATUITO

    c = Consumo(dia="2026-08-25")
    c.registrar(70_000, 10, 30, hoje=date(2026, 8, 25))
    assert c.media_por_imagem == 7_000
    assert c.imagens_que_ainda_cabem(ORCAMENTO_GRATUITO) == 18   # 130.000 / 7.000
    assert 0.34 < c.fracao_usada(ORCAMENTO_GRATUITO) < 0.36


def test_consumo_nao_estima_sem_medicao():
    """Sem imagem medida, devolver um número seria devolver um palpite."""
    from auditoria.consumo import Consumo

    assert Consumo().imagens_que_ainda_cabem(200_000) is None


def test_consumo_conta_o_teto_por_modelo_e_nao_da_conta_somada():
    """Confirmado no console da Groq: cada modelo tem seu próprio balde diário
    de 200.000 tokens. Somando os três num só, o app dizia que cabiam 28
    imagens quando cabiam mais de 40 — mandava parar de auditar com cota
    sobrando, e a cota é o recurso escasso de um lote de 100 fotos."""
    from auditoria.consumo import Consumo, ORCAMENTO_GRATUITO

    # Uma foto custa ~7.100 tokens no rigor Padrão, repartidos assim.
    por_foto = {"qwen/qwen3.6-27b": 2_500, "openai/gpt-oss-120b": 4_600}
    c = Consumo(dia="2026-08-30")
    for _ in range(10):
        c.registrar(sum(por_foto.values()), 1, 3,
                    hoje=date(2026, 8, 30), por_modelo=por_foto)

    assert c.tokens == 71_000
    # Somando tudo num balde só: (200.000 − 71.000) / 7.100 = 18.
    assert c.restante(ORCAMENTO_GRATUITO) // c.media_por_imagem == 18
    # Por modelo, quem aperta é o 120b: (200.000 − 46.000) / 4.600 = 33.
    assert c.imagens_que_ainda_cabem(ORCAMENTO_GRATUITO) == 33
    assert c.modelo_mais_apertado(ORCAMENTO_GRATUITO) == ("openai/gpt-oss-120b", 33)


def test_consumo_aponta_o_modelo_que_vai_estourar_primeiro():
    """Não adianta sobrar cota no balde do Diretor se a do Olho acabou: toda
    foto passa pelos três, então quem manda é o mais apertado."""
    from auditoria.consumo import Consumo

    c = Consumo(dia="2026-08-30")
    c.registrar(30_000, 10, 30, hoje=date(2026, 8, 30), por_modelo={
        "visao": 25_000,      # 2.500/foto, restam 175.000 → 70 imagens
        "texto": 5_000,       # 500/foto, restam 195.000 → 390 imagens
    })
    assert c.modelo_mais_apertado(200_000) == ("visao", 70)
    assert c.imagens_que_ainda_cabem(200_000) == 70
    # A barra tem que refletir o balde mais cheio, não a média dos dois.
    assert c.fracao_usada(200_000) == 25_000 / 200_000


def test_consumo_sem_medicao_por_modelo_cai_no_calculo_antigo():
    """Errar para baixo aqui custa fotos que caberiam; errar para cima custa um
    lote interrompido no meio. Sem discriminação por modelo, vale o pessimista."""
    from auditoria.consumo import Consumo

    c = Consumo(dia="2026-08-30")
    c.registrar(70_000, 10, 30, hoje=date(2026, 8, 30))
    assert not c.por_modelo
    assert c.modelo_mais_apertado(200_000) is None
    assert c.imagens_que_ainda_cabem(200_000) == 18


def test_consumo_zera_os_baldes_por_modelo_na_virada_do_dia():
    from auditoria.consumo import Consumo

    c = Consumo(dia="2026-08-30")
    c.registrar(7_100, 1, 3, hoje=date(2026, 8, 30),
                por_modelo={"visao": 2_500, "texto": 4_600})
    c.registrar(7_100, 1, 3, hoje=date(2026, 8, 31),
                por_modelo={"visao": 2_500, "texto": 4_600})
    assert c.dia == "2026-08-31"
    assert c.por_modelo == {"visao": 2_500, "texto": 4_600}


def test_cliente_groq_discrimina_tokens_por_modelo():
    """O total sozinho não diz quando o lote para — é preciso saber qual balde
    está enchendo, porque o teto da Groq é de cada modelo."""
    from auditoria.modelos import (
        FRACAO_UTIL_DO_OTPM,
        OTPM_ORGANIZACAO,
        ClienteGroq,
        Cota,
    )

    class _Resposta:
        def __init__(self, tokens):
            self.usage = type("U", (), {"total_tokens": tokens})()
            self.choices = [type("C", (), {
                "finish_reason": "stop",
                "message": type("M", (), {"content": "{}"})(),
            })()]

    cliente = ClienteGroq.__new__(ClienteGroq)
    cliente.margem_tokens = 1500
    cliente.aviso = lambda _m: None
    cliente.cota = Cota()
    cliente.tokens_gastos = 0
    cliente.chamadas = 0
    cliente.tokens_por_modelo = {}
    cliente.sem_json_estrito = set()
    cliente.ultimo_corte_por_limite = False
    cliente.otpm = OTPM_ORGANIZACAO
    cliente.teto_saida_maximo = int(OTPM_ORGANIZACAO * FRACAO_UTIL_DO_OTPM)
    cliente._avisou_do_corte = False

    gastos = iter((2_500, 1_700, 1_500))
    cliente._chamar_com_degradacao = lambda _p: _Resposta(next(gastos))

    mensagens = [{"role": "user", "content": "oi"}]
    cliente.conversar("qwen/qwen3.6-27b", mensagens)
    cliente.conversar("openai/gpt-oss-120b", mensagens)
    cliente.conversar("openai/gpt-oss-120b", mensagens)

    assert cliente.tokens_gastos == 5_700
    assert cliente.chamadas == 3
    assert cliente.tokens_por_modelo == {
        "qwen/qwen3.6-27b": 2_500,
        "openai/gpt-oss-120b": 3_200,
    }


def test_consumo_usa_o_teto_de_cada_modelo_e_nao_um_numero_so():
    """O teto diário da Groq é de cada modelo, e eles não são iguais entre si.
    Com um número só, o painel manda parar de auditar com cota sobrando no
    balde certo. Os valores aqui são de teste — os reais estão no registro."""
    from auditoria.consumo import Consumo

    tetos = {"qwen/qwen3.8-27b": 2_000_000, "openai/gpt-oss-120b": 200_000}
    c = Consumo(dia="2026-08-30")
    c.registrar(20_000, 10, 30, hoje=date(2026, 8, 30), por_modelo={
        "qwen/qwen3.8-27b": 100_000,     # 10.000/foto, teto 2M → 190 imagens
        "openai/gpt-oss-120b": 100_000,  # 10.000/foto, teto 200k → 10 imagens
    })
    # Mesmo gasto nos dois; quem aperta é o de teto menor, não o de mais tokens.
    assert c.modelo_mais_apertado(200_000, tetos) == ("openai/gpt-oss-120b", 10)
    assert c.cabem_no_modelo("qwen/qwen3.8-27b", 200_000, tetos) == 190
    assert c.imagens_que_ainda_cabem(200_000, tetos) == 10
    # Sem os tetos por modelo, os dois pareceriam igualmente apertados.
    assert c.cabem_no_modelo("qwen/qwen3.8-27b", 200_000) == 10


def test_fracao_usada_compara_proporcao_e_nao_tokens_absolutos():
    """Com tetos diferentes, o modelo que gastou mais tokens pode ser o mais
    folgado — a barra tem que refletir a proporção."""
    from auditoria.consumo import Consumo

    tetos = {"grande": 2_000_000, "pequeno": 200_000}
    c = Consumo(dia="2026-08-30")
    c.registrar(300_000, 10, 30, hoje=date(2026, 8, 30),
                por_modelo={"grande": 200_000, "pequeno": 100_000})
    # "grande" gastou o dobro, mas usou 10% do teto contra 50% do "pequeno".
    assert c.fracao_usada(200_000, tetos) == 0.5


def test_modelo_fora_do_registro_cai_no_teto_padrao():
    """Sem saber o teto de um ID digitado à mão, o palpite conservador é o dos
    demais — nunca o do modelo mais generoso."""
    from auditoria.consumo import Consumo

    c = Consumo(dia="2026-08-30")
    c.registrar(50_000, 10, 30, hoje=date(2026, 8, 30), por_modelo={"digitado": 50_000})
    assert c.teto_do_modelo("digitado", 200_000, {"outro": 2_000_000}) == 200_000
    assert c.cabem_no_modelo("digitado", 200_000, {"outro": 2_000_000}) == 30


def test_registro_declara_o_teto_diario_de_cada_modelo():
    """Todos os quatro modelos registrados têm 200.000 tokens por dia.

    Por três sessões o registro deu 2.000.000 ao qwen3.8-27b, de uma leitura de
    30/08 do console, e o app anunciou ~256 fotos por dia sobre esse número — o
    console de 04/09 mostra 200.000 para ele na tabela da organização e no modal
    de limites do projeto. A conta real de um lote de 100 fotos é de dias, não
    de um dia."""
    from auditoria import modelos

    tetos = modelos.tetos_diarios()
    assert tetos["qwen/qwen3.8-27b"] == 200_000
    assert tetos["openai/gpt-oss-120b"] == 200_000
    assert "digitado-a-mao" not in tetos


def test_qwen38_registrado_com_as_protecoes_da_familia():
    """Rodou em produção sem registro, portanto sem `reasoning_effort: "none"` e
    sem a marca de JSON não confiável — as duas condicionais em `conversar`
    dependem de `por_id` devolver algo. Funcionou por sorte, não por desenho."""
    from auditoria.modelos import por_id

    m = por_id("qwen/qwen3.8-27b")
    assert m is not None
    assert m.visao, "precisa estar disponível como modelo de visão"
    assert m.raciocinio_desligavel
    assert not m.json_estrito_confiavel


def test_consumo_nao_ultrapassa_os_limites_do_orcamento():
    from auditoria.consumo import Consumo

    c = Consumo(dia="2026-08-25")
    c.registrar(250_000, 30, 90, hoje=date(2026, 8, 25))
    assert c.restante(200_000) == 0
    assert c.imagens_que_ainda_cabem(200_000) == 0
    assert c.fracao_usada(200_000) == 1.0


def test_titulo_da_tabela_nao_corta_palavra_ao_meio(base):
    """Corte cru deixava "…expondo partes internas d" num documento pericial."""
    from auditoria.pipeline import Laudo, NaoConformidade, Visao

    def nc(item, constatacao):
        return NaoConformidade(
            item=base.obter("NR-12", item), constatacao=constatacao, consequencia="",
            gravidade="alta", acao_corretiva="Corrigir.", prazo_dias=7,
            rotulo_risco="Partes energizadas expostas ao contato",
        )

    laudo = Laudo(
        visao=Visao(),
        nao_conformidades=[
            nc("12.3.8", "Botão de comando vermelho com a face frontal quebrada, "
                         "expondo partes internas do dispositivo de acionamento."),
            nc("12.5.16", "Abertura circular vazia na face frontal do painel elétrico, "
                          "sem componente instalado."),
        ],
        data_referencia=HOJE,
    )
    linhas = [l for l in relatorio.markdown(laudo, base, numero=1).splitlines()
              if l.startswith("| 1 |")]
    titulo = linhas[0].split("|")[2].strip()
    assert titulo.endswith("…"), titulo
    assert not titulo.rstrip("…").endswith(" "), "sobrou espaço antes das reticências"
    assert titulo.rstrip("…").split()[-1] in laudo.nao_conformidades[0].constatacao.split()


def test_texto_da_norma_nao_tem_palavra_partida_ao_meio(base):
    """O extrator partia "de" em "d e" dentro da citação oficial."""
    assert "sistema de seccionamento" in base.obter("NR-10", "10.2.8.2.1").texto
    assert "instalação" in base.obter("NR-18", "18.9.1.1").texto


# ---------------------------------------------------------------------------
# Coerência do laudo quando o supervisor veta
# ---------------------------------------------------------------------------

class _DubleQueVeta:
    """Analista propõe um enquadramento; Diretor veta e elogia o que vetou."""

    ultimo_corte_por_limite = False

    def __init__(self, parecer: str):
        self.parecer = parecer

    def conversar(self, modelo, mensagens, teto_saida=1200, temperatura=0.0,
                  json_estrito=False):
        import json as _json

        texto = " ".join(
            p.get("text", "")
            for m in mensagens
            for p in (m["content"] if isinstance(m["content"], list) else [{"text": m["content"]}])
        )
        if "perito em documentação fotográfica" in texto:
            return _json.dumps({
                "ambiente": "painel elétrico em setor industrial",
                "pessoas": {"presentes": False, "quantidade": 0},
                "achados": [{
                    "fato": "Botão de emergência solto sobre a tampa do painel, "
                            "fora da posição de fixação",
                    "onde": "topo do painel", "confianca": "alta",
                }],
            }, ensure_ascii=False)
        if "DOSSIÊ NORMATIVO" in texto:
            rotulo = re.search(r"\[(D\d+)\]", texto).group(1)
            return _json.dumps({
                "nao_conformidades": [{
                    "dossie": rotulo,
                    "constatacao": "Botão de emergência solto sobre a tampa do painel.",
                    "consequencia": "Impossibilidade de acionar a parada.",
                    "gravidade": "critica",
                    "acao_corretiva": "Refixar o botão.",
                    "prazo_dias": 3,
                }],
                "sem_enquadramento": [], "conformidades": [],
            }, ensure_ascii=False)
        return _json.dumps({
            "vetados": [{"ref": "V1", "motivo": "o item citado trata de outra situação"}],
            "ajustes": [],
            "parecer": self.parecer,
        }, ensure_ascii=False)


def test_parecer_nao_contradiz_um_laudo_sem_achados(base):
    """Observado em produção: "nenhuma não conformidade" ao lado de um parecer
    falando em "múltiplas não-conformidades" e "correções imediatas"."""
    laudo = executar(
        _DubleQueVeta("A foto evidencia múltiplas não-conformidades elétricas que "
                      "exigem correções imediatas."),
        base, "imagem", "painel elétrico",
        Configuracao(modelo_visao="demo", modelo_texto="demo", data_referencia=HOJE),
    )
    assert laudo.nao_conformidades == []
    assert "múltiplas não-conformidades" not in laudo.parecer_diretor
    texto = relatorio.markdown(laudo, base, numero=1)
    assert "não se sustentaram na supervisão" in texto
    assert "não atesta conformidade" in texto


def test_achado_vetado_nao_desaparece_do_laudo(base):
    """O veto derruba o enquadramento, não a observação: um botão de emergência
    solto continua sendo um problema mesmo com o item citado errado."""
    laudo = executar(
        _DubleQueVeta("Nenhum enquadramento se sustentou."),
        base, "imagem", "painel elétrico",
        Configuracao(modelo_visao="demo", modelo_texto="demo", data_referencia=HOJE),
    )
    juntos = " ".join(laudo.sem_enquadramento)
    assert "Botão de emergência solto" in juntos
    assert "recusado na supervisão" in juntos
    assert "Botão de emergência solto" in relatorio.markdown(laudo, base, numero=1)


# ---------------------------------------------------------------------------
# Sincronização do lote com os laudos já emitidos
# ---------------------------------------------------------------------------

def _resultado(nome):
    return (nome, "laudo", b"miniatura")


def test_foto_retirada_do_lote_leva_o_laudo_junto():
    from auditoria.lote import sincronizar

    mantidos, fora = sincronizar(
        [_resultado("a.jpg"), _resultado("b.jpg"), _resultado("c.jpg")],
        ["a.jpg", "b.jpg"],
    )
    assert [m[0] for m in mantidos] == ["a.jpg", "b.jpg"]
    assert fora == ["c.jpg"]


def test_lote_vazio_nao_apaga_o_trabalho_da_sessao():
    """O seletor pode devolver lista vazia por um instante durante a interação;
    perder o lote inteiro por causa disso sairia caro em cota e em tempo."""
    from auditoria.lote import sincronizar

    resultados = [_resultado("a.jpg"), _resultado("b.jpg")]
    mantidos, fora = sincronizar(resultados, [])
    assert mantidos == resultados and fora == []


def test_pendentes_preserva_a_ordem_de_envio():
    from auditoria.lote import pendentes

    class Arquivo:
        def __init__(self, name): self.name = name

    fila = [Arquivo("a.jpg"), Arquivo("b.jpg"), Arquivo("c.jpg")]
    assert [a.name for a in pendentes(fila, {"b.jpg"})] == ["a.jpg", "c.jpg"]
    assert pendentes(fila, {"a.jpg", "b.jpg", "c.jpg"}) == []


# ---------------------------------------------------------------------------
# Defeitos vistos no lote de 10 laudos reais de 26/08/2026
# ---------------------------------------------------------------------------

def test_limpeza_de_citacao_nao_deixa_preposicao_nem_cauda_de_subitem():
    """Três laudos reais saíram com "conforme." e "conforme.1/2." no texto.

    A citação do modelo era removida, mas a preposição que a introduzia ficava
    colada na pontuação — e a regex não alcançava a lista abreviada de subitens
    ("18.9.4.1/2"), deixando ".1/2." pendurado na ação corretiva.
    """
    from auditoria.pipeline import _limpar_citacoes

    sujos = [
        "Instalar fechamento provisório ou sistema de proteção conforme NR-18 18.9.4.1/2.",
        "Empilhar as madeiras em local adequado, conforme NR-18 18.16.4.1.",
        "Instalar cobertura resistente ou proteção contra quedas conforme NR-18 18.9.2.",
        "Conforme a NR‑18, a remoção deve ser feita por calha fechada.",
    ]
    for sujo in sujos:
        limpo = _limpar_citacoes(sujo)
        assert "NR" not in limpo, f"citação sobreviveu: {limpo}"
        assert not re.search(r"\bconforme\s*[.,;]", limpo, re.IGNORECASE), limpo
        assert ".1/2" not in limpo, limpo
        assert not limpo.startswith(("," , ".", ";")), limpo


def test_limpeza_de_citacao_preserva_texto_sem_citacao():
    """A limpeza só pode agir quando há citação: nada de mutilar prosa legítima."""
    from auditoria.pipeline import _limpar_citacoes

    intactos = [
        "A proteção deve ter altura mínima de 1,20 m, conforme o projeto aprovado.",
        "Substituir os cabos por novos condutores em conformidade.",
        "Remover o entulho utilizando equipamentos adequados ou calhas fechadas.",
    ]
    for texto in intactos:
        assert _limpar_citacoes(texto) == texto


def test_parecer_do_diretor_nao_carrega_citacao_escrita_pelo_modelo(base):
    """O parecer é a única prosa do laudo que escapava da limpeza.

    Laudos reais saíram com "conforme NR‑18" escrito pelo supervisor — quem cita
    neste projeto é o código, nunca um agente.
    """
    from auditoria.pipeline import agente_diretor  # noqa: F401  (contrato)
    from auditoria.pipeline import _limpar_citacoes

    parecer = ("O risco predominante é a abertura no piso, configurando risco "
               "crítico de queda conforme NR‑18. Recomenda-se cobertura.")
    assert "NR" not in _limpar_citacoes(parecer)


def test_prazo_nunca_excede_o_teto_da_gravidade(base):
    """Laudo real trouxe "🔴 Crítica" no sumário e "7 d" na tabela.

    O prazo proposto pelo modelo é aceito, mas a gravidade que ele mesmo
    atribuiu manda: crítica não sai com prazo de uma semana.
    """
    from auditoria.pipeline import PRAZO_SUGERIDO

    dossie = _dossie_de(base, ["NR-18 18.9.2"])
    proposta = _proposta("D1", gravidade="critica", prazo_dias=7)
    aprovadas, _ = aferir(proposta, dossie, {}, Visao(), HOJE)

    assert len(aprovadas) == 1
    assert aprovadas[0].prazo_dias <= PRAZO_SUGERIDO["critica"]


def test_prazo_mais_curto_que_o_teto_e_respeitado(base):
    """O teto limita para cima, não força para baixo."""
    dossie = _dossie_de(base, ["NR-18 18.9.2"])
    proposta = _proposta("D1", gravidade="media", prazo_dias=2)
    aprovadas, _ = aferir(proposta, dossie, {}, Visao(), HOJE)
    assert aprovadas[0].prazo_dias == 2


def test_busca_textual_nao_oferece_item_que_foto_nao_comprova(base):
    """O pior laudo do lote: fiação desencapada enquadrada no item que manda o
    inventário de riscos ocupacionais listar informações.

    O item existe e é real — mas nenhuma foto prova ou desmente um inventário.
    O analista é obrigado a escolher do dossiê; se o dossiê só oferece papel, o
    laudo sai com item verdadeiro na situação errada.
    """
    from auditoria import dossie as mod_dossie

    achados = [
        "Fios elétricos expostos e desencapados cruzando a frente das tubulações",
        "Cabo elétrico preto com isolamento danificado e fios internos visíveis",
        "Caixa de distribuição elétrica cinza com componentes internos expostos",
    ]
    montado = mod_dossie.montar(base, achados, quando=HOJE, teto=22)
    citados = {f"{e.item.nr} {e.item.item}" for e in montado.entradas}
    assert "NR-01 1.5.7.3.2" not in citados, "inventário de riscos voltou ao dossiê"
    for entrada in montado.entradas:
        assert mod_dossie.comprovavel_em_foto(entrada.item), \
            f"item documental no dossiê: {entrada.item.nr} {entrada.item.item}"


def test_filtro_documental_nao_alcanca_a_taxonomia_curada(base):
    """Alguns itens documentais estão na taxonomia de propósito — o quadro de
    avisos vazio da CIPA, a ficha de entrega de EPI. Um humano decidiu que a foto
    os evidencia; o filtro da busca textual não pode desfazer isso."""
    from auditoria import dossie as mod_dossie
    from auditoria.pipeline import montar_dossie

    curados = {ref for risco in catalogo_riscos().values() for ref in risco.itens}
    documentais = set()
    for ref in curados:
        nr, _, num = ref.partition(" ")
        item = base.obter(nr, num)
        if item is not None and not mod_dossie.comprovavel_em_foto(item):
            documentais.add(ref)

    assert documentais, "amostra vazia invalidaria o teste"

    visao = Visao(
        ambiente="área de vivência de canteiro",
        achados=[Achado("Quadro de avisos vazio, sem ata nem cartaz da CIPA afixado")],
    )
    dossie_final, _ = montar_dossie(base, visao, contexto="", quando=HOJE, teto=22)
    assert dossie_final.entradas, "o caminho curado não pode ser esvaziado pelo filtro"


def test_roteamento_reconhece_o_vocabulario_tecnico_do_agente_de_visao():
    """O Olho escreve "fios desencapados"; a taxonomia dizia só "fio pelado".

    A distância entre o registro técnico do modelo e o vocabulário de campo
    cadastrado fazia o risco elétrico não ser roteado em foto de fiação exposta.
    """
    visao = Visao(
        ambiente="setor de instalações prediais com infraestrutura elétrica aparente",
        achados=[
            Achado("Fios elétricos expostos e desencapados cruzando a frente das tubulações"),
            Achado("Cabo elétrico preto com isolamento danificado e fios internos visíveis"),
        ],
    )
    ids = [r.id for r in rotear_riscos(visao)]
    assert "partes_vivas_expostas" in ids


# ---------------------------------------------------------------------------
# Supervisão do laudo inteiro — o Diretor auditava só as não conformidades
# ---------------------------------------------------------------------------

def _conferencia_do_prompt(prompt: str) -> list[dict]:
    """Conferência que copia a exigência do TEXTO OFICIAL de cada bloco [V<n>].

    É o que o pipeline verifica antes de aceitar um enquadramento: sem trecho
    do item que a constatação descumpra, a NC vira veto. Um dublê que devolvesse
    conferência vazia veria tudo ser vetado — correto, mas inútil para testar
    outra coisa.
    """
    import re as _re

    return [
        {"ref": ref, "fato": FATO, "exigencia": " ".join(oficial.split()[:12]),
         "decisao": "aprovado"}
        for ref, oficial in _re.findall(
            r"\[(V\d+)\][^\n]*\n\s*TEXTO OFICIAL: ([^\n]+)", prompt
        )
    ]


class _DiretorQueDescarta(ClienteDemonstracao):
    """Supervisor que exerce os poderes novos: derruba P1 e C1."""

    def conversar(self, modelo, mensagens, teto_saida=1200, temperatura=0.0,
                  json_estrito=False):
        from auditoria.demo import _texto_do_prompt

        prompt = _texto_do_prompt(mensagens)
        if "Diretor Técnico" in prompt:
            self.prompt_visto = prompt
            import json as _json
            return _json.dumps({
                "conferencia": _conferencia_do_prompt(prompt),
                "vetados": [],
                "ajustes": [],
                "pontos_descartados": [{"ref": "P1", "motivo": "inventário da foto"}],
                "conformidades_descartadas": [{"ref": "C1", "motivo": "contradiz um achado"}],
                "parecer": "Risco predominante conforme V1 avaliado.",
            }, ensure_ascii=False)
        return super().conversar(modelo, mensagens, teto_saida, temperatura, json_estrito)


def test_diretor_recebe_pontos_de_atencao_e_conformidades(base):
    """Antes, as duas listas iam do Analista direto ao documento.

    Era onde sobreviviam o inventário da foto ("parede sem reboco") e a
    contradição de elogiar e criticar o mesmo objeto no mesmo laudo.
    """
    cliente = _DiretorQueDescarta()
    executar(
        cliente, base, "imagem-falsa", "",
        Configuracao(modelo_visao="demo", modelo_texto="demo", data_referencia=HOJE),
    )
    prompt = getattr(cliente, "prompt_visto", "")
    assert "PONTOS DE ATENÇÃO PROPOSTOS" in prompt
    assert "CONFORMIDADES PROPOSTAS" in prompt


def test_diretor_descarta_ponto_de_atencao_que_e_inventario_da_foto(base):
    antes = executar(
        ClienteDemonstracao(), base, "imagem-falsa", "",
        Configuracao(modelo_visao="demo", modelo_texto="demo", data_referencia=HOJE),
    )
    depois = executar(
        _DiretorQueDescarta(), base, "imagem-falsa", "",
        Configuracao(modelo_visao="demo", modelo_texto="demo", data_referencia=HOJE),
    )
    assert antes.sem_enquadramento, "o cenário precisa ter ponto de atenção para descartar"
    assert len(depois.sem_enquadramento) == len(antes.sem_enquadramento) - 1


def test_diretor_roda_mesmo_sem_nenhuma_nao_conformidade(base):
    """Laudos reais com zero enquadramentos e cinco pontos de atenção saíam sem
    passar por supervisor nenhum — e sem sequer uma seção de parecer."""
    class SemEnquadrar(ClienteDemonstracao):
        def conversar(self, modelo, mensagens, teto_saida=1200, temperatura=0.0,
                      json_estrito=False):
            from auditoria.demo import _texto_do_prompt
            import json as _json

            prompt = _texto_do_prompt(mensagens)
            if "DOSSIÊ NORMATIVO" in prompt:
                return _json.dumps({
                    "nao_conformidades": [],
                    "sem_enquadramento": ["Piso irregular a verificar no local"],
                    "conformidades": [],
                }, ensure_ascii=False)
            if "Diretor Técnico" in prompt:
                self.foi_chamado = True
                return _json.dumps({
                    "conferencia": [], "vetados": [], "ajustes": [],
                    "pontos_descartados": [], "conformidades_descartadas": [],
                    "parecer": "Nenhum enquadramento se caracterizou nesta imagem.",
                }, ensure_ascii=False)
            return super().conversar(modelo, mensagens, teto_saida, temperatura, json_estrito)

    cliente = SemEnquadrar()
    laudo = executar(
        cliente, base, "imagem-falsa", "",
        Configuracao(modelo_visao="demo", modelo_texto="demo", data_referencia=HOJE),
    )
    assert laudo.nao_conformidades == []
    assert getattr(cliente, "foi_chamado", False), "Diretor não foi chamado"
    assert laudo.parecer_diretor, "laudo sem não conformidade ficava sem parecer"


def test_parecer_nao_vaza_rotulo_interno_do_supervisor(base):
    """Laudo real saiu com "a má fixação dos cabos … (V1)" — V1 é andaime da
    conversa com o Diretor e não significa nada para quem lê o documento."""
    from auditoria.pipeline import _sem_rotulo_interno

    assert _sem_rotulo_interno("A má fixação dos cabos (V1) e o isolamento.") == \
        "A má fixação dos cabos e o isolamento."
    assert _sem_rotulo_interno("Risco na abertura [P2] do laudo.") == \
        "Risco na abertura do laudo."
    assert _sem_rotulo_interno("Sem rótulo aqui.") == "Sem rótulo aqui."


def test_limpeza_de_rotulo_nao_mutila_notacao_estrutural():
    """V1 é viga 1, P2 é pilar 2, C1 é coluna 1 em projeto estrutural brasileiro.

    Apagar o rótulo solto estragaria a frase de um engenheiro descrevendo a
    própria obra — a mesma armadilha de "carcaça" e "faca" na taxonomia.
    """
    from auditoria.pipeline import _sem_rotulo_interno

    for frase in (
        "Fissura no pilar P2 junto ao encontro com a viga V1.",
        "A coluna C1 apresenta ninho de concretagem.",
        "Escoramento retirado da V1 antes do prazo.",
    ):
        assert _sem_rotulo_interno(frase) == frase


# ---------------------------------------------------------------------------
# Sobriedade do documento
# ---------------------------------------------------------------------------

# Pictogramas, símbolos e emoji. O laudo pode chegar a um auditor fiscal do
# trabalho e é arquivado impresso, muitas vezes em preto e branco — onde bolinha
# colorida vira cinza indistinto e figurinha lê como protótipo.
RE_PICTOGRAMA = re.compile(
    "[\U0001F000-\U0001FAFF←-⇿⌀-➿⬀-⯿️]"
)


def test_laudo_nao_traz_pictograma(base, laudo_demo):
    md = relatorio.markdown(laudo_demo, base, numero=1)
    for renderizado in (md, relatorio.para_html(md)):
        achados = RE_PICTOGRAMA.findall(renderizado)
        assert not achados, f"pictograma no laudo: {achados[:5]}"


def test_sumario_consolidado_nao_traz_pictograma(base, laudo_demo):
    texto = relatorio.consolidado([("foto.jpg", laudo_demo)], base, HOJE)
    achados = RE_PICTOGRAMA.findall(texto)
    assert not achados, f"pictograma no sumário: {achados[:5]}"


def test_gravidade_sai_como_texto_e_nao_como_cor(base, laudo_demo):
    """A gravidade tem de sobreviver à impressão em preto e branco."""
    texto = relatorio.markdown(laudo_demo, base, numero=1)
    assert "Crítica" in texto or "Alta" in texto or "Média" in texto
    for chave, rotulo in relatorio.SELOS.items():
        assert isinstance(rotulo, str), f"{chave} devia ser texto puro, veio {rotulo!r}"


# ---------------------------------------------------------------------------
# Imagem que entrou no lote e não virou laudo não pode desaparecer do sumário
# ---------------------------------------------------------------------------

def test_sumario_declara_as_imagens_nao_auditadas(base, laudo_demo):
    """Foto que falhou tem de aparecer no documento, não sumir em silêncio.

    Um lote de 17 fotos com 3 falhas emitia um sumário dizendo "14 imagens
    analisadas", sem nenhuma menção às outras: quem lesse o laudo entenderia
    que as 14 eram o lote inteiro e que nas demais não havia achado.
    """
    texto = relatorio.consolidado(
        [("foto_1.jpg", laudo_demo)], base, HOJE,
        nao_auditadas=[("foto_2.jpg", "cota diária esgotada"),
                       ("foto_3.jpg", "falha de rede")],
    )
    assert "Imagens não auditadas" in texto
    assert "foto_2.jpg" in texto and "foto_3.jpg" in texto
    assert "cota diária esgotada" in texto
    assert "1 de 3 enviadas" in texto           # o cabeçalho não pode dizer só "1"
    assert "não significa ausência de risco" in texto


def test_sumario_sem_falhas_nao_inventa_secao(base, laudo_demo):
    texto = relatorio.consolidado([("foto_1.jpg", laudo_demo)], base, HOJE)
    assert "Imagens não auditadas" not in texto
    assert "**Imagens analisadas:** 1" in texto


def test_sincronizar_tira_da_lista_de_falhas_a_foto_removida():
    """A mesma regra dos laudos vale para as falhas: foto fora do lote, fora do sumário."""
    from auditoria.lote import sincronizar
    falhas = [("a.jpg", "erro"), ("b.jpg", "erro")]
    mantidas, descartadas = sincronizar(falhas, ["a.jpg"])
    assert mantidas == [("a.jpg", "erro")]
    assert descartadas == ["b.jpg"]


# ---------------------------------------------------------------------------
# Proteção coletiva: o Olho tem de qualificar a barreira, não nomeá-la
# ---------------------------------------------------------------------------

def test_prompt_do_olho_preserva_a_sentinela_do_duble():
    """O ClienteDemonstracao reconhece o Olho por esta frase.

    Se ela mudar, o dublê cai no ramo genérico, a visão volta vazia e o Modo
    Demonstração morre sem erro nenhum — some da tela, e nenhum teste de
    pipeline acusa. Vale um teste barato para travar.
    """
    from auditoria.pipeline import PROMPT_OLHO
    assert "perito em documentação fotográfica" in PROMPT_OLHO


def test_olho_e_proibido_de_afirmar_finalidade_que_nao_verifica():
    """A proibição de afirmar material sem verificar valia só para metade.

    "rede de proteção" para uma tela plástica de sinalização é o mesmo erro que
    "laje de concreto" para uma placa clara — o modelo nomeia o objeto pela
    função que supõe. Num lote real isso custou três falsos negativos de
    periferia em prédio alto.
    """
    from auditoria.pipeline import PROMPT_OLHO
    assert "material ou finalidade" in PROMPT_OLHO
    assert "rede de proteção" in PROMPT_OLHO       # o contraexemplo tem de estar lá


def test_barreira_so_roteia_periferia_quando_o_fato_traz_os_atributos(base):
    """O falso negativo mais caro do lote real, travado nos dois sentidos.

    Enquanto o fato diz "rede de proteção", o roteamento não tem como saber que
    a barreira é uma tela plástica frouxa: o dossiê sai com item genérico de
    NR-01 e o enquadramento correto de periferia nunca chega ao Analista.
    Descritos material, rigidez, fixação e altura, o item certo entra.
    """
    ambiente = ("Área de construção civil em fase de alvenaria, localizada em um "
                "edifício de grande altura com vista para uma cidade.")

    como_saiu = Visao(ambiente=ambiente, achados=[Achado(
        "Rede de proteção laranja de malha plástica estendida ao longo da borda "
        "do piso, fixada a uma estrutura vertical."
    )])
    assert "periferia_laje_sem_guarda_corpo" not in [r.id for r in rotear_riscos(como_saiu)]

    com_atributos = Visao(ambiente=ambiente, achados=[Achado(
        "Tela plástica flexível laranja de malha larga estendida ao longo da borda "
        "do piso, presa a um cone e a uma haste, altura na altura do joelho, sem "
        "guarda-corpo rigido visivel."
    )])
    assert "periferia_laje_sem_guarda_corpo" in [r.id for r in rotear_riscos(com_atributos)]

    from auditoria.pipeline import montar_dossie
    dossie_final, _ = montar_dossie(base, com_atributos, contexto="", quando=HOJE)
    refs = {f"{e.item.nr} {e.item.item}" for e in dossie_final.entradas}
    assert "NR-18 18.9.4" in refs, f"periferia sem o item de anteparo rígido: {refs}"


def test_painel_eletrico_e_quadro_eletrico_abrem_o_mesmo_dossie(base):
    """Uma palavra decidia entre laudo e nada.

    "quadro elétrico" roteava o risco e trazia sete itens; "painel elétrico" —
    o mesmo objeto, outro nome de campo — deixava o dossiê vazio, e o pipeline
    abortava depois de já ter pago a chamada da visão.
    """
    from auditoria.pipeline import montar_dossie

    def refs(palavra):
        visao = Visao(
            ambiente="Setor industrial com equipamentos elétricos instalados",
            achados=[Achado(f"{palavra} com orifício circular vazio sem tampa")],
        )
        dossie_final, _ = montar_dossie(base, visao, contexto="", quando=HOJE)
        return {f"{e.item.nr} {e.item.item}" for e in dossie_final.entradas}

    assert refs("Painel elétrico") == refs("Quadro elétrico") != set()


def test_painel_nao_eletrico_nao_vira_quadro_eletrico_aberto():
    """A armadilha de sempre: palavra de obra que colide com termo elétrico.

    Com o sinal escrito por extenso ("painel eletrico sem tampa"), a cobertura
    parcial do roteador dispensava justamente o radical discriminante, e um
    painel de fôrma de madeira sem tampa protetora virava quadro elétrico
    aberto — item verdadeiro, situação errada.
    """
    for ambiente, fato in (
        ("Fachada de edifício comercial concluído",
         "Painel de vidro temperado sem tampa de acabamento no montante"),
        ("Área de concretagem com formas montadas",
         "Painel de fôrma de madeira apoiado contra a parede, sem tampa protetora"),
    ):
        visao = Visao(ambiente=ambiente, achados=[Achado(fato)])
        ids = [r.id for r in rotear_riscos(visao)]
        assert "quadro_eletrico_aberto_ou_sem_sinalizacao" not in ids, f"{fato} -> {ids}"


def test_lista_de_conformidades_traz_a_ressalva_de_que_nao_e_atestado(base, laudo_demo):
    """A conformidade falsamente atestada foi o pior erro do lote real.

    Um laudo registrou "proteção coletiva contra quedas" para uma tela de
    sombreamento pregada numa ripa, na borda de laje de prédio alto. As regras
    de prompt reduzem a chance disso; a ressalva impressa é a parte que não
    depende de o modelo obedecer.
    """
    import dataclasses
    laudo = dataclasses.replace(
        laudo_demo,
        conformidades=["Barreira instalada na borda da laje, aparentemente contínua."],
    )
    md = relatorio.markdown(laudo, base, numero=1)
    assert "Conformidades observadas" in md
    assert "não é atestado de conformidade" in md.lower()
    # e a ressalva tem de sobreviver à renderização impressa
    assert "não é atestado de conformidade" in relatorio.para_html(md).lower()


# ---------------------------------------------------------------------------
# Veto que apara em vez de derrubar
#
# Cenário real do lote de 14 fotos: escada apoiada sobre entulho. O mesmo fato,
# dois itens diferentes do dossiê, duas respostas certas opostas — é isso que
# separa "aparar" de "vetar", e é por isso que o aparo não pode ser aplicado sem
# reconferir o texto oficial do item.
# ---------------------------------------------------------------------------

FATO = ("Escada portátil de alumínio com os montantes apoiados sobre entulho e sobras "
        "de material, base fora do nível")


class _Duble:
    """Olho vê a escada; Analista enquadra no item pedido; Diretor responde `veredito`."""

    ultimo_corte_por_limite = False

    def __init__(self, item_alvo: str, constatacao: str, veredito_fn):
        self.item_alvo, self.constatacao, self.veredito_fn = item_alvo, constatacao, veredito_fn
        self.prompt_diretor = ""

    def conversar(self, modelo, mensagens, teto_saida=1200, temperatura=0.0, json_estrito=False):
        p = _texto_do_prompt(mensagens)
        if "perito em documentação fotográfica" in p:
            return json.dumps({
                "ambiente": "canteiro de obra em pavimento em construção",
                "pessoas": {"presentes": False, "quantidade": 0},
                "achados": [{"fato": FATO, "onde": "centro", "confianca": "alta"}],
            }, ensure_ascii=False)
        if "DOSSIÊ NORMATIVO" in p:
            rotulo = dict(
                (num, rot) for rot, num in re.findall(r"\[(D\d+)\]\s+(NR-\d{2}(?: Anexo [IVX]+)? \S+)", p)
            )
            alvo = rotulo[self.item_alvo]
            return json.dumps({
                "nao_conformidades": [{
                    "dossie": alvo, "constatacao": self.constatacao,
                    "consequencia": "Queda do trabalhador por escorregamento da escada.",
                    "gravidade": "alta", "acao_corretiva":
                        "Instalar sapatas antiderrapantes e reposicionar a escada em piso firme.",
                    "prazo_dias": 7,
                }],
                "sem_enquadramento": [], "conformidades": [],
            }, ensure_ascii=False)
        self.prompt_diretor = p
        return json.dumps(self.veredito_fn(), ensure_ascii=False)


CONSTATACAO = ("A escada portátil está apoiada sobre entulho, com a base fora do nível, "
               "e não possui sapatas antiderrapantes.")


def _rodar(base, item_alvo, veredito_fn):
    duble = _Duble(item_alvo, CONSTATACAO, veredito_fn)
    laudo = executar(duble, base, "img", "",
                     Configuracao(modelo_visao="d", modelo_texto="d", data_referencia=HOJE))
    return laudo, duble


def test_aparo_salva_o_enquadramento_que_o_fato_sustenta(base):
    """NR-35 Anexo III 5.2.2.5 exige piso estável E sapata: cortada a cláusula da
    sapata, o que sobra ainda descumpre o item — vetar tudo zerava o laudo."""
    laudo, _ = _rodar(base, "NR-35 Anexo III 5.2.2.5", lambda: {
        "conferencia": [{"ref": "V1", "fato": FATO, "decisao": "aparado"}],
        "aparados": [{
            "ref": "V1",
            "constatacao": "A escada portátil está apoiada sobre entulho, com a base fora do nível.",
            "acao_corretiva": "Reposicionar a escada sobre piso estável e nivelado.",
            "gravidade": "alta",
            "retirado": "ausência de sapata antiderrapante, não observável no fato",
            "exigencia": "deve ser apoiada em piso estável",
        }],
        "vetados": [], "ajustes": [], "pontos_descartados": [],
        "conformidades_descartadas": [], "parecer": "Apoio instável da escada.",
    })
    assert len(laudo.nao_conformidades) == 1, "o achado evaporou"
    nc = laudo.nao_conformidades[0]
    assert nc.item.item == "Anexo III 5.2.2.5"
    assert "sapata" not in nc.constatacao.lower()
    assert "entulho" in nc.constatacao
    assert "sapata" not in nc.acao_corretiva.lower()
    assert laudo.aparos and "retirado" in laudo.aparos[0]
    md = relatorio.markdown(laudo, base, numero=1)
    assert "Aparada — NR-35 Anexo III 5.2.2.5" in md


def test_veto_continua_certo_quando_o_item_exigia_justamente_o_que_foi_cortado(base):
    """NR-18 18.8.6.12 trata SÓ de sapata antiderrapante: sem o fato da sapata,
    o que sobra não descumpre este item — aqui vetar é o certo."""
    laudo, _ = _rodar(base, "NR-18 18.8.6.12", lambda: {
        "conferencia": [{"ref": "V1", "fato": FATO, "decisao": "vetado"}],
        "aparados": [],
        "vetados": [{
            "ref": "V1",
            "motivo": "o fato não registra a base da escada; sem isso o item não se descumpre",
            "observacao": "Não é possível determinar pela imagem se a escada possui sapatas "
                          "antiderrapantes; verificar no local.",
        }],
        "ajustes": [], "pontos_descartados": [],
        "conformidades_descartadas": [], "parecer": "Nada se sustentou.",
    })
    assert laudo.nao_conformidades == []
    junto = " ".join(laudo.sem_enquadramento)
    assert "Não é possível determinar pela imagem" in junto
    assert "não possui sapatas antiderrapantes" not in junto, "afirmação vetada vazou"
    assert "recusado na supervisão" in junto


def test_prompt_do_diretor_traz_o_texto_oficial_para_decidir_o_aparo(base):
    _, duble = _rodar(base, "NR-35 Anexo III 5.2.2.5", lambda: {
        "conferencia": [], "aparados": [], "vetados": [], "ajustes": [],
        "pontos_descartados": [], "conformidades_descartadas": [], "parecer": "p",
    })
    assert "TEXTO OFICIAL" in duble.prompt_diretor
    assert "apoiada em piso estável" in duble.prompt_diretor


def test_retirado_nao_leva_o_raciocinio_do_modelo_para_o_laudo(base):
    """No lote de 01/09 o campo "retirado" — que sai impresso no laudo do
    cliente — veio com 674 caracteres de deliberação em primeira pessoa: "Vou
    manter a lógica de que…", "Vou usar 'alta' para ser conservador". O prompt
    pede uma frase; isto garante uma frase.
    """
    monologo = (
        "A afirmação de que a abertura está em desacordo com a exigência de proteção "
        "de aberturas em paredes, o que é interpretação e não fato. Na verdade, a "
        "principal razão do 'aparado' é outra. Vou manter a lógica de que a "
        "constatação original tinha suposições. Vou usar 'alta' para ser conservador."
    )
    laudo, _ = _rodar(base, "NR-35 Anexo III 5.2.2.5", lambda: {
        "conferencia": [{"ref": "V1", "fato": FATO, "decisao": "aparado"}],
        "aparados": [{
            "ref": "V1",
            "constatacao": "A escada portátil está apoiada sobre entulho, com a base fora do nível.",
            "acao_corretiva": "Reposicionar a escada sobre piso estável e nivelado.",
            "gravidade": "alta",
            "retirado": monologo,
            "exigencia": "deve ser apoiada em piso estável",
        }],
        "vetados": [], "ajustes": [], "pontos_descartados": [],
        "conformidades_descartadas": [], "parecer": "p",
    })
    trilha = " ".join(laudo.aparos)
    assert "Vou manter" not in trilha and "Vou usar" not in trilha
    assert "Na verdade" not in trilha
    assert "em desacordo com a exigência" in trilha, "cortou a resposta junto"


def test_enquadramento_aprovado_sem_exigencia_no_item_vira_veto(base):
    """O caso que escapou da primeira versão desta rede.

    O painel empoeirado foi enquadrado em NR-10 10.10.1 — item de SINALIZAÇÃO,
    com a etiqueta "PERIGO" legível na própria foto. Na primeira rodada o
    Diretor APAROU e a rede pegou. Na rodada seguinte ele APROVOU direto, sem
    aparo nenhum, e a não conformidade falsa foi impressa: a verificação só
    olhava aparos. O mesmo laudo saiu se contradizendo — acusava a sinalização
    de comprometida e a listava em "conformidades observadas".

    A exigência agora é cobrada de todo enquadramento que sobrevive, aprovado
    ou aparado.
    """
    laudo, _ = _rodar(base, "NR-35 Anexo III 5.2.2.5", lambda: {
        "conferencia": [{
            "ref": "V1", "fato": FATO, "decisao": "aprovado",
            # Exigência que NÃO existe no texto oficial do item.
            "exigencia": "os degraus devem ser mantidos limpos e desobstruídos",
        }],
        "aparados": [], "vetados": [], "ajustes": [], "pontos_descartados": [],
        "conformidades_descartadas": [], "parecer": "p",
    })
    assert not laudo.nao_conformidades, "a NC aprovada sem lastro no item sobreviveu"
    assert laudo.sem_enquadramento, "o achado evaporou em vez de virar observação"


def test_conferencia_omitida_nao_vira_afirmacao_de_que_a_norma_nao_foi_descumprida(base):
    """O laudo 15 do lote de 08/09, e a frase que ele imprimiu ao cliente.

    `19 PAV. POÇO GRUA SEM PROTEÇÃO` — poço sem proteção de piso NEM de parede,
    confirmado pelo engenheiro na foto — saiu com ZERO não conformidade e com
    "a constatação não descumpre o texto oficial deste item" impresso no laudo.

    O Diretor não tinha refutado nada: ele aprovou o enquadramento e deixou o
    campo `exigencia` vazio. Prova de que foi omissão e não juízo: o ponto de
    atenção saiu com o texto da CONSTATAÇÃO, que é o fallback de
    `observacoes.get(ref) or nc.constatacao` — ou seja, ele também não escreveu
    `observacao`. Nos dois campos que devia preencher não veio nada.

    O enquadramento continua caindo, e isso é deliberado: sem conferência não
    há como sustentá-lo, e reabrir a porta devolveria ao laudo o painel
    empoeirado em item de sinalização. O que não pode é o documento AFIRMAR ao
    engenheiro que a situação não descumpre a norma quando ninguém verificou.
    """
    from auditoria.pipeline import MOTIVO_CONFERENCIA_OMITIDA, MOTIVO_EXIGENCIA_NAO_ANCORA

    laudo, _ = _rodar(base, "NR-35 Anexo III 5.2.2.5", lambda: {
        "conferencia": [{"ref": "V1", "fato": FATO, "decisao": "aprovado",
                         "exigencia": ""}],
        "aparados": [], "vetados": [], "ajustes": [], "pontos_descartados": [],
        "conformidades_descartadas": [], "parecer": "p",
    })
    assert not laudo.nao_conformidades, "sem conferência o enquadramento tem de cair"
    assert laudo.sem_enquadramento, "o achado evaporou em vez de virar observação"
    trilha = " ".join(laudo.vetos)
    assert MOTIVO_CONFERENCIA_OMITIDA in trilha
    assert MOTIVO_EXIGENCIA_NAO_ANCORA not in trilha, (
        "o laudo está afirmando que a norma não foi descumprida, e ninguém conferiu"
    )
    assert laudo.conferencia_omitida == ["NR-35 Anexo III 5.2.2.5"]


def test_exigencia_que_nao_ancora_continua_sendo_refutacao(base):
    """A contraparte, e a razão de a separação não ser cosmética.

    Quando o trecho VEIO e não está no item, a afirmação é verdadeira e é o
    objetivo da rede: o painel empoeirado enquadrado em item de sinalização foi
    refutado de fato. Este teste impede que o conserto do caso omisso dilua o
    caso que a rede existe para pegar — os dois chegam a
    `_exigencia_ancorada` falso e só aqui se separam.
    """
    from auditoria.pipeline import MOTIVO_CONFERENCIA_OMITIDA, MOTIVO_EXIGENCIA_NAO_ANCORA

    laudo, _ = _rodar(base, "NR-35 Anexo III 5.2.2.5", lambda: {
        "conferencia": [{"ref": "V1", "fato": FATO, "decisao": "aprovado",
                         "exigencia": "os degraus devem ser mantidos limpos e desobstruídos"}],
        "aparados": [], "vetados": [], "ajustes": [], "pontos_descartados": [],
        "conformidades_descartadas": [], "parecer": "p",
    })
    assert not laudo.nao_conformidades
    trilha = " ".join(laudo.vetos)
    assert MOTIVO_EXIGENCIA_NAO_ANCORA in trilha
    assert MOTIVO_CONFERENCIA_OMITIDA not in trilha
    assert laudo.conferencia_omitida == [], "refutação não é omissão de supervisão"


def test_o_piso_da_exigencia_e_o_mesmo_nas_duas_funcoes(base):
    """`_exigencia_omitida` e `_exigencia_ancorada` precisam concordar sobre o
    que é "trecho curto demais", senão abre uma faixa em que o enquadramento
    cai por não ancorar e o motivo diz refutação, que é a mentira original.
    """
    from auditoria.pipeline import (
        MINIMO_EXIGENCIA, _exigencia_ancorada, _exigencia_omitida,
    )

    item = base.obter("NR-35", "Anexo III 5.2.2.5")
    assert _exigencia_omitida("")
    assert _exigencia_omitida("   ")
    # Exatamente no piso: deixa de ser omissão e passa a ser avaliado.
    curto = "a" * (MINIMO_EXIGENCIA - 1)
    assert _exigencia_omitida(curto)
    assert not _exigencia_omitida("a" * MINIMO_EXIGENCIA)
    # E nenhum trecho abaixo do piso escapa como se tivesse ancorado.
    assert not _exigencia_ancorada(curto, item)


def test_a_trilha_do_laudo_distingue_supervisao_incompleta(base):
    """O motivo separado só serve se chegar ao papel: é no laudo do cliente que
    a frase errada foi impressa, não no log.
    """
    from auditoria import relatorio

    laudo, _ = _rodar(base, "NR-35 Anexo III 5.2.2.5", lambda: {
        "conferencia": [{"ref": "V1", "fato": FATO, "decisao": "aprovado",
                         "exigencia": ""}],
        "aparados": [], "vetados": [], "ajustes": [], "pontos_descartados": [],
        "conformidades_descartadas": [], "parecer": "p",
    })
    md = relatorio.markdown(laudo, base, 1, "foto.jpg")
    assert "Supervisão incompleta" in md
    assert "não por terem sido refutados" in md
    assert "NR-35 Anexo III 5.2.2.5" in md


def test_enquadramento_aprovado_com_exigencia_do_item_sobrevive(base):
    """A contraparte: aprovado com trecho real do item continua no laudo."""
    laudo, _ = _rodar(base, "NR-35 Anexo III 5.2.2.5", lambda: {
        "conferencia": [{
            "ref": "V1", "fato": FATO, "decisao": "aprovado",
            "exigencia": "deve ser apoiada em piso estável",
        }],
        "aparados": [], "vetados": [], "ajustes": [], "pontos_descartados": [],
        "conformidades_descartadas": [], "parecer": "p",
    })
    assert len(laudo.nao_conformidades) == 1, "vetou um enquadramento legítimo"


def test_aparo_sem_exigencia_no_texto_oficial_vira_veto(base):
    """O caso do lote de 01/09: painel empoeirado enquadrado em item de
    SINALIZAÇÃO. O aparo tirou a parte da sinalização — a foto mostrava a placa
    'PERIGO' legível — e deixou só a poeira, que NR-10 10.10.1 não exige em
    lugar nenhum. Era veto, e o aparo o salvou.

    Aqui o Diretor apara sem conseguir copiar do texto oficial nada que a
    versão aparada descumpra; o pipeline converte em veto.
    """
    laudo, _ = _rodar(base, "NR-35 Anexo III 5.2.2.5", lambda: {
        "conferencia": [{"ref": "V1", "fato": FATO, "decisao": "aparado"}],
        "aparados": [{
            "ref": "V1",
            "constatacao": "A escada apresenta acúmulo de poeira nos degraus.",
            "acao_corretiva": "Realizar a limpeza dos degraus.",
            "gravidade": "baixa",
            "retirado": "apoio instável",
            # Exigência que NÃO está no texto oficial do item.
            "exigencia": "os degraus devem ser mantidos limpos e desobstruídos",
        }],
        "vetados": [], "ajustes": [], "pontos_descartados": [],
        "conformidades_descartadas": [], "parecer": "p",
    })
    assert not laudo.nao_conformidades, "o aparo sem lastro no item sobreviveu"
    # Classe de erro 5: o veto derruba o enquadramento, não a observação — e a
    # observação que sobrevive é a do Analista, não a versão aparada, porque foi
    # justamente o aparo que se rejeitou.
    assert laudo.sem_enquadramento
    observacao = " ".join(laudo.sem_enquadramento).lower()
    assert "entulho" in observacao
    assert "recusado na supervisão" in observacao


def test_aparo_com_exigencia_recopiada_sem_acento_continua_valendo(base):
    """O modelo recopia o texto, não o clona — acento e caixa não podem vetar
    um aparo legítimo."""
    laudo, _ = _rodar(base, "NR-35 Anexo III 5.2.2.5", lambda: {
        "conferencia": [{"ref": "V1", "fato": FATO, "decisao": "aparado"}],
        "aparados": [{
            "ref": "V1",
            "constatacao": "A escada portátil está apoiada sobre entulho, com a base fora do nível.",
            "acao_corretiva": "Reposicionar a escada sobre piso estável e nivelado.",
            "gravidade": "alta",
            "retirado": "ausência de sapata antiderrapante",
            "exigencia": "DEVE SER APOIADA EM PISO ESTAVEL",
        }],
        "vetados": [], "ajustes": [], "pontos_descartados": [],
        "conformidades_descartadas": [], "parecer": "p",
    })
    assert len(laudo.nao_conformidades) == 1, "o aparo legítimo foi vetado"


def test_aparo_nao_deixa_o_modelo_escrever_citacao(base):
    laudo, _ = _rodar(base, "NR-35 Anexo III 5.2.2.5", lambda: {
        "conferencia": [], "aparados": [{
            "ref": "V1",
            "constatacao": "Escada apoiada sobre entulho, em desacordo com a NR-35, item 5.2.2.5.",
            "acao_corretiva": "Reposicionar conforme NR-18 18.8.6.12.",
            "retirado": "cláusula da NR-18 18.8.6.12 sobre sapatas",
            "exigencia": "deve ser apoiada em piso estável",
        }], "vetados": [], "ajustes": [], "pontos_descartados": [],
        "conformidades_descartadas": [], "parecer": "p",
    })
    nc = laudo.nao_conformidades[0]
    assert "NR-35" not in nc.constatacao and "5.2.2.5" not in nc.constatacao
    assert "NR-18" not in nc.acao_corretiva and "18.8.6.12" not in nc.acao_corretiva
    assert "18.8.6.12" not in " ".join(laudo.aparos)
    md = relatorio.markdown(laudo, base, numero=1)
    assert "NR-35, item Anexo III 5.2.2.5" not in md.replace("`", "")  # citação inventada
    assert "`Anexo III 5.2.2.5`" in md  # a citação do código continua lá


def test_gravidade_reescrita_nunca_deixa_prazo_incoerente(base):
    """Ajuste que SOBE a gravidade deixava 'crítica' com prazo de 7 dias."""
    laudo, _ = _rodar(base, "NR-35 Anexo III 5.2.2.5", lambda: {
        "conferencia": [{"ref": "V1", "fato": FATO, "exigencia": "deve ser apoiada em piso estável", "decisao": "aprovado"}], "aparados": [],
        "vetados": [], "ajustes": [{"ref": "V1", "gravidade": "critica"}],
        "pontos_descartados": [], "conformidades_descartadas": [], "parecer": "p",
    })
    nc = laudo.nao_conformidades[0]
    assert nc.gravidade == "critica"
    assert nc.prazo_dias == 1, f"crítica com prazo de {nc.prazo_dias} dias"


def test_escada_com_apoio_instavel_roteia_sem_depender_do_fraseado():
    """O que a foto mostra da escada é o apoio, não a sapata.

    Os sinais cadastrados descreviam a escada pelo defeito da própria escada
    ("bamba", "sem sapata", "degrau quebrado"). O apoio instável — que é o
    fato observável, e o que sobra depois de o supervisor aparar a cláusula da
    sapata — dependia de a frase cair perto de "escada apoiada solta na parede".
    """
    for fato in (
        "Escada portatil com a base assentada sobre entulho solto",
        "Base da escada desnivelada sobre restos de tijolo",
    ):
        visao = Visao(ambiente="Interior de edificação em construção",
                      achados=[Achado(fato)])
        assert "escada_mao_irregular" in [r.id for r in rotear_riscos(visao)], fato


def test_escada_fixa_de_concreto_nao_vira_escada_de_mao():
    """Contraparte obrigatória: escada fixa não é escada de mão.

    Com o sinal escrito por extenso ("escada apoiada em piso irregular"), a
    cobertura parcial dispensava justamente "apoiada", e uma escada fixa de
    concreto num piso desgastado disparava o risco de escada portátil.
    """
    visao = Visao(
        ambiente="Edifício concluído",
        achados=[Achado("Escada fixa de concreto com corrimao, piso irregular por desgaste")],
    )
    assert "escada_mao_irregular" not in [r.id for r in rotear_riscos(visao)]


# ---------------------------------------------------------------------------
# Citação verbatim: nada do documento pode vazar para dentro do item
#
# Um laudo real citou a NR-35 Anexo II 1.1 e imprimiu o cabeçalho da seção
# seguinte colado no fim: "…no trabalho em altura. 2. Campo de Aplicação".
# ---------------------------------------------------------------------------

RE_CAUDA_DE_CABECALHO = re.compile(
    r"(?<=[.;:!?\)])\s+(\d{1,2}(?:\.\d{1,3})*)\.?\s+([^.;:]{3,70})$"
)

# O que o acervo atual ainda não resolve: anexos cuja numeração de seção pula um
# número, de modo que o encadeamento se perde. Nenhum deles é de construção
# civil. A lista é fechada de propósito — um item novo aqui é regressão.
CAUDA_TOLERADA = {"NR-07 Anexo III 1.1.1", "NR-11 Anexo I 6"}


def test_citacao_nao_arrasta_o_cabecalho_da_secao_seguinte(base):
    item = base.obter("NR-35", "Anexo II 1.1")
    assert item is not None
    assert item.texto.endswith("no trabalho em altura.")
    assert "Campo de Aplicação" not in item.texto

    sujos = {
        i.id
        for i in base.itens.values()
        if (m := RE_CAUDA_DE_CABECALHO.search(i.texto))
        and m.group(2).strip()[:1].isupper()
    }
    assert sujos <= CAUDA_TOLERADA, sorted(sujos - CAUDA_TOLERADA)


def test_cabecalho_de_secao_de_anexo_fecha_o_item_anterior():
    """Dentro do anexo a seção tem um nível só e RE_ITEM exige dois."""
    bruto = "\n".join([
        "ANEXO II",
        "SISTEMAS DE ANCORAGEM",
        "",
        "1. Objetivo",
        "",
        "1.1 Estabelecer os requisitos e as medidas de prevenção para o emprego de",
        "sistemas de ancoragem, no trabalho em altura.",
        "",
        "2. Campo de Aplicação",
        "",
        "2.1 Este Anexo se aplica ao sistema de ancoragem instalado na estrutura.",
    ])
    itens = {i.item: i.texto for i in kb_build.parsear_norma("NR-35", bruto, "teste.pdf")}
    assert itens["Anexo II 1.1"].endswith("no trabalho em altura.")
    assert "Campo de Aplicação" not in itens["Anexo II 1.1"]
    assert itens["Anexo II 2"] == "Campo de Aplicação"


def test_linha_numerada_fora_de_sequencia_nao_parte_o_item():
    """Legenda de figura e primeira linha de parágrafo têm a mesma forma que o
    cabeçalho; o que as separa é a inicial minúscula e o número fora de ordem."""
    bruto = "\n".join([
        "ANEXO X",
        "MÁQUINAS PARA CALÇADOS",
        "",
        "1. Balancim",
        "",
        "1.1 O balancim deve possuir dispositivo de acionamento bimanual, conforme",
        "a Figura 1 deste Anexo.",
        "Legenda:",
        "1. trava mecânica do prato giratório",
        "2. proteção fixa",
        "",
        "5. Máquina de cambrê",
    ])
    itens = {i.item: i.texto for i in kb_build.parsear_norma("NR-12", bruto, "teste.pdf")}
    assert "trava mecânica" in itens["Anexo X 1.1"], "legenda virou seção"
    assert "Anexo X 5" not in itens, "número fora de sequência abriu seção"


def test_subtitulo_sem_numero_nao_entra_na_citacao():
    """A NR-18 separa os itens com cabeçalhos sem número."""
    bruto = "\n".join([
        "18.8.6.12 As escadas portáteis devem possuir sapatas antiderrapantes ou",
        "dispositivo que impeça o seu escorregamento.",
        "Escada portátil de uso individual (de mão)",
        "",
        "18.8.6.13 As escadas de mão devem possuir, no máximo, 7 m de extensão.",
    ])
    itens = {i.item: i.texto for i in kb_build.parsear_norma("NR-18", bruto, "teste.pdf")}
    assert itens["18.8.6.12"].endswith("escorregamento.")
    assert "uso individual" not in itens["18.8.6.12"]


# ---------------------------------------------------------------------------
# Item que existe, está vigente e fala do assunto — mas não manda fazer nada
# ---------------------------------------------------------------------------

def test_item_que_so_enuncia_o_objetivo_nao_entra_no_dossie(base):
    """NR-35 Anexo II 1.1 é o objetivo do anexo, não regra prescritiva.

    O portão de emissão só confere existência e vigência, então ele aprovou; e
    o Analista, obrigado a escolher do dossiê, escolheu o que mais parecia
    falar de ancoragem.
    """
    objetivo = base.obter("NR-35", "Anexo II 1.1")
    assert base.titulo_da_secao(objetivo) == "Objetivo"
    assert not dossie.prescritivo(objetivo, base)

    d = dossie.montar(
        base,
        ["Sistema de ancoragem sem identificação, empregado como parte da "
         "proteção contra quedas no trabalho em altura"],
        contexto="trabalho em altura",
        quando=HOJE,
    )
    citados = [e.item.id for e in d.entradas]
    assert "NR-35 Anexo II 1.1" not in citados
    # O item recusado pontuava mais que o dobro do bom: peneirar só depois do
    # corte relativo esvaziaria o dossiê em vez de trocar o item.
    assert "NR-35 Anexo II 3.3" in citados, citados


def test_filtro_de_nao_prescritivo_nao_alcanca_a_taxonomia_curada(base):
    """Curadoria à mão manda mais que heurística: a NR-09 9.6.1 é disposição
    transitória e está mapeada de propósito."""
    refs = {ref for risco in catalogo_riscos().values() for ref in risco.itens}
    barrados = sorted(
        ref for ref in refs
        if not dossie.prescritivo(base.obter(*ref.split(" ", 1)), base)
    )
    assert barrados == [], barrados
    assert dossie.prescritivo(base.obter("NR-09", "9.6.1"), base)


def test_item_prescritivo_continua_no_dossie(base):
    """O filtro não pode cortar o comando normativo comum."""
    for nr, num in (("NR-18", "18.9.4.1"), ("NR-35", "Anexo III 5.2.2.5"),
                    ("NR-12", "12.5.16"), ("NR-06", "6.3.1")):
        item = base.obter(nr, num)
        assert item is not None, f"{nr} {num}"
        assert dossie.prescritivo(item, base), f"{nr} {num} barrado"


# ---------------------------------------------------------------------------
# Resposta cortada no teto: o Olho já refazia, o Analista e o Diretor não
# ---------------------------------------------------------------------------

class _ClienteQueCortaUmaVez:
    """Devolve JSON truncado na primeira chamada de cada agente, íntegro na segunda."""

    def __init__(self):
        self.ultimo_corte_por_limite = False
        self.tetos: list[int] = []
        self.vistos: set[str] = set()

    def conversar(self, modelo, mensagens, teto_saida=1200, temperatura=0.0, json_estrito=False):
        p = _texto_do_prompt(mensagens)
        self.tetos.append(teto_saida)
        quem = ("olho" if "perito em documentação fotográfica" in p
                else "analista" if "DOSSIÊ NORMATIVO" in p else "diretor")
        completo = ClienteDemonstracao().conversar(
            modelo, mensagens, teto_saida, temperatura, json_estrito
        )
        if quem in self.vistos:
            self.ultimo_corte_por_limite = False
            return completo
        self.vistos.add(quem)
        self.ultimo_corte_por_limite = True
        return completo[: len(completo) // 2]          # JSON cortado no meio


def test_analista_e_diretor_refazem_a_chamada_cortada_no_teto(base):
    """Três laudos de um lote real morreram com "não devolveu JSON utilizável".

    Não era JSON inválido: era JSON truncado. O veredito ficou mais longo quando
    ganhou o aparo, passou do teto de saída, e nem o Analista nem o Diretor
    tinham a segunda tentativa que o Olho já fazia desde que um laudo se perdeu
    do mesmo jeito. A foto já foi lida e cobrada — perdê-la aqui é o pior
    desfecho possível.
    """
    cliente = _ClienteQueCortaUmaVez()
    laudo = executar(
        cliente, base, "imagem-falsa", "",
        Configuracao(modelo_visao="d", modelo_texto="d", data_referencia=HOJE),
    )
    assert laudo.nao_conformidades, "o laudo se perdeu na resposta cortada"
    assert not laudo.visao_falhou
    # cada agente foi chamado duas vezes, a segunda com o dobro de espaço
    assert 3600 in cliente.tetos, cliente.tetos      # Analista 1800 → 3600
    assert 6000 in cliente.tetos, cliente.tetos      # Diretor 3000 → 6000


class _ClienteQueDevolveJsonInvalidoUmaVez:
    """Devolve texto não parseável na primeira chamada de cada agente, sem
    nunca sinalizar truncamento — simula aspas de citação não escapadas."""

    def __init__(self):
        self.ultimo_corte_por_limite = False
        self.vistos: set[str] = set()

    def conversar(self, modelo, mensagens, teto_saida=1200, temperatura=0.0, json_estrito=False):
        p = _texto_do_prompt(mensagens)
        quem = ("olho" if "perito em documentação fotográfica" in p
                else "analista" if "DOSSIÊ NORMATIVO" in p else "diretor")
        completo = ClienteDemonstracao().conversar(
            modelo, mensagens, teto_saida, temperatura, json_estrito
        )
        self.ultimo_corte_por_limite = False
        if quem == "olho" or quem in self.vistos:
            return completo
        self.vistos.add(quem)
        return '{"trecho": "citação com "aspas" soltas no meio", "resto": trunca aqui'


def test_analista_e_diretor_refazem_a_chamada_com_json_invalido_nao_sinalizado(base):
    """Um lote real perdeu três fotos de novo com "não devolveu JSON
    utilizável" mesmo depois do fix de resposta cortada — porque o JSON
    quebrado ali não vinha com o sinal de truncamento da API. Sem esse sinal,
    a chamada tem que refazer mesmo assim quando o parser falha."""
    cliente = _ClienteQueDevolveJsonInvalidoUmaVez()
    laudo = executar(
        cliente, base, "imagem-falsa", "",
        Configuracao(modelo_visao="d", modelo_texto="d", data_referencia=HOJE),
    )
    assert laudo.nao_conformidades, "o laudo se perdeu no JSON inválido não sinalizado"
    assert not laudo.visao_falhou


# ---------------------------------------------------------------------------
# O dossiê da `foto (59)`: 9 das 10 vagas eram obrigação de papel
# ---------------------------------------------------------------------------

# Reconstruída do laudo real de 02/09/2026 — o painel elétrico empoeirado que
# resistiu a três correções. Os fatos são os que o Olho registrou, copiados do
# HTML emitido em produção.
FATOS_PAINEL_59 = [
    "Painel elétrico de cor clara fixado em pilar de concreto, apresentando "
    "superfície com acúmulo de poeira e resíduos.",
    "Etiqueta de sinalização com o texto 'PERIGO' e 'ELETRICIDADE' colada na "
    "face frontal do painel.",
    "Botão de emergência vermelho montado em base amarela, posicionado na "
    "lateral direita do painel.",
    "Entrada de energia elétrica protegida por um tubo corrugado amarelo, "
    "conectando uma tomada branca ao painel.",
    "Interruptor de chave tipo 'chave de faca' com acabamento vermelho e "
    "verde, montado na face frontal do painel.",
    "Cabo elétrico preto saindo da parte inferior do painel, parcialmente "
    "envolvido por uma corda verde.",
    "Pilar de concreto com marcas de desgaste, manchas e uma faixa de fita "
    "adesiva azul na base.",
]
AMBIENTE_PAINEL_59 = (
    "Interior de um ambiente de trabalho industrial ou de construção, "
    "caracterizado por superfícies de concreto e presença de equipamentos "
    "elétricos."
)


def test_dossie_do_painel_empoeirado_nao_e_so_obrigacao_de_papel(base):
    """A `foto (59)` saiu com 0 NC porque a supervisão vetou o único
    enquadramento — mas a causa está antes, no dossiê: das 10 vagas, NOVE eram
    obrigação de papel (treinamento de eletricista, memorial descritivo do
    projeto, plano de emergência, ficha de dados de segurança de mistura
    química, metodologia da taxa metabólica da NR-09). Sobrava um item físico,
    `NR-10 10.10.1`, que exige SINALIZAÇÃO — e foi nele que a poeira foi
    enquadrada, com a etiqueta "PERIGO" legível na própria foto.

    Dossiê pobre força escolha ruim: é a classe de erro 1 na forma pura."""
    visao = Visao(
        ambiente=AMBIENTE_PAINEL_59,
        achados=[Achado(fato=f) for f in FATOS_PAINEL_59],
    )
    d, _ = montar_dossie(base, visao, "", HOJE)
    papel = [
        f"{e.item.nr} {e.item.item}"
        for e in d.entradas
        if not dossie.comprovavel_em_foto(e.item)
    ]
    assert not papel, f"obrigação de papel no dossiê da foto (59): {papel}"

    # E o dossiê tem de continuar oferecendo elétrica de verdade: sem itens de
    # proteção contra contato, 10.10.1 volta a ser a única escolha possível.
    eletricos = {e.item.item for e in d.entradas if e.item.nr == "NR-10"}
    assert len(eletricos) >= 3, sorted(eletricos)
    assert eletricos - {"10.10.1"}, "só sobrou o item de sinalização"


def test_foto_de_documento_nao_gera_dossie_nenhum(base):
    """Controle negativo: a foto de um POP impresso sobre a mesa não é achado
    de campo, e o dossiê tem de vir vazio. Antes vinham três itens — exercício
    simulado de emergência, canal de comunicação de dúvidas e cessão de uso do
    CA — todos obrigação que uma fotografia não comprova nem desmente, e o
    Analista é obrigado a escolher do dossiê."""
    d = dossie.montar(
        base,
        ["Folha de papel impressa com o título 'Procedimento Operacional "
         "Padrão' apoiada sobre uma mesa.",
         "Assinaturas manuscritas preenchidas em campos de uma lista."],
        quando=HOJE,
    )
    assert not d.entradas, [f"{e.item.nr} {e.item.item}" for e in d.entradas]


@pytest.mark.parametrize("nr,num", [
    # A contraparte do filtro: itens que falam de papel na superfície mas
    # descrevem coisa que a foto mostra. Barrá-los seria trocar erro de
    # enquadramento por buraco de cobertura.
    ("NR-35", "Anexo II 3.3"),        # "o dispositivo de ancoragem deve ser certificado"
    ("NR-17", "17.6.3"),              # "os planos de trabalho" é a bancada, não um documento
    ("NR-12", "12.12.7"),             # placa de identificação da máquina, em local visível
    ("NR-35", "Anexo III 5.2.2.2.1"), # marcação visível com dados do fabricante
    ("NR-18", "18.9.2"),              # fechamento de abertura no piso
    ("NR-10", "10.10.1"),             # sinalização de segurança na instalação elétrica
])
def test_filtro_documental_nao_alcanca_condicao_visivel(base, nr, num):
    item = base.obter(nr, num)
    assert item is not None, f"{nr} {num}"
    assert dossie.comprovavel_em_foto(item), item.texto[:160]


def test_filtro_documental_nao_alcanca_a_taxonomia_curada(base):
    """Mesma regra que já vale para `prescritivo`: item documental mapeado à
    mão (quadro de avisos da CIPA, ficha de entrega de EPI) é curadoria, e
    entra por `montar_dossie` sem passar pelo filtro."""
    visao = Visao(
        ambiente="Canteiro de obra",
        pessoas_presentes=True,
        achados=[Achado(fato="Trabalhador sobre a laje sem capacete de segurança.")],
    )
    d, origem = montar_dossie(base, visao, "", HOJE)
    curados = {e.item.id for e in d.entradas if e.origem}
    assert curados, "nenhum item curado chegou ao dossiê"


# ---------------------------------------------------------------------------
# Roteamento: plural curto e sinal que vira só palavra-cola
# ---------------------------------------------------------------------------

def test_plural_de_radical_curto_casa_com_o_singular():
    """"fios" tem 4 letras e a guarda de 5 o deixava intacto, enquanto "fio"
    chegava como "fio". O sinal "fio desencapado" foi cadastrado justamente
    porque o Olho escreve "fios desencapados" — e era esse o par que não
    casava."""
    from auditoria.kb import radical

    for plural, singular in (("fios", "fio"), ("vaos", "vao"), ("cabos", "cabo"),
                             ("materiais", "material"), ("pisos", "piso")):
        assert radical(plural) == radical(singular), (plural, singular)


def test_fios_desencapados_routeia_partes_vivas_expostas():
    """A frase é a que o Olho escreve num quadro de tomadas aberto. Sem o
    casamento do plural, o achado não routeava risco nenhum e o dossiê saía com
    um único item de NR-01 sobre divulgação de informações digitais."""
    visao = Visao(
        ambiente="Área interna do pavimento, parede de alvenaria",
        achados=[Achado(fato="Fios desencapados pendurados na parede junto ao quadro.")],
    )
    rotulos = [r.id for r in rotear_riscos(visao, "")]
    assert "partes_vivas_expostas" in rotulos, rotulos


def test_nenhum_sinal_vira_so_palavra_cola():
    """`"t em cima de t"` tem cinco palavras e quatro delas têm duas letras: o
    filtro de radicais as descarta e sobra `cima` sozinho, com cobertura 1.0 em
    "pregos expostos voltados para cima". A guarda vive no validador da
    taxonomia, então este teste falha no import — mas deixa o motivo escrito."""
    from auditoria.kb import radicais
    from auditoria.riscos import _radicais_cola

    cola = _radicais_cola()
    nus = [
        (chave, sinal)
        for chave, risco in catalogo_riscos().items()
        for sinal in risco.sinais
        if not (radicais(sinal) - cola)
    ]
    assert not nus, nus


def test_cinta_de_icamento_routeia_dispositivo_de_icamento():
    """O outro lado do defeito do lote de içamento: tirar o risco de EPI não
    bastava, porque a cinta ficava sem item curado nenhum e o `NR-06 6.9.3`
    continuava sendo o menos ruim do dossiê textual. Fatos verbatim do laudo 7
    de 02/09."""
    visao = Visao(
        ambiente="Piso de obra coberto por camada de pó e detritos de construção",
        achados=[
            Achado(fato="Cinta de içamento de tecido laranja com costuras visíveis, "
                        "apresentando sujidade escura e desgaste na superfície, está "
                        "amontoada e enrolada sobre o piso"),
            Achado(fato="Trecho de tecido da cinta com bordas desfiadas e material "
                        "solto, indicando desgaste estrutural"),
        ],
    )
    rotulos = [r.id for r in rotear_riscos(visao, "")]
    assert "dispositivo_icamento_deteriorado" in rotulos, rotulos


def test_dossie_da_cinta_traz_o_item_de_dispositivo_de_icamento(base):
    """`NR-18 18.10.1.27` é o item que exige do dispositivo auxiliar de içamento
    a marcação indelével com fabricante, capacidade de carga e rastreabilidade.
    Antes desta taxonomia ele nunca chegava ao dossiê: com o texto do Olho o
    BM25 devolve NR-12 Anexo XII (manutenção de linha de transmissão), e só o
    vocabulário jurídico o alcança."""
    visao = Visao(
        ambiente="Piso de obra coberto por camada de pó e detritos de construção",
        achados=[
            Achado(fato="Cinta de içamento de tecido laranja com costuras visíveis, "
                        "apresentando sujidade escura e desgaste na superfície, está "
                        "amontoada e enrolada sobre o piso"),
        ],
    )
    dossie, _ = montar_dossie(base, visao, "", date(2026, 9, 2))
    refs = [f"{e.item.nr} {e.item.item}" for e in dossie.entradas]
    assert "NR-18 18.10.1.27" in refs, refs
    assert "NR-11 11.1.3.1" in refs, refs


def test_cinturao_desgastado_nao_routeia_dispositivo_de_icamento():
    """A contraparte da colisão `cint`: o EPI de altura não pode entrar pelos
    riscos de içamento. O discriminante é `icament`/`tecid`, nunca `cint`."""
    visao = Visao(
        ambiente="Laje de cobertura de edifício em construção",
        pessoas_presentes=True,
        quantidade_pessoas=1,
        achados=[Achado(fato="Trabalhador com cinturao de seguranca apresentando "
                             "desgaste nas fitas")],
    )
    rotulos = [r.id for r in rotear_riscos(visao, "")]
    assert "dispositivo_icamento_deteriorado" not in rotulos, rotulos


def test_cacamba_suspensa_routeia_sem_pessoa_na_cena():
    """O fato é do laudo 1 do lote de 12, e foi ele que mediu o buraco: nenhum
    dos seis riscos de carga passava do corte. `carga_suspensa_sobre_trabalhadores`
    exige pessoa em todos os sinais, o que é certo para ele — a NR-18 18.10.1.21
    cobra o isolamento da ÁREA, não a presença de vítima, e por isso o risco novo
    não exige pessoa."""
    visao = Visao(
        ambiente="Área interna de pavimento em obra, com piso de concreto",
        achados=[Achado(fato="Estrutura metálica pintada de amarela, com formato de "
                             "funil ou caçamba, suspensa no alto do ambiente")],
    )
    rotulos = [r.id for r in rotear_riscos(visao, "")]
    assert "carga_suspensa_area_sem_isolamento" in rotulos, rotulos
    assert not catalogo_riscos()["carga_suspensa_area_sem_isolamento"].exige_pessoa


def test_plataforma_da_grua_com_guarda_corpo_nao_routeia_icamento():
    """Contraparte real, do laudo 2: o guarda-corpo da plataforma da grua está
    PRESENTE. Nenhum risco de içamento pode nascer de um fato que descreve a
    proteção existindo."""
    visao = Visao(
        ambiente="Estrutura metálica elevada de cor amarela, com cabine e "
                 "contrapesos, vista de baixo para cima contra o céu.",
        achados=[Achado(fato="Plataforma aberta com guarda-corpo metálico de tubos "
                             "finos e um poste vertical com uma luz vermelha no topo, "
                             "localizada acima da cabine.")],
    )
    rotulos = [r.id for r in rotear_riscos(visao, "")]
    novos = {"dispositivo_icamento_deteriorado", "carga_suspensa_area_sem_isolamento",
             "equipamento_guindar_sem_itens_seguranca"}
    assert not (set(rotulos) & novos), rotulos


def test_cinta_de_icamento_nao_routeia_risco_de_epi():
    """"cinto" e "cinta" caem no mesmo radical `cint`, e o sinal `"cinto solto"`
    tinha só dois radicais: o fato abaixo — copiado do laudo 7 do lote de
    içamento de 02/09 — cobria os dois e classificava o acessório de içamento
    como EPI. O laudo saiu enquadrando a cinta em NR-06 6.9.3, marcação de EPI,
    quando o item da cinta é NR-18 18.10.1.27 (dispositivo auxiliar de
    içamento)."""
    visao = Visao(
        ambiente="Piso de obra coberto por camada de pó e detritos de construção",
        achados=[
            Achado(fato="Cinta de içamento de tecido laranja com costuras visíveis, "
                        "apresentando sujidade escura e desgaste na superfície, está "
                        "amontoada e enrolada sobre o piso"),
            Achado(fato="Trecho de tecido da cinta com bordas desfiadas e material "
                        "solto, indicando desgaste estrutural"),
        ],
    )
    rotulos = [r.id for r in rotear_riscos(visao, "")]
    assert "epi_usado_de_forma_incorreta" not in rotulos, rotulos


def test_cinturao_solto_de_verdade_continua_routeando():
    """A contraparte: trocar "cinto" por "cinturao" não pode custar o achado que
    o sinal existe para pegar."""
    visao = Visao(
        ambiente="Laje de cobertura de edifício em construção",
        pessoas_presentes=True,
        quantidade_pessoas=1,
        achados=[Achado(fato="Trabalhador junto à borda com cinturao solto na "
                             "cintura, sem conexão a ponto de ancoragem")],
    )
    rotulos = [r.id for r in rotear_riscos(visao, "")]
    assert "epi_usado_de_forma_incorreta" in rotulos, rotulos


def test_grade_vermelha_no_piso_nao_routeia_risco_de_extintor():
    """`"piso sem faixa vermelha"` tem quatro radicais e um deles é `sem`, de
    cola: a cobertura parcial abre a 0,75 faltando `faix`, que é o único
    discriminante. O fato abaixo é o laudo 6 do lote de içamento — uma cancela
    de cremalheira que acionou risco de extintor e levou NR-26 e NR-23 para o
    dossiê."""
    visao = Visao(
        ambiente="Interior de edificação em fase de construção, com piso de "
                 "concreto aparente e estrutura de vigas exposta.",
        pessoas_presentes=True,
        quantidade_pessoas=1,
        achados=[Achado(fato="Grade metálica de malha quadrada com estrutura "
                             "tubular pintada de vermelho, aberta e apoiada no "
                             "piso, sem fechamento lateral visível.")],
    )
    rotulos = [r.id for r in rotear_riscos(visao, "")]
    assert "extintor_sem_sinalizacao" not in rotulos, rotulos


def test_extintor_sem_demarcacao_de_piso_continua_routeando():
    """A contraparte do encurtamento: a demarcação ausente ainda é achado."""
    visao = Visao(
        ambiente="Galpão de apoio da obra",
        achados=[Achado(fato="Extintor de pó químico pendurado na coluna, sem "
                             "faixa vermelha demarcada no piso à frente")],
    )
    rotulos = [r.id for r in rotear_riscos(visao, "")]
    assert "extintor_sem_sinalizacao" in rotulos, rotulos


def test_madeira_com_pregos_nao_routeia_gambiarra():
    """A contraparte do sinal removido: nada de elétrico nesta foto."""
    visao = Visao(
        ambiente="Pavimento em obra, área de desforma",
        achados=[Achado(fato="Peças de madeira de fôrma empilhadas no piso com "
                             "pregos expostos voltados para cima.")],
    )
    rotulos = [r.id for r in rotear_riscos(visao, "")]
    assert "ligacao_eletrica_improvisada" not in rotulos, rotulos
    assert rotulos == ["madeira_com_prego_exposto"], rotulos


# ---------------------------------------------------------------------------
# O padrão dos modelos é o 3.8 nos dois campos
# ---------------------------------------------------------------------------

def test_o_padrao_dos_dois_campos_e_o_modelo_medido_no_lote_de_15():
    """A ordem das listas em `modelos.py` define o padrão, e o 3.8 assumiu os
    dois postos depois da medição do lote de 15: 15/15 laudos contra 11/14, a
    7.804 tokens por foto contra 13.404. O usuário já o selecionava à mão; um
    clique esquecido custava um lote inteiro medido no modelo errado.

    O teto diário não entra nessa conta — os quatro modelos têm o mesmo."""
    from auditoria import modelos

    assert modelos.PADRAO_VISAO == "qwen/qwen3.8-27b"
    assert modelos.PADRAO_TEXTO == "qwen/qwen3.8-27b"
    assert len(set(modelos.tetos_diarios().values())) == 1


def test_o_mesmo_id_tem_rotulo_proprio_em_cada_lista():
    """`por_id` varria `VISAO + TEXTO` e devolvia o primeiro, então o campo de
    TEXTO rotulava o 3.8 como "(visão)" e imprimia a mesma legenda duas vezes.
    Ficou invisível enquanto os padrões eram modelos diferentes."""
    from auditoria import modelos

    visao = modelos.por_id("qwen/qwen3.8-27b", modelos.VISAO)
    texto = modelos.por_id("qwen/qwen3.8-27b", modelos.TEXTO)
    assert visao is not None and texto is not None
    assert visao.rotulo != texto.rotulo, visao.rotulo
    assert "(visão)" in visao.rotulo and "(visão)" not in texto.rotulo
    # Sem `entre`, o comportamento antigo continua — é o que os chamadores que
    # só querem o teto diário do ID usam.
    assert modelos.por_id("qwen/qwen3.8-27b") is visao


def test_o_padrao_de_visao_le_imagem_e_o_de_texto_esta_registrado():
    """Padrão de visão que não aceita imagem quebra o app na primeira foto."""
    from auditoria import modelos

    assert modelos.por_id(modelos.PADRAO_VISAO, modelos.VISAO).visao
    assert modelos.por_id(modelos.PADRAO_TEXTO, modelos.TEXTO) is not None


# ---------------------------------------------------------------------------
# Texto do modelo que saiu impresso quebrado no laudo do cliente (lote de 12)
# ---------------------------------------------------------------------------

def test_citacao_no_meio_da_frase_nao_deixa_preposicao_pendurada():
    """Parecer real do lote de 02/09, laudo 1: o Diretor escreveu "violando a
    NR-10 e a NR-26" e o laudo saiu com "…advertência de perigo, **violando a
    e.** Recomenda-se…". A limpeza de órfãs trata preposição encostada na
    pontuação ("conforme."), não no meio do trecho — e o que sobra ali é um
    verbo sem objeto, que nenhuma regra de pontuação conserta."""
    from auditoria.pipeline import _limpar_citacoes

    limpo = _limpar_citacoes(
        "O principal risco identificado é a ausência de sinalização de segurança "
        "no painel elétrico, o que impede a correta identificação de circuitos e "
        "a advertência de perigo, violando a NR-10 e a NR-26. Recomenda-se a "
        "instalação imediata da sinalização adequada."
    )
    assert "violando a e" not in limpo, limpo
    assert " a e." not in limpo, limpo
    # O que o fragmento descartado não levava junto: o resto da frase fica.
    assert "advertência de perigo" in limpo
    assert limpo.startswith("O principal risco") and "Recomenda-se" in limpo
    assert extrair_citacoes(limpo) == []


@pytest.mark.parametrize("escrito,esperado", [
    # Fragmento que só existia para apresentar a citação sai inteiro.
    ("violando a NR-10 10.10.1 e a NR-26 26.1.1. Recomenda-se a limpeza.",
     "Recomenda-se a limpeza."),
    ("Escada apoiada sobre entulho, em desacordo com a NR-35, item 5.2.2.5.",
     "Escada apoiada sobre entulho."),
    ("A escada está apoiada em piso irregular. Isso descumpre a NR-35 "
     "Anexo III 5.2.2.5. O risco é de queda.",
     "A escada está apoiada em piso irregular. O risco é de queda."),
    # Fragmento com conteúdo próprio fica; só a citação sai.
    ("A abertura no piso não tem fechamento, violando a NR-18 18.9.2, e expõe "
     "o trabalhador a queda.",
     "A abertura no piso não tem fechamento, e expõe o trabalhador a queda."),
    # A vírgula do número não é separador de fragmento.
    ("O guarda-corpo deve ter 1,20 m de altura conforme NR-18 18.9.4.1.",
     "O guarda-corpo deve ter 1,20 m de altura."),
    # Sem citação, nada acontece.
    ("Texto sem citação nenhuma, que deve passar intacto.",
     "Texto sem citação nenhuma, que deve passar intacto."),
    # "anexo" sem numeral romano é palavra comum, não citação.
    ("O documento anexo mostra a planta do pavimento.",
     "O documento anexo mostra a planta do pavimento."),
])
def test_limpeza_de_citacao_por_fragmento(escrito, esperado):
    from auditoria.pipeline import _limpar_citacoes

    assert _limpar_citacoes(escrito) == esperado


def test_citacao_de_anexo_escrita_a_mao_tambem_sai():
    """A regex exigia "NR-nn" para ancorar, então "NR-35 Anexo III 5.2.2.5"
    perdia a NR e mantinha "Anexo III 5.2.2.5" — o pior dos dois mundos, porque
    o renderizador relê o resto como citação legítima."""
    from auditoria.pipeline import _limpar_citacoes

    for escrito in ("Isso descumpre a NR-35 Anexo III 5.2.2.5.",
                    "Reposicionar conforme o Anexo III, item 5.2.2.5.",
                    "A cesta está fora do Anexo XII 4.18."):
        limpo = _limpar_citacoes(escrito)
        assert "Anexo" not in limpo and "5.2.2.5" not in limpo, limpo
        assert "4.18" not in limpo, limpo


def test_limpeza_que_esvazia_tudo_nao_devolve_a_citacao():
    """O fallback antigo devolvia o texto original quando a limpeza esvaziava —
    reintroduzindo justamente a citação que o modelo escreveu à mão, que é o que
    esta função existe para impedir."""
    from auditoria.pipeline import _limpar_citacoes

    assert _limpar_citacoes("violando a NR-10 e a NR-26.") == ""


def test_motivo_do_veto_nao_leva_a_argumentacao_para_o_laudo(base):
    """Laudo 12 do lote de 02/09: o motivo do veto saiu com 493 caracteres de
    argumentação dentro do ponto de atenção que vai ao cliente. O `retirado` do
    aparo ganhou esse corte no #13; o veto ficou de fora porque naquele momento
    só produzia motivo escrito pelo código. Mesma coisa, outra porta."""
    motivo = (
        "O item trata exclusivamente de sinalização de segurança (advertência e "
        "identificação). A constatação descreve uma falha de integridade "
        "física/vedação (abertura sem tampa), o que não é coberto por este item "
        "específico. Além disso, a alegação de que isso 'compromete a integridade "
        "da sinalização' é uma suposição, pois a etiqueta de sinalização está "
        "descrita como presente e legível em outro fato. Não há trecho no texto "
        "oficial que exija vedação física de aberturas sob a rubrica de sinalização"
    )
    laudo, _ = _rodar(base, "NR-18 18.8.6.12", lambda: {
        "conferencia": [], "aparados": [],
        "vetados": [{"ref": "V1", "motivo": motivo}],
        "ajustes": [], "pontos_descartados": [],
        "conformidades_descartadas": [], "parecer": "p",
    })
    assert not laudo.nao_conformidades
    inteiro = " ".join(laudo.vetos + laudo.sem_enquadramento)
    assert "Além disso" not in inteiro, inteiro
    assert "O item trata exclusivamente de sinalização" in inteiro
    assert len(laudo.vetos[0]) < 200, laudo.vetos[0]
    # E o achado não evapora: a observação continua indo para os pontos de
    # atenção, que é a razão de o veto não derrubar a informação junto.
    assert laudo.sem_enquadramento


# ---------------------------------------------------------------------------
# Cronômetro por foto
# ---------------------------------------------------------------------------

def test_laudo_registra_o_tempo_da_foto(base):
    """Um lote de 100 fotos esbarra na cota diária e no relógio (~45 s/foto
    medidos em produção). Sem número no app, planejar lote é chute."""
    laudo = executar(
        ClienteDemonstracao(), base, "imagem-falsa", "",
        Configuracao(modelo_visao="d", modelo_texto="d", data_referencia=HOJE),
    )
    assert laudo.duracao_s > 0
    # O dublê não dorme por cota, então a espera é zero — e não negativa.
    assert laudo.espera_s == 0


def test_o_tempo_e_medido_tambem_quando_a_visao_falha(base):
    """`executar` tem mais de uma saída: a foto sem fato utilizável volta antes
    do dossiê. É por isso que o cronômetro mora no pipeline e não no app."""
    class _SemFatos:
        ultimo_corte_por_limite = False

        def conversar(self, modelo, mensagens, teto_saida=1200, temperatura=0.0,
                      json_estrito=False):
            return '{"ambiente": "obra", "achados": [], "pessoas": {"presentes": false}}'

    laudo = executar(
        _SemFatos(), base, "imagem-falsa", "",
        Configuracao(modelo_visao="d", modelo_texto="d", data_referencia=HOJE),
    )
    assert laudo.visao_falhou
    assert laudo.duracao_s > 0


def test_a_espera_por_cota_entra_no_laudo_separada(base):
    """A espera pela janela de TPM não melhora com modelo mais rápido — só com
    tier pago. Somá-la ao tempo de chamada esconderia qual dos dois é o
    gargalo, que é justamente a pergunta."""
    class _QueDorme(ClienteDemonstracao):
        segundos_esperando = 0.0

        def conversar(self, *a, **k):
            self.segundos_esperando += 12.0     # sem dormir de verdade
            return super().conversar(*a, **k)

    laudo = executar(
        _QueDorme(), base, "imagem-falsa", "",
        Configuracao(modelo_visao="d", modelo_texto="d", data_referencia=HOJE),
    )
    assert laudo.espera_s >= 12.0
    assert laudo.espera_s <= laudo.duracao_s + 60   # é uma fatia, não um extra


def test_o_cliente_groq_conta_o_tempo_que_dormiu(monkeypatch):
    """O contador vive no cliente porque é lá que está o único `time.sleep`."""
    import auditoria.modelos as mod

    dormido = []
    monkeypatch.setattr(mod.time, "sleep", lambda s: dormido.append(s))
    cliente = mod.ClienteGroq.__new__(mod.ClienteGroq)
    cliente.margem_tokens = 1500
    cliente.aviso = lambda _m: None
    cliente.segundos_esperando = 0.0
    cliente.cota = mod.Cota(tokens_restantes=100, tokens_limite=8000, reset_tokens=20.0)

    cliente.aguardar_cota(5_000)
    assert dormido and cliente.segundos_esperando == dormido[0]
    # Cota folgada não dorme nem conta.
    cliente.cota = mod.Cota(tokens_restantes=8000, tokens_limite=8000)
    antes = cliente.segundos_esperando
    cliente.aguardar_cota(1_000)
    assert cliente.segundos_esperando == antes


# ---------------------------------------------------------------------------
# O OTPM: o limite que recusa a requisição pelo TAMANHO, antes de processá-la
# ---------------------------------------------------------------------------

def test_o_teto_de_saida_pedido_nunca_excede_o_otpm_da_conta(monkeypatch):
    """Onze fotos de doze foram recusadas em 04/09/2026 sem chegar ao modelo.

    Não era volume nem código: a organização passou a ter um teto de tokens de
    SAÍDA por minuto (OTPM) de 1.000, e o pipeline pedia 1.600, 1.800 e 3.000 —
    cada um sozinho maior que a janela inteira do minuto. A Groq recusa pelo
    tamanho declarado, com latência de 0,006 s, então nem a primeira foto do dia
    passava. O corte tem de acontecer aqui, no único ponto em que
    `max_completion_tokens` é montado.
    """
    import auditoria.modelos as mod

    enviados = []

    class _Resposta:
        usage = None
        choices = [type("C", (), {
            "finish_reason": "stop",
            "message": type("M", (), {"content": "{}"})(),
        })()]

    cliente = mod.ClienteGroq.__new__(mod.ClienteGroq)
    cliente.margem_tokens = 1500
    cliente.aviso = lambda _m: None
    cliente.cota = mod.Cota()
    cliente.tokens_gastos = 0
    cliente.chamadas = 0
    cliente.tokens_por_modelo = {}
    cliente.sem_json_estrito = set()
    cliente.ultimo_corte_por_limite = False
    cliente.otpm = 1_000
    cliente.teto_saida_maximo = int(1_000 * mod.FRACAO_UTIL_DO_OTPM)
    cliente._avisou_do_corte = False
    cliente._chamar_com_degradacao = lambda p: (
        enviados.append(p["max_completion_tokens"]) or _Resposta()
    )

    for pedido in (1_600, 1_800, 3_000, 6_000):
        cliente.conversar("qwen/qwen3.8-27b", [{"role": "user", "content": "oi"}],
                          teto_saida=pedido)

    assert enviados == [900, 900, 900, 900], enviados
    assert all(t <= cliente.otpm for t in enviados)
    # Teto que já cabe passa intacto: a trava é um limite, não um valor fixo.
    cliente.conversar("qwen/qwen3.8-27b", [{"role": "user", "content": "oi"}],
                      teto_saida=400)
    assert enviados[-1] == 400


def test_recusa_por_tamanho_nao_e_recuperavel_e_guarda_o_texto_da_groq():
    """Os dois 429 da Groq levam a consertos opostos.

    Cota estourada passa com o tempo; recusa por tamanho da requisição, não —
    e um lote que a trate como recuperável queima foto após foto contra o mesmo
    limite. Foi o que aconteceu: onze fotos seguidas.
    """
    import groq

    from auditoria.modelos import traduzir

    original = (
        "Request too large for model `qwen/qwen3.8-27b` in organization "
        "`org_x` service tier `on_demand` on output tokens per minute (OTPM): "
        "Limit 1000, Requested 1113. The request's expected output tokens "
        "exceed the enforced limit; reduce max_tokens (or the request's "
        "expected output) and try again."
    )
    erro = traduzir(groq.RateLimitError(
        "429", response=_resposta_http(429),
        body={"error": {"message": original}},
    ))
    assert not erro.recuperavel, "esperar não faz a requisição caber"
    assert "tamanho" in erro.mensagem.lower()
    # E a mensagem que NOMEIA o limite sobrevive à tradução: foi o palpite
    # escrito no código ("limite de tokens por minuto ou por dia") que mandou
    # o diagnóstico atrás do TPM por horas, com o texto certo já na resposta.
    assert erro.detalhe == original
    assert "OTPM" in erro.detalhe


def test_a_mensagem_original_da_api_sobrevive_a_traducao():
    """Vale para todo erro traduzido, não só o do dia: a tradução é um palpite
    sobre a causa, e o próximo limite novo chega com um nome que este código
    ainda não conhece."""
    import groq

    from auditoria.modelos import traduzir

    casos = [
        groq.AuthenticationError("401", response=_resposta_http(401),
                                 body={"error": {"message": "Invalid API Key"}}),
        groq.RateLimitError("429", response=_resposta_http(429),
                            body={"error": {"message": "Rate limit reached for tokens"}}),
        groq.BadRequestError("400", response=_resposta_http(400),
                             body={"error": {"message": "something new we do not parse"}}),
    ]
    for cru in casos:
        assert traduzir(cru).detalhe, type(cru).__name__


class _ClienteComOtpmApertado:
    """Corta a primeira resposta de cada agente e só aceita 900 de saída."""

    LIMITE = 900

    def __init__(self):
        self.ultimo_corte_por_limite = False
        self.tetos: list[int] = []
        self.pedidos: list[str] = []
        self.vistos: set[str] = set()

    def teto_permitido(self, teto: int) -> int:
        return min(teto, self.LIMITE)

    def conversar(self, modelo, mensagens, teto_saida=1200, temperatura=0.0,
                  json_estrito=False):
        p = _texto_do_prompt(mensagens)
        self.tetos.append(teto_saida)
        self.pedidos.append(p)
        quem = ("olho" if "perito em documentação fotográfica" in p
                else "analista" if "DOSSIÊ NORMATIVO" in p else "diretor")
        completo = ClienteDemonstracao().conversar(
            modelo, mensagens, teto_saida, temperatura, json_estrito
        )
        if quem in self.vistos:
            self.ultimo_corte_por_limite = False
            return completo
        self.vistos.add(quem)
        self.ultimo_corte_por_limite = True
        return completo[: len(completo) // 2]


def test_a_retentativa_nao_dobra_o_teto_acima_do_limite_da_conta(base):
    """Dobrar o teto era o mecanismo da segunda tentativa — e virou 429 certo.

    Com o OTPM abaixo do que os agentes pedem, a chamada refeita com o dobro é
    recusada pelo tamanho e a foto morre onde antes se salvava. Com o teto no
    talo, o que muda entre as duas tentativas passa a ser o PEDIDO: a segunda
    manda encurtar a resposta, que é o conserto certo para uma resposta que não
    coube.
    """
    cliente = _ClienteComOtpmApertado()
    laudo = executar(
        cliente, base, "imagem-falsa", "",
        Configuracao(modelo_visao="d", modelo_texto="d", data_referencia=HOJE),
    )
    assert laudo.nao_conformidades, "o laudo se perdeu na segunda tentativa"
    assert cliente.tetos == [900] * 6, cliente.tetos
    refeitos = [p for p in cliente.pedidos if "REFAÇA A RESPOSTA" in p]
    assert len(refeitos) == 3, "os três agentes cortados deveriam ter refeito o pedido"


def test_o_pedido_de_concisao_corta_prosa_e_nao_a_lista():
    """Encurtar prosa e encurtar evidência são coisas opostas.

    A resposta do Olho É a evidência do laudo: um achado que ele não escrever na
    segunda tentativa não é enquadrado por ninguém depois e some sem rastro. E
    enquadramento que o Diretor deixar fora de `conferencia` chega a
    `_exigencia_ancorada("")`, que é falso, e vira veto automático com o motivo
    errado — encurtar por omissão derruba não conformidade verdadeira nos dois.
    """
    from auditoria.pipeline import PEDIDO_DE_CONCISAO, _exigencia_ancorada

    texto = PEDIDO_DE_CONCISAO.format(teto=900)
    assert "MESMOS itens" in texto
    assert "Corte PROSA, nunca CONTEÚDO" in texto
    # A consequência que o pedido cita é real, não retórica: sem exigência
    # copiada, o enquadramento é recusado.
    class _Item:
        texto = "As aberturas no piso devem ter fechamento provisório resistente."
    assert not _exigencia_ancorada("", _Item())


def test_a_segunda_tentativa_do_olho_nao_perde_a_imagem():
    """O Olho manda lista de partes (texto + imagem); os outros dois, string.

    Concatenar o pedido de concisão como texto apagaria a imagem, e a segunda
    tentativa descreveria uma foto que ela não veria.
    """
    from auditoria.pipeline import _com_pedido_de_concisao

    partes = [
        {"type": "text", "text": "descreva"},
        {"type": "image_url", "image_url": {"url": "data:image/jpeg;base64,AAA"}},
    ]
    refeito = _com_pedido_de_concisao(partes, 900)
    assert [p["type"] for p in refeito] == ["text", "image_url", "text"]
    assert refeito[1] == partes[1]
    assert "900" in refeito[-1]["text"]
    assert _com_pedido_de_concisao("prompt", 900).startswith("prompt")


# ---------------------------------------------------------------------------
# O lote de 9 fotos de poço de elevador (05/09/2026): sinal sem negador
# ---------------------------------------------------------------------------

def test_grade_que_fecha_a_abertura_nao_aciona_risco_de_abertura_desprotegida():
    """Fatos reais do laudo 4 de 05/09/2026, com a proteção INSTALADA.

    "abertura na parede" eram dois radicais e nenhum negador, então o fato
    "Grade metálica montada em um batente de metal, FECHANDO uma abertura
    retangular entre as PAREDES de tijolo" dava cobertura 1,00 — e o laudo do
    cliente saiu com `NR-08 8.3.2.2` sobre uma abertura que estava protegida. O
    engenheiro confirmou a foto: a grade fecha o vão.

    É o defeito que o #27 corrigiu nos dois riscos de elevador e que ficou de pé
    no risco de abertura, que é o que de fato routeia estas fotos.
    """
    protegida = Visao(
        ambiente="Interior de uma construção em fase de alvenaria, com paredes de "
                 "tijolo aparente e piso de concreto.",
        achados=[
            Achado("Grade metálica de malha quadrada (treliça) montada em um batente "
                   "de metal, fechando uma abertura retangular entre as paredes de tijolo."),
            Achado("Paredes de alvenaria de tijolo cerâmico vermelho com juntas de "
                   "argamassa visíveis e superfície irregular, sem reboco."),
        ],
    )
    assert "abertura_parede_desprotegida" not in [r.id for r in rotear_riscos(protegida)]

    # E o contraponto do MESMO lote (laudo 5), onde a abertura é real: continua
    # acionando. Sem isto o conserto seria só uma poda.
    desprotegida = Visao(
        ambiente="Interior de um edifício em fase de construção, caracterizado por "
                 "estruturas de concreto aparente e piso com entulho.",
        achados=[Achado(
            "Abertura retangular vertical no pilar de concreto, com bordas irregulares "
            "e sem porta ou fechamento visível, revelando um vão escuro no interior."
        )],
    )
    assert "abertura_parede_desprotegida" in [r.id for r in rotear_riscos(desprotegida)]

    # A contraparte do terceiro sinal, que o `/critico` cobrou: um pilar cuja
    # abertura JÁ está fechada. `abertura no pilar` chegou a entrar aqui e dava
    # 1,00 neste fato — o mesmo defeito, reintroduzido dentro do conserto.
    pilar_fechado = Visao(
        ambiente="Interior de edifício em construção.",
        achados=[Achado(
            "Abertura no pilar de concreto fechada com chapa metálica parafusada "
            "na estrutura."
        )],
    )
    assert "abertura_parede_desprotegida" not in [r.id for r in rotear_riscos(pilar_fechado)]

    # E o que o terceiro sinal acrescenta: o vão de janela, que a descrição do
    # risco nomeia e que nenhum sinal pegava.
    janela = Visao(
        ambiente="Fachada de edifício em obra.",
        achados=[Achado(
            "Vão de janela aberto na fachada, sem caixilho nem proteção, com queda "
            "direta para o exterior."
        )],
    )
    assert "abertura_parede_desprotegida" in [r.id for r in rotear_riscos(janela)]


def test_guarda_corpo_instalado_nao_aciona_risco_de_guarda_corpo_ausente():
    """O sinal fazia o oposto do que descreve, e o mesmo lote provou os dois lados.

    "guarda corpo so com uma corda" tem cinco radicais e três são cola (`so` cai
    no filtro de duas letras; sobram `com` e `uma`). O guarda-corpo INSTALADO
    cobria 4 de 5 — "cabine ... COM UMA unidade de ar-condicionado ... e UMA
    plataforma cercada por GUARDA-CORPO metálico" — e o que faltava era `corda`,
    o único discriminante. Nos fatos com a corda de verdade ele ficava em 0,60 e
    não disparava.
    """
    instalado = Visao(
        ambiente="Vista aérea de um canteiro de obras urbano com edifícios em construção.",
        achados=[Achado(
            "Cabine de cor branca com uma unidade de ar-condicionado instalada na "
            "lateral externa e uma plataforma superior cercada por guarda-corpo metálico."
        )],
    )
    assert "periferia_laje_sem_guarda_corpo" not in [r.id for r in rotear_riscos(instalado)]

    # NÃO se testa aqui o guarda-corpo íntegro descrito com "sem folgas": ele
    # ainda aciona este risco e mais dois, por quatro sinais diferentes, e o
    # conserto não cabe numa troca de sinal — está medido em "Em aberto" no
    # CLAUDE.md, sob o `sem` que satisfaz um sinal negando outra coisa.

    # E o que o sinal defeituoso deixava passar: a corda no lugar do guarda-corpo.
    improvisado = Visao(
        ambiente="Laje de cobertura em construção.",
        achados=[Achado(
            "Corda de náilon amarela esticada entre dois pontos na borda da laje, "
            "no lugar de guarda-corpo."
        )],
    )
    assert "periferia_laje_sem_guarda_corpo" in [r.id for r in rotear_riscos(improvisado)]


def test_o_que_substitui_a_tela_na_borda_e_a_altura_e_nao_a_tela():
    """Contrapartes do sinal que entrou no lugar de "guarda corpo so com uma corda".

    O candidato óbvio era nomear o objeto — "tela plastica na borda" —, e ele
    parecia seguro justamente por não depender de negação. Medido, dispara nos
    dois fatos abaixo, em que não há periferia desprotegida nenhuma: a tela de
    SINALIZAÇÃO na borda de uma escavação ao nível do solo, e a tela presa
    ATRÁS de um guarda-corpo rígido, como anteparo de fragmentos. O que
    discrimina a proteção inadequada não é a tela, é a ALTURA — e é por isso que
    o sinal fala de joelho. Sem este teste as duas medições viveriam só no
    comentário, e o sinal poderia voltar sem nada quebrar.
    """
    sinalizacao_no_solo = Visao(
        ambiente="Canteiro de obras ao nível do solo.",
        achados=[Achado(
            "Tela plástica laranja de sinalização esticada na borda da área de "
            "escavação, ao nível do solo."
        )],
    )
    assert "periferia_laje_sem_guarda_corpo" not in [
        r.id for r in rotear_riscos(sinalizacao_no_solo)
    ]

    # A cena diz "pavimento", e não "laje"/"periferia", de propósito: com essas
    # duas palavras o fato dispara pelo sinal ANTIGO `periferia da laje sem
    # guarda-corpo`, que tem cinco radicais e passa a 0,80 faltando justamente o
    # `sem` — outro caso da família registrada em "Em aberto", e que não é o que
    # este teste mede. Aqui se isola o sinal que entrou.
    anteparo_atras_do_guarda_corpo = Visao(
        ambiente="Pavimento de edifício em obra.",
        achados=[Achado(
            "Guarda-corpo metálico rígido instalado na borda do pavimento, com tela "
            "plástica presa por trás como anteparo de fragmentos."
        )],
    )
    assert "periferia_laje_sem_guarda_corpo" not in [
        r.id for r in rotear_riscos(anteparo_atras_do_guarda_corpo)
    ]

    # E o positivo que o sinal existe para pegar, do lote de 29/08: a barreira
    # descrita com material, fixação e ALTURA.
    tela_na_altura_do_joelho = Visao(
        ambiente="Área de construção civil em fase de alvenaria, localizada em um "
                 "edifício de grande altura com vista para uma cidade.",
        achados=[Achado(
            "Tela plástica flexível laranja de malha larga estendida ao longo da borda "
            "do piso, presa a um cone e a uma haste, altura na altura do joelho, sem "
            "guarda-corpo rigido visivel."
        )],
    )
    assert "periferia_laje_sem_guarda_corpo" in [
        r.id for r in rotear_riscos(tela_na_altura_do_joelho)
    ]


# ---------------------------------------------------------------------------
# Achado apontado pelo inspetor (desenho D, medido em 08/09)
# ---------------------------------------------------------------------------

# A cena do laudo 15 do lote de 08/09 — `19 PAV. POÇO GRUA SEM PROTEÇÃO`, um poço
# sem proteção de piso NEM de parede, que saiu com 0 NC. O Olho registrou o vão
# vertical e a grade encostada na parede, e NÃO registrou a abertura de piso: sem
# esse fato `abertura_piso_desprotegida` não dispara e o `NR-18 18.9.2` nunca
# chega ao dossiê — nem um Diretor perfeito o enquadraria depois.
CENA_LAUDO_15 = Visao(
    ambiente="Pavimento em obra de edificação, com paredes de alvenaria sem "
             "revestimento e piso de concreto.",
    achados=[
        Achado("Vão vertical retangular aberto na parede de alvenaria, sem "
               "fechamento provisório instalado."),
        Achado("Grade metálica de malha quadrada apoiada e encostada na parede, "
               "ao lado do vão, sem fixação à estrutura."),
    ],
)


def test_a_lista_marcavel_so_oferece_construcao_sem_exigir_pessoa():
    """Os dois filtros da lista, e os dois são de segurança.

    Risco de outro domínio encheria a lista de vocabulário de fábrica num app de
    canteiro; risco que exige pessoa seria descartado em silêncio pelo portão de
    `montar_dossie` numa foto sem ninguém — o inspetor marcaria e nada
    aconteceria, sem uma linha no laudo explicando por quê.
    """
    marcaveis = riscos_marcaveis()
    assert marcaveis, "a lista não pode ficar vazia"
    assert all(r.dominio == "construcao" for r in marcaveis)
    assert not [r.id for r in marcaveis if r.exige_pessoa]
    # Ordem: do mais grave para o menos, que é a ordem em que se lê uma lista de
    # quarenta itens sem ler os quarenta.
    posicao = [GRAVIDADES.index(r.gravidade_base) for r in marcaveis]
    assert posicao == sorted(posicao)


def test_risco_marcado_traz_ao_dossie_o_item_que_o_olho_nao_alcancou(base):
    """O caso que o desenho D existe para consertar, reproduzido sem rede."""
    citados = lambda d: [f"{e.item.nr} {e.item.item}" for e in d.entradas]

    sozinho, _ = montar_dossie(base, CENA_LAUDO_15, "", HOJE)
    assert "NR-18 18.9.2" not in citados(sozinho), (
        "a cena precisa NÃO alcançar o item por conta própria, senão o teste "
        "não mede nada"
    )

    marcado, origem = montar_dossie(
        base, CENA_LAUDO_15, "", HOJE, marcados=["abertura_piso_desprotegida"]
    )
    assert citados(marcado)[0] == "NR-18 18.9.2"
    # E o item vem CURADO, com o risco do inspetor: é dele que `aferir` tira a
    # gravidade base e o portão de pessoa na cena.
    assert origem["D1"].id == "abertura_piso_desprotegida"


def test_o_item_marcado_encabeca_sem_expulsar_o_que_o_roteamento_achou(base):
    """A posição é o mecanismo inteiro — e ela ACRESCENTA, não substitui.

    Encher o dossiê e empurrar o item certo para baixo é a classe de erro 1 pela
    porta do dossiê pobre; foi por isso que a prosa livre no campo de contexto
    (o braço B da medição) foi recusada, com o item esperado caindo de D1 para
    D2,7. Marcar põe o item do inspetor em D1 e desloca os demais um degrau,
    sem tirar nenhum.
    """
    visao = Visao(
        ambiente="Pavimento de edifício em obra, com piso de concreto.",
        achados=[Achado(
            "Tela plástica flexível laranja de malha larga estendida ao longo da "
            "borda do piso, presa a um cone e a uma haste, altura na altura do "
            "joelho, sem guarda-corpo rigido visivel."
        )],
    )
    sozinho, _ = montar_dossie(base, visao, "", HOJE)
    marcado, _ = montar_dossie(
        base, visao, "", HOJE, marcados=["madeira_com_prego_exposto"]
    )
    assert marcado.entradas[0].item.item == "18.16.4.1"
    antes = [e.item.id for e in sozinho.entradas]
    depois = [e.item.id for e in marcado.entradas]
    assert depois[1:len(antes) + 1] == antes[:len(depois) - 1]
    assert antes[0] in depois, "o item que o roteamento achou não pode sumir"


def test_foto_sem_marcacao_sai_exatamente_como_antes(base):
    """As 5 fotos sem marcação da medição saem byte a byte iguais.

    A lista é o desenho que domina os outros três justamente porque não cobra
    nada de quem não a usa; um caminho que altere a foto não marcada desfaria
    isso em silêncio.
    """
    sem_argumento, origem_a = montar_dossie(base, CENA_LAUDO_15, "", HOJE)
    lista_vazia, origem_b = montar_dossie(base, CENA_LAUDO_15, "", HOJE, marcados=[])
    assert [e.item.id for e in sem_argumento.entradas] == [
        e.item.id for e in lista_vazia.entradas
    ]
    assert {k: v.id for k, v in origem_a.items()} == {k: v.id for k, v in origem_b.items()}


def test_id_de_risco_desconhecido_e_ignorado_sem_derrubar_a_foto(base):
    """Lote salvo com taxonomia antiga perde a marcação, não a foto."""
    d, _ = montar_dossie(
        base, CENA_LAUDO_15, "", HOJE,
        marcados=["risco_que_nao_existe_mais", "abertura_piso_desprotegida"],
    )
    assert d.entradas[0].item.item == "18.9.2"


def test_risco_marcado_que_exige_pessoa_nao_burla_o_portao(base):
    """O portão de pessoa na cena vale para o marcado como para o roteado.

    É por isso que a lista não oferece risco de EPI: aqui ele seria descartado
    em silêncio, e silêncio é o que não se quer num campo em que o inspetor
    clicou de propósito.
    """
    de_epi = [r for r in catalogo_riscos().values() if r.exige_pessoa]
    assert de_epi
    d, _ = montar_dossie(
        base, CENA_LAUDO_15, "", HOJE, marcados=[de_epi[0].id]
    )
    assert all(
        f"{e.item.nr} {e.item.item}" not in de_epi[0].itens for e in d.entradas
    ), "risco que exige pessoa entrou numa cena sem ninguém"
    assert de_epi[0].id not in [r.id for r in riscos_marcaveis()]


class _DubleQueGuardaOsPrompts:
    """Devolve laudo mínimo e guarda o texto de cada chamada."""

    ultimo_corte_por_limite = False

    def __init__(self):
        self.prompts: list[str] = []

    def conversar(self, modelo, mensagens, teto_saida=1200, temperatura=0.0,
                  json_estrito=False):
        p = _texto_do_prompt(mensagens)
        self.prompts.append(p)
        if "perito em documentação fotográfica" in p:
            return json.dumps({
                "ambiente": CENA_LAUDO_15.ambiente,
                "pessoas": {"presentes": False, "quantidade": 0},
                "achados": [
                    {"fato": a.fato, "onde": "", "confianca": "alta"}
                    for a in CENA_LAUDO_15.achados
                ],
            }, ensure_ascii=False)
        return json.dumps(
            {"nao_conformidades": [], "sem_enquadramento": [], "conformidades": []},
            ensure_ascii=False,
        )


def _laudo_marcado(base):
    duble = _DubleQueGuardaOsPrompts()
    laudo = executar(
        duble, base, "img", "",
        Configuracao(modelo_visao="d", modelo_texto="d", data_referencia=HOJE),
        marcados=["abertura_piso_desprotegida"],
    )
    return laudo, duble


def test_a_marcacao_nao_chega_ao_agente_de_visao(base):
    """A trava que protege o laudo do clique errado.

    Se a marcação chegasse ao Olho, ele escreveria o que lhe disseram — veja ou
    não —, o `fato` viraria eco do que o inspetor apontou e a conferência do
    Diretor contra os fatos ficaria circular. É a classe de erro 3, e ela entra
    justamente pelo campo que o inspetor preenche de propósito.
    """
    _, duble = _laudo_marcado(base)
    olho = [p for p in duble.prompts if "perito em documentação fotográfica" in p]
    assert olho, "o agente de visão nem chegou a ser chamado"
    risco = catalogo_riscos()["abertura_piso_desprotegida"]
    for p in olho:
        assert risco.id not in p
        assert risco.rotulo not in p


def test_a_trilha_do_laudo_declara_o_que_o_inspetor_apontou(base):
    """Um laudo dirigido em parte por quem inspecionou não tem o mesmo valor de
    evidência que um em que o app chegou sozinho ao item. Sem esta linha,
    dirigir o dossiê seria invisível no documento que vai ao cliente."""
    laudo, _ = _laudo_marcado(base)
    rotulo = catalogo_riscos()["abertura_piso_desprotegida"].rotulo
    assert laudo.riscos_marcados == [rotulo]
    texto = relatorio.markdown(laudo, base, numero=1)
    assert rotulo in texto
    assert "apontado(s) pelo inspetor" in texto
    assert "sem acesso a esta indicação" in texto


def test_laudo_sem_marcacao_nao_ganha_linha_de_trilha(base):
    duble = _DubleQueGuardaOsPrompts()
    laudo = executar(
        duble, base, "img", "",
        Configuracao(modelo_visao="d", modelo_texto="d", data_referencia=HOJE),
    )
    assert laudo.riscos_marcados == []
    assert "apontado(s) pelo inspetor" not in relatorio.markdown(laudo, base, numero=1)


def test_o_sumario_do_lote_declara_as_fotos_dirigidas(base):
    """A declaração vale nos DOIS documentos, e é o sumário que circula.

    O laudo por foto é onde a marcação nasce, mas é o sumário que o engenheiro
    entrega e é o plano de ação dele que vira ordem de serviço — uma linha lida
    solta, longe do laudo de origem. Um sumário que lista a NC dirigida sem
    dizer que foi dirigida esconde justamente o que muda o valor de evidência
    da linha. É a armadilha do corte aplicado a um campo só, com dois
    documentos no lugar de dois campos.
    """
    from auditoria.pipeline import NaoConformidade

    marcado, _ = _laudo_marcado(base)
    marcado.nao_conformidades = [
        NaoConformidade(
            item=base.obter("NR-18", "18.9.2"),
            constatacao="Abertura no piso sem fechamento travado.",
            consequencia="Queda de altura.",
            gravidade="critica",
            acao_corretiva="Instalar fechamento provisório travado.",
            prazo_dias=1,
        )
    ]
    limpo = executar(
        _DubleQueGuardaOsPrompts(), base, "img", "",
        Configuracao(modelo_visao="d", modelo_texto="d", data_referencia=HOJE),
    )

    texto = relatorio.consolidado(
        [("dirigida.jpg", marcado), ("sozinha.jpg", limpo)], base, HOJE
    )
    assert "Imagens com achado apontado pelo inspetor:** 1 de 2" in texto
    assert catalogo_riscos()["abertura_piso_desprotegida"].rotulo in texto
    # E a marca na linha do plano de ação, que é lida longe do laudo de origem.
    linha = [l for l in texto.splitlines() if "Instalar fechamento" in l][0]
    assert "*(apontada)*" in linha


def test_sumario_de_lote_sem_marcacao_nao_ganha_o_bloco(base):
    limpo = executar(
        _DubleQueGuardaOsPrompts(), base, "img", "",
        Configuracao(modelo_visao="d", modelo_texto="d", data_referencia=HOJE),
    )
    texto = relatorio.consolidado([("sozinha.jpg", limpo)], base, HOJE)
    assert "apontado pelo inspetor" not in texto
    assert "*(apontada)*" not in texto


# ---------------------------------------------------------------------------
# Repescagem da conferência do Diretor (o laudo 15 de 09/09)
# ---------------------------------------------------------------------------

MARCA_RECONFERENCIA = "Na revisão anterior você decidiu"
TRECHO_REAL = "deve ser apoiada em piso estável e possuir bases (sapatas) antiderrapantes"


class _DubleQueOmiteAConferencia(_Duble):
    """Diretor aprova e não copia a exigência; a repescagem responde `resposta`.

    `resposta` é o que a segunda chamada devolve — string com o trecho, ou uma
    exceção a levantar. `chamadas_de_reconferencia` conta quantas vezes ela foi
    feita, que é como se trava a regra de não repescar refutação.
    """

    def __init__(self, item_alvo, constatacao, veredito_fn, resposta):
        super().__init__(item_alvo, constatacao, veredito_fn)
        self.resposta = resposta
        self.chamadas_de_reconferencia = 0

    def conversar(self, modelo, mensagens, teto_saida=1200, temperatura=0.0,
                  json_estrito=False):
        if MARCA_RECONFERENCIA in _texto_do_prompt(mensagens):
            self.chamadas_de_reconferencia += 1
            if isinstance(self.resposta, Exception):
                raise self.resposta
            return json.dumps(
                {"conferencia": [{"ref": "V1", "exigencia": self.resposta}]},
                ensure_ascii=False,
            )
        return super().conversar(modelo, mensagens, teto_saida, temperatura, json_estrito)


def _rodar_com_omissao(base, resposta, exigencia_do_diretor=""):
    duble = _DubleQueOmiteAConferencia(
        "NR-35 Anexo III 5.2.2.5", CONSTATACAO,
        lambda: {
            "conferencia": [{"ref": "V1", "fato": FATO, "decisao": "aprovado",
                             "exigencia": exigencia_do_diretor}],
            "aparados": [], "vetados": [], "ajustes": [], "pontos_descartados": [],
            "conformidades_descartadas": [], "parecer": "p",
        },
        resposta,
    )
    laudo = executar(duble, base, "img", "",
                     Configuracao(modelo_visao="d", modelo_texto="d", data_referencia=HOJE))
    return laudo, duble


def test_reconferencia_recupera_o_enquadramento_sem_trecho_copiado(base):
    """O laudo 15 do lote de 09/09, e o que ele custou.

    `19 PAV. POÇO GRUA SEM PROTEÇÃO` foi a foto marcada pelo inspetor. A
    marcação funcionou até o fim: o item entrou curado em D1 e o Analista
    enquadrou `NR-18 18.9.2` e `NR-08 8.3.2.2`, os dois certos. Os dois caíram
    porque o Diretor não copiou o trecho — pela segunda vez na MESMA foto, já
    que o lote de 08/09 tinha falhado no mesmo lugar. O laudo saiu com 0 NC
    sobre um poço sem proteção de piso nem de parede.

    Perguntar de novo, só pelo que faltou, é barato: a resposta são duas ou
    três orações, e nas 14 fotos de 15 em que a conferência não faltou não custa
    chamada nenhuma.
    """
    laudo, duble = _rodar_com_omissao(base, TRECHO_REAL)
    assert duble.chamadas_de_reconferencia == 1
    assert [f"{nc.item.nr} {nc.item.item}" for nc in laudo.nao_conformidades] == [
        "NR-35 Anexo III 5.2.2.5"
    ], "a repescagem trouxe o trecho e o enquadramento continuou caindo"
    assert laudo.conferencia_omitida == []


def test_repescagem_vazia_deixa_o_enquadramento_cair_como_omissao(base):
    """Sem trecho na segunda tentativa, tudo se comporta como antes do conserto.

    É o que impede a repescagem de virar uma porta: ela dá ao supervisor uma
    segunda chance de RESPONDER, não de aprovar. Silêncio duas vezes continua
    derrubando o enquadramento, com a trilha dizendo que foi omissão.
    """
    from auditoria.pipeline import MOTIVO_CONFERENCIA_OMITIDA

    laudo, duble = _rodar_com_omissao(base, "")
    # Ao menos uma, e não exatamente uma: havendo veto, o Gauntlet devolve para
    # um segundo ciclo, que refaz o Diretor e portanto repesca de novo.
    assert duble.chamadas_de_reconferencia >= 1
    assert not laudo.nao_conformidades
    assert MOTIVO_CONFERENCIA_OMITIDA in " ".join(laudo.vetos)
    assert laudo.conferencia_omitida == ["NR-35 Anexo III 5.2.2.5"]
    assert laudo.sem_enquadramento, "o achado evaporou em vez de virar observação"


def test_trecho_que_nao_ancora_nao_e_reperguntado(base):
    """A trava, e ela é o coração deste conserto.

    Trecho que VEIO e não está no item é o supervisor REFUTANDO o
    enquadramento — o painel empoeirado citado em item de sinalização. Repetir
    a pergunta ali daria ao modelo uma segunda chance de inventar a exigência,
    que é precisamente o que esta rede existe para impedir. A repescagem só
    alcança o silêncio.
    """
    from auditoria.pipeline import MOTIVO_EXIGENCIA_NAO_ANCORA

    laudo, duble = _rodar_com_omissao(
        base, TRECHO_REAL,
        exigencia_do_diretor="os degraus devem ser mantidos limpos e desobstruídos",
    )
    assert duble.chamadas_de_reconferencia == 0, (
        "refutação foi reperguntada — o modelo ganhou uma segunda chance de inventar"
    )
    assert not laudo.nao_conformidades
    assert MOTIVO_EXIGENCIA_NAO_ANCORA in " ".join(laudo.vetos)


def test_repescagem_ilegivel_nao_mata_a_foto(base):
    """A repescagem é um bônus: quando ela falha, o laudo é o de antes.

    Deixar `RespostaIlegivel` subir daqui perderia a foto inteira por causa de
    um reparo — trocaria um enquadramento que já ia cair por um laudo que não
    sai. É a armadilha do `except` largo pelo avesso: aqui o erro engolido não
    faz o documento mentir, porque o caminho de saída é o mesmo de antes e a
    trilha continua dizendo "Supervisão incompleta".
    """
    from auditoria.modelos import RespostaIlegivel
    from auditoria.pipeline import MOTIVO_CONFERENCIA_OMITIDA

    laudo, duble = _rodar_com_omissao(base, RespostaIlegivel("json quebrado"))
    assert duble.chamadas_de_reconferencia >= 1
    assert not laudo.nao_conformidades
    assert MOTIVO_CONFERENCIA_OMITIDA in " ".join(laudo.vetos)
    assert not laudo.visao_falhou, "a foto foi perdida por causa do reparo"


class _DubleQueAparaEOmite(_Duble):
    """Diretor APARA e não copia a exigência; guarda o prompt da repescagem."""

    def __init__(self, item_alvo, constatacao, veredito_fn, resposta):
        super().__init__(item_alvo, constatacao, veredito_fn)
        self.resposta = resposta
        self.prompt_de_reconferencia = ""

    def conversar(self, modelo, mensagens, teto_saida=1200, temperatura=0.0,
                  json_estrito=False):
        p = _texto_do_prompt(mensagens)
        if MARCA_RECONFERENCIA in p:
            self.prompt_de_reconferencia = p
            return json.dumps(
                {"conferencia": [{"ref": "V1", "exigencia": self.resposta}]},
                ensure_ascii=False,
            )
        return super().conversar(modelo, mensagens, teto_saida, temperatura, json_estrito)


APARADA = "A escada portátil está apoiada sobre entulho, com a base fora do nível."


def test_a_repescagem_pergunta_pela_constatacao_APARADA(base):
    """O gap que o `/critico` pegou na primeira versão da repescagem.

    O aparo corta da constatação o que o fato não sustenta, e quem tem de
    descumprir o item é o que SOBRA. É a distinção que o `PROMPT_DIRETOR`
    carrega desde o #13: a NR-35 Anexo III 5.2.2.5 exige piso estável E sapata,
    então cortada a sapata ainda descumpre — aparar; a NR-18 18.8.6.12 trata só
    de sapata, então cortada a sapata não descumpre mais nada — vetar.

    Perguntar a repescagem sobre a constatação ORIGINAL salvaria justamente o
    segundo caso: o modelo acharia o trecho que a frase inteira descumpre, e o
    laudo imprimiria a aparada, que não descumpre. Seria reabrir por dentro a
    porta que o #13 e o #15 fecharam — o aparo salvando enquadramento que era
    veto — e dentro do conserto de outra coisa.
    """
    duble = _DubleQueAparaEOmite(
        "NR-35 Anexo III 5.2.2.5", CONSTATACAO,
        lambda: {
            "conferencia": [{"ref": "V1", "fato": FATO, "decisao": "aparado",
                             "exigencia": ""}],
            "aparados": [{"ref": "V1", "constatacao": APARADA,
                          "acao_corretiva": "Reposicionar a escada sobre piso estável.",
                          "gravidade": "alta", "retirado": "a cláusula da sapata"}],
            "vetados": [], "ajustes": [], "pontos_descartados": [],
            "conformidades_descartadas": [], "parecer": "p",
        },
        TRECHO_REAL,
    )
    executar(duble, base, "img", "",
             Configuracao(modelo_visao="d", modelo_texto="d", data_referencia=HOJE))

    assert APARADA in duble.prompt_de_reconferencia, (
        "a repescagem foi feita sobre a constatação que não vai ao laudo"
    )
    assert "sapatas antiderrapantes" not in duble.prompt_de_reconferencia, (
        "a cláusula que o aparo retirou voltou para a pergunta da repescagem"
    )


def test_repescagem_que_devolve_trecho_ruim_continua_sendo_omissao(base):
    """O segundo gap que o `/critico` pegou, e ele é o defeito do #34 de volta.

    A supervisão ficou em SILÊNCIO sobre este enquadramento — foi por isso que
    ele entrou na repescagem. Se o reparo devolver um trecho que não está no
    item (paráfrase em vez de cópia, que é justamente por que
    `_exigencia_ancorada` existe), o enquadramento cai — certo — mas o motivo
    NÃO pode virar refutação: ninguém refutou nada. O laudo estaria afirmando
    ao engenheiro que a situação não descumpre a norma, que é a frase exata que
    o #34 tirou deste mesmo laudo, recriada dentro do conserto que cita o #34
    como trava.
    """
    from auditoria.pipeline import MOTIVO_CONFERENCIA_OMITIDA, MOTIVO_EXIGENCIA_NAO_ANCORA

    laudo, duble = _rodar_com_omissao(
        base, "os degraus devem ser mantidos limpos e desobstruídos"
    )
    assert duble.chamadas_de_reconferencia >= 1
    assert not laudo.nao_conformidades, "trecho que não ancora não pode salvar nada"
    trilha = " ".join(laudo.vetos)
    assert MOTIVO_CONFERENCIA_OMITIDA in trilha
    assert MOTIVO_EXIGENCIA_NAO_ANCORA not in trilha, (
        "o laudo está afirmando que a norma não foi descumprida, e ninguém conferiu"
    )
    assert laudo.conferencia_omitida == ["NR-35 Anexo III 5.2.2.5"]


def test_prompt_do_diretor_veta_constatacao_que_e_verificacao():
    """A cláusula (e), e ela nasceu de um laudo impresso duas vezes.

    `11 PAV. PROTEÇÃO POÇO ELEVADOR SEM PROTEÇÃO` saiu em 09/09 e no lote de
    três do mesmo dia com `NR-18 18.9.2` — na segunda vez CRÍTICA, prazo de 1
    dia — cuja providência era "Verificar no local se a grade possui travamento
    ou fixação na estrutura". O laudo cobrava do engenheiro, em 24 horas, uma
    ida ao local.

    O mecanismo é a regra da MOLDURA aplicada até a metade: o Diretor apara a
    afirmação categórica (certo, a fixação não aparece no recorte) e mantém o
    enquadramento, quando o que restou já não afirma descumprimento nenhum. O
    prompt sempre disse para escrever a verificação em `observacao`; o que
    faltava era dizer que, nesse caso, NÃO SOBRA NADA para aparar.
    """
    from auditoria.pipeline import PROMPT_DIRETOR

    assert "e) o que sobraria da constatação é uma VERIFICAÇÃO" in PROMPT_DIRETOR
    assert "não é possível determinar se há" in PROMPT_DIRETOR
    assert 'escreva a verificação em "observacao"' in PROMPT_DIRETOR


def test_a_clausula_e_protege_a_falta_que_a_foto_mostra():
    """A fronteira, sem a qual a cláusula (e) viraria a classe de erro 5.

    Se ela alcançasse toda constatação sobre peça ausente, o falso negativo
    mais caro do histórico voltaria: a tela plástica frouxa na borda da laje é
    falta que a foto MOSTRA, e a constatação sobre ela afirma. O discriminante
    é o mesmo da moldura — a peça apareceria no recorte se existisse —, e o
    teste é sobre a CONSTATAÇÃO, nunca sobre a ação corretiva, que
    legitimamente pode mandar verificar o resto.
    """
    from auditoria.pipeline import PROMPT_DIRETOR

    assert "A FRONTEIRA, e ela é o oposto disto" in PROMPT_DIRETOR
    assert "tela plástica frouxa pendurada na borda" in PROMPT_DIRETOR
    assert "o teste desta cláusula é sobre a CONSTATAÇÃO, nunca sobre a ação" in PROMPT_DIRETOR


def test_aparo_que_devolve_a_mesma_constatacao_nao_vira_linha_de_trilha(base):
    """O laudo 3 de 09/09: trilha afirmando um corte que não houve.

    Saiu impresso "constatação restrita ao fato registrado — retirado: Nenhuma
    cláusula foi removida, pois…" — o Diretor dizendo no próprio texto que não
    removeu nada, dentro de uma linha que anuncia remoção. A comparação é exata
    de propósito: o aparo existe para RESTRINGIR, e qualquer restrição real
    muda o texto.
    """
    laudo, _ = _rodar(base, "NR-35 Anexo III 5.2.2.5", lambda: {
        "conferencia": [{"ref": "V1", "fato": FATO, "decisao": "aparado",
                         "exigencia": TRECHO_REAL}],
        "aparados": [{"ref": "V1", "constatacao": f"  {CONSTATACAO.upper()}  ",
                      "acao_corretiva": "", "gravidade": "alta",
                      "retirado": "Nenhuma cláusula foi removida, pois a constatação "
                                  "original já estava restrita aos fatos visíveis"}],
        "vetados": [], "ajustes": [], "pontos_descartados": [],
        "conformidades_descartadas": [], "parecer": "p",
    })
    assert laudo.nao_conformidades, "o enquadramento não devia cair por isto"
    assert laudo.aparos == [], f"trilha anuncia corte que não houve: {laudo.aparos}"


def test_aparo_que_muda_uma_clausula_continua_virando_linha(base):
    """A contraparte: restrição de verdade tem de aparecer na trilha.

    Sem ela o conserto acima viraria uma porta — o aparo que corta a cláusula
    sem lastro é exatamente o que a trilha existe para registrar, e é o
    mecanismo que o #13 construiu.
    """
    laudo, _ = _rodar(base, "NR-35 Anexo III 5.2.2.5", lambda: {
        "conferencia": [{"ref": "V1", "fato": FATO, "decisao": "aparado",
                         "exigencia": TRECHO_REAL}],
        "aparados": [{"ref": "V1", "constatacao": APARADA,
                      "acao_corretiva": "Reposicionar a escada sobre piso estável.",
                      "gravidade": "alta", "retirado": "a cláusula da sapata"}],
        "vetados": [], "ajustes": [], "pontos_descartados": [],
        "conformidades_descartadas": [], "parecer": "p",
    })
    assert laudo.nao_conformidades[0].constatacao == APARADA
    assert len(laudo.aparos) == 1
    assert "retirado: a cláusula da sapata" in laudo.aparos[0]


# ---------------------------------------------------------------------------
# Rótulo do dossiê vazando para o laudo (o lote de variabilidade de 10/09)
# ---------------------------------------------------------------------------

def test_rotulo_do_dossie_apresentado_sai_do_texto():
    """`D6` é endereço interno do pipeline e não diz nada a quem lê o laudo.

    Medido em produção: uma conformidade do lote de 10/09 saiu impressa como
    "…atendendo aos requisitos de proteção contra queda de pessoas descritos
    no item D6". Um vazamento em 30 laudos — raro, e ainda assim num documento
    que vai ao cliente.
    """
    from auditoria.pipeline import _limpar_citacoes

    limpo = _limpar_citacoes(
        "Guarda-corpo metálico tubular delimitando a plataforma elevada, "
        "atendendo aos requisitos de proteção contra queda de pessoas "
        "descritos no item D6."
    )
    assert "D6" not in limpo
    # O particípio que só apresentava a referência sai com ela, senão o texto
    # termina em "…descritos." — gramatical, mas pendurado.
    assert "descritos" not in limpo
    assert "Guarda-corpo metálico tubular" in limpo
    assert limpo.rstrip().endswith(".")


def test_rotulo_do_dossie_entre_parenteses_sai():
    from auditoria.pipeline import _limpar_citacoes

    limpo = _limpar_citacoes("A proteção instalada atende ao exigido (D3).")
    assert "D3" not in limpo
    assert limpo.startswith("A proteção instalada atende ao exigido")


def test_rotulo_do_dossie_NU_fica_de_proposito():
    """A contraparte, e ela é deliberada.

    É a mesma razão pela qual `RE_ROTULO_INTERNO` só remove `(V1)` entre
    parênteses: notação de engenharia civil colide com rótulo curto, e mutilar
    a frase de quem descreve a própria obra é pior que deixar o rótulo passar.
    Sem o apresentador ou o delimitador não há como distinguir os dois.
    """
    from auditoria.pipeline import _limpar_citacoes

    texto = "Bloco D3 da edificação com fôrma de pilar apoiada na laje."
    assert _limpar_citacoes(texto) == texto


def test_rotulo_do_dossie_nao_come_numero_de_item_de_nr():
    """A regex do rótulo não pode alcançar "item 18.9.2" — quem cita é o código,
    mas o número do item continua saindo pelo renderizador a partir da base."""
    from auditoria.pipeline import RE_ROTULO_DOSSIE

    assert RE_ROTULO_DOSSIE.search("item 18.9.2") is None
    assert RE_ROTULO_DOSSIE.search("item D6") is not None


class _DubleComConformidadeSuja(_Duble):
    """Analista propõe uma conformidade com rótulo de dossiê e citação à mão."""

    CONFORMIDADE = (
        "Guarda-corpo metálico rígido e contínuo na borda, conforme o item D6 "
        "e a NR-18 18.9.1."
    )

    def conversar(self, modelo, mensagens, teto_saida=1200, temperatura=0.0,
                  json_estrito=False):
        bruto = super().conversar(modelo, mensagens, teto_saida, temperatura, json_estrito)
        dados = json.loads(bruto)
        if "nao_conformidades" in dados:
            dados["conformidades"] = [self.CONFORMIDADE]
            return json.dumps(dados, ensure_ascii=False)
        return bruto


def test_conformidade_passa_pela_limpeza_de_citacao_e_rotulo(base):
    """`conformidades` era a ÚNICA lista do laudo que ia crua ao documento.

    O rótulo era o sintoma visível; o buraco real é a citação normativa escrita
    à mão pelo modelo chegando ao laudo sem passar pela base, que é a garantia
    central deste projeto — o modelo escolhe, o código cita.
    """
    duble = _DubleComConformidadeSuja(
        "NR-35 Anexo III 5.2.2.5", CONSTATACAO,
        lambda: {
            "conferencia": [{"ref": "V1", "fato": FATO, "decisao": "aprovado",
                             "exigencia": TRECHO_REAL}],
            "aparados": [], "vetados": [], "ajustes": [], "pontos_descartados": [],
            "conformidades_descartadas": [], "parecer": "p",
        },
    )
    laudo = executar(duble, base, "img", "",
                     Configuracao(modelo_visao="d", modelo_texto="d", data_referencia=HOJE))
    assert laudo.conformidades, "a conformidade proposta sumiu do laudo"
    saida = laudo.conformidades[0]
    assert "D6" not in saida
    assert "NR-18" not in saida and "18.9.1" not in saida
    assert "Guarda-corpo metálico rígido e contínuo na borda" in saida


# ---------------------------------------------------------------------------
# A repescagem bem-sucedida precisa aparecer na trilha
# ---------------------------------------------------------------------------

def test_repescagem_bem_sucedida_vira_linha_na_trilha(base):
    """Sem esta linha a repescagem é invisível no documento.

    O enquadramento sobrevive e nada diz que ele passou pela rede — de modo que
    um lote sem nenhuma "Supervisão incompleta" não separa o Diretor não ter
    omitido do reparo ter funcionado, que são conclusões opostas sobre o mesmo
    mecanismo. Aconteceu no lote de 10/09: 30 laudos, zero linhas de omissão, e
    nenhum jeito de dizer qual das duas.
    """
    laudo, duble = _rodar_com_omissao(base, TRECHO_REAL)
    assert duble.chamadas_de_reconferencia == 1
    assert laudo.conferencia_reparada == ["NR-35 Anexo III 5.2.2.5"]
    assert laudo.conferencia_omitida == []
    texto = relatorio.markdown(laudo, base, "foto.jpg")
    assert "Conferência repescada" in texto
    assert "NR-35 Anexo III 5.2.2.5" in texto


def test_conferencia_reparada_nao_duplica_com_dois_ciclos(base):
    """Lista local atribuída no fim do ciclo, nunca `append` no laudo.

    É a armadilha que o `conferencia_omitida` já pagou: `laudo.vetos = motivos`
    é atribuição e por isso não duplica; `laudo.aparos.append(...)` não tem essa
    proteção, e o padrão de `Configuracao` é `max_ciclos` maior que 1.
    """
    duble = _DubleQueOmiteAConferencia(
        "NR-35 Anexo III 5.2.2.5", CONSTATACAO,
        lambda: {
            "conferencia": [{"ref": "V1", "fato": FATO, "decisao": "aprovado",
                             "exigencia": ""}],
            "aparados": [], "vetados": [], "ajustes": [], "pontos_descartados": [],
            "conformidades_descartadas": [], "parecer": "p",
        },
        TRECHO_REAL,
    )
    laudo = executar(duble, base, "img", "",
                     Configuracao(modelo_visao="d", modelo_texto="d",
                                  data_referencia=HOJE, max_ciclos=2))
    assert laudo.conferencia_reparada == ["NR-35 Anexo III 5.2.2.5"]


def test_repescagem_vazia_nao_conta_como_reparada(base):
    """A contraparte: silêncio duas vezes continua sendo omissão, e só isso."""
    laudo, _ = _rodar_com_omissao(base, "")
    assert laudo.conferencia_reparada == []
    assert laudo.conferencia_omitida == ["NR-35 Anexo III 5.2.2.5"]
    texto = relatorio.markdown(laudo, base, "foto.jpg")
    assert "Conferência repescada" not in texto
    assert "Supervisão incompleta" in texto
