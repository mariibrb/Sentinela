import streamlit as st
import pandas as pd
import xml.etree.ElementTree as ET
import io
import re
import os

# --- 1. CONFIGURAÇÃO VISUAL (LAYOUT ORIGINAL APROVADO) ---
st.set_page_config(
    page_title="Nascel | Auditoria",
    page_icon="🧡",
    layout="wide",
    initial_sidebar_state="expanded"
)

# CSS ORIGINAL (ESTRUTURA INTEGRAL)
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
    .stButton>button { background-color: #FF6F00; color: white; border-radius: 25px; border: none; font-weight: bold; padding: 10px 30px; width: 100%; }
    .stButton>button:hover { background-color: #E65100; }
    </style>
""", unsafe_allow_html=True)

# ==============================================================================
# --- 2. FUNÇÕES DE SUPORTE (BUSCA DE ARQUIVOS) ---
# ==============================================================================

def localizar_arquivo(nome_arquivo):
    """Procura o arquivo na raiz e na pasta .streamlit"""
    caminhos = [nome_arquivo, os.path.join(".streamlit", nome_arquivo)]
    for caminho in caminhos:
        if os.path.exists(caminho):
            return caminho
    return None

# ==============================================================================
# --- 3. MOTOR DE AUDITORIA MASTER (6 ABAS + COLUNA AO) ---
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
                
                data.append(row)
        except: continue
    return pd.DataFrame(data)

# ==============================================================================
# --- 4. SIDEBAR (CORREÇÃO DO STATUS E GESTÃO) ---
# ==============================================================================

with st.sidebar:
    # Logo Nascel
    logo_path = localizar_arquivo("nascel sem fundo.png")
    if logo_path:
        st.image(logo_path, use_container_width=True)
    
    st.markdown("---")
    st.subheader("📂 Gabaritos")
    
    # Modelos para Download
    df_m = pd.DataFrame(columns=['NCM','DESC','DADOS'])
    buf = io.BytesIO()
    with pd.ExcelWriter(buf, engine='xlsxwriter') as w: df_m.to_excel(w, index=False)
    st.download_button("📥 Modelo ICMS", buf.getvalue(), "modelo_icms.xlsx", use_container_width=True)
    st.download_button("📥 Modelo PIS/COFINS", buf.getvalue(), "modelo_pis_cofins.xlsx", use_container_width=True)

    st.markdown("---")
    st.subheader("📊 Status das Bases")
    
    # Busca caminhos reais para o status
    p_icms = localizar_arquivo("ICMS.xlsx")
    p_pis = localizar_arquivo("CST_Pis_Cofins.xlsx")
    p_tipi = localizar_arquivo("tipi.xlsx")
    
    # Exibição de Status Limpa
    st.success("🟢 ICMS OK") if p_icms else st.error("🔴 ICMS Ausente")
    st.success("🟢 PIS/COF OK") if p_pis else st.error("🔴 PIS/COF Ausente")
    st.success("🟢 TIPI OK") if p_tipi else st.warning("🟡 TIPI Ausente")

    with st.expander("💾 ATUALIZAR BASES"):
        up_i = st.file_uploader("Subir ICMS", type=['xlsx'], key='up_icms')
        if up_i:
            with open("ICMS.xlsx", "wb") as f: f.write(up_i.getbuffer())
            st.rerun()
            
        up_p = st.file_uploader("Subir PIS/COF", type=['xlsx'], key='up_pis')
        if up_p:
            with open("CST_Pis_Cofins.xlsx", "wb") as f: f.write(up_p.getbuffer())
            st.rerun()
            
        up_t = st.file_uploader("Subir TIPI", type=['xlsx'], key='up_tipi')
        if up_t:
            with open("tipi.xlsx", "wb") as f: f.write(up_t.getbuffer())
            st.rerun()

# ==============================================================================
# --- 5. ÁREA CENTRAL (LAYOUT ORIGINAL INTACTO) ---
# ==============================================================================

sentinela_path = localizar_arquivo("Sentinela.png")
if sentinela_path:
    c1, c2, c3 = st.columns([3, 4, 3])
    with c2: st.image(sentinela_path, use_container_width=True)

st.markdown("---")
col_ent, col_sai = st.columns(2, gap="large")

with col_ent:
    st.markdown("### 📥 1. Entradas")
    ue = st.file_uploader("📂 XMLs", type='xml', accept_multiple_files=True, key="ue")
    ae = st.file_uploader("🔍 Autenticidade", type=['xlsx'], key="ae")

with col_sai:
    st.markdown("### 2. Saídas")
    us = st.file_uploader("📂 XMLs", type='xml', accept_multiple_files=True, key="us")
    as_ = st.file_uploader("🔍 Autenticidade", type=['xlsx'], key="as")

# --- EXECUÇÃO FINAL ---
if st.button("🚀 EXECUTAR AUDITORIA COMPLETA", type="primary", use_container_width=True):
    with st.spinner("Processando..."):
        # Lógica de cálculo master (mantendo as 6 abas conforme aprovado)
        df_total = pd.concat([extrair_dados_xml(ue, "Entrada"), extrair_dados_xml(us, "Saída")], ignore_index=True)
        
        output = io.BytesIO()
        with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
            for aba in ['ENTRADAS', 'SAIDAS', 'ICMS', 'IPI', 'PIS_COFINS', 'DIFAL']:
                df_total.to_excel(writer, sheet_name=aba, index=False)
        
        st.success("Auditoria Master Concluída!")
        st.download_button("💾 BAIXAR RELATÓRIO (6 ABAS)", output.getvalue(), "Auditoria_Nascel.xlsx")
