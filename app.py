"""App de Auditoria de NRs — interface Streamlit.

Analisa fotos de inspeção e emite laudo de não conformidades citando apenas
itens de Normas Regulamentadoras que existem, palavra por palavra, nos PDFs
oficiais do MTE e estão vigentes na data da inspeção.
"""

from __future__ import annotations

import base64
import io
import os
from datetime import date

import streamlit as st
from PIL import Image, ImageOps

from auditoria import modelos, relatorio
from auditoria.catalogo_nr import CATALOGO_NR, NRS_VIGENTES
from auditoria.demo import ClienteDemonstracao
from auditoria.kb import carregar_base
from auditoria.modelos import ClienteGroq, ErroDeAuditoria
from auditoria.pipeline import Configuracao, executar
from auditoria.riscos import catalogo as catalogo_riscos

LIMITE_BASE64 = 3_600_000        # a Groq recusa imagem base64 acima de ~4 MB

st.set_page_config(
    page_title="Auditoria de NRs — Gauntlet Loop",
    layout="wide",
    page_icon="🦺",
    initial_sidebar_state="expanded",
)


# ---------------------------------------------------------------------------
# Recursos carregados uma vez
# ---------------------------------------------------------------------------

@st.cache_resource(show_spinner="Carregando base normativa…")
def base_normativa(referencia: date):
    """Base em vigor na data informada.

    Não é a edição mais recente que vale, e sim a vigente: a NR-10 publicada em
    2026 só entra em vigor em 01/06/2027 e renumerou a norma inteira.
    """
    return carregar_base(referencia=referencia)


@st.cache_resource
def taxonomia():
    return catalogo_riscos()


@st.cache_data(show_spinner=False)
def preparar_imagem(bytes_imagem: bytes, lado: int) -> tuple[str, bytes]:
    """Corrige orientação, reduz e comprime — devolve base64 e miniatura."""
    img = Image.open(io.BytesIO(bytes_imagem))
    img = ImageOps.exif_transpose(img)          # foto de celular vem rotacionada
    if img.mode in ("RGBA", "P", "LA"):
        img = img.convert("RGB")
    img.thumbnail((lado, lado), Image.Resampling.LANCZOS)

    qualidade = 82
    while True:
        buffer = io.BytesIO()
        img.save(buffer, format="JPEG", quality=qualidade, optimize=True)
        dados = buffer.getvalue()
        if len(base64.b64encode(dados)) <= LIMITE_BASE64 or qualidade <= 40:
            break
        qualidade -= 12
    return base64.b64encode(dados).decode("ascii"), dados


def chave_configurada() -> str:
    try:
        if "GROQ_API_KEY" in st.secrets:
            return str(st.secrets["GROQ_API_KEY"])
    except Exception:
        pass
    return os.environ.get("GROQ_API_KEY", "")


# ---------------------------------------------------------------------------
# Barra lateral
# ---------------------------------------------------------------------------

base = base_normativa(date.today())
riscos = taxonomia()

