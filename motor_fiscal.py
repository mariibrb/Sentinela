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
                    "CST-ICMS": "", "BC-ICMS": 0.0, "VLR-ICMS": 0.0, "ALQ-ICMS": 0.0, "ICMS-ST": 0.0,
                    "CST-PIS": "", "CST-COF": "", "VAL-PIS": 0.0, "VAL-COF": 0.0, "BC-FED": 0.0,
                    "CST-IPI": "", "VAL-IPI": 0.0, "BC-IPI": 0.0, "ALQ-IPI": 0.0,
                    "VAL-DIFAL": 0.0
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

                    ipi_nodo = imp.find('.//IPI')
                    if ipi_nodo is not None:
                        cst_i = ipi_nodo.find('.//CST')
                        if cst_i is not None: linha["CST-IPI"] = cst_i.text.zfill(2)
                        if ipi_nodo.find('.//vBC') is not None: linha["BC-IPI"] = float(ipi_nodo.find('.//vBC').text)
                        if ipi_nodo.find('.//pIPI') is not None: linha["ALQ-IPI"] = float(ipi_nodo.find('.//pIPI').text)
                        if ipi_nodo.find('.//vIPI') is not None: linha["VAL-IPI"] = float(ipi_nodo.find('.//vIPI').text)

                    difal_nodo = imp.find('.//ICMSUFDest')
                    if difal_nodo is not None:
                        v_difal = difal_nodo.find('vICMSUFDest')
                        if v_difal is not None: linha["VAL-DIFAL"] = float(v_difal.text)

                dados_lista.append(linha)
        except: continue
    return pd.DataFrame(dados_lista)

