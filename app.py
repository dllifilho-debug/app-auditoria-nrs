import streamlit as st
import base64
from groq import Groq
import PyPDF2
import os

st.set_page_config(page_title="App de Auditoria NR", layout="centered")
st.title("🚧 App de Auditoria de NRs")

# Organização visual em abas ou seções limpas
api_key = st.text_input("Chave API do Groq:", type="password")

col1, col2 = st.columns(2)
with col1:
    # Lê a pasta atual e cria uma lista com todos os PDFs que você colocar lá
    pdfs_na_pasta = [arquivo.replace(".pdf", "") for arquivo in os.listdir() if arquivo.endswith(".pdf")]
    opcoes_nr = ["🧠 Deixar a IA identificar a Norma"] + pdfs_na_pasta
    nr_type = st.selectbox("Norma de Referência (Gabarito Oficial):", opcoes_nr)

with col2:
    rigor_nivel = st.selectbox("Perfil da Análise:", [
        "Pragmático (Foco em viabilidade e custo)", 
        "Rigor Total (Foco em conformidade jurídica estrita)"
    ])

company_size = st.text_input("Porte da empresa e Equipe de Manutenção:")
observacao = st.text_area("Observação do Engenheiro (Opcional):", placeholder="Ex: Trabalhador no andaime sem cinto e sem guarda-corpo")

uploaded_file = st.file_uploader("Tire uma foto ou envie da galeria", type=["jpg", "png", "jpeg"])

def extrair_texto_nr(nome_arquivo):
    texto = ""
    try:
        with open(nome_arquivo, "rb") as arquivo:
            leitor = PyPDF2.PdfReader(arquivo)
            for i in range(min(20, len(leitor.pages))):
                texto += leitor.pages[i].extract_text() + "\n"
    except Exception as e:
        return ""
    return texto

if st.button("Gerar Relatório Técnico"):
    if not api_key or not uploaded_file:
        st.warning("Por favor, insira a chave da API e anexe uma imagem.")
    else:
        texto_norma = ""
        regra_prompt = "Identifique as Normas Regulamentadoras (NRs) aplicáveis ao risco visualizado na imagem."
        
        if nr_type != "🧠 Deixar a IA identificar a Norma":
            nome_pdf = f"{nr_type}.pdf"
            texto_norma = extrair_texto_nr(nome_pdf)
            regra_prompt = f"Utilize ESTRITAMENTE as regras da {nr_type} fornecidas no documento oficial abaixo."
            st.info(f"📚 Consultando o arquivo oficial atualizado: {nome_pdf}")
        else:
            st.info("🔍 A IA analisará a imagem e identificará as normas aplicáveis.")

        client = Groq(api_key=api_key)
        image_b64 = base64.b64encode(uploaded_file.read()).decode("utf-8")
        
        texto_observacao = f"Contexto anotado durante a vistoria: {observacao}" if observacao else "Nenhuma observação adicional fornecida."
        
        prompt = f"""Você é um engenheiro de segurança do trabalho sênior, com foco em soluções reais e viáveis. Analise esta imagem.
        Porte da empresa/equipe: {company_size}.
        {texto_observacao}
        Abordagem desejada para o relatório: {rigor_nivel}.
        
        DIRETRIZ DE ANÁLISE:
        {regra_prompt}
        
        TEXTO OFICIAL ATUALIZADO DA NORMA (GABARITO):
        {texto_norma}
        
        Entregue um relatório estruturado de não conformidades (incluindo gravidade, item violado) e um plano de ação prático que a equipe de manutenção consiga implementar de fato."""
        
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
                
                relatorio_gerado = response.choices[0].message.content
                st.success("Análise Finalizada com Sucesso!")
                
                # Exibe o relatório formatado
                st.markdown(relatorio_gerado)
                
                # Botão de copiar (armazena no estado para facilitar)
                st.download_button(
                    label="📥 Baixar Relatório em Arquivo de Texto (.txt)",
                    data=relatorio_gerado,
                    file_name="relatorio_auditoria_nr.txt",
                    mime="text/plain"
                )

            except Exception as e:
                st.error(f"Erro ao processar a imagem: {e}")