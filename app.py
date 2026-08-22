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
    modo_analise = st.radio("Modo de Análise:", ["🧠 Identificação Automática", "📚 Usar Gabarito (Selecionar NRs)"])
    nr_selecionadas = []
    if modo_analise == "📚 Usar Gabarito (Selecionar NRs)":
        pdfs_na_pasta = [arquivo.replace(".pdf", "") for arquivo in os.listdir() if arquivo.endswith(".pdf")]
        nr_selecionadas = st.multiselect("Selecione as NRs aplicáveis (Recomendado: Máx. 3):", pdfs_na_pasta)

with col2:
    company_size = st.text_input("Porte da empresa e Equipe de Manutenção:")

observacao = st.text_area("Observação do Engenheiro (Opcional):", placeholder="Ex: Trabalhador no andaime sem cinto e sem guarda-corpo")

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

DICT_CITACOES_NRS = """REFERÊNCIA TÉCNICA OFICIAL - ITENS VIGENTES DAS NRs (MTE 2025-2026):

=== NR-35 (TRABALHO EM ALTURA) ===
- 35.1: Objetivo da norma
- 35.2.1: Campo de aplicação (trabalho acima de 2,00m do nível inferior)
- 35.4.2: Trabalhador capacitado (treinamento teórico e prático)
- 35.6.2: Seleção de sistema de proteção contra quedas
- 35.6.3: Prioridade do SPCQ (Sistema de Proteção Coletiva)
- 35.6.3.1: SPCQ deve ser projetado por profissional legalmente habilitado
- 35.6.9: Cinturão de segurança tipo paraquedista é obrigatório em SPIQ de retenção de queda
- Anexo II (Sistemas de Ancoragem):
  - 3.2.a: Ancoragem estrutural deve ser projetada e construída sob responsabilidade de PLH
  - 3.1: Sistemas de ancoragem podem atender retenção de quedas, restrição de movimento, posicionamento no trabalho, acesso por cordas

=== NR-18 (INDÚSTRIA DA CONSTRUÇÃO) - ANDAIMES ===
- 18.9.1.1: Em todo perímetro da construção é obrigatório sistema de proteção contra queda de materiais
- 18.9.4.2: Guarda-corpo deve ter:
  a) travessão superior a 1,20 m de altura com resistência mínima de 90 kgf/m
  b) travessão intermediário a 0,70 m de altura com resistência mínima de 66 kgf/m
  c) rodapé com altura mínima de 0,15 m, rente à superfície, com resistência mínima de 22 kgf/m
  d) vãos entre os componentes preenchidos com tela
- 18.12.5: Piso do andaime deve ser forrado de modo contínuo, antiderrapante, nivelado e travado
- 18.12.15.2: Andaimes multidirecionais devem ter guarda-corpo com:
  - travessão superior entre 1,0 m e 1,20 m
  - travessão intermediário 0,50 m abaixo do superior
  - rodapé mínimo de 0,15 m

=== NR-6 (EPI) ===
- 6.1: Objetivo da norma
- 6.4.1: EPI só pode ser comercializado ou utilizado com CA (Certificado de Aprovação) válido
- 6.5.1.c: Empregador deve fornecer gratuitamente EPI adequado ao risco, em perfeito estado
- 6.5.1.d: Orientar e treinar sobre uso adequado
- 6.5.1.e: Fiscalizar o uso
- 6.6: Empregado deve usar apenas para finalidade prevista, responsabilizar pela guarda e conservar
"""

