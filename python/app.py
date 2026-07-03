"""
SafeAir - Dashboard de Monitoramento Ambiental
===============================================
Interface Streamlit que le os dados enviados pelo Arduino (temperatura,
umidade, status) via porta serial e exibe um painel em tempo real com cara
de MVP de startup healthtech.

Execucao:
    streamlit run app.py
"""

import time

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from serial_reader import SerialReader, list_available_ports

# ---------------------------------------------------------------------------
# Paleta de cores (design tokens)
# ---------------------------------------------------------------------------
COLORS = {
    "surface": "#fcfcfb",
    "page": "#f9f9f7",
    "ink_primary": "#0b0b0b",
    "ink_secondary": "#52514e",
    "ink_muted": "#898781",
    "grid": "#e1e0d9",
    "baseline": "#c3c2b7",
    "border": "rgba(11,11,11,0.10)",
    "temp_line": "#2a78d6",   # azul (sequencial)
    "hum_line": "#1baf7a",    # aqua (categorico slot 2)
    "status": {
        "IDEAL": "#0ca30c",     # good
        "ATENCAO": "#fab219",   # warning
        "ALTA": "#ec835a",      # serious
        "CRITICO": "#d03b3b",   # critical
    },
}

STATUS_LABELS = {
    "IDEAL": "IDEAL",
    "ATENCAO": "ATENCAO",
    "ALTA": "UMIDADE ALTA",
    "CRITICO": "CRITICO",
}

STATUS_MENSAGENS = {
    "IDEAL": "Ambiente ideal para pessoas com problemas respiratorios.",
    "ATENCAO": "Umidade um pouco abaixo do ideal. Fique atento aos sintomas respiratorios.",
    "ALTA": "Umidade acima do ideal. Ventile o ambiente para melhorar o conforto respiratorio.",
    "CRITICO": "Risco respiratorio elevado! Umidade muito baixa - considere usar um umidificador.",
}

DICAS_SAUDE = {
    "CRITICO": [
        "Ar muito seco resseca as mucosas nasais e pulmonares, facilitando crises de asma e tosse.",
        "Ligue um umidificador ou deixe uma bacia com agua no ambiente.",
        "Evite ar-condicionado direto no rosto e beba agua com frequencia.",
        "Se sentir falta de ar ou chiado no peito, considere usar a bombinha de resgate.",
    ],
    "ATENCAO": [
        "Umidade um pouco abaixo do ideal pode irritar as vias respiratorias aos poucos.",
        "Fique de olho: se a umidade continuar caindo, prepare o umidificador.",
        "Evite passar longos periodos em ambientes fechados sem ventilacao.",
    ],
    "IDEAL": [
        "Faixa de umidade ideal para quem tem asma ou rinite.",
        "Mantenha a ventilacao regular do ambiente para preservar essa condicao.",
        "Nenhuma acao necessaria - continue monitorando.",
    ],
    "ALTA": [
        "Umidade alta favorece acaros, mofo e fungos - gatilhos comuns de rinite alergica e asma.",
        "Ventile o ambiente e, se possivel, use um desumidificador.",
        "Evite tapetes, cortinas pesadas e roupas de cama umidas nesse cenario.",
    ],
}

REFRESH_SECONDS = 1

# ---------------------------------------------------------------------------
# Configuracao da pagina + CSS customizado
# ---------------------------------------------------------------------------
st.set_page_config(
    page_title="SafeAir",
    page_icon="🌬",
    layout="wide",
    initial_sidebar_state="expanded",
)

