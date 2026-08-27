"""Testes das garantias que o produto promete.

O foco não é cobertura de linha: é travar os comportamentos cuja quebra faria o
app voltar a emitir laudo errado — citação inexistente, item fora de vigência,
cobrança de EPI sem gente na foto, enquadramento fora de tema.
"""

from __future__ import annotations

import re
import sys
from datetime import date
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from auditoria import relatorio
from auditoria.catalogo_nr import CATALOGO_NR, NRS_REVOGADAS, NRS_VIGENTES
from auditoria.demo import ClienteDemonstracao
from auditoria.kb import carregar_base, extrair_citacoes, tokenizar
from auditoria.pipeline import (
    Achado, Configuracao, Visao, aferir, executar, rotear_riscos,
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
                "conferencia": [],
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
