import requests,json,pandas as pd,io,datetime as dt
from common import bars
h={'User-Agent':'Mozilla/5.0','Accept':'application/json'}
ndx=[r['symbol'] for r in requests.get('https://api.nasdaq.com/api/quote/list-type/nasdaq100',headers=h,timeout=30).json()['data']['data']['rows']]
t=requests.get('https://en.wikipedia.org/wiki/List_of_S%26P_500_companies',headers=h,timeout=30).text
spx=pd.read_html(io.StringIO(t))[0]['Symbol'].tolist()
u=sorted(set(ndx)|set(spx));print(len(ndx),len(spx),len(u))
start=(dt.date.today()-dt.timedelta(days=60)).isoformat()
d=bars(u,'1Day',start)
av={s:float(x['volume'].tail(30).mean()) for s,x in d.items() if len(x)>=15}
top=sorted(av,key=av.get,reverse=True)[:100]
json.dump({'built':dt.date.today().isoformat(),'symbols':top,'avg_vol':{s:av[s] for s in top}},open('universe.json','w'),indent=1)
print(top[:25],'...',len(top))
