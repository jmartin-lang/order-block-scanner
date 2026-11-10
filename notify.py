"""Delivery channels + morning digest.
python notify.py digest [--force] [--to a@b.com,c@d.com] [--n 10] [--test]
Channels are used only when configured (env vars / repo secrets):
  DIGEST_EMAILS        comma list of recipients; needs SMTP_USER + SMTP_PASSWORD (or --via mac on a Mac with Mail set up)
  NTFY_DIGEST_TOPIC    private ntfy topic for a phone push of the same digest
  DISCORD_WEBHOOK_URL  Discord channel webhook
  TELEGRAM_BOT_TOKEN + TELEGRAM_CHAT_ID  Telegram bot
"""
import os,sys,json,argparse,requests,pandas as pd,datetime as dt
SITE=os.environ.get('SITE_URL','https://jmartin-lang.github.io/order-block-scanner/')
def load(path='dash_obs.json'):
    return pd.read_json(path,dtype={'first_touch':str,'confirmed':str,'last_touch':str,'ob_candle':str}).fillna('')
def ft(s):
    d=dt.datetime.strptime(s[:16],'%Y-%m-%d %H:%M');h=d.hour%12 or 12
    return f"{d.strftime('%b')} {d.day}, {h}:{d.minute:02d} {'PM' if d.hour>=12 else 'AM'}"
def pick(df,n=10,min_push=5.0):
    f=df[(df.status=='fresh')&(df.run_atr>=min_push)].copy()
    f['abs_dist']=f.dist_pct.abs()
    f=f.sort_values(['abs_dist','vol_rank'])
    # one line per symbol+side: keep the nearest block of each
    f=f.drop_duplicates(['symbol','side'])
    return f.head(n)
def line(i,r):
    side='demand' if r.side=='demand' else 'supply'
    rel='above' if r.dist_pct<0 else 'below'
    flags=[]
    if r.vol_x<=0.92:flags.append('quiet push')
    if r.formed=='session':flags.append('formed in session')
    if r.mtf_4h:flags.append('4H overlap')
    stop=r.zone_low if side=='supply' else r.zone_high
    return (f"{i}. {r.symbol} {r.timeframe} {side.upper()}  zone {r.zone_low:.2f}-{r.zone_high:.2f}  |  price {r.last_price:.2f}, "
            f"{abs(r.dist_pct):.2f}% {'below' if r.dist_pct<0 else 'above'} the zone  |  push {r.run_atr:.1f} ATR"
            +(f"  |  {', '.join(flags)}" if flags else '')+f"  |  block candle {ft(r.ob_candle)} ET")
def digest_text(df,n=10,header=None):
    top=pick(df,n);asof=df['asof'].iloc[0] if len(df) else ''
    now=dt.datetime.now()
    head=header or f"Order blocks closest to being tapped"
    body=[head,f"Data as of {asof}. Thin blocks (1 ATR or less) that price pushed 5+ ATR away from and has not revisited.",""]
    body+= [line(i,r) for i,r in enumerate(top.itertuples(),1)] or ['No fresh blocks match right now.']
    body+=["",f"Full list with filters: {SITE}","Information only, not advice. Block candle times are Eastern."]
    return '\n'.join(body),top
def digest_html(top,asof,head):
    rows=''
    for i,r in enumerate(top.itertuples(),1):
        col='#0a7a4b' if r.side=='demand' else '#b3261e'
        fl=[x for x,c in (('quiet push',r.vol_x<=0.92),('in session',r.formed=='session'),('4H overlap',bool(r.mtf_4h))) if c]
        rows+=(f'<tr><td style="padding:6px 8px">{i}</td><td style="padding:6px 8px"><b>{r.symbol}</b> {r.timeframe}</td>'
               f'<td style="padding:6px 8px;color:{col}">{r.side}</td><td style="padding:6px 8px">{r.zone_low:.2f} to {r.zone_high:.2f}</td>'
               f'<td style="padding:6px 8px">{r.last_price:.2f} ({abs(r.dist_pct):.2f}% {"below" if r.dist_pct<0 else "above"})</td>'
               f'<td style="padding:6px 8px">{r.run_atr:.1f}</td><td style="padding:6px 8px">{", ".join(fl)}</td><td style="padding:6px 8px">{ft(r.ob_candle)}</td></tr>')
    return (f'<div style="font-family:-apple-system,Segoe UI,Arial,sans-serif;font-size:14px;color:#14181f"><h2 style="margin:0 0 4px">{head}</h2>'
            f'<p style="color:#5d6675;margin:0 0 12px">Data as of {asof}. Thin blocks (1 ATR or less) that price pushed 5+ ATR away from and has not revisited.</p>'
            '<table style="border-collapse:collapse;font-size:13px"><tr style="text-align:left;color:#5d6675"><th style="padding:6px 8px">#</th><th style="padding:6px 8px">Name</th><th style="padding:6px 8px">Side</th><th style="padding:6px 8px">Zone</th><th style="padding:6px 8px">Price</th><th style="padding:6px 8px">Push (ATR)</th><th style="padding:6px 8px">Flags</th><th style="padding:6px 8px">Block candle (ET)</th></tr>'
            +rows+f'</table><p style="margin-top:14px"><a href="{SITE}">Open the full list with filters</a></p><p style="color:#5d6675;font-size:12px">Information only, not advice.</p></div>')
