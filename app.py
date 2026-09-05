"""App de Auditoria de NRs — interface Streamlit.

Analisa fotos de inspeção e emite laudo de não conformidades citando apenas
itens de Normas Regulamentadoras que existem, palavra por palavra, nos PDFs
oficiais do MTE e estão vigentes na data da inspeção.
"""

from __future__ import annotations

import base64
import hashlib
import io
import os
import subprocess
from datetime import date
from pathlib import Path

import streamlit as st
from PIL import Image, ImageOps

from auditoria import lote, modelos, relatorio
from auditoria.catalogo_nr import CATALOGO_NR, NRS_VIGENTES
from auditoria.consumo import ORCAMENTO_GRATUITO, Consumo
from auditoria.demo import ClienteDemonstracao
from auditoria.kb import carregar_base
from auditoria.modelos import ClienteGroq, ErroDeAuditoria
from auditoria.pipeline import Configuracao, executar
from auditoria.riscos import catalogo as catalogo_riscos

LIMITE_BASE64 = 3_600_000        # a Groq recusa imagem base64 acima de ~4 MB

st.set_page_config(
    page_title="Auditoria de NRs por imagem",
    layout="wide",
    page_icon="•",
    initial_sidebar_state="expanded",
)


# ---------------------------------------------------------------------------
# Recursos carregados uma vez
# ---------------------------------------------------------------------------

@st.cache_resource
def versao_do_app() -> str:
    """Identifica a versão do código que está de fato rodando.

    Sem isso não dá para distinguir "o conserto não funcionou" de "o conserto
    não chegou ao servidor" — e as duas coisas se parecem muito na tela de quem
    está usando. Usa o SHA do commit quando o `.git` veio junto; caso contrário,
    uma impressão digital dos próprios arquivos, que muda a cada alteração.
    """
    raiz = Path(__file__).resolve().parent
    try:
        git = subprocess.run(
            ["git", "rev-parse", "--short", "HEAD"],
            cwd=raiz, capture_output=True, text=True, timeout=5,
        )
        if git.returncode == 0 and git.stdout.strip():
            return git.stdout.strip()
    except Exception:
        pass

    marca = hashlib.sha256()
    fontes = [raiz / "app.py"] + sorted((raiz / "auditoria").rglob("*.py"))
    for arquivo in fontes:
        marca.update(arquivo.read_bytes())
    return "src-" + marca.hexdigest()[:8]


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


def _duracao(segundos: float) -> str:
    """Segundos em algo legível: "48s", "6 min", "1 h 18 min"."""
    if segundos < 90:
        return f"{segundos:.0f}s"
    minutos = round(segundos / 60)
    if minutos < 90:
        return f"{minutos} min"
    return f"{minutos // 60} h {minutos % 60:02d} min"


