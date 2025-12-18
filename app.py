import streamlit as st
import pandas as pd
import xml.etree.ElementTree as ET
import io
import re
import os

# --- 1. CONFIGURAÇÃO VISUAL (LAYOUT NOVO) ---
st.set_page_config(
    page_title="Nascel | Auditoria",
    page_icon="🧡",
    layout="wide",
    initial_sidebar_state="collapsed"
)

# CSS PERSONALIZADO (Visual Fofo, Laranja e Compacto)
st.markdown("""
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Quicksand:wght@400;600;700&display=swap');

    html, body, [class*="css"] {
        font-family: 'Quicksand', sans-serif;
    }
    
    /* Remove espaço em branco do topo */
    div.block-container {
        padding-top: 2rem !important;
        padding-bottom: 1rem !important;
    }

    /* Cores e Fundos */
    .stApp { background-color: #F7F7F7; }
    h1, h2, h3, h4 { color: #FF6F00 !important; font-weight: 700; }
    
    /* Box Branca dos Uploads */
    div[data-testid="stVerticalBlock"] > div[data-testid="stVerticalBlock"] {
        background-color: white; padding: 20px; border-radius: 20px; box-shadow: 0 4px 15px rgba(0,0,0,0.05);
    }
    
    /* Uploaders */
    .stFileUploader { padding: 10px; border: 2px dashed #FFCC80; border-radius: 15px; text-align: center; }
    
    /* Botões */
    .stButton>button { background-color: #FF6F00; color: white; border-radius: 25px; border: none; font-weight: bold; padding: 10px 30px; width: 100%; }
    .stButton>button:hover { background-color: #E65100; }
    
    /* Métricas */
    div[data-testid="metric-container"] { border-left: 5px solid #FF6F00; background-color: #FFF3E0; border-radius: 10px; }
    </style>
""", unsafe_allow_html=True)

# --- 2. SIDEBAR (LOGO NASCEL) ---
with st.sidebar:
    caminho_logo = ".streamlit/nascel sem fundo.png"
    if os.path.exists(caminho_logo):
        st.image(caminho_logo, use_column_width=True)
    elif os.path.exists("nascel sem fundo.png"):
        st.image("nascel sem fundo.png", use_column_width=True)
    else:
        st.markdown("<h1 style='color:#FF6F00; text-align:center;'>Nascel</h1>", unsafe_allow_html=True)
    
    st.markdown("---")
    st.info("💡 **Dica:** Carregue os arquivos nas caixas ao centro para iniciar.")

# --- 3. TÍTULO PRINCIPAL (SENTINELA) ---
caminho_titulo = ".streamlit/Sentinela.png"

if os.path.exists(caminho_titulo):
    col_c1, col_tit, col_c2 = st.columns([3, 4, 3])
    with col_tit:
        st.image(caminho_titulo, use_column_width=True)
elif os.path.exists("Sentinela.png"):
    col_c1, col_tit, col_c2 = st.columns([3, 4, 3])
    with col_tit:
        st.image("Sentinela.png", use_column_width=True)
else:
    st.markdown("<h1 style='text-align: center; color: #FF6F00; margin-bottom:0;'>SENTINELA</h1>", unsafe_allow_html=True)
    st.markdown("<h4 style='text-align: center; color: #666; margin-top:0;'>Sistema de Auditoria Fiscal</h4>", unsafe_allow_html=True)

# --- 4. ÁREA DE UPLOAD (6 BOTÕES) ---
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

# ==============================================================================
# --- 5. O CÉREBRO ROBUSTO ---
# ==============================================================================

