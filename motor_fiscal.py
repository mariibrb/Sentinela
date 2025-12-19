import pandas as pd
import numpy as np
import xml.etree.ElementTree as ET
import re
import io
import streamlit as st

def extrair_dados_xml(files, fluxo, df_autenticidade=None):
    dados_lista = []
    if not files: return pd.DataFrame()

    for f in files:
        try:
            f.seek(0)
            conteudo_bruto = f.read()
            texto_xml = conteudo_bruto.decode('utf-8', errors='replace')
            texto_xml = re.sub(r'<\?xml[^?]*\?>', '', texto_xml)
            texto_xml = re.sub(r'\sxmlns(:\w+)?="[^"]+"', '', texto_xml)
            root = ET.fromstring(texto_xml)
            
            def buscar(caminho, raiz=root):
                alvo = raiz.find(f'.//{caminho}')
                return alvo.text if alvo is not None and alvo.text is not None else ""

            inf_nfe = root.find('.//infNFe')
            chave_acesso = inf_nfe.attrib.get('Id', '')[3:] if inf_nfe is not None else ""
            
            for det in root.findall('.//det'):
                prod = det.find('prod')
                imp = det.find('imposto')
                ncm_limpo = re.sub(r'\D', '', buscar('NCM', prod)).zfill(8)
                
                linha = {
                    "CHAVE_ACESSO": chave_acesso, "NUM_NF": buscar('nNF'),
                    "DATA_EMISSAO": pd.to_datetime(buscar('dhEmi')).replace(tzinfo=None) if buscar('dhEmi') else None,
                    "UF_EMIT": buscar('UF', root.find('.//emit')), "UF_DEST": buscar('UF', root.find('.//dest')),
                    "AC": int(det.attrib.get('nItem', '0')), "CFOP": buscar('CFOP', prod), "NCM": ncm_limpo,
                    "COD_PROD": buscar('cProd', prod), "DESCR": buscar('xProd', prod),
                    "VPROD": float(buscar('vProd', prod)) if buscar('vProd', prod) else 0.0,
                    # ICMS
                    "CST-ICMS": "", "BC-ICMS": 0.0, "VLR-ICMS": 0.0, "ALQ-ICMS": 0.0, "ICMS-ST": 0.0,
                    # PIS/COFINS
                    "CST-PIS": "", "CST-COF": "", "VAL-PIS": 0.0, "VAL-COF": 0.0, "BC-FED": 0.0,
                    # IPI
                    "CST-IPI": "", "VAL-IPI": 0.0, "BC-IPI": 0.0, "ALQ-IPI": 0.0,
                    # DIFAL
                    "VAL-DIFAL": 0.0
                }

                if imp is not None:
                    # ICMS (Bloco preservado)
                    icms_nodo = imp.find('.//ICMS')
                    if icms_nodo is not None:
                        for nodo in icms_nodo:
                            cst = nodo.find('CST') if nodo.find('CST') is not None else nodo.find('CSOSN')
                            if cst is not None: linha["CST-ICMS"] = cst.text.zfill(2)
                            if nodo.find('vBC') is not None: linha["BC-ICMS"] = float(nodo.find('vBC').text)
                            if nodo.find('vICMS') is not None: linha["VLR-ICMS"] = float(nodo.find('vICMS').text)
                            if nodo.find('pICMS') is not None: linha["ALQ-ICMS"] = float(nodo.find('pICMS').text)
                            if nodo.find('vICMSST') is not None: linha["ICMS-ST"] = float(nodo.find('vICMSST').text)
                    
                    # PIS/COFINS (Bloco preservado)
                    pis = imp.find('.//PIS')
                    if pis is not None:
                        for p in pis:
                            if p.find('CST') is not None: linha["CST-PIS"] = p.find('CST').text.zfill(2)
                            if p.find('vBC') is not None: linha["BC-FED"] = float(p.find('vBC').text)
                            if p.find('vPIS') is not None: linha["VAL-PIS"] = float(p.find('vPIS').text)
                    cof = imp.find('.//COFINS')
                    if cof is not None:
                        for c in cof:
                            if c.find('CST') is not None: linha["CST-COF"] = c.find('CST').text.zfill(2)
                            if c.find('vCOFINS') is not None: linha["VAL-COF"] = float(c.find('vCOFINS').text)

                    # IPI (NOVO BLOCO LAPIDADO)
                    ipi_nodo = imp.find('.//IPI')
                    if ipi_nodo is not None:
                        cst_ipi = ipi_nodo.find('.//CST')
                        if cst_ipi is not None: linha["CST-IPI"] = cst_ipi.text.zfill(2)
                        if ipi_nodo.find('.//vBC') is not None: linha["BC-IPI"] = float(ipi_nodo.find('.//vBC').text)
                        if ipi_nodo.find('.//pIPI') is not None: linha["ALQ-IPI"] = float(ipi_nodo.find('.//pIPI').text)
                        if ipi_nodo.find('.//vIPI') is not None: linha["VAL-IPI"] = float(ipi_nodo.find('.//vIPI').text)

                dados_lista.append(linha)
        except: continue
    return pd.DataFrame(dados_lista)

