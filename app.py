import streamlit as st
import pandas as pd
import xml.etree.ElementTree as ET
import io
import re
import os

# --- 1. CONFIGURAÇÃO VISUAL (ORIGINAL) ---
st.set_page_config(
    page_title="Nascel | Auditoria",
    page_icon="🧡",
    layout="wide",
    initial_sidebar_state="expanded"
)

# CSS PERSONALIZADO (EXATAMENTE O SEU)
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
# --- 2. MOTORES DE EXTRAÇÃO E AUDITORIA (CÉREBRO) ---
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
            if inf is None: continue
            chave = inf.attrib.get('Id', '')[3:]
            
            for det in root.findall('.//det'):
                prod = det.find('prod')
                imp = det.find('imposto')
                
                # Dados básicos
                row = {
                    'Fluxo': fluxo, 'Chave': chave, 'Arquivo': f.name,
                    'NCM': prod.find('NCM').text if prod.find('NCM') is not None else "",
                    'CFOP': prod.find('CFOP').text if prod.find('CFOP') is not None else "",
                    'Valor': float(prod.find('vProd').text) if prod.find('vProd') is not None else 0.0,
                    'CST_ICMS_NF': "", 'CST_PIS_NF': "", 'CST_COFINS_NF': ""
                }
                
                # CST ICMS
                icms = imp.find('.//ICMS')
                if icms is not None:
                    for c in icms:
                        node = c.find('CST') or c.find('CSOSN')
                        if node is not None: row['CST_ICMS_NF'] = node.text
                
                # CST PIS
                pis = imp.find('.//PIS')
                if pis is not None:
                    for p in pis:
                        node = p.find('CST')
                        if node is not None: row['CST_PIS_NF'] = node.text
                
                # CST COFINS
                cof = imp.find('.//COFINS')
                if cof is not None:
                    for c in cof:
                        node = c.find('CST')
                        if node is not None: row['CST_COFINS_NF'] = node.text
                        
                data.append(row)
        except: continue
    return pd.DataFrame(data)

def realizar_auditoria(df, b_icms, b_pc):
    if df.empty: return df
    
    # Limpeza do NCM para cruzamento
    df['NCM_L'] = df['NCM'].str.replace(r'\D', '', regex=True).str.zfill(8)

    # AUDITORIA ICMS (Lógica 9 colunas A-I)
    if b_icms is not None and not b_icms.empty:
        # Pega colunas: 0 (NCM), 2 (CST Interno), 6 (CST Externo)
        rules_icms = b_icms.iloc[:, [0, 2, 6]].copy()
        rules_icms.columns = ['NCM_R', 'CST_INT_R', 'CST_EXT_R']
        rules_icms['NCM_R'] = rules_icms['NCM_R'].astype(str).str.replace(r'\D', '', regex=True).str.zfill(8)
        df = pd.merge(df, rules_icms, left_on='NCM_L', right_on='NCM_R', how='left')
        
        def validar_icms(r):
            if pd.isna(r['NCM_R']): return "NCM NÃO CADASTRADO"
            cfop = str(r['CFOP'])
            # CFOP começando com 5 (Interno) ou 6 (Externo)
            esp = str(r['CST_INT_R']) if cfop.startswith('5') else str(r['CST_EXT_R'])
            esp = str(esp).split('.')[0].zfill(2)
            nf = str(r['CST_ICMS_NF']).zfill(2)
            return "OK" if nf == esp else f"ERRO (Esp: {esp})"
        df['ANALISE_ICMS'] = df.apply(validar_icms, axis=1)

    # AUDITORIA PIS/COFINS
    if b_pc is not None and not b_pc.empty:
        rules_pc = b_pc.iloc[:, [0, 1, 2]].copy() # NCM, ENT, SAI
        rules_pc.columns = ['NCM_P', 'CST_E_P', 'CST_S_P']
        rules_pc['NCM_P'] = rules_pc['NCM_P'].astype(str).str.replace(r'\D', '', regex=True).str.zfill(8)
        df = pd.merge(df, rules_pc, left_on='NCM_L', right_on='NCM_P', how='left')
        
        def validar_pc(r):
            if pd.isna(r['NCM_P']): return "NCM NÃO CADASTRADO"
            cfop = str(r['CFOP'])
            # Entrada (1,2,3) ou Saída (5,6,7)
            esp = str(r['CST_E_P']) if cfop[0] in '123' else str(r['CST_S_P'])
            esp = str(esp).split('.')[0].zfill(2)
            nf = str(r['CST_PIS_NF']).zfill(2)
            return "OK" if nf == esp else f"ERRO (Esp: {esp})"
        df['ANALISE_PIS_COFINS'] = df.apply(validar_pc, axis=1)

    return df

