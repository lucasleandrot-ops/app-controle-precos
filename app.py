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
    
    # Codifica o texto para formato de URL
    texto_url = urllib.parse.quote(texto)
    return f"https://api.whatsapp.com/send?text={texto_url}"

# --- BARRA LATERAL: IDENTIFICAÇÃO ---
st.sidebar.title("👤 Identificação")
usuario_atual = st.sidebar.text_input("Seu Nome", value="Visitante").strip().capitalize()

# 2. Estrutura de Abas
aba_minha_lista, aba_lancamento, aba_cadastros = st.tabs(["📋 Minha Lista", "💰 Lançar Preço", "⚙️ Cadastros"])

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
        res_hist = supabase.table("historico_precos").select("preco, produtos(id, nome, marca), supermercados(nome)").execute()
        
        if res_hist.data:
            df = pd.json_normalize(res_hist.data)
            df_lista = df[df['produtos.id'].isin(ids_salvos)]
            
            if not df_lista.empty:
                idx_min = df_lista.groupby('produtos.id')['preco'].idxmin()
                melhores = df_lista.loc[idx_min].sort_values(by="supermercados.nome")
                
                total_val = melhores['preco'].sum()
                
                c1, c2 = st.columns([1, 1])
                with c1:
                    st.metric("Estimativa Total", f"R$ {total_val:.2f}")
                with c2:
                    # Botão do WhatsApp
                    link_wa = gerar_link_whatsapp(usuario_atual, melhores, total_val)
                    st.markdown(f"""
                        <a href="{link_wa}" target="_blank" style="text-decoration: none;">
                            <button style="background-color: #25D366; color: white; border: none; padding: 10px 20px; border-radius: 5px; cursor: pointer; font-weight: bold; margin-top: 25px;">
                                📱 Enviar para WhatsApp
                            </button>
                        </a>
                    """, unsafe_allow_html=True)

                st.subheader("🛒 Onde comprar cada item:")
                for mercado in melhores['supermercados.nome'].unique():
                    itens_mercado = melhores[melhores['supermercados.nome'] == mercado]
                    subtotal = itens_mercado['preco'].sum()
                    with st.expander(f"📍 {mercado} — Subtotal: R$ {subtotal:.2f}", expanded=True):
                        for _, row in itens_mercado.iterrows():
                            n_exib = f"{row['produtos.nome']} ({row['produtos.marca']})" if row['produtos.marca'] else row['produtos.nome']
                            st.write(f"✅ **{n_exib}**: R$ {row['preco']:.2f}")
            else:
                st.warning("Itens sem preços registrados.")
        else:
            st.warning("Nenhum preço no sistema.")
    else:
        st.info("Sua lista está vazia.")

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

# --- ABA 3: CADASTROS ---
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