@st.cache_data
def carregar_bases_mestre():
    df_tipi = pd.DataFrame()
    df_pc_base = pd.DataFrame()

    def encontrar_arquivo(nome_base):
        possibilidades = [
            nome_base, nome_base.lower(), 
            f".streamlit/{nome_base}", f".streamlit/{nome_base.lower()}",
            "CST_Pis_Cofins.xlsx", ".streamlit/CST_Pis_Cofins.xlsx",
            "tipi.xlsx", ".streamlit/tipi.xlsx"
        ]
        for p in possibilidades:
            if os.path.exists(p): return p
        return None

    # A. TIPI
    caminho_tipi = encontrar_arquivo("tipi.xlsx")
    if caminho_tipi:
        try:
            df_raw = pd.read_excel(caminho_tipi, dtype=str)
            df_tipi = df_raw.iloc[:, [0, 1]].copy()
            df_tipi.columns = ['NCM', 'ALIQ']
            df_tipi['NCM'] = df_tipi['NCM'].str.replace(r'\D', '', regex=True).str.zfill(8)
            df_tipi['ALIQ'] = df_tipi['ALIQ'].str.upper().replace('NT', '0').str.strip().str.replace(',', '.')
        except: pass

    # B. PIS & COFINS
    caminho_pc = encontrar_arquivo("CST_Pis_Cofins.xlsx")
    if caminho_pc:
        try:
            df_pc_raw = pd.read_excel(caminho_pc, dtype=str)
            if len(df_pc_raw.columns) >= 3:
                df_pc_base = df_pc_raw.iloc[:, [0, 1, 2]].copy()
                df_pc_base.columns = ['NCM', 'CST_ENT', 'CST_SAI']
                df_pc_base['NCM'] = df_pc_base['NCM'].str.replace(r'\D', '', regex=True).str.zfill(8)
                df_pc_base['CST_SAI'] = df_pc_base['CST_SAI'].str.replace(r'\D', '', regex=True).str.zfill(2)
        except: pass

    return df_tipi, df_pc_base

# Carrega as bases
df_tipi, df_pc_base = carregar_bases_mestre()

# Prepara Dicionários para busca rápida
bases = {"TIPI": {}, "PC": {}}
if not df_tipi.empty:
    bases["TIPI"] = dict(zip(df_tipi['NCM'], df_tipi['ALIQ']))
if not df_pc_base.empty:
    bases["PC"] = dict(zip(df_pc_base['NCM'], df_pc_base['CST_SAI']))


# --- FUNÇÃO DE EXTRAÇÃO ---
def extrair_tags_com_raio_x(arquivos_upload, origem):
    itens_validos = []
    arquivos_com_erro = []

    for arquivo in arquivos_upload:
        try:
            content = arquivo.read()
            try: xml_str = content.decode('utf-8')
            except: xml_str = content.decode('latin-1')

            xml_str_clean = re.sub(r' xmlns="[^"]+"', '', xml_str)
            xml_str_clean = re.sub(r' xmlns:xsi="[^"]+"', '', xml_str_clean)
            xml_str_clean = re.sub(r' xsi:schemaLocation="[^"]+"', '', xml_str_clean)
            
            root = ET.fromstring(xml_str_clean)

            if "resNFe" in root.tag or root.find(".//resNFe") is not None: continue
            if "procEventoNFe" in root.tag or root.find(".//retEvento") is not None: continue
            
            infNFe = root.find('.//infNFe')
            if infNFe is None:
                arquivos_com_erro.append({"Arquivo": arquivo.name, "Motivo": "XML desconhecido"})
                continue

            dets = root.findall(f".//det")
            if not dets:
                arquivos_com_erro.append({"Arquivo": arquivo.name, "Motivo": "Sem Produtos"})
                continue

            ide = root.find(f".//ide")
            emit = root.find(f".//emit")
            dest = root.find(f".//dest")
            chave = infNFe.attrib.get('Id', '')[3:]

            for det in dets:
                prod = det.find(f"prod")
                imposto = det.find(f"imposto")
                
                def get_val(node, tag, tipo=str):
                    if node is None: return 0.0 if tipo == float else ""
                    res = node.find(f"{tag}")
                    if res is not None and res.text:
                        return float(res.text) if tipo == float else res.text
                    return 0.0 if tipo == float else ""

                def get_pis_cofins(grupo, campo):
                    if imposto is None: return ""
                    node = imposto.find(f"{grupo}")
                    if node is not None:
                        for child in node:
                            res = child.find(f"{campo}")
                            if res is not None: return res.text
                    return ""

                # Valores ICMS
                cst_icms, aliq_icms, val_icms = "", 0.0, 0.0
                if imposto is not None:
                    node_icms = imposto.find(f"ICMS")
                    if node_icms:
                        for child in node_icms:
                            if child.find(f"CST") is not None: cst_icms = child.find(f"CST").text
                            elif child.find(f"CSOSN") is not None: cst_icms = child.find(f"CSOSN").text
                            if child.find(f"pICMS") is not None: aliq_icms = float(child.find(f"pICMS").text)
                            if child.find(f"vICMS") is not None: val_icms = float(child.find(f"vICMS").text)

                # Valores IPI
                cst_ipi, aliq_ipi = "", 0.0
                if imposto is not None:
                    node_ipi = imposto.find(f"IPI")
                    if node_ipi:
                        for child in node_ipi:
                            if child.find(f"CST") is not None: cst_ipi = child.find(f"CST").text
                            if child.find(f"pIPI") is not None: aliq_ipi = float(child.find(f"pIPI").text)

                registro = {
                    "Origem": origem,
                    "Arquivo": arquivo.name,
                    "Número NF": get_val(ide, 'nNF'),
                    "UF Emit": emit.find(f"enderEmit/UF").text if emit is not None and emit.find(f"enderEmit/UF") is not None else "",
                    "UF Dest": dest.find(f"enderDest/UF").text if dest is not None and dest.find(f"enderDest/UF") is not None else "",
                    "Cód Prod": get_val(prod, 'cProd'),
                    "Desc Prod": get_val(prod, 'xProd'),
                    "NCM": get_val(prod, 'NCM'),
                    "CFOP": get_val(prod, 'CFOP'),
                    "vProd": get_val(prod, 'vProd', float),
                    "CST ICMS": cst_icms,
                    "Alq ICMS": aliq_icms,
                    "ICMS": val_icms,
                    "CST IPI": cst_ipi,
                    "Aliq IPI": aliq_ipi,
                    "CST PIS": get_pis_cofins('PIS', 'CST'),
                    "CST COFINS": get_pis_cofins('COFINS', 'CST'),
                    "Chave de Acesso": chave
                }
                itens_validos.append(registro)

        except Exception as e:
            arquivos_com_erro.append({"Arquivo": arquivo.name, "Motivo": f"Erro de Leitura: {str(e)}"})

    return pd.DataFrame(itens_validos), arquivos_com_erro

