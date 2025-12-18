import streamlit as st
import pandas as pd
import xml.etree.ElementTree as ET
import io
import re
import os

# --- CONFIGURAÇÃO ---
st.set_page_config(page_title="Sentinela Fiscal Pro", layout="wide")
st.title("🛡️ Sentinela: Auditoria Fiscal (ICMS, IPI, PIS & COFINS)")

# --- 1. CARREGAR BASES MESTRE (BLINDADO CONTRA ERROS DE ARQUIVO) ---
@st.cache_data
def carregar_bases_mestre():
    # Inicializa tudo como DataFrame vazio para não dar erro de AttributeError
    df_gerencial = pd.DataFrame()
    df_tribut = pd.DataFrame()
    df_inter = pd.DataFrame()
    df_tipi = pd.DataFrame()
    df_pc_base = pd.DataFrame()

    # --- FUNÇÃO DE BUSCA (SHERLOCK HOLMES) ---
    def encontrar_arquivo(nome_base):
        possibilidades = [
            nome_base, nome_base.lower(), nome_base.upper(), 
            f".streamlit/{nome_base}", f".streamlit/{nome_base.lower()}",
            "Pis_Cofins.xlsx", "pis_cofins.xlsx", ".streamlit/Pis_Cofins.xlsx"
        ]
        for p in possibilidades:
            if os.path.exists(p): return p
        
        # Varredura extra
        for root, dirs, files in os.walk("."):
            for file in files:
                if nome_base.lower().split('.')[0] in file.lower():
                    return os.path.join(root, file)
        return None

    # A. Bases Internas (Sentinela)
    caminho_mestre = encontrar_arquivo("Sentinela_MIRÃO_Outubro2025.xlsx")
    if caminho_mestre:
        try:
            xls = pd.ExcelFile(caminho_mestre)
            df_gerencial = pd.read_excel(xls, 'Entradas Gerencial', dtype=str)
            df_tribut = pd.read_excel(xls, 'Bases Tribut', dtype=str)
            try: df_inter = pd.read_excel(xls, 'Bases Tribut', usecols="AC:AD", dtype=str).dropna()
            except: pass
        except Exception as e:
            print(f"Erro ao ler Sentinela: {e}")

    # B. TIPI
    caminho_tipi = encontrar_arquivo("TIPI.xlsx")
    if caminho_tipi:
        try:
            df_raw = pd.read_excel(caminho_tipi, dtype=str)
            df_tipi = df_raw.iloc[:, [0, 1]].copy()
            df_tipi.columns = ['NCM', 'ALIQ']
            df_tipi = df_tipi.dropna(how='all')
            df_tipi['NCM'] = df_tipi['NCM'].str.replace(r'\D', '', regex=True).str.zfill(8)
            df_tipi['ALIQ'] = df_tipi['ALIQ'].str.upper().replace('NT', '0').str.strip().str.replace(',', '.')
            df_tipi = df_tipi[df_tipi['NCM'].str.match(r'^\d{8}$', na=False)]
        except Exception as e:
            print(f"Erro TIPI: {e}")

    # C. PIS & COFINS
    caminho_pc = encontrar_arquivo("Pis_Cofins.xlsx")
    if caminho_pc:
        try:
            df_pc_raw = pd.read_excel(caminho_pc, dtype=str)
            # Pega as 3 primeiras colunas (NCM, Entrada, Saída)
            if len(df_pc_raw.columns) >= 3:
                df_pc_base = df_pc_raw.iloc[:, [0, 1, 2]].copy()
                df_pc_base.columns = ['NCM', 'CST_ENT', 'CST_SAI']
                df_pc_base['NCM'] = df_pc_base['NCM'].str.replace(r'\D', '', regex=True).str.zfill(8)
                df_pc_base['CST_SAI'] = df_pc_base['CST_SAI'].str.replace(r'\D', '', regex=True).str.zfill(2)
        except Exception as e:
            print(f"Erro Pis_Cofins: {e}")

    # Retorna sempre DataFrames (mesmo que vazios), nunca None
    return df_gerencial, df_tribut, df_inter, df_tipi, df_pc_base

df_gerencial, df_tribut, df_inter, df_tipi, df_pc_base = carregar_bases_mestre()

