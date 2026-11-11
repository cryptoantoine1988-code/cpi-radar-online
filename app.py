import datetime as dt
import pandas as pd
import streamlit as st
from engine import load_data, monthly_changes, gas_monthly, forecast_next, btc_context

st.set_page_config(page_title='CPI Radar | Macro & Crypto',page_icon='📡',layout='wide')
st.title('📡 CPI Radar')
st.caption('Prévisions d’inflation américaine et contexte crypto — recherche, pas un signal de trading.')

@st.cache_data(ttl=21600,show_spinner=False)
def data(): return load_data()
@st.cache_data(ttl=3600,show_spinner=False)
def crypto(): return btc_context()

with st.spinner('Récupération des dernières données publiques…'):
    raw, errors = data()
changes = monthly_changes(raw)
if not changes:
    st.error('Les séries officielles FRED sont indisponibles. Réessayez plus tard. Aucune prévision n’est inventée.')
    st.code(str(errors))
    st.stop()

gas = gas_monthly(raw)
results = {}
cols = st.columns(2)
for col, (sid,label) in zip(cols,[('CPIAUCSL','CPI global'),('CPILFESL','Core CPI')]):
    with col:
        st.subheader(label)
        if sid not in changes or len(changes[sid])<28:
            st.warning('Historique insuffisant pour cette série.'); continue
        target = changes[sid]
        result = forecast_next(target,gas)
        results[sid]=result
        st.metric(f'Prévision {result["month"]:%Y-%m} · variation mensuelle',f'{result["forecast"]:+.3f} %')
        st.caption(f'Modèle automatique : {result["model"]} · dernier CPI observé : {target.index[-1]:%Y-%m} · prévision du mois suivant.')
        st.line_chart(target.tail(30),height=230)
        val=result['validation']
        if not val.empty:
            s=val.groupby('model').abs_error.agg(['mean','count']).sort_values('mean')
            st.caption('Validation chronologique rétrospective 2023–2025 (MAE en points de %).')
            st.dataframe(s.rename(columns={'mean':'MAE (pt)','count':'Mois'}).style.format({'MAE (pt)':'{:.3f}'}),use_container_width=True)
        test=result['test']
        if not test.empty:
            st.caption('Backtest 2026 rétrospectif (sous réserve de disponibilité des observations).')
            t=test.groupby('model').abs_error.agg(['mean','count']).sort_values('mean')
            st.dataframe(t.rename(columns={'mean':'MAE (pt)','count':'Mois'}).style.format({'MAE (pt)':'{:.3f}'}),use_container_width=True)
            st.download_button(f'Exporter backtest {label}',test.to_csv(index=False).encode(),file_name=f'backtest_{sid}.csv',mime='text/csv')

st.divider()
st.subheader('₿ Contexte de marché crypto')
try:
    btc=crypto()
    a,b,c,d=st.columns(4)
    a.metric('Bitcoin · USD',f'${btc["price"]:,.0f}')
    b.metric('Variation 7 jours',f'{btc["ret7"]:+.1f} %')
    c.metric('Variation 30 jours',f'{btc["ret30"]:+.1f} %')
    d.metric('Volatilité annualisée indicative',f'{btc["vol"]:.0f} %')
    st.line_chart(btc['series'],height=240)
    if btc['ret7']>2 and btc['ret30']>0: context='Tendance récente BTC positive'
    elif btc['ret7']< -2 and btc['ret30']<0: context='Tendance récente BTC négative'
    else: context='Tendance BTC mitigée'
    st.info(f'**{context}.** Lecture descriptive des prix, pas une prédiction de retournement. Le lien causal CPI → Fed → crypto n’est pas encore calibré ni validé.')
except Exception as exc:
    st.warning(f'Données crypto momentanément indisponibles : {exc}')

st.subheader('Fed et consensus')
for sid, label in [('DGS10','Rendement US Treasury 10 ans'),('DFF','Taux effectif des fonds fédéraux')]:
    if sid in raw and len(raw[sid]):
        s=raw[sid]
        st.write(f'**{label} :** {s.iloc[-1]:.2f} % (observation {s.index[-1]:%d/%m/%Y})')
st.warning('**Consensus CPI non connecté.** Sans consensus daté avant publication, impossible de calculer une surprise attendue crédible. Aucun signal macro-crypto directionnel n’est affiché.')

st.divider()
st.caption('Méthode : CPI mensuel calculé à partir des indices désaisonnalisés FRED. Modèles simples et Ridge entraînés uniquement sur les mois antérieurs à chaque prévision. Sélection sur validation 2023–2025. Essence : variation du dernier mois connu, jamais celle du mois prédit. Backtest rétrospectif : les séries FRED peuvent être révisées, il ne constitue pas un vrai backtest sur vintages historiques. Les prévisions sont recalculées après chaque actualisation ; un historique immuable de snapshots prépublication reste à ajouter.')
if errors:
    with st.expander('Sources indisponibles'):
        for k,v in errors.items(): st.write(k,':',v)
st.caption(f'Consultation : {dt.datetime.now(dt.timezone.utc):%Y-%m-%d %H:%M} UTC · données mises en cache 6 h (macro) / 1 h (crypto).')
