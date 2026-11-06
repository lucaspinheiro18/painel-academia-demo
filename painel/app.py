"""Painel Streamlit: Gerador de Avisos + Assistente de Atendimento (Academia Exemplo)."""
import hmac
import os

import pandas as pd
import streamlit as st

import config
import dados
import demo
import hipoteses
import historico
import ia
import modelos

st.set_page_config(page_title="Academia Exemplo - Operacional", page_icon="⚽", layout="wide")

# ----------------------------------------------------------------------------
# acesso por senha (opcional: só vale se APP_SENHA estiver configurada)
# ----------------------------------------------------------------------------
_senha_app = os.environ.get("APP_SENHA", "")
if _senha_app and not st.session_state.get("autenticado"):
    st.title("⚽ Sistema Operacional - Academia Exemplo (dados fictícios)")
    _tentativa = st.text_input("Senha de acesso", type="password")
    if _tentativa:
        if hmac.compare_digest(_tentativa, _senha_app):
            st.session_state["autenticado"] = True
            st.rerun()
        else:
            st.error("Senha incorreta.")
    st.stop()


def mostrar_avisos(avisos):
    for gravidade, msg in avisos:
        (st.error if gravidade == "erro" else st.warning)(msg)


# ----------------------------------------------------------------------------
# barra lateral
# ----------------------------------------------------------------------------
st.sidebar.title("⚙️ Configurações")

api_key = os.environ.get("GEMINI_API_KEY", "").strip()
if api_key:
    st.sidebar.success("🔑 Chave do Gemini carregada do cofre (Secrets).")
else:
    api_key = st.sidebar.text_input("Cole sua chave do Gemini:", type="password").strip()
    st.sidebar.caption("Dica: guarde a chave nos Secrets do Streamlit para não precisar colar.")

operador = st.sidebar.text_input("Seu nome (vai para o histórico):").strip()

if st.sidebar.button("🔄 Recarregar planilhas", width="stretch"):
    st.cache_data.clear()
    st.rerun()

st.sidebar.divider()
st.sidebar.caption("🔒 CPF, e-mail e telefone são mascarados antes de ir para a IA e para o histórico.")


# ----------------------------------------------------------------------------
# dados (com cache; relê sozinho quando uma planilha muda)
# ----------------------------------------------------------------------------
@st.cache_data(ttl=600, show_spinner="Lendo as planilhas...")
def _carregar(assinatura):
    return dados.carregar_base()


try:
    base = _carregar(dados.assinatura_arquivos())
except Exception as e:  # noqa: BLE001
    st.error(f"Não consegui ler as planilhas: {e}")
    st.stop()

try:
    historico.iniciar()
    demo.semear()   # versão de demonstração: histórico fictício se estiver vazio
except Exception as e:  # noqa: BLE001
    st.sidebar.warning(f"Histórico indisponível: {e}")

if base.avisos:
    with st.sidebar.expander(f"⚠️ Avisos sobre as planilhas ({len(base.avisos)})"):
        mostrar_avisos(base.avisos)

# ----------------------------------------------------------------------------
# página
# ----------------------------------------------------------------------------
st.title("⚽ Sistema Operacional - Academia Exemplo (dados fictícios)")
st.markdown("**Versão de demonstração com dados fictícios.** Use as abas abaixo para gerar avisos, responder dúvidas dos alunos ou ver os testes de hipóteses. "
            "Os textos são **rascunhos**: revise antes de enviar.")

aba_avisos, aba_atendimento, aba_email, aba_resumo, aba_hip = st.tabs(
    ["📢 Gerador de Avisos", "💬 Assistente WhatsApp", "✉️ Assistente de E-mail", "📊 Resumo", "🧪 Hipóteses"])

# ---------------------------- aba 1: avisos ---------------------------------
with aba_avisos:
    col1, col2 = st.columns([1, 2])
    with col1:
        st.subheader("1. Informe os dados")
        id_avisos = st.text_input("ID da Turma (Ex: 932):", key="id_avisos")
        modelo = st.selectbox("Selecione o Modelo:", list(modelos.MODELOS))
        gerar_aviso = st.button("🚀 Gerar Aviso", width="stretch")
    with col2:
        st.subheader("2. Rascunho Gerado")
        if gerar_aviso:
            id_ = dados.parse_id(id_avisos)
            if id_ is None:
                st.error("⚠️ Digite o ID da turma (somente números).")
            elif id_ not in base.turmas:
                st.error(f"⚠️ O ID {id_} não foi encontrado na planilha Academia Exemplo.")
            else:
                turma = base.turmas[id_]
                texto, avisos = modelos.montar(modelo, turma)
                st.caption(f"Turma {turma.id}: {turma.curso_licenca or 'curso não informado'}")
                mostrar_avisos(avisos)
                if not any(g == "erro" for g, _ in avisos):
                    st.success("✨ Aviso gerado!")
                st.code(texto, language=None)