# --- FUNÇÃO DE STATUS ---
def cruzar_status(df, file):
    if df.empty: return df
    if not file: 
        df['Status_Sefaz'] = "Não Verificado"
        return df
    try:
        if file.name.endswith('xlsx'): s = pd.read_excel(file, dtype=str)
        else: s = pd.read_csv(file, dtype=str)
        mapping = dict(zip(s.iloc[:,0].str.replace(r'\D','',regex=True), s.iloc[:,-1]))
        df['Status_Sefaz'] = df['Chave de Acesso'].map(mapping).fillna("Não Localizado")
    except:
        df['Status_Sefaz'] = "Erro Arquivo Status"
    return df

# --- FUNÇÃO AUDITORIA ---
def auditar_ipi(df):
    if df.empty or not bases.get("TIPI"): return df
    def check(row):
        esp = bases["TIPI"].get(str(row['NCM']))
        if not esp: return "NCM Off"
        if esp == 'NT': return "OK"
        try: return "OK" if abs(row['Aliq IPI'] - float(esp)) < 0.1 else f"Div (XML:{row['Aliq IPI']} | TIPI:{esp})"
        except: return "Erro"
    df['Auditoria_IPI'] = df.apply(check, axis=1)
    return df

# --- 6. EXECUÇÃO DO PROCESSAMENTO ---

# Processa Entradas
df_e, erros_e = extrair_tags_com_raio_x(up_ent_xml, "Entrada") if up_ent_xml else (pd.DataFrame(), [])
df_e = cruzar_status(df_e, up_ent_aut)

# Processa Saídas
df_s, erros_s = extrair_tags_com_raio_x(up_sai_xml, "Saída") if up_sai_xml else (pd.DataFrame(), [])
df_s = cruzar_status(df_s, up_sai_aut)
df_s = auditar_ipi(df_s) # Aplica IPI apenas nas saídas

st.markdown("---")

if df_e.empty and df_s.empty:
    st.info("👆 Aguardando arquivos... Carregue os XMLs e relatórios nas caixas acima.")
