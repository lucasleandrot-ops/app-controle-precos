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
st.sidebar.info(f"As listas de compras são salvas individualmente para: **{usuario_atual}**")

# 2. Estrutura de Abas
aba_minha_lista, aba_lancamento, aba_cadastros = st.tabs(["📋 Minha Lista", "💰 Lançar Preço", "⚙️ Cadastros"])

# --- ABA 1: MINHA LISTA ---
with aba_minha_lista:
    st.header(f"Lista de Compras: {usuario_atual}")
    
    # Busca produtos cadastrados
    res_prod = supabase.table("produtos").select("*").execute()
    produtos_data = res_prod.data
    dict_produtos = {f"{p['nome']} ({p['marca']})" if p['marca'] else p['nome']: p['id'] for p in produtos_data}
    
    # Busca o que já está salvo para este usuário
    res_minha_lista = supabase.table("listas").select("produto_id").eq("nome_usuario", usuario_atual).execute()
    ids_salvos = [item['produto_id'] for item in res_minha_lista.data]
    
    # Inverte o dicionário para pegar nomes pelos IDs salvos
    nomes_salvos = [name for name, id in dict_produtos.items() if id in ids_salvos]
    
    selecionados = st.multiselect("O que você precisa comprar hoje?", options=list(dict_produtos.keys()), default=nomes_salvos)
    
    if st.button("Salvar Minha Lista"):
        # Atualiza o banco: deleta o anterior e insere o novo
        supabase.table("listas").delete().eq("nome_usuario", usuario_atual).execute()
        for item in selecionados:
            supabase.table("listas").insert({"nome_usuario": usuario_atual, "produto_id": dict_produtos[item]}).execute()
        st.success("Lista atualizada com sucesso!")
        st.rerun()

    st.divider()

    # CRUZAMENTO DE DADOS: Menor Preço para os itens da lista
    if ids_salvos:
        res_hist = supabase.table("historico_precos").select("preco, data_registro, produtos(id, nome, marca), supermercados(nome)").execute()
        if res_hist.data:
            df = pd.json_normalize(res_hist.data)
            df_lista = df[df['produtos.id'].isin(ids_salvos)]
            
            if not df_lista.empty:
                # Lógica: Menor preço histórico para cada item da lista
                idx_min = df_lista.groupby('produtos.id')['preco'].idxmin()
                melhores = df_lista.loc[idx_min].sort_values(by="supermercados.nome")
                
                st.subheader("🛒 Rota de Compras Recomendada")
                for mercado in melhores['supermercados.nome'].unique():
                    with st.expander(f"📍 {mercado}", expanded=True):
                        itens = melhores[melhores['supermercados.nome'] == mercado]
                        for _, row in itens.iterrows():
                            nome = f"{row['produtos.nome']} ({row['produtos.marca']})" if row['produtos.marca'] else row['produtos.nome']
                            st.write(f"✅ **{nome}**: R$ {row['preco']:.2f} (em {pd.to_datetime(row['data_registro']).strftime('%d/%m')})")
        else:
            st.warning("Nenhum preço cadastrado no sistema ainda.")
    else:
        st.info("Sua lista está vazia.")

# --- ABA 2: LANÇAMENTO ---
with aba_lancamento:
    st.header("Registrar Novo Preço")
    res_merc = supabase.table("supermercados").select("*").execute()
    mercados_data = res_merc.data
    
    if not produtos_data or not mercados_data:
        st.warning("Cadastre produtos e supermercados primeiro.")
    else:
        dict_mercados = {m['nome']: m['id'] for m in mercados_data}
        with st.form("novo_preco", clear_on_submit=True):
            p_sel = st.selectbox("Produto", options=list(dict_produtos.keys()))
            m_sel = st.selectbox("Supermercado", options=list(dict_mercados.keys()))
            valor = st.number_input("Preço (R$)", min_value=0.01, step=0.01, format="%.2f")
            if st.form_submit_button("Salvar Lançamento"):
                supabase.table("historico_precos").insert({"id_produto": dict_produtos[p_sel], "id_supermercado": dict_mercados[m_sel], "preco": valor}).execute()
                st.success("Preço registrado!")

# --- ABA 3: CADASTROS ---
with aba_cadastros:
    st.header("Configurações do App")
    c1, c2 = st.columns(2)
    with c1:
        st.subheader("Novo Supermercado")
        with st.form("cad_merc", clear_on_submit=True):
            n_m = st.text_input("Nome")
            if st.form_submit_button("Cadastrar"):
                if n_m: 
                    supabase.table("supermercados").insert({"nome": n_m}).execute()
                    st.rerun()
    with c2:
        st.subheader("Novo Produto")
        with st.form("cad_prod", clear_on_submit=True):
            n_p = st.text_input("Nome (ex: Arroz)")
            m_p = st.text_input("Marca (ex: Tio João)")
            if st.form_submit_button("Cadastrar"):
                if n_p: 
                    supabase.table("produtos").insert({"nome": n_p, "marca": m_p}).execute()
                    st.rerun()
