import pandas as pd, numpy as np
from ai.training import train_candidates, walk_forward
from ai.features import FEATURE_COLUMNS

def synthetic(n=500):
    rng=np.random.default_rng(42); x=pd.DataFrame({c:rng.normal(size=n) for c in FEATURE_COLUMNS})
    x['timestamp']=pd.date_range('2024-01-01',periods=n,freq='h')
    # known signal: trend + cycle ratio
    score=.8*x.trend_aligned+.3*x.cycle_atr_ratio+rng.normal(0,.5,n)
    x['label']=(score>0).astype(int); x['r_multiple']=np.where(x.label==1,1.2,-1.0)
    return x

def test_training_and_wfo(tmp_path):
    df=synthetic(700); scores,path=train_candidates(df,str(tmp_path/'models')); assert path.endswith('.joblib'); assert len(scores)==3
    w=walk_forward(df,300,100); assert len(w)>=4; assert 'expectancy_r' in w.columns
