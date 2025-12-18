import streamlit as st
import pandas as pd
import xml.etree.ElementTree as ET
import io
import re
import os

# --- CONFIGURAÇÃO ---
st.set_page_config(page_title="Sentinela Fiscal Pro", layout="wide")
st.title("🛡️ Sentinela: Auditoria Fiscal & Autenticidade")

# --- 1. CARREGAR BASES MESTRE ---
@st.cache_data
def carregar_bases_mestre():
    df_gerencial = pd.DataFrame()
    df_tribut = pd.DataFrame()
    df_inter = pd.DataFrame()
    df_tipi = pd.DataFrame()
    df_pc_base = pd.DataFrame()

    def encontrar_arquivo(nome_base):
        possibilidades = [
            nome_base, nome_base.lower(), nome_base.upper(), 
            f".streamlit/{nome_base}", f".streamlit/{nome_base.lower()}",
            "Pis_Cofins.xlsx", "pis_cofins.xlsx", ".streamlit/Pis_Cofins.xlsx"
        ]
        for p in possibilidades:
            if os.path.exists(p): return p
        for root, dirs, files in os.walk("."):
            for file in files:
                if nome_base.lower().split('.')[0] in file.lower():
                    return os.path.join(root, file)
        return None

    # A. Bases Internas
    caminho_mestre = encontrar_arquivo("Sentinela_MIRÃO_Outubro2025.xlsx")
    if caminho_mestre:
        try:
            xls = pd.ExcelFile(caminho_mestre)
            df_gerencial = pd.read_excel(xls, 'Entradas Gerencial', dtype=str)
            df_tribut = pd.read_excel(xls, 'Bases Tribut', dtype=str)
            try: df_inter = pd.read_excel(xls, 'Bases Tribut', usecols="AC:AD", dtype=str).dropna()
            except: pass
        except: pass

    # B. TIPI
    caminho_tipi = encontrar_arquivo("TIPI.xlsx")
    if caminho_tipi:
        try:
            df_raw = pd.read_excel(caminho_tipi, dtype=str)
            df_tipi = df_raw.iloc[:, [0, 1]].copy()
            df_tipi.columns = ['NCM', 'ALIQ']
            df_tipi = df_tipi.dropna(how='all')
            df_tipi['NCM'] = df_tipi['NCM'].str.replace(r'\D', '', regex=True).str.zfill(8)
            df_tipi['ALIQ'] = df_tipi['ALIQ'].str.upper().replace('NT', '0').str.strip().str.replace(',', '.')
            df_tipi = df_tipi[df_tipi['NCM'].str.match(r'^\d{8}$', na=False)]
        except: pass

    # C. PIS & COFINS
    caminho_pc = encontrar_arquivo("Pis_Cofins.xlsx")
    if caminho_pc:
        try:
            df_pc_raw = pd.read_excel(caminho_pc, dtype=str)
            if len(df_pc_raw.columns) >= 3:
                df_pc_base = df_pc_raw.iloc[:, [0, 1, 2]].copy()
                df_pc_base.columns = ['NCM', 'CST_ENT', 'CST_SAI']
                df_pc_base['NCM'] = df_pc_base['NCM'].str.replace(r'\D', '', regex=True).str.zfill(8)
                df_pc_base['CST_SAI'] = df_pc_base['CST_SAI'].str.replace(r'\D', '', regex=True).str.zfill(2)
        except: pass

    return df_gerencial, df_tribut, df_inter, df_tipi, df_pc_base

df_gerencial, df_tribut, df_inter, df_tipi, df_pc_base = carregar_bases_mestre()

