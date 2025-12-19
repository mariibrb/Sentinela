import streamlit as st
import os
import io
import pandas as pd
from motor_fiscal import extrair_dados_xml, gerar_excel_final

# --- CONFIGURAÇÃO VISUAL ---
st.set_page_config(page_title="Nascel | Auditoria", page_icon="🧡", layout="wide")

st.markdown("""
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Quicksand:wght@400;600;700&display=swap');
    html, body, [class*="css"] { font-family: 'Quicksand', sans-serif; }
    .stApp { background-color: #F7F7F7; }
    h1, h2, h3, h4 { color: #FF6F00 !important; font-weight: 700; }
    div[data-testid="stVerticalBlock"] > div[data-testid="stVerticalBlock"] {
        background-color: white; padding: 20px; border-radius: 20px; box-shadow: 0 4px 15px rgba(0,0,0,0.05);
    }
    .stButton>button { background-color: #FF6F00; color: white; border-radius: 25px; font-weight: bold; width: 100%; border: none; padding: 12px; }
    .stButton>button:hover { background-color: #E65100; transform: scale(1.02); }
    </style>
""", unsafe_allow_html=True)

# --- SIDEBAR ---
with st.sidebar:
    if os.path.exists(".streamlit/nascel sem fundo.png"):
        st.image(".streamlit/nascel sem fundo.png", use_container_width=True)
    st.markdown("---")
    with st.expander("📥 **Baixar Gabaritos**"):
        df_m = pd.DataFrame(columns=['NCM', 'REFERENCIA', 'DADOS'])
        buf = io.BytesIO()
        with pd.ExcelWriter(buf, engine='xlsxwriter') as wr: df_m.to_excel(wr, index=False)
        st.download_button("📄 Modelo ICMS", buf.getvalue(), "modelo_icms.xlsx", use_container_width=True)
        st.download_button("📄 Modelo PIS/COFINS", buf.getvalue(), "modelo_pis_cofins.xlsx", use_container_width=True)
    st.markdown("### ⚙️ Configurações")
    with st.expander("🔄 **Atualizar Bases**"):
        st.file_uploader("Base ICMS", type=['xlsx'], key='ui')
        st.file_uploader("Base PIS", type=['xlsx'], key='up')

# --- CENTRAL ---
c1, c2, c3 = st.columns([3, 4, 3])
with c2:
    if os.path.exists(".streamlit/Sentinela.png"):
        st.image(".streamlit/Sentinela.png", use_container_width=True)

st.markdown("---")
col_e, col_s = st.columns(2, gap="large")
with col_e:
    st.markdown("### 📥 1. Entradas")
    xml_ent = st.file_uploader("XMLs Entrada", type='xml', accept_multiple_files=True, key="ue")
with col_s:
    st.markdown("### 📤 2. Saídas")
    xml_sai = st.file_uploader("XMLs Saída", type='xml', accept_multiple_files=True, key="us")

# --- EXECUÇÃO ---
if st.button("🚀 EXECUTAR AUDITORIA COMPLETA", type="primary", use_container_width=True):
    if not xml_ent and not xml_sai:
        st.error("Selecione os arquivos.")
    else:
        with st.spinner("Analisando..."):
            df_e = extrair_dados_xml(xml_ent, "Entrada")
            df_s = extrair_dados_xml(xml_sai, "Saída")
            excel = gerar_excel_final(df_e, df_s)
            st.success("Concluído!")
            st.download_button("💾 BAIXAR RELATÓRIO", excel, "Auditoria_Sentinela.xlsx", use_container_width=True)
