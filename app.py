import streamlit as st
import base64
from groq import Groq
import PyPDF2
import os
import re
from PIL import Image
import io

st.set_page_config(page_title="App de Auditoria NR | Gauntlet Loop", layout="centered", page_icon="🚧")
st.title("🚧 App de Auditoria de NRs")
st.markdown("**Powered by Gauntlet Loop Methodology** - Pipeline de Agentes Autônomos")

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

# Agora suporta múltiplas fotos nativamente sem engessar!
uploaded_files = st.file_uploader("Envie as fotos da vistoria", type=["jpg", "png", "jpeg"], accept_multiple_files=True)

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

def otimizar_imagem_para_api(arquivo_imagem):
    img = Image.open(arquivo_imagem)
    if img.mode in ("RGBA", "P"):
        img = img.convert("RGB")
    # Imagem compactada para isolar o gargalo de tokens no Agente de Visão
    img.thumbnail((640, 640), Image.Resampling.LANCZOS)
    buffered = io.BytesIO()
    img.save(buffered, format="JPEG", quality=70)
    return base64.b64encode(buffered.getvalue()).decode("utf-8")

DICT_CITACOES_NRS = """
=== DICIONÁRIO ESTRITO DE NRs (MTE 2025-2026) ===
NR-35: 35.1 (Objetivo), 35.2.1 (Campo de aplicação >2m), 35.4.2 (Capacitação), 35.6.3 (Prioridade EPC), 35.6.9 (Cinturão em SPIQ), Anexo II 3.2.a (Ancoragem por PLH).
NR-18: 18.9.1.1 (Proteção perímetro), 18.9.4.2 (Guarda-corpo: 1,20m sup, 0,70m int, 0,15m rodapé), 18.12.5 (Piso do andaime), 18.12.15.2 (Multidirecionais).
NR-6: 6.4.1 (CA válido), 6.5.1.c (Fornecimento gratuito).
"""

# ==========================================
# GAUNTLET LOOP: OS 3 AGENTES AUTÔNOMOS
# ==========================================

