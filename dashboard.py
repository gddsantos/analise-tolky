import json
import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from pathlib import Path

# ── Config ───────────────────────────────────────────────────────────
st.set_page_config(
    page_title="Análise de Automações — Uniube · Tolky",
    page_icon="🤖",
    layout="wide",
)

BASE_DIR   = Path(__file__).parent
ANALISES   = BASE_DIR / "analises"

AUTOMACOES = {
    "SAE": {
        "aval":     ANALISES / "01_sae_avaliacoes.csv",
        "metadata": ANALISES / "01_sae_metadata.json",
        "descricao": "Serviço de Apoio ao Estudante — deve acionar apenas para alunos ativos.",
    },
}

# ── Carregamento ─────────────────────────────────────────────────────
@st.cache_data(show_spinner="Carregando dados...")
def load_automacao(nome):
    cfg  = AUTOMACOES[nome]
    aval = pd.read_csv(cfg["aval"])
    meta = json.loads(cfg["metadata"].read_text(encoding="utf-8"))

    # Juntar datas
    aval["date"] = aval["conversation_id"].map(meta["conv_dates"])
    aval["date"] = pd.to_datetime(aval["date"], errors="coerce")

    # Excluir dias com dados incompletos
    EXCLUIR = {"2026-04-07"}
    excluidos = {c for c, d in meta["conv_dates"].items() if d in EXCLUIR}
    aval = aval[~aval["conversation_id"].isin(excluidos)].copy()
    n_excl = len(excluidos)
    meta["funnel"] = dict(meta["funnel"])
    meta["funnel"]["total"]     = max(0, meta["funnel"]["total"] - n_excl)
    meta["funnel"]["confirmed"] = int((aval["verdict"].notna()).sum())

    funnel = meta["funnel"]
    funnel["correto"] = int((aval["verdict"] == "CORRETO").sum())
    funnel["errado"]  = int((aval["verdict"] == "ERRADO").sum())

    daily = meta.get("daily_funnel", {})
    # excluir dias incompletos
    daily = {d: v for d, v in daily.items() if d not in {"2026-04-07"}}

    return aval, funnel, daily

# ── Header ───────────────────────────────────────────────────────────
st.title("🤖 Análise de Automações — Uniube · Tolky")
st.caption("Base: março/2026 · Uniube + Uberlândia")
st.divider()

# ── Seletor de automação ─────────────────────────────────────────────
aut_nome = st.selectbox("Automação", list(AUTOMACOES.keys()))
cfg      = AUTOMACOES[aut_nome]
aval_df, funnel, meta_daily = load_automacao(aut_nome)

st.subheader(f"Automação: {aut_nome}")
st.caption(cfg["descricao"])

# ── Cards do funil ───────────────────────────────────────────────────
pct = lambda n, d: f"{n/d*100:.1f}%" if d else "—"

c1, c2, c3, c4, c5 = st.columns(5)
c1.metric("Total conversas",
          f"{funnel['total']:,}".replace(",", "."))
c2.metric("1. Acionado",
          f"{funnel['confirmed']:,}".replace(",", "."),
          f"{pct(funnel['confirmed'], funnel['total'])} do total")
c3.metric("2. Injetado no contexto",
          f"{funnel['injected']:,}".replace(",", "."),
          f"{pct(funnel['injected'], funnel['confirmed'])} do acionado")
c4.metric("3. Enviado ao usuário",
          f"{funnel['replied']:,}".replace(",", "."),
          f"{pct(funnel['replied'], funnel['injected'])} do injetado")
c5.metric("4. Acionamentos corretos",
          f"{funnel['correto']:,}".replace(",", "."),
          f"{pct(funnel['correto'], funnel['confirmed'])} do acionado")

st.divider()

# ── Linha do tempo + Donut ───────────────────────────────────────────
col_linha, col_donut = st.columns([3, 1])

