"""Identidade visual do app — tudo que é aparência mora aqui.

Para ajustar a paleta, mexa só em `PALETA`. Os seletores `data-testid` e as
classes `st-*` são do Streamlit e podem mudar entre versões; os mais frágeis
estão marcados com [FRÁGIL] para facilitar a caça quando uma atualização quebrar.
Nada neste módulo toca estado, widgets ou fluxo.
"""

import streamlit as st

PALETA = {
    "primaria": "#0F4C5C",
    "primaria_escura": "#0A3642",
    "acento": "#1B998B",
    "fundo": "#F5F7FA",
    "card": "#FFFFFF",
    "borda": "#DCE3EA",
    "texto": "#1F2933",
    "texto_suave": "#5B6B7A",
}

# Nome exibido no cabeçalho. Troque aqui; nada mais depende dele.
MARCA = "NormaLens"
SUBTITULO = "Auditoria de NRs por imagem"

_FONTES = (
    "https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap"
)

_CSS = """
@import url('__FONTES__');

:root {
  --pri: __primaria__; --pri-esc: __primaria_escura__; --ace: __acento__;
  --fundo: __fundo__; --card: __card__; --borda: __borda__;
  --txt: __texto__; --suave: __texto_suave__;
  --sombra: 0 1px 2px rgba(15,76,92,.06), 0 4px 14px rgba(15,76,92,.07);
  --sombra-hover: 0 4px 10px rgba(15,76,92,.14), 0 10px 24px rgba(15,76,92,.12);
  --raio: 12px;
}

html, body, [data-testid="stAppViewContainer"], .stApp {
  font-family: 'Inter', system-ui, -apple-system, 'Segoe UI', sans-serif;
  color: var(--txt);
}

/* [FRÁGIL] faixa de marca no topo, sobre o header nativo */
[data-testid="stHeader"] {
  background: linear-gradient(90deg, var(--pri-esc), var(--pri) 55%, var(--ace));
  height: 3rem;
}
[data-testid="stHeader"]::before {
  content: "__MARCA__"; color: #fff; font-weight: 700; font-size: 1.15rem;
  letter-spacing: -.01em; padding-left: 1rem; display: flex; align-items: center; gap: .6rem;
}
[data-testid="stHeader"]::after {
  content: "__SUBTITULO__"; position: absolute; left: 9.2rem; top: 0; height: 100%;
  display: flex; align-items: center; color: rgba(255,255,255,.75); font-size: .85rem;
  border-left: 1px solid rgba(255,255,255,.35); padding-left: .8rem; pointer-events: none;
}
@media (max-width: 640px) { [data-testid="stHeader"]::after { display: none; } }
[data-testid="stHeader"] button, [data-testid="stHeader"] svg { color: #fff !important; }

[data-testid="stMainBlockContainer"], .block-container { padding-top: 2.2rem; max-width: 1280px; }

/* Tipografia */
h1 { font-weight: 700 !important; letter-spacing: -.02em; color: var(--pri) !important; }
h2, h3 { font-weight: 600 !important; letter-spacing: -.01em; color: var(--pri-esc) !important; }
[data-testid="stCaptionContainer"], .stCaption { color: var(--suave) !important; }
hr { border-color: var(--borda) !important; }

/* Sidebar */
[data-testid="stSidebar"] { background: var(--card); border-right: 1px solid var(--borda); }
[data-testid="stSidebar"] h3 {
  font-size: .78rem !important; text-transform: uppercase; letter-spacing: .08em;
  color: var(--suave) !important; font-weight: 600 !important;
}

/* Botões: secundário com contorno, primário sólido, hover com elevação */
.stButton > button, .stDownloadButton > button,
[data-testid="stBaseButton-secondary"], [data-testid="stBaseButton-primary"] {
  border-radius: 10px; font-weight: 600; transition: all .15s ease;
}
[data-testid="stBaseButton-secondary"] {
  background: var(--card); color: var(--pri); border: 1.5px solid var(--pri);
}
[data-testid="stBaseButton-secondary"]:hover {
  background: #E8F1F3; border-color: var(--pri); color: var(--pri-esc);
  box-shadow: var(--sombra); transform: translateY(-1px);
}
[data-testid="stBaseButton-primary"] {
  background: linear-gradient(180deg, var(--pri), var(--pri-esc)); color: #fff; border: none;
  box-shadow: 0 2px 6px rgba(15,76,92,.25);
}
[data-testid="stBaseButton-primary"]:hover {
  background: linear-gradient(180deg, var(--ace), var(--pri)); color: #fff;
  box-shadow: var(--sombra-hover); transform: translateY(-1px);
}
[data-testid="stBaseButton-primary"]:disabled, [data-testid="stBaseButton-secondary"]:disabled {
  background: #E5EAEF; color: #6B7A89; border: 1.5px solid var(--borda);
  box-shadow: none; transform: none; opacity: 1; cursor: not-allowed;
}
/* Download em destaque: preenchido com o acento */
.stDownloadButton > button {
  background: var(--ace); color: #fff; border: none; box-shadow: 0 2px 6px rgba(27,153,139,.3);
}
.stDownloadButton > button:hover {
  background: #148377; color: #fff; box-shadow: var(--sombra-hover); transform: translateY(-1px);
}

/* Upload: dropzone destacada. [FRÁGIL] stFileUploaderDropzone */
[data-testid="stFileUploaderDropzone"] {
  border: 2px dashed var(--ace); border-radius: var(--raio);
  background: linear-gradient(180deg, #F2FAF9, #FFFFFF); padding: 1.6rem 1rem;
  transition: all .15s ease;
}
[data-testid="stFileUploaderDropzone"]:hover {
  border-color: var(--pri); background: #E8F4F2; box-shadow: var(--sombra);
}

/* Cards: expanders, métricas e abas. [FRÁGIL] stExpander / stMetric */
[data-testid="stExpander"] {
  border: 1px solid var(--borda); border-radius: var(--raio);
  background: var(--card); box-shadow: var(--sombra); overflow: hidden;
}
[data-testid="stExpander"] summary { font-weight: 600; color: var(--pri-esc); }
[data-testid="stMetric"] {
  background: var(--card); border: 1px solid var(--borda); border-left: 4px solid var(--ace);
  border-radius: var(--raio); padding: .9rem 1rem; box-shadow: var(--sombra);
}
[data-testid="stMetricLabel"] { color: var(--suave); font-weight: 500; }
[data-testid="stMetricValue"] { color: var(--pri); font-weight: 700; }

/* Inputs */
[data-testid="stTextInput"] input, [data-testid="stTextArea"] textarea,
[data-testid="stDateInput"] input {
  border-radius: 10px; border-color: var(--borda);
}
[data-testid="stTextInput"] input:focus, [data-testid="stTextArea"] textarea:focus {
  border-color: var(--ace); box-shadow: 0 0 0 3px rgba(27,153,139,.18);
}

/* Abas */
[data-baseweb="tab-list"] { gap: .25rem; border-bottom: 1px solid var(--borda); }
[data-baseweb="tab"] { font-weight: 600; border-radius: 8px 8px 0 0; }
[aria-selected="true"][data-baseweb="tab"] { color: var(--pri); }
[data-baseweb="tab-highlight"] { background: var(--ace) !important; height: 3px; }

/* Alertas com a mesma gramática: borda lateral colorida. [FRÁGIL] stAlert */
[data-testid="stAlert"] { border-radius: var(--raio); border: 1px solid var(--borda); }

/* Imagens e tabelas */
[data-testid="stImage"] img { border-radius: 10px; border: 1px solid var(--borda); }
[data-testid="stTable"] table, [data-testid="stDataFrame"] {
  border-radius: 10px; overflow: hidden; border: 1px solid var(--borda);
}
[data-testid="stTable"] th { background: #EAF1F4; color: var(--pri-esc); }

/* Badge de gravidade: texto + cor, legível também sem cor */
.nr-badge { display:inline-block; padding:.1rem .6rem; border-radius:999px; font-size:.78rem;
  font-weight:700; letter-spacing:.02em; border:1px solid transparent; }
.nr-badge.critica { background:#FDE8E8; color:#9B1C1C; border-color:#F5B5B5; }
.nr-badge.alta    { background:#FEEBDC; color:#9A3412; border-color:#F8C7A1; }
.nr-badge.media   { background:#FEF6D8; color:#7A5B00; border-color:#F1DE92; }
.nr-badge.baixa   { background:#E3F4EF; color:#0E6B5F; border-color:#A9DCCF; }

/* Selo de status da miniatura */
.nr-status { display:block; text-align:center; margin:-.3rem auto .6rem; width:fit-content;
  padding:.1rem .6rem; border-radius:999px; font-size:.74rem; font-weight:700; border:1px solid transparent; }
.nr-status.pendente { background:#EEF1F4; color:#5B6B7A; border-color:var(--borda); }
.nr-status.auditada { background:#E3F4EF; color:#0E6B5F; border-color:#A9DCCF; }
.nr-status.falhou   { background:#FDE8E8; color:#9B1C1C; border-color:#F5B5B5; }

/* Estado vazio: como funciona */
.nr-vazio { display:grid; grid-template-columns:repeat(auto-fit,minmax(200px,1fr)); gap:.8rem; margin:.4rem 0 1rem; }
.nr-vazio > div { background:var(--card); border:1px solid var(--borda); border-radius:var(--raio);
  padding:.9rem 1rem; box-shadow:var(--sombra); font-size:.9rem; color:var(--suave); }
.nr-vazio b { display:block; color:var(--pri-esc); margin-bottom:.2rem; }

/* Stepper (HTML próprio, ver `stepper()`) */
.nr-stepper { display: flex; gap: .5rem; margin: .4rem 0 1.4rem; flex-wrap: wrap; }
.nr-passo {
  flex: 1 1 140px; display: flex; align-items: center; gap: .6rem;
  padding: .6rem .9rem; border-radius: var(--raio); background: var(--card);
  border: 1px solid var(--borda); color: var(--suave); font-weight: 500; font-size: .9rem;
}
.nr-passo .nr-num {
  width: 1.7rem; height: 1.7rem; border-radius: 50%; display: grid; place-items: center;
  background: #E5EAEF; color: var(--suave); font-weight: 700; font-size: .8rem; flex: none;
}
.nr-passo.ativo { border-color: var(--pri); color: var(--pri); box-shadow: var(--sombra); font-weight: 600; }
.nr-passo.ativo .nr-num { background: var(--pri); color: #fff; }
.nr-passo.feito { border-color: var(--ace); color: #0E7469; }
.nr-passo.feito .nr-num { background: var(--ace); color: #fff; }

@media (max-width: 640px) {
  [data-testid="stMainBlockContainer"], .block-container { padding: 1.2rem .8rem; }
  .nr-passo { flex-basis: 45%; }
}
"""


