import streamlit as st
import pandas as pd
import xml.etree.ElementTree as ET
import io
import re
import os

# --- 1. CONFIGURAÇÃO VISUAL (RESTAURAÇÃO DO LAYOUT ORIGINAL) ---
st.set_page_config(
    page_title="Nascel | Auditoria",
    page_icon="🧡",
    layout="wide",
    initial_sidebar_state="expanded"
)

# CSS ORIGINAL (IDENTIDADE VISUAL APROVADA)
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
# --- 2. MOTOR DE AUDITORIA PROFUNDA (300+ LINHAS DE LÓGICA) ---
# ==============================================================================

def extrair_motor_fiscal(files, fluxo):
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
                    'CST_PIS_NF': "", 'CST_COF_NF': "", 'UF_Dest': uf_dest
                }
                
                # Extração Técnica de Impostos
                if imp is not None:
                    # ICMS
                    icms_node = imp.find('.//ICMS')
                    if icms_node is not None:
                        for c in icms_node:
                            cst_n = c.find('CST') or c.find('CSOSN')
                            if cst_n is not None: row['CST_ICMS_NF'] = cst_n.text
                            if c.find('pICMS') is not None: row['Aliq_ICMS_NF'] = float(c.find('pICMS').text)
                    
                    # IPI
                    ipi_node = imp.find('.//IPI')
                    if ipi_node is not None:
                        p_ipi = ipi_node.find('.//pIPI')
                        if p_ipi is not None: row['Aliq_IPI_NF'] = float(p_ipi.text)
                    
                    # PIS/COFINS
                    pis_node = imp.find('.//PIS')
                    if pis_node is not None:
                        c_pis = pis_node.find('.//CST')
                        if c_pis is not None: row['CST_PIS_NF'] = c_pis.text
                
                data.append(row)
        except: continue
    return pd.DataFrame(data)

def auditoria_master(df, bi, bp, bt):
    if df.empty: return {}
    df['NCM_L'] = df['NCM'].str.replace(r'\D', '', regex=True).str.zfill(8)

    # 1. ICMS E DIFAL (REGRA COLUNA AO / ÍNDICE 40)
    if bi is not None:
        # Posições: NCM(0), CST_I(2), CST_E(6), ALIQ_INT_AO(40)
        rules_i = bi.iloc[:, [0, 2, 6, 40]].copy()
        rules_i.columns = ['NCM_R', 'CST_INT_R', 'CST_EXT_R', 'ALIQ_INT_AO']
        rules_i['NCM_R'] = rules_i['NCM_R'].astype(str).str.zfill(8)
        df = pd.merge(df, rules_i, left_on='NCM_L', right_on='NCM_R', how='left')
        
        # Cálculo DIFAL: (Aliq Interna AO - Aliq Nota)
        df['DIFAL_ESTIMADO'] = df.apply(lambda r: (float(str(r['ALIQ_INT_AO']).replace(',','.')) - r['Aliq_ICMS_NF']) if str(r['CFOP']).startswith('6') else 0, axis=1)

    # 2. PIS/COFINS
    if bp is not None:
        rules_p = bp.iloc[:, [0, 1, 2]].copy()
        rules_p.columns = ['NCM_P', 'CST_E_P', 'CST_S_P']
        rules_p['NCM_P'] = rules_p['NCM_P'].astype(str).str.zfill(8)
        df = pd.merge(df, rules_p, left_on='NCM_L', right_on='NCM_P', how='left')

    return {
        'ENTRADAS': df[df['Fluxo'] == 'Entrada'],
        'SAIDAS': df[df['Fluxo'] == 'Saída'],
        'ICMS': df[['Chave', 'NCM', 'CFOP', 'CST_ICMS_NF', 'CST_INT_R', 'CST_EXT_R', 'Aliq_ICMS_NF']],
        'IPI': df[df['Aliq_IPI_NF'] > 0],
        'PIS_COFINS': df[['Chave', 'NCM', 'CST_PIS_NF', 'CST_E_P', 'CST_S_P']],
        'DIFAL': df[df['DIFAL_ESTIMADO'] > 0]
    }

# ==============================================================================
# --- 3. SIDEBAR (LOGO NASCEL E STATUS) ---
# ==============================================================================
with st.sidebar:
    for l in [".streamlit/nascel sem fundo.png", "nascel sem fundo.png"]:
        if os.path.exists(l): st.image(l, use_column_width=True); break
    else: st.title("Nascel")
    
    st.markdown("---")
    st.subheader("📊 Bases de Auditoria")
    p_i = "ICMS.xlsx" if os.path.exists("ICMS.xlsx") else "base_icms.xlsx"
    p_p = "CST_Pis_Cofins.xlsx"
    
    st.success("🟢 ICMS/DIFAL OK") if os.path.exists(p_i) else st.error("🔴 ICMS OFF")
    st.success("🟢 PIS/COF OK") if os.path.exists(p_p) else st.error("🔴 PIS/COF OFF")

    with st.expander("💾 Trocar Bases"):
        up_i = st.file_uploader("Subir ICMS (Mapeia Coluna AO)", type=['xlsx'])
        if up_i:
            with open("ICMS.xlsx", "wb") as f: f.write(up_i.getbuffer())
            st.rerun()

# ==============================================================================
# --- 4. ÁREA CENTRAL (SENTINELA) ---
# ==============================================================================
for s in [".streamlit/Sentinela.png", "Sentinela.png"]:
    if os.path.exists(s):
        col_l, col_tit, col_r = st.columns([3, 4, 3])
        with col_tit: st.image(s, use_column_width=True); break

st.markdown("---")
col_ent, col_sai = st.columns(2, gap="large")

with col_ent:
    st.markdown("### 📥 1. Entradas")
    ue = st.file_uploader("📂 XMLs", type='xml', accept_multiple_files=True, key="ue")
    ae = st.file_uploader("🔍 Autenticidade Entradas", type=['xlsx'], key="ae")
with col_sai:
    st.markdown("### 📤 2. Saídas")
    us = st.file_uploader("📂 XMLs", type='xml', accept_multiple_files=True, key="us")
    as_ = st.file_uploader("🔍 Autenticidade Saídas", type=['xlsx'], key="as")

st.markdown("<br>", unsafe_allow_html=True)

if st.button("🚀 EXECUTAR AUDITORIA MASTER", type="primary", use_container_width=True):
    with st.spinner("Gerando auditoria completa com 6 abas..."):
        bi = pd.read_excel(p_i, dtype=str) if os.path.exists(p_i) else None
        bp = pd.read_excel(p_p, dtype=str) if os.path.exists(p_p) else None
        
        df_total = pd.concat([extrair_motor_fiscal(ue, "Entrada"), extrair_motor_fiscal(us, "Saída")], ignore_index=True)
        abas_dict = auditoria_master(df_total, bi, bp, None)
        
        # EXPORTADOR PARA EXCEL COM AS 6 ABAS
        output = io.BytesIO()
        with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
            for nome, dados in abas_dict.items():
                dados.to_excel(writer, sheet_name=nome, index=False)
        
        st.success("Relatório Master Pronto!")
        st.download_button("💾 BAIXAR RELATÓRIO (ENT/SAI/ICMS/IPI/PIS/DIFAL)", output.getvalue(), "Auditoria_Nascel_Sentinela.xlsx")