with col_linha:
    st.subheader("Volumes dia a dia")

    df_vol = aval_df.dropna(subset=["date"]).copy()
    df_vol["dia"] = df_vol["date"].dt.strftime("%Y-%m-%d")
    correto_d = df_vol[df_vol["verdict"]=="CORRETO"].groupby("dia").size()

    daily_funnel = pd.DataFrame.from_dict(meta_daily, orient="index").sort_index()
    daily_funnel = daily_funnel[~daily_funnel.index.isin(["2026-04-07"])]
    daily_funnel["correto"] = correto_d
    daily_funnel = daily_funnel.fillna(0).astype(int).reset_index().rename(columns={"index":"dia"})

    SERIES = [
        ("total",     "Total conversas",       "#94A3B8"),
        ("confirmed", "Acionado",              "#3B82F6"),
        ("injected",  "Injetado no contexto",  "#8B5CF6"),
        ("replied",   "Enviado ao usuário",    "#F59E0B"),
        ("correto",   "Acionamentos corretos", "#22C55E"),
    ]
    fig_vol = go.Figure()
    for col, label, color in SERIES:
        fig_vol.add_trace(go.Scatter(
            x=daily_funnel["dia"], y=daily_funnel[col],
            mode="lines+markers+text", name=label,
            text=daily_funnel[col], textposition="top center",
            textfont=dict(size=9),
            line=dict(color=color, width=2),
            hovertemplate=f"%{{x}}<br>{label}: %{{y}}<extra></extra>",
        ))
    fig_vol.update_layout(
        legend=dict(orientation="h", yanchor="bottom", y=1.02),
        margin=dict(t=10, b=10, l=0, r=0),
        height=340,
        plot_bgcolor="white",
        xaxis_title="", yaxis_title="conversas",
    )
    st.plotly_chart(fig_vol, use_container_width=True)

    st.subheader("Taxa dia a dia")

    daily = (
        aval_df.dropna(subset=["date"])
        .groupby(["date", "verdict"])
        .size()
        .reset_index(name="n")
        .pivot_table(index="date", columns="verdict", values="n", fill_value=0)
        .reset_index()
    )
    for col in ("CORRETO", "ERRADO"):
        if col not in daily.columns:
            daily[col] = 0

    daily["total"]   = daily["CORRETO"] + daily["ERRADO"]
    daily["fp_pct"]  = (daily["ERRADO"]  / daily["total"] * 100).round(1)
    daily["ok_pct"]  = (daily["CORRETO"] / daily["total"] * 100).round(1)

    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=daily["date"], y=daily["fp_pct"],
        mode="lines+markers", name="Falso positivo %",
        line=dict(color="#EF4444", width=2),
        fill="tozeroy", fillcolor="rgba(239,68,68,0.08)",
        hovertemplate="%{x|%d/%m}<br>Falso positivo: %{y:.1f}%<extra></extra>",
    ))
    fig.add_trace(go.Scatter(
        x=daily["date"], y=daily["ok_pct"],
        mode="lines+markers", name="Correto %",
        line=dict(color="#22C55E", width=2),
        hovertemplate="%{x|%d/%m}<br>Correto: %{y:.1f}%<extra></extra>",
    ))
    fig.add_hline(y=50, line_dash="dot", line_color="#94A3B8",
                  annotation_text="50%", annotation_position="right")
    fig.update_layout(
        yaxis=dict(range=[0, 105], ticksuffix="%", title=""),
        xaxis_title="",
        legend=dict(orientation="h", yanchor="bottom", y=1.02),
        margin=dict(t=10, b=10, l=0, r=0),
        height=300,
        plot_bgcolor="white",
    )
    st.plotly_chart(fig, use_container_width=True)

with col_donut:
    st.subheader("Distribuição")
    fig_d = go.Figure(go.Pie(
        labels=["✅ Correto", "❌ Falso positivo"],
        values=[funnel["correto"], funnel["errado"]],
        hole=0.6,
        marker_colors=["#22C55E", "#EF4444"],
        textinfo="percent",
        hovertemplate="%{label}: %{value:,} conversas<extra></extra>",
    ))
    fig_d.update_layout(
        showlegend=True,
        legend=dict(orientation="v", yanchor="middle", y=0.5),
        margin=dict(t=10, b=10, l=0, r=0),
        height=300,
    )
    st.plotly_chart(fig_d, use_container_width=True)

st.divider()

# ── Motivos ──────────────────────────────────────────────────────────
col_err, col_ok = st.columns(2)

def motivo_chart(df, verdict, color, titulo):
    subset = (
        df[df["verdict"] == verdict]
        .groupby("motivo").size()
        .reset_index(name="n")
        .sort_values("n", ascending=True)
        .tail(10)
    )
    fig = px.bar(
        subset, x="n", y="motivo", orientation="h",
        color_discrete_sequence=[color],
        labels={"n": "Conversas", "motivo": ""},
    )
    fig.update_layout(margin=dict(t=10, b=10, l=0, r=0), height=300)
    return fig

with col_err:
    st.subheader("Top motivos — Falso positivo")
    st.plotly_chart(motivo_chart(aval_df, "ERRADO", "#EF4444", ""), use_container_width=True)

with col_ok:
    st.subheader("Top motivos — Correto")
    st.plotly_chart(motivo_chart(aval_df, "CORRETO", "#22C55E", ""), use_container_width=True)

st.divider()

# ── Drill-down ───────────────────────────────────────────────────────
st.subheader("Conversas — drill-down")

f1, f2 = st.columns(2)
filtro_v = f1.selectbox("Veredicto", ["Todos", "✅ Correto", "❌ Falso positivo"])
filtro_m = f2.selectbox(
    "Motivo",
    ["Todos"] + sorted(aval_df["motivo"].dropna().unique().tolist()),
)

tbl = aval_df.copy()
if filtro_v == "✅ Correto":
    tbl = tbl[tbl["verdict"] == "CORRETO"]
elif filtro_v == "❌ Falso positivo":
    tbl = tbl[tbl["verdict"] == "ERRADO"]
if filtro_m != "Todos":
    tbl = tbl[tbl["motivo"] == filtro_m]

tbl = tbl[["date", "verdict", "motivo", "user_msgs", "conversation_id"]].copy()
tbl["verdict"] = tbl["verdict"].map({"CORRETO": "✅ Correto", "ERRADO": "❌ Falso positivo"})
tbl.columns = ["Data", "Veredicto", "Motivo", "Mensagens do usuário", "ID conversa"]
tbl = tbl.sort_values("Data", ascending=False)

st.dataframe(tbl, use_container_width=True, height=400)
st.caption(f"{len(tbl):,} conversas exibidas".replace(",", "."))
