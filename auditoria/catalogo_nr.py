# -*- coding: utf-8 -*-
"""
Catálogo oficial das Normas Regulamentadoras (NR) de Segurança e Saúde no
Trabalho do Ministério do Trabalho e Emprego (MTE) do Brasil.

Cobertura: NR-01 a NR-38 (38 entradas), incluindo as REVOGADAS, que ficam
registradas com ``status="revogada"`` justamente para que o motor de laudos
possa RECUSAR citá-las em vez de alucinar itens inexistentes.

Situação em 2026-08-23: 38 números existentes, 36 vigentes e 2 revogadas
(NR-02 e NR-27).

Fontes dos títulos oficiais
---------------------------
1. Texto oficial dos PDFs publicados pelo MTE presentes neste repositório
   (fonte primária, título transcrito do cabeçalho do PDF): NR-01, NR-03,
   NR-04, NR-05, NR-06, NR-07, NR-08, NR-09, NR-10, NR-11, NR-12, NR-15,
   NR-16, NR-17, NR-18, NR-21, NR-23, NR-24, NR-26, NR-28, NR-33, NR-35.
2. Demais NRs: títulos conferidos por pesquisa cruzada em fontes públicas que
   reproduzem o texto oficial do MTE. A página oficial
   gov.br/trabalho-e-emprego .../normas-regulamentadoras-vigentes NÃO pôde ser
   acessada neste ambiente (bloqueio de egresso de rede), o que está
   registrado aqui por honestidade de proveniência.

Observação sobre a NR-10
------------------------
A Portaria MTE nº 737, de 29/05/2026, renomeia a NR-10 para "Segurança em
Instalações Elétricas e Serviços em Eletricidade", mas com vigência somente a
partir de 01/06/2027. Até lá o título vigente é o registrado abaixo.
"""

from __future__ import annotations

# Valores aceitos em cada campo controlado.
STATUS_VALIDOS = ("vigente", "revogada")
TIPOS_VALIDOS = ("geral", "setorial", "especial")

