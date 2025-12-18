import streamlit as st
import pandas as pd
import xml.etree.ElementTree as ET
import io
import re
import os

# --- 1. CONFIGURAÇÃO VISUAL E LAYOUT ---
st.set_page_config(
    page_title="Sentinela Fiscal Pro",
    page_icon="🛡️",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Estilo Visual (CSS)
st.markdown("""
    <style>
    .main {background-color: #f8f9fa;}
    div.stMetric {background-color: #ffffff; padding: 10px; border-radius: 5px; border: 1px solid #e0e0e0;}
    h1 {color: #1f77b4;}
    </style>
""", unsafe_allow_html=True)

st.title("🛡️ Sentinela: Auditoria Fiscal & Autenticidade")
st.markdown("---")

# --- 2. CARREGAR BASES DO SISTEMA (TIPI, PIS/COFINS) ---
@st.cache_data
def carregar_bases_sistema():
    bases = {"TIPI": {}, "PIS_COFINS": {}}
    
    # 1. TIPI (Se existir o arquivo na pasta)
    if os.path.exists("TIPI.xlsx"):
        try:
            df = pd.read_excel("TIPI.xlsx", dtype=str)
            df['NCM'] = df.iloc[:, 0].str.replace(r'\D', '', regex=True)
            df['ALIQ'] = df.iloc[:, 1].str.replace(',', '.')
            bases["TIPI"] = dict(zip(df['NCM'], df['ALIQ']))
        except: pass

    # 2. PIS COFINS (Se existir o arquivo na pasta)
    if os.path.exists("Pis_Cofins.xlsx"):
        try:
            df = pd.read_excel("Pis_Cofins.xlsx", dtype=str)
            df['NCM'] = df.iloc[:, 0].str.replace(r'\D', '', regex=True)
            bases["PIS_COFINS"] = dict(zip(df['NCM'], df.iloc[:, 2])) 
        except: pass
        
    return bases

bases_sistema = carregar_bases_sistema()

# --- 3. FUNÇÃO DE EXTRAÇÃO XML ---
def extrair_xml(arquivos, origem):
    dados = []
    
    for arq in arquivos:
        try:
            # Ler arquivo
            raw = arq.read()
            try: xml = raw.decode('utf-8')
            except: xml = raw.decode('latin-1')
            
            # Limpar Namespaces (Isso evita muitos erros de leitura)
            xml = re.sub(r' xmlns="[^"]+"', '', xml)
            xml = re.sub(r' xmlns:xsi="[^"]+"', '', xml)
            
            root = ET.fromstring(xml)
            
            # Pular eventos e resumos
            if "resNFe" in root.tag or "procEvento" in root.tag: continue
            
            inf = root.find('.//infNFe')
            if inf is None: continue
            
            chave = inf.attrib.get('Id', '')[3:]
            nat_op = root.find('.//ide/natOp').text if root.find('.//ide/natOp') is not None else ""
            emit_nome = root.find('.//emit/xNome').text if root.find('.//emit/xNome') is not None else ""
            
            dets = root.findall('.//det')
            
            for det in dets:
                prod = det.find('prod')
                imposto = det.find('imposto')
                
                # Função auxiliar para pegar valor
                def val(node, tag, is_float=False):
                    if node is None: return 0.0 if is_float else ""
                    x = node.find(tag)
                    if x is not None and x.text:
                        return float(x.text) if is_float else x.text
                    return 0.0 if is_float else ""

                item = {
                    "Origem": origem,
                    "Arquivo": arq.name,
                    "Chave": chave,
                    "Emitente": emit_nome,
                    "Natureza": nat_op,
                    "Item": det.attrib.get('nItem'),
                    "NCM": val(prod, 'NCM'),
                    "CFOP": val(prod, 'CFOP'),
                    "Valor Prod": val(prod, 'vProd', True),
                    "CST ICMS": "", "Aliq ICMS": 0.0,
                    "CST IPI": "", "Aliq IPI": 0.0,
                    "CST PIS": "", "CST COFINS": ""
                }
                
                if imposto:
                    # ICMS
                    icms = imposto.find('ICMS')
                    if icms:
                        for c in icms:
                            if c.find('CST') is not None: item['CST ICMS'] = c.find('CST').text
                            elif c.find('CSOSN') is not None: item['CST ICMS'] = c.find('CSOSN').text
                            if c.find('pICMS') is not None: item['Aliq ICMS'] = float(c.find('pICMS').text)
                    # IPI
                    ipi = imposto.find('IPI')
                    if ipi:
                        for c in ipi:
                            if c.find('CST') is not None: item['CST IPI'] = c.find('CST').text
                            if c.find('pIPI') is not None: item['Aliq IPI'] = float(c.find('pIPI').text)
                    # PIS/COFINS
                    pis = imposto.find('PIS')
                    if pis:
                        for c in pis:
                            if c.find('CST') is not None: item['CST PIS'] = c.find('CST').text
                    cof = imposto.find('COFINS')
                    if cof:
                        for c in cof:
                            if c.find('CST') is not None: item['CST COFINS'] = c.find('CST').text
                
                dados.append(item)
        except: pass
        
    return pd.DataFrame(dados)

# --- 4. SIDEBAR (OS 6 BOTÕES CORRIGIDOS) ---
with st.sidebar:
    st.image("https://cdn-icons-png.flaticon.com/512/950/950264.png", width=50)
    st.header("Central de Uploads")
    
    # 1. ENTRADAS (Keys únicas adicionadas: key="ent_...")
    with st.expander("📥 1. Entradas", expanded=True):
        up_ent_xml = st.file_uploader("XML Entradas", type='xml', accept_multiple_files=True, key="ent_xml")
        up_ent_aut = st.file_uploader("Autenticidade (Excel)", type=['xlsx', 'csv'], key="ent_aut")
        up_ent_ger = st.file_uploader("Gerencial (Regras)", type=['xlsx'], key="ent_ger") 
        
    # 2. SAÍDAS (Keys únicas adicionadas: key="sai_...")
    with st.expander("📤 2. Saídas", expanded=True):
        up_sai_xml = st.file_uploader("XML Saídas", type='xml', accept_multiple_files=True, key="sai_xml")
        up_sai_aut = st.file_uploader("Autenticidade (Excel)", type=['xlsx', 'csv'], key="sai_aut")
        up_sai_ger = st.file_uploader("Gerencial (Regras)", type=['xlsx'], key="sai_ger") 

# --- 5. LÓGICA DE PROCESSAMENTO ---

# Função para ler excel de status
def get_status_dict(file):
    if not file: return {}
    try:
        if file.name.endswith('xlsx'): df = pd.read_excel(file, dtype=str)
        else: df = pd.read_csv(file, dtype=str)
        # Limpa chave (col 0) e pega status (col 5 ou última)
        return dict(zip(df.iloc[:, 0].str.replace(r'\D', '', regex=True), df.iloc[:, -1]))
    except: return {}

# Processa XMLs
df_ent = extrair_xml(up_ent_xml, "Entrada") if up_ent_xml else pd.DataFrame()
df_sai = extrair_xml(up_sai_xml, "Saída") if up_sai_xml else pd.DataFrame()

# Lógica de Análise
def aplicar_analises(df, status_file):
    if df.empty: return df
    
    # 1. Autenticidade
    status_dict = get_status_dict(status_file)
    if status_dict:
        df['Status Sefaz'] = df['Chave'].map(status_dict).fillna("Não Localizado")
    else:
        df['Status Sefaz'] = "Arquivo Autent. Não Enviado"

    # 2. Auditoria IPI (Se TIPI existir)
    if bases_sistema["TIPI"]:
        def check_ipi(row):
            ncm = str(row['NCM'])
            aliq_xml = row['Aliq IPI']
            aliq_tipi = bases_sistema["TIPI"].get(ncm)
            if aliq_tipi is None: return "NCM fora da TIPI"
            if aliq_tipi == "NT": return "OK (NT)"
            try:
                if abs(aliq_xml - float(aliq_tipi)) > 0.1: return f"Divergente (XML: {aliq_xml}% | TIPI: {aliq_tipi}%)"
                return "OK"
            except: return "Erro Calc"
        df['Auditoria IPI'] = df.apply(check_ipi, axis=1)

    # 3. Auditoria PIS/COFINS (Se Base existir)
    if bases_sistema["PIS_COFINS"]:
        def check_pc(row):
            ncm = str(row['NCM'])
            cst_xml = str(row['CST PIS'])
            cst_esp = bases_sistema["PIS_COFINS"].get(ncm)
            if not cst_esp: return "Sem Base"
            if cst_xml != cst_esp: return f"Div: {cst_xml} | Esp: {cst_esp}"
            return "OK"
        df['Auditoria PIS/COF'] = df.apply(check_pc, axis=1)
        
    return df

# Executa as análises
df_ent_final = aplicar_analises(df_ent, up_ent_aut)
df_sai_final = aplicar_analises(df_sai, up_sai_aut)

# --- 6. EXIBIÇÃO DASHBOARD ---

if df_ent_final.empty and df_sai_final.empty:
    st.info("👋 Bem-vindo! Use a barra lateral para carregar seus XMLs e verificar a Autenticidade.")

else:
    # Abas para organizar
    tab1, tab2, tab3 = st.tabs(["📊 Visão Geral", "📥 Entradas", "📤 Saídas"])
    
    with tab1:
        st.markdown("### Resumo Executivo")
        c1, c2, c3, c4 = st.columns(4)
        
        total_ent = len(df_ent_final)
        total_sai = len(df_sai_final)
        
        # Conta erros de autenticidade (se não for Autorizado ou OK)
        err_ent = 0
        if not df_ent_final.empty and 'Status Sefaz' in df_ent_final.columns:
            err_ent = len(df_ent_final[~df_ent_final['Status Sefaz'].str.contains("Autoriz|OK", na=False, case=False)])
            
        err_sai = 0
        if not df_sai_final.empty and 'Status Sefaz' in df_sai_final.columns:
            err_sai = len(df_sai_final[~df_sai_final['Status Sefaz'].str.contains("Autoriz|OK", na=False, case=False)])

        c1.metric("Total Lidos", total_ent + total_sai)
        c2.metric("Itens Entrada", total_ent)
        c3.metric("Itens Saída", total_sai)
        c4.metric("Alertas Sefaz", err_ent + err_sai, delta_color="inverse")
        
        st.markdown("---")
        g1, g2 = st.columns(2)
        
        if not df_ent_final.empty and 'Status Sefaz' in df_ent_final.columns:
            with g1: 
                st.caption("Entradas por Status")
                st.bar_chart(df_ent_final['Status Sefaz'].value_counts())
                
        if not df_sai_final.empty and 'Status Sefaz' in df_sai_final.columns:
            with g2: 
                st.caption("Saídas por Status")
                st.bar_chart(df_sai_final['Status Sefaz'].value_counts())

    with tab2:
        st.subheader("Detalhe Entradas")
        if not df_ent_final.empty:
            st.dataframe(df_ent_final, use_container_width=True)
        else:
            st.warning("Sem dados de entrada.")

    with tab3:
        st.subheader("Detalhe Saídas")
        if not df_sai_final.empty:
            st.dataframe(df_sai_final, use_container_width=True)
        else:
            st.warning("Sem dados de saída.")

    # --- 7. EXPORTAÇÃO EXCEL ---
    st.markdown("---")
    if st.button("💾 Baixar Relatório Final (Excel)"):
        buffer = io.BytesIO()
        with pd.ExcelWriter(buffer, engine='xlsxwriter') as writer:
            if not df_ent_final.empty: 
                df_ent_final.to_excel(writer, index=False, sheet_name='Entradas')
            if not df_sai_final.empty: 
                df_sai_final.to_excel(writer, index=False, sheet_name='Saídas')
            
        st.download_button(
            label="📥 Clique Aqui para Download",
            data=buffer.getvalue(),
            file_name="Relatorio_Sentinela_Completo.xlsx",
            mime="application/vnd.ms-excel"
        )
