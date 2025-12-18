import streamlit as st
import pandas as pd
import xml.etree.ElementTree as ET
import io
import re
import os

# --- 1. CONFIGURAÇÃO VISUAL ---
st.set_page_config(page_title="Nascel | Auditoria", page_icon="🧡", layout="wide")

# CSS (IDENTIDADE ORIGINAL)
st.markdown("""
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Quicksand:wght@400;600;700&display=swap');
    html, body, [class*="css"] { font-family: 'Quicksand', sans-serif; }
    .stApp { background-color: #F7F7F7; }
    h1, h2, h3 { color: #FF6F00 !important; }
    div[data-testid="stVerticalBlock"] > div { background-color: white; padding: 15px; border-radius: 15px; }
    </style>
""", unsafe_allow_html=True)

# ==============================================================================
# --- 2. MOTOR DE EXTRAÇÃO TÉCNICA ---
# ==============================================================================

def extrair_xmls(files, fluxo):
    dados = []
    if not files: return pd.DataFrame()
    for f in files:
        try:
            f.seek(0)
            tree = ET.parse(f)
            root = tree.getroot()
            ns = {'nfe': 'http://www.portalfiscal.inf.br/nfe'}
            
            for det in root.findall('.//nfe:det', ns):
                prod = det.find('nfe:prod', ns)
                imp = det.find('nfe:imposto', ns)
                
                item = {
                    'Fluxo': fluxo,
                    'Chave': root.find('.//nfe:infNFe', ns).attrib['Id'][3:],
                    'NCM': prod.find('nfe:NCM', ns).text,
                    'CFOP': prod.find('nfe:CFOP', ns).text,
                    'Valor_Prod': float(prod.find('nfe:vProd', ns).text),
                    'CST_ICMS': "", 'Aliq_ICMS': 0.0, 'Aliq_IPI': 0.0, 'CST_PIS': "", 'CST_COF': ""
                }
                
                # ICMS
                icms = imp.find('.//nfe:ICMS', ns)
                if icms is not None:
                    for tag in icms[0]:
                        if 'CST' in tag.tag or 'CSOSN' in tag.tag: item['CST_ICMS'] = tag.text
                        if 'pICMS' in tag.tag: item['Aliq_ICMS'] = float(tag.text)
                
                # IPI / PIS / COFINS
                ipi = imp.find('.//nfe:IPI/nfe:IPITrib/nfe:pIPI', ns)
                if ipi is not None: item['Aliq_IPI'] = float(ipi.text)
                
                pis = imp.find('.//nfe:PIS//nfe:CST', ns)
                if pis is not None: item['CST_PIS'] = pis.text
                
                dados.append(item)
        except: continue
    return pd.DataFrame(dados)

# ==============================================================================
# --- 3. LÓGICA DE AUDITORIA (REGRA COLUNA AO / ÍNDICE 40) ---
# ==============================================================================

def processar_auditoria(df_xml, b_icms, b_pc):
    if df_xml.empty: return {}
    
    # Normalização
    df_xml['NCM_L'] = df_xml['NCM'].str.replace(r'\D', '', regex=True).str.zfill(8)
    
    # 1. Cruzamento ICMS/DIFAL (Coluna AO é o índice 40 no Python)
    # Supondo que a Alíquota Interna para cálculo do DIFAL está na coluna AO
    if b_icms is not None:
        try:
            # Pegamos NCM(0), CST_INT(2), CST_EXT(6) e ALIQ_AO(40)
            regras = b_icms.iloc[:, [0, 2, 6, 40]].copy()
            regras.columns = ['NCM_R', 'CST_INT', 'CST_EXT', 'ALIQ_INTERNA_AO']
            regras['NCM_R'] = regras['NCM_R'].astype(str).str.zfill(8)
            df_xml = pd.merge(df_xml, regras, left_on='NCM_L', right_on='NCM_R', how='left')
        except: pass

    # Separação por Tributo para as Abas
    aba_icms = df_xml.copy()
    aba_ipi = df_xml[df_xml['Aliq_IPI'] > 0].copy()
    aba_pc = df_xml.copy() # PIS/COFINS
    
    # DIFAL: Diferença entre a Alíquota Interna (AO) e a da Nota (Inter)
    df_xml['DIFAL_ESTIMADO'] = df_xml.apply(lambda r: float(str(r.get('ALIQ_INTERNA_AO', 0)).replace(',','.')) - r['Aliq_ICMS'] if str(r['CFOP']).startswith('6') else 0, axis=1)
    aba_difal = df_xml[df_xml['DIFAL_ESTIMADO'] > 0].copy()

    return {
        'ENTRADAS': df_xml[df_xml['Fluxo'] == 'Entrada'],
        'SAIDAS': df_xml[df_xml['Fluxo'] == 'Saída'],
        'ICMS': aba_icms,
        'IPI': aba_ipi,
        'PIS_COFINS': aba_pc,
        'DIFAL': aba_difal
    }

# ==============================================================================
# --- 4. INTERFACE E SIDEBAR ---
# ==============================================================================

with st.sidebar:
    for l in [".streamlit/nascel sem fundo.png", "nascel sem fundo.png"]:
        if os.path.exists(l): st.image(l); break
    
    st.markdown("---")
    st.subheader("⚙️ Configuração de Bases")
    f_i = st.file_uploader("Base ICMS (Precisa da Coluna AO)", type=['xlsx'])
    f_p = st.file_uploader("Base PIS/COFINS", type=['xlsx'])

# LAYOUT CENTRAL (COLUNAS 1 E 2)
st.markdown("<h2 style='text-align: center;'>SENTINELA - AUDITORIA COMPLETA</h2>", unsafe_allow_html=True)
col1, col2 = st.columns(2)

with col1:
    st.subheader("📥 1. Entradas")
    xml_ent = st.file_uploader("XMLs Entrada", accept_multiple_files=True, key="e")
with col2:
    st.subheader("📤 2. Saídas")
    xml_sai = st.file_uploader("XMLs Saída", accept_multiple_files=True, key="s")

if st.button("🚀 EXECUTAR AUDITORIA APROVADA", use_container_width=True):
    with st.spinner("Processando todas as abas..."):
        df_e = extrair_xmls(xml_ent, "Entrada")
        df_s = extrair_xmls(xml_sai, "Saída")
        df_total = pd.concat([df_e, df_s])
        
        b_icms = pd.read_excel(f_i) if f_i else None
        b_pc = pd.read_excel(f_p) if f_p else None
        
        # Gera o dicionário de abas
        abas = processar_auditoria(df_total, b_icms, b_pc)
        
        # EXPORTAÇÃO COM AS ABAS ESPECÍFICAS
        output = io.BytesIO()
        with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
            for nome_aba, dados_aba in abas.items():
                dados_aba.to_excel(writer, sheet_name=nome_aba, index=False)
        
        st.success("Relatório gerado com sucesso!")
        st.download_button("💾 BAIXAR AUDITORIA COMPLETA (6 ABAS)", output.getvalue(), "Auditoria_Nascel.xlsx")