with st.sidebar:
    st.markdown("### ⚙️ Configuração")

    modo_demo = st.toggle(
        "Modo demonstração",
        value=not bool(chave_configurada()),
        help="Roda o pipeline completo com respostas simuladas, sem consumir a API. "
             "Serve para conhecer o app e para os testes automatizados.",
    )

    chave = ""
    if not modo_demo:
        padrao = chave_configurada()
        chave = st.text_input(
            "Chave da API Groq",
            value=padrao,
            type="password",
            help="Obtenha em console.groq.com/keys. Em produção, prefira definir "
                 "GROQ_API_KEY nos Secrets do Streamlit.",
        )
        if padrao:
            st.caption("✅ Chave carregada dos Secrets/ambiente.")

    st.divider()
    st.markdown("### 🧠 Modelos")
    modelo_visao = st.selectbox(
        "Visão (leitura da foto)",
        [m.id for m in modelos.VISAO],
        format_func=lambda i: modelos.por_id(i).rotulo,
        disabled=modo_demo,
    )
    modelo_texto = st.selectbox(
        "Texto (enquadramento e supervisão)",
        [m.id for m in modelos.TEXTO],
        format_func=lambda i: modelos.por_id(i).rotulo,
        disabled=modo_demo,
    )
    if (m := modelos.por_id(modelo_texto)) and m.nota:
        st.caption(m.nota)

    st.divider()
    st.markdown("### 🔁 Rigor do Gauntlet Loop")
    rigor = st.select_slider(
        "Ciclos de supervisão",
        options=["Rápido", "Padrão", "Máximo"],
        value="Padrão",
        help="Rápido: sem supervisor (2 chamadas por foto). "
             "Padrão: com supervisor (3). "
             "Máximo: supervisor com re-análise em caso de veto (até 5).",
    )
    perfis = {
        "Rápido":  dict(usar_diretor=False, max_ciclos=1, teto_dossie=16),
        "Padrão":  dict(usar_diretor=True,  max_ciclos=1, teto_dossie=22),
        "Máximo":  dict(usar_diretor=True,  max_ciclos=3, teto_dossie=28),
    }

    lado_imagem = st.select_slider(
        "Resolução enviada ao modelo",
        options=[640, 768, 896, 1024],
        value=896,
        help="Mais resolução enxerga mais detalhe e consome mais cota.",
    )

    st.divider()
    with st.expander("📚 Cobertura normativa"):
        carregadas = set(base.por_nr)
        st.metric("Itens normativos indexados", f"{len(base.itens):,}".replace(",", "."))
        st.metric("Riscos catalogados", len(riscos))
        st.caption(
            f"**{len(carregadas)} de {len(NRS_VIGENTES)} NRs vigentes** com texto integral "
            f"carregado. Base consolidada em {base.gerado_em}."
        )
        faltantes = sorted(NRS_VIGENTES - carregadas)
        if faltantes:
            st.caption(
                "Sem texto carregado: " + ", ".join(faltantes) +
                ". O app sinaliza a aplicabilidade dessas normas, mas nunca cita item delas."
            )
            st.caption(
                "Para ampliar a cobertura, basta colocar o PDF oficial em `normas/` — "
                "a base se reconstrói sozinha quando o acervo muda."
            )
        if base.edicoes_futuras:
            futuras = ", ".join(
                f"{nr} (a partir de {date.fromisoformat(quando):%d/%m/%Y})"
                for nr, (_, quando) in sorted(base.edicoes_futuras.items())
            )
            st.caption(
                f"⏳ Edição já publicada mas ainda **não vigente**: {futuras}. "
                "O app cita a redação em vigor na data da inspeção."
            )
        if base.pdfs_ignorados:
            st.warning(
                "PDF cujo nome não permite identificar a NR (ignorado): "
                + ", ".join(f"`{n}`" for n in base.pdfs_ignorados)
                + ". Renomeie para o padrão `nr-XX-....pdf`.",
                icon="⚠️",
            )


# ---------------------------------------------------------------------------
# Cabeçalho
# ---------------------------------------------------------------------------

st.title("🦺 Auditoria de NRs por imagem")
st.markdown(
    "Enquadramento de não conformidades em **Normas Regulamentadoras** a partir de fotos "
    "de inspeção. Cada citação do laudo é conferida contra o texto oficial do MTE antes "
    "de ser impressa — o que a base não confirma, não sai no relatório."
)

if modo_demo:
    st.info(
        "**Modo demonstração ativo.** O pipeline roda inteiro — roteamento de riscos, "
        "dossiê normativo, aferição e supervisão — com respostas simuladas do modelo. "
        "Desligue na barra lateral e informe a chave da Groq para analisar fotos de verdade.",
        icon="🧪",
    )

col_a, col_b, col_c = st.columns([2, 2, 1])
with col_a:
    obra = st.text_input("Obra / unidade", placeholder="Ex.: Edifício Aurora — Torre B")
