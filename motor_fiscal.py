import pandas as pd
import numpy as np
from datetime import datetime
import streamlit as st

class AnalisadorFiscalConsolidado:
    def __init__(self, df_icms=None, df_pis=None, df_cofins=None, df_ipi=None):
        """
        Inicializa o motor de análise. Pode ser alimentado por DataFrames 
        diretamente da interface do Streamlit.
        """
        self.data_processamento = datetime.now().strftime("%d/%m/%Y %H:%M:%S")
        self.df_icms = df_icms if df_icms is not None else pd.DataFrame()
        self.df_pis = df_pis if df_pis is not None else pd.DataFrame()
        self.df_cofins = df_cofins if df_cofins is not None else pd.DataFrame()
        self.df_ipi = df_ipi if df_ipi is not None else pd.DataFrame()
        self.df_final = self.df_icms.copy()

    def analisar_aba_pis(self):
        """Analisa a consistência do PIS: Calculado vs Declarado"""
        if not self.df_pis.empty:
            # Garante que as colunas necessárias existam
            cols = ['base_calculo', 'aliquota_pis', 'valor_pis_declarado']
            if all(c in self.df_pis.columns for c in cols):
                self.df_pis['valor_pis_calculado'] = self.df_pis['base_calculo'] * (self.df_pis['aliquota_pis'] / 100)
                self.df_pis['status_pis'] = np.where(
                    abs(self.df_pis['valor_pis_calculado'] - self.df_pis['valor_pis_declarado']) < 0.01, 
                    'OK', 'Divergente'
                )
        return self

    def analisar_aba_cofins(self):
        """Analisa a consistência do COFINS: Calculado vs Declarado"""
        if not self.df_cofins.empty:
            cols = ['base_calculo', 'aliquota_cofins', 'valor_cofins_declarado']
            if all(c in self.df_cofins.columns for c in cols):
                self.df_cofins['valor_cofins_calculado'] = self.df_cofins['base_calculo'] * (self.df_cofins['aliquota_cofins'] / 100)
                self.df_cofins['status_cofins'] = np.where(
                    abs(self.df_cofins['valor_cofins_calculado'] - self.df_cofins['valor_cofins_declarado']) < 0.01, 
                    'OK', 'Divergente'
                )
        return self

    def analisar_aba_ipi(self):
        """Analisa a incidência de IPI na aba específica"""
        if not self.df_ipi.empty:
            cols = ['base_calculo', 'aliquota_ipi']
            if all(c in self.df_ipi.columns for c in cols):
                self.df_ipi['valor_ipi_calculado'] = self.df_ipi['base_calculo'] * (self.df_ipi['aliquota_ipi'] / 100)
                self.df_ipi['status_ipi'] = np.where(
                    self.df_ipi['aliquota_ipi'] > 20, 'Alíquota Alta - Revisar', 'OK'
                )
        return self

    def integrar_e_consolidar(self):
        """
        Realiza o merge de todas as abas analisadas na base principal (ICMS).
        """
        if self.df_final.empty:
            return self

        # Integração PIS
        if 'status_pis' in self.df_pis.columns:
            self.df_final = self.df_final.merge(
                self.df_pis[['id_item', 'valor_pis_calculado', 'status_pis']], on='id_item', how='left'
            )
        
        # Integração COFINS
        if 'status_cofins' in self.df_cofins.columns:
            self.df_final = self.df_final.merge(
                self.df_cofins[['id_item', 'valor_cofins_calculado', 'status_cofins']], on='id_item', how='left'
            )
            
        # Integração IPI
        if 'status_ipi' in self.df_ipi.columns:
            self.df_final = self.df_final.merge(
                self.df_ipi[['id_item', 'valor_ipi_calculado', 'status_ipi']], on='id_item', how='left'
            )

        # Cálculo da Carga Tributária Total Consolidada
        self.df_final['total_tributos_federais'] = (
            self.df_final.get('valor_pis_calculado', 0).fillna(0) + 
            self.df_final.get('valor_cofins_calculado', 0).fillna(0) + 
            self.df_final.get('valor_ipi_calculado', 0).fillna(0)
        )
        
        self.df_final['carga_total_geral'] = (
            self.df_final['total_tributos_federais'] + self.df_final.get('valor_icms', 0)
        )
        
        return self

    def aplicar_aprovacao_nivel_1(self):
        """
        Aprovação 1: Validação de integridade entre todas as abas.
        """
        if self.df_final.empty:
            return self

        # Verifica se as colunas de status existem antes de validar
        cond_pis = self.df_final.get('status_pis') == 'OK' if 'status_pis' in self.df_final.columns else True
        cond_cofins = self.df_final.get('status_cofins') == 'OK' if 'status_cofins' in self.df_final.columns else True
        cond_ipi = self.df_final.get('status_ipi') == 'OK' if 'status_ipi' in self.df_final.columns else True

        condicoes = [
            (cond_pis & cond_cofins & cond_ipi),
            (self.df_final['valor_item'] <= 0)
        ]
        escolhas = ['Aprovado 1', 'Erro: Valor Negativo']
        
        self.df_final['status_aprovacao'] = np.select(condicoes, escolhas, default='Revisão Fiscal Necessária')
        self.df_final['data_analise'] = self.data_processamento
        
        return self

    def gerar_output_github(self):
        """Retorna o DataFrame final e exibe log no terminal/Streamlit"""
        if self.df_final.empty:
            return pd.DataFrame()

        print(f"Auditoria Fiscal Consolidada - {self.data_processamento}")
        return self.df_final

# --- INTERFACE STREAMLIT ---

def main():
    st.set_page_config(page_title="Sentinela Fiscal", layout="wide")
    st.title("🛡️ Sentinela: Análise Fiscal PIS/COFINS/IPI")

    uploaded_file = st.file_uploader("Upload da Planilha Fiscal (.xlsx)", type="xlsx")

    if uploaded_file:
        try:
            # Lendo as abas
            df_icms = pd.read_excel(uploaded_file, sheet_name='ICMS')
            df_pis = pd.read_excel(uploaded_file, sheet_name='PIS')
            df_cofins = pd.read_excel(uploaded_file, sheet_name='COFINS')
            df_ipi = pd.read_excel(uploaded_file, sheet_name='IPI')

            # Processamento
            analisador = AnalisadorFiscalConsolidado(df_icms, df_pis, df_cofins, df_ipi)
            df_resultado = (analisador.analisar_aba_pis()
                                      .analisar_aba_cofins()
                                      .analisar_aba_ipi()
                                      .integrar_e_consolidar()
                                      .aplicar_aprovacao_nivel_1()
                                      .gerar_output_github())

            # Exibição
            st.subheader("Resultado da Integração")
            st.dataframe(df_resultado)

            # Botão de Download
            csv = df_resultado.to_csv(index=False).encode('utf-8')
            st.download_button("Baixar Relatório Consolidado", csv, "analise_sentinela.csv", "text/csv")

        except Exception as e:
            st.error(f"Erro ao processar as abas: {e}")

if __name__ == "__main__":
    main()
