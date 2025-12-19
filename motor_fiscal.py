import pandas as pd
import xml.etree.ElementTree as ET
import re
import io
import streamlit as st

def extrair_dados_xml(files, fluxo, df_autenticidade=None):
    dados_lista = []
    if not files: 
        return pd.DataFrame()

    container_status = st.empty()
    progresso = st.progress(0)
    total_arquivos = len(files)
    
    for i, f in enumerate(files):
        try:
            f.seek(0)
            conteudo_bruto = f.read()
            texto_xml = conteudo_bruto.decode('utf-8', errors='replace')
            texto_xml = re.sub(r'<\?xml[^?]*\?>', '', texto_xml)
            root = ET.fromstring(texto_xml)
            
            def buscar(caminho, raiz=root):
                alvo = raiz.find(f'.//{caminho}')
                return alvo.text if alvo is not None and alvo.text is not None else ""

            inf_nfe = root.find('.//infNFe')
            chave_acesso = inf_nfe.attrib.get('Id', '')[3:] if inf_nfe is not None else ""
            num_nf = buscar('nNF')
            data_emi = buscar('dhEmi')
            
            emit_uf = buscar('UF', root.find('.//emit'))
            dest_uf = buscar('UF', root.find('.//dest'))
            
            for det in root.findall('.//det'):
                prod = det.find('prod')
                imp = det.find('imposto')
                
                # Blindagem: NCM com 8 dígitos para garantir o Procv
                ncm_limpo = re.sub(r'\D', '', buscar('NCM', prod)).zfill(8)
                
                linha = {
                    "CHAVE_ACESSO": chave_acesso, "NUM_NF": num_nf,
                    "DATA_EMISSAO": pd.to_datetime(data_emi).replace(tzinfo=None) if data_emi else None,
                    "UF_EMIT": emit_uf, "UF_DEST": dest_uf, "AC": int(det.attrib.get('nItem', '0')),
                    "CFOP": buscar('CFOP', prod), "NCM": ncm_limpo,
                    "COD_PROD": buscar('cProd', prod), "DESCR": buscar('xProd', prod),
                    "VPROD": float(buscar('vProd', prod)) if buscar('vProd', prod) else 0.0,
                    "FRETE": float(buscar('vFrete', prod)) if buscar('vFrete', prod) else 0.0,
                    "SEG": float(buscar('vSeg', prod)) if buscar('vSeg', prod) else 0.0,
                    "DESP": float(buscar('vOutro', prod)) if buscar('vOutro', prod) else 0.0,
                    "DESC": float(buscar('vDesc', prod)) if buscar('vDesc', prod) else 0.0,
                    "CST-ICMS": "", "BC-ICMS": 0.0, "VLR-ICMS": 0.0, "ALQ-ICMS": 0.0,
                    "BC-ICMS-ST": 0.0, "ICMS-ST": 0.0, "pRedBC": 0.0, "STATUS": ""
                }

                if imp is not None:
                    icms_nodo = imp.find('.//ICMS')
                    if icms_nodo is not None:
                        for nodo in icms_nodo:
                            cst = nodo.find('CST') if nodo.find('CST') is not None else nodo.find('CSOSN')
                            if cst is not None: linha["CST-ICMS"] = cst.text.zfill(2)
                            if nodo.find('vBC') is not None: linha["BC-ICMS"] = float(nodo.find('vBC').text)
                            if nodo.find('vICMS') is not None: linha["VLR-ICMS"] = float(nodo.find('vICMS').text)
                            if nodo.find('pICMS') is not None: linha["ALQ-ICMS"] = float(nodo.find('pICMS').text)

                linha["VC"] = linha["VPROD"] + linha["ICMS-ST"] + linha["DESP"] - linha["DESC"]
                dados_lista.append(linha)
            progresso.progress((i + 1) / total_arquivos)
        except: continue
    
    return pd.DataFrame(dados_lista)

def gerar_excel_final(df_ent, df_sai):
    try:
        base_t = pd.read_excel(".streamlit/Base_ICMS.xlsx")
        base_t['NCM_KEY'] = base_t.iloc[:, 0].astype(str).str.replace(r'\D', '', regex=True).str.zfill(8).str.strip()
    except: 
        base_t = pd.DataFrame(columns=['NCM_KEY'])

    if df_sai is None or df_sai.empty: 
        return None

    df_icms_audit = df_sai.copy()
    
    # Mapeamento do Bônus: ST na Entrada
    tem_entradas = df_ent is not None and not df_ent.empty
    ncms_ent_st = []
    if tem_entradas:
        # Considera NCMs que entraram com CST 60 ou valor de ICMS ST destacado
        ncms_ent_st = df_ent[(df_ent['CST-ICMS']=="60") | (df_ent['ICMS-ST'] > 0)]['NCM'].unique().tolist()

    def format_brl(v): return f"R$ {v:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")

    def auditoria_final(row):
        ncm_atual = str(row['NCM']).strip().zfill(8)
        info_ncm = base_t[base_t['NCM_KEY'] == ncm_atual]
        
        # 1. Coluna Bônus: Validação de ST na Entrada (Independente do NCM na Base)
        if tem_entradas:
            st_entrada = "✅ ST Localizado" if ncm_atual in ncms_ent_st else "❌ Sem ST na Entrada"
        else:
            st_entrada = "⚠️ XMLs de Entrada não carregados"
            
        # 2. Validação da Base
        if info_ncm.empty:
            return pd.Series([st_entrada, f"NCM {ncm_atual} Ausente na Base", format_brl(row['VLR-ICMS']), "R$ 0,00", "Cadastrar NCM", "R$ 0,00", "Não"])

        cst_esp = str(info_ncm.iloc[0, 2]).zfill(2)
        is_interna = row['UF_EMIT']
