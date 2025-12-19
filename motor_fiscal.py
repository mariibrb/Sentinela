import pandas as pd
import xml.etree.ElementTree as ET
import re
import io
import streamlit as st

def extrair_dados_xml(files, fluxo, df_autenticidade=None):
    dados_lista = []
    if not files: return pd.DataFrame()

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
            
            # Dados do Emitente e Destinatário para lógica Interestadual
            emit_uf = buscar('UF', root.find('.//emit'))
            dest_uf = buscar('UF', root.find('.//dest'))
            
            itens = root.findall('.//det')
            for det in itens:
                prod = det.find('prod')
                imp = det.find('imposto')
                n_item = det.attrib.get('nItem', '0')
                
                linha = {
                    "CHAVE_ACESSO": chave_acesso, "NUM_NF": num_nf,
                    "DATA_EMISSAO": pd.to_datetime(data_emi).replace(tzinfo=None) if data_emi else None,
                    "UF_EMIT": emit_uf, "UF_DEST": dest_uf, "AC": int(n_item),
                    "CFOP": buscar('CFOP', prod), "NCM": buscar('NCM', prod),
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
                    icms_data = imp.find('.//ICMS')
                    if icms_data is not None:
                        for nodo in icms_data:
                            cst = nodo.find('CST') if nodo.find('CST') is not None else nodo.find('CSOSN')
                            if cst is not None: linha["CST-ICMS"] = cst.text.zfill(2)
                            if nodo.find('vBC') is not None: linha["BC-ICMS"] = float(nodo.find('vBC').text)
                            if nodo.find('vICMS') is not None: linha["VLR-ICMS"] = float(nodo.find('vICMS').text)
                            if nodo.find('pICMS') is not None: linha["ALQ-ICMS"] = float(nodo.find('pICMS').text)
                            if nodo.find('pRedBC') is not None: linha["pRedBC"] = float(nodo.find('pRedBC').text)
                            if nodo.find('vBCST') is not None: linha["BC-ICMS-ST"] = float(nodo.find('vBCST').text)
                            if nodo.find('vICMSST') is not None: linha["ICMS-ST"] = float(nodo.find('vICMSST').text)

                dados_lista.append(linha)
            
            progresso.progress((i + 1) / total_arquivos)
        except: continue
    
    df_res = pd.DataFrame(dados_lista)
    if not df_res.empty and df_autenticidade is not None:
        df_res['CHAVE_ACESSO'] = df_res['CHAVE_ACESSO'].astype(str).str.strip()
        map_auth = dict(zip(df_autenticidade.iloc[:, 0].astype(str).str.strip(), df_autenticidade.iloc[:, 5]))
        df_res['STATUS'] = df_res['CHAVE_ACESSO'].map(map_auth).fillna("Não encontrada")

    return df_res

def gerar_excel_final(df_ent, df_sai):
    # Carregando as bases de apoio para o PROCV
    try:
        base_tribut = pd.read_excel(".streamlit/Base_ICMS.xlsx")
        base_tribut['NCM'] = base_tribut.iloc[:, 0].astype(str).str.strip() # Col A
    except:
        base_tribut = pd.DataFrame(columns=['NCM'])

    df_icms_audit = df_sai.copy() if not df_sai.empty else pd.DataFrame()

    if not df_icms_audit.empty:
        # Preparação dos dados para a lógica do PROCV
        ncms_entrada_60 = []
        if not df_ent.empty:
            ncms_entrada_60 = df_ent[df_ent['CST-ICMS'] == "60"]['NCM'].unique().tolist()

        def auditoria_expert(row):
            status_nota = str(row['STATUS'])
            if "Cancelamento" in status_nota or "Cancelada" in status_nota:
                return pd.Series(["NF Cancelada", "R$ 0,00", "R$ 0,00", "Não se aplica", "NF Cancelada"])

            # Busca no PROCV (Base Tributária)
            info_ncm = base_tribut[base_tribut['NCM'] == str(row['NCM']).strip()]
            cst_esperado = str(info_ncm.iloc[0, 2]).zfill(2) if not info_ncm.empty else "NCM não encontrado"
            alq_esperada = float(info_ncm.iloc[0, 3]) if not info_ncm.empty else 0.0

            mensagens = []
            
            # --- LÓGICA 1: VALIDAÇÃO DE CST ---
            cst_atual = str(row['CST-ICMS']).strip()
            if cst_atual == "60":
                if row['NCM'] not in ncms_entrada_60:
                    mensagens.append(f"Divergente — CST informado: 60 | Esperado: {cst_esperado}")
            elif cst_atual != cst_esperado and cst_esperado != "NCM não encontrado":
                mensagens.append(f"Divergente — CST informado: {cst_atual} | Esperado: {cst_esperado}")

            # --- LÓGICA 2: VALIDAÇÃO DE BASE E REDUÇÃO ---
            if cst_atual == "00" and abs(row['BC-ICMS'] - row['VPROD']) > 0.02:
                mensagens.append("Base ICMS incorreta — valor diferente do produto")
            
            if cst_atual == "20":
                if row['pRedBC'] == 0: mensagens.append("CST 020 sem redução da base")
                calc_red = row['VPROD'] * (1 - row['pRedBC']/100)
                if abs(row['BC-ICMS'] - calc_red) > 0.02: mensagens.append("Base ICMS incorreta após redução")

            # --- LÓGICA 3: ALÍQUOTA (INTERNA E INTERESTADUAL) ---
            if row['UF_EMIT'] == row['UF_DEST']:
                if row['ALQ-ICMS'] != alq_esperada and cst_esperado != "NCM não encontrado":
                    mensagens.append(f"Alíquota Errada - Destacado: {row['ALQ-ICMS']}% | Esperado: {alq_esperada}%")
            
            # --- LÓGICA 4: CÁLCULO DE COMPLEMENTO ---
            complemento = 0.0
            if row['ALQ-ICMS'] < alq_esperada and row['BC-ICMS'] > 0:
                complemento = (alq_esperada - row['ALQ-ICMS']) * row['BC-ICMS'] / 100

            diagnostico = "; ".join(mensagens) if mensagens else "Correto"
            acao = "Cc-e permitida para correção cadastral" if "Alíquota" in diagnostico else "Requer NF Complementar ou Estorno"
            if diagnostico == "Correto": acao = "Manter conforme XML"

            def fmt(v): return f"R$ {v:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
            
            return pd.Series([diagnostico, fmt(row['VLR-ICMS']), fmt(row['BC-ICMS'] * alq_esperada / 100), acao, fmt(complemento)])

        df_icms_audit[['Diagnóstico Detalhado', 'ICMS Destacado', 'ICMS Esperado', 'Como Corrigir?', 'Complemento de ICMS']] = df_icms_audit.apply(auditoria_expert, axis=1)
        # Inserção da coluna Alíquota Esperada conforme pedido
        df_icms_audit['Alíquota Esperada'] = df_icms_audit.apply(lambda r: f"{(base_tribut[base_tribut['NCM']==str(r['NCM']).strip()].iloc[0,3] if not base_tribut[base_tribut['NCM']==str(r['NCM']).strip()].empty else 0.0):.2f}%", axis=1)

    mem = io.BytesIO()
    with pd.ExcelWriter(mem, engine='xlsxwriter') as wr:
        if not df_ent.empty: df_ent.to_excel(wr, sheet_name='ENTRADAS', index=False)
        if not df_sai.empty:
            df_sai.to_excel(wr, sheet_name='SAIDAS', index=False)
            df_icms_audit.to_excel(wr, sheet_name='ICMS', index=False)
            for aba in ['IPI', 'PIS_COFINS', 'DIFAL']: df_sai.to_excel(wr, sheet_name=aba, index=False)
    return mem.getvalue()