def send_email(to,subject,text,html=None):
    """SMTP (set SMTP_USER + SMTP_PASSWORD, e.g. a Gmail app password; SMTP_HOST/PORT/FROM optional)."""
    import smtplib
    from email.message import EmailMessage
    user,pw=os.environ.get('SMTP_USER'),os.environ.get('SMTP_PASSWORD')
    if not (user and pw):return 'no SMTP credentials set'
    m=EmailMessage();m['Subject']=subject;m['From']=os.environ.get('SMTP_FROM',user);m['To']=to;m.set_content(text)
    if html:m.add_alternative(html,subtype='html')
    with smtplib.SMTP_SSL(os.environ.get('SMTP_HOST','smtp.gmail.com'),int(os.environ.get('SMTP_PORT','465'))) as s:
        s.login(user,pw);s.send_message(m)
    return 'sent'
def send_mac_mail(to,subject,text):
    """Local macOS Mail.app (works only on a Mac with a Mail account set up)."""
    import subprocess,tempfile
    with tempfile.NamedTemporaryFile('w',suffix='.txt',delete=False) as b:b.write(text)
    with tempfile.NamedTemporaryFile('w',suffix='.txt',delete=False) as j:j.write(subject)
    scr=('set theBody to (read POSIX file "%s" as \u00abclass utf8\u00bb)\nset theSubject to (read POSIX file "%s" as \u00abclass utf8\u00bb)\n'
         'tell application "Mail"\nset msg to make new outgoing message with properties {subject:theSubject, content:theBody, visible:false}\n'
         'tell msg to make new to recipient with properties {address:"%s"}\nsend msg\nend tell')%(b.name,j.name,to)
    r=subprocess.run(['osascript','-e',scr.encode().decode('unicode_escape')],capture_output=True,text=True,timeout=60)
    return 'sent' if r.returncode==0 else r.stderr.strip()
def send_ntfy(subject,text):
    t=os.environ.get('NTFY_DIGEST_TOPIC')
    if not t:return None
    return requests.post(f'https://ntfy.sh/{t}',data=text.encode('utf-8'),headers={'Title':subject},timeout=30).status_code
def send_discord(text):
    u=os.environ.get('DISCORD_WEBHOOK_URL')
    if not u:return None
    return requests.post(u,json={'content':'```\n'+text[:1900]+'\n```'},timeout=30).status_code
def send_telegram(text):
    t,c=os.environ.get('TELEGRAM_BOT_TOKEN'),os.environ.get('TELEGRAM_CHAT_ID')
    if not (t and c):return None
    return requests.post(f'https://api.telegram.org/bot{t}/sendMessage',json={'chat_id':c,'text':text[:4000],'disable_web_page_preview':True},timeout=30).status_code
def main():
    ap=argparse.ArgumentParser();ap.add_argument('cmd');ap.add_argument('--force',action='store_true');ap.add_argument('--to',default='');ap.add_argument('--n',type=int,default=10);ap.add_argument('--test',action='store_true');ap.add_argument('--file',default='dash_obs.json');ap.add_argument('--via',default='smtp')
    a=ap.parse_args();df=load(a.file)
    et=pd.Timestamp.now(tz='America/New_York')
    if not a.force and not (et.weekday()<5 and 8<=et.hour<9):
        print(f'outside the 8-9am ET send window ({et:%a %H:%M}); skipping');return
    text,top=digest_text(df,a.n)
    subject=('TEST: ' if a.test else '')+f"Order blocks closest to being tapped, {et:%a %b %-d}"
    to=a.to or os.environ.get('DIGEST_EMAILS','')
    sent=[]
    html=digest_html(top,df['asof'].iloc[0],'Order blocks closest to being tapped')
    for addr in [x.strip() for x in to.split(',') if x.strip()]:
        try:sent.append(('email '+addr,send_mac_mail(addr,subject,text) if a.via=='mac' else send_email(addr,subject,text,html)))
        except Exception as e:sent.append(('email '+addr,'failed: '+str(e)[:120]))
    r=send_ntfy(subject,text)
    if r is not None:sent.append(('ntfy push',r))
    for nm,fn in (('discord',send_discord),('telegram',send_telegram)):
        r=fn(text)
        if r is not None:sent.append((nm,r))
    print(text);print('---');print(sent)
if __name__=='__main__':main()
