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
            texto_xml = re.sub(r'\sxmlns(:\w+)?="[^"]+"', '', texto_xml)
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
                
                # Blindagem: NCM sempre com 8 dígitos para o Procv funcionar
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
    
    # 1. Mapeamento opcional de entradas (Bônus)
    ncms_ent_st = []
    if df_ent is not None and not df_ent.empty:
        ncms_ent_st = df_ent[(df_ent['CST-ICMS']=="60") | (df_ent['ICMS-ST'] > 0)]['NCM'].unique().tolist()

    def format_brl(v): return f"R$ {v:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")

    def auditoria_soberana(row):
        ncm_atual = str(row['NCM']).strip().zfill(8)
        info_ncm = base_t[base_t['NCM_KEY'] == ncm_atual]
        
        # Validação de Base: Sempre ocorre primeiro
        if info_ncm.empty:
            return pd.Series([f"NCM {ncm_atual} Ausente na Base", format_brl(row['VLR-ICMS']), "R$ 0,00", "Cadastrar NCM", "R$ 0,00", "Não"])

        cst_esp = str(info_ncm.iloc[0, 2]).zfill(2)
        is_interna = row['UF_EMIT'] == row['UF_DEST']
        aliq_esp = float(info_ncm.iloc[0, 3]) if is_interna else (float(info_ncm.iloc[0, 29]) if len(info_ncm.columns) > 29 else 12.0)

        diag_list = []
        cst_xml = str(row['CST-ICMS']).strip()

        # AUDITORIA INDEPENDENTE DE SAÍDA (O XML contra a sua Base)
        if cst_xml == "60":
            if row['VLR-ICMS'] > 0: 
                diag_list.append(f"CST 60: Destacado {format_brl(row['VLR-ICMS'])} | Esperado R$ 0,00")
            
            # Validação de Entrada: Só gera alerta SE os arquivos de entrada existirem e o NCM não estiver lá
            if df_ent is not None and not df_ent.empty and ncm_atual not in ncms_ent_st:
                diag_list.append(f"Analisar: NCM {ncm_atual} sem estoque ST (Entradas)")
            
            aliq_esp = 0.0
        else:
            if aliq_esp > 0 and row['VLR-ICMS'] == 0: 
                diag_list.append(f"ICMS: Destacado R$ 0,00 | Esperado {aliq_esp}%")
            if cst_xml != cst_esp: 
                diag_list.append(f"CST: Destacado {cst_xml} | Esperado {cst_esp}")
            if row['ALQ-ICMS'] != aliq_esp and aliq_esp > 0: 
                diag_list.append(f"Aliq: Destacada {row['ALQ-ICMS']}% | Esperada {aliq_esp}%")

        complemento_num = (aliq_esp - row['ALQ-ICMS']) * row['BC-ICMS'] / 100 if (row['ALQ-ICMS'] < aliq_esp and cst_xml != "60") else 0.0
        res = "; ".join(diag_list) if diag_list else "✅ Correto"
        
        # Definição de Ação Curta
        if res == "✅ Correto": acao = "✅ Correto"
        elif "Analisar" in res: acao = "Validar Entrada"
        elif "CST" in res and complemento_num == 0: acao = "Cc-e"
        else: acao = "Complemento/Estorno"

        cce = "Sim" if acao == "Cc-e" else "Não"
        return pd.Series([res, format_brl(row['VLR-ICMS']), format_brl(row['BC-ICMS'] * aliq_esp / 100 if aliq_esp > 0 else 0), acao, format_brl(complemento_num), cce])

    df_icms_audit[['Diagnóstico', 'ICMS XML', 'ICMS Esperado', 'Ação', 'Complemento', 'Cc-e']] = df_icms_audit.apply(auditoria_soberana, axis=1)

    mem = io.BytesIO()
    with pd.ExcelWriter(mem, engine='xlsxwriter') as wr:
        if df_ent is not None and not df_ent.empty:
            df_ent.to_excel(wr, sheet_name='ENTRADAS', index=False)
        df_sai.to_excel(wr, sheet_name='SAIDAS', index=False)
        df_icms_audit.to_excel(wr, sheet_name='ICMS', index=False)
        for aba in ['IPI', 'PIS_COFINS', 'DIFAL']: df_sai.to_excel(wr, sheet_name=aba, index=False)
    return mem.getvalue()