def gerar_excel_final(df_ent, df_sai):
    def limpar_txt(v): return str(v).replace('.0', '').strip()
    def format_brl(v): return f"R$ {v:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
    
    try:
        base_icms = pd.read_excel(".streamlit/Base_ICMS.xlsx")
        base_icms['NCM_KEY'] = base_icms.iloc[:, 0].apply(limpar_txt).str.replace(r'\D', '', regex=True).str.zfill(8)
        base_icms['CST_KEY'] = base_icms.iloc[:, 2].apply(limpar_txt).str.zfill(2)
    except: base_icms = pd.DataFrame()

    try:
        base_pc = pd.read_excel(".streamlit/Base_CST_Pis_Cofins.xlsx")
        base_pc['NCM_KEY'] = base_pc.iloc[:, 0].apply(limpar_txt).str.replace(r'\D', '', regex=True).str.zfill(8)
        base_pc.columns = [c.upper() for c in base_pc.columns]
    except: base_pc = pd.DataFrame()

    if df_sai is None or df_sai.empty: df_sai = pd.DataFrame([{"AVISO": "Sem dados"}])

    # --- ABA ICMS ---
    df_icms_audit = df_sai.copy()
    tem_entradas = df_ent is not None and not df_ent.empty
    ncms_ent_st = df_ent[(df_ent['CST-ICMS']=="60") | (df_ent['ICMS-ST'] > 0)]['NCM'].unique().tolist() if tem_entradas else []
    def audit_icms(row):
        ncm = str(row['NCM']).zfill(8); info = base_icms[base_icms['NCM_KEY'] == ncm] if not base_icms.empty else pd.DataFrame()
        st_e = "✅ ST Localizado" if ncm in ncms_ent_st else "❌ Sem ST na Entrada" if tem_entradas else "⚠️ Entrada não enviada"
        if info.empty: return pd.Series([st_e, "NCM Ausente", format_brl(row['VLR-ICMS']), "R$ 0,00", "Cadastrar NCM", "R$ 0,00"])
        cst_e, aliq_e = str(info.iloc[0]['CST_KEY']), float(info.iloc[0, 3]) if row['UF_EMIT'] == row['UF_DEST'] else 12.0
        diag, acao = [], []
        if str(row['CST-ICMS']).zfill(2) != cst_e.zfill(2): diag.append("CST: Divergente"); acao.append(f"Cc-e (CST {cst_e})")
        if abs(row['ALQ-ICMS'] - aliq_e) > 0.01: diag.append("Aliq: Divergente"); acao.append("Ajustar Alíquota")
        return pd.Series([st_e, "; ".join(diag) if diag else "✅ Correto", format_brl(row['VLR-ICMS']), format_brl(row['BC-ICMS']*aliq_e/100), " + ".join(acao) if acao else "✅ Correto", format_brl(max(0, (aliq_e - row['ALQ-ICMS']) * row['BC-ICMS'] / 100))])
    df_icms_audit[['ST na Entrada', 'Diagnóstico', 'ICMS XML', 'ICMS Esperado', 'Ação', 'Complemento']] = df_icms_audit.apply(audit_icms, axis=1)

    # --- ABA PIS/COFINS ---
    df_pc = df_sai.copy()
    def audit_pc(row):
        ncm = str(row['NCM']).zfill(8); info = base_pc[base_pc['NCM_KEY'] == ncm] if not base_pc.empty else pd.DataFrame()
        if info.empty: return pd.Series(["NCM não mapeado", f"P/C: {row['CST-PIS']}/{row['CST-COF']}", "-", "Cadastrar NCM"])
        try: cp_e, cc_e = str(info.iloc[0]['CST_PIS']).zfill(2), str(info.iloc[0]['CST_COFINS']).zfill(2)
        except: cp_e, cc_e = "01", "01"
        diag, acao = [], []
        if str(row['CST-PIS']) != cp_e: diag.append("PIS: Divergente"); acao.append(f"Cc-e (CST PIS {cp_e})")
        if str(row['CST-COF']) != cc_e: diag.append("COF: Divergente"); acao.append(f"Cc-e (CST COF {cc_e})")
        return pd.Series(["; ".join(diag) if diag else "✅ Correto", f"P/C: {row['CST-PIS']}/{row['CST-COF']}", f"P/C: {cp_e}/{cc_e}", " + ".join(acao) if acao else "✅ Correto"])
    df_pc[['Diagnóstico', 'CST XML (P/C)', 'CST Esperado (P/C)', 'Ação']] = df_pc.apply(audit_pc, axis=1)

    # --- ABA IPI ---
    df_ipi = df_sai.copy()
    def audit_ipi(row):
        ncm = str(row['NCM']).zfill(8); info = base_pc[base_pc['NCM_KEY'] == ncm] if not base_pc.empty else pd.DataFrame()
        if info.empty: return pd.Series(["NCM não mapeado", row['CST-IPI'], "-", format_brl(row['VAL-IPI']), "R$ 0,00", "Cadastrar NCM", "R$ 0,00"])
        try: ci_e, ai_e = str(info.iloc[0]['CST_IPI']).zfill(2), float(info.iloc[0]['ALQ_IPI'])
        except: ci_e, ai_e = "50", 0.0
        v_e = row['BC-IPI'] * (ai_e / 100); diag, acao = [], []
        if str(row['CST-IPI']) != ci_e: diag.append("CST: Divergente"); acao.append(f"Cc-e (CST IPI {ci_e})")
        if abs(row['VAL-IPI'] - v_e) > 0.01: diag.append("Valor: Divergente"); acao.append("Complementar" if row['VAL-IPI'] < v_e else "Estornar")
        return pd.Series(["; ".join(diag) if diag else "✅ Correto", row['CST-IPI'], ci_e, format_brl(row['VAL-IPI']), format_brl(v_e), " + ".join(acao) if acao else "✅ Correto", format_brl(max(0, v_e - row['VAL-IPI']))])
    df_ipi[['Diagnóstico', 'CST XML', 'CST Base', 'IPI XML', 'IPI Esperado', 'Ação', 'Complemento']] = df_ipi.apply(audit_ipi, axis=1)

    # --- ABA DIFAL (AJUSTADA: ✅ CORRETO NO DIAGNÓSTICO E NA AÇÃO) ---
    df_difal = df_sai.copy()
    def audit_difal(row):
        is_inter = row['UF_EMIT'] != row['UF_DEST']
        cfop = str(row['CFOP'])
        cfops_difal_obrigatorio = ['6107', '6108', '6933', '6404']
        diag, acao = [], []
        
        if is_inter:
            if cfop in cfops_difal_obrigatorio:
                if row['VAL-DIFAL'] == 0:
                    diag.append(f"CFOP {cfop}: DIFAL Obrigatório")
                    acao.append("Emitir Complementar de DIFAL")
                else: 
                    diag.append("✅ Correto")
                    acao.append("✅ Correto")
            else: 
                diag.append("✅ Correto") # Operação interestadual que não exige DIFAL obrigatoriamente
                acao.append("✅ Correto")
        else:
            diag.append("✅ Correto") # Operação interna
            acao.append("✅ Correto")
            
        return pd.Series(["; ".join(diag), format_brl(row['VAL-DIFAL']), "; ".join(acao)])

    df_difal[['Diagnóstico', 'DIFAL XML', 'Ação']] = df_difal.apply(audit_difal, axis=1)

    mem = io.BytesIO()
    with pd.ExcelWriter(mem, engine='xlsxwriter') as wr:
        if tem_entradas: df_ent.to_excel(wr, sheet_name='ENTRADAS', index=False)
        df_sai.to_excel(wr, sheet_name='SAIDAS', index=False)
        df_icms_audit.to_excel(wr, sheet_name='ICMS', index=False)
        df_pc.to_excel(wr, sheet_name='PIS_COFINS', index=False)
        df_ipi.to_excel(wr, sheet_name='IPI', index=False)
        df_difal.to_excel(wr, sheet_name='DIFAL', index=False)
    return mem.getvalue()
