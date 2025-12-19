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
    .stFileUploader { padding: 5px; border: 1px dashed #FF6F00; border-radius: 10px; }
    </style>
""", unsafe_allow_html=True)

# --- SIDEBAR (LOGOTIPO E APOIO) ---
with st.sidebar:
    if os.path.exists(".streamlit/nascel sem fundo.png"):
        st.image(".streamlit/nascel sem fundo.png", use_container_width=True)
    st.markdown("---")
    with st.expander("📥 **Baixar Modelos**"):
        df_m = pd.DataFrame(columns=['CHAVE', 'STATUS'])
        buf = io.BytesIO()
        with pd.ExcelWriter(buf, engine='xlsxwriter') as wr: df_m.to_excel(wr, index=False)
        st.download_button("📄 Modelo Autenticidade", buf.getvalue(), "modelo_autenticidade.xlsx", use_container_width=True)

# --- ÁREA CENTRAL ---
c1, c2, c3 = st.columns([3, 4, 3])
with c2:
    if os.path.exists(".streamlit/Sentinela.png"):
        st.image(".streamlit/Sentinela.png", use_container_width=True)
    else:
        st.title("🛡️ Sentinela Fiscal")

st.markdown("---")

# --- BLOCO 1: AUTENTICIDADE (CENTRALIZADO) ---
st.markdown("### 🔍 Passo 1: Base de Autenticidade")
st.info("Suba aqui o arquivo que contém as Chaves de Acesso e os Status das Notas.")
base_autenticidade = st.file_uploader("Upload da Planilha de Autenticidade (Excel ou CSV)", type=['xlsx', 'csv'], key="auth_central")

st.markdown("<br>", unsafe_allow_html=True)

# --- BLOCO 2: XMLS ---
st.markdown("### 📥 Passo 2: Upload de XMLs")
col_e, col_s = st.columns(2, gap="large")

with col_e:
    st.markdown("##### Entradas (Compras)")
    xml_ent = st.file_uploader("Solte os XMLs de Entrada", type='xml', accept_multiple_files=True, key="ue")

with col_s:
    st.markdown("##### Saídas (Vendas)")
    xml_sai = st.file_uploader("Solte os XMLs de Saída", type='xml', accept_multiple_files=True, key="us")

# --- EXECUÇÃO ---
st.markdown("<br>", unsafe_allow_html=True)
if st.button("🚀 EXECUTAR AUDITORIA COMPLETA", type="primary", use_container_width=True):
    if not xml_ent and not xml_sai:
        st.error("Por favor, carregue os arquivos XML.")
    else:
        with st.spinner("O Sentinela está cruzando os dados..."):
            # Lendo base de autenticidade
            df_autent_data
