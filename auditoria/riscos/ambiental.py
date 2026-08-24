"""Riscos de EPI, emergência, agentes ambientais e gestão de SST.

Domínio que cobre o que aparece na foto de qualquer estabelecimento — o
trabalhador e o que ele veste, a rota de fuga, o extintor, o tambor de produto
químico, a boca de visita — mais os documentos de gestão que a inspeção cobra
no mesmo ato (PGR, ordem de serviço, CIPA, PCMSO, SESMT).

Duas armadilhas motivaram o cuidado deste mapa:

1. **EPI sem gente.** Cobrar "trabalhador sem capacete" numa foto de canteiro
   vazio é o erro mais comum do app. Todo risco cuja constatação exija ver uma
   pessoa carrega `exige_pessoa: True`; o restante do pipeline usa esse campo
   para suprimir o achado quando não há trabalhador visível.

2. **Item que não existe mais.** A NR-23 de 2022 é um texto curto de sete
   itens: não há mais "23.12.3", não há mais item de extintor, de carga, de
   distância máxima de caminhamento. O que sustenta a exigência sobre extintor
   hoje é o 23.3.1 (conformidade com a legislação estadual de incêndio) somado
   ao 26.3.2 (cor de identificação de equipamento de segurança). O mesmo vale
   para ruído: a NR-15 Anexo 1 não está indexada como item na base, e quem
   sustenta a exigência é a NR-09.
"""

from __future__ import annotations