# ==============================================================================
# --- 3. SIDEBAR (LOGOS, STATUS E GESTÃO) ---
# ==============================================================================
with st.sidebar:
    if os.path.exists(".streamlit/nascel sem fundo.png"):
        st.image(".streamlit/nascel sem fundo.png", use_column_width=True)
    elif os.path.exists("nascel sem fundo.png"):
        st.image("nascel sem fundo.png", use_column_width=True)
    else:
        st.markdown("<h1 style='color:#FF6F00; text-align:center;'>Nascel</h1>", unsafe_allow_html=True)
    
    st.markdown("---")

    def get_file(name):
        paths = [f".streamlit/{name}", name, f"bases/{name}"]
        for p in paths:
            if os.path.exists(p): return p
        return None

    st.subheader("📊 Status das Bases")
    f_icms = get_file("base_icms.xlsx")
    f_pc = get_file("CST_Pis_Cofins.xlsx")

    if f_icms: st.success("🟢 Base ICMS OK")
    else: st.error("🔴 Base ICMS Ausente")
    
    if f_pc: st.success("🟢 Base PIS/COF OK")
    else: st.error("🔴 Base PIS/COF Ausente")

    st.markdown("---")

    with st.expander("💾 GERENCIAR BASES"):
        if f_icms:
            with open(f_icms, "rb") as f: st.download_button("📥 Baixar ICMS Atual", f, "base_icms.xlsx", key="dl_icms")
        up_i = st.file_uploader("Trocar ICMS (A-I)", type=['xlsx'], key='up_i')
        if up_i:
            with open("base_icms.xlsx", "wb") as f: f.write(up_i.getbuffer())
            st.rerun()

        st.markdown("---")
        if f_pc:
            with open(f_pc, "rb") as f: st.download_button("📥 Baixar PIS/COF Atual", f, "CST_Pis_Cofins.xlsx", key="dl_pc")
        up_p = st.file_uploader("Trocar PIS/COF", type=['xlsx'], key='up_p')
        if up_p:
            with open("CST_Pis_Cofins.xlsx", "wb") as f: f.write(up_p.getbuffer())
            st.rerun()

    with st.expander("📂 GABARITOS"):
        df_micms = pd.DataFrame(columns=['NCM','DESC_I','CST_I','AL_I','RE_I','DESC_E','CST_E','AL_E','OBS'])
        buf_i = io.BytesIO()
        with pd.ExcelWriter(buf_i, engine='xlsxwriter') as w: df_micms.to_excel(w, index=False)
        st.download_button("Gabarito ICMS", buf_i.getvalue(), "modelo_icms.xlsx")
        
        df_mpc = pd.DataFrame({'NCM': ['00000000'], 'CST_ENT': ['50'], 'CST_SAI': ['01']})
        buf_p = io.BytesIO()
        with pd.ExcelWriter(buf_p, engine='xlsxwriter') as w: df_mpc.to_excel(w, index=False)
        st.download_button("Gabarito PIS/COF", buf_p.getvalue(), "modelo_pc.xlsx")

# ==============================================================================
# --- 4. ÁREA CENTRAL (LAYOUT ORIGINAL) ---
# ==============================================================================

if os.path.exists(".streamlit/Sentinela.png"):
    col_l, col_tit, col_r = st.columns([3, 4, 3])
    with col_tit: st.image(".streamlit/Sentinela.png", use_column_width=True)
elif os.path.exists("Sentinela.png"):
    col_l, col_tit, col_r = st.columns([3, 4, 3])
    with col_tit: st.image("Sentinela.png", use_column_width=True)
else:
    st.markdown("<h1 style='text-align: center; color: #FF6F00;'>SENTINELA</h1>", unsafe_allow_html=True)

st.markdown("---")

col_ent, col_sai = st.columns(2, gap="large")

with col_ent:
    st.markdown("### 📥 1. Entradas")
    st.markdown("---")
    up_ent_xml = st.file_uploader("📂 XMLs", type='xml', accept_multiple_files=True, key="ent_xml")
    up_ent_aut = st.file_uploader("🔍 Autenticidade Entradas", type=['xlsx', 'csv'], key="ent_aut")

with col_sai:
    st.markdown("### 2. Saídas")
    st.markdown("---")
    up_sai_xml = st.file_uploader("📂 XMLs", type='xml', accept_multiple_files=True, key="sai_xml")
    up_sai_aut = st.file_uploader("🔍 Autenticidade Saídas", type=['xlsx', 'csv'], key="sai_aut")

# --- EXECUÇÃO DA AUDITORIA ---
st.markdown("<br>", unsafe_allow_html=True)
if st.button("🚀 EXECUTAR AUDITORIA COMPLETA", type="primary", use_container_width=True):
    if not up_ent_xml and not up_sai_xml:
        st.warning("Por favor, carregue os arquivos XML para análise.")
    else:
        with st.spinner("Realizando análises de ICMS, PIS e COFINS..."):
            # Carregamento das bases
            path_i = get_file("base_icms.xlsx")
            path_p = get_file("CST_Pis_Cofins.xlsx")
            b_icms = pd.read_excel(path_i, dtype=str) if path_i else None
            b_pc = pd.read_excel(path_p, dtype=str) if path_p else None
            
            # Extração
            df_e = extrair_dados_xml(up_ent_xml, "Entrada")
            df_s = extrair_dados_xml(up_sai_xml, "Saída")
            df_total = pd.concat([df_e, df_s], ignore_index=True)
            
            # Auditoria
            df_final = realizar_auditoria(df_total, b_icms, b_pc)
            
            st.success("Auditoria Concluída!")
            st.dataframe(df_final, use_container_width=True)
            
            # Geração do Excel com Abas
            output = io.BytesIO()
            with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
                df_final.to_excel(writer, sheet_name='RELATORIO_GERAL', index=False)
                
                # Filtra Divergências (ERRO ou NÃO CADASTRADO)
                cond_erro = (df_final.get('ANALISE_ICMS', '').str.contains('ERRO|NÃO', na=False)) | \
                            (df_final.get('ANALISE_PIS_COFINS', '').str.contains('ERRO|NÃO', na=False))
                df_erros = df_final[cond_erro]
                df_erros.to_excel(writer, sheet_name='DIVERGENCIAS', index=False)
            
            st.download_button(
                label="💾 BAIXAR PLANILHA COM TODAS AS ABAS",
                data=output.getvalue(),
                file_name="Auditoria_Consolidada.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            )
