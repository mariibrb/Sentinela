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
                    # Campos ICMS
                    "CST-ICMS": "", "BC-ICMS": 0.0, "VLR-ICMS": 0.0, "ALQ-ICMS": 0.0, "ICMS-ST": 0.0,
                    # Campos PIS/COFINS/IPI/DIFAL
                    "VBC-PIS": 0.0, "VAL-PIS": 0.0, "VBC-COF": 0.0, "VAL-COF": 0.0,
                    "VBC-IPI": 0.0, "VAL-IPI": 0.0, "VAL-DIFAL": 0.0
                }

                if imp is not None:
                    # ICMS
                    icms_nodo = imp.find('.//ICMS')
                    if icms_nodo is not None:
                        for nodo in icms_nodo:
                            cst = nodo.find('CST') if nodo.find('CST') is not None else nodo.find('CSOSN')
                            if cst is not None: linha["CST-ICMS"] = cst.text.zfill(2)
                            if nodo.find('vBC') is not None: linha["BC-ICMS"] = float(nodo.find('vBC').text)
                            if nodo.find('vICMS') is not None: linha["VLR-ICMS"] = float(nodo.find('vICMS').text)
                            if nodo.find('pICMS') is not None: linha["ALQ-ICMS"] = float(nodo.find('pICMS').text)
                            if nodo.find('vICMSST') is not None: linha["ICMS-ST"] = float(nodo.find('vICMSST').text)
                    
                    # PIS
                    pis = imp.find('.//PIS')
                    if pis is not None:
                        if pis.find('.//vBC') is not None: linha["VBC-PIS"] = float(pis.find('.//vBC').text)
                        if pis.find('.//vPIS') is not None: linha["VAL-PIS"] = float(pis.find('.//vPIS').text)
                    
                    # COFINS
                    cof = imp.find('.//COFINS')
                    if cof is not None:
                        if cof.find('.//vBC') is not None: linha["VBC-COF"] = float(cof.find('.//vBC').text)
                        if cof.find('.//vCOFINS') is not None: linha["VAL-COF"] = float(cof.find('.//vCOFINS').text)

                    # IPI
                    ipi = imp.find('.//IPI')
                    if ipi is not None:
                        if ipi.find('.//vBC') is not None: linha["VBC-IPI"] = float(ipi.find('.//vBC').text)
                        if ipi.find('.//vIPI') is not None: linha["VAL-IPI"] = float(ipi.find('.//vIPI').text)

                    # DIFAL
                    difal = imp.find('.//ICMSUFDest')
                    if difal is not None:
                        if difal.find('vICMSUFDest') is not None: linha["VAL-DIFAL"] = float(difal.find('vICMSUFDest').text)

                dados_lista.append(linha)
        except: continue
    return pd.DataFrame(dados_lista)

