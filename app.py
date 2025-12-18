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

# CSS Customizado para dar um visual mais "App"
st.markdown("""
    <style>
    .main {background-color: #f8f9fa;}
    .stMetric {background-color: #ffffff; padding: 10px; border-radius: 5px; border: 1px solid #e0e0e0;}
    h1 {color: #1f77b4;}
    h2, h3 {color: #444;}
    </style>
""", unsafe_allow_html=True)

st.title("🛡️ Sentinela: Auditoria Fiscal Inteligente")
st.markdown("---")

# --- 2. CARREGAR BASES PADRÃO (TIPI, PIS/COFINS) ---
@st.cache_data
def carregar_bases_sistema():
    # Tenta carregar as tabelas "Mestres" do sistema (não as gerenciais do usuário)
    bases = {"TIPI": {}, "PIS_COFINS": {}, "TRIBUT": {}}
    
    # 1. TIPI
    if os.path.exists("TIPI.xlsx"):
        try:
            df = pd.read_excel("TIPI.xlsx", dtype=str)
            # Limpa NCM e Alíquota
            df['NCM'] = df.iloc[:, 0].str.replace(r'\D', '', regex=True)
            df['ALIQ'] = df.iloc[:, 1].str.replace(',', '.')
            bases["TIPI"] = dict(zip(df['NCM'], df['ALIQ']))
        except: pass

    # 2. PIS COFINS
    if os.path.exists("Pis_Cofins.xlsx"):
        try:
            df = pd.read_excel("Pis_Cofins.xlsx", dtype=str)
            df['NCM'] = df.iloc[:, 0].str.replace(r'\D', '', regex=True)
            bases["PIS_COFINS"] = dict(zip(df['NCM'], df.iloc[:, 2])) # NCM -> CST Saída
        except: pass
        
    return bases

bases_sistema = carregar_bases_sistema()

# --- 3. FUNÇÃO DE EXTRAÇÃO XML (CORE) ---
def extrair_xml(arquivos, origem):
    dados = []
    
    for arq in arquivos:
        try:
            # Tratamento de encoding e namespaces
            raw = arq.read()
            try: xml = raw.decode('utf-8')
            except: xml = raw.decode('latin-1')
            
            # Limpeza radical de namespaces
            xml = re.sub(r' xmlns="[^"]+"', '', xml)
            xml = re.sub(r' xmlns:xsi="[^"]+"', '', xml)
            
            root = ET.fromstring(xml)
            
            # Filtros
            if "resNFe" in root.tag or "procEvento" in root.tag: continue
            
            inf = root.find('.//infNFe')
            if inf is None: continue
            
            chave = inf.attrib.get('Id', '')[3:]
            nat_op = root.find('.//ide/natOp').text if root.find('.//ide/natOp') is not None else ""
            
            dets = root.findall('.//det')
            
            for det in dets:
                prod = det.find('prod')
                imposto = det.find('imposto')
                
                # Helpers
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

# --- 4. SIDEBAR (OS 6 BOTÕES) ---
with st.sidebar:
    st.image("https://cdn-icons-png.flaticon.com/512/950/950264.png", width=50)
    st.header("Central de Uploads")
    
    with st.expander("📥 1. Entradas", expanded=True):
        up_ent_xml = st.file_uploader("XML Entradas", type='xml', accept_multiple_files=True)
        up_ent_aut = st.file_uploader("Autenticidade (Excel)", type=['xlsx', 'csv'])
        up_ent_ger = st.file_uploader("Gerencial (Regras)", type=['xlsx']) # Botão 3
        
    with st.expander("📤 2. Saídas", expanded=True):
        up_sai_xml = st.file_uploader("XML Saídas", type='xml', accept_multiple_files=True)
        up_sai_aut = st.file_uploader("Autenticidade (Excel)", type=['xlsx', 'csv'])
        up_sai_ger = st.file_uploader("Gerencial (Regras)", type=['xlsx']) # Botão 6

# --- 5. PROCESSAMENTO E LÓGICA ---

# Função para carregar status
def get_status_dict(file):
    if not file: return {}
    try:
        if file.name.endswith('xlsx'): df = pd.read_excel(file, dtype=str)
        else: df = pd.read_csv(file, dtype=str)
        return dict(zip(df.iloc[:, 0].str.replace(r'\D', '', regex=True), df.iloc[:, -1]))
    except: return {}

# Processa DataFrames
df_ent = extrair_xml(up_ent_xml, "Entrada") if up_ent_xml else pd.DataFrame()
df_sai = extrair_xml(up_sai_xml, "Saída") if up_sai_xml else pd.DataFrame()