# --- 2. EXTRAÇÃO XML ---
def extrair_tags_com_raio_x(arquivos_upload):
    itens_validos = []
    arquivos_com_erro = []

    for arquivo in arquivos_upload:
        try:
            content = arquivo.read()
            try: xml_str = content.decode('utf-8')
            except: xml_str = content.decode('latin-1')

            # Limpeza de namespaces
            xml_str_clean = re.sub(r' xmlns="[^"]+"', '', xml_str)
            xml_str_clean = re.sub(r' xmlns:xsi="[^"]+"', '', xml_str_clean)
            xml_str_clean = re.sub(r' xsi:schemaLocation="[^"]+"', '', xml_str_clean)
            
            root = ET.fromstring(xml_str_clean)

            if "resNFe" in root.tag or root.find(".//resNFe") is not None:
                arquivos_com_erro.append({"Arquivo": arquivo.name, "Motivo": "Nota de Resumo"})
                continue
            if "procEventoNFe" in root.tag:
                arquivos_com_erro.append({"Arquivo": arquivo.name, "Motivo": "Evento/Cancelamento"})
                continue
            
            infNFe = root.find('.//infNFe')
            if infNFe is None:
                arquivos_com_erro.append({"Arquivo": arquivo.name, "Motivo": "XML desconhecido"})
                continue

            dets = root.findall(f".//det")
            if not dets:
                arquivos_com_erro.append({"Arquivo": arquivo.name, "Motivo": "Sem Produtos"})
                continue

            # Extração Cabeçalho
            ide = root.find(f".//ide")
            emit = root.find(f".//emit")
            dest = root.find(f".//dest")
            chave = infNFe.attrib.get('Id', '')[3:]

            for det in dets:
                prod = det.find(f"prod")
                imposto = det.find(f"imposto")
                
                def get_val(node, tag, tipo=str):
                    if node is None: return 0.0 if tipo == float else ""
                    res = node.find(f"{tag}")
                    if res is not None and res.text:
                        return float(res.text) if tipo == float else res.text
                    return 0.0 if tipo == float else ""

                def get_pis_cofins(grupo, campo):
                    if imposto is None: return ""
                    node = imposto.find(f"{grupo}")
                    if node is not None:
                        for child in node:
                            res = child.find(f"{campo}")
                            if res is not None: return res.text
                    return ""

                # ICMS
                cst_icms, bc_icms, aliq_icms, val_icms = "", 0.0, 0.0, 0.0
                if imposto is not None:
                    node_icms = imposto.find(f"ICMS")
                    if node_icms:
                        for child in node_icms:
                            if child.find(f"CST") is not None: cst_icms = child.find(f"CST").text
                            elif child.find(f"CSOSN") is not None: cst_icms = child.find(f"CSOSN").text
                            if child.find(f"vBC") is not None: bc_icms = float(child.find(f"vBC").text)
                            if child.find(f"pICMS") is not None: aliq_icms = float(child.find(f"pICMS").text)
                            if child.find(f"vICMS") is not None: val_icms = float(child.find(f"vICMS").text)

                # IPI
                cst_ipi, aliq_ipi = "", 0.0
                if imposto is not None:
                    node_ipi = imposto.find(f"IPI")
                    if node_ipi:
                        for child in node_ipi:
                            if child.find(f"CST") is not None: cst_ipi = child.find(f"CST").text
                            if child.find(f"pIPI") is not None: aliq_ipi = float(child.find(f"pIPI").text)

                # Difal
                v_difal = 0.0
                if imposto is not None:
                    node_difal = imposto.find(f"ICMSUFDest")
                    if node_difal and node_difal.find(f"vICMSUFDest") is not None:
                        v_difal = float(node_difal.find(f"vICMSUFDest").text)

                registro = {
                    "Arquivo": arquivo.name,
                    "Número NF": get_val(ide, 'nNF'),
                    "UF Emit": emit.find(f"enderEmit/UF").text if emit is not None and emit.find(f"enderEmit/UF") is not None else "",
                    "UF Dest": dest.find(f"enderDest/UF").text if dest is not None and dest.find(f"enderDest/UF") is not None else "",
                    "nItem": det.attrib.get('nItem', '0'),
                    "Cód Prod": get_val(prod, 'cProd'),
                    "Desc Prod": get_val(prod, 'xProd'),
                    "NCM": get_val(prod, 'NCM'),
                    "CFOP": get_val(prod, 'CFOP'),
                    "vProd": get_val(prod, 'vProd', float),
                    "CST ICMS": cst_icms,
                    "BC ICMS": bc_icms,
                    "Alq ICMS": aliq_icms,
                    "ICMS": val_icms,
                    "ICMS UF Dest": v_difal,
                    "CST IPI": cst_ipi,
                    "Aliq IPI": aliq_ipi,
                    "CST PIS": get_pis_cofins('PIS', 'CST'),
                    "CST COFINS": get_pis_cofins('COFINS', 'CST'),
                    "Chave de Acesso": chave
                }
                itens_validos.append(registro)

        except Exception as e:
            arquivos_com_erro.append({"Arquivo": arquivo.name, "Motivo": f"Erro: {str(e)}"})

    return itens_validos, arquivos_com_erro

