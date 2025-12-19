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
    
    /* Deixa os containers brancos e arredondados */
    div[data-testid="stVerticalBlock"] > div[data-testid="stVerticalBlock"] {
        background-color: white; padding: 20px; border-radius: 20px; box-shadow: 0 4px 15px rgba(0,0,0,0.05);
    }
    
    /* Botão Principal Laranja */
    .stButton>button { 
        background-color: #FF6F00; color: white; border-radius: 25px; 
        font-weight: bold; width: 100%; border: none; padding: 12px;
        transition: 0.3s;
    }
    .stButton>button:hover { background-color: #E65100; transform: scale(1.02); }

    /* Ajuste delicado para os campos de upload na lateral */
    .stFileUploader { padding-bottom: 10px; }
    </style>
""", unsafe_allow_html=True)

# --- BARRA LATERAL (SIDEBAR DELICADA) ---
with st.sidebar:
    if os.path.exists(".streamlit/nascel sem fundo.png"):
        st.image(".streamlit/nascel sem fundo.png", use_container_width=True)
    
    st.markdown("---")
    
    # Seção de Downloads
    with st.expander("📥 **Baixar Gabaritos**", expanded=False):
        df_modelo = pd.DataFrame(columns=['NCM', 'REFERENCIA', 'DADOS'])
        buffer = io.BytesIO()
        with pd.ExcelWriter(buffer, engine='xlsxwriter') as writer:
            df_modelo.to_excel(writer, index=False)
        
        st.download_button(label="📄 Modelo ICMS", data=buffer.getvalue(), file_name="modelo_icms.xlsx", use_container_width=True)
        st.download_button(label="📄 Modelo PIS/COFINS", data=buffer.getvalue(), file_name="modelo_pis_cofins.xlsx", use_container_width=True)

    # Seção de Uploads (Onde deixamos delicado)
    st.markdown("### ⚙️ Configurações")
    
    with st.expander("🔄 **Atualizar Base ICMS**"):
        up_icms = st.file_uploader("Arraste o arquivo ICMS aqui", type=['xlsx'], key='up_i', label_visibility="collapsed")
        if up_icms:
            with open(".streamlit/Base_ICMS.xlsx", "wb") as f: f.write(up_icms.getbuffer())
            st.toast("Base ICMS atualizada com sucesso!", icon="✅")

    with st.expander("🔄 **Atualizar Base PIS/COF**"):
        up_pis = st.file_uploader("Arraste o arquivo PIS aqui", type=['xlsx'], key='up_p', label_visibility="collapsed")
        if up_pis:
            with open(".streamlit/Base_CST_Pis_Cofins.xlsx", "wb") as f: f.write(up_pis.getbuffer())
            st.toast("Base PIS/COF atualizada com sucesso!", icon="✅")

    with st.expander("🔄 **Atualizar Base TIPI**"):
        up_tipi = st.file_uploader("Arraste o arquivo TIPI aqui", type=['xlsx'], key='up_t', label_visibility="collapsed")
        if up_tipi:
            with open(".streamlit/Base_IPI_Tipi.xlsx", "wb") as f: f.write(up_tipi.getbuffer())
            st.toast("Base TIPI atualizada com sucesso!", icon="✅")

# --- ÁREA CENTRAL ---
c1, c2, c3 = st.columns([3, 4, 3])
with c2:
    if os.path.exists(".streamlit/Sentinela.png"):
        st.image(".streamlit/Sentinela.png", use_container_width=True)

st.markdown("---")
col_ent, col_sai = st.columns(2, gap="large")

with col_ent:
    st.markdown("### 📥 1. Entradas")
    xml_ent = st.file_uploader("📂 Enviar XMLs de Entrada", type='xml', accept_multiple_files=True, key="main_ue")
    aut_ent = st.file_uploader("🔍 Planilha de Autenticidade", type=['xlsx'], key="main_ae")

with col_sai:
    st.markdown("### 📤 2. Saídas")
    xml_sai = st.file_uploader("📂 Enviar XMLs de Saída", type='xml', accept_multiple_files=True, key="main_us")
    as_ = st.file_uploader("🔍 Planilha de Autenticidade", type=['xlsx'], key="main_as")

# --- BOTÃO DE EXECUÇÃO ---
st.markdown("<br>", unsafe_allow_html=True)
if st.button("🚀 EXECUTAR AUDITORIA COMPLETA", type="primary", use_container_width=True):
    if not xml_ent and not xml_sai:
        st.error("Por favor, selecione ao menos um arquivo XML para analisar.")
    else:
        with st.spinner("O Sentinela está cruzando os dados tributários..."):
            df_e = extrair_dados_xml(xml_ent, "Entrada")
            df_s = extrair_dados_xml(xml_sai, "Saída")
            excel_final = gerar_excel_final(df_e, df_s)
            
            st.success("Análise finalizada!")
            st.download_button(
                label="💾 BAIXAR RELATÓRIO COMPLETO",
                data=excel_final,
                file_name="Auditoria_Nascel_Sentinela.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                use_container_width=True
            )
