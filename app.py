import streamlit as st
import pandas as pd
import xml.etree.ElementTree as ET

st.set_page_config(page_title="Sentinela Fiscal", layout="wide")
st.title("🛡️ Auditoria Fiscal Sentinela")

# 1. Lendo a tua planilha que já está no GitHub
@st.cache_data
def carregar_regras():
    # Carregamos a aba 'Bases Tribut' que existe no teu ficheiro
    df = pd.read_excel("base_regras.xlsx", sheet_name='Bases Tribut')
    df['NCM_Limpo'] = df['NCM'].astype(str).str.replace('.0', '', regex=False).str.strip()
    return df

try:
    base_regras = carregar_regras()
    st.success("✅ Base de regras carregada!")
except:
    st.error("⚠️ Erro: Não encontrei a aba 'Bases Tribut' no ficheiro base_regras.xlsx")

# 2. Área para subires os teus 800 XMLs
arquivos_xml = st.file_uploader("Arraste aqui os seus arquivos XML", type="xml", accept_multiple_files=True)

if arquivos_xml:
    resultados = []
    for arq in arquivos_xml:
        tree = ET.parse(arq)
        root = tree.getroot()
        ns = {'nfe': 'http://www.portalfiscal.inf.br/nfe'}
        
        # Dados do XML
        nNF = root.find('.//nfe:ide/nfe:nNF', ns).text
        uf_emit = root.find('.//nfe:emit/nfe:enderEmit/nfe:UF', ns).text
        uf_dest = root.find('.//nfe:dest/nfe:enderDest/nfe:UF', ns).text
        cpf_dest = root.find('.//nfe:dest/nfe:CPF', ns)
        
        for det in root.findall('.//nfe:det', ns):
            ncm = det.find('.//nfe:prod/nfe:NCM', ns).text
            cfop = det.find('.//nfe:prod/nfe:CFOP', ns).text
            # Valor do DIFAL (se houver)
            difal = root.find('.//nfe:total/nfe:ICMSTot/nfe:vICMSUFDest', ns)
            v_difal = float(difal.text) if difal is not None else 0
            
            # TUA REGRA: Se for CPF e Interestadual
            analise = "OK"
            if cpf_dest is not None and uf_emit != uf_dest:
                if cfop != '6108':
                    analise = "ERRO: CFOP deve ser 6108"
                elif v_difal <= 0:
                    analise = "ERRO: DIFAL não destacado"
            
            resultados.append({
                'Nota': nNF, 'NCM': ncm, 'CFOP': cfop, 'Resultado': analise
            })

    df_res = pd.DataFrame(resultados)
    st.dataframe(df_res, use_container_width=True)
    
    # Botão para descarregar o resultado para Excel/CSV
    csv = df_res.to_csv(index=False).encode('utf-8-sig')
    st.download_button("📥 Baixar Relatório de Erros", csv, "auditoria.csv", "text/csv")