def aplicar_estilos() -> None:
    """Injeta o CSS global. Chamar uma vez, logo após `set_page_config`."""
    css = _CSS.replace("__FONTES__", _FONTES)
    css = css.replace("__MARCA__", MARCA).replace("__SUBTITULO__", SUBTITULO)
    for chave, valor in PALETA.items():
        css = css.replace(f"__{chave}__", valor)
    st.markdown(f"<style>{css}</style>", unsafe_allow_html=True)


def stepper(passos: list[tuple[str, str]]) -> str:
    """HTML do indicador de etapas. `passos` = [(rótulo, "pendente|ativo|feito")].

    Puramente visual: quem chama decide o estado a partir do que já sabe.
    """
    itens = []
    for n, (rotulo, estado) in enumerate(passos, 1):
        marca = "✓" if estado == "feito" else str(n)
        itens.append(
            f'<div class="nr-passo {estado}"><span class="nr-num">{marca}</span>{rotulo}</div>'
        )
    return f'<div class="nr-stepper">{"".join(itens)}</div>'


def badge_gravidade(chave: str, rotulo: str) -> str:
    """HTML de um selo de gravidade; o texto continua sendo o rótulo do laudo."""
    classe = chave if chave in ("critica", "alta", "media", "baixa") else "baixa"
    return f'<span class="nr-badge {classe}">{rotulo}</span>'


def como_funciona() -> str:
    """Estado vazio: três cartões explicando o fluxo, mostrado antes do upload."""
    return (
        '<div class="nr-vazio">'
        "<div><b>1. Envie as fotos</b>Um lote de imagens da vistoria, de qualquer pavimento.</div>"
        "<div><b>2. O app audita</b>Leitura da imagem, dossiê normativo e supervisão técnica.</div>"
        "<div><b>3. Baixe o laudo</b>Cada citação é conferida contra o texto oficial do MTE.</div>"
        "</div>"
    )


_ROTULOS_STATUS = {"pendente": "Pendente", "auditada": "Auditada", "falhou": "Não auditada"}


def selo_status(estado: str) -> str:
    """HTML do selo de uma miniatura: pendente | auditada | falhou."""
    return f'<span class="nr-status {estado}">{_ROTULOS_STATUS.get(estado, estado)}</span>'
