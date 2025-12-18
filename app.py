import streamlit as st
import pandas as pd
import xml.etree.ElementTree as ET
import io
import re
import os

# ==============================================================================
# 1. CONFIGURAÇÃO VISUAL (IDENTIDADE NASCEL)
# ==============================================================================
st.set_page_config(page_title="Nascel | Sentinela", page_icon="🧡", layout="wide")

st.markdown("""
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Quicksand:wght@400;600;700&display=swap');
    html, body, [class*="css"] { font-family: 'Quicksand', sans-serif; }
    .stApp { background-color: #F7F7F7; }
    h1, h2, h3 { color: #FF6F00 !important; font-weight: 700; }
    .stButton>button { background-color: #FF6F00; color: white; border-radius: 25px; font-weight: bold; width: 100%; transition: 0.3s; }
    .stButton>button:hover { background-color: #E65100; transform: scale(1.02); }
    [data-testid="stSidebar"] { background-color: #FFFFFF; border-right: 1px solid #EEE; padding-top: 2rem; }
    .status-box { padding: 10px; border-radius: 10px; margin-bottom: 10px; text-align: center; font-weight: bold; }
    </style>
""", unsafe_allow_html=True)

# ==============================================================================
# 2. FUNÇÕES TÉCNICAS (EXTRAÇÃO E AUDITORIA)
# ==============================================================================

@st.cache_data
def carregar_base_inicial(nome_arquivo, colunas=None):
    """Tenta ler as bases do repositório/GitHub automaticamente."""
    paths = [nome_arquivo, f".streamlit/{nome_arquivo}", f"bases/{nome_arquivo}"]
    for p in paths:
        if os.path.exists(p):
            try:
                return pd.read_excel(p, usecols=colunas, dtype=str) if colunas else pd.read_excel(p, dtype=str)
            except: continue
    return None

def extrair_xmls(files, fluxo):
    """Lógica de extração de dados dos XMLs."""
    data = []
    for f in files:
        try:
            tree = ET.parse(f)
            root = tree.getroot()
            ns = {'nfe': 'http://www.portalfiscal.inf.br/nfe'}
            for det in root.findall('.//nfe:det', ns):
                prod = det.find('nfe:prod', ns)
                imposto = det.find('nfe:imposto', ns)
                
                # Coleta básica
                ncm = prod.find('nfe:NCM', ns).text if prod is not None else ""
                cfop = prod.find('nfe:CFOP', ns).text if prod is not None else ""
                v_prod = float(prod.find('nfe:vProd', ns).text) if prod is not None else 0.0
                
                # Coleta ICMS
                cst_icms = ""
                icms_tag = imposto.find('.//nfe:ICMS', ns) if imposto is not None else None
                if icms_tag is not None:
                    for tag in icms_tag:
                        c = tag.find('nfe:CST', ns) or tag.find('nfe:CSOSN', ns)
                        if c is not None: cst_icms = c.text

                data.append({
                    'Fluxo': fluxo, 'NCM': ncm, 'CFOP': cfop, 
                    'CST_NF': cst_icms, 'Vl_Produto': v_prod, 'Arquivo': f.name
                })
        except: continue
    return pd.DataFrame(data)

def motor_auditoria(df_notas, df_regras):
    """Aplica a regra Interna (B-E) ou Interestadual (F-I) pelo CFOP."""
    if df_regras is None or df_notas.empty: return df_notas
    
    # Ajusta cabeçalhos da Base Rosa (A-I)
    df_regras.columns = ['NCM', 'D_Int', 'CST_Int', 'Aliq_Int', 'Red_Int', 'D_Ext', 'CST_Ext', 'Aliq_Ext', 'Obs']
    df_regras['NCM_Limpo'] = df_regras['NCM'].str.replace(r'\D', '', regex=True).str.zfill(8)
    
    df_notas['NCM_Busca'] = df_notas['NCM'].str.replace(r'\D', '', regex=True).str.zfill(8)
    df_final = pd.merge(df_notas, df_regras, left_on='NCM_Busca', right_on='NCM_Limpo', how='left')

    def validar_linha(row):
        if pd.isna(row['NCM_Limpo']): return "NCM NÃO CADASTRADO"
        cfop = str(row['CFOP'])
        cst_nota = str(row['CST_NF']).zfill(2)
        # CFOP 5 = Interno, 6 = Externo
        cst_esperado = str(row['CST_Int']).zfill(2) if cfop.startswith('5') else str(row['CST_Ext']).zfill(2)
        return "OK" if cst_nota == cst_esperado else f"ERRO CST (Esperado {cst_esperado})"

    df_final['STATUS_AUDITORIA'] = df_final.apply(validar_linha, axis=1)
    return df_final