def consumo_do_dia() -> Consumo:
    """Acumulado do dia, guardado na sessão do navegador."""
    estado = st.session_state.get("consumo")
    if not isinstance(estado, Consumo):
        estado = Consumo()
        st.session_state.consumo = estado
    return estado


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
    st.markdown("### Configuração")

    modo_demo = st.toggle(
        "Modo demonstração",
        value=not bool(chave_configurada()),
        help="Roda o pipeline completo com respostas simuladas, sem consumir a API. "
             "Serve para conhecer o app e para os testes automatizados.",
    )

    chave = ""
    if not modo_demo:
        # A chave da instalação nunca é escrita no campo: o input de senha do
        # Streamlit tem botão para revelar o conteúdo, e este app roda numa URL
        # pública. Quem abrir o link escolhe usar a própria chave — que é o
        # padrão — ou, deliberadamente, a da instalação.
        da_instalacao = chave_configurada()
        if da_instalacao:
            origem = st.radio(
                "Chave da API Groq",
                ["Usar minha própria chave", "Usar a chave desta instalação"],
                key="origem_da_chave",
                help="Cada conta Groq tem cota própria. Usar a chave da instalação "
                     "consome a cota de quem a configurou.",
            )
        else:
            origem = "Usar minha própria chave"

        if origem == "Usar minha própria chave":
            chave = st.text_input(
                "Sua chave da API Groq" if da_instalacao else "Chave da API Groq",
                value="",
                type="password",
                placeholder="gsk_…",
                help="Crie a sua em console.groq.com/keys. É gratuita e tem cota "
                     "diária própria, independente da de qualquer outra pessoa.",
            )
        else:
            chave = da_instalacao
            st.caption(
                "Em uso a chave configurada nesta instalação — o consumo sai da "
                "cota de quem a configurou."
            )

    st.divider()
    st.markdown("### Modelos")
    OUTRO = "Outro (digitar o ID)"

    def _rotulo(catalogo: list[modelos.Modelo]):
        """Rótulo dentro de UMA das listas: o mesmo ID tem rótulo diferente em
        cada uma, e uma busca global devolveria sempre o de visão."""
        def formatar(identificador: str) -> str:
            conhecido = modelos.por_id(identificador, catalogo)
            return conhecido.rotulo if conhecido else identificador
        return formatar

    escolha_visao = st.selectbox(
        "Visão (leitura da foto)",
        [m.id for m in modelos.VISAO] + [OUTRO],
        format_func=_rotulo(modelos.VISAO),
        disabled=modo_demo,
    )
    modelo_visao = (
        st.text_input("ID do modelo de visão", value=modelos.PADRAO_VISAO,
                      disabled=modo_demo).strip()
        if escolha_visao == OUTRO else escolha_visao
    )

    escolha_texto = st.selectbox(
        "Texto (enquadramento e supervisão)",
        [m.id for m in modelos.TEXTO] + [OUTRO],
        format_func=_rotulo(modelos.TEXTO),
        disabled=modo_demo,
    )
    modelo_texto = (
        st.text_input("ID do modelo de texto", value=modelos.PADRAO_TEXTO,
                      disabled=modo_demo).strip()
        if escolha_texto == OUTRO else escolha_texto
    )

    for identificador, catalogo in ((modelo_visao, modelos.VISAO),
                                    (modelo_texto, modelos.TEXTO)):
        if (m := modelos.por_id(identificador, catalogo)) and m.nota:
            st.caption(f"**{m.rotulo}** — {m.nota}")
    if OUTRO in (escolha_visao, escolha_texto):
        # A Groq desliga modelos a cada um ou dois meses; quando isso acontecer,
        # a troca é aqui, sem esperar por uma nova versão do app.
        st.caption(
            f"Modelos desligados retornam erro 404. Confira os IDs vigentes e as "
            f"substituições recomendadas em [depreciações da Groq]({modelos.PAGINA_DEPRECIACOES})."
        )

    st.divider()
    st.markdown("### Rigor da análise")
    rigor = st.select_slider(
        "Ciclos de supervisão",
        options=["Rápido", "Padrão", "Máximo"],
        value="Padrão",
        help="Rápido: sem revisão técnica (2 chamadas por foto). "
             "Padrão: com revisão técnica (3). "
             "Máximo: revisão técnica com reenquadramento em caso de veto (até 5).",
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
    if not modo_demo:
        otpm = st.number_input(
            "Limite de saída por minuto da conta (OTPM)",
            min_value=200, max_value=1_000_000,
            value=st.session_state.get("otpm", modelos.OTPM_ORGANIZACAO),
            step=100,
            help="Teto de tokens de RESPOSTA por minuto da sua organização na "
                 "Groq. Não aparece na tabela pública do plano gratuito: veja em "
                 "console.groq.com/settings/limits, passando o mouse sobre o TPM "
                 "para ver o detalhamento de entrada e saída. Em 04/09/2026 ele "
                 "recusou 11 fotos de 12 de um lote, porque o app pedia respostas "
                 "maiores que a janela inteira do minuto.",
        )
        st.session_state.otpm = otpm
        st.caption(
            f"Cada chamada vai pedir no máximo "
            f"{int(otpm * modelos.FRACAO_UTIL_DO_OTPM):,}".replace(",", ".")
            + " tokens de resposta."
        )

        gasto = consumo_do_dia()
        with st.expander("Consumo do dia", expanded=bool(gasto.tokens)):
            orcamento = st.number_input(
                "Teto diário de tokens (padrão)",
                min_value=10_000, max_value=100_000_000,
                value=st.session_state.get("orcamento_diario", ORCAMENTO_GRATUITO),
                step=10_000,
                help="Na Groq o teto diário é de cada modelo, não da conta somada. "
                     "Os modelos do registro usam o teto próprio deles, lido no "
                     "console em 04/09: 200.000 para os quatro. Este campo vale "
                     "para modelo digitado à mão, e para ajustar se a sua conta "
                     "não for a gratuita.",
            )
            st.session_state.orcamento_diario = orcamento
            tetos = modelos.tetos_diarios()

            if gasto.imagens:
                cabem = gasto.imagens_que_ainda_cabem(orcamento, tetos)
                apertado = gasto.modelo_mais_apertado(orcamento, tetos)

                # Uma barra por modelo, cada uma contra o teto DAQUELE modelo: é
                # o balde proporcionalmente mais cheio que interrompe o lote, e
                # uma barra só, somando todos, escondia justamente isso.
                for modelo, gastos in sorted(
                    gasto.por_modelo.items(), key=lambda p: -p[1]
                ):
                    teto = gasto.teto_do_modelo(modelo, orcamento, tetos)
                    rotulo = f"{gastos:,} de {teto:,}".replace(",", ".")
                    st.progress(
                        min(gastos / teto, 1.0) if teto > 0 else 1.0,
                        text=f"{modelo} — {rotulo} tokens",
                    )
                if not gasto.por_modelo:
                    st.progress(
                        gasto.fracao_usada(orcamento, tetos),
                        text=f"{gasto.tokens:,} de {orcamento:,} tokens".replace(",", "."),
                    )

                a, b = st.columns(2)
                a.metric("Imagens hoje", gasto.imagens)
                b.metric("Média por imagem", f"{gasto.media_por_imagem:,}".replace(",", "."))
                if cabem:
                    limite = f" — quem aperta é `{apertado[0]}`" if apertado else ""
                    st.caption(
                        f"Ainda cabem cerca de **{cabem} imagem(ns)** hoje, nesse "
                        f"ritmo{limite}."
                    )
                else:
                    esgotado = f" do modelo `{apertado[0]}`" if apertado else ""
                    st.warning(
                        f"Teto diário{esgotado} atingido pela contagem desta sessão. "
                        "A cota volta na virada do dia.",
                    )
            else:
                st.caption("Nenhuma imagem auditada hoje nesta sessão.")

            st.caption(
                "A contagem cobre apenas esta sessão do navegador: recarregar a página "
                "zera o acumulado, embora a cota real da conta siga consumida."
            )
            if gasto.tokens and st.button("Zerar contagem", use_container_width=True):
                st.session_state.pop("consumo", None)
                st.rerun()

    with st.expander("Cobertura normativa"):
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
                f"Edição já publicada mas ainda **não vigente**: {futuras}. "
                "O app cita a redação em vigor na data da inspeção."
            )
        st.caption(f"Versão em execução: `{versao_do_app()}`")
        if base.pdfs_ignorados:
            st.warning(
                "PDF cujo nome não permite identificar a NR (ignorado): "
                + ", ".join(f"`{n}`" for n in base.pdfs_ignorados)
                + ". Renomeie para o padrão `nr-XX-....pdf`.",
            )


