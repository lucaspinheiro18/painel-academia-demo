"""Aba 'Hipóteses': testes de hipóteses sobre as turmas (dados da planilha de turmas).

Tudo é calculado na hora a partir da planilha; se ela mudar, os resultados mudam.
Nível de significância: 5%. Quando há várias comparações, usa-se a correção de Holm.
"""
from __future__ import annotations

import itertools

import altair as alt
import numpy as np
import pandas as pd
import streamlit as st
from scipy import stats

ALFA = 0.05
MESES = ["Jan", "Fev", "Mar", "Abr", "Mai", "Jun", "Jul", "Ago", "Set", "Out", "Nov", "Dez"]
# Participação de cada região na população brasileira (IBGE, Censo 2022, valores aproximados, em %).
POP_REGIAO = {"Sudeste": 41.8, "Nordeste": 26.9, "Sul": 14.7, "Norte": 8.5, "Centro-Oeste": 8.0}
AZUL, LARANJA = "#2a78d6", "#eb6834"


# ----------------------------------------------------------------------------
# dados
# ----------------------------------------------------------------------------
@st.cache_data(show_spinner=False)
def carregar(caminho: str, aba: str, assinatura=None) -> pd.DataFrame:
    d = pd.read_excel(caminho, sheet_name=aba)
    for c in ("Início Online", "Fim Online", "Início Presencial", "Fim Presencial"):
        d[c] = pd.to_datetime(d[c], errors="coerce")
    d = d[d["ID"].notna()].copy()
    out = pd.DataFrame({
        "id": d["ID"].astype(int),
        "curso": d["Curso"].astype(str).str.strip(),
        "regiao": d["Região"].astype(str).str.strip(),
        "dur_online": (d["Fim Online"] - d["Início Online"]).dt.days,
        "dur_pres": (d["Fim Presencial"] - d["Início Presencial"]).dt.days,
        "intervalo": (d["Início Presencial"] - d["Fim Online"]).dt.days,
        "vagas": pd.to_numeric(d["Máximo de alunos"], errors="coerce"),
        "mes": d["Início Online"].dt.month,
        "adiada": d["Status"].astype(str).str.contains("adiad", case=False).astype(int),
    })
    return out


# ----------------------------------------------------------------------------
# utilitários
# ----------------------------------------------------------------------------
def n_(x, casas=2):
    return f"{x:.{casas}f}".replace(".", ",")


def p_(p):
    return "< 0,001" if p < 0.001 else n_(p, 3)


def holm(ps):
    ps = np.asarray(ps, float)
    ordem = np.argsort(ps)
    aj = np.empty_like(ps)
    corrente = 0.0
    for k, i in enumerate(ordem):
        corrente = max(corrente, (len(ps) - k) * ps[i])
        aj[i] = min(1.0, corrente)
    return aj


def _ptxt(p):
    return "p < 0,001" if p < 0.001 else f"p = {n_(p, 3)}"


def veredito(p, rejeita, mantem):
    if p < ALFA:
        st.success(f"{_ptxt(p)} (abaixo de 0,05) → **{rejeita}**")
    else:
        st.info(f"{_ptxt(p)} (acima de 0,05) → **{mantem}**")


def cabecalho(codigo, titulo, h0, h1, teste):
    st.markdown(f"### {codigo}. {titulo}")
    c1, c2 = st.columns(2)
    c1.markdown(f"**H₀:** {h0}")
    c2.markdown(f"**H₁:** {h1}")
    st.caption(f"Teste: {teste}")


