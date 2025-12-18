import streamlit as st
import pandas as pd
import xml.etree.ElementTree as ET
import io
import re
import os

# --- 1. CONFIGURAÇÃO VISUAL (IDENTIDADE NASCEL) ---
st.set_page_config(
    page_title="Nascel | Auditoria",
    page_icon="🧡",
    layout="wide",
    initial_sidebar_state="expanded"
)

# CSS PERSONALIZADO (RESTABELECIDO)
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
# --- 2. MOTORES DE CÁLCULO E EXTRAÇÃO (O MECANISMO ROBUSTO) ---
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
            
            # Dados da Nota (Emitente/Destinatário para DIFAL se necessário)
            dest = inf.find('dest')
            uf_dest = dest.find('UF').text if dest is not None and dest.find('UF') is not None else ""
            
            for det in root.findall('.//det'):
                prod = det.find('prod')
                imp = det.find('imposto')
                
                row = {
                    'Fluxo': fluxo, 'Chave': chave, 'Arquivo': f.name,
                    'NCM': prod.find('NCM').text if prod.find('NCM') is not None else "",
                    'CFOP': prod.find('CFOP').text if prod.find('CFOP') is not None else "",
                    'Descricao': prod.find('xProd').text if prod.find('xProd') is not None else "",
                    'Valor_Prod': float(prod.find('vProd').text) if prod.find('vProd') is not None else 0.0,
                    'CST_ICMS_NF': "", 'Aliq_ICMS_NF': 0.0, 'Vl_ICMS_NF': 0.0,
                    'Aliq_IPI_NF': 0.0, 'CST_PIS_NF': "", 'CST_COFINS_NF': "", 'UF_Dest': uf_dest
                }
                
                # Extração Técnica de Impostos
                if imp is not None:
                    # ICMS
                    icms = imp.find('.//ICMS')
                    if icms is not None:
                        for c in icms:
                            node = c.find('CST') or c.find('CSOSN')
                            if node is not None: row['CST_ICMS_NF'] = node.text
                            if c.find('pICMS') is not None: row['Aliq_ICMS_NF'] = float(c.find('pICMS').text)
                            if c.find('vICMS') is not None: row['Vl_ICMS_NF'] = float(c.find('vICMS').text)
                    
                    # IPI
                    ipi = imp.find('.//IPI')
                    if ipi is not None:
                        p_ipi = ipi.find('.//pIPI')
                        if p_ipi is not None: row['Aliq_IPI_NF'] = float(p_ipi.text)
                    
                    # PIS/COFINS
                    pis = imp.find('.//PIS')
                    if pis is not None:
                        c_pis = pis.find('.//CST')
                        if c_pis is not None: row['CST_PIS_NF'] = c_pis.text
                    
                    cof = imp.find('.//COFINS')
                    if cof is not None:
                        c_cof = cof.find('.//CST')
                        if c_cof is not None: row['CST_COFINS_NF'] = c_cof.text
                        
                data.append(row)
        except: continue
    return pd.DataFrame(data)

