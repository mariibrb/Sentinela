import streamlit as st
import os
import io
import pandas as pd
# Importa o cérebro (motor) para dentro da interface
from motor_fiscal import extrair_dados_xml, gerar_excel_final

# --- CONFIGURAÇÃO VISUAL ---
st.set_page_config(page_title="Nascel | Auditoria", page_icon="🧡", layout="wide")

# CSS para manter o layout laranja e organizado
st.markdown("""
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Quicksand:wght@400;600;700&display=swap');
    html, body, [class*="css"] { font-family: 'Quicksand', sans-serif; }
    .stApp { background-color: #F7F7F7; }
    h1, h2, h3, h4 { color: #FF6F00 !important; font-weight: 700; }
    div[data-testid="stVerticalBlock"] > div[data-testid="stVerticalBlock"] {
        background-color: white; padding: 20px; border-radius: 20px; box-shadow: 0 4px 15px rgba(0,0,0,0.05);
    }
    .stButton>button { background-color: #FF6F00; color: white; border-radius: 25px; font-weight: bold; width: 100%; border: none; padding: 10px; }
    .stButton>button:hover { background-color: #E65100; }
    </style>
""", unsafe_allow_html=True)

# --- BARRA LATERAL (SIDEBAR) ---
with st.sidebar:
    if os.path.exists(".streamlit/nascel sem fundo.png"):
        st.image(".streamlit/nascel sem fundo.png", use_container_width=True)
    
    st.markdown("---")
    st.subheader("📥 Baixar Modelos")
    
    # Criador automático dos arquivos de modelo
    df_modelo = pd.DataFrame(columns=['NCM', 'REFERENCIA', 'DADOS'])
    buffer = io.BytesIO()
    with pd.ExcelWriter(buffer, engine='xlsxwriter') as writer:
        df_modelo.to_excel(writer, index=False)
    
    st.download_button(label="📂 Modelo ICMS", data=buffer.getvalue(), file_name="modelo_icms.xlsx", use_container_width=True)
    st.download_button(label="📂 Modelo PIS e COFINS", data=buffer.getvalue(), file_name="modelo_pis_cofins.xlsx", use_container_width=True)

    st.markdown("---")
    st.subheader("📤 Atualizar Bases")
    
    # Upload para atualizar as planilhas na pasta .streamlit
    up_icms = st.file_uploader("Atualizar Base ICMS", type=['xlsx'], key='up_i')
    if up_icms:
        with open(".streamlit/Base_ICMS.xlsx", "wb") as f:
            f.write(up_icms.getbuffer())
        st.success("Base ICMS Atualizada!")

    up_pis = st.file_uploader("Atualizar Base PIS/COF", type=['xlsx'], key='up_p')
    if up_pis:
        with open(".streamlit/Base_CST_Pis_Cofins.xlsx", "wb") as f:
            f.write(up_pis.getbuffer())
        st.success("Base PIS/COF Atualizada!")

    up_tipi = st.file_uploader("Atualizar Base TIPI", type=['xlsx'], key='up_t')
    if up_tipi:
        with open(".streamlit/Base_IPI_Tipi.xlsx", "wb") as f:
            f.write(up_tipi.getbuffer())
        st.success("Base TIPI Atualizada!")

# --- ÁREA CENTRAL ---
c1, c2, c3 = st.columns([3, 4, 3])
with c2:
    if os.path.exists(".streamlit/Sentinela.png"):
        st.image(".streamlit/Sentinela.png", use_container_width=True)

st.markdown("---")
col_ent, col_sai = st.columns(2, gap="large")

with col_ent:
    st.markdown("### 📥 1. Entradas")
    xml_ent = st.file_uploader("📂 XMLs", type='xml', accept_multiple_files=True, key="main_ue")
    aut_ent = st.file_uploader("🔍 Planilha Autenticidade", type=['xlsx'], key="main_ae")

with col_sai:
    st.markdown("### 📤 2. Saídas")
    xml_sai = st.file_uploader("📂 XMLs", type='xml', accept_multiple_files=True, key="main_us")
    as_ = st.file_uploader("🔍 Planilha Autenticidade", type=['xlsx'], key="main_as")

# --- BOTÃO DE EXECUÇÃO ---
if st.button("🚀 EXECUTAR AUDITORIA COMPLETA", type="primary", use_container_width=True):
    if not xml_ent and not xml_sai:
        st.warning("Por favor, selecione ao menos um arquivo XML.")
    else:
        with st.spinner("O Sentinela está processando os dados..."):
            # Chama as funções que estão no motor_fiscal.py
            df_e = extrair_dados_xml(xml_ent, "Entrada")
            df_s = extrair_dados_xml(xml_sai, "Saída")
            
            # Gera o arquivo final com as 6 abas
            excel_final = gerar_excel_final(df_e, df_s)
            
            st.success("Auditoria Concluída com Sucesso!")
            st.download_button(
                label="💾 BAIXAR RELATÓRIO COMPLETO",
                data=excel_final,
                file_name="Auditoria_Nascel_Sentinela.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                use_container_width=True
            )