def agente_olho_executor(client, image_b64):
    """AGENTE 1: Especialista em Extração Visual (Frio e Objetivo)"""
    prompt = """Você é o Agente Extrator Visual. Sua ÚNICA função é descrever o que você vê na imagem com precisão cirúrgica. 
    Não cite normas, não proponha soluções. Apenas liste os fatos materiais: equipamentos, estruturas, posições das pessoas, presença ou ausência de EPIs/EPCs perceptíveis."""
    
    response = client.chat.completions.create(
        model="qwen/qwen3.6-27b",
        messages=[{"role": "user", "content": [{"type": "text", "text": prompt}, {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{image_b64}"}}]}],
        max_tokens=600,
        temperature=0.1
    )
    return re.sub(r'<think>.*?</think>', '', response.choices[0].message.content, flags=re.DOTALL).strip()

def agente_analista_executor(client, fatos_visuais, bloco_gabarito, company_size, observacao):
    """AGENTE 2: O Engenheiro Analista que cruza os fatos com as normas"""
    prompt = f"""Você é o Engenheiro Analista. Baseado APENAS nos fatos visuais relatados abaixo, cruze-os com as normas vigentes e elabore um Relatório Técnico de Não Conformidades.
    
    FATOS VISUAIS OBSERVADOS: {fatos_visuais}
    CONTEXTO DO ENGENHEIRO LOCAL: {observacao}
    PORTE DA EMPRESA: {company_size}
    
    BASE NORMATIVA: {bloco_gabarito}
    
    Elabore um laudo com: 1. Fatos Constatados, 2. Enquadramento Normativo, 3. Plano de Ação Direto."""
    
    response = client.chat.completions.create(
        model="openai/gpt-oss-120b", # Usando o motor robusto de texto recomendado pela Groq
        messages=[{"role": "user", "content": prompt}],
        max_tokens=1500,
        temperature=0.2
    )
    return re.sub(r'<think>.*?</think>', '', response.choices[0].message.content, flags=re.DOTALL).strip()

def agente_supervisor_diretor(client, laudo_bruto):
    """AGENTE 3 (O GAUNTLET): O Diretor Técnico Rigoroso que exige o 'Fator Uau'"""
    prompt = f"""Você é o Diretor Técnico de Engenharia de Segurança (O Supervisor do Gauntlet Loop). Seu trabalho é auditar o laudo abaixo gerado por um engenheiro júnior.
    
    REGRAS DE ACEITAÇÃO (O Fator Uau):
    1. O laudo NÃO PODE conter a citação '18.4.1.3' (item inexistente).
    2. O laudo NÃO PODE usar dramatização (ex: "risco mortal iminente"). Deve usar linguagem fria pericial ("aparente não conformidade").
    3. Ancoragens de andaime DEVEM obrigatoriamente exigir projeto de PLH (Anexo II, 3.2.a da NR-35).
    4. Se houver recomendação de gambiarras (fita zebrada como guarda-corpo, arames), VOCÊ DEVE REPROVAR e reescrever o plano de ação exigindo estrutura normativa.
    
    LAUDO BRUTO:
    {laudo_bruto}
    
    TAREFA: Reescreva e refine o laudo bruto, aplicando correções implacáveis caso qualquer uma das 4 regras acima tenha sido violada. Entregue o laudo final formatado e perfeito para o cliente."""
    
    response = client.chat.completions.create(
        model="openai/gpt-oss-120b",
        messages=[{"role": "user", "content": prompt}],
        max_tokens=1500,
        temperature=0.1
    )
    return re.sub(r'<think>.*?</think>', '', response.choices[0].message.content, flags=re.DOTALL).strip()


if st.button("Executar Gauntlet Loop de Auditoria"):
    if not api_key or len(uploaded_files) == 0:
        st.warning("Insira a chave da API e anexe ao menos uma imagem.")
    else:
        # Preparação do Gabarito (Feita uma única vez fora do loop para não estourar tokens)
        bloco_gabarito = DICT_CITACOES_NRS
        if modo_analise == "📚 Usar Gabarito (Selecionar NRs)" and len(nr_selecionadas) > 0:
            bloco_gabarito = "GABARITO ESTRITO EXTRAÍDO PELO ENGENHEIRO:\n"
            for nr in nr_selecionadas:
                bloco_gabarito += extrair_texto_nr(f"{nr}.pdf", max_paginas=5)
        
        client = Groq(api_key=api_key)
        
        for idx, arquivo_foto in enumerate(uploaded_files):
            st.markdown(f"### 📸 Analisando Foto {idx + 1} de {len(uploaded_files)}")
            image_b64 = otimizar_imagem_para_api(arquivo_foto)
            
            # Interface de Status para acompanhar os Subagentes (Gauntlet Loop UI)
            with st.status(f"Iniciando Pipeline de Agentes para a Foto {idx + 1}...", expanded=True) as status:
                try:
                    st.write("🕵️‍♂️ **Agente Olho (Visão)** extraindo fatos materiais...")
                    fatos_visuais = agente_olho_executor(client, image_b64)
                    
                    st.write("📝 **Agente Analista** cruzando fatos com NRs...")
                    laudo_bruto = agente_analista_executor(client, fatos_visuais, bloco_gabarito, company_size, observacao)
                    
                    st.write("⚖️ **Agente Diretor (Supervisor)** aplicando critérios de aceitação...")
                    laudo_final = agente_supervisor_diretor(client, laudo_bruto)
                    
                    status.update(label="✅ Loop Gauntlet Concluído com Sucesso!", state="complete", expanded=False)
                    
                    st.markdown(laudo_final)
                    st.download_button(label=f"📥 Baixar Relatório da Foto {idx + 1} (.txt)", data=laudo_final, file_name=f"relatorio_foto_{idx+1}.txt", mime="text/plain", key=f"download_{idx}")
                    st.divider()
                    
                except Exception as e:
                    status.update(label=f"❌ Falha no Loop da Foto {idx + 1}", state="error")
                    st.error(f"Erro ao processar: {e}")