RISCOS: dict[str, dict] = {
    # ------------------------------------------------------------------
    # EPI — todos dependem de haver trabalhador na cena
    # ------------------------------------------------------------------
    "epi_nao_utilizado": {
        "rotulo": "Trabalhador sem o EPI exigido para a atividade",
        "descricao": (
            "Trabalhador visível executando atividade sem o equipamento de proteção "
            "individual exigido pelo risco da tarefa (capacete, óculos, protetor "
            "auricular, luva, calçado de segurança, cinto)."
        ),
        "sinais": [
            "sem capacete",
            "sem oculos de protecao",
            "sem luva",
            "de chinelo",
            "sem protetor auricular",
            "trabalhador sem epi",
            "de bermuda e sandalia",
            "sem bota",
        ],
        "itens": ["NR-06 6.5.1", "NR-06 6.6.1"],
        "gravidade_base": "alta",
        "exige_pessoa": True,
    },
    "epi_danificado_ou_inadequado": {
        "rotulo": "EPI danificado, improvisado ou inadequado ao risco",
        "descricao": (
            "Trabalhador usando EPI visivelmente deteriorado (capacete trincado, luva "
            "rasgada, lente arranhada, cinto puído) ou peça improvisada que não é EPI, "
            "como pano no rosto, luva de tecido comum ou óculos de sol."
        ),
        "sinais": [
            "capacete trincado",
            "luva rasgada",
            "epi velho",
            "pano no rosto",
            "oculos quebrado",
            "bota furada",
            "mascara de pano",
            "epi improvisado",
        ],
        "itens": ["NR-06 6.5.1", "NR-06 6.5.2"],
        "gravidade_base": "alta",
        "exige_pessoa": True,
    },
    "epi_usado_de_forma_incorreta": {
        "rotulo": "EPI presente mas usado de forma incorreta",
        "descricao": (
            "Trabalhador porta o EPI mas não o utiliza como proteção: capacete sem "
            "jugular ou apoiado na nuca, óculos na testa, protetor auricular pendurado "
            "no pescoço, máscara sob o queixo, cinto desconectado do ponto de ancoragem."
        ),
        "sinais": [
            "capacete na nuca",
            "oculos na testa",
            "protetor auricular pendurado no pescoco",
            "mascara no queixo",
            "capacete sem jugular",
            "cinto solto",
            "epi pendurado",
        ],
        "itens": ["NR-06 6.5.1", "NR-06 6.6.1"],
        "gravidade_base": "alta",
        "exige_pessoa": True,
    },
    "epi_sem_certificado_de_aprovacao": {
        "rotulo": "EPI em uso sem marcação de Certificado de Aprovação",
        "descricao": (
            "EPI vestido pelo trabalhador sem a marcação legível de nome do fabricante, "
            "lote e número do CA, ou com marcação apagada, coberta de tinta ou raspada."
        ),
        "sinais": [
            "epi sem ca",
            "capacete sem etiqueta",
            "sem numero de ca",
            "etiqueta apagada",
            "epi generico",
            "luva sem marcacao",
            "epi sem selo",
        ],
        "itens": ["NR-06 6.4.1", "NR-06 6.9.3"],
        "gravidade_base": "media",
        "exige_pessoa": True,
    },
    "epi_guarda_e_conservacao_inadequadas": {
        "rotulo": "EPI guardado, disponibilizado ou conservado de forma inadequada",
        "descricao": (
            "Equipamentos de proteção individual largados no chão, na terra, dentro de "
            "caçamba ou em cima de material, sujos ou molhados, sem local próprio de "
            "guarda, ou disponibilizados fora da embalagem original e sem identificação."
        ),
        "sinais": [
            "epi jogado no chao",
            "capacete no barro",
            "luva suja largada",
            "epi na caçamba",
            "protetor auricular no chao",
            "epi sem lugar de guarda",
            "mascara solta em cima da bancada",
        ],
        "itens": ["NR-06 6.5.1", "NR-06 6.5.1.2"],
        "gravidade_base": "media",
    },
    # ------------------------------------------------------------------
    # Prevenção e combate a incêndio / saídas de emergência
    # ------------------------------------------------------------------
    "extintor_obstruido_ou_inacessivel": {
        "rotulo": "Extintor de incêndio obstruído ou sem acesso livre",
        "descricao": (
            "Extintor, hidrante ou outro equipamento de combate a incêndio bloqueado por "
            "material, mobiliário, veículo ou entulho, ou removido do suporte e deitado "
            "no chão, de modo que não possa ser alcançado de imediato."
        ),
        "sinais": [
            "extintor atras de caixa",
            "extintor bloqueado",
            "extintor no chao",
            "material na frente do extintor",
            "hidrante obstruido",
            "extintor atras de empilhadeira",
            "acesso ao extintor fechado",
        ],
        # 26.3.2 trata da COR de identificação do equipamento de segurança — é o
        # enquadramento de "extintor sem sinalização", não o de extintor obstruído.
        # Quem proíbe obstruir equipamento de combate a incêndio é a NR-11 11.3.2.
        "itens": ["NR-23 23.3.1", "NR-11 11.3.2"],
        "gravidade_base": "alta",
    },
    "extintor_sem_sinalizacao": {
        "rotulo": "Extintor sem sinalização ou demarcação de piso",
        "descricao": (
            "Extintor ou hidrante instalado sem placa de identificação acima do "
            "equipamento e sem a demarcação vermelha no piso à sua frente, tornando o "
            "equipamento de segurança impossível de localizar à distância."
        ),
        "sinais": [
            "extintor sem placa",
            "sem sinalizacao do extintor",
            "piso sem faixa vermelha",
            "extintor escondido na parede",
            "sem placa de incendio",
            "extintor sem identificacao",
            "nao da pra achar o extintor",
        ],
        "itens": ["NR-26 26.3.2", "NR-26 26.3.1", "NR-23 23.3.1"],
        "gravidade_base": "media",
    },
    "extintor_vencido_ou_sem_manutencao": {
        "rotulo": "Extintor com carga vencida, lacre rompido ou sem inspeção registrada",
        "descricao": (
            "Extintor com etiqueta de recarga vencida, manômetro fora da faixa verde, lacre "
            "rompido ou mangote danificado. A NR-23 não fixa ela própria a periodicidade de "
            "manutenção: ela remete à legislação estadual de incêndio e às normas técnicas "
            "oficiais, e é esse comando que o extintor vencido descumpre."
        ),
        "sinais": [
            "extintor vencido",
            "extintor sem lacre",
            "etiqueta de recarga vencida",
            "manometro do extintor no vermelho",
            "extintor descarregado",
            "extintor enferrujado",
            "mangueira do extintor rachada",
        ],
        "itens": ["NR-23 23.3.1"],
        "gravidade_base": "media",
    },
    "saida_emergencia_obstruida": {
        "rotulo": "Saída de emergência ou via de passagem obstruída",
        "descricao": (
            "Porta de saída, corredor, escada ou via de passagem de emergência bloqueada "
            "por material empilhado, paletes, mobiliário, veículo ou entulho, impedindo o "
            "abandono rápido do local."
        ),
        "sinais": [
            "saida bloqueada",
            "porta de emergencia com caixa na frente",
            "corredor entulhado",
            "palete na frente da porta",
            "escada com material empilhado",
            "passagem obstruida",
            "carrinho na frente da saida",
        ],
        "itens": ["NR-23 23.3.4.1", "NR-23 23.3.3"],
        "gravidade_base": "critica",
    },
    "saida_emergencia_trancada": {
        "rotulo": "Saída de emergência fechada à chave ou presa",
        "descricao": (
            "Porta de saída de emergência trancada com cadeado, corrente, tranca ou "
            "chave durante a jornada, ou com dispositivo que impeça a abertura pelo lado "
            "de dentro do estabelecimento."
        ),
        "sinais": [
            "porta trancada",
            "cadeado na saida",
            "corrente na porta de emergencia",
            "saida presa com arame",
            "porta chaveada",
            "tranca no portao de saida",
            "barra antipanico bloqueada",
        ],
        "itens": ["NR-23 23.3.5", "NR-23 23.3.5.1"],
        "gravidade_base": "critica",
    },
    "saida_emergencia_sem_sinalizacao": {
        "rotulo": "Saída de emergência sem identificação ou indicação de direção",
        "descricao": (
            "Aberturas, saídas e vias de passagem de emergência sem placa de saída, sem "
            "seta indicando a direção do escape ou com sinalização apagada, queimada ou "
            "coberta."
        ),
        "sinais": [
            "sem placa de saida",
            "sem seta de rota de fuga",
            "placa de saida apagada",
            "nao tem indicacao de saida",
            "luminaria de saida queimada",
            "sinalizacao de escape coberta",
            "corredor sem sinalizacao de saida",
        ],
        "itens": ["NR-23 23.3.4", "NR-26 26.3.1"],
        "gravidade_base": "alta",
    },
    "procedimento_de_emergencia_ausente": {
        "rotulo": "Local sem meios e informação de resposta a emergência",
        "descricao": (
            "Estabelecimento sem os recursos visíveis de resposta a emergência exigidos "
            "pelos seus riscos: sem ponto de encontro, sem material de primeiros "
            "socorros, sem alarme, sem informação afixada sobre abandono do local."
        ),
        "sinais": [
            "sem ponto de encontro",
            "sem caixa de primeiros socorros",
            "sem alarme",
            "nao tem plano de emergencia no quadro",
            "sem chuveiro lava olhos",
            "sem placa de abandono",
            "nada indicando o que fazer em emergencia",
        ],
        "itens": ["NR-01 1.5.6.1", "NR-01 1.5.6.2", "NR-23 23.3.2"],
        "gravidade_base": "alta",
    },
    # ------------------------------------------------------------------
    # Sinalização de segurança e cores
    # ------------------------------------------------------------------
    "sinalizacao_de_seguranca_ausente": {
        "rotulo": "Ausência de sinalização de advertência dos riscos do local",
        "descricao": (
            "Área com perigo evidente (máquina, desnível, área de carga, produto "
            "químico, alta tensão) sem placa, faixa ou cor de advertência que indique o "
            "risco a quem circula pelo local."
        ),
        "sinais": [
            "sem placa",
            "sem aviso de perigo",
            "area sem faixa no chao",
            "nenhuma sinalizacao",
            "sem placa de risco",
            "sem demarcacao de piso",
            "sem cone nem fita",
        ],
        "itens": ["NR-26 26.3.1", "NR-26 26.3.2"],
        "gravidade_base": "media",
    },
    "tubulacao_sem_identificacao_por_cor": {
        "rotulo": "Tubulação ou equipamento de segurança sem identificação por cor",
        "descricao": (
            "Tubulações que conduzem líquidos ou gases, ou equipamentos de segurança, sem "
            "a cor ou o rótulo de identificação do conteúdo e do sentido de fluxo, "
            "impedindo saber o que corre dentro da linha."
        ),
        "sinais": [
            "tubulacao sem cor",
            "cano sem identificacao",
            "tubo pintado tudo igual",
            "nao sei o que passa no cano",
            "sem faixa de cor na tubulacao",
            "tubulacao sem seta de fluxo",
            "encanamento sem etiqueta",
        ],
        "itens": ["NR-26 26.3.2", "NR-26 26.3.1"],
        "gravidade_base": "media",
    },
    # ------------------------------------------------------------------
    # Produto químico
    # ------------------------------------------------------------------
    "produto_quimico_sem_rotulagem": {
        "rotulo": "Produto químico sem rotulagem preventiva na embalagem",
        "descricao": (
            "Tambor, bombona, galão ou frasco com produto químico sem rótulo, com rótulo "
            "ilegível, ou reenvasado em embalagem de outro produto — sem pictograma de "
            "perigo, palavra de advertência e frases de precaução."
        ),
        "sinais": [
            "tambor sem rotulo",
            "bombona sem identificacao",
            "produto em garrafa pet",
            "rotulo rasgado",
            "galao sem etiqueta",
            "sem simbolo de perigo",
            "quimico em vasilhame de refrigerante",
        ],
        "itens": ["NR-26 26.4.2.1", "NR-26 26.4.2.2", "NR-26 26.4.1.1"],
        "gravidade_base": "alta",
    },
    "ficha_dados_seguranca_indisponivel": {
        "rotulo": "Ficha com dados de segurança do produto químico indisponível",
        "descricao": (
            "Local onde se manipula ou armazena produto químico sem a ficha com dados de "
            "segurança (FDS/FISPQ) acessível aos trabalhadores no ponto de uso — nenhuma "
            "pasta, quadro ou porta-documento com as fichas junto ao produto."
        ),
        "sinais": [
            "sem fispq",
            "sem fds no local",
            "nao tem ficha do produto",
            "pasta de fispq vazia",
            "quadro sem ficha de seguranca",
            "ninguem sabe o que tem no produto",
            "sem documento do quimico",
        ],
        "itens": ["NR-26 26.5.1"],
        "gravidade_base": "media",
    },
    "armazenamento_de_inflamavel_irregular": {
        "rotulo": "Inflamável armazenado fora de área apropriada e delimitada",
        "descricao": (
            "Combustível ou inflamável (galão de gasolina, botijão de GLP, tambor de "
            "solvente, cilindro) guardado solto em área de circulação, junto a fonte de "
            "calor, faísca ou material combustível, sem bacia de contenção, delimitação "
            "da área de risco nem identificação."
        ),
        "sinais": [
            "galao de gasolina solto",
            "botijao perto de solda",
            "tambor de solvente no corredor",
            "cilindro deitado",
            "inflamavel sem area demarcada",
            "combustivel perto de fogo",
            "estopa junto do solvente",
        ],
        "itens": ["NR-18 18.16.5", "NR-16 16.8"],
        "gravidade_base": "alta",
    },
    "area_de_risco_nao_delimitada": {
        "rotulo": "Área de risco de inflamáveis ou explosivos sem delimitação",
        "descricao": (
            "Área de risco associada a inflamáveis, explosivos ou radiações — abastecimento, "
            "tancagem, paiol, fonte radioativa — sem cerca, faixa, corrente ou placa que "
            "delimite o perímetro e impeça a circulação de quem não trabalha ali."
        ),
        "sinais": [
            "area de abastecimento aberta",
            "tanque sem cerca",
            "sem faixa isolando a area",
            "qualquer um passa perto do tanque",
            "sem placa de area de risco",
            "perimetro sem isolamento",
            "sem corrente delimitando",
        ],
        "itens": ["NR-16 16.8", "NR-26 26.3.1"],
        "gravidade_base": "alta",
    },
    # ------------------------------------------------------------------
    # Espaço confinado
    # ------------------------------------------------------------------
    "espaco_confinado_sem_sinalizacao": {
        "rotulo": "Espaço confinado sem sinalização permanente na entrada",
        "descricao": (
            "Tanque, silo, poço de visita, caixa subterrânea, galeria ou vaso com meios "
            "limitados de entrada sem a sinalização permanente de espaço confinado junto "
            "à abertura, ou com a placa apagada, coberta ou arrancada."
        ),
        "sinais": [
            "tanque sem placa",
            "boca de visita sem aviso",
            "silo sem sinalizacao",
            "poço aberto sem placa",
            "entrada de tanque sem identificacao",
            "placa de espaco confinado apagada",
            "caixa subterranea sem aviso",
        ],
        "itens": ["NR-33 33.5.13.1", "NR-33 33.5.13.3", "NR-33 33.5.13.4"],
        "gravidade_base": "alta",
    },
    "espaco_confinado_entrada_sem_permissao": {
        "rotulo": "Entrada em espaço confinado sem Permissão de Entrada e Trabalho",
        "descricao": (
            "Trabalhador entrando ou já dentro de tanque, silo, poço ou galeria sem a PET "
            "emitida e afixada no local, sem sinalização provisória de liberação e sem "
            "evidência de avaliação atmosférica prévia."
        ),
        "sinais": [
            "homem dentro do tanque",
            "entrou no poço sem papel",
            "sem permissao de entrada",
            "sem pet no local",
            "descendo no silo direto",
            "sem medidor de gas",
            "entrada liberada sem checagem",
        ],
        "itens": ["NR-33 33.5.5", "NR-33 33.5.15.1", "NR-33 33.7.1"],
        "gravidade_base": "critica",
        "exige_pessoa": True,
    },
    "espaco_confinado_sem_vigia": {
        "rotulo": "Trabalho em espaço confinado sem vigia na entrada",
        "descricao": (
            "Trabalhador dentro de espaço confinado sem nenhuma pessoa posicionada do "
            "lado de fora, junto à abertura, mantendo contato e controle de quem entrou e "
            "saiu."
        ),
        "sinais": [
            "sozinho dentro do tanque",
            "ninguem do lado de fora",
            "sem vigia na boca de visita",
            "trabalhador sumiu dentro do poço",
            "abertura sem ninguem",
            "entrou sozinho na galeria",
            "sem acompanhante na entrada",
        ],
        "itens": ["NR-33 33.3.4", "NR-33 33.7.1"],
        "gravidade_base": "critica",
        "exige_pessoa": True,
    },
    "atmosfera_ipvs_sem_protecao_respiratoria": {
        "rotulo": "Acesso a atmosfera perigosa sem proteção respiratória autônoma",
        "descricao": (
            "Trabalhador entrando em espaço confinado com indício de atmosfera perigosa "
            "— vapores, esgoto, fumaça, tanque de produto químico — usando apenas máscara "
            "descartável ou semifacial, sem máscara autônoma ou linha de ar comprimido."
        ),
        "sinais": [
            "mascara de papel no tanque",
            "sem mascara autonoma",
            "descendo no esgoto sem respirador",
            "so com semifacial",
            "sem cilindro de ar",
            "fumaça dentro do tanque",
            "cheiro forte e sem protecao",
        ],
        "itens": ["NR-33 33.5.17.2", "NR-33 33.5.5"],
        "gravidade_base": "critica",
        "exige_pessoa": True,
    },
    # ------------------------------------------------------------------
    # Agentes ambientais
    # ------------------------------------------------------------------
    "exposicao_a_ruido_sem_controle": {
        "rotulo": "Trabalhador exposto a ruído elevado sem controle nem proteção",
        "descricao": (
            "Trabalhador junto a fonte de ruído intenso — serra, esmerilhadeira, "
            "compressor, martelete, gerador, britador — sem protetor auricular e sem "
            "enclausuramento, barreira ou outra medida de controle da fonte."
        ),
        "sinais": [
            "sem protetor auricular perto da serra",
            "barulho alto sem abafador",
            "esmerilhadeira sem protecao no ouvido",
            "compressor ligado do lado",
            "sem plug de ouvido",
            "gerador aberto sem enclausuramento",
            "martelete sem abafador",
        ],
        "itens": ["NR-09 9.6.1", "NR-09 9.5.2", "NR-06 6.5.1"],
        "gravidade_base": "alta",
        "exige_pessoa": True,
    },
    "exposicao_a_poeira_ou_agente_quimico": {
        "rotulo": "Trabalhador exposto a poeira, névoa ou vapor sem controle",
        "descricao": (
            "Trabalhador dentro de nuvem de poeira, névoa ou vapor — corte de material, "
            "lixamento, pintura, jateamento, varrição a seco, transferência de produto "
            "químico — sem proteção respiratória adequada, exaustão, umidificação ou "
            "confinamento da fonte."
        ),
        "sinais": [
            "nuvem de poeira",
            "cortando sem agua",
            "pintando sem mascara",
            "muita fumaça no galpao",
            "sem exaustao",
            "lixando a seco",
            "cheiro de tinta sem respirador",
        ],
        "itens": ["NR-09 9.5.2", "NR-06 6.5.1"],
        "gravidade_base": "alta",
        "exige_pessoa": True,
    },
    "exposicao_a_calor_sem_medidas": {
        "rotulo": "Trabalhador exposto a calor sem medidas de prevenção",
        "descricao": (
            "Trabalhador em atividade sob sol forte ou junto a fonte artificial de calor "
            "— forno, caldeira, fundição, telhado, asfalto — sem água potável no posto, "
            "sem área de sombra ou descanso e sem pausa ou rodízio visível."
        ),
        "sinais": [
            "sol a pino sem sombra",
            "sem agua no posto",
            "trabalhando na frente do forno",
            "sem area de descanso",
            "telhado no sol",
            "muito calor no galpao",
            "asfalto quente sem pausa",
        ],
        "itens": ["NR-09 Anexo III 4.1.1", "NR-09 Anexo III 3.1"],
        "gravidade_base": "alta",
        "exige_pessoa": True,
    },
    "solda_sem_protecao_contra_radiacao": {
        "rotulo": "Solda ou corte sem proteção contra radiação e respingos",
        "descricao": (
            "Operação de solda, corte ou esmerilhamento sem máscara de solda com filtro, "
            "sem avental e luva de raspa, ou sem biombo/cortina isolando o arco de quem "
            "circula ou trabalha ao lado."
        ),
        "sinais": [
            "soldando sem mascara",
            "sem biombo de solda",
            "clarao de solda no meio do galpao",
            "sem avental de raspa",
            "olhando a solda de perto",
            "corte com maçarico sem protecao",
            "faisca voando na passagem",
        ],
        "itens": ["NR-09 9.5.2", "NR-06 6.5.1", "NR-06 6.5.2"],
        "gravidade_base": "alta",
        "exige_pessoa": True,
    },
    "contato_com_agente_biologico": {
        "rotulo": "Contato com esgoto, lixo ou material biológico sem barreira",
        "descricao": (
            "Trabalhador em contato com esgoto, lodo, caixa de gordura, resíduo de saúde, "
            "lixo ou animais mortos sem luva impermeável, bota, avental ou proteção "
            "facial, ou sem local de higienização próximo."
        ),
        "sinais": [
            "mexendo em esgoto sem luva",
            "lixo a ceu aberto",
            "agua parada com sujeira",
            "caixa de gordura aberta",
            "sem bota na lama de esgoto",
            "residuo de hospital solto",
            "sem lugar pra lavar a mao",
        ],
        "itens": ["NR-09 9.5.2", "NR-06 6.5.1"],
        "gravidade_base": "alta",
        "exige_pessoa": True,
    },
    # ------------------------------------------------------------------
    # Gestão de SST
    # ------------------------------------------------------------------
    "pgr_ou_inventario_de_riscos_ausente": {
        "rotulo": "Ausência de PGR ou de inventário de riscos no estabelecimento",
        "descricao": (
            "Estabelecimento em operação sem o Programa de Gerenciamento de Riscos "
            "implementado — sem inventário de riscos e plano de ação disponíveis no "
            "local aos trabalhadores e à inspeção."
        ),
        "sinais": [
            "sem pgr",
            "nao tem inventario de riscos",
            "pasta de documentos vazia",
            "sem plano de acao",
            "nenhum documento de seguranca no local",
            "sem programa de riscos",
            "nada documentado",
        ],
        "itens": ["NR-01 1.5.3.1.1", "NR-01 1.5.7.1", "NR-01 1.5.7.3.1"],
        "gravidade_base": "media",
    },
    "ordem_de_servico_ausente": {
        "rotulo": "Ausência de ordem de serviço de segurança e saúde",
        "descricao": (
            "Organização sem ordens de serviço de segurança e saúde elaboradas e com "
            "ciência dada aos trabalhadores sobre os riscos da função e as medidas de "
            "prevenção que devem cumprir."
        ),
        "sinais": [
            "sem ordem de servico",
            "ninguem assinou nada",
            "sem os assinada",
            "sem documento de ciencia de risco",
            "trabalhador nao sabe o risco da funcao",
            "sem instrucao por escrito",
        ],
        "itens": ["NR-01 1.4.1"],
        "gravidade_base": "media",
    },
    "trabalhador_sem_capacitacao": {
        "rotulo": "Trabalhador em atividade de risco sem capacitação comprovada",
        "descricao": (
            "Trabalhador executando atividade que exige treinamento prévio específico "
            "(altura, espaço confinado, eletricidade, máquina, empilhadeira) sem "
            "evidência de capacitação inicial concluída antes do início das funções."
        ),
        "sinais": [
            "sem treinamento",
            "nao fez curso",
            "primeiro dia na funcao",
            "ajudante operando maquina",
            "sem certificado de capacitacao",
            "trabalhador improvisando",
            "ninguem treinado no local",
        ],
        "itens": ["NR-01 1.7.1", "NR-01 1.7.1.2.1"],
        "gravidade_base": "alta",
        "exige_pessoa": True,
    },
    "cipa_nao_constituida_ou_sem_divulgacao": {
        "rotulo": "CIPA não constituída ou sem divulgação aos trabalhadores",
        "descricao": (
            "Estabelecimento com efetivo que obriga a CIPA sem a comissão constituída, ou "
            "com CIPA existente cujas deliberações não são divulgadas — quadro de aviso "
            "ausente, vazio ou com atas vencidas."
        ),
        "sinais": [
            "sem cipa",
            "quadro de aviso vazio",
            "sem ata no mural",
            "nenhum cartaz da cipa",
            "mural desatualizado",
            "ninguem sabe quem e da cipa",
            "sem comissao de acidentes",
        ],
        # 5.7.1 trata de treinamento dos membros antes da posse — outra obrigação,
        # que não é a descrita aqui. O que a evidência observável (mural vazio, ata
        # vencida) sustenta é a falta de reunião ordinária mensal: 5.6.1.
        "itens": ["NR-05 5.4.1", "NR-05 5.6.3.2"],
        "gravidade_base": "media",
    },
    "pcmso_ausente": {
        "rotulo": "Ausência de programa de controle médico de saúde ocupacional",
        "descricao": (
            "Organização sem PCMSO elaborado e implantado ou sem os exames médicos "
            "ocupacionais obrigatórios realizados — trabalhadores em atividade sem "
            "Atestado de Saúde Ocupacional válido."
        ),
        "sinais": [
            "sem pcmso",
            "sem exame admissional",
            "sem aso",
            "nao faz exame periodico",
            "sem medico responsavel",
            "sem atestado de saude",
            "nenhum controle medico",
        ],
        "itens": ["NR-07 7.4.1", "NR-07 7.5.6"],
        "gravidade_base": "media",
    },
    "sesmt_nao_constituido": {
        "rotulo": "SESMT não constituído ou não registrado",
        "descricao": (
            "Estabelecimento cujo grau de risco e número de empregados obrigam o Serviço "
            "Especializado em Engenharia de Segurança e em Medicina do Trabalho sem o "
            "serviço constituído ou sem o registro eletrônico atualizado."
        ),
        "sinais": [
            "sem sesmt",
            "sem tecnico de seguranca no local",
            "nenhum profissional de seguranca",
            "obra grande sem tecnico",
            "sem engenheiro de seguranca",
            "servico de seguranca nao registrado",
        ],
        "itens": ["NR-04 4.4.2", "NR-04 4.6.1"],
        "gravidade_base": "media",
    },
    "condicao_de_grave_e_iminente_risco": {
        "rotulo": "Condição de grave e iminente risco passível de interdição",
        "descricao": (
            "Situação de trabalho com potencial imediato de acidente com lesão grave ou "
            "morte, em que a atividade segue em curso — exige paralisação imediata e é "
            "passível de embargo ou interdição."
        ),
        "sinais": [
            "risco de morte na hora",
            "vai desabar",
            "situacao gravissima",
            "tem que parar a obra agora",
            "acidente prestes a acontecer",
            "risco iminente",
            "trabalhando embaixo de carga suspensa",
        ],
        "itens": ["NR-03 3.4.1", "NR-01 1.4.3.1"],
        "gravidade_base": "critica",
    },

    # ------------------------------------------------------------------
    # NR-20 — Inflamáveis e combustíveis. A norma se aplica por classe de
    # instalação (Tabela I), então as descrições ficam nas condições físicas que
    # a foto realmente mostra, sem presumir o porte da instalação.
    # ------------------------------------------------------------------
    "area_inflamavel_sem_sinalizacao_ignicao": {
        "rotulo": "Área com inflamáveis sem sinalização de proibição de fontes de ignição",
        "descricao": (
            "Local de armazenamento ou manuseio de inflamáveis e combustíveis sem "
            "sinalização visível proibindo fumar, chama aberta e demais fontes de ignição."
        ),
        "sinais": [
            "tambor de diesel", "botijao de gas", "galao de gasolina", "sem placa de proibido fumar",
            "estoque de tinta e solvente", "combustivel sem sinalizacao", "glp",
            "deposito de inflamavel", "cilindro de acetileno",
        ],
        "itens": ["NR-20 20.13.4"],
        "gravidade_base": "alta",
    },
    "tanque_inflamavel_sem_contencao": {
        "rotulo": "Tanque de inflamável ou combustível sem sistema de contenção de vazamento",
        "descricao": (
            "Tanque ou reservatório de líquido inflamável ou combustível apoiado diretamente "
            "no solo, sem bacia de contenção ou outro sistema para reter vazamento e "
            "derramamento."
        ),
        "sinais": [
            "tambor no chao", "tanque sem bacia", "sem bacia de contencao",
            "combustivel direto no solo", "mancha de oleo no chao", "vazamento de diesel",
            "reservatorio de combustivel sem dique",
        ],
        "itens": ["NR-20 20.14.4"],
        "gravidade_base": "alta",
    },
    "bacia_contencao_usada_como_deposito": {
        "rotulo": "Bacia de contenção utilizada para armazenar materiais",
        "descricao": (
            "Interior da bacia de contenção ocupado por materiais, recipientes ou similares, "
            "o que reduz seu volume útil e compromete a retenção em caso de vazamento."
        ),
        "sinais": [
            "material dentro da bacia", "bacia de contencao entulhada",
            "tambores dentro do dique", "dique usado como deposito",
            "bacia com sucata", "objetos na bacia de contencao",
        ],
        "itens": ["NR-20 20.14.4.1"],
        "gravidade_base": "media",
    },
    "equipamento_eletrico_inadequado_area_classificada": {
        "rotulo": "Equipamento elétrico comum em área sujeita a atmosfera inflamável",
        "descricao": (
            "Instalação, luminária, tomada, extensão ou ferramenta elétrica de uso comum "
            "instalada ou utilizada em área classificada, sem a proteção adequada contra "
            "ignição exigida para o local."
        ),
        "sinais": [
            "extensao perto do combustivel", "luminaria comum na area de inflamavel",
            "tomada perto de tambor", "ferramenta eletrica junto ao combustivel",
            "instalacao eletrica em area classificada", "fio proximo a inflamavel",
        ],
        "itens": ["NR-20 20.13.1"],
        "gravidade_base": "critica",
    },

}