def gerar_excel_final(df_ent, df_sai):
    def limpar_txt(v): return str(v).replace('.0', '').strip()
    
    # Bases de Dados
    try:
        base_icms = pd.read_excel(".streamlit/Base_ICMS.xlsx")
        base_icms['NCM_KEY'] = base_icms.iloc[:, 0].apply(limpar_txt).str.replace(r'\D', '', regex=True).str.zfill(8)
    except: base_icms = pd.DataFrame()

    try:
        base_pc = pd.read_excel(".streamlit/Base_CST_Pis_Cofins.xlsx")
        base_pc['NCM_KEY'] = base_pc.iloc[:, 0].apply(limpar_txt).str.replace(r'\D', '', regex=True).str.zfill(8)
        base_pc.columns = [c.upper() for c in base_pc.columns]
    except: base_pc = pd.DataFrame()

    if df_sai is None or df_sai.empty: df_sai = pd.DataFrame([{"AVISO": "Sem dados"}])
    def format_brl(v): return f"R$ {v:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")

    # --- AUDITORIA ICMS (Preservado) ---
    df_icms = df_sai.copy()
    def audit_icms(row):
        ncm = str(row['NCM']).zfill(8)
        info = base_icms[base_icms['NCM_KEY'] == ncm] if not base_icms.empty else pd.DataFrame()
        if info.empty: return pd.Series(["-", "NCM não mapeado", format_brl(row['VLR-ICMS']), "Cadastrar NCM"])
        cst_esp = str(info.iloc[0, 2]).zfill(2)
        diag = f"CST XML {row['CST-ICMS']} vs Base {cst_esp}" if str(row['CST-ICMS']) != cst_esp else "✅ Correto"
        acao = f"Cc-e (Corrigir CST para {cst_esp})" if str(row['CST-ICMS']) != cst_esp else "✅ Correto"
        return pd.Series(["-", diag, format_brl(row['VLR-ICMS']), acao])
    df_icms[['ST na Entrada', 'Diagnóstico', 'ICMS XML', 'Ação']] = df_icms.apply(audit_icms, axis=1)

    # --- AUDITORIA PIS/COFINS (Preservado) ---
    df_pc = df_sai.copy()
    def audit_pc(row):
        ncm = str(row['NCM']).zfill(8)
        info = base_pc[base_pc['NCM_KEY'] == ncm] if not base_pc.empty else pd.DataFrame()
        if info.empty: return pd.Series(["NCM não mapeado", "-", "-", "Cadastrar NCM"])
        try:
            cst_p_esp = str(info.iloc[0]['CST_PIS']).zfill(2)
            cst_c_esp = str(info.iloc[0]['CST_COFINS']).zfill(2)
        except: cst_p_esp, cst_c_esp = "01", "01"
        diag_list, acao_list = [], []
        if str(row['CST-PIS']) != cst_p_esp:
            diag_list.append(f"PIS: XML {row['CST-PIS']} vs Base {cst_p_esp}")
            acao_list.append(f"Cc-e (Corrigir CST PIS para {cst_p_esp})")
        if str(row['CST-COF']) != cst_c_esp:
            diag_list.append(f"COF: XML {row['CST-COF']} vs Base {cst_c_esp}")
            acao_list.append(f"Cc-e (Corrigir CST COF para {cst_c_esp})")
        res_diag = "; ".join(diag_list) if diag_list else "✅ CSTs Corretos"
        res_acao = " + ".join(acao_list) if acao_list else "✅ Correto"
        return pd.Series([res_diag, f"PIS: {row['CST-PIS']} / COF: {row['CST-COF']}", f"PIS: {cst_p_esp} / COF: {cst_c_esp}", res_acao])
    df_pc[['Diagnóstico', 'CST XML (P/C)', 'CST Esperado (P/C)', 'Ação']] = df_pc.apply(audit_pc, axis=1)

    # --- AUDITORIA IPI (NOVA LAPIDAÇÃO) ---
    df_ipi = df_sai.copy()
    def audit_ipi(row):
        ncm = str(row['NCM']).zfill(8)
        # Usando a base de PIS/COFINS que costuma ter o IPI, ou a de ICMS
        info = base_pc[base_pc['NCM_KEY'] == ncm] if not base_pc.empty else pd.DataFrame()
        
        if info.empty: 
            return pd.Series(["NCM não mapeado", format_brl(row['VAL-IPI']), "Cadastrar NCM"])
        
        # Procura coluna CST_IPI na base
        try:
            cst_i_esp = str(info.iloc[0]['CST_IPI']).zfill(2)
        except:
            cst_i_esp = "50" # Padrão saída tributada se não achar

        diag_ipi = "✅ Correto"
        acao_ipi = "✅ Correto"
        
        if str(row['CST-IPI']) != cst_i_esp:
            diag_ipi = f"CST IPI: XML {row['CST-IPI']} vs Base {cst_i_esp}"
            acao_ipi = f"Cc-e (Corrigir CST IPI para {cst_i_esp})"
        
        return pd.Series([diag_ipi, format_brl(row['VAL-IPI']), acao_ipi])

    df_ipi[['Diagnóstico', 'IPI XML', 'Ação']] = df_ipi.apply(audit_ipi, axis=1)

    # --- ABA DIFAL ---
    df_difal = df_sai.copy()

    mem = io.BytesIO()
    with pd.ExcelWriter(mem, engine='xlsxwriter') as wr:
        df_sai.to_excel(wr, sheet_name='SAIDAS', index=False)
        df_icms.to_excel(wr, sheet_name='ICMS', index=False)
        df_pc.to_excel(wr, sheet_name='PIS_COFINS', index=False)
        df_ipi.to_excel(wr, sheet_name='IPI', index=False)
        df_difal.to_excel(wr, sheet_name='DIFAL', index=False)
    return mem.getvalue()
