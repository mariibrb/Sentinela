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

# CSS PERSONALIZADO (MANTIDO)
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
# --- 2. MOTORES DE AUDITORIA (LÓGICA DAS ABAS) ---
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
                row = {
                    'Fluxo': fluxo, 'Chave': chave, 'Arquivo': f.name,
                    'NCM': prod.find('NCM').text if prod.find('NCM') is not None else "",
                    'CFOP': prod.find('CFOP').text if prod.find('CFOP') is not None else "",
                    'Valor': float(prod.find('vProd').text) if prod.find('vProd') is not None else 0.0,
                    'CST_ICMS_NF': "", 'CST_PIS_NF': ""
                }
                # Captura ICMS
                icms = imp.find('.//ICMS')
                if icms is not None:
                    for c in icms:
                        node = c.find('CST') or c.find('CSOSN')
                        if node is not None: row['CST_ICMS_NF'] = node.text
                # Captura PIS
                pis = imp.find('.//PIS')
                if pis is not None:
                    for p in pis:
                        node = p.find('CST')
                        if node is not None: row['CST_PIS_NF'] = node.text
                data.append(row)
        except: continue
    return pd.DataFrame(data)

def realizar_auditoria_completa(df, b_icms, b_pc):
    if df.empty: return df
    df['NCM_L'] = df['NCM'].str.replace(r'\D', '', regex=True).str.zfill(8)

    # --- ANÁLISE ICMS (Colunas A, C e G da sua planilha) ---
    if b_icms is not None and not b_icms.empty:
        if len(b_icms.columns) >= 7:
            rules_icms = b_icms.iloc[:, [0, 2, 6]].copy()
            rules_icms.columns = ['NCM_R', 'CST_INT_R', 'CST_EXT_R']
            rules_icms['NCM_R'] = rules_icms['NCM_R'].astype(str).str.replace(r'\D', '', regex=True).str.zfill(8)
            df = pd.merge(df, rules_icms, left_on='NCM_L', right_on='NCM_R', how='left')
            
            def check_icms(r):
                if pd.isna(r['NCM_R']): return "NCM NÃO CADASTRADO"
                esp = str(r['CST_INT_R']) if str(r['CFOP']).startswith('5') else str(r['CST_EXT_R'])
                esp = str(esp).split('.')[0].zfill(2)
                return "OK" if str(r['CST_ICMS_NF']).zfill(2) == esp else f"ERRO (Esp: {esp})"
            df['ANALISE_ICMS'] = df.apply(check_icms, axis=1)

    # --- ANÁLISE PIS/COFINS ---
    if b_pc is not None and not b_pc.empty:
        if len(b_pc.columns) >= 3:
            rules_pc = b_pc.iloc[:, [0, 1, 2]].copy()
            rules_pc.columns = ['NCM_P', 'CST_E_P', 'CST_S_P']
            rules_pc['NCM_P'] = rules_pc['NCM_P'].astype(str).str.replace(r'\D', '', regex=True).str.zfill(8)
            df = pd.merge(df, rules_pc, left_on='NCM_L', right_on='NCM_P', how='left')
            
            def check_pc(r):
                if pd.isna(r['NCM_P']): return "NCM NÃO CADASTRADO"
                esp = str(r['CST_E_P']) if str(r['CFOP'])[0] in '123' else str(r['CST_S_P'])
                esp = str(esp).split('.')[0].zfill(2)
                return "OK" if str(r['CST_PIS_NF']).zfill(2) == esp else f"ERRO (Esp: {esp})"
            df['ANALISE_PIS_COFINS'] = df.apply(check_pc, axis=1)

    return df

