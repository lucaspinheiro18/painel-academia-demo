"""Tela inicial (capa) do app: apresentação curta e um botão para entrar no painel."""
import streamlit as st

CSS = """
<style>
section[data-testid="stSidebar"], [data-testid="stSidebarCollapsedControl"], [data-testid="collapsedControl"] {display: none;}
.block-container {max-width: 980px; padding-top: 4.5rem;}
.hero {
    background:
        radial-gradient(circle at 88% 18%, rgba(255,255,255,.13) 0, rgba(255,255,255,.13) 84px, transparent 85px),
        radial-gradient(circle at 10% 90%, rgba(255,255,255,.08) 0, rgba(255,255,255,.08) 120px, transparent 121px),
        linear-gradient(135deg, #0b2447 0%, #1d5fb8 58%, #1baf7a 135%);
    color: #ffffff; text-align: center; border-radius: 28px; padding: 64px 28px 56px;
    box-shadow: 0 18px 50px rgba(11, 36, 71, .28);
}
.hero .eyebrow {letter-spacing: .14em; text-transform: uppercase; font-size: .74rem; opacity: .85; margin-bottom: 18px;}
.hero .titulo {font-size: 2.6rem; font-weight: 800; line-height: 1.1; margin: 0 0 14px;}
.hero .sub {font-size: 1.2rem; opacity: .92; max-width: 560px; margin: 0 auto 28px;}
.hero .chips span {
    display: inline-block; margin: 4px; padding: 8px 18px; border-radius: 999px; font-size: .95rem;
    background: rgba(255,255,255,.16); border: 1px solid rgba(255,255,255,.30);
}
.nota {text-align: center; opacity: .65; font-size: .85rem; margin-top: 18px;}
div[data-testid="stButton"] > button[kind="primary"] {
    background: #eb6834; border: none; color: #fff; font-size: 1.15rem; font-weight: 700;
    padding: .9rem 1.5rem; border-radius: 999px; box-shadow: 0 10px 24px rgba(235, 104, 52, .35);
    transition: transform .15s ease, box-shadow .15s ease, background .15s ease;
}
div[data-testid="stButton"] > button[kind="primary"] p {font-size: 1.2rem; font-weight: 700;}
div[data-testid="stButton"] > button[kind="primary"]:hover {
    background: #d9562a; transform: translateY(-2px); box-shadow: 0 14px 28px rgba(235, 104, 52, .45);
}
</style>
"""

HERO = """
<div class="hero">
  <div class="eyebrow">Trabalho final · Estatística Aplicada às Ciências Humanas e Sociais</div>
  <div class="titulo">⚽ Painel Operacional de Cursos</div>
  <div class="sub">Avisos, respostas aos alunos e testes de hipóteses em um só lugar.</div>
  <div class="chips">
    <span>📢 Avisos prontos</span><span>💬 Respostas com IA</span><span>🧪 Hipóteses estatísticas</span>
  </div>
</div>
"""


def mostrar() -> bool:
    """Desenha a capa. Devolve True quando a pessoa clica em 'Entrar no painel'."""
    st.markdown(CSS, unsafe_allow_html=True)
    st.markdown(HERO, unsafe_allow_html=True)
    st.write("")
    st.write("")
    _, meio, _ = st.columns([1, 1.4, 1])
    with meio:
        entrou = st.button("Entrar no painel →", type="primary", width="stretch")
    st.markdown('<div class="nota">Versão de demonstração · dados fictícios de planejamento 2027</div>', unsafe_allow_html=True)
    return entrou
