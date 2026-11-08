import os,time,requests,pandas as pd
def _keys():
    k,s=os.environ.get('ALPACA_KEY'),os.environ.get('ALPACA_SECRET')
    if k and s:return k,s
    d={}
    for l in open(os.path.expanduser('~/.config/secondleg/keys.env')):
        if '=' in l:
            a,b=l.strip().split('=',1);d[a]=b
    return d['ALPACA_KEY'],d['ALPACA_SECRET']
_K,_S=_keys()
HDR={'APCA-API-KEY-ID':_K,'APCA-API-SECRET-KEY':_S}
BASE='https://data.alpaca.markets/v2/stocks/bars'
def bars(symbols,tf,start,end=None,feed='sip'):
    out={s:[] for s in symbols}
    for i in range(0,len(symbols),50):
        chunk=symbols[i:i+50];tok=None
        while True:
            p={'symbols':','.join(chunk),'timeframe':tf,'start':start,'limit':10000,'adjustment':'split','feed':feed}
            if end:p['end']=end
            if tok:p['page_token']=tok
            for att in range(8):
                r=requests.get(BASE,headers=HDR,params=p,timeout=60)
                if r.status_code==429:time.sleep(10*(att+1));continue
                break
            r.raise_for_status();j=r.json()
            for s,b in (j.get('bars') or {}).items():out[s]+=b
            tok=j.get('next_page_token')
            if not tok:break
    res={}
    for s,b in out.items():
        if not b:continue
        d=pd.DataFrame(b).rename(columns={'t':'ts','o':'open','h':'high','l':'low','c':'close','v':'volume'})
        d['ts']=pd.to_datetime(d['ts'],utc=True).dt.tz_convert('America/New_York')
        res[s]=d.set_index('ts')[['open','high','low','close','volume']]
    return res
def rth(d):
    t=d.index.hour*60+d.index.minute
    return d[(t>=9*60)&(t<16*60)&~((d.index.hour==9)&(d.index.minute<30)&(d.index.to_series().diff().dt.total_seconds().fillna(900).values<=900))]