def realizar_auditoria_completa(df, b_icms, b_pc, b_tipi):
    if df.empty: return df
    df['NCM_L'] = df['NCM'].str.replace(r'\D', '', regex=True).str.zfill(8)

    # 1. AUDITORIA ICMS (Regra 5 vs 6 usando Planilha ICMS.xlsx)
    if b_icms is not None and len(b_icms.columns) >= 7:
        # Colunas: 0=NCM, 2=CST Interno, 4=Aliq Interna, 6=CST Externo
        rules_i = b_icms.iloc[:, [0, 2, 4, 6]].copy()
        rules_i.columns = ['NCM_R', 'CST_INT_R', 'ALIQ_INT_R', 'CST_EXT_R']
        rules_i['NCM_R'] = rules_i['NCM_R'].astype(str).str.replace(r'\D', '', regex=True).str.zfill(8)
        df = pd.merge(df, rules_i, left_on='NCM_L', right_on='NCM_R', how='left')
        
        def audit_icms(r):
            if pd.isna(r['NCM_R']): return "NCM NÃO CADASTRADO"
            cfop = str(r['CFOP'])
            # Interno (5) ou Externo (6)
            esp_cst = str(r['CST_INT_R']) if cfop.startswith('5') else str(r['CST_EXT_R'])
            esp_cst = str(esp_cst).split('.')[0].zfill(2)
            nf_cst = str(r['CST_ICMS_NF']).zfill(2)
            
            if nf_cst != esp_cst: return f"ERRO CST (Nota: {nf_cst} | Esp: {esp_cst})"
            return "OK"
        df['ANALISE_ICMS'] = df.apply(audit_icms, axis=1)

    # 2. AUDITORIA PIS/COFINS
    if b_pc is not None and len(b_pc.columns) >= 3:
        rules_p = b_pc.iloc[:, [0, 1, 2]].copy()
        rules_p.columns = ['NCM_P', 'CST_E_P', 'CST_S_P']
        rules_p['NCM_P'] = rules_p['NCM_P'].astype(str).str.replace(r'\D', '', regex=True).str.zfill(8)
        df = pd.merge(df, rules_p, left_on='NCM_L', right_on='NCM_P', how='left')
        
        def audit_pc(r):
            if pd.isna(r['NCM_P']): return "NCM NÃO CADASTRADO"
            cfop = str(r['CFOP'])
            # Entrada (1,2,3) vs Saída (5,6,7)
            esp = str(r['CST_E_P']) if cfop[0] in '123' else str(r['CST_S_P'])
            esp = str(esp).split('.')[0].zfill(2)
            return "OK" if str(r['CST_PIS_NF']).zfill(2) == esp else f"ERRO (Esp: {esp})"
        df['ANALISE_PIS_COFINS'] = df.apply(audit_pc, axis=1)

    # 3. AUDITORIA IPI (TIPI)
    if b_tipi is not None:
        rules_t = b_tipi.iloc[:, [0, 1]].copy()
        rules_t.columns = ['NCM_T', 'ALIQ_T']
        rules_t['NCM_T'] = rules_t['NCM_T'].astype(str).str.replace(r'\D', '', regex=True).str.zfill(8)
        df = pd.merge(df, rules_t, left_on='NCM_L', right_on='NCM_T', how='left')
        df['ANALISE_IPI'] = df.apply(lambda r: "OK" if pd.isna(r['ALIQ_T']) or abs(r['Aliq_IPI_NF'] - float(str(r['ALIQ_T']).replace(',','.'))) < 0.1 else "DIVERGENTE", axis=1)

    return df

# ==============================================================================
# --- 3. SIDEBAR E GESTÃO DE ARQUIVOS ---
# ==============================================================================

with st.sidebar:
    # Logo Nascel com fallback
    logos = [".streamlit/nascel sem fundo.png", "nascel sem fundo.png"]
    for l in logos:
        if os.path.exists(l): st.image(l, use_column_width=True); break
    else: st.markdown("<h1 style='color:#FF6F00; text-align:center;'>Nascel</h1>", unsafe_allow_html=True)
    
    st.markdown("---")

    def get_f(n):
        for p in [f".streamlit/{n}", n, f"bases/{n}"]:
            if os.path.exists(p): return p
        return None

    # Status Dinâmico
    st.subheader("📊 Status das Bases")
    p_i = get_f("ICMS.xlsx") or get_f("base_icms.xlsx")
    p_p = get_f("CST_Pis_Cofins.xlsx")
    p_t = get_f("tipi.xlsx")

    if p_i: st.success("🟢 ICMS OK")
    else: st.error("🔴 ICMS Ausente")
    if p_p: st.success("🟢 PIS/COF OK")
    else: st.error("🔴 PIS/COF Ausente")
    if p_t: st.success("🟢 TIPI OK")

    st.markdown("---")
    with st.expander("💾 GERENCIAR BASES"):
        up_i = st.file_uploader("Subir ICMS (A-I)", type=['xlsx'], key='ui')
        if up_i:
            with open("ICMS.xlsx", "wb") as f: f.write(up_i.getbuffer())
            st.rerun()
        up_pc = st.file_uploader("Subir PIS/COF", type=['xlsx'], key='upc')
        if up_pc:
            with open("CST_Pis_Cofins.xlsx", "wb") as f: f.write(up_pc.getbuffer())
            st.rerun()

    with st.expander("📂 GABARITOS"):
        # Gabarito ICMS 9 Colunas A-I
        df_micms = pd.DataFrame(columns=['NCM','DESC_INT','CST_INT','ALIQ_INT','RED_INT','DESC_EXT','CST_EXT','ALIQ_EXT','OBS'])
        buf_i = io.BytesIO()
        with pd.ExcelWriter(buf_i, engine='xlsxwriter') as w: df_micms.to_excel(w, index=False)
        st.download_button("📥 Gabarito ICMS", buf_i.getvalue(), "modelo_icms.xlsx")
        
        df_mpc = pd.DataFrame({'NCM': ['00000000'], 'CST_ENT': ['50'], 'CST_SAI': ['01']})
        buf_p = io.BytesIO()
        with pd.ExcelWriter(buf_p, engine='xlsxwriter') as w: df_mpc.to_excel(w, index=False)
        st.download_button("📥 Gabarito PIS/COF", buf_p.getvalue(), "modelo_pc.xlsx")

