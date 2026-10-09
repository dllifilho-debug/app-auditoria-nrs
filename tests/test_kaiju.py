"""Testes do "Enviar para o Kaiju" (auditoria/kaiju.py).

Travam o que o envio promete: a citação que chega ao Kaiju é a do `Item` da base,
o laudo não é tocado, a chave de reenvio é estável, e o cliente HTTP fala o
contrato da função `enviar_nc_auditoria` (migration 0005 do kaiju-sgi) — tudo
sem rede, com transporte falso.
"""

import copy
import dataclasses
import json
import sys
from datetime import date
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from auditoria import kaiju
from auditoria.demo import ClienteDemonstracao
from auditoria.kb import carregar_base
from auditoria.pipeline import Configuracao, executar

HOJE = date(2026, 8, 23)
OBRA = "0b5e0000-0000-4000-8000-000000000001"


@pytest.fixture(scope="module")
def laudo():
    base = carregar_base()
    return executar(
        ClienteDemonstracao(), base, "imagem-falsa",
        "Vistoria em canteiro de obra de edificação",
        Configuracao(modelo_visao="demo", modelo_texto="demo",
                     data_referencia=HOJE, max_ciclos=3),
    )


@pytest.fixture()
def candidatas(laudo):
    assert laudo.nao_conformidades, "o laudo de demonstração deixou de ter NC"
    return kaiju.listar_candidatas([("IMG_0001.jpg", laudo), ("IMG_0002.jpg", laudo)], HOJE, OBRA)


# ---------------------------------------------------------------------------
# Chave de reenvio
# ---------------------------------------------------------------------------

def test_chave_externa_e_estavel():
    a = kaiju.chave_externa(OBRA, HOJE, "IMG_0001.jpg", "NR-18|18.9.2")
    assert a == kaiju.chave_externa(OBRA, HOJE, "IMG_0001.jpg", "NR-18|18.9.2")
    assert a.startswith("audnr-") and len(a) == len("audnr-") + 32


@pytest.mark.parametrize("variacao", [
    ("outra-obra", HOJE, "IMG_0001.jpg", "NR-18|18.9.2"),
    (OBRA, date(2026, 8, 24), "IMG_0001.jpg", "NR-18|18.9.2"),
    (OBRA, HOJE, "IMG_0002.jpg", "NR-18|18.9.2"),
    (OBRA, HOJE, "IMG_0001.jpg", "NR-18|18.9.3"),
    (None, HOJE, "IMG_0001.jpg", "NR-18|18.9.2"),
])
def test_chave_externa_muda_com_obra_data_foto_ou_item(variacao):
    assert kaiju.chave_externa(*variacao) != kaiju.chave_externa(OBRA, HOJE, "IMG_0001.jpg", "NR-18|18.9.2")


# ---------------------------------------------------------------------------
# Candidatas e payload
# ---------------------------------------------------------------------------

def test_candidatas_numeram_os_laudos_como_o_relatorio(laudo, candidatas):
    n = len(laudo.nao_conformidades)
    assert [c.numero for c in candidatas] == [1] * n + [2] * n
    assert len({c.chave for c in candidatas}) == 2 * n, "duas fotos com a mesma NC colidiram"


def test_foto_apontada_pelo_inspetor_vai_declarada(laudo):
    dirigido = dataclasses.replace(laudo, riscos_marcados=["Abertura no piso"])
    c = kaiju.listar_candidatas([("IMG_0001.jpg", dirigido)], HOJE, OBRA)[0]
    item = kaiju.montar_item(c, HOJE, "abc1234")
    assert "Achado apontado pelo inspetor nesta foto: Abertura no piso." in item["descricao"]


def test_citacao_vem_do_item_da_base_e_nao_do_texto(candidatas):
    for c in candidatas:
        item = kaiju.montar_item(c, HOJE, "abc1234")
        assert item["norma_ref"] == c.nc.item.nr
        assert item["item_ref"] == c.nc.item.item
        assert item["titulo"].startswith(f"{c.nc.item.nr} {c.nc.item.item} — ")


def test_payload_tem_o_contrato_da_migration_0005(candidatas):
    item = kaiju.montar_item(candidatas[0], HOJE, "abc1234", obra="Torre B", responsavel="Eng. X")
    nc = candidatas[0].nc
    assert item["origem_externa_id"] == candidatas[0].chave
    assert item["severidade"] == nc.gravidade
    assert item["data_identificacao"] == "2026-08-23"
    assert item["prazo"] == date.fromordinal(HOJE.toordinal() + nc.prazo_dias).isoformat()
    assert item["acao"] == {
        "titulo": item["acao"]["titulo"], "descricao": nc.acao_corretiva.strip(),
        "tipo": "corretiva", "prioridade": nc.gravidade, "prazo": item["prazo"],
    }
    json.dumps(kaiju.montar_itens(candidatas, HOJE, "abc1234"))  # vai pela rede como JSON


