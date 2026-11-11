"""CPI Radar: retrospective, lag-only forecasts; no claim of real-time vintage validation."""
import io
import numpy as np
import pandas as pd
import requests

SERIES = ('CPIAUCSL', 'CPILFESL', 'GASREGW', 'DGS10', 'DFF')


def fetch_fred(series, timeout=12):
    """Télécharge une série FRED avec tentatives et source de secours."""
    import time

    urls = [
        f"https://fred.stlouisfed.org/graph/fredgraph.csv?id={series}",
        f"https://api.db.nomics.world/v22/series/FRED/{series}?observations=1",
    ]

    errors = []

    for url in urls:
        for attempt in range(2):
            try:
                response = requests.get(
                    url,
                    timeout=(6, timeout),
                    headers={
                        "User-Agent": "Mozilla/5.0 CPI-Radar/1.1"
                    },
                )
                response.raise_for_status()

                if "db.nomics.world" in url:
                    payload = response.json()
                    docs = payload["series"]["docs"]
                    if not docs:
                        raise ValueError("Série absente de DBnomics")

                    doc = docs[0]
                    dates = doc["period"]
                    values = doc["value"]

                    out = pd.Series(
                        pd.to_numeric(
                            pd.Series(values).replace("NA", np.nan),
                            errors="coerce",
                        ).to_numpy(),
                        index=pd.to_datetime(dates),
                        name=series,
                    )
                else:
                    df = pd.read_csv(io.StringIO(response.text))
                    df.columns = [str(c).strip() for c in df.columns]

                    date_col = (
                        "observation_date"
                        if "observation_date" in df.columns
                        else "DATE"
                    )

                    if date_col not in df.columns or series not in df.columns:
                        raise ValueError("Format CSV FRED inattendu")

                    out = pd.Series(
                        pd.to_numeric(
                            df[series].replace(".", np.nan),
                            errors="coerce",
                        ).to_numpy(),
                        index=pd.to_datetime(df[date_col]),
                        name=series,
                    )

                out = out.dropna().sort_index()

                if len(out) < 24:
                    raise ValueError("Historique insuffisant")

                return out

            except Exception as exc:
                errors.append(f"{url}: {exc}")
                if attempt == 0:
                    time.sleep(1)

    raise RuntimeError(
        f"Impossible de récupérer {series}. "
        + " | ".join(errors)
    )


def load_data():
    raw = {}
    errors = {}
    for series in SERIES:
        try: raw[series] = fetch_fred(series)
        except Exception as exc: errors[series] = str(exc)
    return raw, errors

def monthly_changes(raw):
    res = {}
    for sid in ('CPIAUCSL','CPILFESL'):
        if sid in raw:
            x = raw[sid].resample('MS').last().dropna()
            res[sid] = (x.pct_change() * 100).dropna()
    return res

def gas_monthly(raw):
    if 'GASREGW' not in raw: return None
    return raw['GASREGW'].resample('MS').mean().pct_change().mul(100).dropna()

def features(target, gas=None):
    z = pd.DataFrame({'y': target})
    for k in (1,2,3): z[f'lag{k}'] = target.shift(k)
    z['avg3'] = target.shift(1).rolling(3).mean()
    z['month_sin'] = np.sin(2*np.pi*z.index.month/12)
    z['month_cos'] = np.cos(2*np.pi*z.index.month/12)
    if gas is not None: z['gas_lag1'] = gas.shift(1).reindex(z.index)
    return z

def ridge_predict(train, row, cols, alpha=12.0):
    x = train[cols].to_numpy(float)
    y = train['y'].to_numpy(float)
    mu, sd = x.mean(0), x.std(0)
    sd[sd < 1e-9] = 1
    xz = (x-mu)/sd
    ym = y.mean()
    b = np.linalg.solve(xz.T@xz + alpha*np.eye(len(cols)), xz.T@(y-ym))
    return float(ym + ((row[cols].to_numpy(float)-mu)/sd)@b)

