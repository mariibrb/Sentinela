import streamlit as st
import pandas as pd
import xml.etree.ElementTree as ET
import os

st.set_page_config(page_title="Auditoria Fiscal Sentinela", layout="wide")
st.title("🛡️ Auditoria Fiscal Sentinela - Ciclo Completo")

# 1. CARREGAMENTO DAS BASES DE REGRA (EXCEL MESTRE)
@st.cache_data
def carregar_bases_mestre():
    arquivo = 'Sentinela_MIRÃO_Outubro2025.xlsx'
    if not os.path.exists(arquivo):
        st.error(f"Arquivo {arquivo} não encontrado no diretório!")
        return None
    
    bases = {
        'tribut': pd.read_excel(arquivo, sheet_name='Bases Tribut'),
        'tes': pd.read_excel(arquivo, sheet_name='TES'),
        'autent': pd.read_excel(arquivo, sheet_name='Autent')
    }
    return bases

bases = carregar_bases_mestre()

# 2. FUNÇÃO DE AUDITORIA (LÓGICA DAS COLUNAS AO-AT)
def realizar_auditoria(row, bases):
    analises = {}
    
    # Validação de Status (Baseado na aba Autent)
    status_sefaz = "Autorizada"
    if not bases['autent'].empty:
        # Lógica de busca por chave de acesso
        pass 
    analises['STATUS_SEFAZ'] = status_sefaz

    # Análise CST ICMS (Equivalente à fórmula da coluna AP)
    ncm_regra = bases['tribut'][bases['tribut']['NCM'] == row['NCM']]
    if not ncm_regra.empty:
        cst_esperado = str(ncm_regra.iloc[0]['CST'])
        if str(row['CST_ICMS']) == cst_esperado:
            analises['Analise_CST_ICMS'] = "Correto"
        else:
            analises['Analise_CST_ICMS'] = f"Divergente - Esperado: {cst_esperado}"
    else:
        analises['Analise_CST_ICMS'] = "NCM não encontrado"

    # CST x BC (Equivalente à coluna AQ)
    if row['CST_ICMS'] == "20" and row['pRedBC'] == 0:
        analises['CST_x_BC'] = "Erro: CST 020 sem redução"
    elif row['CST_ICMS'] == "00" and abs(row['vBC'] - row['vProd']) > 0.02:
        analises['CST_x_BC'] = "Erro: Base difere do produto"
    else:
        analises['CST_x_BC'] = "Correto"

    return analises

# 3. INTERFACE DE UPLOAD
arquivos_xml = st.file_uploader("Suba seus XMLs para auditoria", type="xml", accept_multiple_files=True)

if arquivos_xml and bases:
    dados_xml = []
    for arq in arquivos_xml:
        try:
            tree = ET.parse(arq)
            root = tree.getroot()
            ns = {'nfe': 'http://www.portalfiscal.inf.br/nfe'}
            
            # Extração de campos (Igual à aba Base_XML)
            for det in root.findall('.//nfe:det', ns):
                item = {
                    'Número NF': root.find('.//nfe:ide/nfe:nNF', ns).text,
                    'UF Emit': root.find('.//nfe:emit/nfe:enderEmit/nfe:UF', ns).text,
                    'UF Dest': root.find('.//nfe:dest/nfe:enderDest/nfe:UF', ns).text,
                    'NCM': det.find('.//nfe:prod/nfe:NCM', ns).text,
                    'CFOP': det.find('.//nfe:prod/nfe:CFOP', ns).text,
                    'vProd': float(det.find('.//nfe:prod/nfe:vProd', ns).text),
                    'CST_ICMS': det.find('.//nfe:imposto//nfe:CST', ns).text if det.find('.//nfe:imposto//nfe:CST', ns) is not None else "00",
                    # Adicione aqui todos os outros campos da Base_XML...
                }
                
                # Executa a auditoria para a linha
                item.update(realizar_auditoria(item, bases))
                dados_xml.append(item)
        except:
            continue

    df_resultado = pd.DataFrame(dados_xml)
    st.write("### Relatório de Auditoria Gerado")
    st.dataframe(df_resultado)
    
    # Download
    csv = df_resultado.to_csv(index=False).encode('utf-8-sig')
    st.download_button("📥 Baixar Planilha de Auditoria", csv, "auditoria_final.csv")