def perm_chi2(grupo, y, n_sim=5000, semente=1):
    """p-valor por simulação (Monte Carlo) do qui-quadrado de independência grupo × desfecho binário."""
    cod, _ = pd.factorize(grupo)
    k = cod.max() + 1
    tam = np.bincount(cod, minlength=k).astype(float)
    total = y.sum()
    n = len(y)

    def chi(yv):
        s = np.bincount(cod, weights=yv, minlength=k)
        esp1 = tam * total / n
        esp0 = tam * (n - total) / n
        with np.errstate(divide="ignore", invalid="ignore"):
            v = np.where(esp1 > 0, (s - esp1) ** 2 / esp1, 0) + np.where(esp0 > 0, ((tam - s) - esp0) ** 2 / esp0, 0)
        return v.sum()

    obs = chi(y.astype(float))
    rng = np.random.default_rng(semente)
    sims = np.array([chi(rng.permutation(y).astype(float)) for _ in range(n_sim)])
    return obs, (1 + (sims >= obs - 1e-12).sum()) / (n_sim + 1)


# ----------------------------------------------------------------------------
# hipóteses
# ----------------------------------------------------------------------------
def h1(d):
    cabecalho("H1", "Duração da fase online por tipo de curso",
              "a duração da fase online é a mesma em todos os tipos de curso.",
              "pelo menos um tipo de curso tem duração diferente.",
              "Kruskal-Wallis (comparações em pares: Mann-Whitney com correção de Holm). Tamanho de efeito: ε².")
    base = d.dropna(subset=["dur_online"])
    cont = base["curso"].value_counts()
    grupos = [c for c in cont.index if cont[c] >= 5]
    if len(grupos) < 2:
        st.warning("Poucas turmas por curso para este teste.")
        return
    base = base[base["curso"].isin(grupos)]
    amostras = [base.loc[base["curso"] == g, "dur_online"] for g in grupos]
    H, p = stats.kruskal(*amostras)
    eps2 = H / (len(base) - 1)
    a, b, c = st.columns(3)
    a.metric("H de Kruskal-Wallis", n_(H))
    b.metric("p-valor", p_(p))
    c.metric("Efeito ε²", n_(eps2))
    esq, dir_ = st.columns([3, 2])
    with esq:
        graf = alt.Chart(base).mark_boxplot(size=22, color=AZUL, extent="min-max").encode(
            y=alt.Y("curso:N", sort=alt.EncodingSortField("dur_online", op="median"), title=None),
            x=alt.X("dur_online:Q", title="Duração da fase online (dias)"))
        st.altair_chart(graf.properties(height=220), width="stretch")
    with dir_:
        res = base.groupby("curso")["dur_online"].agg(Turmas="count", Mediana="median").sort_values("Mediana")
        st.dataframe(res, width="stretch")
    veredito(p, "rejeitamos H₀: a duração do online varia conforme o curso.",
             "não rejeitamos H₀: não há evidência de diferença entre os cursos.")
    if p < ALFA:
        pares = list(itertools.combinations(grupos, 2))
        brutos = [stats.mannwhitneyu(base.loc[base.curso == x, "dur_online"], base.loc[base.curso == y, "dur_online"]).pvalue
                  for x, y in pares]
        aj = holm(brutos)
        tab = pd.DataFrame({"Comparação": [f"{x} × {y}" for x, y in pares], "p ajustado (Holm)": [p_(v) for v in aj],
                            "Diferença significativa?": ["Sim" if v < ALFA else "Não" for v in aj]})
        with st.expander("Comparações em pares"):
            st.dataframe(tab, width="stretch", hide_index=True)


