import streamlit as st
import base64
from groq import Groq
import PyPDF2
import os
import re

st.set_page_config(page_title="App de Auditoria NR", layout="centered")
st.title("🚧 App de Auditoria de NRs")

api_key = st.text_input("Chave API do Groq:", type="password")

col1, col2 = st.columns(2)
with col1:
    modo_analise = st.radio("Modo de Analise:", ["🧠 Identificacao Automatica", "📚 Usar Gabarito (Selecionar NRs)"])
    nr_selecionadas = []
    if modo_analise == "📚 Usar Gabarito (Selecionar NRs)":
        pdfs_na_pasta = [arquivo.replace(".pdf", "") for arquivo in os.listdir() if arquivo.endswith(".pdf")]
        nr_selecionadas = st.multiselect("Selecione as NRs aplicaveis (Recomendado: Max. 3):", pdfs_na_pasta)

with col2:
    company_size = st.text_input("Porte da empresa e Equipe de Manutencao:")

observacao = st.text_area("Observacao do Engenheiro (Opcional):", placeholder="Ex: Trabalhador no andaime sem cinto e sem guarda-corpo")

uploaded_file = st.file_uploader("Tire uma foto ou envie da galeria", type=["jpg", "png", "jpeg"])

def extrair_texto_nr(nome_arquivo, max_paginas=12):
    texto = ""
    try:
        with open(nome_arquivo, "rb") as arquivo:
            leitor = PyPDF2.PdfReader(arquivo)
            total_paginas = min(max_paginas, len(leitor.pages))
            for i in range(total_paginas):
                texto += leitor.pages[i].extract_text() + "\n"
    except Exception as e:
        return ""
    return texto

DICT_CITACOES_NRS = """REFERENCIA TECNICA OFICIAL - ITENS VIGENTES DAS NRs (MTE 2025-2026):

=== NR-35 (TRABALHO EM ALTURA) ===
- 35.1: Objetivo da norma
- 35.2.1: Campo de aplicacao (trabalho acima de 2,00m do nivel inferior)
- 35.4.2: Trabalhador capacitado (treinamento teorico e pratico)
- 35.6.2: Selecao de sistema de protecao contra quedas
- 35.6.3: Prioridade do SPCQ (Sistema de Protecao Coletiva)
- 35.6.3.1: SPCQ deve ser projetado por profissional legalmente habilitado
- 35.6.9: Cinturao de seguranca tipo paraquedista e obrigatorio em SPIQ de retencao de queda
- Anexo II (Sistemas de Ancoragem):
  - 3.2.a: Ancoragem estrutural deve ser projetada e construida sob responsabilidade de PLH
  - 3.1: Sistemas de ancoragem podem atender retencao de quedas, restricao de movimento, posicionamento no trabalho, acesso por cordas

=== NR-18 (INDUSTRIA DA CONSTRUCAO) - ANDAIMES ===
- 18.9.1.1: Em todo perimetro da construcao e obrigatorio sistema de protecao contra queda de materiais (Portaria MTE no 836/2026, vigente 29/06/2026)
- 18.9.4.2: Guarda-corpo deve ter:
  a) travessao superior a 1,20 m de altura com resistencia minima de 90 kgf/m
  b) travessao intermediario a 0,70 m de altura com resistencia minima de 66 kgf/m
  c) rodape com altura minima de 0,15 m, rente a superficie, com resistencia minima de 22 kgf/m
  d) vaos entre os componentes preenchidos com tela
- 18.12.5: Piso do andaime deve ser forrado de modo continuo, antiderrapante, nivelado e travado
- 18.12.15.2: Andaimes multidirecionais devem ter guarda-corpo com:
  - travessao superior entre 1,0 m e 1,20 m
  - travessao intermediario 0,50 m abaixo do superior
  - rodape minimo de 0,15 m

=== NR-6 (EPI) ===
- 6.1: Objetivo da norma
- 6.4.1: EPI so pode ser comercializado ou utilizado com CA (Certificado de Aprovacao) valido
- 6.5.1.c: Empregador deve fornecer gratuitamente EPI adequado ao risco, em perfeito estado
- 6.5.1.d: Orientar e treinar sobre uso adequado
- 6.5.1.e: Fiscalizar o uso
- 6.6: Empregado deve usar apenas para finalidade prevista, responsabilizar pela guarda e conservar

=== NR-1 (DISPOSICOES GERAIS) ===
- 1.5.4: Gerenciamento de Riscos Ocupacionais (GRO) e Programa de Gerenciamento de Riscos (PGR)
- 1.5.4.1: Identificacao de perigos
- 1.6: Glossario (inclui riscos psicossociais desde 26/05/2026 - Portaria MTE no 1.419/2024)

=== NR-9 (AVALIACAO DE EXPOSICOES) ===
- 9.1: Objetivo
- 9.2: Avaliacao e controle das exposicoes ocupacionais a agentes fisicos, quimicos e biologicos
- 9.5: Medidas de controle (hierarquia: eliminacao, substituicao, EPC, administrativas, EPI)

=== NR-15 (INSALUBRIDADE) ===
- 15.1: Atividades e operacoes insalubres
- 15.4.1.3: Laudos de insalubridade devem estar disponiveis aos trabalhadores, sindicatos e fiscalizacao (Portaria MTE no 2.021/2025, vigente 03/04/2026)
- Anexos vigentes: 1, 2, 3, 5, 6, 7, 8, 9, 10, 11, 12, 13, 13-A, 14 (Anexo 4 foi revogado)
"""

