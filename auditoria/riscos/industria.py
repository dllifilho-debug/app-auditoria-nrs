"""Riscos de máquinas, eletricidade, movimentação de materiais e ergonomia.

Domínio coberto: NR-12 (máquinas e equipamentos), NR-10 (instalações e serviços
em eletricidade), NR-11 (transporte, movimentação, armazenagem e manuseio de
materiais) e NR-17 (ergonomia).

Duas armadilhas conhecidas foram evitadas aqui, e vale registrar por quê:

1. A NR-10 deste repositório é a edição de 2026, reescrita e renumerada. Itens
   que a memória popular associa a "partes vivas" ou "desenergização" mudaram de
   endereço (proteção coletiva virou 10.6, desenergização virou 10.13). Todo item
   citado abaixo foi lido no texto da base, não recuperado de memória.
2. A NR-12 de 2025 não traz mais um anexo de máquinas para trabalhar madeira nem
   qualquer menção a "coifa", "cutelo divisor" ou "rebolo". Serra de bancada e
   esmeril, portanto, se enquadram nos requisitos gerais de proteção de zona de
   perigo e de contenção de projeção de partículas — não em item específico, que
   não existe.

Os `sinais` são deliberadamente escritos no vocabulário de quem descreve uma
foto ("fio pelado", "gambiarra", "polia exposta"), não no da norma; é por eles
que o roteador encontra o risco antes de qualquer citação ser feita.
"""

from __future__ import annotations