# ==============================================================================
# --- 4. ÁREA CENTRAL (LAYOUT ORIGINAL PRESERVADO) ---
# ==============================================================================

# Logo Sentinela Central
for s in [".streamlit/Sentinela.png", "Sentinela.png"]:
    if os.path.exists(s):
        col_l, col_tit, col_r = st.columns([3, 4, 3])
        with col_tit: st.image(s, use_column_width=True); break
else:
    st.markdown("<h1 style='text-align: center; color: #FF6F00;'>SENTINELA</h1>", unsafe_allow_html=True)

st.markdown("---")

# Duas Colunas (Layout que você pediu para NÃO mudar)
col_ent, col_sai = st.columns(2, gap="large")

with col_ent:
    st.markdown("### 📥 1. Entradas")
    st.markdown("---")
    up_ent_xml = st.file_uploader("📂 XMLs", type='xml', accept_multiple_files=True, key="ent_xml")
    up_ent_aut = st.file_uploader("🔍 Autenticidade Entradas", type=['xlsx', 'csv'], key="ent_aut")

with col_sai:
    st.markdown("### 📤 2. Saídas")
    st.markdown("---")
    up_sai_xml = st.file_uploader("📂 XMLs", type='xml', accept_multiple_files=True, key="sai_xml")
    up_sai_aut = st.file_uploader("🔍 Autenticidade Saídas", type=['xlsx', 'csv'], key="sai_aut")

# --- EXECUÇÃO E RESULTADOS ---
st.markdown("<br>", unsafe_allow_html=True)
if st.button("🚀 EXECUTAR AUDITORIA COMPLETA", type="primary", use_container_width=True):
    if not up_ent_xml and not up_sai_xml:
        st.warning("Aguardando upload dos arquivos XML.")
    else:
        with st.spinner("Extraindo e auditando tributos (ICMS, IPI, PIS, COFINS)..."):
            # Carregamento de bases
            bi = pd.read_excel(p_i, dtype=str) if p_i else None
            bp = pd.read_excel(p_p, dtype=str) if p_p else None
            bt = pd.read_excel(p_t, dtype=str) if p_t else None
            
            # Extração
            df_e = extrair_dados_xml(up_ent_xml, "Entrada")
            df_s = extrair_dados_xml(up_sai_xml, "Saída")
            df_total = pd.concat([df_e, df_s], ignore_index=True)
            
            # Auditoria Consolidada
            df_final = realizar_auditoria_completa(df_total, bi, bp, bt)
            
            st.success("Análise Finalizada com Sucesso!")
            st.dataframe(df_final, use_container_width=True)
            
            # GERADOR DE RELATÓRIO COM ABAS
            output = io.BytesIO()
            with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
                # Aba 1: Geral
                df_final.to_excel(writer, sheet_name='RELATORIO_GERAL', index=False)
                
                # Abas de Erros Específicas
                if 'ANALISE_ICMS' in df_final:
                    df_final[df_final['ANALISE_ICMS'] != 'OK'].to_excel(writer, sheet_name='ERROS_ICMS', index=False)
                if 'ANALISE_PIS_COFINS' in df_final:
                    df_final[df_final['ANALISE_PIS_COFINS'] != 'OK'].to_excel(writer, sheet_name='ERROS_PIS_COFINS', index=False)
            
            st.download_button(
                label="💾 BAIXAR RELATÓRIO COMPLETO (COM ABAS)",
                data=output.getvalue(),
                file_name="Relatorio_Auditoria_Nascel.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            )