# ------------------------- aba 2: atendimento -------------------------------
with aba_atendimento:
    col_a, col_b = st.columns([1, 2])
    with col_a:
        st.subheader("1. Dúvida do Aluno")
        id_atend = st.text_input("ID da Turma (opcional; deixe em branco para dúvidas gerais):",
                                 key="id_atend")
        mensagem = st.text_area("Cole a mensagem do WhatsApp aqui:", height=150)
        responder = st.button("🤖 Gerar Resposta Inteligente", width="stretch",
                              disabled=not base.faq)
    with col_b:
        st.subheader("2. Resposta do Assistente")
        if not base.faq:
            st.error("A FAQ não foi carregada; este assistente fica indisponível até ela ser corrigida.")
        if responder:
            turma = None
            id_ = dados.parse_id(id_atend) if id_atend.strip() else None
            if not api_key:
                st.error("⚠️ Informe a chave do Gemini (menu lateral ou Secrets).")
            elif not mensagem.strip():
                st.error("⚠️ Cole a mensagem enviada pelo aluno.")
            elif id_atend.strip() and id_ is None:
                st.error("⚠️ O ID da turma deve conter somente números.")
            else:
                if id_ is not None:
                    turma = base.turmas.get(id_)
                    if turma is None:
                        st.warning(f"O ID {id_} não foi encontrado; respondi sem dados da turma.")
                    else:
                        mostrar_avisos(turma.avisos)
                mascarada, n_mascarados = ia.mascarar(mensagem)
                try:
                    with st.spinner("Analisando a dúvida e preparando a resposta..."):
                        texto, ms, encaminhado = ia.gerar_resposta(api_key, mascarada, turma, base.faq_texto)
                except Exception as e:  # noqa: BLE001
                    st.error(f"Erro ao gerar a resposta: {e}")
                else:
                    if encaminhado:
                        assunto = ia.ASSUNTO_FORA_FAQ
                    else:
                        assunto = ia.classificar_assunto(api_key, mascarada, [a for a, _ in base.faq])
                    st.success("✨ Resposta gerada!")
                    st.code(texto, language=None)
                    detalhes = [f"⏱ {ms / 1000:.1f}s"]
                    if assunto:
                        detalhes.append(f"assunto: {assunto}")
                    if encaminhado:
                        detalhes.append("assunto fora da FAQ: orientação de envio por e-mail")
                    if n_mascarados:
                        detalhes.append(f"{n_mascarados} dado(s) pessoal(is) mascarado(s)")
                    st.caption(" · ".join(detalhes))
                    try:
                        historico.registrar(id_ if turma else None, operador, mascarada, texto,
                                            encaminhado, config.MODELO_IA, ms, assunto)
                    except Exception as e:  # noqa: BLE001
                        st.warning(f"A resposta foi gerada, mas não consegui salvar no histórico: {e}")

# ------------------------- aba 3: assistente de e-mail -------------------------
with aba_email:
    col_e1, col_e2 = st.columns([1, 2])
    with col_e1:
        st.subheader("1. E-mail do Aluno")
        id_email = st.text_input("ID da Turma (opcional; deixe em branco para dúvidas gerais):",
                                 key="id_email")
        nome_aluno = st.text_input("Nome do aluno (opcional, para a saudação):", key="nome_email").strip()
        assunto_email = st.text_input("Assunto do e-mail recebido:", key="assunto_email").strip()
        corpo_email = st.text_area("Cole o corpo do e-mail aqui:", height=220, key="corpo_email")
        responder_email = st.button("✉️ Gerar Resposta por E-mail", width="stretch",
                                    disabled=not base.faq, key="btn_email")
    with col_e2:
        st.subheader("2. Resposta por E-mail")
        if not base.faq:
            st.error("A FAQ não foi carregada; este assistente fica indisponível até ela ser corrigida.")
        if responder_email:
            turma = None
            id_ = dados.parse_id(id_email) if id_email.strip() else None
            if not api_key:
                st.error("⚠️ Informe a chave do Gemini (menu lateral ou Secrets).")
            elif not corpo_email.strip():
                st.error("⚠️ Cole o corpo do e-mail enviado pelo aluno.")
            elif id_email.strip() and id_ is None:
                st.error("⚠️ O ID da turma deve conter somente números.")
            else:
                if id_ is not None:
                    turma = base.turmas.get(id_)
                    if turma is None:
                        st.warning(f"O ID {id_} não foi encontrado; respondi sem dados da turma.")
                    else:
                        mostrar_avisos(turma.avisos)
                assunto_masc, n1 = ia.mascarar(assunto_email)
                corpo_masc, n2 = ia.mascarar(corpo_email)
                try:
                    with st.spinner("Analisando o e-mail e redigindo a resposta..."):
                        assunto_resp, texto_resp, ms, fora_faq = ia.gerar_resposta_email(
                            api_key, assunto_masc, corpo_masc, turma, base.faq_texto, nome_aluno)
                except Exception as e:  # noqa: BLE001
                    st.error(f"Erro ao gerar a resposta: {e}")
                else:
                    if fora_faq:
                        assunto_cls = ia.ASSUNTO_FORA_FAQ
                        st.warning("Este assunto não está na FAQ. Deixei uma resposta curta de recebimento: "
                                   "revise ou responda manualmente.")
                    else:
                        assunto_cls = ia.classificar_assunto(
                            api_key, f"{assunto_masc}\n{corpo_masc}", [a for a, _ in base.faq])
                        st.success("✨ Resposta gerada!")
                    st.markdown("**Assunto:**")
                    st.code(assunto_resp, language=None)
                    st.markdown("**Corpo do e-mail:**")
                    st.code(texto_resp, language=None)
                    detalhes = [f"⏱ {ms / 1000:.1f}s"]
                    if assunto_cls:
                        detalhes.append(f"assunto: {assunto_cls}")
                    if n1 + n2:
                        detalhes.append(f"{n1 + n2} dado(s) pessoal(is) mascarado(s)")
                    st.caption(" · ".join(detalhes))
                    try:
                        historico.registrar(id_ if turma else None, operador,
                                            f"Assunto: {assunto_masc}\n\n{corpo_masc}",
                                            f"Assunto: {assunto_resp}\n\n{texto_resp}",
                                            fora_faq, config.MODELO_IA, ms, assunto_cls, canal="E-mail")
                    except Exception as e:  # noqa: BLE001
                        st.warning(f"A resposta foi gerada, mas não consegui salvar no histórico: {e}")

