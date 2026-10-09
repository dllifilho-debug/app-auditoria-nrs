"""Envio das não conformidades do lote para o KAIJU SGI.

O Kaiju guarda NC e plano de ação no Supabase, com isolamento entre empresas por
RLS. O app grava lá **com o login do próprio engenheiro** (decisão registrada em
`kaiju-sgi/docs/CONTEXTO.md`): nenhum segredo do Kaiju vive aqui, só a URL e a
chave pública, e quem decide o que cada usuário pode gravar é o banco.

Duas metades, de propósito separadas:

- `listar_candidatas` / `montar_itens` — puras, testáveis sem rede. Leem o
  `Laudo` já emitido e nunca o alteram. A citação vem do `Item` da base, como
  no relatório: nada escrito por modelo vira `norma_ref`/`item_ref`.
- `ClienteKaiju` — HTTP com a biblioteca padrão (Auth e PostgREST do Supabase),
  com o transporte injetável para teste. Sem dependência nova no deploy.

O envio é uma chamada só à função `enviar_nc_auditoria` (migration 0005 do
kaiju-sgi): o lote entra inteiro ou não entra, e reenviar é seguro — item que já
existe volta como "ja_existia" e não é sobrescrito no Kaiju.
"""

import hashlib
import json
import urllib.error
import urllib.request
from dataclasses import dataclass, field
from datetime import date, timedelta
from typing import Callable, Sequence

from .pipeline import GRAVIDADE_ORDEM, Laudo, NaoConformidade

ORIGEM_APP = "app-auditoria-nrs"
PAPEIS_QUE_ENVIAM = ("admin", "tecnico_sst")
TIMEOUT_S = 30


class ErroKaiju(RuntimeError):
    """Falha de login, permissão ou rede, com mensagem pronta para a tela."""

    def __init__(self, mensagem: str, codigo: str = "", status: int = 0):
        super().__init__(mensagem)
        self.codigo = codigo
        self.status = status


# ---------------------------------------------------------------------------
# Payload — puro
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class Candidata:
    """Uma NC do lote que pode ser enviada, com a chave que a identifica no Kaiju."""
    chave: str
    foto: str
    numero: int                      # nº do laudo no lote, o mesmo do relatório
    nc: NaoConformidade
    apontada: tuple[str, ...] = ()   # riscos marcados pelo inspetor nessa foto


def chave_externa(estabelecimento_id: str | None, data_inspecao: date,
                  foto: str, item_id: str) -> str:
    """Identidade estável da NC entre envios.

    Muda se mudar a obra, a data, a foto ou o item — e só nesses casos. A obra
    entra porque nome de arquivo se repete entre câmeras ("IMG_0001.jpg"):
    deduplicar duas NCs reais numa só seria perda silenciosa, pior que duplicata.
    """
    bruto = "|".join([estabelecimento_id or "", data_inspecao.isoformat(), foto, item_id])
    return "audnr-" + hashlib.sha256(bruto.encode("utf-8")).hexdigest()[:32]


def listar_candidatas(
    resultados: Sequence[tuple[str, Laudo]],
    data_inspecao: date,
    estabelecimento_id: str | None,
) -> list[Candidata]:
    candidatas: list[Candidata] = []
    for numero, (foto, laudo) in enumerate(resultados, 1):
        for nc in laudo.nao_conformidades:
            candidatas.append(Candidata(
                chave=chave_externa(estabelecimento_id, data_inspecao, foto, nc.item.id),
                foto=foto,
                numero=numero,
                nc=nc,
                apontada=tuple(laudo.riscos_marcados),
            ))
    return candidatas


def _curto(texto: str, limite: int = 90) -> str:
    texto = " ".join(texto.split())
    if len(texto) <= limite:
        return texto
    return texto[: limite - 1].rsplit(" ", 1)[0].rstrip(",;:") + "…"


def _descricao(c: Candidata, data_inspecao: date, versao: str,
               obra: str, responsavel: str) -> str:
    nc = c.nc
    partes = [nc.constatacao.strip()]
    if nc.consequencia.strip():
        partes.append(f"Consequência: {nc.consequencia.strip()}")
    if nc.complementos:
        citados = "; ".join(f"{i.nr} item {i.item}" for i in nc.complementos)
        partes.append(f"Citação complementar: {citados}.")
    # Mesma declaração que o sumário faz: foto dirigida muda o valor de evidência.
    if c.apontada:
        partes.append("Achado apontado pelo inspetor nesta foto: " + "; ".join(c.apontada) + ".")
    rastreio = (
        f"Origem: {ORIGEM_APP}, versão {versao}; foto {c.foto}; laudo nº {c.numero} "
        f"da inspeção de {data_inspecao:%d/%m/%Y}"
    )
    if obra.strip():
        rastreio += f"; obra/unidade: {obra.strip()}"
    if responsavel.strip():
        rastreio += f"; inspeção: {responsavel.strip()}"
    partes.append(rastreio + " — evidência fotográfica arquivada pelo inspetor.")
    return "\n\n".join(partes)


