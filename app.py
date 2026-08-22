import streamlit as st
import base64
from groq import Groq
import PyPDF2
import os
import re  # Ferramenta para apagar o "pensamento" em inglês da IA

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

def extrair_texto_nr(nome_arquivo, max_paginas=8):
    texto = ""
    try:
        with open(nome_arquivo, "rb") as arquivo:
            leitor = PyPDF2.PdfReader(arquivo)
            # Otimizado para ler apenas as primeiras páginas mais relevantes e evitar estouro de tokens
            total_paginas = min(max_paginas, len(leitor.pages))
            for i in range(total_paginas):
                texto += leitor.pages[i].extract_text() + "\n"
    except Exception as e:
        return ""
    return texto

if st.button("Gerar Relatório Técnico"):
    if not api_key or not uploaded_file:
        st.warning("Por favor, insira a chave da API e anexe uma imagem.")
    else:
        # Lógica para Múltiplas NRs com limite inteligente de páginas
        if modo_analise == "📚 Usar Gabarito (Selecionar NRs)" and len(nr_selecionadas) > 0:
            texto_norma = ""
            nomes_pdfs = []
            
            # Se selecionar mais de uma, reduzimos o número de páginas por PDF para caber no limite da Groq
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
            regra_prompt = "Identifique as Normas Regulamentadoras aplicáveis usando seu conhecimento técnico. Como você está sem o texto oficial em anexo, cite expressamente os itens normativos, mas NÃO INVENTE dimensões numéricas exatas (como metragens específicas), focando apenas na exigência do dispositivo de segurança."
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
        
        REGRAS DE OURO DA AUDITORIA (RESTRIÇÕES ABSOLUTAS):
        1. LINGUAGEM PERICIAL: É proibido usar conclusões legais definitivas ou dramáticas. Use exclusivamente termos objetivos como "aparente não conformidade", "indícios de", e registre que a constatação é visual.
        2. ANCORAGEM (NR-35): É ESTRITAMENTE PROIBIDO recomendar a ancoragem do cinto de segurança em tubos do andaime sem exigir projeto específico assinado por Profissional Legalmente Habilitado (PLH).
        3. IMPROVISAÇÕES PROIBIDAS: Nunca recomende o uso de arames, barbantes, fitas zebradas ou adaptações irregulares.
        4. HIERARQUIA DE RISCO E EPI: Siga a hierarquia de controles da NR-35 (EPC primeiro). Ao citar EPIs (NR-6), SEMPRE exija a verificação do Certificado de Aprovação (CA) válido.
        5. CITAÇÃO DOS ITENS (OBRIGATÓRIO): Você DEVE apontar expressamente o número do item da Norma Regulamentadora (Ex: NR-18.4.1.3, NR-35.4.2) correspondente a cada não conformidade que identificar.
        
        DIRETRIZ DE ENQUADRAMENTO:
        {regra_prompt}
        {bloco_gabarito}
        
        Entregue um relatório estruturado separando fato observado, inferência e requisito normativo. O plano de ação deve exigir verificação de capacidade de carga e validação por pessoa competente/PLH quando aplicável."""
        
        with st.spinner("Processando análise de risco com base nas normas oficiais..."):
            try:
                response = client.chat.completions.create(
                    model="qwen/qwen3.6-27b",
                    messages=[
                        {
                            "role": "user",
                            "content": [
                                {"type": "text", "text": prompt},
                                {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{image_b64}"}}
                            ]
                        }
                    ],
                    max_tokens=4096,
                    temperature=0.2
                )
                
                # Recebe a resposta bruta e apaga o bloco de pensamento em inglês
                relatorio_bruto = response.choices[0].message.content
                relatorio_limpo = re.sub(r'<think>.*?</think>', '', relatorio_bruto, flags=re.DOTALL).strip()
                
                st.success("Análise Finalizada com Sucesso!")
                
                # Exibe o relatório formatado sem o inglês
                st.markdown(relatorio_limpo)
                
                # Botão de copiar/baixar
                st.download_button(
                    label="📥 Baixar Relatório em Arquivo de Texto (.txt)",
                    data=relatorio_limpo,
                    file_name="relatorio_auditoria_nr.txt",
                    mime="text/plain"
                )

            except Exception as e:
                st.error(f"Erro ao processar a imagem: {e}")