CATALOGO_NR: dict[str, dict] = {
    "NR-01": {
        "titulo": "Disposições Gerais e Gerenciamento de Riscos Ocupacionais",
        "status": "vigente",
        "revogada_por": None,
        "escopo": (
            "Norma-mãe: estabelece as disposições gerais, o campo de aplicação "
            "das demais NRs, os direitos e deveres de empregadores e "
            "trabalhadores e o Gerenciamento de Riscos Ocupacionais (GRO/PGR), "
            "incluindo inventário de riscos, plano de ação, treinamentos e "
            "ordens de serviço."
        ),
        "tipo": "geral",
        "palavras_chave": [
            "pgr",
            "programa de gerenciamento de riscos",
            "gro",
            "gerenciamento de riscos ocupacionais",
            "inventario de riscos",
            "inventário de riscos",
            "plano de acao",
            "plano de ação",
            "ordem de servico",
            "ordem de serviço",
            "treinamento",
            "capacitacao",
            "capacitação",
            "integracao",
            "integração",
            "riscos ocupacionais",
            "perigo",
            "documentacao de sst",
            "documentação de sst",
            "disposicoes gerais",
            "disposições gerais",
        ],
    },
    "NR-02": {
        "titulo": "Inspeção Prévia",
        "status": "revogada",
        "revogada_por": (
            "Portaria SEPRT/ME n.º 915, de 30 de julho de 2019 (DOU 31/07/2019)"
        ),
        "escopo": (
            "REVOGADA. Exigia que todo estabelecimento novo solicitasse "
            "aprovação prévia de suas instalações ao órgão regional do "
            "Ministério do Trabalho (CAI) antes de iniciar as atividades. Não "
            "pode ser citada em laudos: não há itens vigentes."
        ),
        "tipo": "geral",
        "palavras_chave": [
            "inspecao previa",
            "inspeção prévia",
            "aprovacao de instalacoes",
            "aprovação de instalações",
            "cai",
            "certificado de aprovacao de instalacoes",
            "certificado de aprovação de instalações",
            "novo estabelecimento",
            "inicio de funcionamento",
            "início de funcionamento",
            "revogada",
            "norma revogada",
        ],
    },
    "NR-03": {
        "titulo": "Embargo e Interdição",
        "status": "vigente",
        "revogada_por": None,
        "escopo": (
            "Disciplina os requisitos para a caracterização de grave e iminente "
            "risco (GIR) e os procedimentos de embargo de obra e interdição de "
            "estabelecimento, setor, máquina ou equipamento pela Inspeção do "
            "Trabalho."
        ),
        "tipo": "geral",
        "palavras_chave": [
            "embargo",
            "interdicao",
            "interdição",
            "grave e iminente risco",
            "gir",
            "risco grave",
            "paralisacao de obra",
            "paralisação de obra",
            "auditor fiscal do trabalho",
            "inspecao do trabalho",
            "inspeção do trabalho",
            "maquina interditada",
            "máquina interditada",
        ],
    },
    "NR-04": {
        "titulo": "Serviços Especializados em Segurança e em Medicina do Trabalho",
        "status": "vigente",
        "revogada_por": None,
        "escopo": (
            "Obriga empresas privadas e públicas a manter Serviços "
            "Especializados em Segurança e em Medicina do Trabalho (SESMT), "
            "dimensionados pelo grau de risco da atividade e pelo número de "
            "empregados do estabelecimento."
        ),
        "tipo": "geral",
        "palavras_chave": [
            "sesmt",
            "servico especializado",
            "serviço especializado",
            "medicina do trabalho",
            "engenheiro de seguranca",
            "engenheiro de segurança",
            "tecnico de seguranca do trabalho",
            "técnico de segurança do trabalho",
            "medico do trabalho",
            "médico do trabalho",
            "enfermeiro do trabalho",
            "auxiliar de enfermagem do trabalho",
            "grau de risco",
            "dimensionamento",
            "cnae",
        ],
    },
    "NR-05": {
        "titulo": "Comissão Interna de Prevenção de Acidentes e de Assédio - CIPA",
        "status": "vigente",
        "revogada_por": None,
        "escopo": (
            "Regula a constituição, o dimensionamento, a eleição e as "
            "atribuições da CIPA, cujo objetivo é a prevenção de acidentes e "
            "doenças do trabalho e, desde 2022, também a prevenção e o combate "
            "ao assédio sexual e demais violências no trabalho."
        ),
        "tipo": "geral",
        "palavras_chave": [
            "cipa",
            "comissao interna de prevencao de acidentes",
            "comissão interna de prevenção de acidentes",
            "assedio",
            "assédio",
            "assedio sexual",
            "assédio sexual",
            "mapa de risco",
            "eleicao cipa",
            "eleição cipa",
            "sipat",
            "cipatr",
            "quadro de avisos",
            "ata de reuniao",
            "ata de reunião",
            "designado de cipa",
        ],
    },
    "NR-06": {
        "titulo": "Equipamentos de Proteção Individual - EPI",
        "status": "vigente",
        "revogada_por": None,
        "escopo": (
            "Define o que é EPI, a obrigação do empregador de fornecer "
            "gratuitamente equipamento adequado ao risco, em perfeito estado e "
            "com Certificado de Aprovação (CA), além das obrigações de "
            "treinamento, higienização, substituição e registro de entrega."
        ),
        "tipo": "geral",
        "palavras_chave": [
            "epi",
            "equipamento de protecao individual",
            "equipamento de proteção individual",
            "capacete",
            "capacete sem jugular",
            "oculos de protecao",
            "óculos de proteção",
            "protetor auricular",
            "abafador",
            "luva",
            "bota",
            "botina",
            "calcado de seguranca",
            "calçado de segurança",
            "protetor facial",
            "mascara",
            "máscara",
            "respirador",
            "pff2",
            "certificado de aprovacao",
            "certificado de aprovação",
            "ca vencido",
            "sem epi",
            "uniforme",
            "colete refletivo",
        ],
    },
    "NR-07": {
        "titulo": "Programa de Controle Médico de Saúde Ocupacional - PCMSO",
        "status": "vigente",
        "revogada_por": None,
        "escopo": (
            "Exige a elaboração e implementação do PCMSO, com exames médicos "
            "ocupacionais (admissional, periódico, de retorno ao trabalho, de "
            "mudança de risco e demissional), emissão de ASO e monitoramento da "
            "saúde em função dos riscos do inventário do PGR."
        ),
        "tipo": "geral",
        "palavras_chave": [
            "pcmso",
            "exame medico ocupacional",
            "exame médico ocupacional",
            "aso",
            "atestado de saude ocupacional",
            "atestado de saúde ocupacional",
            "exame admissional",
            "exame periodico",
            "exame periódico",
            "exame demissional",
            "audiometria",
            "medico coordenador",
            "médico coordenador",
            "primeiros socorros",
            "material de primeiros socorros",
            "saude ocupacional",
            "saúde ocupacional",
        ],
    },
    "NR-08": {
        "titulo": "Edificações",
        "status": "vigente",
        "revogada_por": None,
        "escopo": (
            "Fixa requisitos técnicos mínimos das edificações que abrigam "
            "locais de trabalho: pé-direito, pisos, aberturas, escadas, rampas, "
            "passarelas, proteção contra intempéries e circulação segura."
        ),
        "tipo": "geral",
        "palavras_chave": [
            "edificacao",
            "edificação",
            "pe direito",
            "pé-direito",
            "piso",
            "piso irregular",
            "escada fixa",
            "corrimao",
            "corrimão",
            "guarda corpo",
            "guarda-corpo",
            "rampa",
            "passarela",
            "circulacao",
            "circulação",
            "cobertura",
            "protecao contra intemperies",
            "proteção contra intempéries",
            "abertura no piso",
        ],
    },
    "NR-09": {
        "titulo": (
            "Avaliação e Controle das Exposições Ocupacionais a Agentes "
            "Físicos, Químicos e Biológicos"
        ),
        "status": "vigente",
        "revogada_por": None,
        "escopo": (
            "Estabelece os critérios de avaliação quantitativa/qualitativa e as "
            "medidas de prevenção da exposição ocupacional a agentes físicos "
            "(ruído, vibração, calor, radiações), químicos e biológicos, "
            "integrada ao PGR da NR-01."
        ),
        "tipo": "geral",
        "palavras_chave": [
            "agente fisico",
            "agente físico",
            "agente quimico",
            "agente químico",
            "agente biologico",
            "agente biológico",
            "ruido",
            "ruído",
            "vibracao",
            "vibração",
            "calor",
            "radiacao",
            "radiação",
            "poeira",
            "particulado",
            "vapor",
            "avaliacao de exposicao",
            "avaliação de exposição",
            "limite de exposicao",
            "limite de exposição",
            "nivel de acao",
            "nível de ação",
            "ppra",
        ],
    },
    "NR-10": {
        "titulo": "Segurança em Instalações e Serviços em Eletricidade",
        "status": "vigente",
        "revogada_por": None,
        "escopo": (
            "Aplica-se a qualquer trabalho em instalações elétricas ou em suas "
            "proximidades, em todas as fases (projeto, construção, operação, "
            "manutenção, reforma e desativação), exigindo desenergização, "
            "aterramento, prontuário, medidas de controle do risco elétrico e "
            "trabalhadores autorizados. A Portaria MTE nº 737/2026 altera o "
            "título para 'Segurança em Instalações Elétricas e Serviços em "
            "Eletricidade' a partir de 01/06/2027."
        ),
        "tipo": "especial",
        "palavras_chave": [
            "eletricidade",
            "instalacao eletrica",
            "instalação elétrica",
            "choque eletrico",
            "choque elétrico",
            "arco eletrico",
            "arco elétrico",
            "quadro eletrico",
            "quadro elétrico",
            "quadro de distribuicao",
            "quadro de distribuição",
            "fiacao exposta",
            "fiação exposta",
            "cabo desencapado",
            "gambiarra",
            "desenergizacao",
            "desenergização",
            "bloqueio e etiquetagem",
            "loto",
            "aterramento",
            "prontuario de instalacoes eletricas",
            "prontuário de instalações elétricas",
            "alta tensao",
            "alta tensão",
            "baixa tensao",
            "baixa tensão",
            "sep",
            "trabalhador autorizado",
        ],
    },
    "NR-11": {
        "titulo": (
            "Transporte, Movimentação, Armazenagem e Manuseio de Materiais"
        ),
        "status": "vigente",
        "revogada_por": None,
        "escopo": (
            "Trata da operação segura de elevadores, guindastes, "
            "transportadores industriais e máquinas transportadoras, do "
            "transporte manual de sacos e do empilhamento e armazenagem de "
            "materiais."
        ),
        "tipo": "especial",
        "palavras_chave": [
            "empilhadeira",
            "empilhamento",
            "armazenagem",
            "estoque",
            "porta palete",
            "porta-palete",
            "palete",
            "movimentacao de materiais",
            "movimentação de materiais",
            "transporte manual de cargas",
            "guindaste",
            "talha",
            "ponte rolante",
            "elevador de carga",
            "transportador de correia",
            "esteira transportadora",
            "carga suspensa",
            "amarracao de carga",
            "amarração de carga",
            "operador habilitado",
            "corredor obstruido",
            "corredor obstruído",
        ],
    },
    "NR-12": {
        "titulo": "Segurança no Trabalho em Máquinas e Equipamentos",
        "status": "vigente",
        "revogada_por": None,
        "escopo": (
            "Define referências técnicas e medidas de proteção para máquinas e "
            "equipamentos de todos os tipos: proteções fixas e móveis "
            "intertravadas, dispositivos de parada de emergência, distâncias de "
            "segurança, zonas de prensagem e manutenção segura."
        ),
        "tipo": "especial",
        "palavras_chave": [
            "maquina",
            "máquina",
            "equipamento",
            "protecao fixa",
            "proteção fixa",
            "protecao movel intertravada",
            "proteção móvel intertravada",
            "intertravamento",
            "zona de prensagem",
            "ponto de operacao",
            "ponto de operação",
            "dispositivo de parada de emergencia",
            "dispositivo de parada de emergência",
            "botao de emergencia",
            "botão de emergência",
            "serra",
            "serra circular",
            "policorte",
            "esmerilhadeira",
            "prensa",
            "torno",
            "correia exposta",
            "polia exposta",
            "eixo cardan",
            "transmissao de forca",
            "transmissão de força",
            "sem protecao",
            "sem proteção",
            "coifa",
            "manual de instrucoes",
            "manual de instruções",
            "apreciacao de risco",
            "apreciação de risco",
        ],
    },
    "NR-13": {
        "titulo": (
            "Caldeiras, Vasos de Pressão, Tubulações e Tanques Metálicos de "
            "Armazenamento"
        ),
        "status": "vigente",
        "revogada_por": None,
        "escopo": (
            "Estabelece requisitos mínimos para gestão da integridade "
            "estrutural de caldeiras, vasos de pressão, tubulações de "
            "interligação e tanques metálicos de armazenamento, nos aspectos de "
            "instalação, inspeção, operação e manutenção."
        ),
        "tipo": "especial",
        "palavras_chave": [
            "caldeira",
            "vaso de pressao",
            "vaso de pressão",
            "tubulacao",
            "tubulação",
            "tanque metalico",
            "tanque metálico",
            "compressor",
            "reservatorio de ar comprimido",
            "reservatório de ar comprimido",
            "valvula de seguranca",
            "válvula de segurança",
            "manometro",
            "manômetro",
            "pressao interna",
            "pressão interna",
            "inspecao de seguranca periodica",
            "inspeção de segurança periódica",
            "prontuario",
            "prontuário",
            "placa de identificacao",
            "placa de identificação",
            "operador de caldeira",
            "casa de caldeiras",
            "autoclave",
        ],
    },
    "NR-14": {
        "titulo": "Fornos",
        "status": "vigente",
        "revogada_por": None,
        "escopo": (
            "Fixa requisitos de construção, isolamento térmico, instalação e "
            "operação de fornos industriais, incluindo proteção contra calor "
            "radiante, gases e explosão."
        ),
        "tipo": "especial",
        "palavras_chave": [
            "forno",
            "forno industrial",
            "calor radiante",
            "isolamento termico",
            "isolamento térmico",
            "queimador",
            "chama",
            "fornalha",
            "estufa industrial",
            "gases de combustao",
            "gases de combustão",
            "chamine",
            "chaminé",
            "risco de explosao",
            "risco de explosão",
            "superficie quente",
            "superfície quente",
        ],
    },
    "NR-15": {
        "titulo": "Atividades e Operações Insalubres",
        "status": "vigente",
        "revogada_por": None,
        "escopo": (
            "Caracteriza as atividades insalubres e seus limites de tolerância "
            "por meio de 14 anexos (ruído, calor, radiações, frio, umidade, "
            "vibração, agentes químicos, poeiras minerais, agentes biológicos), "
            "definindo os graus de adicional de insalubridade."
        ),
        "tipo": "geral",
        "palavras_chave": [
            "insalubridade",
            "insalubre",
            "limite de tolerancia",
            "limite de tolerância",
            "adicional de insalubridade",
            "ruido continuo",
            "ruído contínuo",
            "ruido de impacto",
            "ruído de impacto",
            "calor",
            "ibutg",
            "frio",
            "umidade",
            "poeira mineral",
            "silica",
            "sílica",
            "asbesto",
            "amianto",
            "benzeno",
            "chumbo",
            "agente biologico",
            "agente biológico",
            "radiacao ionizante",
            "radiação ionizante",
            "laudo de insalubridade",
        ],
    },
    "NR-16": {
        "titulo": "Atividades e Operações Perigosas",
        "status": "vigente",
        "revogada_por": None,
        "escopo": (
            "Caracteriza as atividades e operações perigosas que geram "
            "adicional de periculosidade: explosivos, inflamáveis, radiações "
            "ionizantes, energia elétrica, segurança pessoal/patrimonial e "
            "motociclistas."
        ),
        "tipo": "geral",
        "palavras_chave": [
            "periculosidade",
            "perigosa",
            "adicional de periculosidade",
            "explosivo",
            "inflamavel",
            "inflamável",
            "combustivel liquido",
            "combustível líquido",
            "abastecimento",
            "posto de combustivel",
            "posto de combustível",
            "radiacao ionizante",
            "radiação ionizante",
            "energia eletrica",
            "energia elétrica",
            "vigilante",
            "seguranca patrimonial",
            "segurança patrimonial",
            "motociclista",
            "motoboy",
            "laudo de periculosidade",
        ],
    },
    "NR-17": {
        "titulo": "Ergonomia",
        "status": "vigente",
        "revogada_por": None,
        "escopo": (
            "Estabelece parâmetros de adaptação das condições de trabalho às "
            "características psicofisiológicas dos trabalhadores: levantamento "
            "e transporte de cargas, mobiliário, postos de trabalho, "
            "equipamentos, condições ambientais e organização do trabalho, com "
            "exigência de AET quando indicada."
        ),
        "tipo": "geral",
        "palavras_chave": [
            "ergonomia",
            "ergonomico",
            "ergonômico",
            "postura",
            "postura inadequada",
            "levantamento de carga",
            "levantamento manual de peso",
            "esforco repetitivo",
            "esforço repetitivo",
            "ler dort",
            "mobiliario",
            "mobiliário",
            "cadeira",
            "bancada",
            "altura de trabalho",
            "iluminacao",
            "iluminação",
            "conforto termico",
            "conforto térmico",
            "aet",
            "analise ergonomica do trabalho",
            "análise ergonômica do trabalho",
            "pausa",
            "trabalho em pe",
            "trabalho em pé",
            "teletrabalho",
        ],
    },
    "NR-18": {
        "titulo": "Segurança e Saúde no Trabalho na Indústria da Construção",
        "status": "vigente",
        "revogada_por": None,
        "escopo": (
            "Norma setorial dos canteiros de obra: áreas de vivência, "
            "escavações, fundações, estruturas, andaimes e plataformas, "
            "escadas, formas, armações de aço, proteção contra quedas e queda "
            "de materiais, PGR da construção e ordem e limpeza no canteiro."
        ),
        "tipo": "setorial",
        "palavras_chave": [
            "canteiro de obras",
            "obra",
            "construcao civil",
            "construção civil",
            "andaime",
            "andaime fachadeiro",
            "andaime suspenso",
            "plataforma de trabalho",
            "guarda corpo e rodape",
            "guarda-corpo e rodapé",
            "protecao periferica",
            "proteção periférica",
            "escavacao",
            "escavação",
            "talude",
            "vala",
            "escoramento",
            "forma",
            "armacao de aco",
            "armação de aço",
            "vergalhao sem protecao",
            "vergalhão sem proteção",
            "ferro sem pino",
            "betoneira",
            "elevador de obra",
            "grua",
            "area de vivencia",
            "área de vivência",
            "alojamento",
            "refeitorio de obra",
            "refeitório de obra",
            "entulho",
            "ordem e limpeza",
            "queda de materiais",
            "bandeja de protecao",
            "bandeja de proteção",
        ],
    },
    "NR-19": {
        "titulo": "Explosivos",
        "status": "vigente",
        "revogada_por": None,
        "escopo": (
            "Disciplina o depósito, o manuseio, o transporte e a queima de "
            "explosivos e pólvoras, bem como a segurança em fábricas de "
            "explosivos e no uso de fogos de artifício."
        ),
        "tipo": "especial",
        "palavras_chave": [
            "explosivo",
            "polvora",
            "pólvora",
            "dinamite",
            "espoleta",
            "detonacao",
            "detonação",
            "paiol",
            "deposito de explosivos",
            "depósito de explosivos",
            "fogo de artificio",
            "fogo de artifício",
            "cordel detonante",
            "desmonte de rocha",
            "blaster",
        ],
    },
    "NR-20": {
        "titulo": (
            "Segurança e Saúde no Trabalho com Inflamáveis e Combustíveis"
        ),
        "status": "vigente",
        "revogada_por": None,
        "escopo": (
            "Estabelece requisitos mínimos para gestão da segurança nas "
            "atividades de extração, produção, armazenamento, transferência, "
            "manuseio e manipulação de inflamáveis e líquidos combustíveis, "
            "incluindo classificação das instalações e capacitação por classe."
        ),
        "tipo": "especial",
        "palavras_chave": [
            "inflamavel",
            "inflamável",
            "combustivel",
            "combustível",
            "liquido combustivel",
            "líquido combustível",
            "glp",
            "botijao de gas",
            "botijão de gás",
            "gas liquefeito",
            "gás liquefeito",
            "tanque de combustivel",
            "tanque de combustível",
            "posto de abastecimento",
            "area classificada",
            "área classificada",
            "atmosfera explosiva",
            "permissao de trabalho",
            "permissão de trabalho",
            "trabalho a quente",
            "solda proxima a inflamavel",
            "solda próxima a inflamável",
            "diesel",
            "gasolina",
            "solvente",
        ],
    },
    "NR-21": {
        "titulo": "Trabalhos a Céu Aberto",
        "status": "vigente",
        "revogada_por": None,
        "escopo": (
            "Exige proteção dos trabalhadores em atividades a céu aberto contra "
            "intempéries (sol, chuva, frio) por meio de abrigos, além de "
            "condições mínimas de moradia quando fornecida pelo empregador."
        ),
        "tipo": "geral",
        "palavras_chave": [
            "ceu aberto",
            "céu aberto",
            "trabalho ao ar livre",
            "insolacao",
            "insolação",
            "exposicao ao sol",
            "exposição ao sol",
            "intemperies",
            "intempéries",
            "abrigo",
            "sombra",
            "chuva",
            "protetor solar",
            "moradia do trabalhador",
            "agua potavel no campo",
            "água potável no campo",
        ],
    },
    "NR-22": {
        "titulo": "Segurança e Saúde Ocupacional na Mineração",
        "status": "vigente",
        "revogada_por": None,
        "escopo": (
            "Norma setorial aplicável a minas subterrâneas, minas a céu aberto, "
            "garimpos, beneficiamento mineral e pesquisa mineral, tratando de "
            "ventilação, escoramento, transporte, explosivos e plano de "
            "emergência."
        ),
        "tipo": "setorial",
        "palavras_chave": [
            "mineracao",
            "mineração",
            "mina",
            "mina subterranea",
            "mina subterrânea",
            "garimpo",
            "lavra",
            "beneficiamento mineral",
            "britagem",
            "pilha de esteril",
            "pilha de estéril",
            "barragem de rejeitos",
            "ventilacao de mina",
            "ventilação de mina",
            "escoramento de galeria",
            "teto e paredes",
            "poeira de mina",
        ],
    },
    "NR-23": {
        "titulo": "Proteção Contra Incêndios",
        "status": "vigente",
        "revogada_por": None,
        "escopo": (
            "Exige que todo estabelecimento disponha de proteção contra "
            "incêndio, saídas suficientes e desobstruídas para retirada rápida, "
            "equipamentos de combate ao fogo e trabalhadores treinados no uso "
            "correto desses equipamentos."
        ),
        "tipo": "geral",
        "palavras_chave": [
            "incendio",
            "incêndio",
            "extintor",
            "extintor obstruido",
            "extintor obstruído",
            "extintor vencido",
            "hidrante",
            "mangueira de incendio",
            "mangueira de incêndio",
            "saida de emergencia",
            "saída de emergência",
            "rota de fuga",
            "rota de fuga obstruida",
            "rota de fuga obstruída",
            "porta corta fogo",
            "porta corta-fogo",
            "alarme de incendio",
            "alarme de incêndio",
            "brigada de incendio",
            "brigada de incêndio",
            "sinalizacao de extintor",
            "sinalização de extintor",
            "combate a incendio",
            "combate a incêndio",
        ],
    },
    "NR-24": {
        "titulo": "Condições Sanitárias e de Conforto nos Locais de Trabalho",
        "status": "vigente",
        "revogada_por": None,
        "escopo": (
            "Fixa requisitos de instalações sanitárias, vestiários, refeitórios, "
            "cozinhas, locais para refeição, alojamentos e fornecimento de água "
            "potável nos locais de trabalho."
        ),
        "tipo": "geral",
        "palavras_chave": [
            "instalacao sanitaria",
            "instalação sanitária",
            "banheiro",
            "vaso sanitario",
            "vaso sanitário",
            "mictorio",
            "mictório",
            "lavatorio",
            "lavatório",
            "chuveiro",
            "vestiario",
            "vestiário",
            "armario",
            "armário",
            "refeitorio",
            "refeitório",
            "local para refeicao",
            "local para refeição",
            "cozinha",
            "alojamento",
            "agua potavel",
            "água potável",
            "bebedouro",
            "condicoes sanitarias",
            "condições sanitárias",
            "higiene",
        ],
    },
    "NR-25": {
        "titulo": "Resíduos Industriais",
        "status": "vigente",
        "revogada_por": None,
        "escopo": (
            "Determina medidas de eliminação, destinação e controle dos "
            "resíduos industriais sólidos, líquidos e gasosos, de modo a evitar "
            "risco à saúde e à segurança dos trabalhadores."
        ),
        "tipo": "geral",
        "palavras_chave": [
            "residuo industrial",
            "resíduo industrial",
            "residuo solido",
            "resíduo sólido",
            "efluente",
            "descarte",
            "destinacao de residuos",
            "destinação de resíduos",
            "residuo perigoso",
            "resíduo perigoso",
            "oleo usado",
            "óleo usado",
            "borra",
            "lancamento de gases",
            "lançamento de gases",
            "contaminacao",
            "contaminação",
            "tambor de residuo",
            "tambor de resíduo",
        ],
    },
    "NR-26": {
        "titulo": "Sinalização de Segurança",
        "status": "vigente",
        "revogada_por": None,
        "escopo": (
            "Define as cores de segurança e a sinalização a serem empregadas "
            "nos locais de trabalho para prevenir acidentes, além da rotulagem "
            "preventiva de produtos químicos conforme o GHS e as FISPQ."
        ),
        "tipo": "geral",
        "palavras_chave": [
            "sinalizacao",
            "sinalização",
            "sinalizacao de seguranca",
            "sinalização de segurança",
            "cores de seguranca",
            "cores de segurança",
            "placa de advertencia",
            "placa de advertência",
            "faixa amarela",
            "demarcacao de piso",
            "demarcação de piso",
            "rotulagem",
            "rotulo de produto quimico",
            "rótulo de produto químico",
            "ghs",
            "fispq",
            "fds",
            "pictograma",
            "tubulacao identificada",
            "tubulação identificada",
            "sem placa",
        ],
    },
    "NR-27": {
        "titulo": (
            "Registro Profissional do Técnico de Segurança do Trabalho no "
            "Ministério do Trabalho"
        ),
        "status": "revogada",
        "revogada_por": (
            "Portaria GM/MTE n.º 262, de 29 de maio de 2008 (DOU 30/05/2008)"
        ),
        "escopo": (
            "REVOGADA. Condicionava o exercício da profissão de Técnico de "
            "Segurança do Trabalho ao registro no Ministério do Trabalho. Não "
            "pode ser citada em laudos: não há itens vigentes."
        ),
        "tipo": "geral",
        "palavras_chave": [
            "registro profissional",
            "tecnico de seguranca do trabalho",
            "técnico de segurança do trabalho",
            "registro no ministerio do trabalho",
            "registro no ministério do trabalho",
            "habilitacao profissional",
            "habilitação profissional",
            "carteira profissional",
            "revogada",
            "norma revogada",
        ],
    },
    "NR-28": {
        "titulo": "Fiscalização e Penalidades",
        "status": "vigente",
        "revogada_por": None,
        "escopo": (
            "Disciplina o procedimento de fiscalização das NRs pela Auditoria "
            "Fiscal do Trabalho, os prazos para correção de irregularidades e a "
            "gradação das multas aplicáveis por infração a cada item das normas."
        ),
        "tipo": "geral",
        "palavras_chave": [
            "fiscalizacao",
            "fiscalização",
            "penalidade",
            "multa",
            "auto de infracao",
            "auto de infração",
            "notificacao",
            "notificação",
            "prazo para correcao",
            "prazo para correção",
            "gradacao de multa",
            "gradação de multa",
            "infracao",
            "infração",
            "auditor fiscal do trabalho",
            "dupla visita",
        ],
    },
    "NR-29": {
        "titulo": "Norma Regulamentadora de Segurança e Saúde no Trabalho Portuário",
        "status": "vigente",
        "revogada_por": None,
        "escopo": (
            "Norma setorial que regula a proteção obrigatória contra acidentes "
            "e doenças no trabalho portuário, a bordo e em terra, abrangendo "
            "operação de cargas, equipamentos portuários e acessos."
        ),
        "tipo": "setorial",
        "palavras_chave": [
            "porto",
            "portuario",
            "portuário",
            "trabalho portuario",
            "trabalho portuário",
            "cais",
            "navio",
            "conteiner",
            "contêiner",
            "porao",
            "porão",
            "estiva",
            "capatazia",
            "guindaste portuario",
            "guindaste portuário",
            "ogmo",
            "movimentacao de carga no cais",
            "movimentação de carga no cais",
            "prancha de acesso",
        ],
    },
    "NR-30": {
        "titulo": "Segurança e Saúde no Trabalho Aquaviário",
        "status": "vigente",
        "revogada_por": None,
        "escopo": (
            "Norma setorial aplicável aos trabalhadores de embarcações "
            "comerciais, de pesca e de apoio, tratando de condições de bordo, "
            "convés, máquinas, alojamentos e plataformas de trabalho aquaviário."
        ),
        "tipo": "setorial",
        "palavras_chave": [
            "aquaviario",
            "aquaviário",
            "embarcacao",
            "embarcação",
            "navio",
            "convés",
            "conves",
            "tripulacao",
            "tripulação",
            "pesca",
            "barco pesqueiro",
            "praca de maquinas",
            "praça de máquinas",
            "colete salva vidas",
            "colete salva-vidas",
            "homem ao mar",
            "alojamento de bordo",
        ],
    },
    "NR-31": {
        "titulo": (
            "Segurança e Saúde no Trabalho na Agricultura, Pecuária, "
            "Silvicultura, Exploração Florestal e Aquicultura"
        ),
        "status": "vigente",
        "revogada_por": None,
        "escopo": (
            "Norma setorial do meio rural: agrotóxicos, máquinas e implementos "
            "agrícolas, tratores, colheitadeiras, motosserras, trabalho com "
            "animais, transporte de trabalhadores rurais, alojamentos e áreas "
            "de vivência no campo."
        ),
        "tipo": "setorial",
        "palavras_chave": [
            "rural",
            "agricultura",
            "pecuaria",
            "pecuária",
            "silvicultura",
            "exploracao florestal",
            "exploração florestal",
            "aquicultura",
            "agrotoxico",
            "agrotóxico",
            "defensivo agricola",
            "defensivo agrícola",
            "pulverizacao",
            "pulverização",
            "trator",
            "trator sem estrutura de protecao",
            "epcc",
            "colheitadeira",
            "motosserra",
            "roçadeira",
            "rocadeira",
            "implemento agricola",
            "implemento agrícola",
            "tomada de potencia",
            "tomada de potência",
            "curral",
            "lavoura",
            "transporte de trabalhadores rurais",
        ],
    },
    "NR-32": {
        "titulo": "Segurança e Saúde no Trabalho em Serviços de Saúde",
        "status": "vigente",
        "revogada_por": None,
        "escopo": (
            "Norma setorial para hospitais, clínicas, laboratórios e demais "
            "serviços de saúde, tratando de risco biológico, perfurocortantes, "
            "quimioterápicos, radiações ionizantes, gases medicinais, "
            "lavanderia e resíduos de serviços de saúde."
        ),
        "tipo": "setorial",
        "palavras_chave": [
            "servico de saude",
            "serviço de saúde",
            "hospital",
            "clinica",
            "clínica",
            "laboratorio",
            "laboratório",
            "risco biologico",
            "risco biológico",
            "perfurocortante",
            "agulha",
            "descarpack",
            "caixa de perfurocortantes",
            "quimioterapico",
            "quimioterápico",
            "radiacao ionizante",
            "radiação ionizante",
            "raio x",
            "gas medicinal",
            "gás medicinal",
            "esterilizacao",
            "esterilização",
            "rss",
            "residuo de servico de saude",
            "resíduo de serviço de saúde",
            "vacinacao de trabalhadores",
            "vacinação de trabalhadores",
            "lavanderia hospitalar",
        ],
    },
    "NR-33": {
        "titulo": "Segurança e Saúde nos Trabalhos em Espaços Confinados",
        "status": "vigente",
        "revogada_por": None,
        "escopo": (
            "Estabelece os requisitos mínimos para identificação, sinalização, "
            "isolamento e entrada segura em espaços confinados, com Permissão "
            "de Entrada e Trabalho (PET), monitoramento atmosférico, vigia, "
            "supervisor de entrada e plano de resgate."
        ),
        "tipo": "especial",
        "palavras_chave": [
            "espaco confinado",
            "espaço confinado",
            "tanque",
            "silo",
            "cisterna",
            "caixa d agua",
            "caixa d'água",
            "galeria",
            "poco",
            "poço",
            "reservatorio fechado",
            "reservatório fechado",
            "pet",
            "permissao de entrada e trabalho",
            "permissão de entrada e trabalho",
            "vigia",
            "supervisor de entrada",
            "monitoramento atmosferico",
            "monitoramento atmosférico",
            "deteccao de gases",
            "detecção de gases",
            "oxigenio",
            "oxigênio",
            "ventilacao forcada",
            "ventilação forçada",
            "resgate",
            "tripe de resgate",
            "tripé de resgate",
            "atmosfera imediatamente perigosa a vida",
            "iplvs",
        ],
    },
    "NR-34": {
        "titulo": (
            "Condições e Meio Ambiente de Trabalho na Indústria da Construção, "
            "Reparação e Desmonte Naval"
        ),
        "status": "vigente",
        "revogada_por": None,
        "escopo": (
            "Norma setorial dos estaleiros e da atividade naval: trabalho a "
            "quente, jateamento e pintura, movimentação de cargas em "
            "estaleiro, trabalho em altura e em espaços confinados em "
            "embarcações e estruturas navais."
        ),
        "tipo": "setorial",
        "palavras_chave": [
            "naval",
            "estaleiro",
            "construcao naval",
            "construção naval",
            "reparacao naval",
            "reparação naval",
            "desmonte naval",
            "embarcacao",
            "embarcação",
            "dique seco",
            "trabalho a quente",
            "solda em estaleiro",
            "jateamento",
            "pintura industrial",
            "andaime em embarcacao",
            "andaime em embarcação",
            "casco",
        ],
    },
    "NR-35": {
        "titulo": "Trabalho em Altura",
        "status": "vigente",
        "revogada_por": None,
        "escopo": (
            "Aplica-se a toda atividade executada acima de 2,00 m do nível "
            "inferior onde haja risco de queda, exigindo análise de risco, "
            "permissão de trabalho, sistema de proteção contra quedas, "
            "capacitação e plano de emergência e resgate."
        ),
        "tipo": "especial",
        "palavras_chave": [
            "altura",
            "trabalho em altura",
            "acima de 2 metros",
            "acima de 2,00 m",
            "risco de queda",
            "queda de altura",
            "cinturao",
            "cinturão",
            "cinturao de seguranca tipo paraquedista",
            "cinturão de segurança tipo paraquedista",
            "talabarte",
            "talabarte duplo",
            "trava quedas",
            "trava-quedas",
            "linha de vida",
            "ancoragem",
            "ponto de ancoragem",
            "telhado",
            "cobertura",
            "escada de mao",
            "escada de mão",
            "plataforma elevatoria",
            "plataforma elevatória",
            "pta",
            "cadeira suspensa",
            "sem cinto",
            "analise de risco",
            "análise de risco",
            "permissao de trabalho",
            "permissão de trabalho",
            "resgate em altura",
        ],
    },
    "NR-36": {
        "titulo": (
            "Segurança e Saúde no Trabalho em Empresas de Abate e "
            "Processamento de Carnes e Derivados"
        ),
        "status": "vigente",
        "revogada_por": None,
        "escopo": (
            "Norma setorial dos frigoríficos e abatedouros: mobiliário e postos "
            "de trabalho, ritmo e pausas, facas e equipamentos de corte, "
            "ambientes frios, plataformas e passarelas e movimentação de "
            "carcaças."
        ),
        "tipo": "setorial",
        "palavras_chave": [
            "frigorifico",
            "frigorífico",
            "abate",
            "abatedouro",
            "processamento de carnes",
            "desossa",
            "faca",
            "afiacao",
            "afiação",
            "camara fria",
            "câmara fria",
            "ambiente artificialmente frio",
            "nora",
            "carcaca",
            "carcaça",
            "linha de producao de carnes",
            "linha de produção de carnes",
            "pausa psicofisiologica",
            "pausa psicofisiológica",
            "luva de malha de aco",
            "luva de malha de aço",
        ],
    },
    "NR-37": {
        "titulo": "Segurança e Saúde em Plataformas de Petróleo",
        "status": "vigente",
        "revogada_por": None,
        "escopo": (
            "Norma setorial aplicável às plataformas de petróleo fixas e "
            "flutuantes em águas jurisdicionais brasileiras, tratando de "
            "acomodações, sistemas de emergência e abandono, movimentação de "
            "cargas e transporte de pessoas para bordo."
        ),
        "tipo": "setorial",
        "palavras_chave": [
            "plataforma de petroleo",
            "plataforma de petróleo",
            "offshore",
            "petroleo",
            "petróleo",
            "sonda de perfuracao",
            "sonda de perfuração",
            "fpso",
            "abandono de plataforma",
            "baleeira",
            "heliponto",
            "modulo de acomodacao",
            "módulo de acomodação",
            "aguas jurisdicionais brasileiras",
            "águas jurisdicionais brasileiras",
            "transferencia de pessoas por guindaste",
            "transferência de pessoas por guindaste",
        ],
    },
    "NR-38": {
        "titulo": (
            "Segurança e Saúde no Trabalho nas Atividades de Limpeza Urbana e "
            "Manejo de Resíduos Sólidos"
        ),
        "status": "vigente",
        "revogada_por": None,
        "escopo": (
            "Norma setorial da limpeza urbana: coleta de resíduos sólidos, "
            "varrição, capina, transporte, triagem e destinação, incluindo "
            "coletores em via pública, veículos coletores e unidades de "
            "tratamento e aterros."
        ),
        "tipo": "setorial",
        "palavras_chave": [
            "limpeza urbana",
            "manejo de residuos solidos",
            "manejo de resíduos sólidos",
            "coleta de lixo",
            "gari",
            "coletor de residuos",
            "coletor de resíduos",
            "varricao",
            "varrição",
            "capina",
            "caminhao compactador",
            "caminhão compactador",
            "estribo traseiro",
            "aterro sanitario",
            "aterro sanitário",
            "usina de triagem",
            "catador",
            "residuo domiciliar",
            "resíduo domiciliar",
            "via publica",
            "via pública",
        ],
    },
}