def test_descricao_leva_o_rastreio_ate_a_foto(candidatas):
    descricao = kaiju.montar_item(candidatas[0], HOJE, "abc1234",
                                  obra="Torre B", responsavel="Eng. X")["descricao"]
    assert candidatas[0].nc.constatacao.strip() in descricao
    assert ("Origem: app-auditoria-nrs, versão abc1234; foto IMG_0001.jpg; laudo nº 1 "
            "da inspeção de 23/08/2026; obra/unidade: Torre B; inspeção: Eng. X") in descricao
    assert "evidência fotográfica arquivada pelo inspetor" in descricao


def test_gravidade_fora_da_escala_vai_sem_severidade(candidatas):
    c = candidatas[0]
    estranha = dataclasses.replace(c, nc=dataclasses.replace(c.nc, gravidade="gravissima"))
    item = kaiju.montar_item(estranha, HOJE, "abc1234")
    assert item["severidade"] is None and item["acao"]["prioridade"] is None


def test_nc_sem_acao_corretiva_vai_sem_acao(candidatas):
    c = candidatas[0]
    sem_acao = dataclasses.replace(c, nc=dataclasses.replace(c.nc, acao_corretiva="  "))
    assert "acao" not in kaiju.montar_item(sem_acao, HOJE, "abc1234")


def test_montar_payload_nao_altera_o_laudo(laudo):
    antes = copy.deepcopy(dataclasses.asdict(laudo))
    kaiju.montar_itens(kaiju.listar_candidatas([("IMG_0001.jpg", laudo)], HOJE, OBRA),
                       HOJE, "abc1234", obra="Torre B")
    assert dataclasses.asdict(laudo) == antes


# ---------------------------------------------------------------------------
# Cliente HTTP, com transporte falso
# ---------------------------------------------------------------------------

class TransporteFalso:
    def __init__(self, *respostas: tuple[int, object]):
        self.respostas = list(respostas)
        self.pedidos: list[dict] = []

    def __call__(self, metodo, url, cabecalhos, corpo):
        self.pedidos.append({"metodo": metodo, "url": url, "cabecalhos": cabecalhos,
                             "corpo": json.loads(corpo) if corpo else None})
        status, dados = self.respostas.pop(0)
        return status, json.dumps(dados).encode("utf-8")


LOGIN_OK = {"access_token": "tok-1", "refresh_token": "ref-1",
            "user": {"id": "u-1", "email": "eng@exemplo.com"}}
URL = "https://projeto.supabase.co"


def _cliente(*respostas):
    t = TransporteFalso(*respostas)
    return kaiju.ClienteKaiju(URL + "/", "chave-publica", transporte=t), t


def test_sem_configuracao_nao_cria_cliente():
    with pytest.raises(kaiju.ErroKaiju):
        kaiju.ClienteKaiju("", "chave")


def test_login_usa_grant_de_senha_com_a_chave_publica():
    cliente, t = _cliente((200, LOGIN_OK))
    sessao = cliente.entrar(" eng@exemplo.com ", "segredo")
    assert (sessao.usuario_id, sessao.email, sessao.access_token) == ("u-1", "eng@exemplo.com", "tok-1")
    p = t.pedidos[0]
    assert p["url"] == URL + "/auth/v1/token?grant_type=password"
    assert p["cabecalhos"]["apikey"] == "chave-publica" and "Authorization" not in p["cabecalhos"]
    assert p["corpo"] == {"email": "eng@exemplo.com", "password": "segredo"}


@pytest.mark.parametrize("resposta", [
    {"error": "invalid_grant", "error_description": "Invalid login credentials"},
    {"code": 400, "error_code": "invalid_credentials", "msg": "Invalid login credentials"},
])
def test_login_errado_vira_mensagem_clara(resposta):
    cliente, _ = _cliente((400, resposta))
    with pytest.raises(kaiju.ErroKaiju, match="E-mail ou senha incorretos"):
        cliente.entrar("eng@exemplo.com", "errada")


