import streamlit as st
import pandas as pd
from supabase import create_client, Client

# 1. Configuração e Conexão
st.set_page_config(page_title="Controle de Preços", page_icon="🛒", layout="centered")
st.title("🛒 App de Controle de Preços")

@st.cache_resource
def init_connection():
    url = st.secrets["SUPABASE_URL"]
    key = st.secrets["SUPABASE_KEY"]
    return create_client(url, key)

supabase: Client = init_connection()

# 2. Estrutura de Abas
aba_lancamento, aba_cadastros, aba_historico = st.tabs(["Lançar Preço", "Cadastros", "Histórico e Análises"])

# 3. Aba de Lançamento de Preços
with aba_lancamento:
    st.header("Registrar Novo Preço")
    
    resposta_produtos = supabase.table("produtos").select("*").execute()
    resposta_mercados = supabase.table("supermercados").select("*").execute()
    
    produtos = resposta_produtos.data
    mercados = resposta_mercados.data
    
    if not produtos or not mercados:
        st.warning("Cadastre pelo menos um produto e um supermercado na aba 'Cadastros' para começar.")
    else:
        dict_produtos = {f"{p['nome']} ({p['marca']})" if p['marca'] else p['nome']: p['id'] for p in produtos}
        dict_mercados = {m['nome']: m['id'] for m in mercados}
        
        with st.form("form_preco", clear_on_submit=True):
            produto_selecionado = st.selectbox("Produto", options=list(dict_produtos.keys()))
            mercado_selecionado = st.selectbox("Supermercado", options=list(dict_mercados.keys()))
            preco = st.number_input("Preço Atual (R$)", min_value=0.01, format="%.2f", step=0.50)
            submit = st.form_submit_button("Salvar Preço")
            
            if submit:
                id_prod = dict_produtos[produto_selecionado]
                id_merc = dict_mercados[mercado_selecionado]
                supabase.table("historico_precos").insert({
                    "id_produto": id_prod,
                    "id_supermercado": id_merc,
                    "preco": preco
                }).execute()
                st.success(f"Preço de R$ {preco:.2f} registrado para '{produto_selecionado}' no '{mercado_selecionado}'!")

# 4. Aba de Cadastros
with aba_cadastros:
    st.header("Cadastros de Apoio")
    col1, col2 = st.columns(2)
    
    with col1:
        st.subheader("Novo Supermercado")
        with st.form("form_mercado", clear_on_submit=True):
            nome_mercado = st.text_input("Nome do estabelecimento")
            if st.form_submit_button("Salvar Supermercado"):
                if nome_mercado:
                    supabase.table("supermercados").insert({"nome": nome_mercado}).execute()
                    st.success(f"'{nome_mercado}' cadastrado!")
                    st.rerun()
                else:
                    st.warning("Digite o nome do supermercado.")

    with col2:
        st.subheader("Novo Produto")
        with st.form("form_produto", clear_on_submit=True):
            nome_produto = st.text_input("Nome do produto")
            marca_produto = st.text_input("Marca (Opcional)")
            if st.form_submit_button("Salvar Produto"):
                if nome_produto:
                    supabase.table("produtos").insert({"nome": nome_produto, "marca": marca_produto}).execute()
                    st.success(f"'{nome_produto}' cadastrado!")
                    st.rerun()
                else:
                    st.warning("Digite o nome do produto.")

# 5. Aba de Histórico e Análises
with aba_historico:
    st.header("Análise de Preços")
    
    # Busca os dados relacionais (trazendo os nomes em vez dos IDs)
    resposta_historico = supabase.table("historico_precos").select("preco, data_registro, produtos(nome, marca), supermercados(nome)").execute()
    dados_historico = resposta_historico.data
    
    if not dados_historico:
        st.info("Nenhum preço registrado ainda. Faça lançamentos para ver os gráficos.")
    else:
        # Transformando os dados brutos em uma tabela organizada do Pandas
        lista_formatada = []
        for linha in dados_historico:
            nome_prod = f"{linha['produtos']['nome']} ({linha['produtos']['marca']})" if linha['produtos']['marca'] else linha['produtos']['nome']
            lista_formatada.append({
                "Produto": nome_prod,
                "Supermercado": linha['supermercados']['nome'],
                "Preço (R$)": float(linha['preco']),
                "Data": linha['data_registro']
            })
            
        df = pd.DataFrame(lista_formatada)
        df["Data"] = pd.to_datetime(df["Data"]).dt.date # Formata a data corretamente
        
        # --- SEÇÃO 1: Lista de Compras Inteligente ---
        st.subheader("🛒 Sua Lista de Compras (Menor Preço)")
        st.write("Onde comprar cada item hoje baseado nos últimos registros.")
        
        # Lógica: Ordena pelas datas mais recentes, agrupa por produto e pega a linha com menor preço
        df_ordenado = df.sort_values(by="Data", ascending=False)
        indice_menor_preco = df_ordenado.groupby("Produto")["Preço (R$)"].idxmin()
        df_melhor_compra = df_ordenado.loc[indice_menor_preco].reset_index(drop=True)
        
        # Exibe a tabela formatada
        st.dataframe(df_melhor_compra, use_container_width=True, hide_index=True)
        
        st.divider()
        
        # --- SEÇÃO 2: Linha do Tempo e Tendências ---
        st.subheader("📈 Linha do Tempo por Produto")
        produto_grafico = st.selectbox("Escolha um produto para ver a variação de preço:", df["Produto"].unique())
        
        df_filtrado = df[df["Produto"] == produto_grafico]
        
        # Gráfico de linha separando os supermercados por cor
        st.line_chart(df_filtrado, x="Data", y="Preço (R$)", color="Supermercado")
        
        st.divider()
        
        # --- SEÇÃO 3: Tabela Bruta (Últimos Lançamentos) ---
        st.subheader("📋 Últimos Lançamentos")
        st.dataframe(df_ordenado, use_container_width=True, hide_index=True)