def gerar_excel_final(df_ent, df_sai):
    try:
        base_t = pd.read_excel(".streamlit/Base_ICMS.xlsx")
        def limpar_texto(val): return str(val).replace('.0', '').strip()
        base_t['NCM_KEY'] = base_t.iloc[:, 0].apply(limpar_texto).str.replace(r'\D', '', regex=True).str.zfill(8)
        base_t['CST_KEY'] = base_t.iloc[:, 2].apply(limpar_texto).str.zfill(2)
    except: 
        base_t = pd.DataFrame(columns=['NCM_KEY', 'CST_KEY'])

    if df_sai is None or df_sai.empty: 
        df_sai = pd.DataFrame([{"AVISO": "Nenhum dado de Saída processado"}])

    # --- AUDITORIA ICMS ---
    df_icms_audit = df_sai.copy()
    tem_entradas = df_ent is not None and not df_ent.empty
    ncms_ent_st = df_ent[(df_ent['CST-ICMS']=="60") | (df_ent['ICMS-ST'] > 0)]['NCM'].unique().tolist() if tem_entradas else []

    def format_brl(v): return f"R$ {v:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")

    def auditoria_final(row):
        if "AVISO" in row: return pd.Series(["-"] * 6)
        ncm_atual = str(row['NCM']).strip().zfill(8)
        info_ncm = base_t[base_t['NCM_KEY'] == ncm_atual]
        st_entrada = ("✅ ST Localizado" if ncm_atual in ncms_ent_st else "❌ Sem ST na Entrada") if tem_entradas else "⚠️ Entrada não enviada"
        if info_ncm.empty:
            return pd.Series([st_entrada, f"NCM {ncm_atual} Ausente na Base", format_brl(row['VLR-ICMS']), "R$ 0,00", "Cadastrar NCM na Base", "R$ 0,00"])
        cst_esp = str(info_ncm.iloc[0]['CST_KEY'])
        aliq_esp = float(info_ncm.iloc[0, 3]) if row['UF_EMIT'] == row['UF_DEST'] else (float(info_ncm.iloc[0, 29]) if len(info_ncm.columns) > 29 else 12.0)
        cst_xml = str(row['CST-ICMS']).strip().zfill(2)
        diag_list, acoes_list = [], []
        if cst_xml == "60":
            if row['VLR-ICMS'] > 0: 
                diag_list.append(f"CST 60 com destaque: {format_brl(row['VLR-ICMS'])} | Esperado R$ 0,00")
                acoes_list.append("Estorno de ICMS destacado indevidamente")
            aliq_esp = 0.0
        else:
            if aliq_esp > 0 and row['VLR-ICMS'] == 0: 
                diag_list.append(f"ICMS: Destacado R$ 0,00 | Esperado {aliq_esp}%")
                acoes_list.append("Emitir NF Complementar de Imposto")
            if cst_xml != cst_esp: 
                diag_list.append(f"CST: Destacado {cst_xml} | Esperado {cst_esp}")
                acoes_list.append(f"Cc-e (Corrigir CST para {cst_esp})")
            if abs(row['ALQ-ICMS'] - aliq_esp) > 0.01 and aliq_esp > 0: 
                diag_list.append(f"Aliq: Destacada {row['ALQ-ICMS']}% | Esperada {aliq_esp}%")
                acoes_list.append("Ajustar parâmetro de Alíquota no ERP")
        comp_num = (aliq_esp - row['ALQ-ICMS']) * row['BC-ICMS'] / 100 if (row['ALQ-ICMS'] < aliq_esp and cst_xml != "60") else 0.0
        res = "; ".join(diag_list) if diag_list else "✅ Correto"
        acao = " + ".join(list(dict.fromkeys(acoes_list))) if acoes_list else "✅ Correto"
        return pd.Series([st_entrada, res, format_brl(row['VLR-ICMS']), format_brl(row['BC-ICMS'] * aliq_esp / 100 if aliq_esp > 0 else 0), acao, format_brl(comp_num)])

    df_icms_audit[['ST na Entrada', 'Diagnóstico', 'ICMS XML', 'ICMS Esperado', 'Ação', 'Complemento']] = df_icms_audit.apply(auditoria_final, axis=1)

    # --- ABAS DE TRIBUTOS FEDERAIS E DIFAL ---
    # PIS e COFINS
    df_pis_cofins = df_sai.copy()
    if not df_pis_cofins.empty and "AVISO" not in df_pis_cofins.columns:
        df_pis_cofins['Análise PIS'] = np.where(df_pis_cofins['VAL-PIS'] > 0, "✅ Destacado", "ℹ️ Sem destaque")
        df_pis_cofins['Análise COFINS'] = np.where(df_pis_cofins['VAL-COF'] > 0, "✅ Destacado", "ℹ️ Sem destaque")

    # IPI
    df_ipi = df_sai.copy()
    if not df_ipi.empty and "AVISO" not in df_ipi.columns:
        df_ipi['Análise IPI'] = "" # Coluna vazia conforme solicitado

    # DIFAL
    df_difal = df_sai.copy()
    if not df_difal.empty and "AVISO" not in df_difal.columns:
        df_difal['Análise DIFAL'] = np.where((df_difal['UF_EMIT'] != df_difal['UF_DEST']) & (df_difal['VAL-DIFAL'] == 0), "❌ DIFAL não localizado", "✅ OK ou Interna")

    mem = io.BytesIO()
    with pd.ExcelWriter(mem, engine='xlsxwriter') as wr:
        if tem_entradas: df_ent.to_excel(wr, sheet_name='ENTRADAS', index=False)
        df_sai.to_excel(wr, sheet_name='SAIDAS', index=False)
        df_icms_audit.to_excel(wr, sheet_name='ICMS', index=False)
        df_ipi.to_excel(wr, sheet_name='IPI', index=False)
        df_pis_cofins.to_excel(wr, sheet_name='PIS_COFINS', index=False)
        df_difal.to_excel(wr, sheet_name='DIFAL', index=False)
    return mem.getvalue()