RISCOS: dict[str, dict] = {
    # ------------------------------------------------------------------
    # NR-12 — proteção de zonas de perigo
    # ------------------------------------------------------------------
    "maquina_sem_protecao_zona_perigo": {
        "rotulo": "Zona de perigo de máquina sem proteção fixa ou móvel intertravada",
        "descricao": (
            "Transmissão de força, polia, correia, engrenagem, eixo, corrente ou ponto de "
            "operação acessível ao trabalhador, sem proteção fixa nem proteção móvel "
            "associada a dispositivo de intertravamento."
        ),
        "sinais": [
            "polia exposta",
            "correia sem protecao",
            "engrenagem a mostra",
            "eixo girando exposto",
            "maquina sem carenagem",
            "ponto de operacao aberto",
            "corrente de transmissao exposta",
            "cardan sem protecao",
        ],
        "itens": ["NR-12 12.5.1", "NR-12 12.5.9", "NR-12 12.5.11"],
        "gravidade_base": "critica",
    },
    "protecao_movel_sem_intertravamento": {
        "rotulo": "Proteção móvel de máquina sem dispositivo de intertravamento",
        "descricao": (
            "Porta, tampa, grade ou capô que dá acesso à zona de perigo e pode ser aberto "
            "sem ferramenta, com a máquina continuando a operar depois da abertura, ou sem "
            "bloqueio que mantenha a proteção fechada até a parada dos movimentos perigosos."
        ),
        "sinais": [
            "porta da maquina aberta com maquina ligada",
            "tampa sem sensor",
            "grade que abre sem parar a maquina",
            "capo aberto maquina rodando",
            "portinhola sem chave de seguranca",
            "protecao so encostada",
        ],
        "itens": ["NR-12 12.5.6", "NR-12 12.5.7", "NR-12 12.5.8"],
        "gravidade_base": "critica",
    },
    "protecao_burlada_ou_danificada": {
        "rotulo": "Proteção ou dispositivo de segurança burlado, improvisado ou danificado",
        "descricao": (
            "Proteção presa com arame ou fita, sensor de segurança neutralizado, chave de "
            "intertravamento acionada por peça solta, grade amassada, faltando parafusos ou "
            "com vãos abertos por deterioração."
        ),
        "sinais": [
            "protecao amarrada com arame",
            "sensor tapado com fita",
            "chave de seguranca burlada",
            "grade amassada",
            "protecao remendada",
            "parafuso faltando na protecao",
            "protecao quebrada",
        ],
        "itens": ["NR-12 12.5.16", "NR-12 12.5.2", "NR-12 12.11.5"],
        "gravidade_base": "critica",
    },
    "risco_projecao_particulas_sem_protecao": {
        "rotulo": "Máquina com risco de projeção de peças ou partículas sem proteção de contenção",
        "descricao": (
            "Máquina que lança cavaco, faísca, estilhaço, respingo ou fragmento de ferramenta "
            "na direção do operador ou da circulação, sem anteparo, visor ou enclausuramento "
            "capaz de conter a projeção."
        ),
        "sinais": [
            "cavaco voando",
            "faisca na direcao do operador",
            "sem anteparo de acrilico",
            "estilhaco de peca",
            "respingo de material quente",
            "maquina aberta jogando material",
        ],
        "itens": ["NR-12 12.5.10", "NR-12 12.5.12"],
        "gravidade_base": "alta",
    },
    "serra_bancada_sem_protecao_disco": {
        "rotulo": "Serra de bancada ou máquina de corte com disco desprotegido",
        "descricao": (
            "Serra circular de bancada, policorte ou máquina de corte estacionária com o "
            "disco de corte descoberto na zona de operação, sem cobertura sobre o disco nem "
            "guia que impeça o contato das mãos e o retrocesso da peça."
        ),
        "sinais": [
            "serra sem protecao do disco",
            "disco de serra exposto",
            "serra de bancada improvisada",
            "policorte sem capa",
            "disco girando sem cobertura",
            "mao perto do disco",
            "serra sem guia",
        ],
        "itens": ["NR-12 12.5.1", "NR-12 12.5.10"],
        "gravidade_base": "critica",
    },
    "esmeril_sem_protecao_rebolo": {
        "rotulo": "Esmeril ou lixadeira de bancada sem proteção do rebolo",
        "descricao": (
            "Moto-esmeril, politriz ou lixadeira estacionária com o rebolo ou disco abrasivo "
            "sem capa de contenção, sem apoio de peça regulado ou sem visor, expondo o "
            "operador ao contato e à projeção de fragmentos em caso de ruptura do abrasivo."
        ),
        "sinais": [
            "esmeril sem capa",
            "rebolo exposto",
            "esmerilhadeira de bancada sem protecao",
            "disco abrasivo descoberto",
            "sem visor no esmeril",
            "apoio do esmeril solto",
        ],
        "itens": ["NR-12 12.5.10", "NR-12 12.5.11"],
        "gravidade_base": "alta",
    },
    "prensa_sem_sistema_seguranca": {
        "rotulo": "Prensa, guilhotina ou dobradeira sem sistema de segurança na zona de prensagem",
        "descricao": (
            "Prensa, guilhotina, tesoura ou dobradeira cuja zona de prensagem permite o "
            "ingresso das mãos, sem enclausuramento, cortina de luz ou proteção móvel "
            "intertravada, ou com as transmissões de força e o volante descobertos."
        ),
        "sinais": [
            "prensa sem cortina de luz",
            "mao dentro da prensa",
            "guilhotina sem protecao frontal",
            "dobradeira aberta",
            "volante da prensa exposto",
            "zona de prensagem livre",
        ],
        "itens": [
            "NR-12 Anexo VIII 2.1",
            "NR-12 Anexo VIII 2.7",
            "NR-12 Anexo VIII 2.10",
        ],
        "gravidade_base": "critica",
    },
    # ------------------------------------------------------------------
    # NR-12 — comandos, parada de emergência e bloqueio
    # ------------------------------------------------------------------
    "parada_emergencia_ausente_ou_inacessivel": {
        "rotulo": "Dispositivo de parada de emergência ausente, obstruído ou inoperante",
        "descricao": (
            "Máquina sem botão ou cabo de parada de emergência, ou com o acionador escondido "
            "atrás de material, longe do posto de operação, quebrado, pintado por cima ou "
            "travado, impedindo a interrupção imediata do movimento perigoso."
        ),
        "sinais": [
            "sem botao de emergencia",
            "botao vermelho quebrado",
            "emergencia atras de caixa",
            "cogumelo escondido",
            "botao de emergencia longe do operador",
            "parada de emergencia enferrujada",
        ],
        "itens": ["NR-12 12.6.1", "NR-12 12.6.2", "NR-12 12.6.3"],
        "gravidade_base": "critica",
    },
    "comando_bimanual_irregular": {
        "rotulo": "Comando bimanual burlado ou posicionado fora da distância segura",
        "descricao": (
            "Dispositivo de acionamento bimanual com um dos botões travado, amarrado ou "
            "coberto, botões próximos o bastante para serem acionados com uma só mão, ou "
            "pedestal posicionado tão perto da zona de perigo que a mão alcança o ponto de "
            "operação antes da parada."
        ),
        "sinais": [
            "botao bimanual amarrado",
            "um botao travado com fita",
            "aciona com uma mao so",
            "botoes muito juntos",
            "bimanual colado na maquina",
            "peso em cima do botao",
        ],
        "itens": ["NR-12 12.4.3", "NR-12 12.4.5"],
        "gravidade_base": "alta",
    },
    "pedal_acionamento_desprotegido": {
        "rotulo": "Pedal ou botoeira de acionamento sem proteção contra acionamento acidental",
        "descricao": (
            "Pedal de máquina solto no piso, sem capa de proteção sobre ele ou com acesso por "
            "mais de uma direção, e botoeiras de partida localizadas de modo a serem "
            "acionadas por esbarrão, queda de peça ou passagem de pessoa."
        ),
        "sinais": [
            "pedal sem capa",
            "pedal solto no chao",
            "botao de partida desprotegido",
            "pedal aberto",
            "botoeira no caminho de passagem",
            "aciona sem querer",
        ],
        "itens": ["NR-12 12.4.1", "NR-12 Anexo VIII 2.9.1"],
        "gravidade_base": "alta",
    },
    "partida_acidental_manutencao_sem_bloqueio": {
        "rotulo": "Manutenção ou limpeza de máquina sem bloqueio e etiquetagem das fontes de energia",
        "descricao": (
            "Trabalhador com o corpo ou as mãos dentro da máquina para manutenção, ajuste, "
            "desatolamento ou limpeza, sem que as fontes de energia estejam isoladas, "
            "descarregadas, bloqueadas na posição desligado e sinalizadas com cartão ou "
            "etiqueta de bloqueio."
        ),
        "sinais": [
            "sem cadeado de bloqueio",
            "sem etiqueta no disjuntor",
            "mexendo na maquina ligada",
            "desatolando com a maquina energizada",
            "limpeza com maquina em funcionamento",
            "chave geral sem trava",
            "sem loto",
        ],
        "itens": ["NR-12 12.11.3", "NR-12 12.4.9"],
        "gravidade_base": "critica",
        "exige_pessoa": True,
    },
    "sinalizacao_seguranca_maquina_ausente": {
        "rotulo": "Máquina sem sinalização de segurança legível sobre os riscos",
        "descricao": (
            "Máquina ou instalação sem placas, cores ou inscrições que advirtam do risco "
            "específico e da parte perigosa a que se referem, ou com a sinalização apagada, "
            "coberta por sujeira, em idioma estrangeiro ou ilegível."
        ),
        "sinais": [
            "sem placa de aviso na maquina",
            "adesivo de perigo apagado",
            "aviso rasgado",
            "placa em ingles",
            "sinalizacao coberta de graxa",
            "maquina sem identificacao de risco",
        ],
        "itens": ["NR-12 12.12.1", "NR-12 12.12.2", "NR-12 12.12.4.1"],
        "gravidade_base": "media",
    },
    # ------------------------------------------------------------------
    # NR-12 / NR-11 — arranjo físico, piso e estabilidade
    # ------------------------------------------------------------------
    "area_circulacao_maquinas_obstruida": {
        "rotulo": "Área de circulação em torno de máquinas obstruída ou sem demarcação",
        "descricao": (
            "Corredor de circulação no setor de máquinas sem demarcação no piso, ocupado por "
            "material, pallet, refugo ou ferramenta, ou espaço entre máquinas estreito demais "
            "para operar, ajustar e limpar com segurança."
        ),
        "sinais": [
            "corredor entupido",
            "pallet no corredor",
            "sem faixa amarela no chao",
            "passagem estreita entre maquinas",
            "material empilhado na passagem",
            "corredor sem demarcacao",
        ],
        "itens": [
            "NR-12 12.2.1",
            "NR-12 12.2.1.2",
            "NR-12 12.2.2",
            "NR-12 12.2.3",
        ],
        "gravidade_base": "media",
    },
    "piso_local_maquinas_danificado": {
        "rotulo": "Piso do local de máquinas danificado, escorregadio ou com desnível",
        "descricao": (
            "Piso do setor de máquinas ou de armazenagem quebrado, esburacado, com placa "
            "solta, poça de óleo, água ou sobra de material solto, oferecendo risco de queda, "
            "tropeço ou tombamento de equipamento de transporte."
        ),
        "sinais": [
            "piso quebrado",
            "buraco no chao da fabrica",
            "poca de oleo no piso",
            "chao escorregadio",
            "desnivel no piso",
            "placa de piso solta",
        ],
        "itens": ["NR-12 12.2.4", "NR-08 8.3.2.4"],
        "gravidade_base": "media",
    },
    "maquina_sem_estabilidade_ou_fixacao": {
        "rotulo": "Máquina sem fixação, nivelamento ou travas que garantam estabilidade",
        "descricao": (
            "Máquina estacionária apoiada em calço improvisado, sem chumbamento ou base "
            "nivelada, que se desloca ou vibra em operação, ou máquina móvel sobre rodízios "
            "sem pelo menos dois deles travados."
        ),
        "sinais": [
            "maquina em cima de calco",
            "maquina balancando",
            "sem chumbador",
            "base torta",
            "rodizio sem trava",
            "maquina andando com a vibracao",
        ],
        "itens": ["NR-12 12.2.6", "NR-12 12.2.6.1", "NR-12 12.2.7"],
        "gravidade_base": "alta",
    },
    # ------------------------------------------------------------------
    # NR-10 / NR-12 — elétrica
    # ------------------------------------------------------------------
    "partes_vivas_expostas": {
        "rotulo": "Partes energizadas expostas ao contato",
        "descricao": (
            "Condutor, barramento, borne, terminal ou emenda energizada acessível ao toque, "
            "sem isolação, barreira ou invólucro: tomada quebrada, disjuntor sem espelho, "
            "caixa de passagem aberta, ponta de fio descascada em circuito vivo."
        ),
        "sinais": [
            "fio pelado",
            "fio descascado",
            "tomada quebrada",
            "caixa de passagem aberta",
            "barramento exposto",
            "terminal sem capa",
            "sem espelho no interruptor",
            # O agente de visão descreve em registro técnico, não no vocabulário
            # de campo: escreve "fios desencapados" e "caixa de distribuição com
            # componentes expostos" onde o eletricista diz "fio pelado". Sem
            # estes sinais o risco não era roteado, o dossiê saía sem nenhum item
            # elétrico e o laudo enquadrava fio exposto em item de documentação.
            "fio desencapado",
            "fios eletricos expostos",
            "condutor eletrico exposto",
            "fio sem isolamento",
            "caixa de distribuicao com componentes expostos",
            "emenda exposta",
        ],
        "itens": ["NR-10 10.2.8.2", "NR-10 10.2.8.2.1", "NR-12 12.3.8"],
        "gravidade_base": "critica",
    },
    "quadro_eletrico_aberto_ou_sem_sinalizacao": {
        "rotulo": "Quadro ou painel elétrico sem fechamento, sem sinalização ou usado como depósito",
        "descricao": (
            "Painel ou quadro de comando com a porta aberta ou ausente fora de intervenção, "
            "sem tampa interna, sem sinalização de perigo de choque e restrição de acesso, ou "
            "com objetos, ferramentas e sujeira guardados no seu interior."
        ),
        "sinais": [
            "quadro aberto",
            "painel sem porta",
            "quadro sem placa de perigo",
            "quadro sujo por dentro",
            "ferramenta dentro do quadro",
            "disjuntor a mostra",
            "quadro sem tampa",
            # Dois radicais, ambos obrigatórios pela cobertura: com sinal
            # longo ("painel eletrico sem tampa") a cobertura parcial dispensa
            # justamente o discriminante, e "painel de fôrma de madeira sem
            # tampa protetora" virava quadro elétrico aberto. Medido.
            "painel eletrico",
            "painel elétrico",
            "painel de comando",
        ],
        "itens": ["NR-10 10.10.1", "NR-12 12.3.5"],
        "gravidade_base": "alta",
    },
    "ligacao_eletrica_improvisada": {
        "rotulo": "Emenda ou ligação elétrica improvisada (gambiarra)",
        "descricao": (
            "Emenda de condutor feita por torção e fita isolante, fio enfiado direto na "
            "tomada sem plugue, benjamim sobrecarregado, T ligado em T, ou derivação "
            "pendurada sem caixa e sem conector apropriado."
        ),
        "sinais": [
            "gambiarra",
            "emenda com fita isolante",
            "fio enfiado na tomada",
            "benjamim",
            "puxadinho eletrico",
            "fio torcido",
            "t em cima de t",
        ],
        "itens": ["NR-12 12.3.6", "NR-10 10.4.4"],
        "gravidade_base": "alta",
    },
    "cabo_eletrico_danificado": {
        "rotulo": "Cabo de alimentação danificado, esmagado ou mal posicionado",
        "descricao": (
            "Cabo de máquina ou de ferramenta com capa rasgada, ressecada, queimada ou "
            "emendada, passando por aresta viva, sobre parte móvel, esmagado por porta ou "
            "roda, ou atravessando corredor de circulação sem proteção."
        ),
        "sinais": [
            "cabo rasgado",
            "capa do fio ressecada",
            "cabo passando no corredor",
            "fio esmagado pela porta",
            "cabo encostando em parte quente",
            "cabo prensado",
            "extensao atravessada no chao",
            # Mesmo motivo do risco de partes vivas: registro técnico do agente
            # de visão, que não usa o vocabulário de campo já cadastrado.
            "cabo com isolamento danificado",
            "isolamento do cabo comprometido",
            "cabo eletrico estendido sobre o piso",
        ],
        "itens": ["NR-12 12.3.4", "NR-12 12.3.8"],
        "gravidade_base": "alta",
    },
    "instalacao_eletrica_em_area_molhada": {
        "rotulo": "Instalação ou extensão elétrica exposta em área molhada ou lavada",
        "descricao": (
            "Tomada, extensão, quadro ou cabo de máquina em piso molhado, área de lavagem ou "
            "sujeito a respingo, sem grau de proteção adequado, sem estanqueidade e sem "
            "dispositivo diferencial-residual protegendo o circuito."
        ),
        "sinais": [
            "extensao no chao molhado",
            "tomada perto da agua",
            "fio na poca",
            "quadro em area de lavagem",
            "cabo dentro da agua",
            "sem dr no circuito",
        ],
        "itens": ["NR-12 12.3.3", "NR-10 10.4.2"],
        "gravidade_base": "critica",
    },
    "maquina_sem_aterramento": {
        "rotulo": "Carcaça de máquina ou equipamento sem aterramento",
        "descricao": (
            "Carcaça, invólucro, blindagem ou estrutura metálica de máquina que pode ficar "
            "acidentalmente sob tensão, sem condutor de proteção conectado: cabo terra "
            "cortado, solto, pintado sobre o ponto de contato, ou plugue com o pino de terra "
            "removido."
        ),
        "sinais": [
            "sem fio terra",
            "pino de terra cortado",
            "cabo terra solto",
            "sem aterramento na carcaca",
            "plugue com dois pinos",
            "terra desconectado",
        ],
        "itens": ["NR-12 12.3.2", "NR-10 10.2.8.3"],
        "gravidade_base": "alta",
    },
    "circuitos_sem_identificacao": {
        "rotulo": "Circuitos, disjuntores e comandos elétricos sem identificação",
        "descricao": (
            "Disjuntores, chaves, botoeiras, cabos e eletrodutos sem etiqueta ou legenda que "
            "identifique o circuito e o equipamento que alimentam, impedindo o desligamento "
            "correto em manutenção e emergência."
        ),
        "sinais": [
            "disjuntor sem etiqueta",
            "quadro sem legenda",
            "fio sem identificacao",
            "nao sabe qual disjuntor desliga",
            "chave sem nome",
            "cabos misturados sem marcacao",
        ],
        "itens": ["NR-10 10.3.3.1", "NR-10 10.10.1"],
        "gravidade_base": "media",
    },
    "trabalho_energizado_sem_desenergizacao": {
        "rotulo": "Intervenção em instalação elétrica sem desenergização nem permissão de trabalho",
        "descricao": (
            "Trabalhador intervindo em circuito, quadro ou equipamento energizado sem a "
            "sequência de desenergização, sem impedimento de reenergização e sinalização de "
            "bloqueio, sem permissão de trabalho e sem evidência de autorização para o "
            "serviço em eletricidade."
        ),
        "sinais": [
            "mexendo no quadro energizado",
            "sem travar o disjuntor",
            "sem placa de nao ligue",
            "trabalhando com o painel vivo",
            "sem ordem de servico eletrico",
            "eletricista sem epi no painel",
        ],
        "itens": ["NR-10 10.5.1", "NR-10 10.11.2"],
        "gravidade_base": "critica",
        "exige_pessoa": True,
    },
    "sala_eletrica_usada_como_deposito": {
        "rotulo": "Local ou compartimento de serviço elétrico usado para guardar objetos",
        "descricao": (
            "Sala elétrica, cabine de medição, casa de força ou invólucro de equipamento "
            "elétrico com material, caixas, escadas, produtos de limpeza ou entulho "
            "armazenados, ocupando espaço exclusivo da instalação e bloqueando o acesso."
        ),
        "sinais": [
            "caixa dentro da sala eletrica",
            "vassoura encostada no painel",
            "entulho na cabine",
            "deposito na casa de forca",
            "material na frente do quadro",
            "escada guardada na sala eletrica",
        ],
        "itens": ["NR-10 10.4.4.1"],
        "gravidade_base": "media",
    },
    # ------------------------------------------------------------------
    # NR-12 / NR-11 — movimentação de materiais
    # ------------------------------------------------------------------
    "transportador_correia_sem_protecao": {
        "rotulo": "Transportador contínuo sem proteção nos pontos de agarramento ou sem parada de emergência",
        "descricao": (
            "Correia transportadora, rosca ou elevador de canecas com tambor, roletes, "
            "esticador ou ponto de entrada da correia acessíveis, sem proteção nos pontos de "
            "esmagamento e agarramento, ou sem dispositivo de parada de emergência ao longo "
            "da extensão acessível."
        ),
        "sinais": [
            "esteira sem protecao",
            "tambor da correia exposto",
            "rolete a mostra",
            "rosca transportadora aberta",
            "sem cabo de emergencia na esteira",
            "ponto de agarramento livre",
        ],
        "itens": ["NR-12 12.8.1", "NR-12 12.8.7"],
        "gravidade_base": "alta",
    },
    "carga_suspensa_sobre_trabalhadores": {
        "rotulo": "Circulação ou permanência de trabalhadores sob carga suspensa",
        "descricao": (
            "Carga içada por ponte rolante, talha, guindaste ou pórtico passando sobre "
            "pessoas ou postos de trabalho, sem área exclusiva delimitada e sinalizada para "
            "o percurso da carga."
        ),
        "sinais": [
            "carga passando por cima de gente",
            "pessoa embaixo da ponte rolante",
            "carga icada sobre posto de trabalho",
            "sem area isolada para icamento",
            "talha passando sobre o corredor",
            "trabalhador embaixo da carga",
        ],
        "itens": ["NR-12 12.8.9", "NR-12 12.8.9.1", "NR-12 12.2.8"],
        "gravidade_base": "critica",
        "exige_pessoa": True,
    },
    "cabo_aco_ou_lingada_deteriorados": {
        "rotulo": "Cabo de aço, corrente, cinta ou gancho de içamento deteriorado",
        "descricao": (
            "Acessório de içamento com fios rompidos, amassamento, dobra permanente, "
            "corrosão, cinta têxtil rasgada ou queimada, gancho aberto, deformado ou sem "
            "trava de segurança, ainda em uso na movimentação de carga."
        ),
        "sinais": [
            "cabo de aco desfiado",
            "cinta rasgada",
            "gancho sem trava",
            "corrente torta",
            "gancho aberto",
            "estropo remendado",
            "cabo de aco enferrujado",
        ],
        "itens": ["NR-11 11.1.3.1", "NR-12 12.8.4", "NR-11 11.1.3"],
        "gravidade_base": "critica",
    },
    "equipamento_movimentacao_sem_carga_maxima": {
        "rotulo": "Equipamento de movimentação sem indicação visível da carga máxima",
        "descricao": (
            "Talha, ponte rolante, pórtico, guincho, elevador de carga ou empilhadeira sem "
            "placa legível, em local visível, indicando a carga máxima de trabalho permitida "
            "e a identificação do equipamento."
        ),
        "sinais": [
            "sem placa de carga maxima",
            "talha sem identificacao",
            "ponte rolante sem tonelagem",
            "placa apagada no equipamento",
            "guincho sem indicacao de capacidade",
            "nao tem etiqueta de capacidade",
        ],
        "itens": ["NR-11 11.1.3.2"],
        "gravidade_base": "media",
    },
    "empilhadeira_operacao_irregular": {
        "rotulo": "Empilhadeira ou equipamento de transporte motorizado em operação irregular",
        "descricao": (
            "Empilhadeira, rebocador ou paleteira motorizada operada sem sinal sonoro de "
            "advertência funcionando, sem que o operador porte o cartão de identificação com "
            "nome e fotografia, ou conduzida por trabalhador sem treinamento específico para "
            "a função."
        ),
        "sinais": [
            "empilhadeira sem buzina",
            "operador sem cracha",
            "qualquer um dirige a empilhadeira",
            "empilhadeira sem sinal sonoro",
            "sem cartao de operador",
            "empilhadeira em area de pedestre",
        ],
        "itens": ["NR-11 11.1.5", "NR-11 11.1.6", "NR-11 11.1.7"],
        "gravidade_base": "alta",
        "exige_pessoa": True,
    },
    "empilhadeira_combustao_em_local_fechado": {
        "rotulo": "Máquina de transporte a combustão operando em local fechado sem ventilação",
        "descricao": (
            "Empilhadeira, trator ou transportador movido a motor de combustão interna "
            "operando dentro de galpão, câmara ou container fechado e sem ventilação, sem "
            "dispositivo neutralizador de gases, acumulando monóxido no ambiente."
        ),
        "sinais": [
            "empilhadeira a diesel dentro do galpao",
            "fumaca de escapamento no ambiente",
            "motor a combustao em local fechado",
            "cheiro de diesel no barracao",
            "galpao fechado com maquina ligada",
            "sem exaustao no deposito",
        ],
        "itens": ["NR-11 11.1.10", "NR-11 11.1.9"],
        "gravidade_base": "alta",
    },
    "poco_elevador_carga_sem_cercamento": {
        "rotulo": "Poço de elevador ou monta-carga sem cercamento ou com abertura desprotegida",
        "descricao": (
            "Poço de elevador de carga ou monta-carga sem cercamento sólido em toda a altura, "
            "ou abertura de pavimento liberada com a cabine em outro nível, sem cancela, "
            "porta ou corrimão fechando o vão."
        ),
        "sinais": [
            "poco de elevador aberto",
            "monta carga sem cancela",
            "vao do elevador sem protecao",
            "buraco do elevador liberado",
            "porta do monta carga faltando",
            "abertura sem corrimao",
        ],
        "itens": ["NR-11 11.1.1", "NR-11 11.1.2"],
        "gravidade_base": "critica",
    },
    "armazenamento_obstruindo_saida_ou_extintor": {
        "rotulo": "Material armazenado obstruindo saída, porta ou equipamento de combate a incêndio",
        "descricao": (
            "Carga, caixa, pallet, tambor ou bobina depositada em frente a porta, saída de "
            "emergência, extintor, hidrante ou quadro de comando, ou dificultando o trânsito "
            "e a iluminação do local."
        ),
        "sinais": [
            "extintor obstruido",
            "caixa na frente da saida",
            "pallet bloqueando a porta",
            "hidrante atras de material",
            "saida de emergencia entupida",
            "material tapando a luminaria",
        ],
        "itens": ["NR-11 11.3.2", "NR-11 11.3.4"],
        "gravidade_base": "alta",
    },
    "empilhamento_instavel_de_material": {
        "rotulo": "Empilhamento instável, alto demais ou encostado na estrutura",
        "descricao": (
            "Pilha de sacaria, caixas, bobinas ou pallets desaprumada, sem amarração, com "
            "altura incompatível com a estabilidade e a resistência da embalagem, encostada "
            "em parede ou coluna, ou sobre piso cuja capacidade de carga é excedida."
        ),
        "sinais": [
            "pilha torta",
            "caixa empilhada ate o teto",
            "pilha encostada na parede",
            "empilhamento sem amarracao",
            "bobina solta sem calco",
            "pilha na iminencia de cair",
        ],
        "itens": ["NR-11 11.2.5", "NR-11 11.3.1", "NR-11 11.3.3"],
        "gravidade_base": "alta",
    },
    # ------------------------------------------------------------------
    # NR-17 — ergonomia
    # ------------------------------------------------------------------
    "levantamento_manual_peso_excessivo": {
        "rotulo": "Levantamento manual de carga com peso ou alcance incompatível com a segurança",
        "descricao": (
            "Trabalhador levantando, sozinho e sem meio auxiliar, volume pesado ou volumoso, "
            "com o corpo curvado, carga afastada do tronco além de 60 cm ou pega e depósito "
            "em alturas que obrigam flexão e torção acentuadas."
        ),
        "sinais": [
            "carregando saco pesado nas costas",
            "levantando peso curvado",
            "erguendo sozinho carga grande",
            "pegando caixa do chao com o tronco torto",
            "carga longe do corpo",
            "carregando fardo no ombro",
        ],
        "itens": ["NR-17 17.5.1", "NR-17 17.5.2.1", "NR-17 17.5.4"],
        "gravidade_base": "alta",
        "exige_pessoa": True,
    },
    "transporte_manual_sem_meio_mecanico": {
        "rotulo": "Transporte manual de material por longa distância sem meio mecânico auxiliar",
        "descricao": (
            "Deslocamento repetido de carga a braço por percursos longos, ou empurrando e "
            "puxando carrinho, vagonete ou paleteira inadequados, sem protetor de mãos, com "
            "esforço e frequência incompatíveis com a segurança do trabalhador."
        ),
        "sinais": [
            "carregando material no braco por longa distancia",
            "empurrando carrinho pesado",
            "carrinho sem protecao de mao",
            "puxando carga na rampa",
            "sem paleteira",
            "levando saco de um lado para o outro",
        ],
        "itens": ["NR-17 17.5.3", "NR-11 11.2.2.1", "NR-11 11.1.4"],
        "gravidade_base": "media",
        "exige_pessoa": True,
    },
    "mobiliario_posto_trabalho_inadequado": {
        "rotulo": "Posto de trabalho com bancada, plano ou assento inadequado",
        "descricao": (
            "Bancada, mesa ou plano de trabalho em altura incompatível com a tarefa e a "
            "estatura do trabalhador, sem espaço para pernas e pés, ou assento sem regulagem "
            "de altura, sem encosto lombar e com borda frontal viva."
        ),
        "sinais": [
            "bancada muito baixa",
            "trabalhando curvado na mesa",
            "banco sem encosto",
            "cadeira quebrada",
            "sem espaco para as pernas",
            "assento improvisado com caixote",
        ],
        "itens": ["NR-17 17.6.1", "NR-17 17.6.3", "NR-17 17.6.6"],
        "gravidade_base": "media",
    },
    "trabalho_em_pe_sem_assento_para_pausa": {
        "rotulo": "Trabalho realizado em pé sem assento disponível para as pausas",
        "descricao": (
            "Posto em que a tarefa é executada em pé durante toda a jornada, sem assento com "
            "encosto disponível no local para descanso nas pausas, e sem que o posto permita "
            "alternar as posições em pé e sentada quando a tarefa permitiria."
        ),
        "sinais": [
            "trabalha o dia todo em pe",
            "nao tem banco para sentar",
            "sem cadeira no posto",
            "operador em pe sem descanso",
            "linha de producao sem assento",
            "so tem caixote para sentar",
        ],
        "itens": ["NR-17 17.6.7", "NR-17 17.6.2"],
        "gravidade_base": "baixa",
    },
    "postura_forcada_e_repetitividade": {
        "rotulo": "Postura extrema ou movimento repetitivo contínuo no posto de trabalho",
        "descricao": (
            "Atividade executada de forma contínua com braços acima dos ombros, tronco "
            "flexionado ou torcido, agachamento ou joelhos no piso, movimentos repetidos de "
            "membros superiores, ou espaço tão restrito que impede movimentar os segmentos "
            "corporais livremente."
        ),
        "sinais": [
            "braco acima do ombro o tempo todo",
            "trabalhando agachado",
            "de joelhos no chao",
            "tronco torcido",
            "movimento repetitivo na esteira",
            "espaco apertado para trabalhar",
        ],
        "itens": ["NR-17 17.4.3", "NR-17 17.4.2", "NR-17 17.4.6"],
        "gravidade_base": "media",
        "exige_pessoa": True,
    },
    "iluminacao_insuficiente_no_posto": {
        "rotulo": "Iluminação insuficiente ou com ofuscamento no posto de trabalho",
        "descricao": (
            "Posto de trabalho escuro, com luminária queimada, suja ou removida, sombra "
            "projetada sobre a tarefa, ou com foco de luz e reflexo causando ofuscamento e "
            "contraste excessivo no campo visual do trabalhador."
        ),
        "sinais": [
            "local escuro",
            "lampada queimada",
            "sombra em cima da peca",
            "luminaria suja",
            "luz ofuscando o operador",
            "trabalhando no escuro",
            "so tem lanterna de celular",
        ],
        "itens": ["NR-17 17.8.1", "NR-17 17.8.2", "NR-17 17.8.3"],
        "gravidade_base": "media",
    },

    # ------------------------------------------------------------------
    # NR-13 — Caldeiras e vasos de pressão. No canteiro, o caso comum é o
    # reservatório do compressor de ar: é vaso de pressão para todos os efeitos.
    # ------------------------------------------------------------------
    "vaso_pressao_sem_placa_identificacao": {
        "rotulo": "Vaso de pressão sem placa de identificação afixada e visível",
        "descricao": (
            "Reservatório de ar comprimido, autoclave ou outro vaso de pressão sem placa "
            "de identificação indelével no corpo, ou sem a categoria e o código de "
            "identificação em local visível."
        ),
        "sinais": [
            "compressor de ar", "reservatorio de ar comprimido", "vaso de pressao",
            "cilindro sem placa", "tanque de ar sem identificacao", "autoclave",
            "sem placa de identificacao", "tanque pressurizado",
        ],
        "itens": ["NR-13 13.5.1.3", "NR-13 13.5.1.4"],
        "gravidade_base": "media",
    },
    "vaso_pressao_sem_dispositivo_seguranca": {
        "rotulo": "Vaso de pressão sem válvula de segurança ou sem indicador de pressão",
        "descricao": (
            "Vaso de pressão em operação sem válvula de segurança (ou outro dispositivo de "
            "alívio), sem manômetro, ou com o dispositivo de alívio visivelmente bloqueado, "
            "amarrado ou substituído por improviso."
        ),
        "sinais": [
            "sem valvula de seguranca", "valvula de alivio bloqueada", "sem manometro",
            "manometro quebrado", "compressor sem valvula", "valvula amarrada",
            "dispositivo de alivio lacrado", "reservatorio sem manometro",
        ],
        "itens": ["NR-13 13.5.1.2"],
        "gravidade_base": "critica",
    },
    "caldeira_sem_dispositivo_seguranca": {
        "rotulo": "Caldeira sem válvula de segurança ou sem instrumentação de pressão",
        "descricao": (
            "Caldeira em operação sem válvula de segurança ajustada, sem instrumento "
            "indicador de pressão ou sem os dispositivos de controle de nível exigidos."
        ),
        "sinais": [
            "caldeira", "gerador de vapor", "caldeira sem valvula", "sem visor de nivel",
            "caldeira sem manometro", "vaso de vapor", "sem indicador de pressao",
        ],
        "itens": ["NR-13 13.4.1.2"],
        "gravidade_base": "critica",
    },
    "vaso_pressao_instalacao_sem_acesso_seguro": {
        "rotulo": "Vaso de pressão instalado sem acesso seguro aos drenos e indicadores",
        "descricao": (
            "Vaso de pressão posicionado de modo que drenos, respiros, bocas de visita ou "
            "indicadores de nível, pressão e temperatura não possam ser alcançados por "
            "meio seguro — encaixotado, encostado em parede ou sobre base improvisada."
        ),
        "sinais": [
            "compressor entalado", "vaso encostado na parede", "sem acesso ao dreno",
            "manometro inacessivel", "equipamento em vao apertado",
            "reservatorio sobre base improvisada", "sem passagem para manutencao",
        ],
        "itens": ["NR-13 13.5.2.1"],
        "gravidade_base": "media",
    },

}
