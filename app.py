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
        
        prompt = f"""Você é um engenheiro de segurança do trabalho sênior elaborando um relatório pericial. Analise esta imagem com extremo rigor técnico.
        Porte da empresa/equipe: {company_size}.
        {texto_observacao}
        
        REGRAS DE OURO DA AUDITORIA (RESTRIÇÕES ABSOLUTAS):
        1. LINGUAGEM PERICIAL: É proibido usar conclusões legais definitivas ou dramáticas como "ilegal", "risco de morte" ou "vida em perigo". Use exclusivamente termos objetivos como "aparente não conformidade", "indícios de", e registre que a constatação é visual e possui limitações.
        2. ANCORAGEM (NR-35): É ESTRITAMENTE PROIBIDO recomendar a ancoragem do cinto de segurança em tubos ou componentes do próprio andaime sem a exigência de projeto específico assinado por Profissional Legalmente Habilitado (PLH).
        3. IMPROVISAÇÕES PROIBIDAS: Nunca recomende o uso de arames, barbantes, fitas zebradas ou adaptações para fixação de estrutura, rodapés ou pisos.
        4. HIERARQUIA DE RISCO E EPI: Siga a hierarquia de controles da NR-35 (Eliminação > Proteção Coletiva > Sistema de Proteção Individual contra Quedas). Ao citar EPIs (NR-6), nunca os trate como solução universal e SEMPRE exija a verificação do Certificado de Aprovação (CA) válido.
        5. DIMENSÕES E ATUALIZAÇÕES: Não utilize metragens padronizadas da sua memória (como 0,90m para guarda-corpo ou 25cm para tábuas). Você só pode citar dimensões numéricas se elas estiverem escritas ESTRITAMENTE no Gabarito Oficial fornecido abaixo.
        
        DIRETRIZ DE ENQUADRAMENTO:
        {regra_prompt}
        
        TEXTO OFICIAL ATUALIZADO DA NORMA (GABARITO):
        {texto_norma}
        
        Entregue um relatório estruturado separando fato observado, inferência e requisito normativo. O plano de ação deve exigir verificação de capacidade de carga, integridade do sistema e validação por pessoa competente/PLH quando aplicável."""
        
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
                
                # Botão de copiar/baixar
                st.download_button(
                    label="📥 Baixar Relatório em Arquivo de Texto (.txt)",
                    data=relatorio_gerado,
                    file_name="relatorio_auditoria_nr.txt",
                    mime="text/plain"
                )

            except Exception as e:
                st.error(f"Erro ao processar a imagem: {e}")
