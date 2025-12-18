import streamlit as st
import pandas as pd
import xml.etree.ElementTree as ET
import io
import re
import os

# --- 1. CONFIGURAÇÃO ---
st.set_page_config(page_title="Sentinela - Nascel", page_icon="🛡️", layout="wide")

# --- 2. CSS (VISUAL NASCEL) ---
st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;600;700&display=swap');
    html, body, [class*="css"] { font-family: 'Inter', sans-serif; color: #333; }
    
    .main-title { font-size: 2.5rem; font-weight: 700; color: #555; margin-bottom: 0; }
    .sub-title { font-size: 1rem; color: #FF8C00; font-weight: 600; margin-bottom: 30px; }
    
    /* Cards de Upload */
    .feature-card {
        background-color: white; padding: 20px; border-radius: 12px;
        border: 1px solid #E0E0E0; text-align: center; height: 100%;
        box-shadow: 0 4px 6px rgba(0,0,0,0.05); transition: all 0.3s;
    }
    .feature-card:hover { transform: translateY(-3px); border-color: #FF8C00; box-shadow: 0 8px 15px rgba(255, 140, 0, 0.15); }
    .card-icon { font-size: 2rem; display: block; margin-bottom: 10px; }
    
    /* Botão Principal */
    .stButton button { width: 100%; height: 3.5em; font-size: 1.1em; border-radius: 8px; font-weight: 700; }
    
    /* Uploaders */
    [data-testid='stFileUploader'] section { background-color: #FFF8F0; border: 1px dashed #FF8C00; }
</style>
""", unsafe_allow_html=True)

# --- 3. CARREGAMENTO DE BASES (REGRAS FISCAIS) ---
@st.cache_data
def carregar_bases():
    # Tenta achar os arquivos na raiz ou na pasta .streamlit
    def find(name):
        if os.path.exists(name): return name
        if os.path.exists(f".streamlit/{name}"): return f".streamlit/{name}"
        return None

    df_tipi, df_pc = pd.DataFrame(), pd.DataFrame()
    
    # TIPI
    path_tipi = find("tipi.xlsx") or find("TIPI.xlsx")
    if path_tipi:
        try:
            raw = pd.read_excel(path_tipi, dtype=str)
            df_tipi = raw.iloc[:, [0, 1]].copy()
            df_tipi.columns = ['NCM', 'ALIQ']
            df_tipi['NCM'] = df_tipi['NCM'].str.replace(r'\D', '', regex=True).str.zfill(8)
            df_tipi['ALIQ'] = df_tipi['ALIQ'].str.upper().replace('NT', '0').str.strip().str.replace(',', '.')
            df_tipi = dict(zip(df_tipi['NCM'], df_tipi['ALIQ']))
        except: pass

    # PIS/COFINS
    path_pc = find("Pis_Cofins.xlsx") or find("CST_Pis_Cofins.xlsx")
    if path_pc:
        try:
            raw = pd.read_excel(path_pc, dtype=str)
            # Assume col 0: NCM, col 2: CST Saída (ajuste se necessário)
            if len(raw.columns) >= 3:
                df_pc = raw.iloc[:, [0, 2]].copy()
                df_pc.columns = ['NCM', 'CST_SAI']
                df_pc['NCM'] = df_pc['NCM'].str.replace(r'\D', '', regex=True).str.zfill(8)
                df_pc['CST_SAI'] = df_pc['CST_SAI'].str.replace(r'\D', '', regex=True).str.zfill(2)
                df_pc = dict(zip(df_pc['NCM'], df_pc['CST_SAI']))
        except: pass

    return df_tipi, df_pc

map_tipi, map_pc = carregar_bases()

# --- 4. MOTOR DE EXTRAÇÃO XML (SENTINELA) ---
def processar_xmls(arquivos):
    ns = {'nfe': 'http://www.portalfiscal.inf.br/nfe'}
    dados = []
    
    for arquivo in arquivos:
        try:
            arquivo.seek(0)
            content = arquivo.read()
            try: xml_str = content.decode('utf-8')
            except: xml_str = content.decode('latin-1')
            
            # Limpeza
            xml_str = re.sub(r' xmlns="[^"]+"', '', xml_str)
            root = ET.fromstring(xml_str)
            
            # Filtros básicos
            if "resNFe" in root.tag or "infCte" in root.tag: continue
            
            inf = root.find('.//infNFe')
            if inf is None: continue
            
            chave = inf.attrib.get('Id', '')[3:]
            ide = root.find('.//ide')
            emit = root.find('.//emit')
            dest = root.find('.//dest')
            dets = root.findall('.//det')
            
            num_nf = ide.find('nNF').text if ide is not None and ide.find('nNF') is not None else ""
            uf_emit = emit.find('enderEmit/UF').text if emit is not None and emit.find('enderEmit/UF') is not None else ""
            uf_dest = dest.find('enderDest/UF').text if dest is not None and dest.find('enderDest/UF') is not None else ""

            for det in dets:
                prod = det.find('prod')
                imposto = det.find('imposto')
                
                # Helpers
                def get_txt(node, tag): 
                    found = node.find(tag)
                    return found.text if found is not None else ""
                def get_float(node, tag):
                    found = node.find(tag)
                    return float(found.text) if found is not None else 0.0

                # Extração Impostos
                cst_icms, aliq_icms, bc_icms, v_icms = "", 0.0, 0.0, 0.0
                cst_ipi, aliq_ipi = "", 0.0
                cst_pis, cst_cof = "", ""
                v_difal = 0.0

                if imposto is not None:
                    # ICMS
                    icms_node = imposto.find('ICMS')
                    if icms_node:
                        for child in icms_node:
                            if child.find('CST') is not None: cst_icms = child.find('CST').text
                            elif child.find('CSOSN') is not None: cst_icms = child.find('CSOSN').text
                            aliq_icms = get_float(child, 'pICMS')
                            bc_icms = get_float(child, 'vBC')
                            v_icms = get_float(child, 'vICMS')
                    
                    # IPI
                    ipi_node = imposto.find('IPI')
                    if ipi_node:
                        for child in ipi_node:
                            if child.find('CST') is not None: cst_ipi = child.find('CST').text
                            aliq_ipi = get_float(child, 'pIPI')

                    # PIS/COF
                    pis_node = imposto.find('PIS')
                    if pis_node:
                        for child in pis_node:
                            if child.find('CST') is not None: cst_pis = child.find('CST').text
                    
                    cof_node = imposto.find('COFINS')
                    if cof_node:
                        for child in cof_node:
                            if child.find('CST') is not None: cst_cof = child.find('CST').text
                    
                    # Difal
                    difal_node = imposto.find('ICMSUFDest')
                    if difal_node: v_difal = get_float(difal_node, 'vICMSUFDest')

                dados.append({
                    'Chave': chave, 'Numero': num_nf, 'UF Emit': uf_emit, 'UF Dest': uf_dest,
                    'Item': det.attrib.get('nItem'), 'cProd': get_txt(prod, 'cProd'),
                    'xProd': get_txt(prod, 'xProd'), 'NCM': get_txt(prod, 'NCM'),
                    'CFOP': get_txt(prod, 'CFOP'), 'Valor Prod': get_float(prod, 'vProd'),
                    'CST ICMS': cst_icms, 'Aliq ICMS': aliq_icms, 'BC ICMS': bc_icms, 'Vlr ICMS': v_icms,
                    'CST IPI': cst_ipi, 'Aliq IPI': aliq_ipi,
                    'CST PIS': cst_pis, 'CST COFINS': cst_cof,
                    'Difal Dest': v_difal
                })
        except: pass
        
    return pd.DataFrame(dados)

# --- 5. INTERFACE ---
col_logo, col_text = st.columns([1, 5])
with col_logo:
    path = "nascel sem fundo.png" if os.path.exists("nascel sem fundo.png") else ".streamlit/nascel sem fundo.png"
    if os.path.exists(path): st.image(path, width=150)
    else: st.markdown("### NASCEL")
with col_text:
    st.markdown('<div class="main-title">Sentinela: Análise Tributária</div>', unsafe_allow_html=True)
    st.markdown('<div class="sub-title">Central de Auditoria Fiscal e Compliance</div>', unsafe_allow_html=True)

st.divider()

# --- ÁREA DE UPLOAD UNIFICADA ---
st.markdown("### 📂 Importação das Bases")
c1, c2, c3 = st.columns(3, gap="medium")

with c1:
    st.markdown('<div class="feature-card"><span class="card-icon">📥</span><b>Entradas XML</b></div>', unsafe_allow_html=True)
    xml_ent = st.file_uploader("Up Entradas", type=["xml"], accept_multiple_files=True, label_visibility="collapsed", key="in")

with c2:
    st.markdown('<div class="feature-card"><span class="card-icon">📤</span><b>Saídas XML</b></div>', unsafe_allow_html=True)
    xml_sai = st.file_uploader("Up Saídas", type=["xml"], accept_multiple_files=True, label_visibility="collapsed", key="out")

with c3:
    st.markdown('<div class="feature-card"><span class="card-icon">📋</span><b>Status Sefaz (Excel)</b></div>', unsafe_allow_html=True)
    file_status = st.file_uploader("Up Status", type=["xlsx", "csv"], label_visibility="collapsed", key="st")

st.markdown("<br>", unsafe_allow_html=True)

# --- BOTÃO DE AÇÃO ---
if st.button("🚀 GERAR PLANILHA DE ANÁLISE TRIBUTÁRIA", type="primary"):
    
    if not (xml_ent or xml_sai):
        st.error("⚠️ É necessário enviar pelo menos XMLs de Entrada ou Saída.")
    else:
        with st.spinner("Processando XMLs, cruzando com Sefaz e aplicando regras fiscais..."):
            
            # 1. Carregar Status Sefaz
            status_dict = {}
            if file_status:
                try:
                    if file_status.name.endswith('.xlsx'): df_st = pd.read_excel(file_status, dtype=str)
                    else: df_st = pd.read_csv(file_status, dtype=str)
                    status_dict = dict(zip(df_st.iloc[:, 0].str.replace(r'\D', '', regex=True), df_st.iloc[:, 5]))
                except: st.warning("Erro ao ler arquivo de Status Sefaz.")

            # 2. Processar Dados
            df_e = processar_xmls(xml_ent) if xml_ent else pd.DataFrame()
            df_s = processar_xmls(xml_sai) if xml_sai else pd.DataFrame()
            
            # 3. Cruzar Status (Importante para não calcular imposto de nota cancelada)
            if not df_e.empty: 
                df_e['Status'] = df_e['Chave'].map(status_dict).fillna("Não verificado")
            if not df_s.empty: 
                df_s['Status'] = df_s['Chave'].map(status_dict).fillna("Não verificado")

            # 4. Análise Tributária (Exemplo: IPI e PIS/COFINS nas Saídas)
            df_analise_ipi = pd.DataFrame()
            df_analise_pc = pd.DataFrame()

            if not df_s.empty:
                # IPI
                df_analise_ipi = df_s.copy()
                def check_ipi(row):
                    if "Cancelada" in str(row['Status']): return "NF Cancelada"
                    esp = map_tipi.get(str(row['NCM']))
                    if not esp: return "NCM sem TIPI"
                    try: 
                        esp_val = float(esp)
                        return "Correto" if abs(row['Aliq IPI'] - esp_val) < 0.1 else f"Div: XML {row['Aliq IPI']} | TIPI {esp_val}"
                    except: return "Erro"
                if map_tipi: df_analise_ipi['Auditoria IPI'] = df_analise_ipi.apply(check_ipi, axis=1)

                # PIS/COF
                df_analise_pc = df_s.copy()
                def check_pc(row):
                    if "Cancelada" in str(row['Status']): return "NF Cancelada"
                    esp = map_pc.get(str(row['NCM']))
                    if not esp: return "NCM sem Base"
                    if str(row['CST PIS']) != esp: return f"Div PIS: {row['CST PIS']} (Esp: {esp})"
                    if str(row['CST COFINS']) != esp: return f"Div COF: {row['CST COFINS']} (Esp: {esp})"
                    return "Correto"
                if map_pc: df_analise_pc['Auditoria PIS_COF'] = df_analise_pc.apply(check_pc, axis=1)

            # 5. Gerar Excel Final
            buffer = io.BytesIO()
            with pd.ExcelWriter(buffer, engine='xlsxwriter') as writer:
                if not df_e.empty: df_e.to_excel(writer, index=False, sheet_name='Entradas_Geral')
                if not df_s.empty: df_s.to_excel(writer, index=False, sheet_name='Saidas_Geral')
                if not df_analise_ipi.empty: df_analise_ipi.to_excel(writer, index=False, sheet_name='Auditoria_IPI')
                if not df_analise_pc.empty: df_analise_pc.to_excel(writer, index=False, sheet_name='Auditoria_PIS_COFINS')

            st.success("✅ Processamento Concluído!")
            st.download_button(
                label="📥 BAIXAR PLANILHA COMPLETA (SENTINELA)",
                data=buffer.getvalue(),
                file_name="Sentinela_Analise_Tributaria.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                type="primary",
                use_container_width=True
            )
