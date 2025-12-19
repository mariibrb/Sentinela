import pandas as pd
import numpy as np
import io
import xml.etree.ElementTree as ET
from datetime import datetime

def extrair_dados_xml(xml_files, tipo, df_autenticidade=None):
    """
    Extrai dados detalhados dos XMLs de NF-e, incluindo bases e impostos.
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
            chave = root.find(".//nfe:infNFe", ns).attrib['Id'][3:] if root.find(".//nfe:infNFe", ns) is not None else "N/A"
            
            # Detalhamento de Itens
            for det in root.findall(".//nfe:det", ns):
                prod = det.find("nfe:prod", ns)
                imposto = det.find("nfe:imposto", ns)
                
                # Dados Básicos
                item = {
                    'CHAVE': chave,
                    'TIPO': tipo,
                    'produto': prod.find("nfe:xProd", ns).text if prod is not None else "",
                    'ncm': prod.find("nfe:NCM", ns).text if prod is not None else "",
                    'valor_item': float(prod.find("nfe:vProd", ns).text) if prod is not None else 0.0,
                }

                # ICMS
                icms_tag = imposto.find(".//nfe:ICMS", ns)
                item['valor_icms'] = 0.0
                if icms_tag is not None:
                    v_icms = icms_tag.find(".//nfe:vICMS", ns)
                    if v_icms is not None: item['valor_icms'] = float(v_icms.text)

                # PIS
                pis_tag = imposto.find(".//nfe:PIS", ns)
                item['base_calculo'] = 0.0
                item['aliquota_pis'] = 0.0
                item['valor_pis_xml'] = 0.0
                if pis_tag is not None:
                    v_bc = pis_tag.find(".//nfe:vBC", ns)
                    p_pis = pis_tag.find(".//nfe:pPIS", ns)
                    v_pis = pis_tag.find(".//nfe:vPIS", ns)
                    if v_bc is not None: item['base_calculo'] = float(v_bc.text)
                    if p_pis is not None: item['aliquota_pis'] = float(p_pis.text)
                    if v_pis is not None: item['valor_pis_xml'] = float(v_pis.text)

                # COFINS
                cofins_tag = imposto.find(".//nfe:COFINS", ns)
                item['aliquota_cofins'] = 0.0
                item['valor_cofins_xml'] = 0.0
                if cofins_tag is not None:
                    p_cof = cofins_tag.find(".//nfe:pCOFINS", ns)
                    v_cof = cofins_tag.find(".//nfe:vCOFINS", ns)
                    if p_cof is not None: item['aliquota_cofins'] = float(p_cof.text)
                    if v_cof is not None: item['valor_cofins_xml'] = float(v_cof.text)

                # IPI
                ipi_tag = imposto.find(".//nfe:IPI", ns)
                item['aliquota_ipi'] = 0.0
                item['valor_ipi_xml'] = 0.0
                if ipi_tag is not None:
                    p_ipi = ipi_tag.find(".//nfe:pIPI", ns)
                    v_ipi = ipi_tag.find(".//nfe:vIPI", ns)
                    if p_ipi is not None: item['aliquota_ipi'] = float(p_ipi.text)
                    if v_ipi is not None: item['valor_ipi_xml'] = float(v_ipi.text)

                registros.append(item)
        except Exception as e:
            continue

    df = pd.DataFrame(registros)
    
    # Aplicação da Autenticidade (Cruzamento de Status)
    if df_autenticidade is not None and not df.empty:
        df = df.merge(df_autenticidade[['CHAVE', 'STATUS']], on='CHAVE', how='left')
        
    return df

def gerar_excel_final(df_e, df_s):
    """
    Gera o Excel final com abas de Entradas, Saídas e Auditoria de Tributos.
    """
    output = io.BytesIO()
    
    # Conciliação para as abas de PISCOFINS e IPI
    df_consolidado = pd.concat([df_e, df_s], ignore_index=True)

    # --- ABA PISCOFINS COM ANALISE ---
    df_piscofins = df_consolidado.copy()
    if not df_piscofins.empty:
        # Soma o valor destacado e compara com o cálculo matemático
        destacado = df_piscofins['valor_pis_xml'] + df_piscofins['valor_cofins_xml']
        esperado = df_piscofins['base_calculo'] * ((df_piscofins['aliquota_pis'] + df_piscofins['aliquota_cofins']) / 100)
        
        df_piscofins['ANALISE'] = np.where(
            abs(destacado - esperado) < 0.01, "CORRETO", "ESPERADO DESTACADO"
        )

    # --- ABA IPI COM ANALISE ---
    df_ipi = df_consolidado.copy()
    if not df_ipi.empty:
        # Compara Valor IPI XML vs (Base * Alíquota)
        esperado_ipi = df_ipi['base_calculo'] * (df_ipi['aliquota_ipi'] / 100)
        df_ipi['ANALISE'] = np.where(
            abs(df_ipi['valor_ipi_xml'] - esperado_ipi) < 0.01, "CORRETO", "ESPERADO DESTACADO"
        )

    # Escrita das Abas
    with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
        if not df_e.empty: df_e.to_excel(writer, sheet_name='Entradas', index=False)
        if not df_s.empty: df_s.to_excel(writer, sheet_name='Saídas', index=False)
        df_piscofins.to_excel(writer, sheet_name='PISCOFINS', index=False)
        df_ipi.to_excel(writer, sheet_name='IPI', index=False)
        
    return output.getvalue()