st.markdown(
    f"""
    <style>
        #MainMenu {{visibility: hidden;}}
        footer {{visibility: hidden;}}

        .stApp {{
            background-color: {COLORS["page"]};
        }}

        .safeair-header {{
            display: flex;
            align-items: center;
            justify-content: space-between;
            padding: 0.5rem 0 1.25rem 0;
            border-bottom: 1px solid {COLORS["border"]};
            margin-bottom: 1.5rem;
        }}
        .safeair-title {{
            font-size: 2rem;
            font-weight: 800;
            color: {COLORS["ink_primary"]};
            letter-spacing: -0.02em;
            margin: 0;
        }}
        .safeair-tagline {{
            font-size: 0.95rem;
            color: {COLORS["ink_secondary"]};
            margin-top: 0.15rem;
        }}
        .safeair-badge {{
            font-size: 0.75rem;
            font-weight: 700;
            color: #1baf7a;
            background: rgba(27, 175, 122, 0.12);
            border-radius: 999px;
            padding: 0.3rem 0.8rem;
        }}

        .metric-card {{
            background: {COLORS["surface"]};
            border: 1px solid {COLORS["border"]};
            border-radius: 14px;
            padding: 1.1rem 1.3rem;
            box-shadow: 0 1px 3px rgba(11,11,11,0.06);
        }}
        .metric-label {{
            font-size: 0.8rem;
            font-weight: 600;
            color: {COLORS["ink_muted"]};
            text-transform: uppercase;
            letter-spacing: 0.04em;
        }}
        .metric-value {{
            font-size: 2.4rem;
            font-weight: 800;
            color: {COLORS["ink_primary"]};
            line-height: 1.15;
            margin-top: 0.2rem;
        }}
        .metric-unit {{
            font-size: 1.1rem;
            font-weight: 600;
            color: {COLORS["ink_secondary"]};
        }}

        .status-badge {{
            display: inline-block;
            font-weight: 700;
            font-size: 1.4rem;
            padding: 0.15rem 0;
            margin-top: 0.2rem;
        }}

        .risk-banner {{
            border-radius: 14px;
            padding: 1rem 1.4rem;
            color: white;
            font-weight: 600;
            font-size: 1.05rem;
            margin: 1.25rem 0;
            box-shadow: 0 2px 6px rgba(11,11,11,0.10);
        }}

        .section-title {{
            font-size: 1.05rem;
            font-weight: 700;
            color: {COLORS["ink_primary"]};
            margin: 1.6rem 0 0.6rem 0;
        }}

        .disconnected-box {{
            background: {COLORS["surface"]};
            border: 1px dashed {COLORS["baseline"]};
            border-radius: 14px;
            padding: 2.5rem;
            text-align: center;
            color: {COLORS["ink_secondary"]};
        }}

        /* --- Responsivo (celular/tablet) --------------------------------- */
        @media (max-width: 640px) {{
            .safeair-header {{
                flex-direction: column;
                align-items: flex-start;
                gap: 0.6rem;
            }}
            .safeair-title {{
                font-size: 1.5rem;
            }}
            .safeair-tagline {{
                font-size: 0.85rem;
            }}
            .metric-card {{
                padding: 0.9rem 1rem;
            }}
            .metric-value {{
                font-size: 1.8rem;
            }}
            .status-badge {{
                font-size: 1.1rem;
            }}
            .risk-banner {{
                font-size: 0.9rem;
                padding: 0.8rem 1rem;
            }}
            .section-title {{
                font-size: 0.95rem;
            }}
            .disconnected-box {{
                padding: 1.5rem;
            }}
        }}
    </style>
    """,
    unsafe_allow_html=True,
)

# ---------------------------------------------------------------------------
# Estado da sessao
# ---------------------------------------------------------------------------
if "reader" not in st.session_state:
    st.session_state.reader = None

# ---------------------------------------------------------------------------
# Sidebar - configuracao da conexao serial
# ---------------------------------------------------------------------------
with st.sidebar:
    st.markdown("### Conexao Serial")

    portas = list_available_ports()
    opcoes = portas + ["Digitar manualmente..."]

    if portas:
        porta_selecionada = st.selectbox("Porta serial", opcoes, index=0)
    else:
        porta_selecionada = "Digitar manualmente..."
        st.info("Nenhuma porta serial detectada automaticamente.")

    if porta_selecionada == "Digitar manualmente...":
        porta = st.text_input("Porta (ex: COM3)", value="COM3")
    else:
        porta = porta_selecionada

    baud_rate = st.number_input("Baud rate", value=9600, step=1200)

    col_a, col_b = st.columns(2)
    conectar = col_a.button("Conectar", use_container_width=True)
    desconectar = col_b.button("Desconectar", use_container_width=True)

    if conectar:
        if st.session_state.reader is not None:
            st.session_state.reader.stop()
        reader = SerialReader(porta, int(baud_rate))
        reader.start()
        if reader.is_connected:
            st.session_state.reader = reader
            st.success(f"Conectado em {porta}")
        else:
            st.session_state.reader = None
            st.error(f"Falha ao conectar: {reader.last_error}")

    if desconectar and st.session_state.reader is not None:
        st.session_state.reader.stop()
        st.session_state.reader = None
        st.info("Desconectado.")

    st.markdown("---")
    st.caption(
        "Selecione a porta em que o Arduino esta conectado e clique em "
        "Conectar. O dashboard atualiza automaticamente a cada segundo."
    )

# ---------------------------------------------------------------------------
# Cabecalho
# ---------------------------------------------------------------------------
st.markdown(
    f"""
    <div class="safeair-header">
        <div>
            <p class="safeair-title">SafeAir</p>
            <p class="safeair-tagline">Monitoramento ambiental inteligente para pessoas com problemas respiratorios</p>
        </div>
        <div class="safeair-badge">MVP • Fisica Experimental III</div>
    </div>
    """,
    unsafe_allow_html=True,
)

reader = st.session_state.reader