def test_vinculos_marcam_quem_pode_enviar():
    cliente, t = _cliente((200, LOGIN_OK), (200, [
        {"empresa_id": "e-2", "papel": "cliente_leitura", "empresas": {"razao_social": "Beta"}},
        {"empresa_id": "e-1", "papel": "tecnico_sst", "empresas": {"razao_social": "Alfa"}},
    ]))
    vinculos = cliente.vinculos(cliente.entrar("eng@exemplo.com", "s"))
    assert [(v.razao_social, v.pode_enviar) for v in vinculos] == [("Alfa", True), ("Beta", False)]
    assert t.pedidos[1]["cabecalhos"]["Authorization"] == "Bearer tok-1"
    assert "usuario_id=eq.u-1" in t.pedidos[1]["url"]


def test_envio_chama_a_rpc_e_separa_criadas_de_existentes():
    cliente, t = _cliente((200, LOGIN_OK), (200, [
        {"origem_externa_id": "audnr-a", "nc_id": "n-1", "situacao": "criada"},
        {"origem_externa_id": "audnr-b", "nc_id": "n-2", "situacao": "ja_existia"},
    ]))
    itens = [{"origem_externa_id": "audnr-a", "descricao": "x"},
             {"origem_externa_id": "audnr-b", "descricao": "y"}]
    r = cliente.enviar(cliente.entrar("eng@exemplo.com", "s"), "e-1", OBRA, itens)
    assert (r.criadas, r.ja_existiam) == (["audnr-a"], ["audnr-b"])
    p = t.pedidos[1]
    assert (p["metodo"], p["url"]) == ("POST", URL + "/rest/v1/rpc/enviar_nc_auditoria")
    assert p["corpo"] == {"p_empresa_id": "e-1", "p_estabelecimento_id": OBRA, "p_itens": itens}


def test_envio_vazio_nem_sai_do_app():
    cliente, t = _cliente((200, LOGIN_OK))
    with pytest.raises(kaiju.ErroKaiju, match="Nenhuma"):
        cliente.enviar(cliente.entrar("eng@exemplo.com", "s"), "e-1", None, [])
    assert len(t.pedidos) == 1


def test_token_expirado_renova_uma_vez_e_repete():
    cliente, t = _cliente(
        (200, LOGIN_OK),
        (401, {"code": "PGRST301", "message": "JWT expired"}),
        (200, {**LOGIN_OK, "access_token": "tok-2", "refresh_token": "ref-2"}),
        (200, [{"origem_externa_id": "audnr-a", "situacao": "criada"}]),
    )
    sessao = cliente.entrar("eng@exemplo.com", "s")
    r = cliente.enviar(sessao, "e-1", None, [{"origem_externa_id": "audnr-a", "descricao": "x"}])
    assert r.criadas == ["audnr-a"]
    assert t.pedidos[2]["url"] == URL + "/auth/v1/token?grant_type=refresh_token"
    assert t.pedidos[2]["corpo"] == {"refresh_token": "ref-1"}
    assert t.pedidos[3]["cabecalhos"]["Authorization"] == "Bearer tok-2"
    assert (sessao.access_token, sessao.refresh_token) == ("tok-2", "ref-2")


@pytest.mark.parametrize("status, codigo, trecho", [
    (403, "42501", "admin ou técnico de SST"),
    (409, "23503", "não pertence à empresa"),
    (404, "PGRST202", "migration 0005"),
    (400, "KJ003", "dado incompleto"),
])
def test_recusa_do_kaiju_vira_mensagem_com_causa(status, codigo, trecho):
    cliente, _ = _cliente((200, LOGIN_OK), (status, {"code": codigo, "message": "detalhe"}))
    with pytest.raises(kaiju.ErroKaiju, match=trecho) as erro:
        cliente.enviar(cliente.entrar("eng@exemplo.com", "s"), "e-1", None,
                       [{"origem_externa_id": "a", "descricao": "x"}])
    assert erro.value.codigo == codigo


def test_sem_rede_vira_erro_do_kaiju_e_nao_excecao_crua():
    def fora_do_ar(*_):
        raise kaiju.ErroKaiju("Sem conexão com o Kaiju: recusado")
    cliente = kaiju.ClienteKaiju(URL, "chave", transporte=fora_do_ar)
    with pytest.raises(kaiju.ErroKaiju, match="Sem conexão"):
        cliente.entrar("eng@exemplo.com", "s")


def test_transporte_padrao_converte_falha_de_rede(monkeypatch):
    import urllib.error

    def recusa(*_, **__):
        raise urllib.error.URLError("connection refused")
    monkeypatch.setattr(kaiju.urllib.request, "urlopen", recusa)
    with pytest.raises(kaiju.ErroKaiju, match="Sem conexão com o Kaiju"):
        kaiju.ClienteKaiju(URL, "chave").entrar("eng@exemplo.com", "s")
