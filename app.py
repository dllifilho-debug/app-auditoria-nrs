import streamlit as st
import base64
from groq import Groq
import os
import re
import time
from PIL import Image
import io

st.set_page_config(page_title="App de Auditoria NR | Gauntlet Loop", layout="centered", page_icon="🚧")
st.title("🚧 App de Auditoria de NRs")
st.markdown("**Powered by Gauntlet Loop** - Pipeline de Agentes Autônomos de Engenharia")

api_key = st.text_input("Chave API do Groq:", type="password")

col1, col2 = st.columns(2)
with col1:
    # Como abolimos o PDF para não estourar tokens, o usuário escolhe a Bula Enxuta
    foco_auditoria = st.selectbox("Foco Principal da Auditoria (Gabarito Enxuto):", 
                                  ["Geral (NR-18, NR-35, NR-06)", "Trabalho em Altura (NR-35 Foco)", "Máquinas e Equipamentos (NR-12)"])

with col2:
    company_size = st.text_input("Porte da empresa e Equipe de Manutenção:")

observacao = st.text_area("Contexto do Engenheiro (Opcional):", placeholder="Ex: Vistoria na laje do 3º pavimento, concretagem em andamento.")

uploaded_files = st.file_uploader("Envie as fotos da vistoria (Lote)", type=["jpg", "png", "jpeg"], accept_multiple_files=True)

def otimizar_imagem_para_api(arquivo_imagem):
    img = Image.open(arquivo_imagem)
    if img.mode in ("RGBA", "P"):
        img = img.convert("RGB")
    # Imagem compactada para garantir o limite de tokens da Groq
    img.thumbnail((640, 640), Image.Resampling.LANCZOS)
    buffered = io.BytesIO()
    img.save(buffered, format="JPEG", quality=70)
    return base64.b64encode(buffered.getvalue()).decode("utf-8")

# GABARITO ENXUTO (A BULA): Substitui os PDFs. É leve, direto e impede alucinações.
BULA_NRS_GERAL = """
=== DICIONÁRIO ESTRITO DE NRs (MTE 2025-2026) ===
NR-35 (Altura): 35.2.1 (Campo de aplicação >2m), 35.4.2 (Capacitação), 35.6.3 (Prioridade EPC), 35.6.9 (Cinturão em SPIQ), Anexo II 3.2.a (Ancoragem exige projeto de PLH).
NR-18 (Construção): 18.9.1.1 (Proteção de periferia contra queda), 18.9.4.2 (Guarda-corpo: 1,20m sup, 0,70m int, 0,15m rodapé), 18.12.5 (Piso nivelado/antiderrapante).
NR-6 (EPI): 6.4.1 (CA válido obrigatoriamente), 6.5.1.c (Fornecimento gratuito pelo empregador).
Regra Geral de Canteiro: Áreas de vivência e circulação devem ser desimpedidas e limpas.
"""

# ==========================================
# GAUNTLET LOOP V2: ALTA RIGIDEZ TÉCNICA
# ==========================================

