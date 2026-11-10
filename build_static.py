import json,pandas as pd
d=pd.read_json('dash_obs.json',dtype={'first_touch':str,'confirmed':str,'last_touch':str,'ob_candle':str})
d=d.fillna('')
import html as H,datetime as _dt
def ft(s):
    d=_dt.datetime.strptime(s[:16],'%Y-%m-%d %H:%M');h=d.hour%12 or 12
    return f"{d.strftime('%b')} {d.day}, {h}:{d.minute:02d} {'PM' if d.hour>=12 else 'AM'}"
def f2(x):return f'{float(x):.2f}'
def td(t,c=''):return f'<td class="{c}">{H.escape(str(t))}</td>' if c else f'<td>{H.escape(str(t))}</td>'
dd=d[d.run_atr>=5]
fresh=dd[dd.status=='fresh'].assign(a=lambda x:x.dist_pct.abs()).sort_values(['a','vol_rank']).head(10)
tested=dd[(dd.status=='tested')&(dd.last_touch!='')&(dd.first_touch.str[:10]!=dd.ob_candle.str[:10])].sort_values(['last_touch','confirmed','vol_rank'],ascending=[False,False,True]).head(10)
nr=''.join('<tr>'+td(x.symbol,'sym')+td(x.timeframe)+td(x.side,x.side)+td(f2(x.zone_low),'n')+td(f2(x.zone_high),'n')+td(f2(x.zone_atr),'n hn')+td(f'{x.run_atr:.1f}','n')+td(f'{x.vol_x:.2f}x','n hn')+td(x.formed,'hn')+td('yes' if x.mtf_4h else '','hn')+td(ft(x.ob_candle))+td(f2(x.last_price),'n hn')+td(('+' if x.dist_pct>0 else '')+f2(x.dist_pct)+'%','n')+'</tr>' for x in fresh.itertuples())
rr=''.join('<tr>'+td(x.symbol,'sym')+td(x.timeframe)+td(x.side,x.side)+td(f2(x.zone_low),'n')+td(f2(x.zone_high),'n')+td(f'{x.run_atr:.1f}','n')+td(f'{x.vol_x:.2f}x','n hn')+td(x.formed,'hn')+td('yes' if x.mtf_4h else '','hn')+td(ft(x.ob_candle))+td(ft(x.last_touch))+td(x.touches,'n hn')+td('yes' if x.in_zone_now else 'no','in' if x.in_zone_now else '')+'</tr>' for x in tested.itertuples())
take=''
if len(fresh):
    a_=fresh.iloc[0];take+=f"Nearest fresh thin block: {a_.symbol} {a_.timeframe} {a_.side}, {abs(a_.dist_pct):.2f}% {'above' if a_.dist_pct<0 else 'below'} price. "
if len(tested):
    r_=tested.iloc[0];take+=f"Latest retrace: {r_.symbol} {r_.timeframe} {r_.side}"+(', and it tagged the zone on the latest bar.' if r_.in_zone_now else f', touched {ft(r_.last_touch)}.')
scope=f"Top 100 stocks in SPY and QQQ by average volume. Thin order blocks (1 ATR or less) that price pushed away from by at least 5 ATR, formed in the last 7 sessions. Data as of {ft(d['asof'].iloc[0].replace(' ET',''))} ET."
keep=['symbol','vol_rank','timeframe','side','zone_low','zone_high','zone_atr','run_atr','vol_x','formed','mtf_4h','ob_candle','confirmed','status','first_touch','last_touch','touches','in_zone_now','last_price','dist_pct','asof']
data=json.dumps(d[keep].to_dict('records'),separators=(',',':'))
t=open('static_template.html').read().replace('__DATA__',data)
t=t.replace('<tbody id="near"></tbody>','<tbody id="near">'+nr+'</tbody>').replace('<tbody id="ret"></tbody>','<tbody id="ret">'+rr+'</tbody>')
t=t.replace('<p class="sub" id="scope"></p>','<p class="sub" id="scope">'+scope+'</p>').replace('<p class="take" id="take"></p>','<p class="take" id="take">'+take+'</p>')
open('public/index.html','w').write(t);open('public/data.json','w').write(data)
print(len(data),'bytes of data')