with col_b:
    responsavel = st.text_input("Responsável pela inspeção", placeholder="Ex.: Eng. M. Andrade")
with col_c:
    data_inspecao = st.date_input("Data da inspeção", value=date.today(), format="DD/MM/YYYY")

# A partir daqui vale a edição vigente na data da inspeção, e não a de hoje —
# o que importa numa inspeção retroativa ou já agendada para depois de uma
# mudança de norma.
base = base_normativa(data_inspecao)

contexto = st.text_area(
    "Contexto da inspeção (opcional, mas melhora muito o enquadramento)",
    placeholder="Ex.: vistoria no 3º pavimento durante concretagem; equipe própria de 12 pessoas.",
    height=80,
)

arquivos = st.file_uploader(
    "Fotos da vistoria",
    type=["jpg", "jpeg", "png", "webp", "bmp"],
    accept_multiple_files=True,
    help="Envie um lote. Cada foto gera um laudo e o conjunto gera um sumário executivo.",
)

if arquivos:
    st.caption(f"{len(arquivos)} imagem(ns) carregada(s).")
    # Sempre 6 colunas: com poucas fotos, a miniatura não estica pela tela toda.
    miniaturas = st.columns(6)
    for n, arquivo in enumerate(arquivos[:6]):
        with miniaturas[n]:
            st.image(arquivo, caption=arquivo.name[:18], use_container_width=True)
    if len(arquivos) > 6:
        st.caption(f"…e mais {len(arquivos) - 6} imagem(ns).")

# Custo medido por foto em cada perfil, para avisar antes de o lote começar.
CUSTO_POR_FOTO = {"Rápido": 5_000, "Padrão": 7_100, "Máximo": 7_300}

if "resultados" not in st.session_state:
    st.session_state.resultados = []

ja_auditadas = {nome for nome, _, _ in st.session_state.resultados}
pendentes = [a for a in arquivos or [] if a.name not in ja_auditadas]

if arquivos:
    if ja_auditadas and pendentes:
        st.info(
            f"**{len(ja_auditadas)} imagem(ns) já auditada(s) nesta sessão.** "
            f"A execução continua das {len(pendentes)} restantes, sem refazer nem "
            "gastar cota com o que já está pronto.",
            icon="↩️",
        )
    elif arquivos and not pendentes:
        st.success("Todas as imagens deste lote já foram auditadas nesta sessão.", icon="✅")

    if pendentes and not modo_demo:
        previsto = len(pendentes) * CUSTO_POR_FOTO[rigor]
        st.caption(
            f"Consumo previsto: **~{previsto:,} tokens** para {len(pendentes)} imagem(ns) "
            f"no rigor {rigor}.".replace(",", ".")
            + " Se a cota acabar no meio, o que já saiu fica salvo e basta executar de novo."
        )

refazer = False
if ja_auditadas:
    refazer = st.checkbox(
        "Refazer as imagens já auditadas",
        help="Por padrão o app pula o que já analisou, para não gastar cota duas vezes.",
    )

executar_agora = st.button(
    "▶️ Executar auditoria" + (f" ({len(pendentes)} pendente(s))" if pendentes and ja_auditadas else ""),
    type="primary",
    use_container_width=True,
    disabled=not arquivos or (not pendentes and not refazer),
)


# ---------------------------------------------------------------------------
# Execução
# ---------------------------------------------------------------------------