def agente_olho_executor(client, image_b64):
    """AGENTE 1: Visão Fria e Material"""
    prompt = """Você é o Agente Extrator Visual pericial. Sua ÚNICA função é descrever os fatos materiais na imagem.
    REGRAS RÍGIDAS (PENA DE DEMISSÃO):
    1. Se não houver trabalhadores humanos visíveis na foto, ESCREVA EXPLICITAMENTE: 'Nenhum trabalhador presente na cena'.
    2. NÃO presuma materiais se não tiver certeza (ex: diga 'placa sólida', NUNCA afirme ser 'laje de concreto' sem evidência visual clara).
    3. NÃO cite normas, não julgue riscos e não proponha soluções. Apenas descreva a geometria, objetos, desníveis e o ambiente."""
    
    response = client.chat.completions.create(
        model="qwen/qwen3.6-27b",
        messages=[{"role": "user", "content": [{"type": "text", "text": prompt}, {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{image_b64}"}}]}],
        max_tokens=400,
        temperature=0.0
    )
    return re.sub(r'<think>.*?</think>', '', response.choices[0].message.content, flags=re.DOTALL).strip()

def agente_analista_executor(client, fatos_visuais, bula_gabarito, company_size, observacao):
    """AGENTE 2: Enquadramento Normativo"""
    prompt = f"""Você é o Engenheiro Analista elaborando um Relatório de Não Conformidades.
    
    FATOS VISUAIS: {fatos_visuais}
    CONTEXTO ANOTADO: {observacao}
    PORTE DA EMPRESA: {company_size}
    
    DICIONÁRIO DE NORMAS PERMITIDO: 
    {bula_gabarito}
    
    REGRAS DE ENQUADRAMENTO:
    1. PROIBIDO INVENTAR: Você SÓ PODE usar os itens listados no Dicionário acima.
    2. COERÊNCIA MATERIAL: NÃO use regras de andaimes para justificar buracos no chão ou entulho. Se o Dicionário não tiver uma regra exata para o risco, classifique como: "Requer verificação do PGR local".
    3. FANTASMAS: Se os Fatos Visuais dizem que não há trabalhadores presentes, É ESTRITAMENTE PROIBIDO citar falta de EPI (NR-6) ou falta de treinamento (NR-35).
    
    Elabore o laudo bruto contendo: 1. Descrição dos Fatos, 2. Tabela de Enquadramento, 3. Plano de Ação."""
    
    response = client.chat.completions.create(
        model="openai/gpt-oss-120b", 
        messages=[{"role": "user", "content": prompt}],
        max_tokens=1000,
        temperature=0.1
    )
    return re.sub(r'<think>.*?</think>', '', response.choices[0].message.content, flags=re.DOTALL).strip()

def agente_supervisor_diretor(client, laudo_bruto, bula_gabarito):
    """AGENTE 3: Supervisor de Qualidade (Fator Uau)"""
    prompt = f"""Você é o Diretor Técnico de Engenharia de Segurança. Audite o laudo bruto gerado pelo seu Analista.
    
    LAUDO BRUTO:
    {laudo_bruto}
    
    DICIONÁRIO OFICIAL (GABARITO):
    {bula_gabarito}
    
    CHECKLIST DE REPROVAÇÃO E CORREÇÃO OBRIGATÓRIA:
    1. ALUCINAÇÃO DE SIGLA: Verifique rigorosamente se o Analista usou a sigla PLH. A sigla PLH significa EXCLUSIVAMENTE "Profissional Legalmente Habilitado". Se estiver escrito "Planejamento de...", apague e corrija imediatamente.
    2. CITAÇÕES FALSAS: Cruze os itens normativos do laudo com o Dicionário Oficial. Se o Analista citou um item que não está no dicionário (ex: 18.4.1.3), DELETE a não-conformidade inteira.
    3. EPI PARA NINGUÉM: Se o laudo cobra EPI (cinto, capacete, CA), mas os fatos indicam que NÃO HÁ trabalhadores na imagem, EXCLUA sumariamente essa cobrança e a citação da NR-06.
    4. DRAMATIZAÇÃO: Remova qualquer linguagem alarmista.
    
    Reescreva o laudo final corrigindo todas as infrações. O texto deve ser impecável, frio e digno de assinatura pericial."""
    
    response = client.chat.completions.create(
        model="openai/gpt-oss-120b",
        messages=[{"role": "user", "content": prompt}],
        max_tokens=1500,
        temperature=0.0
    )
    return re.sub(r'<think>.*?</think>', '', response.choices[0].message.content, flags=re.DOTALL).strip()


if st.button("Executar Gauntlet Loop de Auditoria em Lote"):
    if not api_key or len(uploaded_files) == 0:
        st.warning("Insira a chave da API e anexe ao menos uma imagem.")
    else:
        client = Groq(api_key=api_key)
        
        for idx, arquivo_foto in enumerate(uploaded_files):
            st.markdown(f"### 📸 Analisando Foto {idx + 1} de {len(uploaded_files)}")
            image_b64 = otimizar_imagem_para_api(arquivo_foto)
            
            with st.status(f"Iniciando Pipeline de Agentes (Foto {idx + 1})...", expanded=True) as status:
                try:
                    st.write("🕵️‍♂️ **Agente Olho (Visão)** periciando fatos materiais...")
                    fatos_visuais = agente_olho_executor(client, image_b64)
                    
                    st.write("📝 **Agente Analista** cruzando restrições normativas...")
                    laudo_bruto = agente_analista_executor(client, fatos_visuais, BULA_NRS_GERAL, company_size, observacao)
                    
                    st.write("⚖️ **Agente Diretor (Supervisor)** podando alucinações técnicas...")
                    laudo_final = agente_supervisor_diretor(client, laudo_bruto, BULA_NRS_GERAL)
                    
                    status.update(label=f"✅ Loop Gauntlet Concluído: Foto {idx + 1}", state="complete", expanded=False)
                    
                    st.markdown(laudo_final)
                    st.download_button(label=f"📥 Baixar Relatório da Foto {idx + 1} (.txt)", data=laudo_final, file_name=f"relatorio_foto_{idx+1}.txt", mime="text/plain", key=f"download_{idx}")
                    st.divider()
                    
                    # Bypass inteligente do limite de Tokens por Minuto da Groq (Escalabilidade)
                    if idx + 1 < len(uploaded_files):
                        st.info("⏱️ Pausa estratégica de 15 segundos para não estourar o limite de Tokens da API...")
                        time.sleep(15)
                        
                except Exception as e:
                    status.update(label=f"❌ Falha no Loop da Foto {idx + 1}", state="error")
                    st.error(f"Erro ao processar: {e}")
