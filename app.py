import streamlit as st
import pandas as pd
from supabase import create_client, Client
import urllib.parse

# 1. Configuração e Conexão
st.set_page_config(page_title="Controle de Preços", page_icon="🛒", layout="wide")

@st.cache_resource
def init_connection():
    url = st.secrets["SUPABASE_URL"]
    key = st.secrets["SUPABASE_KEY"]
    return create_client(url, key)

supabase: Client = init_connection()

# Função para formatar a mensagem do WhatsApp
def gerar_link_whatsapp(nome_usuario, df_melhores, total):
    texto = f"🛒 *Lista de Compras - {nome_usuario}*\n\n"
    for mercado in df_melhores['supermercados.nome'].unique():
        itens_mercado = df_melhores[df_melhores['supermercados.nome'] == mercado]
        subtotal = itens_mercado['preco'].sum()
        texto += f"📍 *{mercado}* (Subtotal: R$ {subtotal:.2f})\n"
        for _, row in itens_mercado.iterrows():
            nome = f"{row['produtos.nome']} ({row['produtos.marca']})" if row['produtos.marca'] else row['produtos.nome']
            texto += f"- {nome}: R$ {row['preco']:.2f}\n"
        texto += "\n"
    texto += f"💰 *Total Estimado: R$ {total:.2f}*"
    texto_url = urllib.parse.quote(texto)
    return f"https://api.whatsapp.com/send?text={texto_url}"

# --- BARRA LATERAL ---
st.sidebar.title("👤 Identificação")
usuario_atual = st.sidebar.text_input("Seu Nome", value="Visitante").strip().capitalize()

# 2. Estrutura de Abas (Adicionada aba de Histórico Geral)
aba_minha_lista, aba_lancamento, aba_analise, aba_cadastros = st.tabs([
    "📋 Minha Lista", "💰 Lançar Preço", "📈 Histórico Geral", "⚙️ Cadastros"
])

# --- ABA 1: MINHA LISTA ---
with aba_minha_lista:
    st.header(f"Lista de Compras: {usuario_atual}")
    res_prod = supabase.table("produtos").select("*").execute()
    produtos_data = res_prod.data
    dict_produtos = {f"{p['nome']} ({p['marca']})" if p['marca'] else p['nome']: p['id'] for p in produtos_data}
    
    res_minha_lista = supabase.table("listas").select("produto_id").eq("nome_usuario", usuario_atual).execute()
    ids_salvos = [item['produto_id'] for item in res_minha_lista.data]
    nomes_salvos = [name for name, id in dict_produtos.items() if id in ids_salvos]
    
    selecionados = st.multiselect("O que você precisa comprar hoje?", options=list(dict_produtos.keys()), default=nomes_salvos)
    
    if st.button("Salvar/Atualizar Minha Lista"):
        supabase.table("listas").delete().eq("nome_usuario", usuario_atual).execute()
        for item in selecionados:
            supabase.table("listas").insert({"nome_usuario": usuario_atual, "produto_id": dict_produtos[item]}).execute()
        st.success("Lista salva!")
        st.rerun()

    st.divider()

    if ids_salvos:
        res_hist = supabase.table("historico_precos").select("preco, data_registro, produtos(id, nome, marca), supermercados(nome)").execute()
        if res_hist.data:
            df = pd.json_normalize(res_hist.data)
            df_lista = df[df['produtos.id'].isin(ids_salvos)]
            if not df_lista.empty:
                idx_min = df_lista.groupby('produtos.id')['preco'].idxmin()
                melhores = df_lista.loc[idx_min].sort_values(by="supermercados.nome")
                total_val = melhores['preco'].sum()
                
                c1, c2 = st.columns([1, 1])
                with c1: st.metric("Estimativa Total", f"R$ {total_val:.2f}")
                with c2:
                    link_wa = gerar_link_whatsapp(usuario_atual, melhores, total_val)
                    st.markdown(f'<a href="{link_wa}" target="_blank"><button style="background-color: #25D366; color: white; border: none; padding: 10px 20px; border-radius: 5px; cursor: pointer; font-weight: bold; margin-top: 25px;">📱 Enviar WhatsApp</button></a>', unsafe_allow_html=True)

                for mercado in melhores['supermercados.nome'].unique():
                    itens_m = melhores[melhores['supermercados.nome'] == mercado]
                    with st.expander(f"📍 {mercado} — R$ {itens_m['preco'].sum():.2f}", expanded=True):
                        for _, row in itens_m.iterrows():
                            n = f"{row['produtos.nome']} ({row['produtos.marca']})" if row['produtos.marca'] else row['produtos.nome']
                            st.write(f"✅ **{n}**: R$ {row['preco']:.2f}")

