"""Contabilidade de consumo diário de tokens.

O teto que aperta na Groq é o diário, não o por minuto. A cota que a API informa
no cabeçalho é da janela de um minuto e não diz nada sobre quanto resta do dia —
sem somar aqui, só se descobre o limite ao esbarrar nele no meio de um lote.

A lógica vive separada da interface para poder ser testada: a regra de virada de
data é justamente a que ninguém percebe estar quebrada até a meia-noite.
"""

from dataclasses import dataclass, field
from datetime import date

ORCAMENTO_GRATUITO = 200_000        # teto diário de tokens do plano gratuito


@dataclass
class Consumo:
    """Quanto já se gastou no dia corrente."""

    dia: str = field(default_factory=lambda: date.today().isoformat())
    tokens: int = 0
    imagens: int = 0
    chamadas: int = 0

    def registrar(self, tokens: int, imagens: int, chamadas: int, hoje: date | None = None):
        """Soma uma execução, zerando tudo se o dia virou."""
        agora = (hoje or date.today()).isoformat()
        if agora != self.dia:
            self.dia, self.tokens, self.imagens, self.chamadas = agora, 0, 0, 0
        self.tokens += max(tokens, 0)
        self.imagens += max(imagens, 0)
        self.chamadas += max(chamadas, 0)
        return self

    @property
    def media_por_imagem(self) -> int:
        return self.tokens // self.imagens if self.imagens else 0

    def restante(self, orcamento: int) -> int:
        return max(orcamento - self.tokens, 0)

    def imagens_que_ainda_cabem(self, orcamento: int) -> int | None:
        """Quantas imagens ainda cabem no teto, no ritmo medido até agora.

        Devolve None enquanto não houver medição — estimar sem dado próprio
        seria devolver um palpite com cara de número."""
        media = self.media_por_imagem
        return self.restante(orcamento) // media if media else None

    def fracao_usada(self, orcamento: int) -> float:
        return min(self.tokens / orcamento, 1.0) if orcamento > 0 else 1.0
