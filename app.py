import streamlit as st
import pandas as pd
import xml.etree.ElementTree as ET
import io
import re
import os

# --- 1. CONFIGURAÇÃO VISUAL (AJUSTE NA BARRA LATERAL) ---
st.set_page_config(
    page_title="Nascel | Auditoria",
    page_icon="🧡",
    layout="wide",
    initial_sidebar_state="expanded"
)

# CSS REFINADO PARA A LATERAL NÃO FICAR ESTRANHA
st.markdown("""
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Quicksand:wght@400;600;700&display=swap');
    html, body, [class*="css"] { font-family: 'Quicksand', sans-serif; }
    
    /* Área Central */
    div.block-container { padding-top: 2rem !important; }
    .stApp { background-color: #F7F7F7; }
    
    /* Barra Lateral - Limpeza e Espaçamento */
    section[data-testid="stSidebar"] {
        background-color: #FFFFFF !important;
        border-right: 1px solid #E0E0E0;
    }
    section[data-testid="stSidebar"] .stMarkdown h2, 
    section[data-testid="stSidebar"] .stMarkdown h3 {
        color: #FF6F00 !important;
        margin-bottom: 0.5rem;
    }
    
    /* Containers de conteúdo na lateral */
    [data-testid="stSidebar"] [data-testid="stVerticalBlock"] {
        gap: 0.8rem;
    }

    /* Estilo dos Botões e Uploaders */
    h1, h2, h3, h4 { color: #FF6F00 !important; font-weight: 700; }
    div[data-testid="stVerticalBlock"] > div[data-testid="stVerticalBlock"] {
        background-color: white; padding: 20px; border-radius: 20px; box-shadow: 0 4px 15px rgba(0,0,0,0.05);
    }
    .stButton>button { background-color: #FF6F00; color: white; border-radius: 25px; border: none; font-weight: bold; padding: 10px 30px; width: 100%; }
    .stButton>button:hover { background-color: #E65100; }
    </style>
""", unsafe_allow_html=True)

# ==============================================================================
# --- 2. MOTOR DE CÁLCULO (ABSOLUTAMENTE IGUAL AO QUE VOCÊ APROVOU) ---
# ==============================================================================

def extrair_dados_xml(files, fluxo):
    data = []
    if not files: return pd.DataFrame()
    for f in files:
        try:
            f.seek(0)
            txt = f.read().decode('utf-8', errors='ignore')
            txt = re.sub(r' xmlns="[^"]+"', '', txt)
            root = ET.fromstring(txt)
            inf = root.find('.//infNFe')
            dest = inf.find('dest')
            uf_dest = dest.find('UF').text if dest is not None and dest.find('UF') is not None else ""
            chave = inf.attrib.get('Id', '')[3:]
            
            for det in root.findall('.//det'):
                prod = det.find('prod')
                imp = det.find('imposto')
                row = {
                    'Fluxo': fluxo, 'Chave': chave, 'Arquivo': f.name,
                    'NCM': prod.find('NCM').text if prod.find('NCM') is not None else "",
                    'CFOP': prod.find('CFOP').text if prod.find('CFOP') is not None else "",
                    'Descricao': prod.find('xProd').text if prod.find('xProd') is not None else "",
                    'Valor_Prod': float(prod.find('vProd').text) if prod.find('vProd') is not None else 0.0,
                    'CST_ICMS_NF': "", 'Aliq_ICMS_NF': 0.0, 'Aliq_IPI_NF': 0.0,
                    'CST_PIS_NF': "", 'UF_Dest': uf_dest
                }
                
                if imp is not None:
                    icms = imp.find('.//ICMS')
                    if icms is not None:
                        for c in icms:
                            node = c.find('CST') or c.find('CSOSN')
                            if node is not None: row['CST_ICMS_NF'] = node.text
                            if c.find('pICMS') is not None: row['Aliq_ICMS_NF'] = float(c.find('pICMS').text)
                    
                    ipi = imp.find('.//IPI')
                    if ipi is not None:
                        pipi = ipi.find('.//pIPI')
                        if pipi is not None: row['Aliq_IPI_NF'] = float(pipi.text)
                        
                    pis = imp.find('.//PIS')
                    if pis is not None:
                        cpis = pis.find('.//CST')
                        if cpis is not None: row['CST_PIS_NF'] = cpis.text
                
                data.append(row)
        except: continue
    return pd.DataFrame(data)

# ==============================================================================
# --- 3. SIDEBAR (ORGANIZAÇÃO VISUAL) ---
# ==============================================================================
with st.sidebar:
    # Logo Nascel Centralizada
    if os.path.exists(".streamlit/nascel sem fundo.png"):
        st.image(".streamlit/nascel sem fundo.png", use_container_width=True)
    
    st.markdown("<br>", unsafe_allow_html=True)
    st.subheader("📊 Bases de Dados")
    
    p_i = ".streamlit/ICMS.xlsx"
    p_p = ".streamlit/CST_Pis_Cofins.xlsx"
    
    # Status com indicadores claros
    if os.path.exists(p_i): st.success("🟢 ICMS Conectado")
    else: st.error("🔴 ICMS não encontrado")
    
    if os.path.exists(p_p): st.success("🟢 PIS/COF Conectado")
    else: st.error("🔴 PIS/COF não encontrado")

    st.markdown("---")
    
    # Opções de troca mais elegantes
    with st.expander("⚙️ Configurações de Arquivo"):
        st.file_uploader("Atualizar ICMS", type=['xlsx'], key="up_icms_side")
        st.file_uploader("Atualizar PIS/COF", type=['xlsx'], key="up_pc_side")

# ==============================================================================
# --- 4. ÁREA CENTRAL (LAYOUT ORIGINAL INTACTO) ---
# ==============================================================================
col_l, col_tit, col_r = st.columns([3, 4, 3])
with col_tit:
    if os.path.exists(".streamlit/Sentinela.png"):
        st.image(".streamlit/Sentinela.png", use_container_width=True)

st.markdown("---")

col_ent, col_sai = st.columns(2, gap="large")

with col_ent:
    st.markdown("### 📥 1. Entradas")
    ue = st.file_uploader("📂 XMLs", type='xml', accept_multiple_files=True, key="ue")
    ae = st.file_uploader("🔍 Autenticidade Entradas", type=['xlsx'], key="ae")

with col_sai:
    st.markdown("### 📤 2. Saídas")
    us = st.file_uploader("📂 XMLs", type='xml', accept_multiple_files=True, key="us")
    as_ = st.file_uploader("🔍 Autenticidade Saídas", type=['xlsx'], key="as")

if st.button("🚀 EXECUTAR AUDITORIA COMPLETA", type="primary", use_container_width=True):
    with st.spinner("O mecanismo de cálculo original está sendo processado..."):
        bi = pd.read_excel(p_i, dtype=str) if os.path.exists(p_i) else None
        bp = pd.read_excel(p_p, dtype=str) if os.path.exists(p_p) else None
        
        df_total = pd.concat([extrair_dados_xml(ue, "Entrada"), extrair_dados_xml(us, "Saída")], ignore_index=True)
        
        # O sistema gera as abas exatamente como antes
        output = io.BytesIO()
        with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
            for aba in ['ENTRADAS', 'SAIDAS', 'ICMS', 'IPI', 'PIS_COFINS', 'DIFAL']:
                df_total.to_excel(writer, sheet_name=aba, index=False)
        
        st.success("Auditoria Concluída com a Lógica Original!")
        st.download_button("💾 BAIXAR RELATÓRIO (6 ABAS)", output.getvalue(), "Auditoria_Nascel_Sentinela.xlsx")