# --- 3. INTERFACE ---
with st.sidebar:
    st.header("📂 Upload Central")
    
    xml_saidas = st.file_uploader("1. Notas de SAÍDA (XML)", accept_multiple_files=True, type='xml')
    xml_entradas = st.file_uploader("2. Notas de ENTRADA (XML)", accept_multiple_files=True, type='xml')
    
    st.markdown("---")
    st.subheader("🔑 Autenticidade (Sefaz)")
    st.info("O arquivo de status será usado para validar tanto Entradas quanto Saídas.")
    rel_status = st.file_uploader("3. Relatório de Status (Excel/CSV)", type=['xlsx', 'csv'])

# --- 4. PROCESSAMENTO ---
if (xml_saidas or xml_entradas):
    
    # 4.1 Carregar Status de Autenticidade
    status_dict = {}
    if rel_status:
        try:
            if rel_status.name.endswith('.xlsx'):
                df_st_rel = pd.read_excel(rel_status, dtype=str)
            else:
                df_st_rel = pd.read_csv(rel_status, dtype=str)
            
            # Assume Coluna 0 = Chave e Coluna 5 = Situação (Ajuste se necessário)
            # Limpa caracteres não numéricos da chave para garantir o match
            status_dict = dict(zip(df_st_rel.iloc[:, 0].str.replace(r'\D', '', regex=True), df_st_rel.iloc[:, 5]))
            st.toast("Base de Autenticidade Carregada!", icon="🔓")
        except Exception as e:
            st.error(f"Erro ao ler arquivo de status: {e}")

    # 4.2 Processar XMLs
    lista_s, erros_s = extrair_tags_com_raio_x(xml_saidas) if xml_saidas else ([], [])
    lista_e, erros_e = extrair_tags_com_raio_x(xml_entradas) if xml_entradas else ([], [])
    
    df_s = pd.DataFrame(lista_s)
    df_e = pd.DataFrame(lista_e)
    df_erros = pd.DataFrame(erros_s + erros_e)

    # --- LÓGICA DE AUTENTICIDADE (OS "BOTÕES") ---
    # Aqui aplicamos a lógica para ambas as abas: Entradas e Saídas
    
    st.markdown("### 🔍 Painel de Autenticidade")
    col1, col2 = st.columns(2)

    # Processar Saídas
    if not df_s.empty:
        # Cria a coluna Status Autenticidade
        df_s['Status Autenticidade'] = df_s['Chave de Acesso'].str.replace(r'\D', '', regex=True).map(status_dict).fillna("Pendente/Não Encontrado")
        
        # Cria coluna auxiliar 'AP' usada nas validações fiscais
        df_s['AP'] = df_s['Status Autenticidade']
        
        with col1:
            st.markdown("#### 📤 Autenticidade Saídas")
            contagem = df_s.drop_duplicates(subset=['Chave de Acesso'])['Status Autenticidade'].value_counts()
            st.write(contagem)
            if "Cancelada" in str(contagem) or "Cancelado" in str(contagem):
                st.error("⚠️ Atenção: Existem notas de saída CANCELADAS!")

    # Processar Entradas
    if not df_e.empty:
        # Cria a coluna Status Autenticidade (ESSA ERA A PARTE QUE FALTAVA)
        df_e['Status Autenticidade'] = df_e['Chave de Acesso'].str.replace(r'\D', '', regex=True).map(status_dict).fillna("Pendente/Não Encontrado")
        
        with col2:
            st.markdown("#### 📥 Autenticidade Entradas")
            contagem_e = df_e.drop_duplicates(subset=['Chave de Acesso'])['Status Autenticidade'].value_counts()
            st.write(contagem_e)
            if "Cancelada" in str(contagem_e) or "Cancelado" in str(contagem_e):
                st.error("⚠️ Atenção: Você recebeu notas CANCELADAS!")

    st.markdown("---")

    # --- ANÁLISE TRIBUTÁRIA (APENAS SAÍDAS POR ENQUANTO) ---
    # Carrega dicionários para análise rápida
    map_tribut_cst, map_tribut_aliq, map_gerencial_cst, map_inter, map_tipi, map_pis_cofins_saida = {}, {}, {}, {}, {}, {}
    
    if not df_s.empty:
        if not df_tribut.empty:
            map_tribut_cst = dict(zip(df_tribut.iloc[:, 0].astype(str), df_tribut.iloc[:, 2].astype(str)))
            map_tribut_aliq = dict(zip(df_tribut.iloc[:, 0].astype(str), df_tribut.iloc[:, 3].astype(str)))
        if not df_gerencial.empty:
            map_gerencial_cst = dict(zip(df_gerencial.iloc[:, 0].astype(str), df_gerencial.iloc[:, 1].astype(str)))
        if not df_inter.empty:
            map_inter = dict(zip(df_inter.iloc[:, 0].astype(str), df_inter.iloc[:, 1].astype(str)))
        if not df_tipi.empty:
            map_tipi = dict(zip(df_tipi['NCM'], df_tipi['ALIQ']))
        if not df_pc_base.empty:
            map_pis_cofins_saida = dict(zip(df_pc_base['NCM'], df_pc_base['CST_SAI']))

    # DFs de análise
    df_icms = pd.DataFrame()
    df_ipi = pd.DataFrame()
    df_pc = pd.DataFrame()
    df_difal = pd.DataFrame()

    if not df_s.empty:
        # 1. ICMS
        df_icms = df_s.copy()
        def f_analise_cst(row):
            status = str(row.get('Status Autenticidade', ''))
            if "Cancelado" in status or "Cancelada" in status: return "NF CANCELADA"
            
            cst_esp = map_tribut_cst.get(str(row['NCM']).strip())
            cst = str(row['CST ICMS']).strip()
            if not cst_esp: return "NCM não encontrado na Base"
            if map_gerencial_cst.get(str(row['NCM']).strip()) == "60" and cst != "60": return f"Divergente — CST: {cst} | Esp: 60"
            return "Correto" if cst == cst_esp else f"Divergente — CST: {cst} | Esp: {cst_esp}"
        
        def f_aliq(row):
             status = str(row.get('Status Autenticidade', ''))
             if "Cancelado" in status or "Cancelada" in status: return "NF CANCELADA"

             if row['UF Emit'] == row['UF Dest']: esp = map_tribut_aliq.get(str(row['NCM']).strip())
             else: esp = map_inter.get(row['UF Dest'])
             try: esp_val = float(str(esp).replace(',', '.'))
             except: return "Erro valor esperado"
             return "Correto" if abs(row['Alq ICMS'] - esp_val) < 0.1 else f"Destacado: {row['Alq ICMS']} | Esp: {esp_val}"

        df_icms['Análise CST ICMS'] = df_icms.apply(f_analise_cst, axis=1)
        df_icms['Analise Aliq ICMS'] = df_icms.apply(f_aliq, axis=1)

        # 2. IPI
        df_ipi = df_s.copy()
        def f_analise_ipi(row):
            status = str(row.get('Status Autenticidade', ''))
            if "Cancelado" in status or "Cancelada" in status: return "NF CANCELADA"
            
            if not map_tipi: return "TIPI Off"
            esp = map_tipi.get(str(row['NCM']).strip())
            if esp is None: return "NCM Off"
            try: esp_val = float(str(esp).replace(',', '.'))
            except: return "Erro TIPI"
            return "Correto" if abs(row['Aliq IPI'] - esp_val) < 0.1 else f"Dest: {row['Aliq IPI']} | Esp: {esp_val}"
        df_ipi['Análise IPI'] = df_ipi.apply(f_analise_ipi, axis=1)

        # 3. PIS/COFINS
        df_pc = df_s.copy()
        def f_pc(row):
            status = str(row.get('Status Autenticidade', ''))
            if "Cancelado" in status or "Cancelada" in status: return "NF CANCELADA"
            
            if not map_pis_cofins_saida: return "Base Off"
            esp = map_pis_cofins_saida.get(str(row['NCM']).strip())
            if esp is None: return "NCM Off"
            erros = []
            if str(row['CST PIS']).strip() != esp: erros.append(f"PIS: {row['CST PIS']} (Esp: {esp})")
            if str(row['CST COFINS']).strip() != esp: erros.append(f"COF: {row['CST COFINS']} (Esp: {esp})")
            return "Correto" if not erros else " | ".join(erros)
        df_pc['Análise PIS e COFINS'] = df_pc.apply(f_pc, axis=1)

        # 4. DIFAL
        df_difal = df_s.copy()
        def f_difal(row):
            status = str(row.get('Status Autenticidade', ''))
            if "Cancelado" in status or "Cancelada" in status: return "NF CANCELADA"

            if row['UF Emit'] == row['UF Dest']: return "N/A (Interna)"
            aliq_dest_str = map_inter.get(row['UF Dest'])
            if not aliq_dest_str: return "UF sem aliq"
            try:
                aliq_dest = float(str(aliq_dest_str).replace(',', '.'))
                v_calc = (max(0, aliq_dest - row['Alq ICMS']) / 100) * row['BC ICMS']
                return "Correto" if abs(row['ICMS UF Dest'] - v_calc) < 0.05 else f"Div: XML {row['ICMS UF Dest']:.2f} | Calc {v_calc:.2f}"
            except: return "Erro Calc"
        df_difal['Análise Difal'] = df_difal.apply(f_difal, axis=1)

    # --- EXPORTAR ---
    if not df_s.empty or not df_e.empty or not df_erros.empty:
        buffer = io.BytesIO()
        with pd.ExcelWriter(buffer, engine='xlsxwriter') as writer:
            
            # ABA ENTRADAS (Agora com Status)
            if not df_e.empty: 
                # Reordenando colunas para Status ficar visível logo no começo se quiser
                cols = list(df_e.columns)
                if 'Status Autenticidade' in cols:
                    cols.insert(1, cols.pop(cols.index('Status Autenticidade')))
                    df_e = df_e[cols]
                df_e.to_excel(writer, index=False, sheet_name='Entradas')
            
            # ABA SAÍDAS (Agora com Status)
            if not df_s.empty: 
                cols = list(df_s.columns)
                if 'Status Autenticidade' in cols:
                    cols.insert(1, cols.pop(cols.index('Status Autenticidade')))
                    df_s = df_s[cols]
                df_s.to_excel(writer, index=False, sheet_name='Saídas')
            
            # Abas de Auditoria
            if not df_icms.empty: df_icms.to_excel(writer, index=False, sheet_name='Auditoria ICMS')
            if not df_ipi.empty: df_ipi.to_excel(writer, index=False, sheet_name='Auditoria IPI')
            if not df_pc.empty: df_pc.to_excel(writer, index=False, sheet_name='Auditoria Pis_Cofins')
            if not df_difal.empty: df_difal.to_excel(writer, index=False, sheet_name='Auditoria Difal')
            
            if not df_erros.empty:
                df_erros.to_excel(writer, index=False, sheet_name='❌ Arquivos Ignorados')

        st.success(f"✅ Análise Completa! Status validado em Entradas e Saídas.")
        st.download_button("📥 Baixar Relatório com Autenticidade", buffer.getvalue(), "Sentinela_Relatorio_Final.xlsx")