# --- Consistência interna (falha cedo se o catálogo for corrompido) ---------

# Conjuntos, não tuplas: o uso natural em todo o código é pertencência e
# diferença ("quais vigentes ainda não têm texto carregado").
NRS_REVOGADAS: frozenset[str] = frozenset(
    k for k, v in CATALOGO_NR.items() if v["status"] == "revogada"
)
NRS_VIGENTES: frozenset[str] = frozenset(
    k for k, v in CATALOGO_NR.items() if v["status"] == "vigente"
)


def _validar() -> None:
    esperadas = {f"NR-{n:02d}" for n in range(1, 39)}
    faltando = esperadas - set(CATALOGO_NR)
    sobrando = set(CATALOGO_NR) - esperadas
    if faltando or sobrando:
        raise ValueError(f"catálogo inconsistente: faltando={faltando} sobrando={sobrando}")
    for codigo, dados in CATALOGO_NR.items():
        for campo in ("titulo", "status", "revogada_por", "escopo", "tipo", "palavras_chave"):
            if campo not in dados:
                raise ValueError(f"{codigo}: campo obrigatório ausente: {campo}")
        if dados["status"] not in STATUS_VALIDOS:
            raise ValueError(f"{codigo}: status inválido: {dados['status']!r}")
        if dados["tipo"] not in TIPOS_VALIDOS:
            raise ValueError(f"{codigo}: tipo inválido: {dados['tipo']!r}")
        if len(dados["palavras_chave"]) < 6:
            raise ValueError(f"{codigo}: mínimo de 6 palavras-chave")
        if any(p != p.lower() for p in dados["palavras_chave"]):
            raise ValueError(f"{codigo}: palavras-chave devem estar em minúsculas")
        if (dados["status"] == "revogada") != bool(dados["revogada_por"]):
            raise ValueError(f"{codigo}: 'revogada_por' incoerente com 'status'")


_validar()


def esta_vigente(codigo: str) -> bool:
    """True se a NR existe e está vigente. Use antes de citar itens em laudo."""
    dados = CATALOGO_NR.get(_normalizar_codigo(codigo))
    return bool(dados) and dados["status"] == "vigente"


def _normalizar_codigo(codigo: str) -> str:
    """Aceita 'nr 5', 'NR-5', 'NR05', '5' e devolve o código canônico 'NR-05'."""
    bruto = "".join(ch for ch in str(codigo) if ch.isdigit())
    if not bruto:
        return str(codigo).strip().upper()
    return f"NR-{int(bruto):02d}"


__all__ = [
    "CATALOGO_NR",
    "NRS_VIGENTES",
    "NRS_REVOGADAS",
    "STATUS_VALIDOS",
    "TIPOS_VALIDOS",
    "esta_vigente",
]
