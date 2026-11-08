"""Order block detector (causal: an OB is only known once its displacement bar CLOSES).
Demand OB = last down candle before a bullish displacement that breaks structure.
Supply OB = last up candle before a bearish displacement that breaks structure.
"""
import pandas as pd,numpy as np
P=dict(atr_n=14,disp_atr=1.5,disp_bars=3,swing_n=10,max_zone_atr=1.2,min_vol_x=0.0)

def atr(d,n):
    pc=d['close'].shift()
    tr=pd.concat([d.high-d.low,(d.high-pc).abs(),(d.low-pc).abs()],axis=1).max(axis=1)
    return tr.rolling(n).mean()

def find_obs(d,p=P):
    d=d.copy();d['atr']=atr(d,p['atr_n']);o=d.open.values;h=d.high.values;l=d.low.values;c=d.close.values;a=d.atr.values
    day=d.index.date;res=[];used=set()
    for j in range(p['swing_n']+p['atr_n'],len(d)):           # j = bar on which displacement is confirmed
        if np.isnan(a[j]):continue
        for side in ('demand','supply'):
            for k in range(1,p['disp_bars']+1):               # impulse = bars (j-k+1 .. j); OB candle sits at i=j-k
                i=j-k
                if i<p['swing_n'] or (p.get('same_session',True) and day[i]!=day[j]):continue
                if side=='demand':
                    ext=h[i+1:j+1].max();move=ext-l[i+1:j+1].min() if False else c[j]-min(l[i],l[i+1:j+1].min())
                    swing=h[i-p['swing_n']:i].max()
                    ok=c[j]>swing and move>=p['disp_atr']*a[i] and c[j]>=h[i]
                    cand=[x for x in range(i,i-4,-1) if x>=0 and c[x]<o[x]]
                else:
                    move=max(h[i],h[i+1:j+1].max())-c[j]
                    swing=l[i-p['swing_n']:i].min()
                    ok=c[j]<swing and move>=p['disp_atr']*a[i] and c[j]<=l[i]
                    cand=[x for x in range(i,i-4,-1) if x>=0 and c[x]>o[x]]
                if not ok or not cand:continue
                b=cand[0]                                       # last opposite-colour candle before impulse
                if p.get('same_session',True) and day[b]!=day[j]:continue
                if (side,b) in used:continue
                top,bot=h[b],l[b]
                if top-bot>p['max_zone_atr']*a[b]:             # too tall -> use body + the extreme wick side
                    top,bot=(max(o[b],c[b]),l[b]) if side=='demand' else (h[b],min(o[b],c[b]))
                used.add((side,b))
                res.append(dict(side=side,ob_time=d.index[b],confirm_time=d.index[j],top=top,bottom=bot,
                                impulse_atr=round(move/a[i],2),atr=a[i]))
                break
    out=pd.DataFrame(res)
    if out.empty:return out
    keep=[];pos={t:n for n,t in enumerate(d.index)}
    for r in out.sort_values('confirm_time').itertuples():      # one OB per impulse leg: drop overlapping same-side zones confirmed within 6 bars
        dup=False
        for q in keep:
            if q.side==r.side and abs(pos[q.confirm_time]-pos[r.confirm_time])<=6 and r.top>=q.bottom and r.bottom<=q.top:dup=True;break
        if not dup:keep.append(r)
    out=pd.DataFrame(keep).drop(columns='Index',errors='ignore').reset_index(drop=True)
    # status: first revisit after confirmation, and mitigation (close through far side)
    st=[];first=[];
    for r in out.itertuples():
        f=d.loc[d.index>r.confirm_time]
        touch=f[(f.low<=r.top)&(f.high>=r.bottom)]
        t0=touch.index[0] if len(touch) else pd.NaT
        brk=f[(f.close<r.bottom)] if r.side=='demand' else f[(f.close>r.top)]
        t1=brk.index[0] if len(brk) else pd.NaT
        first.append(t0);st.append('broken' if pd.notna(t1) and (pd.isna(t0) or t1<=t0) else ('tested' if pd.notna(t0) else 'fresh'))
    out['first_touch']=first;out['status']=st
    return out
