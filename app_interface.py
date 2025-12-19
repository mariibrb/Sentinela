
import streamlit as st
import os
import io
import pandas as pd
from datetime import datetime
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

# --- BARRA LATERAL ---
with st.sidebar:
    if os.path.exists(".streamlit/nascel sem fundo.png"):
        st.image(".streamlit/nascel sem fundo.png", use_container_width=True)
    
    st.markdown("---")
    
    with st.expander("📥 **Baixar Gabaritos**", expanded=False):
        df_modelo = pd.DataFrame(columns=['CHAVE', 'STATUS'])
        buffer = io.BytesIO()
        with pd.ExcelWriter(buffer, engine='xlsxwriter') as writer:
            df_modelo.to_excel(writer, index=False)
        st.download_button("📄 Modelo ICMS", buffer.getvalue(), "modelo_icms.xlsx", use_container_width=True)
        st.download_button("📄 Modelo PIS/COFINS", buffer.getvalue(), "modelo_pis_cofins.xlsx", use_container_width=True)

    st.markdown("### ⚙️ Configurações de Base")
    
    with st.expander("🔄 **Atualizar Base ICMS**"):
        up_icms = st.file_uploader("Arquivo ICMS", type=['xlsx'], key='base_i', label_visibility="collapsed")
        if up_icms:
            with open(".streamlit/Base_ICMS.xlsx", "wb") as f: f.write(up_icms.getbuffer())
            st.toast("Base ICMS atualizada!", icon="✅")

    with st.expander("🔄 **Atualizar Base PIS/COF**"):
        up_pis = st.file_uploader("Arquivo PIS", type=['xlsx'], key='base_p', label_visibility="collapsed")
        if up_pis:
            with open(".streamlit/Base_CST_Pis_Cofins.xlsx", "wb") as f: f.write(up_pis.getbuffer())
            st.toast("Base PIS/COF atualizada!", icon="✅")

    with st.expander("🔄 **Atualizar Base TIPI**"):
        up_tipi = st.file_uploader("Arquivo TIPI", type=['xlsx'], key='base_t', label_visibility="collapsed")
        if up_tipi:
            with open(".streamlit/Base_IPI_Tipi.xlsx", "wb") as f: f.write(up_tipi.getbuffer())
            st.toast("Base TIPI atualizada!", icon="✅")

# --- ÁREA CENTRAL ---
c1, c2, c3 = st.columns([3, 4, 3])
with c2:
    if os.path.exists(".streamlit/Sentinela.png"):
        st.image(".streamlit/Sentinela.png", use_container_width=True)

st.markdown("---")

col_ent, col_sai = st.columns(2, gap="large")

with col_ent:
    st.markdown("### 📥 1. Entradas")
    xml_ent = st.file_uploader("📂 XMLs de Entrada", type='xml', accept_multiple_files=True, key="ue")
    aut_ent = st.file_uploader("🔍 Autenticidade Entrada", type=['xlsx'], key="ae")

with col_sai:
    st.markdown("### 📤 2. Saídas")
    xml_sai = st.file_uploader("📂 XMLs de Saída", type='xml', accept_multiple_files=True, key="us")
    aut_sai = st.file_uploader("🔍 Autenticidade Saída", type=['xlsx'], key="as")

# --- EXECUÇÃO ---
st.markdown("<br>", unsafe_allow_html=True)
if st.button("🚀 EXECUTAR AUDITORIA", type="primary", use_container_width=True):
    if not xml_ent and not xml_sai:
        st.error("Por favor, carregue os arquivos XML.")
    else:
        with st.spinner("O Sentinela está processando e cruzando o Status..."):
            df_autent_data = None
            arq_aut = aut_sai if aut_sai else aut_ent
            if arq_aut:
                df_autent_data = pd.read_excel(arq_aut)

            # Extração
            df_e = extrair_dados_xml(xml_ent, "Entrada", df_autenticidade=df_autent_data)
            df_s = extrair_dados_xml(xml_sai, "Saída", df_autenticidade=df_autent_data)
            
            # Geração do Excel com as novas colunas de análise nas abas
            excel_binario = gerar_excel_final(df_e, df_s)
            
            st.success("Análise concluída!")
            st.download_button(
                label="💾 BAIXAR RELATÓRIO",
                data=excel_binario,
                file_name="Auditoria_Sentinela_Completa.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                use_container_width=True
            )
