"""Dublê de modelo para o Modo Demonstração.

Não é uma maquete: as respostas atravessam o pipeline inteiro — roteamento de
riscos, montagem de dossiê, aferição determinística, veto do diretor e
renderização. Serve para conhecer o app sem chave de API e, principalmente,
para os testes automatizados exercitarem o caminho real de ponta a ponta.

O truque que o torna honesto: o analista simulado lê o dossiê que o próprio
código montou e escolhe rótulos de lá, em vez de devolver um laudo pronto.
"""

from __future__ import annotations

import json
import re

# Fatos correspondentes à cena clássica de canteiro: abertura no piso tapada
# por chapa solta, entulho e madeira com prego na área de circulação.
FATOS_DEMO = {
    "ambiente": "Área externa de canteiro de obra de edificação, em piso de concreto magro sobre terreno irregular",
    "pessoas": {"presentes": False, "quantidade": 0, "descricao": ""},
    "achados": [
        {
            "fato": "Abertura quadrada no piso, de aproximadamente 60 cm de lado, coberta parcialmente por uma placa rígida de madeira apoiada solta sobre o vão, sem fixação nem travamento visível; sob a placa aparecem barras metálicas paralelas",
            "onde": "centro da imagem",
            "confianca": "alta",
        },
        {
            "fato": "Empilhamento desordenado de sarrafos e peças de madeira de tamanhos variados, com pregos aparentes voltados para cima, junto a um tubo cilíndrico cinza",
            "onde": "canto superior esquerdo",
            "confianca": "alta",
        },
        {
            "fato": "Entulho, cacos e sobras de material espalhados pela área de circulação, sem recipiente de coleta visível",
            "onde": "por toda a extensão do piso",
            "confianca": "alta",
        },
        {
            "fato": "Piso de circulação irregular, com depressões, material solto e ausência de nivelamento",
            "onde": "primeiro plano",
            "confianca": "media",
        },
        {
            "fato": "Nenhum trabalhador presente na cena; nenhuma sinalização, barreira ou cone delimitando a abertura no piso",
            "onde": "cena inteira",
            "confianca": "alta",
        },
    ],
}

# Itens que o analista simulado procura no dossiê, em ordem de preferência,
# com o enquadramento correspondente.
PREFERENCIAS = [
    (
        "18.9.2",
        {
            "constatacao": "A abertura no piso está coberta por placa de madeira apenas apoiada sobre o vão, sem travamento nem fixação à estrutura, e sem qualquer sistema de proteção contra quedas no entorno.",
            "consequencia": "Deslocamento da placa sob pisada ou passagem de carrinho, com queda de trabalhador pelo vão.",
            "gravidade": "critica",
            "acao_corretiva": "Substituir a placa por fechamento provisório de material resistente, travado ou fixado à estrutura, ou instalar sistema de proteção contra quedas no perímetro da abertura; sinalizar até a conclusão.",
            "prazo_dias": 1,
        },
    ),
    (
        "18.16.15",
        {
            "constatacao": "As vias de circulação apresentam entulho, sobras de material e peças de madeira empilhadas de forma desordenada, sem manutenção de passagem desimpedida.",
            "consequencia": "Tropeço e queda de mesmo nível durante a circulação, e obstrução de rota em caso de emergência.",
            "gravidade": "media",
            "acao_corretiva": "Estabelecer rotina diária de organização e limpeza do canteiro, liberando as vias de circulação e destinando o material a área própria de estocagem.",
            "prazo_dias": 7,
        },
    ),
    (
        "18.16.16",
        {
            "constatacao": "Há acúmulo de entulho e sobras de material dispersos pela área, sem uso de equipamento ou calha fechada para remoção.",
            "consequencia": "Dispersão de resíduo e poeira, e agravamento da obstrução das áreas de trabalho.",
            "gravidade": "media",
            "acao_corretiva": "Providenciar recipientes de coleta e remover o entulho por meio de equipamento apropriado ou calha fechada.",
            "prazo_dias": 15,
        },
    ),
    (
        "18.16.4.1",
        {
            "constatacao": "As peças de madeira estão empilhadas com pregos aparentes voltados para cima, sem que tenham sido retirados ou rebatidos.",
            "consequencia": "Perfuração de pé ou mão de quem circular ou manusear o material.",
            "gravidade": "alta",
            "acao_corretiva": "Retirar ou rebater os pregos antes do empilhamento e reorganizar a pilha em local delimitado, fora da via de circulação.",
            "prazo_dias": 3,
        },
    ),
]

PARECER_DEMO = (
    "O risco predominante do local é a abertura no piso com fechamento não travado, "
    "que caracteriza exposição a queda com altura desconhecida e exige providência imediata. "
    "As demais constatações são de organização do canteiro e concorrem para acidente de "
    "mesmo nível. Não há trabalhador na cena, de modo que nenhuma conclusão sobre uso de "
    "EPI ou capacitação pode ser extraída desta imagem."
)


class ClienteDemonstracao:
    """Implementa o mesmo contrato de `ClienteGroq`, sem rede."""

    def __init__(self) -> None:
        self.chamadas = 0
        self.tokens_gastos = 0
        self.cota = None

    def conversar(
        self, modelo: str, mensagens: list[dict], teto_saida: int = 1200,
        temperatura: float = 0.0, json_estrito: bool = False,
    ) -> str:
        self.chamadas += 1
        prompt = _texto_do_prompt(mensagens)

        if "perito em documentação fotográfica" in prompt:
            return json.dumps(FATOS_DEMO, ensure_ascii=False)
        if "DOSSIÊ NORMATIVO" in prompt:
            return json.dumps(self._analisar(prompt), ensure_ascii=False)
        if "Diretor Técnico" in prompt:
            return json.dumps({"vetados": [], "ajustes": [], "parecer": PARECER_DEMO},
                              ensure_ascii=False)
        return "{}"

    def _analisar(self, prompt: str) -> dict:
        """Escolhe rótulos reais do dossiê que o pipeline acabou de montar."""
        disponiveis = dict(re.findall(r"\[(D\d+)\]\s+NR-\d{2}\s+(\S+)", prompt))
        por_item = {numero: rotulo for rotulo, numero in disponiveis.items()}

        nao_conformidades = []
        for numero, corpo in PREFERENCIAS:
            rotulo = por_item.get(numero)
            if rotulo:
                nao_conformidades.append({"dossie": rotulo, **corpo})

        if not nao_conformidades and disponiveis:
            primeiro = sorted(disponiveis, key=lambda r: int(r[1:]))[0]
            nao_conformidades.append({
                "dossie": primeiro,
                "constatacao": "Condição observada na imagem em desacordo com o item citado.",
                "consequencia": "Exposição dos trabalhadores ao risco descrito.",
                "gravidade": "media",
                "acao_corretiva": "Regularizar a condição conforme o requisito normativo.",
                "prazo_dias": 15,
            })

        return {
            "nao_conformidades": nao_conformidades,
            "sem_enquadramento": [
                "Não é possível determinar pela imagem a profundidade do vão sob a abertura "
                "nem a existência de projeto para a estrutura metálica visível abaixo dela."
            ],
            "conformidades": [],
        }


def _texto_do_prompt(mensagens: list[dict]) -> str:
    partes: list[str] = []
    for msg in mensagens:
        conteudo = msg.get("content")
        if isinstance(conteudo, str):
            partes.append(conteudo)
        elif isinstance(conteudo, list):
            partes += [p.get("text", "") for p in conteudo if p.get("type") == "text"]
    return "\n".join(partes)
