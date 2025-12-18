import streamlit as st
import pandas as pd
import xml.etree.ElementTree as ET
import io
import re
import os

st.set_page_config(page_title="Sentinela Fiscal Pro", layout="wide")
st.title("🛡️ Sentinela: Entradas, Saídas e Auditoria ICMS")

# --- 1. CARREGAR BASES MESTRE (GITHUB) ---
@st.cache_data
def carregar_bases_mestre():
    caminho_mestre = "Sentinela_MIRÃO_Outubro2025.xlsx"
    if os.path.exists(caminho_mestre):
        xls = pd.ExcelFile(caminho_mestre)
        df_gerencial = pd.read_excel(xls, 'Entradas Gerencial', dtype=str)
        df_tribut = pd.read_excel(xls, 'Bases Tribut', dtype=str)
        return df_gerencial, df_tribut
    return None, None

df_gerencial, df_tribut = carregar_bases_mestre()

# --- 2. FUNÇÃO DE EXTRAÇÃO (FORMATO APROVADO BASE_XML) ---
def extrair_tags_estilo_query(xml_content):
    ns = {'nfe': 'http://www.portalfiscal.inf.br/nfe'}
    try:
        root = ET.fromstring(xml_content)
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
        
        registro = {
            "Natureza Operação": ide.find('nfe:natOp', ns).text if ide is not None else "",
            "Número NF": ide.find('nfe:nNF', ns).text if ide is not None else "",
            "Finalidade": ide.find('nfe:finNFe', ns).text if ide is not None else "",
            "UF Emit": emit.find('nfe:enderEmit/nfe:UF', ns).text if emit is not None else "",
            "CNPJ Emit": emit.find('nfe:CNPJ', ns).text if emit is not None else "",
            "UF Dest": dest.find('nfe:enderDest/nfe:UF', ns).text if dest is not None else "",
            "dest.CPF": dest.find('nfe:CPF', ns).text if dest is not None and dest.find('nfe:CPF', ns) is not None else "",
            "dest.CNPJ": dest.find('nfe:CNPJ', ns).text if dest is not None and dest.find('nfe:CNPJ', ns) is not None else "",
            "dest.IE": dest.find('nfe:IE', ns).text if dest is not None and dest.find('nfe:IE', ns) is not None else "",
            "nItem": det.attrib['nItem'],
            "Cód Prod": prod.find('nfe:cProd', ns).text if prod is not None else "",
            "Desc Prod": prod.find('nfe:xProd', ns).text if prod is not None else "",
            "NCM": prod.find('nfe:NCM', ns).text if prod is not None else "",
            "CEST": prod.find('nfe:CEST', ns).text if prod is not None and prod.find('nfe:CEST', ns) is not None else "",
            "CFOP": prod.find('nfe:CFOP', ns).text if prod is not None else "",
            "vProd": float(prod.find('nfe:vProd', ns).text) if prod is not None else 0.0,
            "vDesc": float(prod.find('nfe:vDesc', ns).text) if prod is not None and prod.find('nfe:vDesc', ns) is not None else 0.0,
            "Origem": imposto.find('.//nfe:orig', ns).text if imposto.find('.//nfe:orig', ns) is not None else "",
            "CST ICMS": imposto.find('.//nfe:CST', ns).text if imposto.find('.//nfe:CST', ns) is not None else "",
            "BC ICMS": float(imposto.find('.//nfe:vBC', ns).text) if imposto.find('.//nfe:vBC', ns) is not None else 0.0,
            "Alq ICMS": float(imposto.find('.//nfe:pICMS', ns).text) if imposto.find('.//nfe:pICMS', ns) is not None else 0.0,
            "ICMS": float(imposto.find('.//nfe:vICMS', ns).text) if imposto.find('.//nfe:vICMS', ns) is not None else 0.0,
            "pRedBC ICMS": float(imposto.find('.//nfe:pRedBC', ns).text) if imposto.find('.//nfe:pRedBC', ns) is not None else 0.0,
            "BC ICMS-ST": float(imposto.find('.//nfe:vBCST', ns).text) if imposto.find('.//nfe:vBCST', ns) is not None else 0.0,
            "ICMS-ST": float(imposto.find('.//nfe:vICMSST', ns).text) if imposto.find('.//nfe:vICMSST', ns) is not None else 0.0,
            "FCPST": float(imposto.find('.//nfe:vFCPST', ns).text) if imposto.find('.//nfe:vFCPST', ns) is not None else 0.0,
            "CST IPI": imposto.find('.//nfe:IPI//nfe:CST', ns).text if imposto.find('.//nfe:IPI//nfe:CST', ns) is not None else "",
            "BC IPI": float(imposto.find('.//nfe:IPI//nfe:vBC', ns).text) if imposto.find('.//nfe:IPI//nfe:vBC', ns) is not None else 0.0,
            "Aliq IPI": float(imposto.find('.//nfe:IPI//nfe:pIPI', ns).text) if imposto.find('.//nfe:IPI//nfe:pIPI', ns) is not None else 0.0,
            "IPI": float(imposto.find('.//nfe:IPI//nfe:vIPI', ns).text) if imposto.find('.//nfe:IPI//nfe:vIPI', ns) is not None else 0.0,
            "CST PIS": imposto.find('.//nfe:PIS//nfe:CST', ns).text if imposto.find('.//nfe:PIS//nfe:CST', ns) is not None else "",
            "BC PIS": float(imposto.find('.//nfe:vBC', ns).text) if imposto.find('.//nfe:vBC', ns) is not None else 0.0,
            "Aliq PIS": float(imposto.find('.//nfe:pPIS', ns).text) if imposto.find('.//nfe:pPIS', ns) is not None else 0.0,
            "PIS": float(imposto.find('.//nfe:vPIS', ns).text) if imposto.find('.//nfe:vPIS', ns) is not None else 0.0,
            "CST COFINS": imposto.find('.//nfe:COFINS//nfe:CST', ns).text if imposto.find('.//nfe:COFINS//nfe:CST', ns) is not None else "",
            "BC COFINS": float(imposto.find('.//nfe:vBC', ns).text) if imposto.find('.//nfe:vBC', ns) is not None else 0.0,
            "Aliq COFINS": float(imposto.find('.//nfe:pCOFINS', ns).text) if imposto.find('.//nfe:pCOFINS', ns) is not None else 0.0,
            "COFINS": float(imposto.find('.//nfe:vCOFINS', ns).text) if imposto.find('.//nfe:vCOFINS', ns) is not None else 0.0,
            "FCP": float(imposto.find('.//nfe:vFCP', ns).text) if imposto.find('.//nfe:vFCP', ns) is not None else 0.0,
            "ICMS UF Dest": float(imposto.find('.//nfe:vICMSUFDest', ns).text) if imposto.find('.//nfe:vICMSUFDest', ns) is not None else 0.0,
            "Chave de Acesso": chave
        }
        itens.append(registro)
    return itens