if st.button("Gerar Relatório Técnico"):
    if not api_key or not uploaded_file:
        st.warning("Por favor, insira a chave da API e anexe uma imagem.")
    else:
        if modo_analise == "📚 Usar Gabarito (Selecionar NRs)" and len(nr_selecionadas) > 0:
            texto_norma = ""
            nomes_pdfs = []
            limite_paginas = 5 if len(nr_selecionadas) > 1 else 15
            for nr in nr_selecionadas:
                nome_pdf = f"{nr}.pdf"
                texto_norma += f"\n\n--- INÍCIO DO GABARITO DA {nr} ---\n"
                texto_norma += extrair_texto_nr(nome_pdf, max_paginas=limite_paginas)
                nomes_pdfs.append(nome_pdf)
            nomes_juntos = ", ".join(nomes_pdfs)
            regra_prompt = f"Utilize ESTRITAMENTE as regras das NRs fornecidas nos documentos oficiais abaixo ({nomes_juntos}). Você SÓ PODE citar dimensões numéricas se elas estiverem ESTRITAMENTE escritas no Gabarito Oficial fornecido."
            bloco_gabarito = f"\nTEXTO OFICIAL ATUALIZADO DAS NORMAS (GABARITO):\n{texto_norma}"
            st.info(f"📚 Consultando os arquivos oficiais otimizados: {nomes_juntos}")
        else:
            regra_prompt = "Identifique as Normas Regulamentadoras aplicáveis usando seu conhecimento técnico. Você DEVE usar o DICIONÁRIO DE CITAÇÕES CORRETAS abaixo como referência obrigatória para citar os itens das NRs. NUNCA invente números de itens que não existam na redação vigente."
            bloco_gabarito = ""
            if modo_analise == "📚 Usar Gabarito (Selecionar NRs)" and len(nr_selecionadas) == 0:
                st.warning("⚠️ Você escolheu usar o gabarito, mas não selecionou nenhuma NR. A IA fará a identificação automática.")
            st.info("🔍 A IA analisará a imagem e identificará as normas aplicáveis pelo seu conhecimento interno.")
            
        client = Groq(api_key=api_key)
        image_b64 = base64.b64encode(uploaded_file.read()).decode("utf-8")
        texto_observacao = f"Contexto anotado durante a vistoria: {observacao}" if observacao else "Nenhuma observação adicional fornecida."
        
        prompt = f"""Você é um engenheiro de segurança do trabalho sênior elaborando um relatório pericial. Analise esta imagem com extremo rigor técnico e escreva SEMPRE em Português Brasileiro.
        Porte da empresa/equipe: {company_size}.
        {texto_observacao}
        
        === REGRAS DE OURO DA AUDITORIA (RESTRIÇÕES ABSOLUTAS) ===
        1. LINGUAGEM PERICIAL: É proibido usar conclusões legais definitivas ou dramáticas. Use exclusivamente termos objetivos como "aparente não conformidade", "indícios de", "constatação visual", "na imagem analisada".
        2. ANCORAGEM (NR-35): É ESTRITAMENTE PROIBIDO recomendar a ancoragem do cinto de segurança em tubos do andaime sem exigir projeto específico assinado por Profissional Legalmente Habilitado (PLH). Cite o Anexo II, item 3.2.a da NR-35.
        3. IMPROVISAÇÕES PROIBIDAS: Nunca recomende o uso de arames, barbantes, fitas zebradas ou adaptações irregulares para fixação de tábuas, guarda-corpo ou EPIs.
        4. HIERARQUIA DE RISCO E EPI: Siga a hierarquia de controles da NR-35 (eliminação -> proteção coletiva -> EPI). Ao citar EPIs (NR-6), SEMPRE exija a verificação do Certificado de Aprovação (CA) válido (item 6.4.1).
        5. CITAÇÃO DOS ITENS (OBRIGATÓRIO): Você DEVE usar o DICIONÁRIO DE CITAÇÕES CORRETAS abaixo como referência. NUNCA invente números de itens. Se não tiver certeza, use linguagem genérica ("conforme NR-18 vigente", "segundo NR-35").
        6. NR-18 - GUARDA-CORPO: Para andaimes, cite o item 18.9.4.2 (travessão 1,20m, intermediário 0,70m, rodapé 0,15m) ou 18.12.15.2 para andaimes multidirecionais. NUNCA cite 18.4.1.3 (item inexistente na redação vigente).
        7. NR-35 - CAMPO DE APLICAÇÃO: Cite o item 35.2.1 para definição de trabalho em altura (>2,00m). NUNCA cite 35.1.1 para isso (é o Objetivo da norma).
        8. NR-35 - CAPACITAÇÃO: O item 35.4.2 trata de trabalhador capacitado. NUNCA cite para fornecimento de EPI.
        9. NR-35 - CINTURÃO: Cite o item 35.6.9 para obrigatoriedade do cinturão tipo paraquedista em SPIQ de retenção de queda.
        10. NR-6 - FORNECIMENTO: Cite o item 6.5.1.c para fornecimento gratuito de EPI. NUNCA cite 6.1 ou 6.3 para isso.
        
        === DICIONÁRIO DE CITAÇÕES CORRETAS DAS NRs (USE OBRIGATORIAMENTE) ===
        {DICT_CITACOES_NRS}
        
        === DIRETRIZ DE ENQUADRAMENTO ===
        {regra_prompt}
        {bloco_gabarito}
        
        === ESTRUTURA DO RELATÓRIO ===
        Entregue um relatório estruturado com:
        1. DESCRIÇÃO DA CENA (fatos observados na imagem)
        2. ANÁLISE DE NÃO CONFORMIDADES (tabela ou lista com: Fato Observado, Inferência Técnica, Requisito Normativo com item correto)
        3. PLANO DE AÇÃO (priorizado: 1. Interdição se houver risco iminente, 2. EPC, 3. Validação técnica/PLH, 4. EPI com CA, 5. Treinamento/Capacitação formal)
        O plano de ação deve exigir verificação de capacidade de carga e validação por pessoa competente/PLH quando aplicável.
        IMPORTANTE: Se a imagem não permitir confirmação de algum detalhe (altura exata, tipo de andaime, etc.), registre como "não é possível confirmar visualmente" em vez de assumir."""
        
        with st.spinner("Processando análise de risco com base nas normas oficiais..."):
            try:
                response = client.chat.completions.create(
                    model="llama-3.2-11b-vision-preview",
                    messages=[{"role": "user", "content": [{"type": "text", "text": prompt}, {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{image_b64}"}}]}],
                    max_tokens=4096,
                    temperature=0.2
                )
                relatorio_bruto = response.choices[0].message.content
                relatorio_limpo = re.sub(r'<think>.*?</think>', '', relatorio_bruto, flags=re.DOTALL).strip()
                st.success("Análise Finalizada com Sucesso!")
                st.markdown(relatorio_limpo)
                st.download_button(label="📥 Baixar Relatório em Arquivo de Texto (.txt)", data=relatorio_limpo, file_name="relatorio_auditoria_nr.txt", mime="text/plain")
            except Exception as e:
                st.error(f"Erro ao processar a imagem: {e}")