# ==============================================================================
# 3. LAYOUT: BARRA LATERAL (CENTRO DE CONTROLE)
# ==============================================================================
with st.sidebar:
    st.image("https://raw.githubusercontent.com/seu-usuario/seu-repo/main/.streamlit/nascel%20sem%20fundo.png", width=180) # URL do seu GitHub
    st.markdown("### 🛠️ Gestão de Bases")
    st.divider()

    # Inicialização das Bases no Session State
    if 'df_icms' not in st.session_state:
        st.session_state['df_icms'] = carregar_base_inicial("base_icms.xlsx", colunas="A:I")
    if 'df_tipi' not in st.session_state:
        st.session_state['df_tipi'] = carregar_base_inicial("tipi.xlsx")

    # Indicadores Visuais de Status
    st.markdown("**Status da Conexão:**")
    if st.session_state['df_icms'] is not None:
        st.success("🟢 BASE ICMS: ATIVA")
    else:
        st.error("🔴 BASE ICMS: AUSENTE")

    if st.session_state['df_tipi'] is not None:
        st.success("🟢 TIPI: ATIVA")
    else:
        st.error("🔴 TIPI: AUSENTE")

    st.divider()
    
    # Opção de Atualização Manual
    with st.expander("⬆️ Atualizar Arquivos"):
        up_icms = st.file_uploader("Nova Base ICMS (A-I)", type="xlsx")
        if up_icms:
            st.session_state['df_icms'] = pd.read_excel(up_icms, usecols="A:I", dtype=str)
            st.success("ICMS Atualizado!")
            st.rerun()
            
        up_tipi = st.file_uploader("Nova TIPI", type="xlsx")
        if up_tipi:
            st.session_state['df_tipi'] = pd.read_excel(up_tipi, dtype=str)
            st.success("TIPI Atualizada!")

# ==============================================================================
# 4. ÁREA CENTRAL (OPERAÇÃO E GABARITOS)
# ==============================================================================

# Título Principal
st.markdown("<h1 style='text-align: center;'>SENTINELA FISCAL</h1>", unsafe_allow_html=True)
st.caption("<p style='text-align: center;'>Módulo de Auditoria Inteligente de ICMS - Fluxo Mirão</p>", unsafe_allow_html=True)

tab_trabalho, tab_gabaritos = st.tabs(["🚀 Auditoria", "📂 Gabaritos"])

# Aba de Gabaritos (Sem TIPI Vazia, apenas ICMS conforme solicitado)
with tab_gabaritos:
    st.subheader("Modelos para Preenchimento")
    st.info("Baixe o modelo abaixo caso precise cadastrar novos NCMs na sua base de regras.")
    
    cols_modelo = ['NCM', 'DESC_INT', 'CST_INT', 'ALIQ_INT', 'RED_INT', 'DESC_EXT', 'CST_EXT', 'ALIQ_EXT', 'OBS']
    df_mod = pd.DataFrame(columns=cols_modelo)
    buf = io.BytesIO()
    with pd.ExcelWriter(buf, engine='xlsxwriter') as w:
        df_mod.to_excel(w, index=False)
    st.download_button("📥 Baixar Modelo ICMS (9 Colunas)", buf.getvalue(), "modelo_regras_icms.xlsx")

# Aba de Auditoria (Área de Uploads)
with tab_trabalho:
    c1, c2 = st.columns(2, gap="large")
    with c1:
        st.markdown("### 📥 1. Entradas")
        xmls_e = st.file_uploader("XMLs de Entrada", type="xml", accept_multiple_files=True, key="e1")
    with c2:
        st.markdown("### 📤 2. Saídas")
        xmls_s = st.file_uploader("XMLs de Saída", type="xml", accept_multiple_files=True, key="s1")

    st.divider()
    
    if st.button("🚀 EXECUTAR AUDITORIA COMPLETA", type="primary", use_container_width=True):
        if not xmls_e and not xmls_s:
            st.warning("Por favor, carregue arquivos XML para análise.")
        elif st.session_state['df_icms'] is None:
            st.error("ERRO: A Base de ICMS não foi detectada na barra lateral!")
        else:
            with st.spinner("Processando Auditoria..."):
                # Extração
                df_ent = extrair_xmls(xmls_e, "Entrada")
                df_sai = extrair_xmls(xmls_s, "Saída")
                df_total = pd.concat([df_ent, df_sai], ignore_index=True)
                
                # Auditoria com as Regras A-I
                resultado = motor_auditoria(df_total, st.session_state['df_icms'])
                
                # Exibição
                st.subheader("📊 Resultado da Análise")
                st.dataframe(resultado, use_container_width=True)
                
                # Download do Relatório Final
                rel_buf = io.BytesIO()
                with pd.ExcelWriter(rel_buf, engine='xlsxwriter') as wr:
                    resultado.to_excel(wr, index=False)
                st.download_button("💾 Baixar Relatório de Auditoria", rel_buf.getvalue(), "Auditoria_Finalizada.xlsx")