# ---------------------------- aba 4: resumo ---------------------------------
with aba_resumo:
    st.subheader("Resumo dos atendimentos")
    st.caption("Lido do histórico salvo pelo painel. As dúvidas aparecem com CPF, e-mail e telefone mascarados.")
    if st.button("🔄 Atualizar resumo"):
        st.rerun()
    try:
        df = historico.tabela()
    except Exception as e:  # noqa: BLE001
        df = None
        st.warning(f"Não consegui ler o histórico: {e}")
    if df is not None:
        if df.empty:
            st.info("Ainda não há atendimentos registrados. Gere uma resposta na aba de atendimento.")
        else:
            hoje = pd.Timestamp.now(tz="America/Sao_Paulo").strftime("%Y-%m-%d")
            c1, c2, c3, c4 = st.columns(4)
            c1.metric("Total de respostas", len(df))
            c2.metric("Hoje", int((df["data"] == hoje).sum()))
            c3.metric("Encaminhadas por e-mail", int(df["encaminhado_email"].fillna(0).sum()))
            tempo = pd.to_numeric(df["tempo_ms"], errors="coerce").mean()
            c4.metric("Tempo médio da IA", f"{tempo / 1000:.1f}s" if pd.notna(tempo) else "–")

            st.markdown("**Respostas por dia**")
            por_dia = df.dropna(subset=["data"]).groupby("data").size()
            st.bar_chart(por_dia)

            st.markdown("**Por canal**")
            st.bar_chart(df["canal"].value_counts())

            st.markdown("**Assuntos mais perguntados**")
            por_assunto = df["assunto"].value_counts()
            st.bar_chart(por_assunto, horizontal=True)

            esq, dir_ = st.columns(2)
            with esq:
                st.markdown("**Por operador**")
                por_op = df["operador"].fillna("(sem nome)").value_counts()
                st.bar_chart(por_op)
            with dir_:
                st.markdown("**Turmas mais citadas**")
                por_turma = df["id_turma"].dropna().astype(int).astype(str).value_counts().head(10)
                if por_turma.empty:
                    st.caption("Nenhuma resposta foi ligada a uma turma ainda.")
                else:
                    st.bar_chart(por_turma)

            st.markdown("**Últimas 20 dúvidas**")
            ultimas = df.sort_values("id", ascending=False).head(20)[
                ["data_hora", "canal", "assunto", "id_turma", "operador", "duvida", "encaminhado_email"]]
            ultimas = ultimas.rename(columns={
                "data_hora": "Data/Hora", "canal": "Canal", "assunto": "Assunto", "id_turma": "Turma", "operador": "Operador",
                "duvida": "Dúvida", "encaminhado_email": "Foi p/ e-mail"})
            st.dataframe(ultimas, width="stretch", hide_index=True)

# ---------------------------- aba 5: hipóteses ------------------------------
with aba_hip:
    hipoteses.mostrar(config.ARQ_CBF, config.ABA_CBF, dados.assinatura_arquivos())