# ---------------------------------------------------------------------------
# Estado: nao conectado
# ---------------------------------------------------------------------------
if reader is None or not reader.is_connected:
    if reader is not None and not reader.is_connected:
        st.markdown(
            f"""
            <div class="risk-banner" style="background:{COLORS['status']['CRITICO']}">
                Conexao perdida com o Arduino. Verifique o cabo USB e clique em
                "Conectar" novamente na barra lateral.
            </div>
            """,
            unsafe_allow_html=True,
        )

    st.markdown(
        """
        <div class="disconnected-box">
            <h3>Aguardando conexao</h3>
            <p>Conecte o Arduino via USB, selecione a porta na barra lateral
            e clique em <b>Conectar</b> para iniciar o monitoramento.</p>
        </div>
        """,
        unsafe_allow_html=True,
    )
    st.stop()

# ---------------------------------------------------------------------------
# Estado: conectado -> dashboard ao vivo
# ---------------------------------------------------------------------------
history = reader.get_history()
latest = reader.get_latest()

if latest is None:
    st.markdown(
        """
        <div class="disconnected-box">
            <h3>Conectado - aguardando primeira leitura</h3>
            <p>Pressione o botao START no hardware para iniciar as leituras do sensor.</p>
        </div>
        """,
        unsafe_allow_html=True,
    )
    time.sleep(REFRESH_SECONDS)
    st.rerun()

status_atual = latest["status"]
cor_status = COLORS["status"][status_atual]

# --- Cards de metricas -------------------------------------------------
col1, col2, col3 = st.columns(3)

with col1:
    st.markdown(
        f"""
        <div class="metric-card">
            <div class="metric-label">Temperatura</div>
            <div class="metric-value">{latest['temperatura']:.1f}<span class="metric-unit"> °C</span></div>
        </div>
        """,
        unsafe_allow_html=True,
    )

with col2:
    st.markdown(
        f"""
        <div class="metric-card">
            <div class="metric-label">Umidade</div>
            <div class="metric-value">{latest['umidade']:.0f}<span class="metric-unit"> %</span></div>
        </div>
        """,
        unsafe_allow_html=True,
    )

