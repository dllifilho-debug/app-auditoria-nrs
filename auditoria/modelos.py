"""Camada de acesso aos modelos, com controle de cota.

O que derrubava o app em produção não era o modelo errado: era o teto de tokens
por minuto da conta gratuita da Groq (8.000 TPM) contra três chamadas por foto.
Uma pausa fixa de 15 s não resolve isso — a janela é de 60 s e o consumo varia
com o tamanho do laudo. Aqui a espera é calculada a partir dos cabeçalhos
`x-ratelimit-*` que a própria API devolve, então o app anda rápido quando há
folga e desacelera exatamente o necessário quando não há.
"""

import os
import re
import time
from dataclasses import dataclass, field
from typing import Any, Callable, Protocol

# --------------------------------------------------------------------------
# Registro de modelos
# --------------------------------------------------------------------------

@dataclass(frozen=True)
class Modelo:
    id: str
    rotulo: str
    visao: bool
    contexto: int
    teto_saida: int
    nota: str = ""
    # Modelo com modo de raciocínio: os tokens de pensamento não passam pelo
    # validador de JSON da Groq, que devolve 400 `json_validate_failed`. Para
    # esses, pedimos o JSON pelo prompt e extraímos do texto.
    json_estrito_confiavel: bool = True
    # Modelo cujo raciocínio pode ser desligado. O agente de visão não precisa
    # raciocinar: precisa descrever. Deixá-lo pensar consome todo o orçamento de
    # saída antes de a resposta começar a ser escrita.
    raciocinio_desligavel: bool = False


VISAO = [
    Modelo("qwen/qwen3.6-27b", "Qwen 3.6 27B (visão)", True, 262_144, 65_536,
           "Único modelo multimodal da Groq, e destino de migração oficial dos "
           "modelos de visão já desligados.",
           json_estrito_confiavel=False, raciocinio_desligavel=True),
]

TEXTO = [
    Modelo("openai/gpt-oss-120b", "GPT-OSS 120B", False, 131_072, 65_536,
           "Produção. Melhor raciocínio normativo disponível na Groq."),
    Modelo("openai/gpt-oss-20b", "GPT-OSS 20B", False, 131_072, 65_536,
           "Mais rápido e barato; use quando a cota estiver apertada."),
    Modelo("qwen/qwen3.6-27b", "Qwen 3.6 27B", False, 262_144, 65_536,
           "Contexto maior, com modo de raciocínio.",
           json_estrito_confiavel=False, raciocinio_desligavel=True),
]

PADRAO_VISAO = VISAO[0].id
PADRAO_TEXTO = TEXTO[0].id

# A Groq desligou modelos quinze vezes desde 2024, em média a cada um ou dois
# meses. Um registro fixo em código envelhece entre uma release e outra, então o
# app aceita um ID digitado à mão: quando a troca vier, ela é feita na barra
# lateral, sem depender de alterar o código.
PAGINA_DEPRECIACOES = "https://console.groq.com/docs/deprecations"


def por_id(modelo_id: str) -> Modelo | None:
    return next((m for m in VISAO + TEXTO if m.id == modelo_id), None)


# --------------------------------------------------------------------------
# Erros com mensagem que ajuda quem está usando o app
# --------------------------------------------------------------------------

class ErroDeAuditoria(Exception):
    """Falha já traduzida para o vocabulário do usuário."""

    def __init__(self, mensagem: str, sugestao: str = "", recuperavel: bool = False):
        super().__init__(mensagem)
        self.mensagem = mensagem
        self.sugestao = sugestao
        self.recuperavel = recuperavel


def traduzir(erro: Exception) -> ErroDeAuditoria:
    import groq

    if isinstance(erro, ErroDeAuditoria):
        return erro
    if isinstance(erro, groq.AuthenticationError):
        return ErroDeAuditoria(
            "Chave da API recusada pela Groq.",
            "Confira a chave em console.groq.com/keys e cole-a novamente.",
        )
    if isinstance(erro, groq.PermissionDeniedError):
        return ErroDeAuditoria(
            "Esta chave não tem permissão para o modelo escolhido.",
            "Selecione outro modelo na barra lateral ou verifique o plano da conta.",
        )
    if isinstance(erro, groq.NotFoundError):
        return ErroDeAuditoria(
            "O modelo selecionado não existe mais na Groq.",
            "Modelos em preview saem sem aviso. Escolha outro na barra lateral.",
        )
    if isinstance(erro, groq.RateLimitError):
        return ErroDeAuditoria(
            "Cota da Groq esgotada (limite de tokens por minuto ou por dia).",
            "Aguarde um minuto, reduza o lote de fotos ou use o modelo mais leve.",
            recuperavel=True,
        )
    if isinstance(erro, groq.APITimeoutError):
        return ErroDeAuditoria(
            "A Groq demorou demais para responder.",
            "Tente de novo; se persistir, reduza o rigor da análise.",
            recuperavel=True,
        )
    if isinstance(erro, groq.APIConnectionError):
        return ErroDeAuditoria(
            "Não foi possível falar com a API da Groq.",
            "Verifique a conexão de rede.",
            recuperavel=True,
        )
    if isinstance(erro, groq.BadRequestError):
        texto = str(erro)
        if RECUSA_JSON.search(texto):
            return ErroDeAuditoria(
                "O modelo não conseguiu responder no formato exigido.",
                "Tente novamente ou escolha outro modelo na barra lateral.",
                recuperavel=True,
            )
        if re.search(r"image|base64|payload|too large|size", texto, re.IGNORECASE):
            return ErroDeAuditoria(
                "A Groq recusou a imagem enviada.",
                "Reduza a resolução de envio na barra lateral.",
            )
        return ErroDeAuditoria(f"A Groq recusou a requisição: {erro}")
    return ErroDeAuditoria(f"Falha inesperada: {type(erro).__name__}: {erro}")


