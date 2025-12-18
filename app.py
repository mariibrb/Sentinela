import streamlit as st
import pandas as pd
import xml.etree.ElementTree as ET
import io
import re
import os

# --- 1. CONFIGURAÇÃO VISUAL (ORIGINAL) ---
st.set_page_config(
    page_title="Nascel | Auditoria",
    page_icon="🧡",
    layout="wide",
    initial_sidebar_state="expanded"
)

# CSS PERSONALIZADO (MANTIDO)
st.markdown("""
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Quicksand:wght@400;600;700&display=swap');
    html, body, [class*="css"] { font-family: 'Quicksand', sans-serif; }
    div.block-container { padding-top: 2rem !important; padding-bottom: 1rem !important; }
    .stApp { background-color: #F7F7F7; }
    h1, h2, h3, h4 { color: #FF6F00 !important; font-weight: 700; }
    div[data-testid="stVerticalBlock"] > div[data-testid="stVerticalBlock"] {
        background-color: white; padding: 20px; border-radius: 20px; box-shadow: 0 4px 15px rgba(0,0,0,0.05);
    }
    .stFileUploader { padding: 10px; border: 2px dashed #FFCC80; border-radius: 15px; text-align: center; }
    .stButton>button { background-color: #FF6F00; color: white; border-radius: 25px; border: none; font-weight: bold; padding: 10px 30px; width: 100%; }
    .stButton>button:hover { background-color: #E65100; }
    </style>
""", unsafe_allow_html=True)

# ==============================================================================
# --- 2. SIDEBAR: LOGO NASCEL, STATUS, GESTÃO DE BASES E GABARITOS ---
# ==============================================================================
with st.sidebar:
    # LOGO DA NASCEL
    caminho_logo = ".streamlit/nascel sem fundo.png"
    if os.path.exists(caminho_logo): 
        st.image(caminho_logo, use_column_width=True)
    elif os.path.exists("nascel sem fundo.png"): 
        st.image("nascel sem fundo.png", use_column_width=True)
    else: 
        st.markdown("<h1 style='color:#FF6F00; text-align:center;'>Nascel</h1>", unsafe_allow_html=True)
    
    st.markdown("---")

    def get_file(name):
        paths = [f".streamlit/{name}", name, f"bases/{name}"]
        for p in paths:
            if os.path.exists(p): return p
        return None

    # STATUS DAS BASES
    st.subheader("📊 Status das Bases")
    f_icms = get_file("base_icms.xlsx")
    f_tipi = get_file("tipi.xlsx")
    f_pc = get_file("CST_Pis_Cofins.xlsx")

    if f_icms: st.success("🟢 Base ICMS OK")
    else: st.error("🔴 Base ICMS Ausente")

    if f_tipi: st.success("🟢 Base TIPI OK")
    else: st.error("🔴 Base TIPI Ausente")

    if f_pc: st.success("🟢 Base PIS/COF OK")
    else: st.error("🔴 Base PIS/COF Ausente")

    st.markdown("---")

    # 1. GERENCIAR BASES ATUAIS (DOWNLOAD/UPLOAD)
    with st.expander("💾 1. GERENCIAR BASES ATUAIS"):
        st.caption("Regras de ICMS")
        if f_icms:
            with open(f_icms, "rb") as f: st.download_button("📥 Baixar ICMS", f, "base_icms.xlsx", key="side_dl_icms")
        up_icms = st.file_uploader("Nova Base ICMS", type=['xlsx'], key='side_up_icms')
        if up_icms:
            with open("base_icms.xlsx", "wb") as f: f.write(up_icms.getbuffer())
            st.success("ICMS Atualizado!")

        st.markdown("---")
        st.caption("Tabela TIPI")
        if f_tipi:
            with open(f_tipi, "rb") as f: st.download_button("📥 Baixar TIPI", f, "tipi.xlsx", key="side_dl_tipi")
        up_tipi = st.file_uploader("Nova TIPI", type=['xlsx'], key='side_up_tipi')
        if up_tipi:
            with open("tipi.xlsx", "wb") as f: f.write(up_tipi.getbuffer())
            st.success("TIPI Atualizada!")

        st.markdown("---")
        st.caption("Regras PIS/COFINS")
        if f_pc:
            with open(f_pc, "rb") as f: st.download_button("📥 Baixar PIS/COF", f, "CST_Pis_Cofins.xlsx", key="side_dl_pc")
        up_pc = st.file_uploader("Nova PIS/COF", type=['xlsx'], key='side_up_pc')
        if up_pc:
            with open("CST_Pis_Cofins.xlsx", "wb") as f: f.write(up_pc.getbuffer())
            st.success("PIS/COF Atualizado!")

    # 2. MODELOS DE GABARITO (MOVIMENTADO PARA A SIDEBAR)
    with st.expander("📂 2. MODELOS DE GABARITO"):
        st.caption("Modelos para novos cadastros")
        
        # Gabarito ICMS (A-I)
        df_m_icms = pd.DataFrame(columns=['NCM','DESC_INT','CST_INT','ALIQ_INT','RED_INT','DESC_EXT','CST_EXT','ALIQ_EXT','OBS'])
        b_icms = io.BytesIO()
        with pd.ExcelWriter(b_icms, engine='xlsxwriter') as w: df_m_icms.to_excel(w, index=False)
        st.download_button("📥 Gabarito ICMS", b_icms.getvalue(), "modelo_icms.xlsx")
        
        st.markdown("---")
        
        # Gabarito PIS/COFINS
        df_m_pc = pd.DataFrame({'NCM': ['00000000'], 'CST_ENT': ['50'], 'CST_SAI': ['01']})
        b_pc = io.BytesIO()
        with pd.ExcelWriter(b_pc, engine='xlsxwriter') as w: df_m_pc.to_excel(w, index=False)
        st.download_button("📥 Gabarito PIS/COF", b_pc.getvalue(), "modelo_pc.xlsx")

# ==============================================================================
# --- 3. ÁREA CENTRAL: LOGO SENTINELA E OPERAÇÃO ---
# ==============================================================================

caminho_titulo = ".streamlit/Sentinela.png"
if os.path.exists(caminho_titulo):
    col_l, col_tit, col_r = st.columns([3, 4, 3])
    with col_tit: st.image(caminho_titulo, use_column_width=True)
elif os.path.exists("Sentinela.png"):
    col_l, col_tit, col_r = st.columns([3, 4, 3])
    with col_tit: st.image("Sentinela.png", use_column_width=True)
else:
    st.markdown("<h1 style='text-align: center; color: #FF6F00;'>SENTINELA</h1>", unsafe_allow_html=True)

st.markdown("---")

col_ent, col_sai = st.columns(2, gap="large")

with col_ent:
    st.markdown("### 📥 1. Entradas")
    st.markdown("---")
    up_ent_xml = st.file_uploader("📂 XMLs", type='xml', accept_multiple_files=True, key="ent_xml")
    up_ent_aut = st.file_uploader("🔍 Autenticidade", type=['xlsx', 'csv'], key="ent_aut")

with col_sai:
    st.markdown("### 📤 2. Saídas")
    st.markdown("---")
    up_sai_xml = st.file_uploader("📂 XMLs", type='xml', accept_multiple_files=True, key="sai_xml")
    up_sai_aut = st.file_uploader("🔍 Autenticidade", type=['xlsx', 'csv'], key="sai_aut")
