import streamlit as st
import os
import io
import pandas as pd

# IMPORTANTE: Aqui conectamos com o arquivo de cálculos que faremos a seguir
# from motor_fiscal import extrair_dados_xml, processar_auditoria_completa

# --- 1. CONFIGURAÇÃO VISUAL (LAYOUT PERFEITO E BLINDADO) ---
st.set_page_config(
    page_title="Nascel | Auditoria",
    page_icon="🧡",
    layout="wide",
    initial_sidebar_state="expanded"
)

# CSS ORIGINAL APROVADO (NÃO ALTERAR)
st.markdown("""
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Quicksand:wght@400;600;700&display=swap');
    html, body, [class*="css"] { font-family: 'Quicksand', sans-serif; }
    div.block-container { padding-top: 2rem !important; }
    .stApp { background-color: #F7F7F7; }
    h1, h2, h3, h4 { color: #FF6F00 !important; font-weight: 700; }
    div[data-testid="stVerticalBlock"] > div[data-testid="stVerticalBlock"] {
        background-color: white; padding: 20px; border-radius: 20px; box-shadow: 0 4px 15px rgba(0,0,0,0.05);
    }
    .stButton>button { 
        background-color: #FF6F00; color: white; border-radius: 25px; 
        border: none; font-weight: bold; padding: 10px 30px; width: 100%; 
    }
    .stButton>button:hover { background-color: #E65100; }
    </style>
""", unsafe_allow_html=True)

# ==============================================================================
# --- 2. BARRA LATERAL (APENAS DOWNLOAD DE MODELOS E UPLOAD DE BASES) ---
# ==============================================================================
with st.sidebar:
    # Logo Nascel
    if os.path.exists(".streamlit/nascel sem fundo.png"):
        st.image(".streamlit/nascel sem fundo.png", use_container_width=True)
    
    st.markdown("---")
    st.subheader("📥 Baixar Modelos")
    
    # Gerador simples de gabaritos para download
    df_m = pd.DataFrame(columns=['NCM','REFERENCIA','DADOS'])
    buf = io.BytesIO()
    with pd.ExcelWriter(buf, engine='xlsxwriter') as w: df_m.to_excel(w, index=False)
    
    st.download_button("📂 Modelo ICMS", buf.getvalue(), "modelo_icms.xlsx", use_container_width=True)
    st.download_button("📂 Modelo PIS/COFINS", buf.getvalue(), "modelo_pis_cofins.xlsx", use_container_width=True)

    st.markdown("---")
    st.subheader("📤 Atualizar Bases")
    
    # Uploads diretos para as pastas do sistema
    up_icms = st.file_uploader("Atualizar Base ICMS", type=['xlsx'], key='up_i')
    if up_icms:
        with open(".streamlit/ICMS.xlsx", "wb") as f: f.write(up_icms.getbuffer())
        st.success("Base ICMS Atualizada!")

    up_pis = st.file_uploader("Atualizar Base PIS/COF", type=['xlsx'], key='up_p')
    if up_pis:
        with open(".streamlit/CST_Pis_Cofins.xlsx", "wb") as f: f.write(up_pis.getbuffer())
        st.success("Base PIS/COF Atualizada!")

    up_tipi = st.file_uploader("Atualizar Base TIPI", type=['xlsx'], key='up_t')
    if up_tipi:
        with open(".streamlit/tipi.xlsx", "wb") as f: f.write(up_tipi.getbuffer())
        st.success("Base TIPI Atualizada!")

# ==============================================================================
# --- 3. ÁREA CENTRAL (LOGO SENTINELA E INPUTS DE ARQUIVOS) ---
# ==============================================================================

# Logo Sentinela Centralizado
c1, c2, c3 = st.columns([3, 4, 3])
with c2:
    if os.path.exists(".streamlit/Sentinela.png"):
        st.image(".streamlit/Sentinela.png", use_container_width=True)

st.markdown("---")

# Layout de Duas Colunas para XMLs e Autenticidade
col_ent, col_sai = st.columns(2, gap="large")

with col_ent:
    st.markdown("### 📥 1. Entradas")
    xml_ent = st.file_uploader("📂 Selecionar XMLs", type='xml', accept_multiple_files=True, key="main_ue")
    aut_ent = st.file_uploader("🔍 Planilha Autenticidade", type=['xlsx'], key="main_ae")

with col_sai:
    st.markdown("### 📤 2. Saídas")
    xml_sai = st.file_uploader("📂 Selecionar XMLs", type='xml', accept_multiple_files=True, key="main_us")
    as_ = st.file_uploader("🔍 Planilha Autenticidade", type=['xlsx'], key="main_as")

# ==============================================================================
# --- 4. BOTÃO DE EXECUÇÃO ---
# ==============================================================================
st.markdown("<br>", unsafe_allow_html=True)

if st.button("🚀 EXECUTAR AUDITORIA COMPLETA", type="primary", use_container_width=True):
    # Aqui o código chamará as funções do motor_fiscal.py
    # Por enquanto deixamos o feedback visual
    with st.spinner("O Sentinela está cruzando os dados tributários..."):
        # Exemplo de chamada (será habilitado após criar o motor_fiscal.py):
        # df_final = processar_auditoria_completa(xml_ent, xml_sai, ...)
        st.success("Auditoria realizada com sucesso!")
        # st.download_button("💾 BAIXAR RELATÓRIO", ...)