# --- ABA 2: LANÇAMENTO ---
with aba_lancamento:
    st.header("💰 Registrar Novo Preço")
    res_merc = supabase.table("supermercados").select("*").execute()
    mercados_data = res_merc.data
    if not produtos_data or not mercados_data:
        st.warning("Cadastre produtos e mercados primeiro.")
    else:
        dict_mercados = {m['nome']: m['id'] for m in mercados_data}
        with st.form("form_preco", clear_on_submit=True):
            p_sel = st.selectbox("Produto", options=list(dict_produtos.keys()))
            m_sel = st.selectbox("Supermercado", options=list(dict_mercados.keys()))
            valor = st.number_input("Preço (R$)", min_value=0.01, step=0.01)
            if st.form_submit_button("Salvar"):
                supabase.table("historico_precos").insert({"id_produto": dict_produtos[p_sel], "id_supermercado": dict_mercados[m_sel], "preco": valor}).execute()
                st.success("Salvo!")

# --- NOVA ABA 3: HISTÓRICO GERAL (A VOLTA DOS DADOS) ---
with aba_analise:
    st.header("📈 Histórico e Tendências")
    res_h = supabase.table("historico_precos").select("preco, data_registro, produtos(nome, marca), supermercados(nome)").execute()
    if res_h.data:
        df_h = pd.json_normalize(res_h.data)
        df_h['Produto'] = df_h.apply(lambda x: f"{x['produtos.nome']} ({x['produtos.marca']})" if x['produtos.marca'] else x['produtos.nome'], axis=1)
        df_h['Data'] = pd.to_datetime(df_h['data_registro']).dt.date
        
        st.subheader("Variação de Preços")
        prod_alvo = st.selectbox("Selecione um produto para ver o gráfico:", options=sorted(df_h['Produto'].unique()))
        df_grafico = df_h[df_h['Produto'] == prod_alvo]
        st.line_chart(df_grafico, x="Data", y="preco", color="supermercados.nome")
        
        st.subheader("Todos os Registros")
        st.dataframe(df_h[['Data', 'Produto', 'supermercados.nome', 'preco']].sort_values(by='Data', ascending=False), use_container_width=True)
    else:
        st.info("Ainda não há dados históricos para exibir.")

# --- ABA 4: CADASTROS ---
with aba_cadastros:
    st.header("⚙️ Cadastros")
    c1, c2 = st.columns(2)
    with c1:
        with st.form("cad_m", clear_on_submit=True):
            n_m = st.text_input("Novo Supermercado")
            if st.form_submit_button("Cadastrar Mercado"):
                if n_m: 
                    supabase.table("supermercados").insert({"nome": n_m}).execute()
                    st.rerun()
    with c2:
        with st.form("cad_p", clear_on_submit=True):
            n_p = st.text_input("Novo Produto")
            m_p = st.text_input("Marca")
            if st.form_submit_button("Cadastrar Produto"):
                if n_p: 
                    supabase.table("produtos").insert({"nome": n_p, "marca": m_p}).execute()
                    st.rerun()