def h2(d):
    cabecalho("H2", "Relação entre as durações e o intervalo entre as fases",
              "não há correlação monotônica entre a duração do online e a do presencial.",
              "há correlação entre a duração do online e a do presencial.",
              "Correlação de Spearman (pares completos).")
    cols = {"dur_online": "Duração online", "dur_pres": "Duração presencial", "intervalo": "Intervalo", "vagas": "Capacidade"}
    base = d[list(cols)].dropna()
    par = base[["dur_online", "dur_pres"]]
    rho, p = stats.spearmanr(par["dur_online"], par["dur_pres"])
    a, b, c = st.columns(3)
    a.metric("ρ de Spearman (online × presencial)", n_(rho))
    b.metric("p-valor", p_(p))
    c.metric("Turmas com todos os dados", len(base))
    mat = base.rename(columns=cols).corr(method="spearman")
    longo = mat.reset_index().melt("index", var_name="y", value_name="rho").rename(columns={"index": "x"})
    longo["rotulo"] = longo["rho"].map(lambda v: n_(v))
    cor = alt.Chart(longo).mark_rect().encode(
        x=alt.X("x:N", title=None), y=alt.Y("y:N", title=None),
        color=alt.Color("rho:Q", scale=alt.Scale(scheme="blueorange", domain=[-1, 1]), legend=None))
    txt = alt.Chart(longo).mark_text(fontSize=14).encode(x="x:N", y="y:N", text="rotulo:N")
    st.altair_chart((cor + txt).properties(height=240), width="stretch")
    forca = "fraca" if abs(rho) < .3 else "moderada" if abs(rho) < .6 else "forte"
    veredito(p, f"rejeitamos H₀: há correlação {forca} entre as durações (ρ = {n_(rho)}).",
             "não rejeitamos H₀: não há evidência de correlação entre as durações.")


def h3(d):
    cabecalho("H3", "Distribuição das turmas presenciais pelas regiões",
              "as turmas presenciais se distribuem entre as regiões na mesma proporção da população.",
              "a distribuição das turmas difere da distribuição da população.",
              "Qui-quadrado de aderência (população: IBGE, Censo 2022, valores aproximados). Efeito: w de Cohen.")
    pres = d[d["regiao"].isin(POP_REGIAO)]
    obs = pres["regiao"].value_counts().reindex(list(POP_REGIAO), fill_value=0)
    n = int(obs.sum())
    esp = np.array(list(POP_REGIAO.values())) / sum(POP_REGIAO.values()) * n
    chi, p = stats.chisquare(obs.values, esp)
    w = np.sqrt(chi / n)
    a, b, c = st.columns(3)
    a.metric("Qui-quadrado", n_(chi))
    b.metric("p-valor", p_(p))
    c.metric("Efeito w", n_(w))
    longo = pd.DataFrame({
        "Região": list(POP_REGIAO) * 2,
        "Grupo": ["Turmas presenciais"] * 5 + ["População"] * 5,
        "%": list(obs.values / n * 100) + list(np.array(list(POP_REGIAO.values())) / sum(POP_REGIAO.values()) * 100)})
    graf = alt.Chart(longo).mark_bar().encode(
        x=alt.X("Região:N", sort=list(POP_REGIAO), title=None, axis=alt.Axis(labelAngle=0)),
        xOffset="Grupo:N", y=alt.Y("%:Q", title="% do total"),
        color=alt.Color("Grupo:N", scale=alt.Scale(domain=["Turmas presenciais", "População"], range=[AZUL, LARANJA]),
                        legend=alt.Legend(orient="top", title=None)))
    st.altair_chart(graf.properties(height=260), width="stretch")
    res = pd.DataFrame({"Região": list(POP_REGIAO), "Turmas": obs.values, "Esperadas": np.round(esp, 1),
                        "Resíduo padronizado": np.round((obs.values - esp) / np.sqrt(esp), 2)})
    with st.expander("Frequências observadas × esperadas"):
        st.dataframe(res, width="stretch", hide_index=True)
        if (esp < 5).any():
            st.caption("⚠️ Há regiões com menos de 5 turmas esperadas; leia o p-valor com cautela.")
    veredito(p, "rejeitamos H₀: a oferta de turmas não acompanha a população.",
             "não rejeitamos H₀: não há evidência de que a oferta destoe da população.")