def montar_item(c: Candidata, data_inspecao: date, versao: str,
                obra: str = "", responsavel: str = "") -> dict:
    nc = c.nc
    # Gravidade fora da escala do Kaiju derrubaria o lote inteiro no enum; vai sem.
    severidade = nc.gravidade if nc.gravidade in GRAVIDADE_ORDEM else None
    prazo = (data_inspecao + timedelta(days=max(nc.prazo_dias, 0))).isoformat()
    titulo = f"{nc.item.nr} {nc.item.item} — {_curto(nc.rotulo_risco or nc.constatacao, 70)}"

    item: dict = {
        "origem_externa_id": c.chave,
        "titulo": titulo,
        "descricao": _descricao(c, data_inspecao, versao, obra, responsavel),
        "norma_ref": nc.item.nr,
        "item_ref": nc.item.item,
        "severidade": severidade,
        "data_identificacao": data_inspecao.isoformat(),
        "prazo": prazo,
    }
    if nc.acao_corretiva.strip():
        item["acao"] = {
            "titulo": _curto(nc.acao_corretiva, 90),
            "descricao": nc.acao_corretiva.strip(),
            "tipo": "corretiva",
            "prioridade": severidade,
            "prazo": prazo,
        }
    return item


def montar_itens(candidatas: Sequence[Candidata], data_inspecao: date, versao: str,
                 obra: str = "", responsavel: str = "") -> list[dict]:
    return [montar_item(c, data_inspecao, versao, obra, responsavel) for c in candidatas]


# ---------------------------------------------------------------------------
# Cliente HTTP — Supabase Auth + PostgREST
# ---------------------------------------------------------------------------

@dataclass
class Sessao:
    usuario_id: str
    email: str
    access_token: str
    refresh_token: str


@dataclass(frozen=True)
class Vinculo:
    empresa_id: str
    razao_social: str
    papel: str

    @property
    def pode_enviar(self) -> bool:
        return self.papel in PAPEIS_QUE_ENVIAM


@dataclass(frozen=True)
class Obra:
    id: str
    nome: str
    tipo: str


@dataclass
class ResultadoEnvio:
    criadas: list[str] = field(default_factory=list)
    ja_existiam: list[str] = field(default_factory=list)


# (método, url, cabeçalhos, corpo) → (status HTTP, corpo da resposta)
Transporte = Callable[[str, str, dict, bytes | None], tuple[int, bytes]]


def _transporte_urllib(metodo: str, url: str, cabecalhos: dict,
                       corpo: bytes | None) -> tuple[int, bytes]:
    pedido = urllib.request.Request(url, data=corpo, headers=cabecalhos, method=metodo)
    try:
        with urllib.request.urlopen(pedido, timeout=TIMEOUT_S) as resposta:
            return resposta.status, resposta.read()
    except urllib.error.HTTPError as erro:
        return erro.code, erro.read()
    except (urllib.error.URLError, TimeoutError, OSError) as erro:
        raise ErroKaiju(f"Sem conexão com o Kaiju: {erro}") from erro


# Códigos do Postgres/PostgREST que chegam ao usuário com causa conhecida.
MENSAGENS = {
    "42501": "Sem permissão para gravar NC nesta empresa — o envio exige papel "
             "admin ou técnico de SST no Kaiju.",
    "23503": "A obra escolhida não pertence à empresa selecionada.",
    "23514": "Prazo anterior à data da inspeção — confira a data informada.",
    "22P02": "Valor fora do formato esperado pelo Kaiju (gravidade ou data).",
    "KJ003": "Lote recusado pelo Kaiju por dado incompleto.",
    "PGRST202": "A função de envio não existe neste Kaiju — a migration 0005 "
                "(enviar_nc_auditoria) ainda não foi aplicada.",
    "PGRST301": "Sessão do Kaiju expirada — entre de novo.",
}


def _erro_da_resposta(status: int, corpo: bytes) -> ErroKaiju:
    try:
        dados = json.loads(corpo or b"{}")
    except ValueError:
        dados = {}
    if not isinstance(dados, dict):
        dados = {}
    # Auth novo manda `code` numérico (o HTTP) e a causa em `error_code`; o antigo, em
    # `error`. PostgREST manda o SQLSTATE em `code`.
    codigo = str(dados.get("error_code") or dados.get("code") or dados.get("error") or "")
    detalhe = (dados.get("message") or dados.get("msg")
               or dados.get("error_description") or "")
    if codigo in ("invalid_grant", "invalid_credentials"):
        return ErroKaiju("E-mail ou senha incorretos.", codigo, status)
    if codigo == "email_not_confirmed":
        return ErroKaiju("E-mail ainda não confirmado no Kaiju.", codigo, status)
    base = MENSAGENS.get(codigo, f"O Kaiju recusou a operação (HTTP {status}).")
    return ErroKaiju(f"{base} [{codigo or status}] {detalhe}".strip(), codigo, status)


