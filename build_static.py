import json,pandas as pd
d=pd.read_json('dash_obs.json',dtype={'first_touch':str,'confirmed':str,'last_touch':str,'ob_candle':str})
d=d.fillna('')
import html as H,datetime as _dt
def ft(s):
    d=_dt.datetime.strptime(s[:16],'%Y-%m-%d %H:%M');h=d.hour%12 or 12
    return f"{d.strftime('%b')} {d.day}, {h}:{d.minute:02d} {'PM' if d.hour>=12 else 'AM'}"
def f2(x):return f'{float(x):.2f}'
def spark_svg(x):
    s=list(x.spark);n=len(s)
    if n<2:return ''
    w,h,p=120,34,2;lo=min(min(s),x.zone_low);hi=max(max(s),x.zone_high);rg=(hi-lo) or 1
    X=lambda i:p+(i/(n-1))*(w-2*p);Y=lambda v:h-p-(v-lo)/rg*(h-2*p)
    pts=' '.join(f'{X(i):.1f},{Y(v):.1f}' for i,v in enumerate(s));zx=X(x.sx);zy=Y(x.zone_high);zh=max(2,Y(x.zone_low)-Y(x.zone_high))
    col='var(--ok)' if x.side=='demand' else 'var(--bad)'
    return (f'<svg viewBox="0 0 120 34" width="120" height="34" role="img" aria-label="price since the block candle with the zone shaded"><rect x="{zx:.1f}" y="{zy:.1f}" width="{w-p-zx:.1f}" height="{zh:.1f}" fill="{col}" opacity=".3"/>'
            f'<polyline points="{pts}" fill="none" stroke="var(--fg)" stroke-width="1.2" stroke-linejoin="round"/><circle cx="{X(n-1):.1f}" cy="{Y(s[-1]):.1f}" r="2" fill="var(--fg)"/></svg>')
def tv_link(s):
    s=H.escape(str(s),quote=True);return f'<a class="tv" href="https://www.tradingview.com/chart/?symbol={s}&amp;interval=15" target="_blank" rel="noopener" title="Open {s} on TradingView, 15 minute chart">{s}</a>'
def tdh(h,c=''):return f'<td class="{c}">{h}</td>'
def td(t,c=''):return f'<td class="{c}">{H.escape(str(t))}</td>' if c else f'<td>{H.escape(str(t))}</td>'
dd=d[d.run_atr>=5]
fresh=dd[dd.status=='fresh'].assign(a=lambda x:x.dist_pct.abs()).sort_values(['a','vol_rank']).head(10)
tested=dd[(dd.status=='tested')&(dd.last_touch!='')&(dd.first_touch.str[:10]!=dd.ob_candle.str[:10])].sort_values(['last_touch','confirmed','vol_rank'],ascending=[False,False,True]).head(10)
nr=''.join('<tr>'+tdh(tv_link(x.symbol),'sym')+td(x.timeframe)+td(x.group,'hn')+td(x.side,x.side)+tdh(spark_svg(x),'ch')+td(f2(x.zone_low),'n')+td(f2(x.zone_high),'n')+td(f'{x.run_atr:.1f}','n')+td(f'{x.vol_x:.2f}x','n hn')+td(x.formed,'hn')+td('yes' if x.mtf_4h else '','hn')+td(ft(x.ob_candle))+td(f2(x.last_price),'n hn')+td(('+' if x.dist_pct>0 else '')+f2(x.dist_pct)+'%','n')+'</tr>' for x in fresh.itertuples())
rr=''.join('<tr>'+tdh(tv_link(x.symbol),'sym')+td(x.timeframe)+td(x.group,'hn')+td(x.side,x.side)+tdh(spark_svg(x),'ch')+td(f2(x.zone_low),'n')+td(f2(x.zone_high),'n')+td(f'{x.run_atr:.1f}','n')+td(f'{x.vol_x:.2f}x','n hn')+td(x.formed,'hn')+td('yes' if x.mtf_4h else '','hn')+td(ft(x.ob_candle))+td(ft(x.last_touch))+td(x.touches,'n hn')+td('yes' if x.in_zone_now else 'no','in' if x.in_zone_now else '')+'</tr>' for x in tested.itertuples())
take=''
if len(fresh):
    a_=fresh.iloc[0];take+=f"Nearest fresh thin block: {a_.symbol} {a_.timeframe} {a_.side}, {abs(a_.dist_pct):.2f}% {'above' if a_.dist_pct<0 else 'below'} price. "
if len(tested):
    r_=tested.iloc[0];take+=f"Latest retrace: {r_.symbol} {r_.timeframe} {r_.side}"+(', and it tagged the zone on the latest bar.' if r_.in_zone_now else f', touched {ft(r_.last_touch)}.')
scope=f"Universe: S&P 500, Nasdaq-100 and S&P 400 stocks ranked by average volume (top 250), plus today's biggest movers and most active names. Thin order blocks (1 ATR or less) that price pushed away from by at least 5 ATR, formed in the last 7 sessions. Data as of {ft(d['asof'].iloc[0].replace(' ET',''))} ET."
keep=['symbol','vol_rank','group','spark','sx','timeframe','side','zone_low','zone_high','zone_atr','run_atr','vol_x','formed','mtf_4h','ob_candle','confirmed','status','first_touch','last_touch','touches','in_zone_now','last_price','dist_pct','asof']
data=json.dumps(d[keep].to_dict('records'),separators=(',',':'))
import os
J=json.load(open('journal.json')) if os.path.exists('journal.json') else []
def jc(x):return td(x) if x not in (None,'') else td('')
jr=''.join('<tr>'+td(e.get('date',''))+tdh(tv_link(e['symbol']) if e.get('symbol') else '','sym')+td(e.get('tf',''))+td(e.get('side'),e.get('side') or '')+td(e.get('entry',''),'n')+td(e.get('stop',''),'n')+td(e.get('exit',''),'n')+td(e.get('result',''),'n')+td(e.get('notes',''))+'</tr>' for e in sorted(J,key=lambda e:e.get('date',''),reverse=True)) or '<tr><td colspan="9">No trades logged yet.</td></tr>'
t=open('static_template.html').read().replace('__DATA__',data)
t=t.replace('<tbody id="jr"></tbody>','<tbody id="jr">'+jr+'</tbody>')
t=t.replace('<tbody id="near"></tbody>','<tbody id="near">'+nr+'</tbody>').replace('<tbody id="ret"></tbody>','<tbody id="ret">'+rr+'</tbody>')
t=t.replace('<p class="sub" id="scope"></p>','<p class="sub" id="scope">'+scope+'</p>').replace('<p class="take" id="take"></p>','<p class="take" id="take">'+take+'</p>')
open('public/index.html','w').write(t);open('public/data.json','w').write(data)
print(len(data),'bytes of data')