if st.button("Gerar Relatorio Tecnico"):
    if not api_key or not uploaded_file:
        st.warning("Por favor, insira a chave da API e anexe uma imagem.")
    else:
        if modo_analise == "📚 Usar Gabarito (Selecionar NRs)" and len(nr_selecionadas) > 0:
            texto_norma = ""
            nomes_pdfs = []
            limite_paginas = 5 if len(nr_selecionadas) > 1 else 15
            for nr in nr_selecionadas:
                nome_pdf = f"{nr}.pdf"
                texto_norma += f"\n\n--- INICIO DO GABARITO DA {nr} ---\n"
                texto_norma += extrair_texto_nr(nome_pdf, max_paginas=limite_paginas)
                nomes_pdfs.append(nome_pdf)
            nomes_juntos = ", ".join(nomes_pdfs)
            regra_prompt = f"Utilize ESTRITAMENTE as regras das NRs fornecidas nos documentos oficiais abaixo ({nomes_juntos}). Voce SO PODE citar dimensoes numericas se elas estiverem ESTRITAMENTE escritas no Gabarito Oficial fornecido."
            bloco_gabarito = f"\nTEXTO OFICIAL ATUALIZADO DAS NORMAS (GABARITO):\n{texto_norma}"
            st.info(f"📚 Consultando os arquivos oficiais otimizados: {nomes_juntos}")
        else:
            regra_prompt = "Identifique as Normas Regulamentadoras aplicaveis usando seu conhecimento tecnico. Voce DEVE usar o DICIONARIO DE CITACOES CORRETAS abaixo como referencia obrigatoria para citar os itens das NRs. NUNCA invente numeros de itens que nao existam na redacao vigente."
            bloco_gabarito = ""
            if modo_analise == "📚 Usar Gabarito (Selecionar NRs)" and len(nr_selecionadas) == 0:
                st.warning("⚠️ Voce escolheu usar o gabarito, mas nao selecionou nenhuma NR. A IA fara a identificacao automatica.")
            st.info("🔍 A IA analisara a imagem e identificara as normas aplicaveis pelo seu conhecimento interno.")
        client = Groq(api_key=api_key)
        image_b64 = base64.b64encode(uploaded_file.read()).decode("utf-8")
        texto_observacao = f"Contexto anotado durante a vistoria: {observacao}" if observacao else "Nenhuma observacao adicional fornecida."
        prompt = f"""Voce e um engenheiro de seguranca do trabalho senior elaborando um relatorio pericial. Analise esta imagem com extremo rigor tecnico e escreva SEMPRE em Portugues Brasileiro.
        Porte da empresa/equipe: {company_size}.
        {texto_observacao}
        === REGRAS DE OURO DA AUDITORIA (RESTRICOES ABSOLUTAS) ===
        1. LINGUAGEM PERICIAL: E proibido usar conclusoes legais definitivas ou dramaticas. Use exclusivamente termos objetivos como "aparente nao conformidade", "indicios de", "constatacao visual", "na imagem analisada".
        2. ANCORAGEM (NR-35): E ESTRITAMENTE PROIBIDO recomendar a ancoragem do cinto de seguranca em tubos do andaime sem exigir projeto especifico assinado por Profissional Legalmente Habilitado (PLH). Cite o Anexo II, item 3.2.a da NR-35.
        3. IMPROVISACOES PROIBIDAS: Nunca recomende o uso de arames, barbantes, fitas zebradas ou adaptacoes irregulares para fixacao de tabuas, guarda-corpo ou EPIs.
        4. HIERARQUIA DE RISCO E EPI: Siga a hierarquia de controles da NR-35 (eliminacao -> protecao coletiva -> EPI). Ao citar EPIs (NR-6), SEMPRE exija a verificacao do Certificado de Aprovacao (CA) valido (item 6.4.1).
        5. CITACAO DOS ITENS (OBRIGATORIO): Voce DEVE usar o DICIONARIO DE CITACOES CORRETAS abaixo como referencia. NUNCA invente numeros de itens. Se nao tiver certeza, use linguagem generica ("conforme NR-18 vigente", "segundo NR-35").
        6. NR-18 - GUARDA-CORPO: Para andaimes, cite o item 18.9.4.2 (travessao 1,20m, intermediario 0,70m, rodape 0,15m) ou 18.12.15.2 para andaimes multidirecionais. NUNCA cite 18.4.1.3 (item inexistente na redacao vigente).
        7. NR-35 - CAMPO DE APLICACAO: Cite o item 35.2.1 para definicao de trabalho em altura (>2,00m). NUNCA cite 35.1.1 para isso (e o Objetivo da norma).
        8. NR-35 - CAPACITACAO: O item 35.4.2 trata de trabalhador capacitado. NUNCA cite para fornecimento de EPI.
        9. NR-35 - CINTURAO: Cite o item 35.6.9 para obrigatoriedade do cinturao tipo paraquedista em SPIQ de retencao de queda.
        10. NR-6 - FORNECIMENTO: Cite o item 6.5.1.c para fornecimento gratuito de EPI. NUNCA cite 6.1 ou 6.3 para isso.
        === DICIONARIO DE CITACOES CORRETAS DAS NRs (USE OBRIGATORIAMENTE) ===
        {DICT_CITACOES_NRS}
        === DIRETRIZ DE ENQUADRAMENTO ===
        {regra_prompt}
        {bloco_gabarito}
        === ESTRUTURA DO RELATORIO ===
        Entregue um relatorio estruturado com:
        1. DESCRICAO DA CENA (fatos observados na imagem)
        2. ANALISE DE NAO CONFORMIDADES (tabela ou lista com: Fato Observado, Inferencia Tecnica, Requisito Normativo com item correto)
        3. PLANO DE ACAO (priorizado: 1. Interdicao se houver risco iminente, 2. EPC, 3. Validacao tecnica/PLH, 4. EPI com CA, 5. Treinamento/Capacitacao formal)
        O plano de acao deve exigir verificacao de capacidade de carga e validacao por pessoa competente/PLH quando aplicavel.
        IMPORTANTE: Se a imagem nao permitir confirmacao de algum detalhe (altura exata, tipo de andaime, etc.), registre como "nao e possivel confirmar visualmente" em vez de assumir."""
        with st.spinner("Processando analise de risco com base nas normas oficiais..."):
            try:
                response = client.chat.completions.create(
                    model="llama-3.2-90b-vision-preview",
                    messages=[{"role": "user", "content": [{"type": "text", "text": prompt}, {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{image_b64}"}}]}],
                    max_tokens=4096,
                    temperature=0.2
                )
                relatorio_bruto = response.choices[0].message.content
                relatorio_limpo = re.sub(r'<think>.*?</think>', '', relatorio_bruto, flags=re.DOTALL).strip()
                st.success("Analise Finalizada com Sucesso!")
                st.markdown(relatorio_limpo)
                st.download_button(label="📥 Baixar Relatorio em Arquivo de Texto (.txt)", data=relatorio_limpo, file_name="relatorio_auditoria_nr.txt", mime="text/plain")
            except Exception as e:
                st.error(f"Erro ao processar a imagem: {e}")