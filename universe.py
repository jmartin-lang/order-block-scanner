"""Weekly universe: S&P 500 + Nasdaq-100 + S&P 400, top 250 by 30-day average volume."""
import requests,json,pandas as pd,io,datetime as dt,os,sys
from common import bars
h={'User-Agent':'Mozilla/5.0','Accept':'application/json'}
def wiki(url,col='Symbol'):
    t=requests.get(url,headers=h,timeout=40).text
    for x in pd.read_html(io.StringIO(t)):
        if col in x.columns:return x[col].astype(str).str.replace('-','.',regex=False).tolist()
    return []
src={}
try:src['spx']=wiki('https://en.wikipedia.org/wiki/List_of_S%26P_500_companies')
except Exception as e:print('spx failed',e)
try:src['mid']=wiki('https://en.wikipedia.org/wiki/List_of_S%26P_400_companies')
except Exception as e:print('mid failed',e)
try:src['ndx']=[r['symbol'] for r in requests.get('https://api.nasdaq.com/api/quote/list-type/nasdaq100',headers=h,timeout=30).json()['data']['data']['rows']]
except Exception as e:print('ndx failed',e)
print({k:len(v) for k,v in src.items()})
if not src.get('spx'):
    print('no S&P 500 list; keeping the existing universe.json');sys.exit(0)
large=set(src.get('spx',[]))|set(src.get('ndx',[]));mid=set(src.get('mid',[]))-large
allsyms=sorted(large|mid)
start=(dt.date.today()-dt.timedelta(days=60)).isoformat()
d=bars(allsyms,'1Day',start)
av={s:float(x['volume'].tail(30).mean()) for s,x in d.items() if len(x)>=15}
top=sorted(av,key=av.get,reverse=True)[:250]
json.dump({'built':dt.date.today().isoformat(),'symbols':top,'groups':{s:('Large' if s in large else 'Mid') for s in top},'avg_vol':{s:av[s] for s in top}},open('universe.json','w'),indent=1)
print(len(top),'symbols;',sum(1 for s in top if s in mid),'mid-caps; first 12:',top[:12])
