"""Thin order blocks with a big push out of them (the VICI / BX pattern). Writes dash_obs.json (+ csv)."""
import json,requests,pandas as pd,numpy as np
from common import bars,rth,HDR
from ob import find_obs,P
uni=json.load(open('universe.json'));syms=list(uni['symbols']);groups=dict(uni.get('groups',{}));rank={s:i+1 for i,s in enumerate(syms)}
now=pd.Timestamp.now(tz='America/New_York');end=(pd.Timestamp.now(tz='UTC')-pd.Timedelta(minutes=16)).strftime('%Y-%m-%dT%H:%M:%SZ')
start=(now-pd.Timedelta(days=24)).strftime('%Y-%m-%d')
MAXZ=1.0;MINRUN=3.0;SESS=7;SPARK_N=48
P2={**P,'same_session':False}
BAD_WORDS=('ETF','ETN','Fund','Trust','Index','Bull','Bear','Warrant','Rights','Units','Preferred','Notes','Ultra','Leveraged','Inverse','Daily ')
def movers_extras(max_n=40):
    """Today's biggest movers + most active stocks that are not already in the universe (equities only, price>=5, avg vol>=1M)."""
    try:
        cand=[]
        m=requests.get('https://data.alpaca.markets/v1beta1/screener/stocks/movers?top=20',headers=HDR,timeout=30).json()
        cand+=[x['symbol'] for x in m.get('gainers',[])+m.get('losers',[])]
        a=requests.get('https://data.alpaca.markets/v1beta1/screener/stocks/most-actives?by=volume&top=40',headers=HDR,timeout=30).json()
        cand+=[x['symbol'] for x in a.get('most_actives',[])]
        cand=[s for s in dict.fromkeys(cand) if s not in rank and s.isalpha() and len(s)<=5]
        if not cand:return []
        assets=requests.get('https://paper-api.alpaca.markets/v2/assets?status=active&asset_class=us_equity',headers=HDR,timeout=60).json()
        ok={x['symbol'] for x in assets if x.get('exchange') in ('NASDAQ','NYSE','AMEX') and x.get('tradable') and not any(w in (x.get('name') or '') for w in BAD_WORDS)}
        cand=[s for s in cand if s in ok]
        if not cand:return []
        d=bars(cand,'1Day',(now-pd.Timedelta(days=45)).strftime('%Y-%m-%d'),end=end,feed='sip')
        keep=[s for s,x in d.items() if len(x)>=15 and x['volume'].tail(30).mean()>=1e6 and x['close'].iloc[-1]>=5]
        return keep[:max_n]
    except Exception as e:
        print('movers step skipped:',e);return []
extras=movers_extras()
for s in extras:groups[s]='Mover'
allsyms=syms+extras
def to4h(d15):
    x=d15.copy();x['key']=[(t.date(),0 if (t.hour*60+t.minute)<13*60+30 else 1) for t in x.index]
    g=x.groupby('key').agg(open=('open','first'),high=('high','max'),low=('low','min'),close=('close','last'),volume=('volume','sum'),ts=('open',lambda s:s.index[0]))
    g=g.set_index('ts');g.index.name=None;return g
def break_times(o,d):
    pos={t:n for n,t in enumerate(d.index)};c=d.close.values;bt=[]
    for r in o.itertuples():
        j=pos[r.confirm_time];seg=c[j+1:];k=np.where(seg<r.bottom)[0] if r.side=='demand' else np.where(seg>r.top)[0]
        bt.append(d.index[j+1+k[0]] if len(k) else pd.NaT)
    o=o.copy();o['break_time']=pd.to_datetime(pd.Series(bt,index=o.index,dtype='object'),utc=True).dt.tz_convert('America/New_York');return o
dur={'15Min':pd.Timedelta(minutes=15),'1Hour':pd.Timedelta(hours=1)}
data={tf:{s:rth(x[x.index+dur[tf]<=now]) for s,x in bars(allsyms,tf,start,end=end,feed='sip').items()} for tf in dur}
h4={}
for s,d in data['15Min'].items():
    if len(d)>=200:
        d4=to4h(d);o=find_obs(d4,P2)
        if not o.empty:h4[s]=break_times(o,d4)