# --------------------------------------------------------------------------
# Contrato do cliente (permite trocar por um dublê no modo demonstração)
# --------------------------------------------------------------------------

class Conversador(Protocol):
    def conversar(
        self, modelo: str, mensagens: list[dict], teto_saida: int = 1200,
        temperatura: float = 0.0, json_estrito: bool = False,
    ) -> str: ...


RE_PENSAMENTO = re.compile(r"<think>.*?</think>", re.DOTALL | re.IGNORECASE)

# A Groq recusa o modo JSON de duas formas, e ambas chegam como 400:
# o modelo não suportar `response_format`, ou aceitá-lo e falhar em produzir
# JSON válido (`json_validate_failed`) — o que acontece com modelos de
# raciocínio, cujos tokens de pensamento não passam pelo validador.
RECUSA_JSON = re.compile(
    r"response_format|json_object|json_validate_failed|failed to validate json",
    re.IGNORECASE,
)
# Parâmetros que melhoram a resposta quando aceitos, mas dos quais o pipeline
# não depende. Se a API recusar qualquer um deles, seguimos sem ele em vez de
# derrubar a auditoria — a Groq troca de modelo a cada poucas semanas e nem
# todos aceitam o mesmo conjunto.
OPCIONAIS = {
    "response_format": RECUSA_JSON,
    "reasoning_effort": re.compile(r"reasoning_effort|reasoning", re.IGNORECASE),
}
RE_DURACAO = re.compile(r"([\d.]+)\s*(ms|s|m|h)")


def _segundos(valor: str | None) -> float:
    """Converte "1.2s", "120ms", "2m30s" — o formato dos cabeçalhos da Groq."""
    if not valor:
        return 0.0
    fatores = {"ms": 0.001, "s": 1.0, "m": 60.0, "h": 3600.0}
    total = sum(float(n) * fatores[u] for n, u in RE_DURACAO.findall(valor))
    if total:
        return total
    try:
        return float(valor)
    except ValueError:
        return 0.0


@dataclass
class Cota:
    """Última leitura dos cabeçalhos de limite devolvidos pela API."""

    tokens_restantes: int | None = None
    tokens_limite: int | None = None
    reset_tokens: float = 0.0
    requisicoes_restantes: int | None = None
    reset_requisicoes: float = 0.0

    def descricao(self) -> str:
        if self.tokens_restantes is None:
            return "cota desconhecida"
        teto = f"/{self.tokens_limite}" if self.tokens_limite else ""
        return f"{self.tokens_restantes}{teto} tokens restantes no minuto"


