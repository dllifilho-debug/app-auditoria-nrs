"""Contabilidade de consumo diário de tokens.

O teto que aperta na Groq é o diário, não o por minuto. A cota que a API informa
no cabeçalho é da janela de um minuto e não diz nada sobre quanto resta do dia —
sem somar aqui, só se descobre o limite ao esbarrar nele no meio de um lote.

**O teto diário é por modelo, não da conta.** Confirmado no console da Groq: cada
modelo tem seu próprio balde de 200.000 tokens por dia. Somar os três modelos de
uma foto num balde só, como este arquivo fazia, subestimava a capacidade em mais
de um terço — o Olho e os dois agentes de texto comem de baldes diferentes, e
quem manda é o mais apertado dos três, não a soma. Na prática a tela mandava
parar de auditar com cota sobrando.

A lógica vive separada da interface para poder ser testada: a regra de virada de
data é justamente a que ninguém percebe estar quebrada até a meia-noite.
"""

from dataclasses import dataclass, field
from datetime import date

ORCAMENTO_GRATUITO = 200_000        # teto diário de tokens, POR MODELO


@dataclass
class Consumo:
    """Quanto já se gastou no dia corrente."""

    dia: str = field(default_factory=lambda: date.today().isoformat())
    tokens: int = 0
    imagens: int = 0
    chamadas: int = 0
    # Tokens por modelo. Vazio quando a medição não veio discriminada — aí as
    # contas caem no modo antigo, que é pessimista mas não inventa número.
    por_modelo: dict[str, int] = field(default_factory=dict)

    def registrar(
        self,
        tokens: int,
        imagens: int,
        chamadas: int,
        hoje: date | None = None,
        por_modelo: dict[str, int] | None = None,
    ):
        """Soma uma execução, zerando tudo se o dia virou."""
        agora = (hoje or date.today()).isoformat()
        if agora != self.dia:
            self.dia, self.tokens, self.imagens, self.chamadas = agora, 0, 0, 0
            self.por_modelo = {}
        self.tokens += max(tokens, 0)
        self.imagens += max(imagens, 0)
        self.chamadas += max(chamadas, 0)
        for modelo, gasto in (por_modelo or {}).items():
            self.por_modelo[modelo] = self.por_modelo.get(modelo, 0) + max(gasto, 0)
        return self

    def media_do_modelo(self, modelo: str) -> int:
        """Tokens por imagem gastos naquele modelo."""
        return self.por_modelo.get(modelo, 0) // self.imagens if self.imagens else 0

    def cabem_no_modelo(self, modelo: str, orcamento: int) -> int | None:
        """Quantas imagens ainda cabem no balde daquele modelo."""
        media = self.media_do_modelo(modelo)
        if not media:
            return None
        return max(orcamento - self.por_modelo.get(modelo, 0), 0) // media

    def modelo_mais_apertado(self, orcamento: int) -> tuple[str, int] | None:
        """O modelo que vai bater no teto primeiro, e em quantas imagens.

        É ele que decide o lote — não adianta sobrar cota no balde do Diretor
        se o do Olho acabou, porque toda foto passa pelos três.
        """
        candidatos = [
            (modelo, cabem)
            for modelo in self.por_modelo
            if (cabem := self.cabem_no_modelo(modelo, orcamento)) is not None
        ]
        if not candidatos:
            return None
        return min(candidatos, key=lambda p: p[1])

    @property
    def media_por_imagem(self) -> int:
        return self.tokens // self.imagens if self.imagens else 0

    def restante(self, orcamento: int) -> int:
        return max(orcamento - self.tokens, 0)

    def imagens_que_ainda_cabem(self, orcamento: int) -> int | None:
        """Quantas imagens ainda cabem no teto, no ritmo medido até agora.

        Com medição por modelo, é o balde mais apertado que responde. Sem ela,
        cai no cálculo antigo sobre o total — que trata os baldes como um só e
        portanto subestima, mas errar para baixo aqui só custa fotos que
        caberiam, enquanto errar para cima custa um lote interrompido.

        Devolve None enquanto não houver medição nenhuma: estimar sem dado
        próprio seria devolver um palpite com cara de número.
        """
        if (apertado := self.modelo_mais_apertado(orcamento)) is not None:
            return apertado[1]
        media = self.media_por_imagem
        return self.restante(orcamento) // media if media else None

    def fracao_usada(self, orcamento: int) -> float:
        """Quanto do teto já foi, medido pelo balde mais cheio."""
        if orcamento <= 0:
            return 1.0
        gasto = max(self.por_modelo.values(), default=self.tokens)
        return min(gasto / orcamento, 1.0)
