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
    initial_sidebar_state="expanded" # Alterado para iniciar aberta para ver os controles
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
# --- 2. SIDEBAR: STATUS E GESTÃO DE BASES (MOVIBILIZADO PARA CÁ) ---
# ==============================================================================
with st.sidebar:
    st.markdown("<h1 style='color:#FF6F00; text-align:center;'>Nascel</h1>", unsafe_allow_html=True)
    st.markdown("---")

    # Funções de suporte para as bases
    def get_file(name):
        paths = [f".streamlit/{name}", name, f"bases/{name}"]
        for p in paths:
            if os.path.exists(p): return p
        return None

    # INDICADORES DE STATUS
    st.subheader("📊 Status das Bases")
    f_icms = get_file("base_icms.xlsx")
    f_tipi = get_file("tipi.xlsx")
    f_pc = get_file("CST_Pis_Cofins.xlsx")

    if f_icms: st.success("🟢 Base ICMS OK")
    else: st.error("🔴 Base ICMS Ausente")

    if f_tipi: st.success("🟢 Base TIPI OK")
    else: st.error("🔴 Base TIPI Ausente")

    st.markdown("---")

    # EXPANDER PARA MANUTENÇÃO (BAIXAR/SUBIR)
    with st.expander("💾 GERENCIAR BASES ATUAIS"):
        if f_icms:
            with open(f_icms, "rb") as f: st.download_button("📥 Baixar ICMS Atual", f, "base_icms.xlsx")
        
        up_icms = st.file_uploader("Atualizar ICMS", type=['xlsx'], key='up_sidebar_icms')
        if up_icms:
            with open("base_icms.xlsx", "wb") as f: f.write(up_icms.getbuffer())
            st.success("ICMS Atualizado!")

        st.markdown("---")
        if f_tipi:
            with open(f_tipi, "rb") as f: st.download_button("📥 Baixar TIPI Atual", f, "tipi.xlsx")
        
        up_tipi = st.file_uploader("Atualizar TIPI", type=['xlsx'], key='up_sidebar_tipi')
        if up_tipi:
            with open("tipi.xlsx", "wb") as f: f.write(up_tipi.getbuffer())
            st.success("TIPI Atualizada!")

# --- 3. TÍTULO E LOGO CENTRAL (MANTIDO) ---
st.markdown("<h1 style='text-align: center; color: #FF6F00;'>SENTINELA</h1>", unsafe_allow_html=True)

# --- 4. GABARITOS (APENAS ICMS E PIS/COF - CONFORME PEDIDO) ---
with st.expander("📂 Modelos de Gabarito (Apenas para novos cadastros)"):
    c1, c2 = st.columns(2)
    with c1:
        # Modelo ICMS com 9 colunas (A até I)
        df_m = pd.DataFrame(columns=['NCM','DESC_INT','CST_INT','ALIQ_INT','RED_INT','DESC_EXT','CST_EXT','ALIQ_EXT','OBS'])
        b = io.BytesIO(); 
        with pd.ExcelWriter(b, engine='xlsxwriter') as w: df_m.to_excel(w, index=False)
        st.download_button("Modelo Base ICMS (A-I)", b.getvalue(), "modelo_icms_A_I.xlsx")
    with c2:
        df_m = pd.DataFrame({'NCM': ['00000000'], 'CST_ENT': ['50'], 'CST_SAI': ['01']})
        b = io.BytesIO(); 
        with pd.ExcelWriter(b, engine='xlsxwriter') as w: df_m.to_excel(w, index=False)
        st.download_button("Modelo PIS/COF", b.getvalue(), "modelo_pc.xlsx")

# --- 5. UPLOADS XML (MANTIDO) ---
st.markdown("---")
col_ent, col_sai = st.columns(2, gap="large")
with col_ent:
    st.markdown("### 📥 1. Entradas")
    up_ent_xml = st.file_uploader("📂 XMLs", type='xml', accept_multiple_files=True, key="ent_xml")
    up_ent_aut = st.file_uploader("🔍 Sefaz", type=['xlsx', 'csv'], key="ent_aut")
with col_sai:
    st.markdown("### 📤 2. Saídas")
    up_sai_xml = st.file_uploader("📂 XMLs", type='xml', accept_multiple_files=True, key="sai_xml")
    up_sai_aut = st.file_uploader("🔍 Sefaz", type=['xlsx', 'csv'], key="sai_aut")

# --- 6. LÓGICA DE AUDITORIA COM REGRA CFOP (PASSO FINAL) ---
@st.cache_data(ttl=5)
def carregar_bases():
    # Lógica de leitura de colunas A-I para ICMS
    def ler_icms(nome):
        path = get_file(nome)
        if path:
            df = pd.read_excel(path, usecols="A:I", dtype=str)
            df.columns = ['NCM', 'D_Int', 'CST_Int', 'Aliq_Int', 'Red_Int', 'D_Ext', 'CST_Ext', 'Aliq_Ext', 'Obs']
            df['NCM'] = df['NCM'].str.replace(r'\D', '', regex=True).str.zfill(8)
            return df
        return pd.DataFrame()

    icms = ler_icms("base_icms.xlsx")
    # ... (restante das leituras tipi e pc mantidas do seu original)
    return icms

# O restante do seu código original (extração XML, cruzamento e download final) 
# continua exatamente abaixo daqui.