def one_forecast(z, t, method, min_train=24):
    cols = ['lag1','lag2','lag3','avg3','month_sin','month_cos']
    if method == 'ridge_gas': cols += ['gas_lag1']
    if method == 'persistence': return float(z.loc[t,'lag1'])
    if method == 'avg3': return float(z.loc[t,'avg3'])
    past = z.loc[z.index < t, ['y']+cols].dropna()
    row = z.loc[t,cols]
    if len(past)<min_train or row.isna().any(): return np.nan
    return ridge_predict(past, row, cols)

def evaluate(z, start, end, methods):
    dates = z.loc[(z.index>=pd.Timestamp(start)) & (z.index<=pd.Timestamp(end))].index
    rows = []
    for t in dates:
        if pd.isna(z.loc[t,'y']): continue
        for method in methods:
            p = one_forecast(z,t,method)
            if np.isfinite(p): rows.append({'month':t,'model':method,'actual':float(z.loc[t,'y']),'forecast':p,'abs_error':abs(p-z.loc[t,'y'])})
    return pd.DataFrame(rows)

def select_model(z):
    methods = ['persistence','avg3','ridge','ridge_gas'] if 'gas_lag1' in z else ['persistence','avg3','ridge']
    val = evaluate(z,'2023-01-01','2025-12-01',methods)
    if val.empty: return 'persistence',val
    scores = val.groupby('model').agg(mae=('abs_error','mean'),n=('abs_error','size'))
    eligible = scores[scores.n>=12]
    if eligible.empty: return 'persistence',val
    return str(eligible.sort_values(['mae','n'],ascending=[True,False]).index[0]),val

def forecast_next(target, gas=None):
    z = features(target,gas)
    model, val = select_model(z)
    next_t = target.index.max()+pd.offsets.MonthBegin(1)
    next_row = pd.DataFrame(index=[next_t],columns=z.columns,dtype=float)
    z = pd.concat([z,next_row])
    for k in (1,2,3): z.loc[next_t,f'lag{k}'] = target.iloc[-k]
    z.loc[next_t,'avg3'] = target.iloc[-3:].mean()
    z.loc[next_t,'month_sin'] = np.sin(2*np.pi*next_t.month/12)
    z.loc[next_t,'month_cos'] = np.cos(2*np.pi*next_t.month/12)
    if gas is not None:
        # Only last fully completed month; never use the target month's gasoline data.
        full = gas.loc[gas.index < next_t]
        if len(full): z.loc[next_t,'gas_lag1'] = full.iloc[-1]
    prediction = one_forecast(z,next_t,model)
    if not np.isfinite(prediction):
        model = 'persistence'; prediction = float(target.iloc[-1])
    test = evaluate(features(target,gas),'2026-01-01','2026-12-01',[model,'persistence','avg3','ridge','ridge_gas'] if gas is not None else [model,'persistence','avg3','ridge'])
    return {'month':next_t,'model':model,'forecast':prediction,'validation':val,'test':test}

def btc_context():
    url = 'https://api.coingecko.com/api/v3/coins/bitcoin/market_chart?vs_currency=usd&days=31&interval=daily'
    r = requests.get(url,timeout=18,headers={'User-Agent':'CPI-Radar/1.0'})
    r.raise_for_status()
    points = r.json()['prices']
    s = pd.Series({pd.to_datetime(ms,unit='ms',utc=True).normalize():float(price) for ms,price in points}).sort_index()
    if len(s)<22: raise ValueError('Historique BTC insuffisant')
    ret7 = 100*(s.iloc[-1]/s.iloc[-8]-1)
    ret30 = 100*(s.iloc[-1]/s.iloc[0]-1)
    vol = float(s.pct_change().dropna().std()*np.sqrt(365)*100)
    return {'price':float(s.iloc[-1]),'ret7':float(ret7),'ret30':float(ret30),'vol':vol,'series':s}
