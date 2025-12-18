import streamlit as st
import pandas as pd
import xml.etree.ElementTree as ET
import re
import os
import io

# --- 1. CONFIGURAÇÃO DA PÁGINA ---
st.set_page_config(
    page_title="Sentinela - Nascel",
    page_icon="🛡️",
    layout="wide"
)

# --- 2. CSS PERSONALIZADO (Identidade Nascel) ---
st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;600;700&display=swap');
    html, body, [class*="css"] { font-family: 'Inter', sans-serif; }
    
    .main-title { font-size: 2.5rem; font-weight: 700; color: #555555; margin-bottom: 0px; }
    .sub-title { font-size: 1rem; color: #FF8C00; font-weight: 600; margin-bottom: 30px; }
    
    /* Cards de Upload e Info */
    .feature-card {
        background-color: white; padding: 20px; border-radius: 10px;
        border: 1px solid #E0E0E0; box-shadow: 0 4px 6px rgba(0,0,0,0.05);
        text-align: center; transition: all 0.3s ease; height: 100%;
    }
    .feature-card:hover { transform: translateY(-5px); border-color: #FF8C00; box-shadow: 0 10px 15px rgba(255, 140, 0, 0.15); }
    
    .card-icon { font-size: 2rem; margin-bottom: 10px; display: block; }
    
    /* Botões */
    .stButton button { width: 100%; border-radius: 8px; font-weight: 600; }
    
    /* Área de Upload Especial (Autenticidade) */
    .auth-upload-area {
        background-color: #f8f9fa;
        border: 2px dashed #cbd5e0;
        border-radius: 10px;
        padding: 10px;
        margin-bottom: 20px;
        text-align: center;
    }
    
    [data-testid='stFileUploader'] section { background-color: #FFF8F0; border: 1px dashed #FF8C00; }
</style>
""", unsafe_allow_html=True)

# --- 3. FUNÇÕES AUXILIARES ---

def extrair_tags_simples(arquivos_upload):
    """Extrai dados básicos dos XMLs"""
    lista = []
    for arquivo in arquivos_upload:
        try:
            content = arquivo.read()
            arquivo.seek(0)
            try: xml_str = content.decode('utf-8')
            except: xml_str = content.decode('latin-1')
            
            xml_str = re.sub(r' xmlns="[^"]+"', '', xml_str)
            root = ET.fromstring(xml_str)
            
            infNFe = root.find('.//infNFe')
            ide = root.find('.//ide')
            
            if infNFe is not None and ide is not None:
                chave = infNFe.attrib.get('Id', '')[3:]
                numero = ide.find('nNF').text if ide.find('nNF') is not None else "0"
                lista.append({'Arquivo': arquivo.name, 'Chave': chave, 'Numero': int(numero)})
        except: pass
    return pd.DataFrame(lista)

def carregar_status_sefaz(file_status):
    """Lê o excel de status da sefaz"""
    if not file_status: return {}
    try:
        if file_status.name.endswith('.xlsx'): df = pd.read_excel(file_status, dtype=str)
        else: df = pd.read_csv(file_status, dtype=str)
        return dict(zip(df.iloc[:, 0].str.replace(r'\D', '', regex=True), df.iloc[:, 5]))
    except: return {}

# --- 4. CABEÇALHO ---
col_logo, col_text = st.columns([1, 5])
with col_logo:
    # Tenta achar o logo na raiz ou na pasta .streamlit
    logo_path = "nascel sem fundo.png"
    if not os.path.exists(logo_path): logo_path = ".streamlit/nascel sem fundo.png"
    
    if os.path.exists(logo_path): st.image(logo_path, width=150)
    else: st.markdown("### NASCEL")

with col_text:
    st.markdown('<div class="main-title">Sentinela Fiscal</div>', unsafe_allow_html=True)
    st.markdown('<div class="sub-title">Central de Auditoria e Compliance</div>', unsafe_allow_html=True)

st.divider()

# --- 5. SEÇÃO 1: UPLOAD DE DADOS (Apenas XMLs) ---
st.markdown("### 📂 1. Importação de Arquivos (XMLs)")
c1, c2 = st.columns(2, gap="medium")

with c1:
    st.markdown('<div class="feature-card"><span class="card-icon">📥</span><b>Entradas XML</b></div>', unsafe_allow_html=True)
    xml_entradas = st.file_uploader("Upload Entradas", type=["xml"], accept_multiple_files=True, label_visibility="collapsed", key="in")

with c2:
    st.markdown('<div class="feature-card"><span class="card-icon">📤</span><b>Saídas XML</b></div>', unsafe_allow_html=True)
    xml_saidas = st.file_uploader("Upload Saídas", type=["xml"], accept_multiple_files=True, label_visibility="collapsed", key="out")

st.markdown("<br>", unsafe_allow_html=True)

# --- 6. SEÇÃO 2: AUTENTICIDADE (Com Upload Embutido) ---
st.markdown("### 🛡️ 2. Validação de Autenticidade")

# AQUI ESTÁ A MUDANÇA: Upload de Status fica dentro da seção 2
st.info("Para verificar a autenticidade (Cancelado/Autorizado), faça o upload do relatório da Sefaz abaixo.")
file_status = st.file_uploader("📂 Upload do Relatório de Status Sefaz (Excel ou CSV)", type=["xlsx", "csv"], key="stat_auth")

c_auth_ent, c_auth_sai = st.columns(2, gap="medium")

# Lógica Entradas
with c_auth_ent:
    if st.button("🔍 Verificar Entradas", type="primary", use_container_width=True):
        if not xml_entradas:
            st.warning("⚠️ Adicione os XMLs de Entrada lá em cima primeiro.")
        elif not file_status:
            st.error("⚠️ Para validar autenticidade, o arquivo de Status Sefaz (campo acima) é obrigatório.")
        else:
            # Roda verificação apenas se tiver os dois arquivos
            df_ent = extrair_tags_simples(xml_entradas)
            dic_status = carregar_status_sefaz(file_status)
            if not df_ent.empty:
                df_ent['Status Sefaz'] = df_ent['Chave'].map(dic_status).fillna("Não Encontrado")
                st.success("Verificação concluída!")
                st.dataframe(df_ent[['Numero', 'Chave', 'Status Sefaz']], use_container_width=True)

# Lógica Saídas
with c_auth_sai:
    if st.button("🔍 Verificar Saídas", type="primary", use_container_width=True):
        if not xml_saidas:
            st.warning("⚠️ Adicione os XMLs de Saída lá em cima primeiro.")
        elif not file_status:
            st.error("⚠️ Para validar autenticidade, o arquivo de Status Sefaz (campo acima) é obrigatório.")
        else:
            df_sai = extrair_tags_simples(xml_saidas)
            dic_status = carregar_status_sefaz(file_status)
            if not df_sai.empty:
                df_sai['Status Sefaz'] = df_sai['Chave'].map(dic_status).fillna("Não Encontrado")
                st.success("Verificação concluída!")
                st.dataframe(df_sai[['Numero', 'Chave', 'Status Sefaz']], use_container_width=True)

st.markdown("<br>", unsafe_allow_html=True)

# --- 7. SEÇÃO 3: RELATÓRIOS GERENCIAIS (INDEPENDENTES) ---
st.markdown("### 📊 3. Relatórios Gerenciais")
st.caption("Estes relatórios funcionam mesmo sem o arquivo de Status Sefaz.")

c_ger_ent, c_ger_sai = st.columns(2, gap="medium")

with c_ger_ent:
    if st.button("📈 Gerar Relatório Gerencial Entradas", use_container_width=True):
        if not xml_entradas:
            st.error("⚠️ Você precisa fazer o upload dos XMLs de ENTRADA na Seção 1.")
        else:
            st.toast("Processando relatório gerencial...", icon="📊")
            # Sua lógica gerencial entra aqui (Independente do Status Sefaz)
            df_temp = extrair_tags_simples(xml_entradas)
            st.write(f"Gerando relatório com base em {len(df_temp)} notas de entrada...")
            st.dataframe(df_temp.head()) # Exemplo

with c_ger_sai:
    if st.button("📈 Gerar Relatório Gerencial Saídas", use_container_width=True):
        if not xml_saidas:
            st.error("⚠️ Você precisa fazer o upload dos XMLs de SAÍDA na Seção 1.")
        else:
            st.toast("Processando relatório gerencial...", icon="📊")
            # Sua lógica gerencial entra aqui (Independente do Status Sefaz)
            df_temp = extrair_tags_simples(xml_saidas)
            st.write(f"Gerando relatório com base em {len(df_temp)} notas de saída...")
            st.dataframe(df_temp.head()) # Exemplo
