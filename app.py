import streamlit as st
import pandas as pd
import xml.etree.ElementTree as ET
import os

st.set_page_config(page_title="Sentinela Fiscal", layout="wide")
st.title("🛡️ Auditoria Fiscal Sentinela")

@st.cache_data
def carregar_regras():
    arquivos_excel = [f for f in os.listdir('.') if f.endswith('.xlsx')]
    if not arquivos_excel:
        st.error("❌ Erro: Planilha .xlsx não encontrada no GitHub!")
        return None
    try:
        xls = pd.ExcelFile(arquivos_excel[0])
        aba = 'Bases Tribut' if 'Bases Tribut' in xls.sheet_names else xls.sheet_names[0]
        df = pd.read_excel(xls, sheet_name=aba)
        st.success(f"✅ Base carregada: {arquivos_excel[0]}")
        return df
    except Exception as e:
        st.error(f"Erro: {e}")
        return None

base_regras = carregar_regras()

if base_regras is not None:
    arquivos_xml = st.file_uploader("Arraste seus XMLs aqui", type="xml", accept_multiple_files=True)

    if arquivos_xml:
        resultados = []
        for arq in arquivos_xml:
            try:
                tree = ET.parse(arq)
                root = tree.getroot()
                ns = {'nfe': 'http://www.portalfiscal.inf.br/nfe'}
                
                # Dados básicos da nota
                nf = root.find('.//nfe:ide/nfe:nNF', ns).text
                u_em = root.find('.//nfe:emit/nfe:enderEmit/nfe:UF', ns).text
                u_de = root.find('.//nfe:dest/nfe:enderDest/nfe:UF', ns).text
                cpf  = root.find('.//nfe:dest/nfe:CPF', ns)
                
                # Valor do DIFAL (tag completa em uma linha só para não dar erro)
                tag_difal = root.find('.//nfe:total/nfe:ICMSTot/nfe:vICMSUFDest', ns)
                v_difal = float(tag_difal.text) if tag_difal is not None else 0
                
                for det in root.findall('.//nfe:det', ns):
                    ncm = det.find('.//nfe:prod/nfe:NCM', ns).text
                    cfop = det.find('.//nfe:prod/nfe:CFOP', ns).text
                    
                    status = "OK"
                    # Regra: Se for CPF e Interestadual
                    if cpf is not None and u_em != u_de:
                        if str(cfop) != '6108':
                            status = "ERRO: CFOP esperado 6108"
                        elif v_difal <= 0:
                            status = "ERRO: DIFAL não destacado"
                    
                    resultados.append({'Nota': nf, 'NCM': ncm, 'CFOP': cfop, 'Status': status})
            except:
                continue

        if resultados:
            df_final = pd.DataFrame(resultados)
            st.dataframe(df_final, use_container_width=True)
            st.download_button("📥 Baixar Relatório", df_final.to_csv(index=False).encode('utf-8-sig'), "auditoria.csv")