def h4(d):
    cabecalho("H4", "Distribuição das turmas pelos meses do ano",
              "as turmas começam de forma uniforme ao longo dos meses.",
              "o início das turmas se concentra em alguns meses.",
              "Qui-quadrado de aderência à distribuição uniforme.")
    base = d.dropna(subset=["mes"])
    obs = base["mes"].astype(int).value_counts().reindex(range(1, 13), fill_value=0)
    n = int(obs.sum())
    chi, p = stats.chisquare(obs.values)
    a, b, c = st.columns(3)
    a.metric("Qui-quadrado", n_(chi))
    b.metric("p-valor", p_(p))
    c.metric("Esperado por mês", n_(n / 12, 1))
    df = pd.DataFrame({"Mês": MESES, "Turmas": obs.values})
    graf = alt.Chart(df).mark_bar(color=AZUL).encode(x=alt.X("Mês:N", sort=MESES, title=None, axis=alt.Axis(labelAngle=0)),
                                                       y=alt.Y("Turmas:Q", title="Turmas iniciadas"))
    linha = alt.Chart(pd.DataFrame({"y": [n / 12]})).mark_rule(color=LARANJA, strokeDash=[4, 3]).encode(y="y:Q")
    st.altair_chart((graf + linha).properties(height=240), width="stretch")
    st.caption("Linha tracejada: quantidade esperada por mês se a distribuição fosse uniforme.")
    veredito(p, "rejeitamos H₀: há meses com mais turmas do que outros.",
             "não rejeitamos H₀: não há evidência de concentração em alguns meses.")


def h5(d):
    cabecalho("H5", "Turmas adiadas por região e por curso",
              "a chance de uma turma ser adiada é a mesma entre os grupos.",
              "a chance de adiamento difere entre os grupos.",
              "Qui-quadrado de independência com p-valor por simulação (Monte Carlo, 5.000 sorteios). Efeito: V de Cramér.")
    n = len(d)
    st.metric("Turmas adiadas", f"{int(d['adiada'].sum())} de {n} ({n_(d['adiada'].mean() * 100, 1)}%)")
    esq, dir_ = st.columns(2)
    for col, rot, caixa in (("regiao", "Região", esq), ("curso", "Curso", dir_)):
        base = d[d[col].map(d[col].value_counts()) >= 5]
        obs, p = perm_chi2(base[col].to_numpy(), base["adiada"].to_numpy())
        v = np.sqrt(obs / len(base))
        tab = base.groupby(col)["adiada"].agg(Turmas="count", Adiadas="sum").reset_index()
        tab["% adiadas"] = tab["Adiadas"] / tab["Turmas"] * 100
        with caixa:
            st.markdown(f"**Por {rot.lower()}** · {_ptxt(p)} · V de Cramér = {n_(v)}")
            graf = alt.Chart(tab).mark_bar(color=AZUL).encode(
                y=alt.Y(f"{col}:N", sort="-x", title=None), x=alt.X("% adiadas:Q", title="% de turmas adiadas"),
                tooltip=[col, "Turmas", "Adiadas", alt.Tooltip("% adiadas:Q", format=".1f")])
            st.altair_chart(graf.properties(height=200), width="stretch")
            veredito(p, f"rejeitamos H₀: o adiamento varia por {rot.lower()}.",
                     f"não rejeitamos H₀: sem evidência de diferença por {rot.lower()}.")
    st.caption("Com poucas turmas por grupo, os percentuais são instáveis; por isso o p-valor é obtido por simulação. "
               "Grupos com menos de 5 turmas ficam fora do teste.")


def mostrar(caminho: str, aba: str, assinatura=None):
    st.subheader("Hipóteses e testes estatísticos")
    st.caption("Testes calculados na hora sobre a planilha de turmas (dados fictícios nesta versão). "
               "Nível de significância de 5%; p-valor menor que 0,05 indica evidência contra a hipótese nula (H₀).")
    try:
        d = carregar(caminho, aba, assinatura)
    except Exception as e:  # noqa: BLE001
        st.error(f"Não consegui preparar os dados para os testes: {e}")
        return
    st.markdown(f"**Base:** {len(d)} turmas · {int(d['dur_pres'].notna().sum())} com fase presencial · "
                f"{int(d['vagas'].notna().sum())} com capacidade informada.")
    for i, f in enumerate((h1, h2, h3, h4, h5)):
        if i:
            st.divider()
        f(d)
