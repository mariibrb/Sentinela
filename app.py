import streamlit as st
import pandas as pd
import xml.etree.ElementTree as ET

st.set_page_config(page_title="Sentinela Fiscal", layout="wide")
st.title("🛡️ Auditoria Fiscal Sentinela")

# 1. Lendo a tua planilha com tratamento de erro
@st.cache_data
def carregar_regras():
    try:
        # Tenta ler pelo nome que conhecemos
        xls = pd.ExcelFile("base_regras.xlsx")
        aba_alvo = 'Bases Tribut'
        
        # Se essa aba não existir, ele pega a primeira aba do arquivo
        if aba_alvo not in xls.sheet_names:
            aba_alvo = xls.sheet_names[0]
            
        df = pd.read_excel(xls, sheet_name=aba_alvo)
        # Limpeza básica do NCM
        if 'NCM' in df.columns:
            df['NCM_Limpo'] = df['NCM'].astype(str).str.replace('.0', '', regex=False).str.strip()
        return df
    except Exception as e:
        st.error(f"Erro ao abrir o arquivo: {e}")
        return None

base_regras = carregar_regras()

if base_regras is not None:
    st.success(f"✅ Base de regras carregada (Aba utilizada: {base_regras.index.name if base_regras.index.name else 'Principal'})")
else:
    st.stop() # Para o site aqui se não carregar a base

# 2. Área de Upload
arquivos_xml = st.file_uploader("Arraste aqui os seus arquivos XML", type="xml", accept_multiple_files=True)

if arquivos_xml:
    resultados = []
    for arq in arquivos_xml:
        try:
            tree = ET.parse(arq)
            root = tree.getroot()
            ns = {'nfe': 'http://www.portalfiscal.inf.br/nfe'}
            
            nNF = root.find('.//nfe:ide/nfe:nNF', ns).text
            uf_emit = root.find('.//nfe:emit/nfe:enderEmit/nfe:UF', ns).text
            uf_dest = root.find('.//nfe:dest/nfe:enderDest/nfe:UF', ns).text
            cpf_dest = root.find('.//nfe:dest/nfe:CPF', ns)
            
            for det in root.findall('.//nfe:det', ns):
                ncm = det.find('.//nfe:prod/nfe:NCM', ns).text
                cfop = det.find('.//nfe:prod/nfe:CFOP', ns).text
                difal = root.find('.//nfe:total/nfe:ICMSTot/nfe:vICMSUFDest', ns)
                v_difal = float(difal.text) if difal is not None else 0
                
                analise = "OK"
                if cpf_dest is not None and uf_emit != uf_dest:
                    if str(cfop) != '6108':
                        analise = "ERRO: CFOP deve ser 6108"
                    elif v_difal <= 0:
                        analise = "ERRO: DIFAL não destacado"
                
                resultados.append({
                    'Nota': nNF, 'NCM': ncm, 'CFOP': cfop, 'Resultado': analise
                })
        except Exception as e:
            st.warning(f"Erro ao ler um dos arquivos: {arq.name}")

    if resultados:
        df_res = pd.DataFrame(resultados)
        st.dataframe(df_res, use_container_width=True)
        csv = df_res.to_csv(index=False).encode('utf-8-sig')
        st.download_button("📥 Baixar Relatório", csv, "auditoria.csv", "text/csv")