# --- 2. EXTRAÇÃO XML ---
def extrair_tags_completo(xml_content):
    ns = {'nfe': 'http://www.portalfiscal.inf.br/nfe'}
    try: root = ET.fromstring(xml_content)
    except: return []
    
    infNFe = root.find('.//nfe:infNFe', ns)
    chave = infNFe.attrib['Id'][3:] if infNFe is not None else ""
    ide = root.find('.//nfe:ide', ns)
    emit = root.find('.//nfe:emit', ns)
    dest = root.find('.//nfe:dest', ns)
    
    itens = []
    for det in root.findall('.//nfe:det', ns):
        prod = det.find('nfe:prod', ns)
        imposto = det.find('nfe:imposto', ns)
        
        def get_pis_cofins(tag, field):
            node = imposto.find(f'.//nfe:{tag}', ns)
            if node is not None:
                for child in node:
                    res = child.find(f'nfe:{field}', ns)
                    if res is not None: return res.text
            return ""

        registro = {
            "Número NF": ide.find('nfe:nNF', ns).text if ide is not None else "",
            "UF Emit": emit.find('nfe:enderEmit/nfe:UF', ns).text if emit is not None else "",
            "UF Dest": dest.find('nfe:enderDest/nfe:UF', ns).text if dest is not None else "",
            "nItem": det.attrib['nItem'],
            "Cód Prod": prod.find('nfe:cProd', ns).text if prod is not None else "",
            "Desc Prod": prod.find('nfe:xProd', ns).text if prod is not None else "",
            "NCM": prod.find('nfe:NCM', ns).text if prod is not None else "",
            "CFOP": prod.find('nfe:CFOP', ns).text if prod is not None else "",
            "vProd": float(prod.find('nfe:vProd', ns).text) if prod is not None else 0.0,
            "CST ICMS": imposto.find('.//nfe:CST', ns).text if imposto.find('.//nfe:CST', ns) is not None else "",
            "BC ICMS": float(imposto.find('.//nfe:vBC', ns).text) if imposto.find('.//nfe:vBC', ns) is not None else 0.0,
            "Alq ICMS": float(imposto.find('.//nfe:pICMS', ns).text) if imposto.find('.//nfe:pICMS', ns) is not None else 0.0,
            "ICMS": float(imposto.find('.//nfe:vICMS', ns).text) if imposto.find('.//nfe:vICMS', ns) is not None else 0.0,
            "CST IPI": imposto.find('.//nfe:IPI//nfe:CST', ns).text if imposto.find('.//nfe:IPI//nfe:CST', ns) is not None else "",
            "Aliq IPI": float(imposto.find('.//nfe:IPI//nfe:pIPI', ns).text) if imposto.find('.//nfe:IPI//nfe:pIPI', ns) is not None else 0.0,
            "CST PIS": get_pis_cofins('PIS', 'CST'),
            "CST COFINS": get_pis_cofins('COFINS', 'CST'),
            "Chave de Acesso": chave
        }
        itens.append(registro)
    return itens

# --- 3. INTERFACE ---
with st.sidebar:
    st.header("📂 Upload Central")
    
    # Verificações visuais
    if not df_pc_base.empty: st.toast("Base PIS/COFINS Pronta!", icon="✅")
    else: st.warning("⚠️ Base Pis_Cofins.xlsx não encontrada ou vazia.")
    
    if not df_tipi.empty: st.toast("TIPI Pronta!", icon="✅")
    else: st.warning("⚠️ TIPI não encontrada.")

    xml_saidas = st.file_uploader("1. Notas de SAÍDA", accept_multiple_files=True, type='xml')
    xml_entradas = st.file_uploader("2. Notas de ENTRADA", accept_multiple_files=True, type='xml')
    rel_status = st.file_uploader("3. Status Sefaz", type=['xlsx', 'csv'])