class ClienteGroq:
    """Cliente com espera adaptativa guiada pelos cabeçalhos de cota."""

    def __init__(
        self,
        api_key: str,
        margem_tokens: int = 1500,
        aviso: Callable[[str], None] | None = None,
        tempo_limite: float = 120.0,
    ):
        import groq

        self._groq = groq
        self.cliente = groq.Groq(api_key=api_key, max_retries=3, timeout=tempo_limite)
        self.margem_tokens = margem_tokens
        self.aviso = aviso or (lambda _m: None)
        self.cota = Cota()
        self.tokens_gastos = 0
        self.chamadas = 0
        # Modelos que já recusaram o modo JSON; não insistimos com eles de novo.
        self.sem_json_estrito: set[str] = set()
        # A última resposta foi cortada por atingir o teto de saída? É o sinal
        # determinístico de truncamento, e evita diagnosticar por adivinhação.
        self.ultimo_corte_por_limite = False

    # -- cota ---------------------------------------------------------------

    def _ler_cabecalhos(self, cabecalhos: Any) -> None:
        def inteiro(nome: str) -> int | None:
            bruto = cabecalhos.get(nome)
            try:
                return int(float(bruto)) if bruto is not None else None
            except (TypeError, ValueError):
                return None

        self.cota = Cota(
            tokens_restantes=inteiro("x-ratelimit-remaining-tokens"),
            tokens_limite=inteiro("x-ratelimit-limit-tokens"),
            reset_tokens=_segundos(cabecalhos.get("x-ratelimit-reset-tokens")),
            requisicoes_restantes=inteiro("x-ratelimit-remaining-requests"),
            reset_requisicoes=_segundos(cabecalhos.get("x-ratelimit-reset-requests")),
        )

    def aguardar_cota(self, custo_previsto: int) -> None:
        """Espera só o tempo que a própria API indica faltar para a janela virar."""
        restantes = self.cota.tokens_restantes
        if restantes is None or restantes >= custo_previsto + self.margem_tokens:
            return
        espera = min(max(self.cota.reset_tokens, 1.0) + 0.5, 65.0)
        self.aviso(
            f"Cota apertada ({restantes} tokens restantes). "
            f"Aguardando {espera:.0f}s até a janela reabrir."
        )
        time.sleep(espera)
        self.cota.tokens_restantes = self.cota.tokens_limite

    # -- chamada ------------------------------------------------------------

    def _chamar(self, parametros: dict):
        crua = self.cliente.chat.completions.with_raw_response.create(**parametros)
        self._ler_cabecalhos(crua.headers)
        return crua.parse()

    def conversar(
        self,
        modelo: str,
        mensagens: list[dict],
        teto_saida: int = 1200,
        temperatura: float = 0.0,
        json_estrito: bool = False,
    ) -> str:
        custo = _estimar_tokens(mensagens) + teto_saida
        self.aguardar_cota(custo)

        conhecido = por_id(modelo)
        parametros: dict[str, Any] = {
            "model": modelo,
            "messages": mensagens,
            # `max_tokens` está depreciado na Groq; o nome atual é este.
            "max_completion_tokens": teto_saida,
            "temperature": temperatura,
        }
        if conhecido is not None and not conhecido.json_estrito_confiavel:
            self.sem_json_estrito.add(modelo)
        if json_estrito and modelo not in self.sem_json_estrito:
            parametros["response_format"] = {"type": "json_object"}
        # Sem isto, um modelo de raciocínio gasta todo o orçamento de saída
        # pensando e é cortado antes de escrever a resposta.
        if conhecido is not None and conhecido.raciocinio_desligavel:
            parametros["reasoning_effort"] = "none"

        resposta = self._chamar_com_degradacao(parametros)

        self.chamadas += 1
        if resposta.usage:
            self.tokens_gastos += resposta.usage.total_tokens or 0

        escolha = resposta.choices[0]
        self.ultimo_corte_por_limite = getattr(escolha, "finish_reason", None) == "length"
        conteudo = escolha.message.content or ""
        return RE_PENSAMENTO.sub("", conteudo).strip()

    def _chamar_com_degradacao(self, parametros: dict):
        """Chama a API descartando um parâmetro opcional a cada recusa.

        A Groq muda de modelo a cada poucas semanas e nem todos aceitam o mesmo
        conjunto de parâmetros. Um 400 por parâmetro não suportado não pode
        custar a auditoria inteira: descartamos o parâmetro implicado, anotamos
        para não insistir, e seguimos.
        """
        for _ in range(len(OPCIONAIS) + 1):
            try:
                return self._chamar(parametros)
            except self._groq.BadRequestError as erro:
                alvo = next(
                    (nome for nome, padrao in OPCIONAIS.items()
                     if nome in parametros and padrao.search(str(erro))),
                    None,
                )
                if alvo is None:
                    raise traduzir(erro) from erro
                self.aviso(
                    f"O modelo {parametros['model']} recusou `{alvo}`; "
                    "repetindo a chamada sem esse parâmetro."
                )
                parametros.pop(alvo)
                if alvo == "response_format":
                    self.sem_json_estrito.add(parametros["model"])
            except Exception as erro:                 # traduzido para o usuário
                raise traduzir(erro) from erro
        raise ErroDeAuditoria(
            "A Groq recusou a requisição mesmo sem os parâmetros opcionais.",
            "Tente outro modelo na barra lateral.",
        )


def _estimar_tokens(mensagens: list[dict]) -> int:
    """Estimativa grosseira mas suficiente para reservar cota antes de gastar."""
    total = 0
    for msg in mensagens:
        conteudo = msg.get("content")
        if isinstance(conteudo, str):
            total += len(conteudo) // 3
        elif isinstance(conteudo, list):
            for parte in conteudo:
                if parte.get("type") == "text":
                    total += len(parte.get("text", "")) // 3
                else:
                    total += 1600          # custo típico de uma imagem reduzida
    return total
