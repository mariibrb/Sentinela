import pandas as pd
import numpy as np
import io
import xml.etree.ElementTree as ET
from datetime import datetime

def extrair_dados_xml(xml_files, tipo, df_autenticidade=None):
    """
    Extrai dados detalhados dos XMLs de NF-e e realiza o cruzamento seguro.
    """
    registros = []
    
    if not xml_files:
        return pd.DataFrame()

    for xml_file in xml_files:
        try:
            tree = ET.parse(xml_file)
            root = tree.getroot()
            ns = {'nfe': 'http://www.portalfiscal.inf.br/nfe'}

            # Informações da Nota
            infNFe = root.find(".//nfe:infNFe", ns)
            chave = infNFe.attrib['Id'][3:] if infNFe is not None else "N/A"
            
            # Detalhamento de Itens
            for det in root.findall(".//nfe:det", ns):
                prod = det.find("nfe:prod", ns)
                imposto = det.find("nfe:imposto", ns)
                
                item = {
                    'CHAVE': chave,
                    'TIPO': tipo,
                    'produto': prod.find("nfe:xProd", ns).text if prod is not None else "",
                    'ncm': prod.find("nfe:NCM", ns).text if prod is not None else "",
                    'valor_item': float(prod.find("nfe:vProd", ns).text) if prod is not None else 0.0,
                    'base_calculo': 0.0,
                    'aliquota_pis': 0.0,
                    'valor_pis_xml': 0.0,
                    'aliquota_cofins': 0.0,
                    'valor_cofins_xml': 0.0,
                    'aliquota_ipi': 0.0,
                    'valor_ipi_xml': 0.0
                }

                if imposto is not None:
                    # PIS
                    pis = imposto.find(".//nfe:PIS", ns)
                    if pis is not None:
                        vbc = pis.find(".//nfe:vBC", ns)
                        ppis = pis.find(".//nfe:pPIS", ns)
                        vpis = pis.find(".//nfe:vPIS", ns)
                        if vbc is not None: item['base_calculo'] = float(vbc.text)
                        if ppis is not None: item['aliquota_pis'] = float(ppis.text)
                        if vpis is not None: item['valor_pis_xml'] = float(vpis.text)

                    # COFINS
                    cofins = imposto.find(".//nfe:COFINS", ns)
                    if cofins is not None:
                        pcof = cofins.find(".//nfe:pCOFINS", ns)
                        vcof = cofins.find(".//nfe:vCOFINS", ns)
                        if pcof is not None: item['aliquota_cofins'] = float(pcof.text)
                        if vcof is not None: item['valor_cofins_xml'] = float(vcof.text)

                    # IPI
                    ipi = imposto.find(".//nfe:IPI", ns)
                    if ipi is not None:
                        pipi = ipi.find(".//nfe:pIPI", ns)
                        vipi = ipi.find(".//nfe:vIPI", ns)
                        if pipi is not None: item['aliquota_ipi'] = float(pipi.text)
                        if vipi is not None: item['valor_ipi_xml'] = float(vipi.text)

                registros.append(item)
        except Exception:
            continue

    df = pd.DataFrame(registros)
    
    # --- CORREÇÃO DO KEYERROR (MERGE SEGURO) ---
    if df_autenticidade is not None and not df.empty:
        # Padroniza as colunas da autenticidade para maiúsculo para evitar erro de digitação
        df_autenticidade.columns = [c.upper() for c in df_autenticidade.columns]
        
        if 'CHAVE' in df_autenticidade.columns and 'STATUS' in df_autenticidade.columns:
            df = df.merge(df_autenticidade[['CHAVE', 'STATUS']], on='CHAVE', how='left')
        elif 'CHAVE' in df_autenticidade.columns:
            df = df.merge(df_autenticidade[['CHAVE']], on='CHAVE', how='left')
            
    return df

def gerar_excel_final(df_e, df_s):
    """
    Gera o Excel final com as colunas de ANALISE nas abas PISCOFINS e IPI.
    """
    output = io.BytesIO()
    df_consolidado = pd.concat([df_e, df_s], ignore_index=True)

    # --- ABA PISCOFINS ---
    df_piscofins = df_consolidado.copy()
    if not df_piscofins.empty:
        v_destacado = df_piscofins['valor_pis_xml'] + df_piscofins['valor_cofins_xml']
        v_esperado = df_piscofins['base_calculo'] * ((df_piscofins['aliquota_pis'] + df_piscofins['aliquota_cofins']) / 100)
        df_piscofins['ANALISE'] = np.where(abs(v_destacado - v_esperado) < 0.01, "CORRETO", "ESPERADO DESTACADO")

    # --- ABA IPI ---
    df_ipi = df_consolidado.copy()
    if not df_ipi.empty:
        v_ipi_esp = df_ipi['base_calculo'] * (df_ipi['aliquota_ipi'] / 100)
        df_ipi['ANALISE'] = np.where(abs(df_ipi['valor_ipi_xml'] - v_ipi_esp) < 0.01, "CORRETO", "ESPERADO DESTACADO")

    with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
        if not df_e.empty: df_e.to_excel(writer, sheet_name='Entradas', index=False)
        if not df_s.empty: df_s.to_excel(writer, sheet_name='Saídas', index=False)
        df_piscofins.to_excel(writer, sheet_name='PISCOFINS', index=False)
        df_ipi.to_excel(writer, sheet_name='IPI', index=False)
        
    return output.getvalue()