else:
    st.markdown("## 📊 Resultados da Análise")
    
    # Exibir erros de leitura se houver
    if erros_e or erros_s:
        with st.expander("⚠️ Arquivos ignorados (Erros de Leitura)"):
            st.write(erros_e + erros_s)

    tab1, tab2, tab3 = st.tabs(["Visão Geral", "Entradas", "Saídas"])
    
    with tab1:
        c1, c2, c3 = st.columns(3)
        c1.metric("Total Notas", len(df_e) + len(df_s))
        
        # Lógica segura de contagem
        err_e = len(df_e[~df_e['Status_Sefaz'].str.contains('Autoriz|OK|Não Verif', na=False, case=False)]) if not df_e.empty else 0
        err_s = len(df_s[~df_s['Status_Sefaz'].str.contains('Autoriz|OK|Não Verif', na=False, case=False)]) if not df_s.empty else 0
        c2.metric("Alertas Sefaz", err_e + err_s)
        
        div_ipi = len(df_s[df_s['Auditoria_IPI'].str.contains('Div', na=False)]) if not df_s.empty and 'Auditoria_IPI' in df_s.columns else 0
        c3.metric("Divergências IPI", div_ipi)

    with tab2:
        if not df_e.empty: st.dataframe(df_e, use_container_width=True)
    with tab3:
        if not df_s.empty: st.dataframe(df_s, use_container_width=True)
        
    # ========================================================
    # 🧠 INTELIGÊNCIA: SUGESTÃO DE ATUALIZAÇÃO DE BASES
    # ========================================================
    st.markdown("---")
    st.subheader("🧠 Inteligência das Bases")
    st.info("O Sentinela identificou itens nos XMLs que **não estão cadastrados** nas suas bases atuais. Baixe a planilha abaixo para atualizar seus arquivos mestres.")

    # 1. Preparar dados consolidados (Entradas + Saídas)
    
    # Renomeia colunas para unificar
    # Usa nomes seguros que existem nas funções de extração
    df_e_mini = pd.DataFrame()
    if not df_e.empty:
        df_e_mini = df_e.rename(columns={'Desc Prod': 'Descricao', 'Aliq IPI': 'Aliq_IPI', 'CST PIS': 'CST_PIS', 'CST COFINS': 'CST_COFINS'})
        df_e_mini = df_e_mini[['NCM', 'Descricao', 'Aliq_IPI', 'CST_PIS', 'CST_COFINS']]
    
    df_s_mini = pd.DataFrame()
    if not df_s.empty:
        df_s_mini = df_s.rename(columns={'Desc Prod': 'Descricao', 'Aliq IPI': 'Aliq_IPI', 'CST PIS': 'CST_PIS', 'CST COFINS': 'CST_COFINS'})
        df_s_mini = df_s_mini[['NCM', 'Descricao', 'Aliq_IPI', 'CST_PIS', 'CST_COFINS']]
    
    df_full = pd.concat([df_e_mini, df_s_mini], ignore_index=True)

    if not df_full.empty:
        # A. NOVOS PARA TIPI
        novos_tipi = df_full[~df_full['NCM'].isin(bases.get('TIPI', {}).keys())].copy()
        
        sugestao_tipi = pd.DataFrame()
        if not novos_tipi.empty:
            sugestao_tipi = novos_tipi.groupby('NCM').agg({
                'Descricao': 'first',
                'Aliq_IPI': lambda x: x.mode()[0] if not x.mode().empty else 0.0
            }).reset_index()
            sugestao_tipi.columns = ['NCM', 'Descrição Sugerida', 'Alíquota XML (Sugestão)']

        # B. NOVOS PARA PIS/COFINS
        novos_pc = df_full[~df_full['NCM'].isin(bases.get('PC', {}).keys())].copy()
        
        sugestao_pc = pd.DataFrame()
        if not novos_pc.empty:
            sugestao_pc = novos_pc.groupby('NCM').agg({
                'Descricao': 'first',
                'CST_PIS': lambda x: x.mode()[0] if not x.mode().empty else '',
                'CST_COFINS': lambda x: x.mode()[0] if not x.mode().empty else ''
            }).reset_index()
            sugestao_pc.columns = ['NCM', 'Descrição Sugerida', 'CST PIS (XML)', 'CST COF (XML)']

        # C. BOTÃO DE DOWNLOAD DA ATUALIZAÇÃO
        if not sugestao_tipi.empty or not sugestao_pc.empty:
            col_msg, col_bt = st.columns([2, 1])
            with col_msg:
                st.write(f"📦 **Novos NCMs detectados:** {len(sugestao_tipi)} para TIPI | {len(sugestao_pc)} para PIS/COFINS")
            
            with col_bt:
                buffer_update = io.BytesIO()
                with pd.ExcelWriter(buffer_update, engine='xlsxwriter') as writer:
                    if not sugestao_tipi.empty: 
                        sugestao_tipi.to_excel(writer, sheet_name='Atualizar_TIPI', index=False)
                    if not sugestao_pc.empty: 
                        sugestao_pc.to_excel(writer, sheet_name='Atualizar_PisCofins', index=False)
                
                st.download_button(
                    label="🧠 Baixar Planilha de Atualização",
                    data=buffer_update.getvalue(),
                    file_name="Sugestao_Atualizacao_Bases.xlsx",
                    mime="application/vnd.ms-excel",
                    key="btn_update"
                )
        else:
            st.success("✨ Suas bases estão 100% atualizadas com os XMLs analisados!")
            
    # ========================================================
    # DOWNLOAD RELATÓRIO FINAL
    # ========================================================
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