# --- 3. INTERFACE ---
with st.sidebar:
    st.header("📂 Upload Central")
    xml_saidas = st.file_uploader("1. Notas de SAÍDA", accept_multiple_files=True, type='xml')
    xml_entradas = st.file_uploader("2. Notas de ENTRADA", accept_multiple_files=True, type='xml')
    rel_status = st.file_uploader("3. Relatório Autenticidade (Chave A, Status F)", type=['xlsx', 'csv'])

# --- 4. PROCESSAMENTO ---
if (xml_saidas or xml_entradas) and rel_status:
    # Status Dictionary
    df_st_rel = pd.read_excel(rel_status, dtype=str) if rel_status.name.endswith('.xlsx') else pd.read_csv(rel_status, dtype=str)
    status_dict = dict(zip(df_st_rel.iloc[:, 0].str.replace(r'\D', '', regex=True).str.strip(), df_st_rel.iloc[:, 5].str.strip()))

    # Processar Saídas
    df_saidas = pd.DataFrame()
    if xml_saidas:
        list_s = []
        for f in xml_saidas: list_s.extend(extrair_tags_estilo_query(f.read()))
        df_saidas = pd.DataFrame(list_s)
        df_saidas['AP'] = df_saidas['Chave de Acesso'].str.replace(r'\D', '', regex=True).map(status_dict).fillna("Pendente")

    # Processar Entradas
    df_entradas = pd.DataFrame()
    if xml_entradas:
        list_e = []
        for f in xml_entradas: list_e.extend(extrair_tags_estilo_query(f.read()))
        df_entradas = pd.DataFrame(list_e)
        df_entradas['AP'] = df_entradas['Chave de Acesso'].str.replace(r'\D', '', regex=True).map(status_dict).fillna("Pendente")

    # Aba Base_XML (Consolidado)
    df_base_xml = pd.concat([df_saidas, df_entradas], ignore_index=True)

    # Aba ICMS (Somente Saídas com Auditoria)
    df_icms = df_saidas.copy()
    if not df_icms.empty and df_tribut is not None:
        map_t = dict(zip(df_tribut.iloc[:, 0].astype(str), df_tribut.iloc[:, 2].astype(str)))
        map_g = dict(zip(df_gerencial.iloc[:, 0].astype(str), df_gerencial.iloc[:, 1].astype(str)))

        def auditar(row):
            status, cst, ncm = str(row['AP']), str(row['CST ICMS']).strip(), str(row['NCM']).strip()
            if "Cancelamento" in status: return "NF cancelada"
            esp = map_t.get(ncm)
            if not esp: return "NCM não encontrado"
            if cst == "60":
                return "Correto" if map_g.get(ncm) == "60" else f"Divergente — CST informado: 60 | Esperado: {esp}"
            return "Correto" if cst == esp else f"Divergente — CST informado: {cst} | Esperado: {esp}"

        df_icms['Análise CST ICMS'] = df_icms.apply(auditar, axis=1)

    # --- EXPORTAÇÃO ---
    st.success("Abas geradas com sucesso conforme o padrão aprovado!")
    buffer = io.BytesIO()
    with pd.ExcelWriter(buffer, engine='xlsxwriter') as writer:
        if not df_entradas.empty: df_entradas.to_excel(writer, index=False, sheet_name='Entradas')
        if not df_saidas.empty: df_saidas.to_excel(writer, index=False, sheet_name='Saídas')
        df_base_xml.to_excel(writer, index=False, sheet_name='Base_XML')
        df_icms.to_excel(writer, index=False, sheet_name='ICMS')

    st.download_button("📥 Baixar Sentinela Completa", buffer.getvalue(), "Sentinela_Auditada.xlsx")
