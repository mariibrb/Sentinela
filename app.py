import streamlit as st
import pandas as pd
import xml.etree.ElementTree as ET
import io
import re
import os

# --- 1. CONFIGURAÇÃO VISUAL NASCEL (Cinza & Laranja & Fofo) ---
st.set_page_config(
    page_title="Nascel | Auditoria",
    page_icon="🧡",
    layout="wide",
    initial_sidebar_state="collapsed"
)

# CSS PERSONALIZADO (Mantendo o estilo "fofo" aprovado)
st.markdown("""
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Quicksand:wght@400;600;700&display=swap');

    html, body, [class*="css"] {
        font-family: 'Quicksand', sans-serif;
    }

    /* Fundo Geral - Cinza Suave */
    .stApp {
        background-color: #F7F7F7;
    }

    /* Títulos em Laranja Nascel */
    h1, h2, h3, h4 {
        color: #FF6F00 !important;
        font-weight: 700;
    }

    /* Cards de Upload (O Meio da Tela) */
    div[data-testid="stVerticalBlock"] > div[data-testid="stVerticalBlock"] {
        background-color: white;
        padding: 20px;
        border-radius: 20px;
        box-shadow: 0 4px 15px rgba(0,0,0,0.05);
    }

    /* File Uploader "Fofo" */
    .stFileUploader {
        padding: 10px;
        border: 2px dashed #FFCC80;
        border-radius: 15px;
        text-align: center;
    }

    /* Botões - Laranjas e Redondinhos */
    .stButton>button {
        background-color: #FF6F00;
        color: white;
        border-radius: 25px;
        border: none;
        font-weight: bold;
        padding: 10px 30px;
        width: 100%;
    }
    .stButton>button:hover {
        background-color: #E65100;
    }
    
    /* Métricas */
    div[data-testid="metric-container"] {
        border-left: 5px solid #FF6F00;
        background-color: #FFF3E0;
        border-radius: 10px;
    }
    </style>
""", unsafe_allow_html=True)

# --- 2. SIDEBAR (AJUSTE 1: N Maiúsculo) ---
with st.sidebar:
    if os.path.exists("logo_nascel.png"):
        st.image("logo_nascel.png", use_column_width=True)
    else:
        # AJUSTE AQUI: N maiúsculo
        st.markdown("<h1 style='color:#FF6F00; text-align:center;'>Nascel</h1>", unsafe_allow_html=True)
    
    st.markdown("---")
    st.info("💡 **Dica:** Carregue os arquivos nas caixas ao centro para iniciar.")

# --- 3. ÁREA PRINCIPAL (AJUSTE 2: Imagem Sentinela) ---

# Tenta carregar a imagem banner, se não tiver, usa um título texto como fallback
if os.path.exists("sentinela_banner.png"):
    # Centralizando a imagem
    col_spacer1, col_img, col_spacer2 = st.columns([1, 4, 1])
    with col_img:
        st.image("sentinela_banner.png", use_column_width=True)
else:
    # Fallback se a imagem não estiver na pasta
    st.markdown("<h1 style='text-align: center; color: #FF6F00; font-size: 3em;'>SENTINELA</h1>", unsafe_allow_html=True)
    st.markdown("<h3 style='text-align: center; color: #666;'>Sistema de Auditoria Fiscal Nascel</h3>", unsafe_allow_html=True)

st.markdown("<br>", unsafe_allow_html=True) # Espaço

# --- ÁREA DE UPLOAD (OS 6 BOTÕES NO MEIO) ---
col_ent, col_sai = st.columns(2, gap="large")

with col_ent:
    st.markdown("### 📥 1. Entradas")
    st.markdown("---")
    up_ent_xml = st.file_uploader("📂 XMLs de Notas Fiscais", type='xml', accept_multiple_files=True, key="ent_xml")
    up_ent_aut = st.file_uploader("🔍 Relatório Autenticidade (Sefaz)", type=['xlsx', 'csv'], key="ent_aut")
    up_ent_ger = st.file_uploader("⚙️ Regras Gerenciais (Opcional)", type=['xlsx'], key="ent_ger")

with col_sai:
    st.markdown("### 📤 2. Saídas")
    st.markdown("---")
    up_sai_xml = st.file_uploader("📂 XMLs de Notas Fiscais", type='xml', accept_multiple_files=True, key="sai_xml")
    up_sai_aut = st.file_uploader("🔍 Relatório Autenticidade (Sefaz)", type=['xlsx', 'csv'], key="sai_aut")
    up_sai_ger = st.file_uploader("⚙️ Regras Gerenciais (Opcional)", type=['xlsx'], key="sai_ger")

# --- 4. LÓGICA DO SISTEMA (CÓDIGO ORIGINAL PERFEITO) ---

# Carregar Bases TIPI/PIS (Invisível)
@st.cache_data
def carregar_bases():
    bases = {"TIPI": {}, "PC": {}}
    if os.path.exists("TIPI.xlsx"):
        try:
            d = pd.read_excel("TIPI.xlsx", dtype=str)
            bases["TIPI"] = dict(zip(d.iloc[:,0].str.replace(r'\D','',regex=True), d.iloc[:,1].str.replace(',','.')))
        except: pass
    return bases
bases = carregar_bases()

