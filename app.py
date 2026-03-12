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

# --- NOVO: IDENTIFICAÇÃO DE USUÁRIO ---
st.sidebar.title("👤 Identificação")
usuario_atual = st.sidebar.text_input("Seu Nome", value="Visitante").strip().capitalize()
st.sidebar.write(f"Logado como: **{usuario_atual}**")

# 2. Estrutura de Abas
aba_minha_lista, aba_lancamento, aba_cadastros = st.tabs(["Minha Lista", "Lançar Preço", "Cadastros"])

# --- ABA 1: MINHA LISTA (Onde a mágica acontece) ---
with aba_minha_lista:
    st.header(f"Lista de Compras de {usuario_atual}")
    
    # Busca produtos cadastrados para o multiselect
    res_prod = supabase.table("produtos").select("*").execute()
    dict_produtos = {f"{p['nome']} ({p['marca']})" if p['marca'] else p['nome']: p['id'] for p in res_prod.data}
    
    # Seleção de itens para a lista fixa do usuário
    selecionados = st.multiselect("Adicionar itens à minha lista:", options=list(dict_produtos.keys()))
    
    if st.button("Atualizar Minha Lista"):
        # Limpa a lista antiga do usuário e salva a nova
        supabase.table("listas").delete().eq("nome_usuario", usuario_atual).execute()
        for item in selecionados:
            supabase.table("listas").insert({
                "nome_usuario": usuario_atual,
                "produto_id": dict_produtos[item]
            }).execute()
        st.success("Lista salva!")
        st.rerun()

    st.divider()

    # BUSCA A LISTA SALVA E CRUZA COM OS MENORES PREÇOS
    res_minha_lista = supabase.table("listas").select("produto_id").eq("nome_usuario", usuario_atual).execute()
    ids_na_lista = [item['produto_id'] for item in res_minha_lista.data]

    if ids_na_lista:
        # Busca o histórico de preços
        res_hist = supabase.table("historico_precos").select("preco, produtos(id, nome, marca), supermercados(nome)").execute()
        df = pd.json_normalize(res_hist.data)
        
        # Filtra apenas os produtos que estão na lista do usuário
        df_lista = df[df['produtos.id'].isin(ids_na_lista)]
        
        if not df_lista.empty:
            # Encontra o menor preço para cada produto
            idx_min = df_lista.groupby('produtos.id')['preco'].idxmin()
            melhores_opcoes = df_lista.loc[idx_min]
            
            st.subheader("🛒 Onde comprar cada item hoje:")
            for mercado in melhores_opcoes['supermercados.nome'].unique():
                with st.expander(f"📍 No {mercado}", expanded=True):
                    itens_mercado = melhores_opcoes[melhores_opcoes['supermercados.nome'] == mercado]
                    for _, row in itens_mercado.iterrows():
                        nome = f"{row['produtos.nome']} ({row['produtos.marca']})" if row['produtos.marca'] else row['produtos.nome']
                        st.write(f"- **{nome}**: R$ {row['preco']:.2f}")
    else:
        st.info("Sua lista está vazia. Adicione produtos acima.")

# --- ABA 2 e 3: LANÇAMENTOS E CADASTROS (Mantemos a lógica anterior) ---
with aba_lancamento:
    st.header("Registrar Novo Preço")
    # ... (mesmo código de lançamento que já funcionava)
    st.write("Mantenha o código de formulário de preços aqui")

with aba_cadastros:
    st.header("Cadastros")
    # ... (mesmo código de cadastro de produtos/mercados)
    st.write("Mantenha o código de cadastro aqui")