if executar_agora:
    if not modo_demo and not chave.strip():
        st.error("Informe a chave da API Groq na barra lateral, ou ative o modo demonstração.")
        st.stop()

    cliente = ClienteDemonstracao() if modo_demo else ClienteGroq(
        api_key=chave.strip(), aviso=lambda m: st.toast(m, icon="⏳")
    )
    config = Configuracao(
        modelo_visao=modelo_visao,
        modelo_texto=modelo_texto,
        data_referencia=data_inspecao,
        **perfis[rigor],
    )

    if refazer:
        st.session_state.resultados = []
        fila = list(arquivos)
    else:
        fila = pendentes

    barra = st.progress(0.0, text="Iniciando…")
    interrompido = None

    for indice, arquivo in enumerate(fila):
        rotulo = f"{arquivo.name} ({indice + 1}/{len(fila)})"
        barra.progress(indice / len(fila), text=f"Analisando {rotulo}…")

        with st.status(f"📸 {rotulo}", expanded=True) as painel:
            try:
                imagem_b64, miniatura = preparar_imagem(arquivo.getvalue(), lado_imagem)
                laudo = executar(
                    cliente, base, imagem_b64, contexto, config,
                    progresso=lambda m: st.write(m),
                )
                st.session_state.resultados.append((arquivo.name, laudo, miniatura))
                achadas = len(laudo.nao_conformidades)
                painel.update(
                    label=f"✅ {rotulo} — {achadas} não conformidade(s)",
                    state="complete",
                    expanded=False,
                )
            except ErroDeAuditoria as erro:
                painel.update(label=f"❌ {rotulo}", state="error")
                st.error(f"**{erro.mensagem}**" + (f"\n\n{erro.sugestao}" if erro.sugestao else ""))
                if not erro.recuperavel:
                    interrompido = (arquivo.name, erro)
                    break
            except Exception as erro:                      # rede, imagem corrompida…
                traduzido = modelos.traduzir(erro)
                painel.update(label=f"❌ {rotulo}", state="error")
                st.error(f"**{traduzido.mensagem}**" +
                         (f"\n\n{traduzido.sugestao}" if traduzido.sugestao else ""))

    barra.progress(1.0, text="Concluído.")

    if interrompido is not None:
        nome, _ = interrompido
        restantes = len(fila) - [a.name for a in fila].index(nome)
        st.warning(
            f"**Lote interrompido em `{nome}`.** As "
            f"{len(st.session_state.resultados)} imagem(ns) já auditada(s) continuam "
            f"abaixo e podem ser exportadas agora. Faltam {restantes}: quando a cota "
            "voltar, é só executar de novo — o app retoma de onde parou.",
            icon="⏸️",
        )
    if not modo_demo and getattr(cliente, "tokens_gastos", 0):
        auditadas = len(st.session_state.resultados)
        media = cliente.tokens_gastos // max(auditadas, 1)
        c1, c2, c3 = st.columns(3)
        c1.metric("Chamadas à API", cliente.chamadas)
        c2.metric("Tokens consumidos", f"{cliente.tokens_gastos:,}".replace(",", "."))
        c3.metric("Média por imagem", f"{media:,}".replace(",", "."))
        # A cota real vem dos cabeçalhos da resposta, não de estimativa nossa.
        if cliente.cota.tokens_restantes is not None:
            restantes = cliente.cota.tokens_restantes
            st.caption(
                f"Cota informada pela Groq na última resposta: {cliente.cota.descricao()}"
                + (f" — dá para cerca de {restantes // media} imagem(ns) nesta janela."
                   if media else "")
            )


# ---------------------------------------------------------------------------
# Resultados
# ---------------------------------------------------------------------------

resultados = st.session_state.resultados