# --- 4. PROCESSAMENTO ---
if (xml_saidas or xml_entradas) and rel_status:
    try:
        df_st_rel = pd.read_excel(rel_status, dtype=str) if rel_status.name.endswith('.xlsx') else pd.read_csv(rel_status, dtype=str)
        status_dict = dict(zip(df_st_rel.iloc[:, 0].str.replace(r'\D', '', regex=True), df_st_rel.iloc[:, 5]))
    except:
        st.error("Erro ao ler relatório de status.")
        status_dict = {}

    list_s = []
    if xml_saidas:
        for f in xml_saidas: list_s.extend(extrair_tags_completo(f.read()))
    df_s = pd.DataFrame(list_s)
    
    list_e = []
    if xml_entradas:
        for f in xml_entradas: list_e.extend(extrair_tags_completo(f.read()))
    df_e = pd.DataFrame(list_e)

    if not df_s.empty:
        df_s['AP'] = df_s['Chave de Acesso'].str.replace(r'\D', '', regex=True).map(status_dict).fillna("Pendente")
        
        # --- MAPAS ---
        map_tribut_cst = {}
        map_tribut_aliq = {}
        map_gerencial_cst = {}
        map_inter = {}
        map_tipi = {}
        map_pis_cofins_saida = {}

        if not df_tribut.empty:
            map_tribut_cst = dict(zip(df_tribut.iloc[:, 0].astype(str), df_tribut.iloc[:, 2].astype(str)))
            map_tribut_aliq = dict(zip(df_tribut.iloc[:, 0].astype(str), df_tribut.iloc[:, 3].astype(str)))
        if not df_gerencial.empty:
            map_gerencial_cst = dict(zip(df_gerencial.iloc[:, 0].astype(str), df_gerencial.iloc[:, 1].astype(str)))
        if not df_inter.empty:
            map_inter = dict(zip(df_inter.iloc[:, 0].astype(str), df_inter.iloc[:, 1].astype(str)))
        if not df_tipi.empty:
            map_tipi = dict(zip(df_tipi['NCM'], df_tipi['ALIQ']))
        if not df_pc_base.empty:
            map_pis_cofins_saida = dict(zip(df_pc_base['NCM'], df_pc_base['CST_SAI']))

        # === AUDITORIA ===
        
        # 1. ICMS
        df_icms = df_s.copy()
        def f_analise_cst(row):
            status, cst, ncm = str(row['AP']), str(row['CST ICMS']).strip(), str(row['NCM']).strip()
            if "Cancelamento" in status: return "NF cancelada"
            cst_esp = map_tribut_cst.get(ncm)
            if not cst_esp: return "NCM não encontrado"
            if map_gerencial_cst.get(ncm) == "60" and cst != "60": return f"Divergente — CST: {cst} | Esp: 60"
            return "Correto" if cst == cst_esp else f"Divergente — CST: {cst} | Esp: {cst_esp}"
        
        def f_aliq(row):
             if "Cancelamento" in str(row['AP']): return "NF Cancelada"
             ncm, uf_e, uf_d, aliq_xml = str(row['NCM']), row['UF Emit'], row['UF Dest'], row['Alq ICMS']
             if uf_e == uf_d: esp = map_tribut_aliq.get(ncm)
             else: esp = map_inter.get(uf_d)
             try: esp_val = float(str(esp).replace(',', '.'))
             except: return "Erro valor esperado"
             return "Correto" if abs(aliq_xml - esp_val) < 0.1 else f"Destacado: {aliq_xml} | Esp: {esp_val}"

        df_icms['Análise CST ICMS'] = df_icms.apply(f_analise_cst, axis=1)
        df_icms['Analise Aliq ICMS'] = df_icms.apply(f_aliq, axis=1)

        # 2. IPI
        df_ipi = df_s.copy()
        def f_analise_ipi(row):
            if "Cancelamento" in str(row['AP']): return "NF Cancelada"
            ncm, aliq_xml = str(row['NCM']).strip(), row['Aliq IPI']
            if not map_tipi: return "TIPI não disponível"
            esp = map_tipi.get(ncm)
            if esp is None: return "NCM não encontrado na TIPI"
            try: esp_val = float(str(esp).replace(',', '.'))
            except: return "Erro leitura TIPI"
            if abs(aliq_xml - esp_val) < 0.1: return "Correto"
            else: return f"Destacado: {aliq_xml} | Esp: {esp_val}"
        
        df_ipi['Análise IPI'] = df_ipi.apply(f_analise_ipi, axis=1)

        # 3. PIS/COFINS
        df_pc = df_s.copy()
        def f_analise_pis_cofins(row):
            if "Cancelamento" in str(row['AP']): return "NF Cancelada"
            ncm = str(row['NCM']).strip()
            cst_pis_xml = str(row['CST PIS']).strip()
            cst_cof_xml = str(row['CST COFINS']).strip()

            if not map_pis_cofins_saida: return "Base Excel não carregada"

            cst_saida_esp = map_pis_cofins_saida.get(ncm)
            if cst_saida_esp is None: return "NCM não encontrado na base PC"

            erros = []
            if cst_pis_xml != cst_saida_esp: erros.append(f"PIS: {cst_pis_xml} (Esp: {cst_saida_esp})")
            if cst_cof_xml != cst_saida_esp: erros.append(f"COF: {cst_cof_xml} (Esp: {cst_saida_esp})")

            return "Correto" if not erros else " | ".join(erros)

        df_pc['Análise PIS e COFINS'] = df_pc.apply(f_analise_pis_cofins, axis=1)

    # --- EXPORTAR ---
    buffer = io.BytesIO()
    with pd.ExcelWriter(buffer, engine='xlsxwriter') as writer:
        if not df_e.empty: df_e.to_excel(writer, index=False, sheet_name='Entradas')
        if not df_s.empty: df_s.to_excel(writer, index=False, sheet_name='Saídas')
        if not df_s.empty: df_icms.to_excel(writer, index=False, sheet_name='ICMS')
        if not df_s.empty: df_ipi.to_excel(writer, index=False, sheet_name='IPI')
        if not df_s.empty: df_pc.to_excel(writer, index=False, sheet_name='Pis_Cofins')

    st.success("✅ Auditoria Completa: Entradas, Saídas, ICMS, IPI e Pis_Cofins geradas!")
    st.download_button("📥 Baixar Sentinela Auditada", buffer.getvalue(), "Sentinela_Auditada_Final.xlsx")
