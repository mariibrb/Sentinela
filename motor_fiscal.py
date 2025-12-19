import pandas as pd
import numpy as np
import io
import xml.etree.ElementTree as ET

def extrair_dados_xml(xml_files, tipo, df_autenticidade=None):
    """
    Sua lógica de extração aprovada. 
    Lê os arquivos e retorna o DataFrame com as tags de impostos.
    """
    registros = []
    if not xml_files:
        return pd.DataFrame()

    for xml_file in xml_files:
        try:
            xml_file.seek(0) # Garante leitura do início
            conteudo = xml_file.read()
            root = ET.fromstring(conteudo)
            ns = {'nfe': 'http://www.portalfiscal.inf.br/nfe'}
            if '}' in root.tag:
                uri = root.tag.split('}')[0] + '}'
                ns = {'nfe': uri.replace('{', '').replace('}', '')}

            chave = root.find(".//nfe:infNFe", ns).attrib['Id'][3:]
            
            for det in root.findall(".//nfe:det", ns):
                prod = det.find("nfe:prod", ns)
                imposto = det.find("nfe:imposto", ns)
                
                item = {
                    'CHAVE': chave,
                    'TIPO': tipo,
                    'produto': prod.findtext("nfe:xProd", namespaces=ns),
                    'valor_item': float(prod.findtext("nfe:vProd", namespaces=ns) or 0),
                    'base_calculo': float(imposto.find(".//nfe:vBC", ns).text if imposto.find(".//nfe:vBC", ns) is not None else 0),
                    'aliquota_pis': float(imposto.find(".//nfe:pPIS", ns).text if imposto.find(".//nfe:pPIS", ns) is not None else 0),
                    'valor_pis_xml': float(imposto.find(".//nfe:vPIS", ns).text if imposto.find(".//nfe:vPIS", ns) is not None else 0),
                    'aliquota_cofins': float(imposto.find(".//nfe:pCOFINS", ns).text if imposto.find(".//nfe:pCOFINS", ns) is not None else 0),
                    'valor_cofins_xml': float(imposto.find(".//nfe:vCOFINS", ns).text if imposto.find(".//nfe:vCOFINS", ns) is not None else 0),
                    'aliquota_ipi': float(imposto.find(".//nfe:pIPI", ns).text if imposto.find(".//nfe:pIPI", ns) is not None else 0),
                    'valor_ipi_xml': float(imposto.find(".//nfe:vIPI", ns).text if imposto.find(".//nfe:vIPI", ns) is not None else 0),
                }
                registros.append(item)
            xml_file.seek(0)
        except:
            continue

    df = pd.DataFrame(registros)
    if df_autenticidade is not None and not df.empty:
        df_autenticidade.columns = [c.upper() for c in df_autenticidade.columns]
        if 'CHAVE' in df_autenticidade.columns:
            df = df.merge(df_autenticidade, on='CHAVE', how='left')
    return df

def gerar_excel_final(df_e, df_s):
    """
    Gera o Excel mantendo a estrutura original e injetando 
    apenas as colunas de análise em IPI e PISCOFINS.
    """
    output = io.BytesIO()
    df_consolidado = pd.concat([df_e, df_s], ignore_index=True)

    # --- ABA PISCOFINS ---
    df_piscofins = df_consolidado.copy()
    if not df_piscofins.empty:
        calc_esperado = df_piscofins['base_calculo'] * ((df_piscofins['aliquota_pis'] + df_piscofins['aliquota_cofins']) / 100)
        calc_xml = df_piscofins['valor_pis_xml'] + df_piscofins['valor_cofins_xml']
        df_piscofins['ANALISE'] = np.where(abs(calc_esperado - calc_xml) < 0.01, "CORRETO", "ESPERADO DESTACADO")

    # --- ABA IPI ---
    df_ipi = df_consolidado.copy()
    if not df_ipi.empty:
        # Criando a coluna ANALISE vazia, conforme solicitado, sem nenhuma análise sendo feita
        df_ipi['ANALISE'] = ""

    with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
        df_e.to_excel(writer, sheet_name='Entradas', index=False)
        df_s.to_excel(writer, sheet_name='Saídas', index=False)
        df_piscofins.to_excel(writer, sheet_name='PISCOFINS', index=False)
        df_ipi.to_excel(writer, sheet_name='IPI', index=False)
        
    return output.getvalue()
