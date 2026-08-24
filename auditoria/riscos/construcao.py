"""Riscos de construção civil e canteiro de obras.

Domínio coberto: NR-18 (indústria da construção), NR-35 (trabalho em altura),
NR-08 (edificações), NR-21 (trabalho a céu aberto) e NR-24 (condições
sanitárias e de conforto).

Cada entrada descreve uma condição física que aparece numa foto de canteiro e
aponta o(s) item(ns) normativo(s) que a condição infringe. O mapeamento foi
feito lendo o texto de cada item na base — a proximidade do número não basta:
18.9.2 trata do fechamento de abertura no piso, 18.9.4.2 trata do guarda-corpo
de periferia, e trocar um pelo outro é exatamente o erro que este módulo
existe para impedir.
"""

RISCOS: dict[str, dict] = {
    # ------------------------------------------------------------------
    # Quedas de altura — proteção coletiva
    # ------------------------------------------------------------------
    "queda_altura_sem_protecao_coletiva": {
        "rotulo": "Trabalho com risco de queda de altura sem proteção coletiva instalada",
        "descricao": (
            "Trabalhador exposto a risco de queda de nível em ponto da obra onde não há "
            "nenhuma proteção coletiva instalada (guarda-corpo, anteparo rígido, rede ou "
            "plataforma), nem se observa sistema individual de retenção de queda em uso."
        ),
        "sinais": [
            "trabalhando na beirada",
            "sem protecao contra queda",
            "beira de laje sem nada",
            "operario no alto sem protecao",
            "risco de queda de altura",
            "trabalho em altura sem protecao coletiva",
            "sem grade nenhuma na borda",
            "pessoa na ponta da estrutura",
        ],
        "itens": ["NR-18 18.9.1", "NR-35 35.5.2", "NR-35 35.6.1"],
        "gravidade_base": "critica",
    },
    "periferia_laje_sem_guarda_corpo": {
        "rotulo": "Periferia da edificação sem guarda-corpo e rodapé regulamentares",
        "descricao": (
            "Borda de laje, pavimento, sacada ou perímetro da edificação sem guarda-corpo "
            "com travessão superior a 1,20 m, travessão intermediário, rodapé e fechamento "
            "do vão — ou com guarda-corpo improvisado, baixo, frouxo ou incompleto."
        ),
        "sinais": [
            "periferia da laje sem guarda-corpo",
            "borda de laje aberta",
            "guarda corpo so com uma corda",
            "guarda corpo de madeira frouxo",
            "sem rodape na borda",
            "fita zebrada no lugar de guarda-corpo",
            "sacada sem grade",
            "guarda corpo baixo",
            "vergalhao amarrado como guarda corpo",
        ],
        "itens": ["NR-18 18.9.4", "NR-18 18.9.4.2", "NR-18 18.9.4.1"],
        "gravidade_base": "critica",
    },
    "abertura_piso_desprotegida": {
        "rotulo": "Abertura no piso sem fechamento travado ou proteção contra queda",
        "descricao": (
            "Vão, poço, caixa de passagem ou shaft no piso sem tampa de material resistente "
            "travada/fixada à estrutura, ou sem sistema de proteção contra quedas no seu "
            "contorno."
        ),
        "sinais": [
            "abertura no piso",
            "buraco no piso",
            "vao no piso sem tampa",
            "tampa solta sobre o buraco",
            "placa apoiada sobre abertura",
            "caixa de passagem aberta",
            "shaft aberto",
            "chapa cobrindo buraco",
            "tampao improvisado",
        ],
        "itens": ["NR-18 18.9.2", "NR-08 8.3.2.2"],
        "gravidade_base": "critica",
    },
    "vao_caixa_elevador_sem_fechamento": {
        "rotulo": "Vão de acesso à caixa de elevador sem fechamento provisório",
        "descricao": (
            "Abertura de acesso ao poço/caixa de elevador sem fechamento provisório de toda "
            "a abertura, em material resistente travado ou fixado à estrutura, enquanto as "
            "portas definitivas não são colocadas."
        ),
        "sinais": [
            "poco de elevador aberto",
            "caixa do elevador sem fechamento",
            "vao do elevador so com fita",
            "buraco do elevador sem tapume",
            "porta do elevador faltando",
            "shaft do elevador aberto",
            "tabua atravessada no vao do elevador",
        ],
        "itens": ["NR-18 18.9.3"],
        "gravidade_base": "critica",
    },
    "protecao_queda_materiais_periferia": {
        "rotulo": "Perímetro da obra sem proteção contra queda de materiais",
        "descricao": (
            "Perímetro de edifício em construção sem sistema de proteção contra queda de "
            "materiais (bandeja/plataforma de proteção primária, secundária ou terciária, "
            "ou tela de fechamento), ou com plataforma danificada, sobrecarregada ou "
            "retirada antes do fim dos serviços acima."
        ),
        "sinais": [
            "sem bandeja de protecao",
            "plataforma de protecao quebrada",
            "material caindo da obra",
            "sem tela no perimetro do predio",
            "bandeja cheia de entulho",
            "fachada aberta sem protecao",
            "tijolo empilhado na beirada",
        ],
        "itens": ["NR-18 18.9.1.1", "NR-18 18.9.4.3"],
        "gravidade_base": "alta",
    },
    "rede_seguranca_irregular": {
        "rotulo": "Rede de segurança rasgada, emendada ou instalada de forma irregular",
        "descricao": (
            "Rede de segurança usada como proteção contra quedas apresentando rasgos, malha "
            "irregular, emendas por sobreposição, pontos de fixação soltos — ou, na "
            "periferia, sem o sistema associado de 1,20 m que barre a queda de materiais."
        ),
        "sinais": [
            "rede de protecao rasgada",
            "rede furada",
            "rede solta pendurada",
            "rede emendada com arame",
            "rede de seguranca frouxa",
            "malha da rede aberta",
            "rede presa em poucos pontos",
        ],
        "itens": ["NR-18 18.9.4.4", "NR-18 18.9.4.4.2", "NR-18 18.9.4.4.7"],
        "gravidade_base": "alta",
    },
    # ------------------------------------------------------------------
    # Andaimes e plataformas de trabalho
    # ------------------------------------------------------------------
    "andaime_base_instavel": {
        "rotulo": "Andaime apoiado em base instável, desnivelada ou sem amarração",
        "descricao": (
            "Andaime simplesmente apoiado sem sapatas sobre base rígida e nivelada, calçado "
            "com material improvisado, assentado em terreno mole/irregular, ou torre alta não "
            "amarrada à estrutura nem estaiada."
        ),
        "sinais": [
            "andaime apoiado em tijolo",
            "andaime em cima de tabua",
            "andaime torto",
            "andaime no barro",
            "andaime sem sapata",
            "andaime alto sem amarracao",
            "torre de andaime bamba",
            "pe do andaime calcado com pedra",
        ],
        "itens": ["NR-18 18.12.13", "NR-18 18.12.3"],
        "gravidade_base": "critica",
    },
    "andaime_piso_incompleto": {
        "rotulo": "Piso de andaime sem forração completa ou sem travamento",
        "descricao": (
            "Superfície de trabalho do andaime com tábuas faltando, pranchas soltas ou "
            "desencaixadas, forração parcial, piso escorregadio ou desnivelado — ou uso de "
            "escada/caixote sobre o estrado para alcançar altura maior."
        ),
        "sinais": [
            "andaime com tabua faltando",
            "prancha solta no andaime",
            "piso do andaime incompleto",
            "so duas tabuas no andaime",
            "estrado desencaixado",
            "escada em cima do andaime",
            "caixote em cima do andaime",
            "madeira balancando no andaime",
        ],
        "itens": ["NR-18 18.12.5", "NR-18 18.12.8"],
        "gravidade_base": "critica",
    },
    "andaime_sem_guarda_corpo": {
        "rotulo": "Andaime sem guarda-corpo e rodapé no perímetro da plataforma",
        "descricao": (
            "Plataforma de andaime sem sistema de guarda-corpo com travessão superior, "
            "travessão intermediário e rodapé em todo o perímetro (exceto a face de "
            "trabalho), ou com esses elementos removidos/incompletos."
        ),
        "sinais": [
            "andaime sem guarda corpo",
            "andaime sem corrimao",
            "plataforma do andaime aberta",
            "andaime sem rodape",
            "falta a barra de protecao do andaime",
            "andaime so com o piso",
            "pedreiro no andaime sem protecao lateral",
        ],
        "itens": ["NR-18 18.12.1", "NR-18 18.12.15.2"],
        "gravidade_base": "critica",
    },
    "andaime_sem_travamento": {
        "rotulo": "Andaime tubular sem travamento contra desencaixe dos montantes e painéis",
        "descricao": (
            "Andaime tubular com montantes, painéis ou diagonais apenas encaixados, sem "
            "pinos, grampos ou travas que impeçam o desencaixe acidental das peças."
        ),
        "sinais": [
            "andaime sem pino de trava",
            "pecas do andaime so encaixadas",
            "andaime sem contraventamento",
            "falta diagonal no andaime",
            "andaime sem grampo",
            "quadro do andaime solto",
            "andaime amarrado com arame",
        ],
        "itens": ["NR-18 18.12.7"],
        "gravidade_base": "alta",
    },
    "andaime_acesso_improvisado": {
        "rotulo": "Acesso ao andaime feito por meio improvisado, sem escada adequada",
        "descricao": (
            "Trabalhador sobe ao piso de trabalho do andaime (acima de 1 m) escalando a "
            "própria estrutura, por rampa improvisada ou por escada solta, em vez de escada "
            "incorporada/acoplada aos painéis ou escada coletiva com corrimão."
        ),
        "sinais": [
            "subindo pela estrutura do andaime",
            "escalando o andaime",
            "andaime sem escada de acesso",
            "escada solta encostada no andaime",
            "tabua inclinada como acesso",
            "trepando nos travessoes",
            "acesso improvisado ao andaime",
        ],
        "itens": ["NR-18 18.12.14", "NR-18 18.12.8"],
        "gravidade_base": "alta",
    },
    "andaime_suspenso_irregular": {
        "rotulo": "Andaime suspenso sem sustentação, ancoragem ou estabilidade regulares",
        "descricao": (
            "Balancim/andaime suspenso sem os quatro pontos de sustentação independentes, "
            "sem placa de identificação, sem ponto de ancoragem do SPIQ independente do "
            "andaime, ou com sistema de fixação improvisado (contrapeso solto, apoio em "
            "platibanda sem laudo, enrolamento de cabo no corpo do equipamento)."
        ),
        "sinais": [
            "balancim pendurado",
            "andaime suspenso com contrapeso de tijolo",
            "balancim preso na platibanda",
            "cabo enrolado no balancim",
            "balancim sem placa",
            "andaime suspenso torto",
            "cinto preso no proprio balancim",
            "balancim so com dois cabos",
        ],
        "itens": ["NR-18 18.12.21", "NR-18 18.12.18", "NR-18 18.12.19"],
        "gravidade_base": "critica",
    },
    "plataforma_cavalete_irregular": {
        "rotulo": "Plataforma de trabalho sobre cavaletes fora dos limites permitidos",
        "descricao": (
            "Trabalho sobre plataforma apoiada em cavaletes com mais de 1,5 m de altura ou "
            "menos de 0,9 m de largura, ou sobre tábuas/pranchas soltas apoiadas em latões, "
            "tambores e apoios improvisados."
        ),
        "sinais": [
            "prancha sobre cavalete",
            "tabua apoiada em dois cavaletes",
            "plataforma improvisada com tambor",
            "cavalete alto demais",
            "prancha estreita sobre burrinho",
            "tabua sobre latas de tinta",
            "plataforma balancando",
        ],
        "itens": ["NR-18 18.12.11", "NR-18 18.12.8"],
        "gravidade_base": "alta",
    },
    "torre_elevador_sem_cancela": {
        "rotulo": "Torre de elevador de obra sem cancela ou sem fechamento na base",
        "descricao": (
            "Acesso à torre do elevador de obra sem barreira/cancela de no mínimo 1,8 m com "
            "intertravamento, ou base da torre sem fechamento de pelo menos 2 m em todos os "
            "lados com proteção e sinalização."
        ),
        "sinais": [
            "elevador de obra sem cancela",
            "torre do elevador aberta",
            "base do elevador sem tapume",
            "acesso ao elevador so com corrente",
            "cancela quebrada",
            "vao da torre do elevador aberto",
            "pessoa passando embaixo do elevador de obra",
        ],
        "itens": ["NR-18 18.11.13", "NR-18 18.11.14"],
        "gravidade_base": "alta",
    },
    # ------------------------------------------------------------------
    # Escadas, rampas e passarelas
    # ------------------------------------------------------------------
    "escada_mao_irregular": {
        "rotulo": "Escada de mão em condição irregular ou fora das dimensões permitidas",
        "descricao": (
            "Escada de mão com degraus quebrados, soltos ou improvisados, montante único, "
            "sem sapatas antiderrapantes, não fixada no apoio, com mais de 7 m ou sem "
            "ultrapassar em 1 m o piso superior de acesso."
        ),
        "sinais": [
            "escada bamba",
            "escada de mao improvisada",
            "escada com degrau quebrado",
            "escada de madeira pregada",
            "escada sem sapata",
            "escada escorregando",
            "escada curta demais",
            "escada apoiada solta na parede",
            "escada de um montante so",
        ],
        "itens": [
            "NR-18 18.8.6.13",
            "NR-18 18.8.6.14",
            "NR-18 18.8.6.12",
            "NR-35 Anexo III 5.2.2.5",
        ],
        "gravidade_base": "alta",
    },
    "escada_mao_local_perigoso": {
        "rotulo": "Escada portátil posicionada em local proibido ou sem isolamento",
        "descricao": (
            "Escada portátil montada junto a porta, área de circulação, abertura ou vão, "
            "apoiada em estrutura sem resistência, ou próxima a rede elétrica energizada, "
            "sem que a área no entorno esteja isolada e sinalizada."
        ),
        "sinais": [
            "escada na frente da porta",
            "escada no meio da passagem",
            "escada encostada perto de fiacao",
            "escada perto do buraco",
            "escada apoiada em tapume",
            "escada sem area isolada",
            "escada no corredor de circulacao",
        ],
        "itens": [
            "NR-18 18.8.6.8",
            "NR-18 18.8.6.9",
            "NR-35 Anexo III 5.2.2.7.3",
        ],
        "gravidade_base": "alta",
    },
    "escada_provisoria_coletiva_irregular": {
        "rotulo": "Escada provisória de uso coletivo sem proteção contra quedas ou fora de padrão",
        "descricao": (
            "Escada provisória de obra usada como circulação de trabalhadores sem sistema de "
            "proteção contra quedas nas laterais, com degraus de altura desigual, forração "
            "incompleta, largura insuficiente, sem patamar intermediário ou mal fixada; ou "
            "desnível maior que 0,40 m vencido sem escada nem rampa."
        ),
        "sinais": [
            "escada de obra sem corrimao",
            "escada provisoria de madeira",
            "degraus de altura diferente",
            "escada de obra sem patamar",
            "escada de concreto sem protecao lateral",
            "degrau faltando na escada da obra",
            "desnivel sem escada",
            "escada da obra estreita",
        ],
        "itens": ["NR-18 18.8.6.1", "NR-18 18.8.1"],
        "gravidade_base": "alta",
    },
    "rampa_passarela_irregular": {
        "rotulo": "Rampa ou passarela sem proteção contra quedas ou mal construída",
        "descricao": (
            "Rampa ou passarela de circulação sem sistema de proteção contra quedas em todo "
            "o perímetro, com piso frouxo/incompleto, largura menor que 0,80 m, ou sem peças "
            "transversais de apoio dos pés em rampas inclinadas; inclui travessia de vão com "
            "risco de queda feita sobre tábuas soltas em vez de passarela."
        ),
        "sinais": [
            "passarela sem guarda corpo",
            "rampa sem corrimao",
            "tabua atravessada sobre o vao",
            "prancha ligando duas lajes",
            "rampa escorregadia",
            "passarela de madeira solta",
            "rampa muito inclinada sem sarrafo",
            "passarela estreita",
        ],
        "itens": ["NR-18 18.8.7.1", "NR-18 18.8.7.2", "NR-18 18.8.3"],
        "gravidade_base": "alta",
    },
    # ------------------------------------------------------------------
    # Etapas de obra
    # ------------------------------------------------------------------
    "escavacao_sem_escoramento_ou_talude": {
        "rotulo": "Escavação com mais de 1,25 m sem talude ou escoramento e sem saída de emergência",
        "descricao": (
            "Vala, cava ou escavação com profundidade superior a 1,25 m com paredes verticais "
            "sem escoramento nem talude executado, escoramento danificado, borda carregada com "
            "material ou equipamento, ou sem escada/rampa de saída próxima ao posto de trabalho."
        ),
        "sinais": [
            "vala funda sem escoramento",
            "buraco com parede reta",
            "trabalhador dentro da vala",
            "terra amontoada na beira da vala",
            "vala sem escada para sair",
            "escoramento torto",
            "barranco desmoronando",
            "escavacao sem talude",
        ],
        "itens": ["NR-18 18.7.2.8", "NR-18 18.7.2.7", "NR-18 18.7.2.11"],
        "gravidade_base": "critica",
    },
    "escavacao_sem_isolamento_sinalizacao": {
        "rotulo": "Área de escavação, fundação ou desmonte sem isolamento e sinalização no perímetro",
        "descricao": (
            "Frente de escavação, fundação ou desmonte de rocha sem barreira de isolamento em "
            "todo o perímetro e sem sinalização de advertência visível, permitindo a entrada "
            "de pessoas e veículos não autorizados."
        ),
        "sinais": [
            "vala aberta sem cerca",
            "buraco sem sinalizacao",
            "escavacao sem isolamento",
            "cava aberta na circulacao",
            "sem placa de aviso perto do buraco",
            "carro passando perto da vala",
            "grade de isolamento derrubada",
        ],
        "itens": ["NR-18 18.7.2.2"],
        "gravidade_base": "alta",
    },
    "formas_escoramento_sem_projeto": {
        "rotulo": "Fôrmas e escoramento improvisados ou desforma sem isolamento da área",
        "descricao": (
            "Fôrmas e escoras de laje/pilar montadas de modo improvisado, escoras tortas, "
            "sem travamento, mal apoiadas ou já retiradas fora de sequência — ou montagem e "
            "desforma em curso sem isolamento e sinalização da área embaixo e no entorno."
        ),
        "sinais": [
            "escora torta",
            "escoramento improvisado com madeira",
            "escora sem apoio no chao",
            "forma de laje solta",
            "desforma sem isolar embaixo",
            "escoras retiradas cedo",
            "pontalete bambo",
            "madeira caindo na desforma",
        ],
        "itens": ["NR-18 18.7.4.1", "NR-18 18.7.4.2"],
        "gravidade_base": "alta",
    },
    "armadura_sem_escoramento": {
        "rotulo": "Armadura de pilar ou viga sem escoramento e sem prancha de circulação",
        "descricao": (
            "Gaiola de armadura de pilar, viga ou outra estrutura em pé sem apoio e "
            "escoramento contra tombamento, ou circulação de trabalhadores diretamente sobre "
            "a malha da armadura sem pranchas resistentes firmemente apoiadas."
        ),
        "sinais": [
            "gaiola de ferro em pe sem escora",
            "armadura de pilar solta",
            "andando em cima da ferragem",
            "malha de ferro sem prancha",
            "armadura pode tombar",
            "ferragem apoiada na parede",
            "pisando na armadura da laje",
        ],
        "itens": ["NR-18 18.7.3.4", "NR-18 18.7.3.5"],
        "gravidade_base": "alta",
    },
    "ferro_espera_sem_protecao": {
        "rotulo": "Extremidades de vergalhão (ferro de espera) sem proteção",
        "descricao": (
            "Pontas de vergalhão de aço projetando-se de laje, pilar, viga ou fundação, "
            "voltadas para área de circulação ou de trabalho, sem capa/pino de proteção nem "
            "dobra que elimine o risco de perfuração e empalamento."
        ),
        "sinais": [
            "ferro de espera sem pino",
            "vergalhao apontando pra cima",
            "ponta de ferro exposta",
            "ferro sem capa de protecao",
            "espera de pilar sem protetor",
            "arame e ferro saindo da laje",
            "vergalhao sem dobrar",
        ],
        "itens": ["NR-18 18.7.3.6"],
        "gravidade_base": "critica",
    },
    "area_carpintaria_armacao_irregular": {
        "rotulo": "Área de carpintaria ou armação sem cobertura, piso adequado ou isolamento",
        "descricao": (
            "Bancada de corte de madeira ou de corte/dobra de vergalhões instalada sem "
            "cobertura contra intempéries e queda de material, sobre piso irregular ou "
            "escorregadio, com resíduos acumulados, ou com a área de movimentação de "
            "vergalhões aberta à circulação de pessoas."
        ),
        "sinais": [
            "serra circular no sol",
            "bancada de carpintaria sem cobertura",
            "corte de ferro no meio do canteiro",
            "sobras de madeira embaixo da serra",
            "area de armacao sem isolamento",
            "piso de terra na carpintaria",
            "dobra de ferro sem area isolada",
        ],
        "itens": ["NR-18 18.7.3.1", "NR-18 18.7.3.2"],
        "gravidade_base": "media",
    },
    "telhado_cobertura_fragil": {
        "rotulo": "Trabalho sobre telhado ou cobertura frágil, escorregadia ou instável",
        "descricao": (
            "Trabalhador caminhando ou apoiado diretamente sobre telha de fibrocimento, "
            "zinco, translúcida ou cobertura sem resistência estrutural comprovada, sobre "
            "superfície molhada/escorregadia, ou concentrando carga em um mesmo ponto, "
            "sem tábua de distribuição e sem sistema de proteção contra quedas."
        ),
        "sinais": [
            "andando em cima da telha",
            "telha de amianto quebrando",
            "telhado velho furado",
            "pisando na telha translucida",
            "telhado molhado",
            "sem tabua sobre o telhado",
            "subiu no telhado sem cinto",
            "cobertura enferrujada",
        ],
        "itens": ["NR-18 18.7.8.2", "NR-18 18.7.8.1", "NR-35 35.6.1"],
        "gravidade_base": "critica",
    },
    "demolicao_sem_plano": {
        "rotulo": "Demolição executada sem plano e sem as precauções prévias",
        "descricao": (
            "Serviço de demolição em andamento sem evidência de Plano de Demolição "
            "implementado: linhas de energia, água, gás e esgoto ainda ativas, vizinhança "
            "e via desprotegidas, entulho acumulado na estrutura e ausência de isolamento "
            "da área."
        ),
        "sinais": [
            "demolicao com marreta",
            "parede sendo derrubada",
            "predio sendo demolido sem isolamento",
            "entulho acumulado na demolicao",
            "fiacao viva na demolicao",
            "demolicao com pessoas embaixo",
            "estrutura pela metade",
        ],
        "itens": ["NR-18 18.7.1.1", "NR-18 18.7.1.2"],
        "gravidade_base": "critica",
    },
    # ------------------------------------------------------------------
    # Organização do canteiro
    # ------------------------------------------------------------------
    "canteiro_desorganizado_circulacao_obstruida": {
        "rotulo": "Canteiro desorganizado com vias de circulação e passagens obstruídas",
        "descricao": (
            "Vias de circulação, passagens, corredores ou escadarias do canteiro obstruídos "
            "por materiais, ferramentas, mangueiras, cabos ou sobras, ou piso com saliências "
            "e depressões que dificultam a circulação de pessoas e materiais."
        ),
        "sinais": [
            "corredor cheio de material",
            "passagem obstruida",
            "canteiro baguncado",
            "mangueira atravessada no chao",
            "material jogado na circulacao",
            "escada com material em cima",
            "piso cheio de buraco e sobra",
        ],
        "itens": ["NR-18 18.16.15", "NR-18 18.16.4", "NR-08 8.3.2.1"],
        "gravidade_base": "media",
    },
    "entulho_sobras_acumulados": {
        "rotulo": "Entulho e sobras de material acumulados ou removidos de forma inadequada",
        "descricao": (
            "Entulho, sobras de material ou resíduos orgânicos acumulados no pavimento, "
            "jogados de nível superior sem calha fechada, expostos em local inadequado ou "
            "queimados no canteiro."
        ),
        "sinais": [
            "entulho acumulado",
            "monte de restos de obra",
            "jogando entulho pela janela",
            "sobra de material espalhada",
            "lixo acumulado no canteiro",
            "queimando lixo na obra",
            "cacamba transbordando",
        ],
        "itens": ["NR-18 18.16.16", "NR-18 18.16.17"],
        "gravidade_base": "media",
    },
    "madeira_com_prego_exposto": {
        "rotulo": "Madeira empilhada com pregos, arames ou fitas de amarração expostos",
        "descricao": (
            "Madeira retirada de fôrmas, escoramentos, andaimes ou tapumes empilhada ou "
            "deixada no piso sem que os pregos, arames e fitas de amarração tenham sido "
            "retirados ou rebatidos."
        ),
        "sinais": [
            "madeira com prego pra cima",
            "tabua com prego no chao",
            "sarrafo com prego exposto",
            "madeira empilhada com prego",
            "prego virado pra cima",
            "restos de forma com arame",
            "madeira de desforma jogada",
        ],
        "itens": ["NR-18 18.16.4.1"],
        "gravidade_base": "alta",
    },
    "empilhamento_material_instavel": {
        "rotulo": "Material armazenado ou empilhado de forma instável",
        "descricao": (
            "Pilha de blocos, tijolos, sacos, tubos, chapas ou feixes de vergalhão montada "
            "alta demais, desaprumada, sem calço ou amarração, apoiada em guarda-corpo ou "
            "junto à borda, com risco de desabamento ou escorregamento."
        ),
        "sinais": [
            "pilha de bloco torta",
            "sacos de cimento empilhados muito alto",
            "tubos soltos rolando",
            "chapas encostadas na parede",
            "feixe de vergalhao sem amarrar",
            "pilha desaprumada",
            "material empilhado na beirada",
            "empilhamento instavel",
        ],
        "itens": ["NR-18 18.16.4", "NR-18 18.7.3.3"],
        "gravidade_base": "alta",
    },
    "canteiro_sem_sinalizacao": {
        "rotulo": "Canteiro sem sinalização de segurança e sem vestimenta de alta visibilidade",
        "descricao": (
            "Ausência de placas e sinalização que advirtam sobre os riscos existentes, "
            "identifiquem áreas isoladas, acessos, circulação de veículos e obrigatoriedade "
            "de EPI; ou trabalhador em área de movimentação de veículos e cargas sem colete "
            "de alta visibilidade."
        ),
        "sinais": [
            "sem placa de aviso",
            "canteiro sem sinalizacao",
            "sem faixa de isolamento",
            "trabalhador sem colete refletivo",
            "area de manobra sem sinalizacao",
            "nenhuma placa de uso de epi",
            "acesso de veiculo sem demarcacao",
        ],
        "itens": ["NR-18 18.13.1", "NR-18 18.13.2"],
        "gravidade_base": "media",
    },
    "tapume_galeria_ausente": {
        "rotulo": "Obra sem tapume de fechamento ou sem galeria de proteção sobre o passeio",
        "descricao": (
            "Canteiro sem tapume de no mínimo 2 m que impeça o acesso de pessoas estranhas, "
            "ou obra com mais de dois pavimentos no alinhamento do logradouro sem galeria "
            "sobre o passeio protegendo pedestres."
        ),
        "sinais": [
            "obra aberta para a rua",
            "sem tapume na frente da obra",
            "tapume caido",
            "tapume baixo",
            "calcada sem protecao embaixo da obra",
            "pedestre passando embaixo da obra",
            "sem galeria sobre a calcada",
        ],
        "itens": ["NR-18 18.16.18", "NR-18 18.16.19"],
        "gravidade_base": "media",
    },
    # ------------------------------------------------------------------
    # Áreas de vivência e conforto
    # ------------------------------------------------------------------
    "instalacao_sanitaria_precaria": {
        "rotulo": "Instalação sanitária ausente, insuficiente ou em condição precária",
        "descricao": (
            "Banheiro de canteiro faltando, em número insuficiente para o efetivo, distante "
            "mais de 150 m do posto de trabalho, sem lavatório, bacia sifonada com tampo, "
            "mictório ou chuveiro, ou sem conservação, limpeza, revestimento lavável, "
            "ventilação e água canalizada."
        ),
        "sinais": [
            "banheiro de obra sujo",
            "banheiro quimico entupido",
            "sem banheiro no canteiro",
            "vaso sem tampa",
            "banheiro sem pia",
            "banheiro sem agua",
            "banheiro improvisado com lona",
            "sanitario longe da frente de servico",
        ],
        "itens": ["NR-18 18.5.3", "NR-18 18.5.5", "NR-24 24.2.3"],
        "gravidade_base": "alta",
    },
    "local_refeicao_inadequado": {
        "rotulo": "Local para refeições ausente ou sem condições de higiene e conforto",
        "descricao": (
            "Trabalhadores fazendo refeição na frente de serviço, sobre materiais ou no chão, "
            "por falta de local destinado a esse fim — ou refeitório sem mesas e assentos "
            "suficientes, sem proteção contra intempéries, sujo ou mal conservado."
        ),
        "sinais": [
            "comendo em cima de tijolo",
            "marmita no chao da obra",
            "refeitorio sem mesa",
            "almocando na laje",
            "refeitorio sujo",
            "sem lugar para refeicao",
            "comendo embaixo do sol",
        ],
        "itens": ["NR-18 18.5.1", "NR-18 18.5.7", "NR-24 24.5.2"],
        "gravidade_base": "media",
    },
    "agua_potavel_ausente": {
        "rotulo": "Fornecimento de água potável ausente, insuficiente ou inadequado",
        "descricao": (
            "Falta de bebedouro ou dispositivo equivalente de água potável, filtrada e fresca "
            "no canteiro, nas frentes de trabalho ou no alojamento; água em galão/balde "
            "aberto, recipiente não hermético, ou uso de copo coletivo."
        ),
        "sinais": [
            "sem bebedouro",
            "balde de agua aberto",
            "galao de agua no sol",
            "copo compartilhado",
            "garrafa pet de agua no chao",
            "agua quente para beber",
            "bebedouro longe da frente de trabalho",
        ],
        "itens": ["NR-18 18.5.6", "NR-24 24.9.1"],
        "gravidade_base": "alta",
    },
    "vestiario_inadequado": {
        "rotulo": "Vestiário ausente ou sem armários, higiene e revestimento adequados",
        "descricao": (
            "Ausência de vestiário onde a atividade exige troca de vestimenta ou chuveiro, "
            "ou vestiário sem armários individuais com trancamento, sem assentos, sem "
            "ventilação, sem piso e parede laváveis, ou em má conservação."
        ),
        "sinais": [
            "sem vestiario na obra",
            "roupa pendurada no andaime",
            "armario quebrado",
            "vestiario sem armario",
            "trocando de roupa no barracao",
            "vestiario sujo",
            "mochila jogada no chao do barracao",
        ],
        "itens": ["NR-24 24.4.1", "NR-24 24.4.3"],
        "gravidade_base": "media",
    },
    "sem_abrigo_intemperies_ceu_aberto": {
        "rotulo": "Trabalho a céu aberto sem abrigo contra intempéries",
        "descricao": (
            "Frente de trabalho a céu aberto sem abrigo, ainda que rústico, que proteja os "
            "trabalhadores de chuva, sol forte, frio ou vento, e sem medidas contra insolação "
            "excessiva durante a jornada."
        ),
        "sinais": [
            "trabalhando no sol sem sombra",
            "sem barraca no canteiro",
            "sem abrigo para chuva",
            "descanso embaixo de laje bruta",
            "sem cobertura na frente de servico",
            "sol forte sem protecao",
            "trabalhando na chuva",
        ],
        "itens": ["NR-21 21.1", "NR-21 21.2"],
        "gravidade_base": "media",
    },
    # ------------------------------------------------------------------
    # Sistemas individuais de proteção contra quedas
    # ------------------------------------------------------------------
    "spiq_cinturao_ausente_ou_danificado": {
        "rotulo": "Cinturão paraquedista ausente, desconectado ou com elementos danificados",
        "descricao": (
            "Trabalho em altura com retenção de queda sem cinturão tipo paraquedista, com "
            "cinturão vestido mas talabarte desconectado, ou com fitas, costuras, mosquetões "
            "e trava-quedas rasgados, deformados ou já submetidos a queda."
        ),
        "sinais": [
            "sem cinto de seguranca",
            "cinto solto pendurado",
            "talabarte desconectado",
            "cinturao rasgado",
            "mosquetao enferrujado",
            "cinto abdominal simples no lugar do paraquedista",
            "trava quedas amassado",
            "fita do cinto desfiada",
        ],
        "itens": ["NR-35 35.6.9", "NR-35 35.6.6.5", "NR-35 35.6.9.1.1"],
        "gravidade_base": "critica",
    },
    "ancoragem_sem_projeto": {
        "rotulo": "Ancoragem improvisada, sem projeto ou sem resistência comprovada",
        "descricao": (
            "Talabarte ou linha de vida fixado em ponto improvisado — tubo de andaime, "
            "vergalhão, tubulação, caixilho, telha, o próprio equipamento sobre o qual se "
            "trabalha — sem ancoragem estrutural projetada por profissional habilitado e "
            "sem dispositivo com resistência comprovada."
        ),
        "sinais": [
            "cinto amarrado no cano",
            "ancoragem improvisada",
            "corda presa no vergalhao",
            "linha de vida amarrada em tubo de andaime",
            "gancho preso na telha",
            "cabo de aco amarrado em qualquer ponto",
            "sem ponto de ancoragem definido",
        ],
        "itens": ["NR-35 Anexo II 3.2", "NR-35 Anexo II 4.3", "NR-18 18.12.12"],
        "gravidade_base": "alta",
    },
    "talabarte_mal_conectado": {
        "rotulo": "Talabarte mal posicionado, emendado ou com nós",
        "descricao": (
            "Talabarte ou trava-quedas ancorado abaixo do nível dos ombros ou muito longe, "
            "permitindo queda livre longa ou colisão com estrutura inferior, ou conectado a "
            "outro talabarte/extensor, ou preso por nós e laços."
        ),
        "sinais": [
            "talabarte com no",
            "dois talabartes emendados",
            "corda de seguranca com laco",
            "ancoragem abaixo dos pes",
            "talabarte muito folgado",
            "cinto preso em ponto baixo",
            "sobra de corda arrastando",
        ],
        "itens": ["NR-35 35.6.11.1", "NR-35 35.6.11.1.1"],
        "gravidade_base": "alta",
    },
}