# ---------------------------------------------------------------------------
# Cabeçalho
# ---------------------------------------------------------------------------

st.title("Auditoria de NRs por imagem")
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

# Imagem que entrou no lote e não produziu laudo precisa sobreviver à execução:
# antes ela só aparecia como erro na tela, sumia no rerun seguinte e ficava de
# fora do sumário — o laudo então dizia "14 imagens analisadas" para um lote de
# 17, e as três que faltavam se liam como fotos sem achado.
if "falhas" not in st.session_state:
    st.session_state.falhas = []

# O que a Groq DISSE, guardado à parte do motivo em português que vai ao laudo.
# Um `st.error` some no rerun seguinte, e foi assim que a mensagem que nomeava o
# limite de verdade ("output tokens per minute (OTPM): Limit 1000") se perdeu
# durante um lote inteiro, custando horas de diagnóstico do limite errado.
if "erros_da_api" not in st.session_state:
    st.session_state.erros_da_api = []

# Foto retirada do seletor sai também dos resultados: manter o laudo de uma
# imagem que já não está no lote faria o sumário e o plano de ação contarem
# conteúdo que o inspetor removeu de propósito.
st.session_state.resultados, descartadas = lote.sincronizar(
    st.session_state.resultados, [a.name for a in arquivos or []]
)
st.session_state.falhas, _ = lote.sincronizar(
    st.session_state.falhas, [a.name for a in arquivos or []]
)
if descartadas:
    st.toast(
        f"{len(descartadas)} laudo(s) descartado(s) junto com a(s) imagem(ns).",
    )

