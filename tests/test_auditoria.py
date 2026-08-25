"""Testes das garantias que o produto promete.

O foco não é cobertura de linha: é travar os comportamentos cuja quebra faria o
app voltar a emitir laudo errado — citação inexistente, item fora de vigência,
cobrança de EPI sem gente na foto, enquadramento fora de tema.
"""

from __future__ import annotations

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