class ClienteKaiju:
    def __init__(self, url: str, chave_publica: str,
                 transporte: Transporte = _transporte_urllib):
        if not url or not chave_publica:
            raise ErroKaiju("Kaiju não configurado (URL ou chave pública ausente).")
        self.url = url.rstrip("/")
        self.chave = chave_publica
        self._transporte = transporte

    # -- baixo nível ---------------------------------------------------------

    def _pedir(self, metodo: str, caminho: str, corpo: dict | None = None,
               token: str | None = None) -> object:
        cabecalhos = {
            "apikey": self.chave,
            "Content-Type": "application/json",
            "Accept": "application/json",
        }
        if token:
            cabecalhos["Authorization"] = f"Bearer {token}"
        dados = json.dumps(corpo).encode("utf-8") if corpo is not None else None
        status, resposta = self._transporte(metodo, self.url + caminho, cabecalhos, dados)
        if not 200 <= status < 300:
            raise _erro_da_resposta(status, resposta)
        try:
            return json.loads(resposta) if resposta else None
        except ValueError as erro:
            raise ErroKaiju("Resposta do Kaiju fora do formato esperado.") from erro

    def _autenticado(self, sessao: Sessao, metodo: str, caminho: str,
                     corpo: dict | None = None) -> object:
        """Chama com o token da sessão; se expirou, renova uma vez e repete.

        Um lote de 100 fotos leva horas, e o token de acesso do Supabase dura
        bem menos: sem renovar, o engenheiro descobriria isso só no botão final.
        """
        try:
            return self._pedir(metodo, caminho, corpo, sessao.access_token)
        except ErroKaiju as erro:
            if erro.codigo != "PGRST301" and erro.status != 401:
                raise
        self.renovar(sessao)
        return self._pedir(metodo, caminho, corpo, sessao.access_token)

    # -- Auth ----------------------------------------------------------------

    def entrar(self, email: str, senha: str) -> Sessao:
        if not email.strip() or not senha:
            raise ErroKaiju("Informe e-mail e senha do Kaiju.")
        dados = self._pedir("POST", "/auth/v1/token?grant_type=password",
                            {"email": email.strip(), "password": senha})
        return self._sessao_de(dados)

    def renovar(self, sessao: Sessao) -> None:
        dados = self._pedir("POST", "/auth/v1/token?grant_type=refresh_token",
                            {"refresh_token": sessao.refresh_token})
        nova = self._sessao_de(dados)
        sessao.access_token, sessao.refresh_token = nova.access_token, nova.refresh_token

    @staticmethod
    def _sessao_de(dados: object) -> Sessao:
        try:
            usuario = dados["user"]  # type: ignore[index]
            return Sessao(usuario_id=usuario["id"], email=usuario.get("email", ""),
                          access_token=dados["access_token"],  # type: ignore[index]
                          refresh_token=dados["refresh_token"])  # type: ignore[index]
        except (KeyError, TypeError) as erro:
            raise ErroKaiju("Resposta de login do Kaiju fora do formato esperado.") from erro

    # -- Leitura (RLS devolve só o que o usuário pode ver) --------------------

    def vinculos(self, sessao: Sessao) -> list[Vinculo]:
        linhas = self._autenticado(
            sessao, "GET",
            "/rest/v1/membros?select=empresa_id,papel,empresas(razao_social)"
            f"&usuario_id=eq.{sessao.usuario_id}&ativo=eq.true",
        ) or []
        vinculos = [
            Vinculo(empresa_id=l["empresa_id"], papel=l["papel"],
                    razao_social=(l.get("empresas") or {}).get("razao_social", "—"))
            for l in linhas  # type: ignore[union-attr]
        ]
        return sorted(vinculos, key=lambda v: v.razao_social.lower())

    def obras(self, sessao: Sessao, empresa_id: str) -> list[Obra]:
        linhas = self._autenticado(
            sessao, "GET",
            f"/rest/v1/estabelecimentos?select=id,nome,tipo&empresa_id=eq.{empresa_id}"
            "&ativo=eq.true&order=nome",
        ) or []
        return [Obra(id=l["id"], nome=l["nome"], tipo=l["tipo"]) for l in linhas]  # type: ignore[union-attr]

    # -- Envio ---------------------------------------------------------------

    def enviar(self, sessao: Sessao, empresa_id: str, estabelecimento_id: str | None,
               itens: list[dict]) -> ResultadoEnvio:
        if not itens:
            raise ErroKaiju("Nenhuma não conformidade selecionada para enviar.")
        resposta = self._autenticado(
            sessao, "POST", "/rest/v1/rpc/enviar_nc_auditoria",
            {"p_empresa_id": empresa_id, "p_estabelecimento_id": estabelecimento_id,
             "p_itens": itens},
        )
        resultado = ResultadoEnvio()
        for linha in resposta or []:  # type: ignore[union-attr]
            alvo = resultado.criadas if linha.get("situacao") == "criada" else resultado.ja_existiam
            alvo.append(linha.get("origem_externa_id", ""))
        return resultado
