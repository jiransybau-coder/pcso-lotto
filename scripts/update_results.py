#!/usr/bin/env python3
"""Daily PCSO results updater. Reads Inquirer's per-day lotto pages and merges new draws into results.json.
Run:  python scripts/update_results.py [--days 3] [--dry-run]
Never overwrites results.json unless at least one valid new draw was parsed."""
import json,re,sys,os,urllib.request,datetime as dt
from html.parser import HTMLParser
ROOT=os.path.dirname(os.path.dirname(os.path.abspath(__file__)));OUT=os.path.join(ROOT,'results.json')
MON=['january','february','march','april','may','june','july','august','september','october','november','december']
URL='https://www.inquirer.net/lotto-results/{m}-{d}-{y}/'
GAMES=[(r'ultra.*6\s*/\s*58','658'),(r'grand.*6\s*/\s*55','655'),(r'super.*6\s*/\s*49','649'),(r'lotto\s*6\s*/\s*42','642'),
       (r'\b6\s*d\b','6d'),(r'\b4\s*d\b','4d'),(r'3\s*d|swertres','3d'),(r'2\s*d|ez\s*2','2d')]
LEN={'658':6,'655':6,'649':6,'642':6,'6d':6,'4d':4,'3d':3,'2d':2}
class Rows(HTMLParser):
    def __init__(s):super().__init__();s.rows=[];s.r=None;s.c=None
    def handle_starttag(s,t,a):
        if t=='tr':s.r=[]
        elif t in('td','th') and s.r is not None:s.c=''
    def handle_endtag(s,t):
        if t in('td','th') and s.r is not None and s.c is not None:s.r.append(re.sub(r'\s+',' ',s.c).strip());s.c=None
        elif t=='tr' and s.r is not None:
            if s.r:s.rows.append(s.r)
            s.r=None
    def handle_data(s,d):
        if s.c is not None:s.c+=d
def fetch(u):
    req=urllib.request.Request(u,headers={'User-Agent':'Mozilla/5.0 (compatible; lotto-results-bot)'})
    with urllib.request.urlopen(req,timeout=30) as r:return r.read().decode('utf-8','replace')
def money(x):
    m=re.search(r'[\d,]+(?:\.\d+)?',x or '');return float(m.group(0).replace(',','')) if m else None
def parse(html,day):
    p=Rows();p.feed(html);out={}
    for row in p.rows:
        if len(row)<3:continue
        name=row[0].lower()
        gid=next((g for rx,g in GAMES if re.search(rx,name)),None)
        if not gid or 'mega' in name or '6/45' in name:continue
        nums=re.findall(r'\d+',row[1])
        if len(nums)!=LEN[gid] or re.search(r'await|tba|pending',row[1],re.I):continue
        nums=[int(n) for n in nums]
        if gid in('4d','3d','6d') and any(n>9 for n in nums):continue
        if gid=='2d' and any(n<1 or n>31 for n in nums):continue
        if gid in('658','655','649','642') and any(n<1 or n>58 for n in nums):continue
        jp=money(row[2]);
        if jp is None:continue
        win=None
        if len(row)>3 and re.fullmatch(r'[\d,]+',row[3].strip()):win=int(row[3].replace(',',''))
        key=day.isoformat()
        if gid in('3d','2d'):
            t=re.search(r'(2|5|9)\s*pm',name,re.I)
            if not t:continue
            key+=' '+t.group(1)+'PM'
        out.setdefault(gid,[]).append([key,nums,jp,win])
    return out
def main():
    days=3;dry='--dry-run' in sys.argv
    if '--days' in sys.argv:days=int(sys.argv[sys.argv.index('--days')+1])
    today=(dt.datetime.utcnow()+dt.timedelta(hours=8)).date()
    cur=json.load(open(OUT)) if os.path.exists(OUT) else {}
    new={};errs=0
    for k in range(days):
        d=today-dt.timedelta(days=k)
        try:html=fetch(URL.format(m=MON[d.month-1],d=d.day,y=d.year))
        except Exception as e:print('fetch failed',d,e);errs+=1;continue
        got=parse(html,d);print(d,{g:len(v) for g,v in got.items()})
        for g,v in got.items():new.setdefault(g,[]).extend(v)
    added=0
    for g,v in new.items():
        have={x[0]:i for i,x in enumerate(cur.setdefault(g,{}).setdefault('draws',[]))}
        for x in sorted(v,key=lambda z:z[0]):
            if x[0] in have:
                old=cur[g]['draws'][have[x[0]]]
                if old[3] is None and x[3] is not None:old[3]=x[3];added+=1
                continue
            cur[g]['draws'].append(x);added+=1
        cur[g]['draws'].sort(key=lambda z:z[0])
    if '658' in cur and cur['658']['draws']:
        l=cur['658']['draws'][-1];cur['658']['jackpot']=l[2]
        y,m,d=map(int,l[0][:10].split('-'));cur['658']['asOf']='%s %d, %d'%(MON[m-1].title()[:3],d,y)
    print('new/updated draws:',added)
    if not added:
        print('nothing new');sys.exit(1 if errs==days else 0)
    if dry:print(json.dumps(cur)[:600]);return
    json.dump(cur,open(OUT,'w'),separators=(',',':'));print('results.json updated')
if __name__=='__main__':main()
