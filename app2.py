"""dashboard/app.py — Dashboard Streamlit para visualizar la predicción
mensual del TFM Investment Clock.

Lee `s3://<bucket>/predictions/latest/prediction.json` y muestra:
  - Régimen actual y régimen siguiente predicho (con probabilidades).
  - Cartera asignada para el mes siguiente.
  - Rentabilidad de cada activo desde la fecha de predicción, vía
    Yahoo Finance (ETFs proxy de cada asset class).
  - Equity curve simulada del portfolio combinado vs benchmark SP500.

Despliegue rápido en Streamlit Community Cloud:
  1. Push este folder a un repo público de GitHub.
  2. En streamlit.io/cloud → New app → apunta al repo.
  3. Settings → Secrets, copia el contenido de .streamlit/secrets.toml
     con tus credenciales.

Despliegue local:
    streamlit run dashboard/app.py
"""

from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path

import boto3
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st
import yfinance as yf

# Auto-cargar el .env del proyecto si existe (busca en padre y abuelo del fichero).
# Útil en desarrollo local cuando reutilizas el .env del repo. En Streamlit Cloud
# este bloque no hace nada (no hay .env, se usan los Secrets de la plataforma).
try:
    from dotenv import load_dotenv  # type: ignore
    _here = Path(__file__).resolve()
    for _candidate in [_here.parent / ".env", _here.parent.parent / ".env"]:
        if _candidate.exists():
            load_dotenv(_candidate, override=False)
            break
except ImportError:
    pass


# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------
st.set_page_config(
    page_title="TFM Investment Clock — Dashboard",
    page_icon="📊",
    layout="wide",
)

# Mapeo del nombre interno del modelo → ticker de Yahoo Finance (proxy ETF
# o índice). Estos NO son los mismos instrumentos exactos que usa el modelo
# (que usa series sintéticas TR + LBMA + FRED), pero sí son proxies
# razonables para visualizar performance en streaming.
ASSET_PROXY_TICKERS = {
    "SP500":  "SPY",
    "TB3M":   "BIL",
    "TB10Y":  "IEF",
    "GOLD":   "GLD",
    "OIL":    "USO",
    "REITS":  "IYR",
    "HY":     "HYG",
    "USD":    "UUP",
    "COPPER": "CPER",
}

REGIME_COLORS = {
    "Crisis":     "#d62728",
    "Tightening": "#ff7f0e",
    "Expansion":  "#2ca02c",
    "Recesion":   "#9467bd",
}


# ---------------------------------------------------------------------------
# Helpers — S3 + Yahoo
# ---------------------------------------------------------------------------
def _get_secret(key: str, default: str | None = None) -> str | None:
    """Lee config primero de Streamlit secrets, luego de env vars."""
    try:
        if key in st.secrets:
            return st.secrets[key]
    except Exception:
        pass
    return os.environ.get(key, default)


@st.cache_data(ttl=600, show_spinner=False)
def load_prediction(bucket: str, key: str = "predictions/latest/prediction.json") -> dict:
    """Descarga y parsea el último prediction.json del bucket."""
    region = _get_secret("AWS_DEFAULT_REGION") or _get_secret("AWS_REGION") or "eu-west-1"
    s3 = boto3.client(
        "s3",
        region_name=region,
        aws_access_key_id=_get_secret("AWS_ACCESS_KEY_ID"),
        aws_secret_access_key=_get_secret("AWS_SECRET_ACCESS_KEY"),
    )
    resp = s3.get_object(Bucket=bucket, Key=key)
    return json.loads(resp["Body"].read())


@st.cache_data(ttl=3600, show_spinner=False)
def fetch_asset_prices(tickers: list[str], start_date: str, end_date: str | None = None) -> pd.DataFrame:
    """Descarga precios diarios de Yahoo Finance. Devuelve un DataFrame con
    una columna por ticker. Si algún ticker falla, lo omite con warning."""
    if end_date is None:
        end_date = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    df = yf.download(
        tickers, start=start_date, end=end_date,
        auto_adjust=True, progress=False, group_by="ticker",
        threads=True,
    )
    if isinstance(df.columns, pd.MultiIndex):
        out = pd.DataFrame()
        for t in tickers:
            if (t, "Close") in df.columns:
                out[t] = df[(t, "Close")]
        return out.dropna(how="all")
    else:
        return df[["Close"]].rename(columns={"Close": tickers[0]})


# ---------------------------------------------------------------------------
# UI helpers
# ---------------------------------------------------------------------------
def regime_card(title: str, name: str, badge_color: str = "#4a90e2") -> str:
    return f"""
    <div style="background: {badge_color}1a; border-left: 6px solid {badge_color};
                padding: 18px; border-radius: 6px; margin-bottom: 8px;">
        <div style="color: #888; font-size: 0.9em; text-transform: uppercase;
                    letter-spacing: 0.05em;">{title}</div>
        <div style="font-size: 2.2em; font-weight: 600; color: {badge_color};
                    margin-top: 4px;">{name}</div>
    </div>
    """