# Lógica de Análise (Aplica se houver dados)
def aplicar_analises(df, status_file, tipo):
    if df.empty: return df
    
    # 1. Autenticidade
    status_dict = get_status_dict(status_file)
    if status_dict:
        df['Status Sefaz'] = df['Chave'].map(status_dict).fillna("Não Localizado")
    else:
        df['Status Sefaz'] = "Arquivo de Status não enviado"

    # 2. Auditoria Tributária (Usando bases do sistema, não as gerenciais do usuário)
    # IPI
    if bases_sistema["TIPI"]:
        def check_ipi(row):
            ncm = str(row['NCM'])
            aliq_xml = row['Aliq IPI']
            aliq_tipi = bases_sistema["TIPI"].get(ncm)
            
            if aliq_tipi is None: return "NCM não na TIPI"
            if aliq_tipi == "NT": return "OK (NT)"
            try:
                if abs(aliq_xml - float(aliq_tipi)) > 0.1:
                    return f"Divergente (XML: {aliq_xml}% | TIPI: {aliq_tipi}%)"
                return "OK"
            except: return "Erro leitura TIPI"
        df['Auditoria IPI'] = df.apply(check_ipi, axis=1)

    # PIS COFINS
    if bases_sistema["PIS_COFINS"]:
        def check_pc(row):
            ncm = str(row['NCM'])
            cst_xml = str(row['CST PIS'])
            cst_esp = bases_sistema["PIS_COFINS"].get(ncm)
            
            if not cst_esp: return "Sem Base"
            if cst_xml != cst_esp: return f"Divergente (XML: {cst_xml} | Esp: {cst_esp})"
            return "OK"
        df['Auditoria PIS/COF'] = df.apply(check_pc, axis=1)
        
    return df

# Executa análises
df_ent_final = aplicar_analises(df_ent, up_ent_aut, "Entrada")
df_sai_final = aplicar_analises(df_sai, up_sai_aut, "Saída")

# --- 6. DISPLAY DASHBOARD (VISUAL MELHORADO) ---

if df_ent_final.empty and df_sai_final.empty:
    st.info("👋 Olá! Utilize o menu lateral para carregar seus arquivos XML e de Autenticidade.")
else:
    # Criação das Abas
    tab1, tab2, tab3 = st.tabs(["📊 Dashboard Gerencial", "📥 Detalhe Entradas", "📤 Detalhe Saídas"])
    
    with tab1:
        st.markdown("### Resumo da Operação")
        c1, c2, c3, c4 = st.columns(4)
        
        total_ent = len(df_ent_final)
        total_sai = len(df_sai_final)
        
        # Contagem de Erros de Autenticidade
        err_auth_e = len(df_ent_final[~df_ent_final['Status Sefaz'].str.contains("Autoriz|OK", na=False, case=False)]) if not df_ent_final.empty else 0
        err_auth_s = len(df_sai_final[~df_sai_final['Status Sefaz'].str.contains("Autoriz|OK", na=False, case=False)]) if not df_sai_final.empty else 0
        
        c1.metric("Total XML Lidos", total_ent + total_sai)
        c2.metric("Itens de Entrada", total_ent)
        c3.metric("Itens de Saída", total_sai)
        c4.metric("Alertas Autenticidade", err_auth_e + err_auth_s, delta_color="inverse")
        
        st.markdown("---")
        
        # Gráficos rápidos de status
        col_g1, col_g2 = st.columns(2)
        if not df_ent_final.empty and 'Status Sefaz' in df_ent_final.columns:
            with col_g1:
                st.caption("Status Sefaz - Entradas")
                st.bar_chart(df_ent_final['Status Sefaz'].value_counts())
        
        if not df_sai_final.empty and 'Status Sefaz' in df_sai_final.columns:
            with col_g2:
                st.caption("Status Sefaz - Saídas")
                st.bar_chart(df_sai_final['Status Sefaz'].value_counts())

    with tab2:
        st.markdown("### 📥 Auditoria de Entradas")
        if not df_ent_final.empty:
            # Filtro interativo
            filtro = st.radio("Filtrar Entradas por:", ["Tudo", "Apenas Problemas Autenticidade"], horizontal=True, key="f1")
            
            df_show = df_ent_final.copy()
            if filtro == "Apenas Problemas Autenticidade":
                df_show = df_show[~df_show['Status Sefaz'].str.contains("Autoriz|OK", na=False, case=False)]
            
            st.dataframe(df_show, use_container_width=True)
        else:
            st.warning("Nenhum dado de entrada carregado.")

    with tab3:
        st.markdown("### 📤 Auditoria de Saídas")
        if not df_sai_final.empty:
            filtro_s = st.radio("Filtrar Saídas por:", ["Tudo", "Divergência Tributária", "Problemas Autenticidade"], horizontal=True, key="f2")
            
            df_show_s = df_sai_final.copy()
            if filtro_s == "Problemas Autenticidade":
                df_show_s = df_show_s[~df_show_s['Status Sefaz'].str.contains("Autoriz|OK", na=False, case=False)]
            elif filtro_s == "Divergência Tributária":
                # Verifica se as colunas existem antes de filtrar
                cols_err = [c for c in ['Auditoria IPI', 'Auditoria PIS/COF'] if c in df_show_s.columns]
                if cols_err:
                    mask = df_show_s[cols_err].apply(lambda x: x.str.contains('Divergente', na=False)).any(axis=1)
                    df_show_s = df_show_s[mask]
            
            st.dataframe(df_show_s, use_container_width=True)
        else:
            st.warning("Nenhum dado de saída carregado.")

    # --- 7. EXPORTAÇÃO ---
    st.markdown("### 💾 Exportar Resultados")
    if st.button("Gerar Relatório Excel Completo"):
        buffer = io.BytesIO()
        with pd.ExcelWriter(buffer, engine='xlsxwriter') as writer:
            if not df_ent_final.empty: df_ent_final.to_excel(writer, index=False, sheet_name='Entradas')
            if not df_sai_final.empty: df_sai_final.to_excel(writer, index=False, sheet_name='Saídas')
            
        st.download_button(
            label="📥 Clique para Baixar Excel",
            data=buffer.getvalue(),
            file_name="Relatorio_Sentinela_Pro.xlsx",
            mime="application/vnd.ms-excel"
        )