ja_auditadas = {nome for nome, _, _ in st.session_state.resultados}
pendentes = lote.pendentes(arquivos or [], ja_auditadas)

if arquivos:
    if ja_auditadas and pendentes:
        st.info(
            f"**{len(ja_auditadas)} imagem(ns) já auditada(s) nesta sessão.** "
            f"A execução continua das {len(pendentes)} restantes, sem refazer nem "
            "gastar cota com o que já está pronto.",
        )
    elif arquivos and not pendentes:
        st.success("Todas as imagens deste lote já foram auditadas nesta sessão.")

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
    "Executar auditoria" + (f" ({len(pendentes)} pendente(s))" if pendentes and ja_auditadas else ""),
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
    if not modo_demo and not (modelo_visao and modelo_texto):
        st.error("Informe o ID dos dois modelos na barra lateral.")
        st.stop()

    cliente = ClienteDemonstracao() if modo_demo else ClienteGroq(
        api_key=chave.strip(), aviso=lambda m: st.toast(m),
        otpm=st.session_state.get("otpm", modelos.OTPM_ORGANIZACAO),
    )
    config = Configuracao(
        modelo_visao=modelo_visao,
        modelo_texto=modelo_texto,
        data_referencia=data_inspecao,
        **perfis[rigor],
    )

    if refazer:
        st.session_state.resultados = []
        st.session_state.falhas = []
        st.session_state.erros_da_api = []
        fila = list(arquivos)
    else:
        fila = pendentes

    auditadas_antes = len(st.session_state.resultados)
    barra = st.progress(0.0, text="Iniciando…")
    interrompido = None

    def registrar_falha(nome: str, erro: ErroDeAuditoria) -> None:
        """Guarda a imagem que não virou laudo, sem duplicar em nova tentativa.

        O motivo que vai para o sumário é o texto em português; a mensagem crua
        da API fica à parte, para a tela de diagnóstico — ela é o que nomeia o
        limite atingido, e não é conteúdo de documento de segurança do trabalho.
        """
        st.session_state.falhas = [
            f for f in st.session_state.falhas if f[0] != nome
        ] + [(nome, erro.mensagem)]
        if erro.detalhe:
            st.session_state.erros_da_api = [
                d for d in st.session_state.erros_da_api if d[0] != nome
            ] + [(nome, erro.detalhe)]

    def relatar_erro(erro: ErroDeAuditoria) -> None:
        """Mostra a tradução e, logo abaixo, o texto original da API."""
        st.error(f"**{erro.mensagem}**" + (f"\n\n{erro.sugestao}" if erro.sugestao else ""))
        if erro.detalhe:
            with st.expander("Mensagem original da Groq"):
                st.code(erro.detalhe, language="text")

    for indice, arquivo in enumerate(fila):
        rotulo = f"{arquivo.name} ({indice + 1}/{len(fila)})"
        barra.progress(indice / len(fila), text=f"Analisando {rotulo}…")

        with st.status(rotulo, expanded=True) as painel:
            try:
                imagem_b64, miniatura = preparar_imagem(arquivo.getvalue(), lado_imagem)
                laudo = executar(
                    cliente, base, imagem_b64, contexto, config,
                    progresso=lambda m: st.write(m),
                )
                st.session_state.resultados.append((arquivo.name, laudo, miniatura))
                st.session_state.falhas = [
                    f for f in st.session_state.falhas if f[0] != arquivo.name
                ]
                st.session_state.erros_da_api = [
                    d for d in st.session_state.erros_da_api if d[0] != arquivo.name
                ]
                achadas = len(laudo.nao_conformidades)
                if laudo.visao_falhou:
                    # Resposta crua à vista: sem ela, "o modelo não viu nada" e
                    # "o modelo respondeu num formato que não soubemos ler" são
                    # indistinguíveis, e levam a consertos opostos.
                    st.warning(
                        "O agente de visão não devolveu nenhum fato utilizável para esta "
                        "imagem. Nada foi enquadrado a partir dela.",
                    )
                    with st.expander("Ver o que o modelo de visão respondeu"):
                        st.code(laudo.visao.bruto or "(resposta vazia)", language="json")
                gasto = f" · {laudo.duracao_s:.0f}s" + (
                    f" ({laudo.espera_s:.0f}s de espera de cota)"
                    if laudo.espera_s >= 1 else ""
                )
                painel.update(
                    label=(f"{rotulo} — leitura da imagem falhou{gasto}" if laudo.visao_falhou
                           else f"{rotulo} — {achadas} não conformidade(s){gasto}"),
                    state="error" if laudo.visao_falhou else "complete",
                    expanded=laudo.visao_falhou,
                )
            except ErroDeAuditoria as erro:
                painel.update(label=f"{rotulo} — falhou", state="error")
                relatar_erro(erro)
                registrar_falha(arquivo.name, erro)
                if not erro.recuperavel:
                    interrompido = (arquivo.name, erro)
                    break
            except Exception as erro:                      # rede, imagem corrompida…
                traduzido = modelos.traduzir(erro)
                painel.update(label=f"{rotulo} — falhou", state="error")
                relatar_erro(traduzido)
                registrar_falha(arquivo.name, traduzido)

    barra.progress(1.0, text="Concluído.")

    if interrompido is not None:
        nome, _ = interrompido
        restantes = len(fila) - [a.name for a in fila].index(nome)
        st.warning(
            f"**Lote interrompido em `{nome}`.** As "
            f"{len(st.session_state.resultados)} imagem(ns) já auditada(s) continuam "
            f"abaixo e podem ser exportadas agora. Faltam {restantes}: quando a cota "
            "voltar, é só executar de novo — o app retoma de onde parou.",
        )
    if not modo_demo and getattr(cliente, "tokens_gastos", 0):
        # Média desta execução, não da sessão: num lote retomado, dividir os
        # tokens de agora pelo total acumulado dá um número sem sentido.
        nesta_execucao = len(st.session_state.resultados) - auditadas_antes
        media = cliente.tokens_gastos // max(nesta_execucao, 1)
        consumo_do_dia().registrar(
            cliente.tokens_gastos, nesta_execucao, cliente.chamadas,
            por_modelo=getattr(cliente, "tokens_por_modelo", None),
        )
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