with col3:
    st.markdown(
        f"""
        <div class="metric-card">
            <div class="metric-label">Status do ambiente</div>
            <div class="status-badge" style="color:{cor_status}">{STATUS_LABELS[status_atual]}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )

# --- Banner de risco respiratorio --------------------------------------
st.markdown(
    f"""
    <div class="risk-banner" style="background:{cor_status}">
        {STATUS_MENSAGENS[status_atual]}
    </div>
    """,
    unsafe_allow_html=True,
)

# --- Dataframe do historico ----------------------------------------------
df = pd.DataFrame(history)

# --- Insights: dicas de saude + resumo da sessao ------------------------
col_dicas, col_resumo = st.columns([3, 2])

with col_dicas:
    itens_html = "".join(f"<li style='margin-bottom:0.35rem;'>{d}</li>" for d in DICAS_SAUDE[status_atual])
    st.markdown(
        f"""
        <div class="metric-card" style="border-left: 4px solid {cor_status}; height:100%;">
            <div class="metric-label" style="color:{cor_status};">
                Recomendacoes para asma e rinite - {STATUS_LABELS[status_atual]}
            </div>
            <ul style="margin:0.7rem 0 0 1.1rem; padding:0; color:{COLORS['ink_secondary']}; font-size:0.92rem; line-height:1.5;">
                {itens_html}
            </ul>
        </div>
        """,
        unsafe_allow_html=True,
    )

with col_resumo:
    ordem_status = ["IDEAL", "ATENCAO", "ALTA", "CRITICO"]
    contagem = df["status"].value_counts(normalize=True) * 100
    presentes = [s for s in ordem_status if contagem.get(s, 0) > 0]

    segmentos_html = ""
    for i, s in enumerate(presentes):
        borda = f"border-right: 2px solid {COLORS['surface']};" if i < len(presentes) - 1 else ""
        segmentos_html += f'<div style="width:{contagem.get(s, 0):.1f}%; background:{COLORS["status"][s]}; {borda}"></div>'

    legendas_html = "".join(
        f"""
        <div style="display:flex; align-items:center; gap:0.4rem; margin:0.25rem 1rem 0.25rem 0;">
            <span style="width:9px; height:9px; border-radius:50%; background:{COLORS['status'][s]}; display:inline-block;"></span>
            <span style="font-size:0.82rem; color:{COLORS['ink_secondary']};">{STATUS_LABELS[s]}: <b>{contagem.get(s, 0):.0f}%</b></span>
        </div>
        """
        for s in presentes
    )

    st.markdown(
        f"""
        <div class="metric-card" style="height:100%;">
            <div class="metric-label">Tempo em cada faixa nesta sessao</div>
            <div style="display:flex; height:14px; border-radius:7px; overflow:hidden; margin:0.9rem 0 0.6rem 0;">
                {segmentos_html}
            </div>
            <div style="display:flex; flex-wrap:wrap;">
                {legendas_html}
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

# --- Graficos ao vivo ------------------------------------------------------
st.markdown('<div class="section-title">Historico de Temperatura</div>', unsafe_allow_html=True)

fig_temp = go.Figure()
fig_temp.add_trace(
    go.Scatter(
        x=df["timestamp"],
        y=df["temperatura"],
        mode="lines",
        line=dict(color=COLORS["temp_line"], width=2, shape="spline"),
        name="Temperatura (°C)",
        hovertemplate="%{y:.1f} °C<extra></extra>",
    )
)
fig_temp.update_layout(
    height=260,
    margin=dict(l=10, r=10, t=10, b=10),
    plot_bgcolor=COLORS["surface"],
    paper_bgcolor=COLORS["surface"],
    hovermode="x unified",
    xaxis=dict(showgrid=False, color=COLORS["ink_muted"], linecolor=COLORS["baseline"]),
    yaxis=dict(
        title="°C",
        showgrid=True,
        gridcolor=COLORS["grid"],
        color=COLORS["ink_muted"],
        zeroline=False,
    ),
    showlegend=False,
)
st.plotly_chart(fig_temp, use_container_width=True)

st.markdown('<div class="section-title">Historico de Umidade</div>', unsafe_allow_html=True)

fig_hum = go.Figure()

# Faixas de referencia de umidade (contexto de risco respiratorio)
faixas = [
    (0, 30, COLORS["status"]["CRITICO"]),
    (30, 40, COLORS["status"]["ATENCAO"]),
    (40, 60, COLORS["status"]["IDEAL"]),
    (60, 100, COLORS["status"]["ALTA"]),
]
for y0, y1, cor in faixas:
    fig_hum.add_hrect(y0=y0, y1=y1, fillcolor=cor, opacity=0.06, line_width=0)

fig_hum.add_trace(
    go.Scatter(
        x=df["timestamp"],
        y=df["umidade"],
        mode="lines",
        line=dict(color=COLORS["hum_line"], width=2, shape="spline"),
        name="Umidade (%)",
        hovertemplate="%{y:.0f} %<extra></extra>",
    )
)
fig_hum.update_layout(
    height=260,
    margin=dict(l=10, r=10, t=10, b=10),
    plot_bgcolor=COLORS["surface"],
    paper_bgcolor=COLORS["surface"],
    hovermode="x unified",
    xaxis=dict(showgrid=False, color=COLORS["ink_muted"], linecolor=COLORS["baseline"]),
    yaxis=dict(
        title="%",
        range=[0, 100],
        showgrid=True,
        gridcolor=COLORS["grid"],
        color=COLORS["ink_muted"],
        zeroline=False,
    ),
    showlegend=False,
)
st.plotly_chart(fig_hum, use_container_width=True)

# --- Log das ultimas leituras -------------------------------------------
col_log_titulo, col_log_download = st.columns([4, 1])
with col_log_titulo:
    st.markdown('<div class="section-title">Ultimas leituras</div>', unsafe_allow_html=True)
with col_log_download:
    df_export = df.copy()
    df_export["Hora"] = df_export["timestamp"].dt.strftime("%Y-%m-%d %H:%M:%S")
    df_export = df_export.rename(
        columns={"temperatura": "Temperatura (C)", "umidade": "Umidade (%)", "status": "Status"}
    )
    df_export = df_export[["Hora", "Temperatura (C)", "Umidade (%)", "Status"]]
    st.download_button(
        "Baixar CSV",
        data=df_export.to_csv(index=False).encode("utf-8"),
        file_name="safeair_historico.csv",
        mime="text/csv",
        use_container_width=True,
    )

df_log = df.tail(20).iloc[::-1].copy()
df_log["Hora"] = df_log["timestamp"].dt.strftime("%H:%M:%S")
df_log = df_log.rename(
    columns={"temperatura": "Temperatura (°C)", "umidade": "Umidade (%)", "status": "Status"}
)
df_log = df_log[["Hora", "Temperatura (°C)", "Umidade (%)", "Status"]]


def cor_linha(row):
    cor = COLORS["status"][row["Status"]]
    return [f"background-color: {cor}22" for _ in row]


st.dataframe(
    df_log.style.apply(cor_linha, axis=1),
    use_container_width=True,
    hide_index=True,
)

# ---------------------------------------------------------------------------
# Auto-refresh
# ---------------------------------------------------------------------------
time.sleep(REFRESH_SECONDS)
st.rerun()