def aligned(s,side,top,bot,t,a):
    o=h4.get(s)
    if o is None:return 0
    m=o[(o.side==side)&(o.confirm_time<=t)&(o.confirm_time>=t-pd.Timedelta(days=10))&((o.break_time.isna())|(o.break_time>t))]
    return int(((m.top+0.25*m.atr>=bot)&(m.bottom-0.25*m.atr<=top)).any()) if len(m) else 0
def spark(d,bb):
    s0=max(0,bb-8);c=d.close.values[s0:];n=len(c)
    idx=np.unique(np.linspace(0,n-1,min(n,SPARK_N)).round().astype(int))
    sx=int(np.argmin(np.abs(idx-(bb-s0))))
    return [round(float(c[i]),2) for i in idx],sx
rows=[]
for tf in dur:
    for s,d in data[tf].items():
        if len(d)<60:continue
        o=find_obs(d,P2)
        if o.empty:continue
        days=sorted(set(d.index.date))[-SESS:];last=d.close.iloc[-1];posm={t:n for n,t in enumerate(d.index)};vv=d.volume.values;vmm=d.volume.rolling(20).mean().values
        for r in o.itertuples():
            if r.confirm_time.date() not in days or r.status=='broken':continue
            z=(r.top-r.bottom)/r.atr
            if z>MAXZ:continue
            f=d.loc[d.index>r.confirm_time];tch=f[(f.low<=r.top)&(f.high>=r.bottom)]
            first=tch.index[0] if len(tch) else None
            seg=f.loc[f.index<first] if first is not None else f
            if not len(seg):continue
            run=((seg.high.max()-r.top) if r.side=='demand' else (r.bottom-seg.low.min()))/r.atr
            if run<MINRUN:continue
            bb=posm[r.ob_time];jj=posm[r.confirm_time];volx=float(vv[bb+1:jj+1].sum()/(vmm[bb]*(jj-bb))) if vmm[bb]>0 else 1.0
            inside=r.bottom<=last<=r.top
            dist=0.0 if inside else (last-r.top)/last*100 if last>r.top else (last-r.bottom)/last*100
            sp,sx=spark(d,bb)
            rows.append(dict(symbol=s,vol_rank=rank.get(s,999),group=groups.get(s,'Large'),timeframe={'15Min':'15m','1Hour':'1H'}[tf],side=r.side,
                zone_low=round(r.bottom,2),zone_high=round(r.top,2),zone_atr=round(z,2),run_atr=round(float(run),1),
                ob_candle=f'{r.ob_time:%Y-%m-%d %H:%M}',confirmed=f'{r.confirm_time:%Y-%m-%d %H:%M}',status=r.status,
                first_touch=f'{first:%Y-%m-%d %H:%M}' if first is not None else '',last_touch=f'{tch.index[-1]:%Y-%m-%d %H:%M}' if len(tch) else '',
                touches=int((tch.index.to_series().diff().dt.total_seconds().fillna(1e9)>dur[tf].total_seconds()).sum()) if len(tch) else 0,
                in_zone_now=bool(len(tch) and tch.index[-1]==d.index[-1]),last_price=round(last,2),dist_pct=round(dist,2),
                vol_x=round(volx,2),formed='session' if r.ob_time.date()==r.confirm_time.date() else 'gap',
                mtf_4h=aligned(s,r.side,r.top,r.bottom,r.confirm_time,r.atr),spark=sp,sx=sx))
df=pd.DataFrame(rows).sort_values(['confirmed','vol_rank'],ascending=[False,True])
df['id']=df.symbol+'|'+df.timeframe+'|'+df.side+'|'+df.ob_candle;df['asof']=now.strftime('%Y-%m-%d %H:%M ET')
df.drop(columns=['spark','sx']).to_csv('dash_obs.csv',index=False);df.to_json('dash_obs.json',orient='records')
print(len(df),df.status.value_counts().to_dict(),'groups',df.group.value_counts().to_dict(),'run>=5:',int((df.run_atr>=5).sum()),'extras:',extras[:8],'asof',df['asof'].iloc[0])