# ---------------------------------------------------------------------------
# Sidebar
# ---------------------------------------------------------------------------


s3_bucket = _get_secret("S3_BUCKET")

s3_prefix = _get_secret("S3_PREFIX", "")


# ---------------------------------------------------------------------------
# Carga prediction
# ---------------------------------------------------------------------------
try:
    prediction = load_prediction(s3_bucket, prediction_key)
except Exception as exc:
    st.error(f"❌ No se pudo cargar la predicción desde S3:\n\n```\n{exc}\n```")
    st.info("Verifica `S3_BUCKET`, credenciales AWS y que `predictions/latest/prediction.json` exista.")
    st.stop()


# ---------------------------------------------------------------------------
# Header
# ---------------------------------------------------------------------------
st.title("📊 TFM Investment Clock — Dashboard")

input_month = pd.Timestamp(prediction["input_month"])
generated_at = pd.Timestamp(prediction["generated_at"])
age_days = (datetime.now(timezone.utc) - generated_at.to_pydatetime()).days

freshness = "🟢 Fresca" if age_days < 35 else "🟡 Atención" if age_days < 60 else "🔴 Obsoleta"

c1, c2, c3, c4 = st.columns(4)
c1.metric("Run tag", prediction["run_tag"])
c2.metric("Mes de referencia", input_month.strftime("%Y-%m"))
c3.metric("Generada hace", f"{age_days} días")
c4.metric("Estado", freshness)

st.markdown("---")


# ---------------------------------------------------------------------------
# Régimen actual y régimen predicho
# ---------------------------------------------------------------------------
st.subheader("🌐 Régimen macroeconómico")

c1, c2 = st.columns(2)

reg_t_name = prediction["regime_t"]["name"]
reg_next_name = prediction["regime_next_pred"]["name"]
reg_t_color = REGIME_COLORS.get(reg_t_name, "#666")
reg_next_color = REGIME_COLORS.get(reg_next_name, "#666")

c1.markdown(regime_card("RÉGIMEN ACTUAL", reg_t_name, reg_t_color), unsafe_allow_html=True)
c2.markdown(regime_card("RÉGIMEN PREDICHO (próximo mes)", reg_next_name, reg_next_color), unsafe_allow_html=True)

probs = prediction["regime_next_pred"]["probabilities"]
prob_df = pd.DataFrame([
    {"Régimen": k, "Probabilidad": v} for k, v in probs.items()
]).sort_values("Probabilidad", ascending=False)

fig_probs = px.bar(
    prob_df, x="Régimen", y="Probabilidad",
    color="Régimen", color_discrete_map=REGIME_COLORS,
    text_auto=".1%",
    title="Probabilidades del régimen del próximo mes (ensemble n=7 NN21)",
)
fig_probs.update_layout(showlegend=False, height=360, yaxis_tickformat=".0%")
fig_probs.update_traces(textposition="outside")
st.plotly_chart(fig_probs, use_container_width=True)


# ---------------------------------------------------------------------------
# Cartera asignada
# ---------------------------------------------------------------------------
st.subheader("💼 Cartera asignada")

weights = prediction["portfolio_weights"]
active_weights = {k: v for k, v in weights.items() if v > 1e-6}

w_df = pd.DataFrame([
    {"Activo": k, "Peso": v} for k, v in active_weights.items()
]).sort_values("Peso", ascending=False)

c1, c2 = st.columns([2, 3])

with c1:
    fig_pie = px.pie(
        w_df, names="Activo", values="Peso", hole=0.45,
        title="Distribución de la cartera",
    )
    fig_pie.update_traces(textposition="inside", textinfo="label+percent")
    fig_pie.update_layout(height=380)
    st.plotly_chart(fig_pie, use_container_width=True)

with c2:
    st.markdown("**Pesos del portfolio:**")
    w_display = w_df.copy()
    w_display["Peso"] = w_display["Peso"].apply(lambda x: f"{x:.1%}")
    st.dataframe(w_display, hide_index=True, use_container_width=True)

    st.caption(
        f"🏦 **RF winner momentum 12m**: `{prediction['rf_winner']}` "
        f"(recibe el {prediction['metadata']['rf_weight']:.0%} fijo del portfolio)"
    )
    st.caption(
        f"⚖️ Configuración: lookup table `{prediction['metadata']['lookup_variant']}`, "
        f"ensemble n={prediction['metadata']['n_ensemble']}, "
        f"train hasta {prediction['metadata']['train_end']}"
    )

st.markdown("---")