if st.session_state.falhas and not resultados:
    # Lote inteiro falhou: sem este aviso a tela volta ao estado inicial no rerun
    # seguinte e não sobra vestígio de que alguma coisa foi tentada.
    st.divider()
    st.error(
        "**Nenhuma imagem do lote foi auditada.** Falharam: "
        + ", ".join(f"`{n}` ({m})" for n, m in st.session_state.falhas)
    )

if st.session_state.erros_da_api:
    # A tradução que o app escreve é um palpite sobre a causa; o texto abaixo é
    # o que a Groq respondeu. Foi ele que revelou que o limite atingido era o
    # OTPM, e não o TPM que a mensagem traduzida vinha anunciando havia meses.
    with st.expander(
        f"O que a Groq respondeu ({len(st.session_state.erros_da_api)} falha(s))"
    ):
        for nome, detalhe in st.session_state.erros_da_api:
            st.markdown(f"`{nome}`")
            st.code(detalhe, language="text")
        st.caption(
            "Texto original da API, para diagnóstico. Não entra no laudo."
        )

if resultados:
    st.divider()

    total = sum(len(l.nao_conformidades) for _, l, _ in resultados)
    criticas = sum(
        1 for _, l, _ in resultados for nc in l.nao_conformidades if nc.gravidade == "critica"
    )
    normas = {nc.item.nr for _, l, _ in resultados for nc in l.nao_conformidades}

    if st.session_state.falhas:
        # Antes este aviso não existia e as imagens que falharam sumiam no rerun:
        # o lote parecia completo com fotos que ninguém examinou.
        nomes = ", ".join(f"`{n}`" for n, _ in st.session_state.falhas)
        st.error(
            f"**{len(st.session_state.falhas)} imagem(ns) do lote não foi(ram) "
            f"auditada(s):** {nomes}. Elas constam no sumário como não auditadas. "
            "Executar de novo tenta só as que faltam."
        )

    m1, m2, m3, m4 = st.columns(4)
    m1.metric("Imagens analisadas", len(resultados),
              delta=(f"-{len(st.session_state.falhas)} não auditada(s)"
                     if st.session_state.falhas else None),
              delta_color="inverse" if st.session_state.falhas else "off")
    m2.metric("Não conformidades", total)
    m3.metric("Críticas", criticas, delta="ação imediata" if criticas else None,
              delta_color="inverse" if criticas else "off")
    m4.metric("Normas acionadas", len(normas))

    # Tempo de parede: um lote de 100 fotos esbarra na cota diária e no relógio,
    # e o segundo não aparece em lugar nenhum sem isto aqui. A média
    # sozinha não ajuda a planejar — o que ajuda é saber quanto dela é espera
    # pela janela de TPM, porque essa parte não melhora com modelo mais rápido.
    cronometrados = [l for _, l, _ in resultados if l.duracao_s > 0]
    if cronometrados:
        segundos = sum(l.duracao_s for l in cronometrados)
        espera = sum(l.espera_s for l in cronometrados)
        media = segundos / len(cronometrados)
        fatia = f" — **{espera / segundos:.0%}** disso é espera pela cota" if espera else ""
        st.caption(
            f"**Tempo:** {_duracao(segundos)} em {len(cronometrados)} imagem(ns), "
            f"média de **{media:.0f}s por foto**{fatia}. "
            f"Nesse ritmo, 100 fotos levam ~{_duracao(media * 100)}."
        )

    if st.button("Limpar todos os resultados", help="Recomeça o lote do zero."):
        st.session_state.resultados = []
        st.session_state.falhas = []
        st.rerun()

    texto_consolidado = relatorio.consolidado(
        [(nome, laudo) for nome, laudo, _ in resultados], base, data_inspecao,
        nao_auditadas=st.session_state.falhas,
    )

    aba_resumo, *abas = st.tabs(
        ["Sumário executivo"] + [nome[:24] for nome, _, _ in resultados]
    )

    with aba_resumo:
        st.markdown(texto_consolidado)
        d1, d2 = st.columns(2)
        d1.download_button(
            "Sumário em Markdown", texto_consolidado,
            file_name=f"sumario_inspecao_{data_inspecao:%Y%m%d}.md",
            mime="text/markdown", use_container_width=True,
        )
        d2.download_button(
            "Sumário em HTML (imprimível)",
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
                        rot = relatorio.SELOS.get(nc.gravidade, nc.gravidade)
                        st.markdown(f"`{nc.item.nr} {nc.item.item}` — **{rot}**")
                if not laudo.aprovado:
                    st.warning(
                        f"A revisão técnica vetou {len(laudo.vetos)} enquadramento(s). "
                        "As observações correspondentes seguem entre os pontos de atenção."
                    )
                if st.button("Descartar este laudo", key=f"descartar_{nome}",
                             use_container_width=True,
                             help="Remove o resultado desta imagem. A foto continua no "
                                  "lote e será auditada de novo na próxima execução."):
                    st.session_state.resultados = [
                        r for r in st.session_state.resultados if r[0] != nome
                    ]
                    st.rerun()

            with direita:
                indice = [n for n, (m, _, _) in enumerate(resultados, 1) if m == nome][0]
                texto = relatorio.markdown(
                    laudo, base, identificacao=nome, obra=obra,
                    responsavel=responsavel, numero=indice,
                )
                st.markdown(texto)
                b1, b2 = st.columns(2)
                b1.download_button(
                    "Markdown", texto,
                    file_name=f"laudo_{indice:02d}_{data_inspecao:%Y%m%d}.md",
                    mime="text/markdown", key=f"md_{indice}", use_container_width=True,
                )
                b2.download_button(
                    "HTML imprimível",
                    relatorio.para_html(texto, f"Laudo {indice} — {nome}"),
                    file_name=f"laudo_{indice:02d}_{data_inspecao:%Y%m%d}.html",
                    mime="text/html", key=f"html_{indice}", use_container_width=True,
                )

elif not executar_agora:
    st.divider()
    with st.expander("Como este app evita citar norma inexistente", expanded=False):
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

O laudo traz, ao final, a trilha completa: quantos ciclos rodaram, o que a revisão técnica
vetou e o que a aferição descartou.
            """
        )
