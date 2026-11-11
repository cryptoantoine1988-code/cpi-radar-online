import numpy as np
import pandas as pd
from engine import features, one_forecast, select_model, forecast_next
idx=pd.date_range('2018-01-01',periods=100,freq='MS')
y=pd.Series(.2+.1*np.sin(np.arange(100)/4),index=idx)
gas=pd.Series(np.cos(np.arange(100)/5),index=idx)
z=features(y,gas)
assert np.isnan(one_forecast(z,idx[3],'ridge'))
assert np.isfinite(one_forecast(z,idx[60],'ridge'))
res=forecast_next(y,gas)
assert res['month']==pd.Timestamp('2026-05-01')
assert np.isfinite(res['forecast'])
print('Tests moteur OK:',res['model'],res['forecast'])