# ==============================================================================
# --- 3. SIDEBAR (LOGO E GESTÃO) ---
# ==============================================================================
with st.sidebar:
    logos = [".streamlit/nascel sem fundo.png", "nascel sem fundo.png"]
    for l in logos:
        if os.path.exists(l): st.image(l, use_column_width=True); break
    else: st.markdown("<h1 style='color:#FF6F00;'>Nascel</h1>", unsafe_allow_html=True)
    
    st.markdown("---")

    def get_file(name):
        for p in [f".streamlit/{name}", name, f"bases/{name}"]:
            if os.path.exists(p): return p
        return None

    st.subheader("📊 Status")
    f_icms = get_file("ICMS.xlsx") or get_file("base_icms.xlsx")
    f_pc = get_file("CST_Pis_Cofins.xlsx")

    st.success("🟢 ICMS OK") if f_icms else st.error("🔴 ICMS OFF")
    st.success("🟢 PIS/COF OK") if f_pc else st.error("🔴 PIS/COF OFF")

    with st.expander("💾 GESTÃO"):
        up_i = st.file_uploader("Trocar ICMS", type=['xlsx'], key='ui')
        if up_i:
            with open("ICMS.xlsx", "wb") as f: f.write(up_i.getbuffer())
            st.rerun()
        up_p = st.file_uploader("Trocar PIS/COF", type=['xlsx'], key='up')
        if up_p:
            with open("CST_Pis_Cofins.xlsx", "wb") as f: f.write(up_p.getbuffer())
            st.rerun()

    with st.expander("📂 GABARITOS"):
        df_m = pd.DataFrame(columns=['NCM','DESC_I','CST_I','AL_I','RE_I','DESC_E','CST_E','AL_E','OBS'])
        buf = io.BytesIO()
        with pd.ExcelWriter(buf, engine='xlsxwriter') as w: df_m.to_excel(w, index=False)
        st.download_button("Gabarito ICMS", buf.getvalue(), "modelo_icms.xlsx")

# ==============================================================================
# --- 4. ÁREA CENTRAL (LAYOUT ORIGINAL) ---
# ==============================================================================
for s in [".streamlit/Sentinela.png", "Sentinela.png"]:
    if os.path.exists(s):
        col_l, col_tit, col_r = st.columns([3, 4, 3])
        with col_tit: st.image(s, use_column_width=True); break
else: st.markdown("<h1 style='text-align: center; color: #FF6F00;'>SENTINELA</h1>", unsafe_allow_html=True)

st.markdown("---")
col_ent, col_sai = st.columns(2, gap="large")

with col_ent:
    st.markdown("### 📥 1. Entradas")
    ue = st.file_uploader("📂 XMLs", type='xml', accept_multiple_files=True, key="ue")
    ae = st.file_uploader("🔍 Autenticidade Entradas", type=['xlsx', 'csv'], key="ae")

with col_sai:
    st.markdown("### 2. Saídas")
    us = st.file_uploader("📂 XMLs", type='xml', accept_multiple_files=True, key="us")
    as_ = st.file_uploader("🔍 Autenticidade Saídas", type=['xlsx', 'csv'], key="as")

# --- EXECUÇÃO COM CRIAÇÃO DE ABAS ---
st.markdown("<br>", unsafe_allow_html=True)
if st.button("🚀 EXECUTAR AUDITORIA COMPLETA", type="primary", use_container_width=True):
    if not ue and not us:
        st.warning("Carregue os arquivos.")
    else:
        with st.spinner("Analisando e gerando as abas de análise..."):
            pi = get_file("ICMS.xlsx") or get_file("base_icms.xlsx")
            pp = get_file("CST_Pis_Cofins.xlsx")
            bi = pd.read_excel(pi, dtype=str) if pi else None
            bp = pd.read_excel(pp, dtype=str) if pp else None
            
            df_e = extrair_dados_xml(ue, "Entrada")
            df_s = extrair_dados_xml(us, "Saída")
            df_total = pd.concat([df_e, df_s], ignore_index=True)
            
            # Auditoria
            df_final = realizar_auditoria_completa(df_total, bi, bp)
            
            st.success("Auditoria Finalizada!")
            st.dataframe(df_final, use_container_width=True)
            
            # --- O SEGREDO DAS ABAS ESTÁ AQUI ---
            output = io.BytesIO()
            with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
                # Aba 1
                df_final.to_excel(writer, sheet_name='RELATORIO_GERAL', index=False)
                # Aba 2 (Só Divergências)
                cond = (df_final.get('ANALISE_ICMS', '') != 'OK') | (df_final.get('ANALISE_PIS_COFINS', '') != 'OK')
                df_final[cond].to_excel(writer, sheet_name='DIVERGENCIAS', index=False)
            
            st.download_button("💾 BAIXAR RELATÓRIO COM AS ABAS", output.getvalue(), "Auditoria_Nascel.xlsx")