# Função Extração XML
def processar_xml(files, tipo):
    if not files: return pd.DataFrame()
    data = []
    for f in files:
        try:
            raw = f.read()
            try: txt = raw.decode('utf-8')
            except: txt = raw.decode('latin-1')
            txt = re.sub(r' xmlns="[^"]+"', '', txt)
            root = ET.fromstring(txt)
            
            if 'resNFe' in root.tag or 'procEvento' in root.tag: continue
            inf = root.find('.//infNFe')
            if inf is None: continue
            
            chave = inf.attrib.get('Id','')[3:]
            dets = root.findall('.//det')
            
            for det in dets:
                prod = det.find('prod')
                imp = det.find('imposto')
                
                # Helper valor
                def v(n, t, fl=False):
                    if n is None: return 0.0 if fl else ""
                    x = n.find(t)
                    return (float(x.text) if fl else x.text) if x is not None else (0.0 if fl else "")

                row = {
                    "Origem": tipo,
                    "Arquivo": f.name,
                    "Chave": chave,
                    "NCM": v(prod, 'NCM'),
                    "CFOP": v(prod, 'CFOP'),
                    "Valor": v(prod, 'vProd', True),
                    "CST_ICMS": "", "Aliq_ICMS": 0.0, "Aliq_IPI": 0.0
                }
                
                if imp:
                    # ICMS
                    icms = imp.find('ICMS')
                    if icms:
                        for c in icms:
                            if c.find('CST') is not None: row['CST_ICMS'] = c.find('CST').text
                            elif c.find('CSOSN') is not None: row['CST_ICMS'] = c.find('CSOSN').text
                            if c.find('pICMS') is not None: row['Aliq_ICMS'] = float(c.find('pICMS').text)
                    # IPI
                    ipi = imp.find('IPI')
                    if ipi:
                        for c in ipi:
                            if c.find('pIPI') is not None: row['Aliq_IPI'] = float(c.find('pIPI').text)
                            
                data.append(row)
        except: pass
    return pd.DataFrame(data)

# Função Autenticidade
def cruzar_status(df, file):
    if df.empty: return df
    if not file: 
        df['Status_Sefaz'] = "Não Verificado"
        return df
    try:
        if file.name.endswith('xlsx'): s = pd.read_excel(file, dtype=str)
        else: s = pd.read_csv(file, dtype=str)
        mapping = dict(zip(s.iloc[:,0].str.replace(r'\D','',regex=True), s.iloc[:,-1]))
        df['Status_Sefaz'] = df['Chave'].map(mapping).fillna("Não Localizado")
    except:
        df['Status_Sefaz'] = "Erro Arquivo Status"
    return df

# Função Auditoria TIPI
def auditar_ipi(df):
    if df.empty or not bases["TIPI"]: return df
    def check(row):
        esp = bases["TIPI"].get(str(row['NCM']))
        if not esp: return "NCM Off"
        if esp == 'NT': return "OK"
        try: return "OK" if abs(row['Aliq_IPI'] - float(esp)) < 0.1 else f"Div (XML:{row['Aliq_IPI']} | TIPI:{esp})"
        except: return "Erro"
    df['Auditoria_IPI'] = df.apply(check, axis=1)
    return df

# --- 5. EXIBIÇÃO DOS RESULTADOS ---

# Processamento
df_e = cruzar_status(processar_xml(up_ent_xml, "Entrada"), up_ent_aut)
df_s = auditar_ipi(cruzar_status(processar_xml(up_sai_xml, "Saída"), up_sai_aut))

st.markdown("---")

if df_e.empty and df_s.empty:
    st.info("👆 Aguardando arquivos... Carregue os XMLs e relatórios nas caixas acima.")
else:
    st.markdown("## 📊 Resultados da Análise")
    
    tab1, tab2, tab3 = st.tabs(["Visão Geral", "Entradas", "Saídas"])
    
    with tab1:
        c1, c2, c3 = st.columns(3)
        c1.metric("Total Notas", len(df_e) + len(df_s))
        
        err_e = len(df_e[~df_e['Status_Sefaz'].str.contains('Autoriz|OK|Não Verif', na=False, case=False)]) if not df_e.empty else 0
        err_s = len(df_s[~df_s['Status_Sefaz'].str.contains('Autoriz|OK|Não Verif', na=False, case=False)]) if not df_s.empty else 0
        
        c2.metric("Alertas Sefaz", err_e + err_s)
        
        div_ipi = len(df_s[df_s['Auditoria_IPI'].str.contains('Div', na=False)]) if not df_s.empty and 'Auditoria_IPI' in df_s.columns else 0
        c3.metric("Divergências IPI", div_ipi)

    with tab2:
        if not df_e.empty: st.dataframe(df_e, use_container_width=True)
    
    with tab3:
        if not df_s.empty: st.dataframe(df_s, use_container_width=True)
        
    # Botão Download Gigante e Laranja
    st.markdown("<br>", unsafe_allow_html=True)
    col_dl, _ = st.columns([1,2])
    with col_dl:
        buffer = io.BytesIO()
        with pd.ExcelWriter(buffer, engine='xlsxwriter') as writer:
            if not df_e.empty: df_e.to_excel(writer, sheet_name='Entradas', index=False)
            if not df_s.empty: df_s.to_excel(writer, sheet_name='Saidas', index=False)
            
        st.download_button(
            label="💾 BAIXAR RELATÓRIO COMPLETO",
            data=buffer.getvalue(),
            file_name="Relatorio_Nascel_Auditoria.xlsx",
            mime="application/vnd.ms-excel"
        )
