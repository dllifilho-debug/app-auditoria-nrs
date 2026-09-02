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
from auditoria.riscos import catalogo as catalogo_riscos

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
    from auditoria.modelos import ClienteGroq, Cota

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
    """Os tetos não são iguais entre si: o qwen3.8-27b tem 2.000.000 de tokens
    por dia contra 200.000 dos demais. Com um número só, o painel diria que a
    cota dele acabou com nove décimos sobrando."""
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
    """O 3.8 tem dez vezes o teto dos demais; é isso que faz um lote de 100
    fotos caber num dia."""
    from auditoria import modelos

    tetos = modelos.tetos_diarios()
    assert tetos["qwen/qwen3.8-27b"] == 2_000_000
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
