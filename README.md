# Dashboard Streamlit — TFM Investment Clock

Visualizador en tiempo real de la última predicción mensual del pipeline.
Lee `s3://<bucket>/predictions/latest/prediction.json` y enriquece con
precios live de Yahoo Finance para mostrar la performance de la cartera
desde la fecha de predicción.

## Ejecución local

```bash
cd dashboard
pip install -r requirements.txt

# Configurar credenciales:
cp .streamlit/secrets.toml.example .streamlit/secrets.toml
# Editar .streamlit/secrets.toml con tus valores

streamlit run app.py
```

Abre http://localhost:8501 en el navegador.

## Despliegue en Streamlit Community Cloud (gratis)

1. **Push del repo a GitHub** (puede ser un repo separado del de los workflows).
2. En https://share.streamlit.io → **New app**.
3. Apunta al repo y a `dashboard/app.py` como entry point.
4. En **Advanced settings → Secrets**, pega el contenido de
   `.streamlit/secrets.toml.example` rellenado con tus valores reales.
5. Deploy. URL pública del tipo `https://<tu-app>.streamlit.app/`.

## Qué muestra

- **Estado de frescura**: marca la predicción como 🟢/🟡/🔴 según los días que
  hayan pasado desde que se generó (<35 / 35-60 / >60).
- **Régimen actual + régimen predicho**: cards de colores.
- **Probabilidades del régimen siguiente**: bar chart con las 4 clases.
- **Cartera asignada**: pie chart + tabla de pesos.
- **Equity curve desde la predicción**: línea del portfolio combinado vs
  benchmark SP500 (SPY buy & hold).
- **Métricas live**: retorno total, vol anualizada, Sharpe, max drawdown.
- **Tabla por activo**: rentabilidad individual desde la fecha de predicción.

## Mapping asset → ticker Yahoo (proxy)

El modelo usa series sintéticas TR (yields convertidos a price index, LBMA
para oro, etc.). Para el dashboard usamos ETFs proxy de cada asset class:

| Asset modelo | Ticker Yahoo | Nota |
|---|---|---|
| SP500  | SPY  | S&P 500 ETF |
| TB3M   | BIL  | 1-3M T-Bill ETF (proxy) |
| TB10Y  | IEF  | 7-10Y Treasury ETF (proxy) |
| GOLD   | GLD  | SPDR Gold Shares |
| OIL    | USO  | US Oil Fund (proxy WTI) |
| REITS  | IYR  | iShares US Real Estate ETF |
| HY     | HYG  | iShares iBoxx $ HY Corp Bond |
| USD    | UUP  | Invesco DB US Dollar Bullish (proxy DXY) |
| COPPER | CPER | US Copper Index Fund |

Para el backtest oficial del TFM se usan los parquets en S3 (no estos ETFs).

## Suggested next features (no implementadas todavía)

- **Histórico de predicciones**: leer `s3://<bucket>/predictions/YYYY-MM/`
  para todas las fechas y construir un timeline de regímenes predichos.
- **Cumulative equity vs realized**: cada mes, calcular el retorno
  realizado de esa cartera y acumular en una serie histórica.
- **Sharpe rolling 12m** del backtest agregado.
- **Comparativa cross-modelo** (TFM portfolio vs NN18 vs equal-weight vs
  60/40 buy-and-hold).
- **Mini timeline de regímenes históricos** desde `regime_labels_final.parquet`.
- **Alertas** (badge rojo si el régimen predicho cambia respecto al mes
  anterior, o si la cobertura cae bajo umbral).
- **Export PDF/PNG** del dashboard para reportes mensuales offline.
