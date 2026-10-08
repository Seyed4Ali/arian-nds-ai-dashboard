from __future__ import annotations
from dataclasses import dataclass, asdict
from pathlib import Path
import json
import joblib
import numpy as np
import pandas as pd
from sklearn.base import clone
from sklearn.impute import SimpleImputer
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler
from sklearn.linear_model import LogisticRegression
from sklearn.ensemble import ExtraTreesClassifier, RandomForestClassifier
from sklearn.metrics import roc_auc_score, accuracy_score, log_loss
from sklearn.calibration import CalibratedClassifierCV
from .features import FEATURE_COLUMNS

@dataclass
class ModelScore:
    model: str
    train_rows: int
    test_rows: int
    auc: float
    accuracy: float
    logloss: float
    threshold: float
    trades: int
    win_rate: float
    expectancy_r: float


def models():
    return {
        'logreg': Pipeline([('imp',SimpleImputer(strategy='median')),('scale',StandardScaler()),('clf',LogisticRegression(max_iter=2000,class_weight='balanced'))]),
        'extra_trees': Pipeline([('imp',SimpleImputer(strategy='median')),('clf',ExtraTreesClassifier(n_estimators=400,min_samples_leaf=8,class_weight='balanced',random_state=42,n_jobs=-1))]),
        'random_forest': Pipeline([('imp',SimpleImputer(strategy='median')),('clf',RandomForestClassifier(n_estimators=300,min_samples_leaf=8,class_weight='balanced',random_state=42,n_jobs=-1))]),
    }


def _metrics(model, X, y, r, threshold=0.6):
    p=model.predict_proba(X)[:,1]
    pred=(p>=threshold).astype(int)
    auc=roc_auc_score(y,p) if len(np.unique(y))>1 else float('nan')
    acc=accuracy_score(y,pred)
    ll=log_loss(y,np.clip(p,1e-6,1-1e-6),labels=[0,1]) if len(np.unique(y))>1 else float('nan')
    taken=r[p>=threshold]
    wr=float((taken>0).mean()) if len(taken) else 0.0
    ex=float(taken.mean()) if len(taken) else 0.0
    return auc,acc,ll,len(taken),wr,ex


def chronological_split(df, test_fraction=0.2):
    n=len(df); cut=max(1,int(n*(1-test_fraction)))
    return df.iloc[:cut].copy(), df.iloc[cut:].copy()


def train_candidates(df: pd.DataFrame, out_dir: str, threshold=0.6):
    Path(out_dir).mkdir(parents=True,exist_ok=True)
    df=df.sort_values('timestamp').reset_index(drop=True)
    X=df[FEATURE_COLUMNS].astype(float); y=df['label'].astype(int); r=df['r_multiple'].astype(float)
    train,test=chronological_split(df)
    scores=[]
    for name, model in models().items():
        model.fit(train[FEATURE_COLUMNS],train.label)
        vals=_metrics(model,test[FEATURE_COLUMNS],test.label,test.r_multiple,threshold)
        score=ModelScore(name,len(train),len(test),*vals[:3],threshold,*vals[3:])
        scores.append(score)
    # Select by out-of-sample expectancy first, then AUC; require at least 10 test trades where possible.
    best=max(scores,key=lambda s:(s.expectancy_r if s.trades>=10 else -1e9,s.auc if np.isfinite(s.auc) else -1e9))
    final=models()[best.model]
    final.fit(X,y)
    model_path=Path(out_dir)/f'{best.model}.joblib'; joblib.dump(final,model_path)
    meta={'selected':asdict(best),'feature_columns':FEATURE_COLUMNS,'threshold':threshold,'rows':len(df)}
    (Path(out_dir)/'registry.json').write_text(json.dumps(meta,indent=2),encoding='utf-8')
    return scores, str(model_path)


def walk_forward(df: pd.DataFrame, train_bars=1000, test_bars=250, step=None, threshold=0.6):
    if step is None: step=test_bars
    df=df.sort_values('timestamp').reset_index(drop=True)
    results=[]
    start=0
    while start+train_bars+test_bars<=len(df):
        tr=df.iloc[start:start+train_bars]; te=df.iloc[start+train_bars:start+train_bars+test_bars]
        best_model=None; best_name=None; best_ex=-1e18
        for name,m in models().items():
            m.fit(tr[FEATURE_COLUMNS],tr.label)
            p=m.predict_proba(te[FEATURE_COLUMNS])[:,1]
            taken=te.loc[p>=threshold,'r_multiple']
            ex=float(taken.mean()) if len(taken) else 0.0
            if ex>best_ex: best_ex=ex; best_model=m; best_name=name
        p=best_model.predict_proba(te[FEATURE_COLUMNS])[:,1]
        taken=te.loc[p>=threshold,'r_multiple']
        results.append({'train_start':str(tr.timestamp.iloc[0]),'train_end':str(tr.timestamp.iloc[-1]),'test_start':str(te.timestamp.iloc[0]),'test_end':str(te.timestamp.iloc[-1]),'model':best_name,'test_signals':len(te),'accepted':len(taken),'accept_rate':len(taken)/len(te),'expectancy_r':float(taken.mean()) if len(taken) else 0.0,'win_rate':float((taken>0).mean()) if len(taken) else 0.0})
        start += step
    return pd.DataFrame(results)
