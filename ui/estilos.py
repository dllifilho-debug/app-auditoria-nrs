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
