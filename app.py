import streamlit as st
import pandas as pd
from supabase import create_client, Client

# 1. Configuração e Conexão
st.set_page_config(page_title="Controle de Preços", page_icon="🛒", layout="wide")

@st.cache_resource
def init_connection():
    url = st.secrets["SUPABASE_URL"]
    key = st.secrets["SUPABASE_KEY"]
    return create_client(url, key)

supabase: Client = init_connection()

# --- BARRA LATERAL: IDENTIFICAÇÃO ---
st.sidebar.title("👤 Identificação")
usuario_atual = st.sidebar.text_input("Seu Nome", value="Visitante").strip().capitalize()
st.sidebar.info(f"Gerenciando lista de: **{usuario_atual}**")

# 2. Estrutura de Abas
aba_minha_lista, aba_lancamento, aba_cadastros = st.tabs(["📋 Minha Lista", "💰 Lançar Preço", "⚙️ Cadastros"])

# --- ABA 1: MINHA LISTA (INTELIGÊNCIA DE COMPRA) ---
with aba_minha_lista:
    st.header(f"Lista de Compras: {usuario_atual}")
    
    # Busca produtos cadastrados
    res_prod = supabase.table("produtos").select("*").execute()
    produtos_data = res_prod.data
    dict_produtos = {f"{p['nome']} ({p['marca']})" if p['marca'] else p['nome']: p['id'] for p in produtos_data}
    
    # Busca o que já está salvo para este usuário na tabela 'listas'
    res_minha_lista = supabase.table("listas").select("produto_id").eq("nome_usuario", usuario_atual).execute()
    ids_salvos = [item['produto_id'] for item in res_minha_lista.data]
    
    # Identifica os nomes dos produtos já salvos para aparecerem selecionados no multiselect
    nomes_salvos = [name for name, id in dict_produtos.items() if id in ids_salvos]
    
    selecionados = st.multiselect("O que você precisa comprar hoje?", options=list(dict_produtos.keys()), default=nomes_salvos)
    
    if st.button("Salvar/Atualizar Minha Lista"):
        # Limpa e atualiza a lista do usuário
        supabase.table("listas").delete().eq("nome_usuario", usuario_atual).execute()
        for item in selecionados:
            supabase.table("listas").insert({"nome_usuario": usuario_atual, "produto_id": dict_produtos[item]}).execute()
        st.success("Lista salva com sucesso!")
        st.rerun()

    st.divider()

    # Cálculo da melhor rota baseada nos menores preços
    if ids_salvos:
        # Busca todo o histórico de preços com relacionamentos
        res_hist = supabase.table("historico_precos").select("preco, data_registro, produtos(id, nome, marca), supermercados(nome)").execute()
        
        if res_hist.data:
            df = pd.json_normalize(res_hist.data)
            # Filtra apenas o que está na lista do usuário
            df_lista = df[df['produtos.id'].isin(ids_salvos)]
            
            if not df_lista.empty:
                # Pega a linha do menor preço para cada produto
                idx_min = df_lista.groupby('produtos.id')['preco'].idxmin()
                melhores = df_lista.loc[idx_min]
                
                # Exibe métrica do valor total estimado
                total_geral = melhores['preco'].sum()
                st.metric("Estimativa Total da Lista", f"R$ {total_geral:.2