if resultados:
    st.divider()

    total = sum(len(l.nao_conformidades) for _, l, _ in resultados)
    criticas = sum(
        1 for _, l, _ in resultados for nc in l.nao_conformidades if nc.gravidade == "critica"
    )
    normas = {nc.item.nr for _, l, _ in resultados for nc in l.nao_conformidades}

    m1, m2, m3, m4 = st.columns(4)
    m1.metric("Imagens analisadas", len(resultados))
    m2.metric("Não conformidades", total)
    m3.metric("Críticas", criticas, delta="ação imediata" if criticas else None,
              delta_color="inverse" if criticas else "off")
    m4.metric("Normas acionadas", len(normas))

    texto_consolidado = relatorio.consolidado(
        [(nome, laudo) for nome, laudo, _ in resultados], base, data_inspecao
    )

    aba_resumo, *abas = st.tabs(
        ["📊 Sumário executivo"] + [f"📸 {nome[:20]}" for nome, _, _ in resultados]
    )

    with aba_resumo:
        st.markdown(texto_consolidado)
        d1, d2 = st.columns(2)
        d1.download_button(
            "📥 Sumário em Markdown", texto_consolidado,
            file_name=f"sumario_inspecao_{data_inspecao:%Y%m%d}.md",
            mime="text/markdown", use_container_width=True,
        )
        d2.download_button(
            "🖨️ Sumário em HTML (imprimível)",
            relatorio.para_html(texto_consolidado, "Sumário executivo da inspeção"),
            file_name=f"sumario_inspecao_{data_inspecao:%Y%m%d}.html",
            mime="text/html", use_container_width=True,
        )

    for aba, (nome, laudo, miniatura) in zip(abas, resultados):
        with aba:
            esquerda, direita = st.columns([1, 2])
            with esquerda:
                st.image(miniatura, caption=nome, use_container_width=True)
                if laudo.nao_conformidades:
                    st.markdown("**Gravidade das constatações**")
                    for nc in laudo.nao_conformidades:
                        selo, rot = relatorio.SELOS.get(nc.gravidade, ("⚪", nc.gravidade))
                        st.markdown(f"{selo} `{nc.item.nr} {nc.item.item}` — {rot}")
                if not laudo.aprovado:
                    st.warning(
                        f"O supervisor vetou {len(laudo.vetos)} enquadramento(s), "
                        "removido(s) do laudo."
                    )

            with direita:
                indice = [n for n, (m, _, _) in enumerate(resultados, 1) if m == nome][0]
                texto = relatorio.markdown(
                    laudo, base, identificacao=nome, obra=obra,
                    responsavel=responsavel, numero=indice,
                )
                st.markdown(texto)
                b1, b2 = st.columns(2)
                b1.download_button(
                    "📥 Markdown", texto,
                    file_name=f"laudo_{indice:02d}_{data_inspecao:%Y%m%d}.md",
                    mime="text/markdown", key=f"md_{indice}", use_container_width=True,
                )
                b2.download_button(
                    "🖨️ HTML imprimível",
                    relatorio.para_html(texto, f"Laudo {indice} — {nome}"),
                    file_name=f"laudo_{indice:02d}_{data_inspecao:%Y%m%d}.html",
                    mime="text/html", key=f"html_{indice}", use_container_width=True,
                )

elif not executar_agora:
    st.divider()
    with st.expander("ℹ️ Como este app evita citar norma inexistente", expanded=False):
        st.markdown(
            """
O erro clássico de um auditor automático é citar um item que não existe, ou citar um
item real para a situação errada. Aqui o desenho do pipeline torna os dois improváveis:

1. **Agente Olho** descreve a foto e nada mais. Não conhece norma, não julga, não propõe.
   Se não há ninguém na imagem, ele registra isso — e o sistema passa a proibir qualquer
   cobrança de EPI ou de treinamento.
2. **Dossiê normativo** é montado por código, não por modelo: os fatos são roteados por
   uma taxonomia de riscos curada e por busca textual sobre os itens extraídos dos PDFs
   oficiais. O analista só enxerga os itens que de fato podem se aplicar.
3. **Agente Analista** enquadra os fatos referenciando rótulos do dossiê (D1, D7…).
   Ele nunca escreve um número de NR — quem escreve a citação é o renderizador, a partir
   do item real. Alucinar citação deixa de ser improvável e passa a ser impossível.
4. **Aferição determinística** descarta o que não passa: rótulo inexistente, item fora de
   vigência na data da inspeção, item repetido, cobrança de EPI sem gente na foto.
5. **Diretor Técnico** relê cada enquadramento ao lado do texto oficial do item e veta o
   que a norma não sustenta. No rigor Máximo, o veto volta ao analista para novo ciclo.

O laudo traz, ao final, a trilha completa: quantos ciclos rodaram, o que o supervisor
vetou e o que a aferição descartou.
            """
        )
