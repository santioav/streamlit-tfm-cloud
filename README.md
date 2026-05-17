# Dashboard Streamlit — TFM Investment Clock

Visualizador en tiempo real de la última predicción mensual del pipeline.
Lee `s3://<bucket>/predictions/latest/prediction.json` y enriquece con
precios live de Yahoo Finance para mostrar la performance de la cartera
desde la fecha de predicción.

---

## Cómo gestiona las credenciales

`app.py` lee las credenciales de S3 en este orden:

1. **`st.secrets[KEY]`** — primera prioridad. En Streamlit Community Cloud
   se configuran desde la UI web (Settings → Secrets de la app).
2. **Variables de entorno** — si no hay `st.secrets`, intenta `os.environ`.
3. **Fichero `.env`** — si existe en la carpeta del proyecto, `python-dotenv`
   lo carga al arranque para que esté disponible vía variables de entorno.

**Ningún `secrets.toml` ni `.env` se sube al repo**. `.gitignore` los
excluye. Esto significa que puedes hacer el repo público sin riesgo.

---

## Despliegue en Streamlit Community Cloud (recomendado)

### Paso 1: Crear repo público

Si el repo principal del TFM es privado, crea uno separado solo con la
carpeta `dashboard/`:

```bash
mkdir tfm-dashboard
cd tfm-dashboard
# Copiar el contenido de dashboard/ aquí
git init
git add -A
git commit -m "Initial commit"
gh repo create tfm-dashboard --public --source=. --push
```

Verifica con `git status` que `secrets.toml` y `.env` NO aparecen entre
los ficheros a commitear (gracias al `.gitignore`).

### Paso 2: Crear la app en Streamlit Cloud

1. Entra en https://share.streamlit.io y haz login con GitHub.
2. Clic en **New app**.
3. Configura:
   - Repository: `<tu-usuario>/tfm-dashboard`
   - Branch: `main`
   - Main file path: `app.py`
   - Python version: `3.11` (avanzado)

### Paso 3: Configurar Secrets en la UI de Streamlit Cloud

**Aquí está la clave**: los secrets NO se ponen en el repo. Se pegan en la
UI web de Streamlit Cloud:

1. En la página de tu app → **Settings → Secrets**.
2. Pega este TOML (con tus valores reales):

```toml
S3_BUCKET             = "tfm-fred-miax"
S3_PREFIX             = ""
AWS_ACCESS_KEY_ID     = "AKIA..."
AWS_SECRET_ACCESS_KEY = "..."
AWS_DEFAULT_REGION    = "eu-west-1"
```

3. Guarda. La app reinicia automáticamente con los secrets activos.

### Paso 4: URL pública

A los 2-3 minutos tienes una URL del tipo:

```
https://<tu-app>.streamlit.app/
```

Cualquiera con el link puede acceder. La app refresca su contenido cada
vez que se recarga la página (con cache TTL de 10 min para el JSON y
60 min para los precios de Yahoo).

---

## Desarrollo local

```bash
cd dashboard
pip install -r requirements.txt

# Opción 1: usar el .env del proyecto principal (recomendado)
# El app.py detecta automáticamente C:\ruta\al\repo\.env

# Opción 2: tener un secrets.toml local
cp .streamlit/secrets.toml.example .streamlit/secrets.toml
# Editar .streamlit/secrets.toml con valores reales

streamlit run app.py
```

Abre http://localhost:8501 en el navegador.

⚠️ **NUNCA** hagas commit del `secrets.toml` o del `.env`. El `.gitignore`
los excluye, pero si los renombras o los pones en otra ruta, podrían
quedar tracked sin querer.

---

## Qué muestra

- **Cards de estado**: run tag, mes referencia, días desde generación,
  badge de frescura 🟢/🟡/🔴 (<35 / 35-60 / >60 días).
- **Régimen actual + régimen predicho**: cards de colores semánticos.
- **Bar chart de probabilidades** del régimen siguiente (ensemble n=7 NN21).
- **Pie chart de la cartera asignada** + tabla de pesos.
- **Equity curve live** del portfolio TFM vs benchmark SP500 (SPY).
- **Métricas**: retorno total, vol anualizada, Sharpe, max drawdown.
- **Tabla por activo**: rentabilidad individual desde la predicción.

## Mapping asset → ticker proxy (Yahoo Finance)

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

El backtest oficial del TFM usa los parquets sintéticos TR en S3, no estos
ETFs. Aquí solo son para visualización en streaming.

---

## Permisos AWS mínimos requeridos

Para que la app pueda leer la predicción, el usuario IAM cuya access key
metas en los secrets necesita al menos:

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Action": ["s3:GetObject", "s3:ListBucket"],
      "Resource": [
        "arn:aws:s3:::tfm-fred-miax",
        "arn:aws:s3:::tfm-fred-miax/predictions/*"
      ]
    }
  ]
}
```

**Buena práctica**: crea un usuario IAM dedicado al dashboard, con esos
permisos read-only sobre `predictions/`. Si esas claves se filtran, el
atacante solo puede leer las predicciones (no modificar tu bucket).
