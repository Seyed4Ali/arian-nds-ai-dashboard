from __future__ import annotations
import pandas as pd

def compare_nds_vs_ai(df: pd.DataFrame, threshold=0.6):
    base=df.r_multiple.astype(float)
    accepted=df.loc[df.ai_probability>=threshold,'r_multiple'].astype(float)
    def stats(x):
        x=x.dropna(); wins=x[x>0]; losses=x[x<0]
        return {'trades':len(x),'win_rate':float((x>0).mean()) if len(x) else 0,'expectancy_r':float(x.mean()) if len(x) else 0,'profit_factor':float(wins.sum()/abs(losses.sum())) if len(losses) and losses.sum()!=0 else float('inf')}
    return pd.DataFrame([{'system':'NDS baseline',**stats(base)},{'system':'NDS + AI',**stats(accepted)}])
