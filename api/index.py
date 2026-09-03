"""Fund Watch unified FastAPI entrypoint."""
from __future__ import annotations
import json, math, os
from datetime import date, datetime, time, timedelta
from typing import Any
from urllib.parse import urlencode
from urllib.request import Request, urlopen
from zoneinfo import ZoneInfo
from fastapi import FastAPI, Header, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
try:
    import psycopg
except Exception:
    psycopg=None
from core.dca_backtest import demo as dca_demo, run as run_dca
from core.live_data import fetch_fund_valuations

TZ=ZoneInfo("Asia/Shanghai")
app=FastAPI(title="Fund Watch API",version="0.5.1")
app.add_middleware(CORSMiddleware,allow_origins=["*"],allow_methods=["*"],allow_headers=["*"])
DEMO_FUNDS=[{"fund_code":"000961","fund_name":"天弘沪深300A","fund_type":"指数型","nav":1.0234,"estimated_nav":1.0311,"change_pct":0.75,"confidence":"高","source":"demo"},{"fund_code":"519674","fund_name":"银河创新成长混合","fund_type":"混合型","nav":0.9842,"estimated_nav":0.9937,"change_pct":0.96,"confidence":"中","source":"demo"},{"fund_code":"110022","fund_name":"易方达消费行业","fund_type":"股票型","nav":1.1865,"estimated_nav":1.1789,"change_pct":-0.64,"confidence":"中","source":"demo"}]
DEMO_HOLDINGS={"000961":[("600519","贵州茅台",5.5,1.2),("601318","中国平安",3.5,0.7),("600036","招商银行",3.0,0.4),("000858","五粮液",2.5,1.1),("000333","美的集团",2.0,0.9)],"519674":[("688981","中芯国际",8.5,2.8),("688111","金山办公",6.5,1.6),("688012","中微公司",5.5,2.2),("688036","传音控股",4.5,1.0),("688008","澜起科技",4.0,1.8)],"110022":[("600519","贵州茅台",9.5,1.2),("000858","五粮液",7.5,1.1),("600887","伊利股份",5.5,0.4),("000568","泸州老窖",5.0,-0.3),("600690","海尔智家",4.0,0.8)]}
DEMO_INDUSTRY_ALLOCATION={"000961":[("食品饮料",28.0),("银行",17.0),("非银金融",12.0),("家用电器",10.0),("其他",33.0)],"519674":[("电子",34.0),("计算机",26.0),("通信",11.0),("机械设备",8.0),("其他",21.0)],"110022":[("食品饮料",42.0),("家用电器",12.0),("医药生物",10.0),("商贸零售",7.0),("其他",29.0)]}
DEMO_INDICES=[{"code":"000001","name":"上证指数","price":3850.2,"change_pct":0.82},{"code":"000300","name":"沪深300","price":4522.1,"change_pct":0.95},{"code":"000905","name":"中证500","price":6844.5,"change_pct":1.26},{"code":"399006","name":"创业板指","price":2780.8,"change_pct":1.81},{"code":"HSI","name":"恒生指数","price":25840.3,"change_pct":-0.32},{"code":"IXIC","name":"纳斯达克","price":21540.2,"change_pct":0.44}]
DEMO_INDUSTRIES=[{"code":"sw27","name":"电子","change_pct":2.72,"leading_stock":"中芯国际"},{"code":"sw28","name":"计算机","change_pct":2.15,"leading_stock":"金山办公"},{"code":"sw06","name":"家用电器","change_pct":1.34,"leading_stock":"美的集团"},{"code":"sw01","name":"食品饮料","change_pct":0.92,"leading_stock":"贵州茅台"},{"code":"sw20","name":"医药生物","change_pct":0.31,"leading_stock":"恒瑞医药"},{"code":"sw14","name":"房地产","change_pct":-0.74,"leading_stock":"万科A"}]
DEMO_ALERTS=[{"id":1,"type":"异动","title":"自选基金单日波动阈值","detail":"超过 ±3% 时提醒","enabled":True},{"id":2,"type":"连跌","title":"连续3天下跌","detail":"基金净值连续三日收跌时提醒","enabled":True},{"id":3,"type":"公告","title":"基金经理变更","detail":"监测基金公司公告","enabled":True},{"id":4,"type":"限额","title":"申购限额变化","detail":"限购/放开/暂停时提醒","enabled":True}]

def now_cn()->datetime:return datetime.now(TZ)
def now_iso()->str:return now_cn().isoformat()
def demo_fund(code:str)->dict[str,Any]|None:return next((x for x in DEMO_FUNDS if x["fund_code"]==code),None)
def db_rows(query:str,params:tuple[Any,...]=())->list[dict[str,Any]]:
    url=os.getenv("DATABASE_URL")
    if not url or psycopg is None:return []
    try:
        with psycopg.connect(url,connect_timeout=4) as conn:
            with conn.cursor() as cur:
                cur.execute(query,params)
                if cur.description is None:return []
                cols=[d.name for d in cur.description];return [dict(zip(cols,row)) for row in cur.fetchall()]
    except Exception:return []
def db_fund(code:str)->dict[str,Any]|None:
    r=db_rows("SELECT fund_code,fund_name,fund_type,nav,nav_date,is_index FROM fund_info WHERE fund_code=%s LIMIT 1",(code,));return r[0] if r else None

def session_phase(now:datetime)->tuple[str,str]:
    if now.weekday()>=5:return "weekend","休市 · 等待下个交易日"
    t=now.time()
    if t<time(9,30):return "pre_open","开盘前 · 暂无盘中估值"
    if t<=time(11,30):return "morning","上午交易 · 当前为参考估值"
    if t<time(13,0):return "lunch","午间休市 · 下午开盘后继续估值"
    if t<=time(15,0):return "afternoon","下午交易 · 当前为参考估值"
    return "post_close","收盘后 · 等待官方净值披露"
def market_status(code:str,fund:dict[str,Any])->dict[str,Any]:
    now=now_cn();phase,banner=session_phase(now);nav=fund.get("nav") if fund.get("nav") is not None else fund.get("latest_nav");nd=fund.get("nav_date")
    if hasattr(nd,"isoformat"):nd=nd.isoformat()
    final=phase=="post_close" and bool(nd and str(nd)[:10]==now.date().isoformat())
    return {"fund_code":code,"fund_name":fund.get("fund_name"),"market_phase":phase,"market_phase_label":banner,"banner":"今日官方净值已定稿" if final else banner,"official_nav":float(nav) if nav is not None else None,"official_nav_date":nd,"official_status":"final" if final else ("published" if nav is not None else "unavailable"),"is_final":final,"timezone":"Asia/Shanghai","as_of":now.isoformat()}
def save_estimate_snapshot(payload:dict[str,Any])->None:
    url=os.getenv("DATABASE_URL")
    if not url or psycopg is None or payload.get("estimated_nav") is None:return
    try:
        with psycopg.connect(url,connect_timeout=4) as conn:
            with conn.cursor() as cur:
                cur.execute("INSERT INTO estimated_nav_snapshot(fund_code,trade_date,snapshot_time,est_nav,est_change_pct,official_nav,deviation,model_version) VALUES(%s,%s,%s,%s,%s,%s,%s,%s)",(payload.get("fund_code"),now_cn().date(),now_cn(),payload.get("estimated_nav"),payload.get("estimated_change_pct"),payload.get("latest_nav"),None,"v1"))
            conn.commit()
    except Exception:pass
def demo_history(code:str,points:int)->list[dict[str,Any]]:
    f=demo_fund(code)
    if not f:return []
    base=float(f["nav"]);chg=float(f.get("change_pct",0))/100;now=now_cn().replace(second=0,microsecond=0)
    return [{"time":(now-timedelta(minutes=(points-1-i)*30)).isoformat(),"nav":round(base*(1+chg*i/max(points-1,1)+math.sin(i/4.2)*.0014),6)} for i in range(points)]
def external_json(url:str,params:dict[str,str])->Any:
    req=Request(f"{url}?{urlencode(params)}",headers={"User-Agent":"Mozilla/5.0 (Fund-Watch/0.5)","Accept":"application/json,text/plain,*/*"})
    with urlopen(req,timeout=4) as r:return json.loads(r.read().decode("utf-8",errors="replace"))
def live_indices()->list[dict[str,Any]]:
    try:
        raw=external_json("https://push2.eastmoney.com/api/qt/ulist.np/get",{"secids":"1.000001,1.000300,1.000905,0.399006,100.HSI,100.IXIC","fields":"f2,f3,f12,f14"});rows=((raw.get("data") or {}).get("diff") or []) if isinstance(raw,dict) else [];names={"000001":"上证指数","000300":"沪深300","000905":"中证500","399006":"创业板指","HSI":"恒生指数","IXIC":"纳斯达克"};out=[]
        for r in rows:
            c=str(r.get("f12") or "");p=r.get("f2");g=r.get("f3")
            if c in names and p not in (None,"-"):out.append({"code":c,"name":names[c],"price":float(p),"change_pct":float(g or 0)})
        return out if len(out)>=3 else []
    except Exception:return []
def live_industries()->list[dict[str,Any]]:
    try:
        raw=external_json("https://push2.eastmoney.com/api/qt/clist/get",{"pn":"1","pz":"30","po":"1","np":"1","fltt":"2","invt":"2","fid":"f3","fs":"m:90+t:2","fields":"f2,f3,f12,f14"});rows=((raw.get("data") or {}).get("diff") or []) if isinstance(raw,dict) else [];out=[]
        for r in rows:
            if r.get("f14") and r.get("f3") not in (None,"-"):out.append({"code":str(r.get("f12") or ""),"name":str(r.get("f14")),"change_pct":float(r.get("f3"))})
        return out
    except Exception:return []

@app.get("/api")
def root():return {"name":"Fund Watch","version":"0.5.1","status":"ok","mode":"postgres" if os.getenv("DATABASE_URL") else "demo"}
@app.get("/api/health")
def health():return {"code":0,"status":"healthy","mode":"postgres" if os.getenv("DATABASE_URL") else "demo","database":"ok" if os.getenv("DATABASE_URL") and db_rows("SELECT 1") else ("not_configured" if not os.getenv("DATABASE_URL") else "error"),"time":now_iso()}
@app.get("/api/funds")
def funds():
    rows=db_rows("SELECT fund_code,fund_name,fund_type,nav,nav_date,is_index FROM fund_info ORDER BY fund_code LIMIT 200")
    if rows:
        for r in rows:r["nav"]=float(r["nav"]) if r["nav"] is not None else None;r["source"]="postgres";r["confidence"]="高" if r.get("is_index") else "中"
        try:live=fetch_fund_valuations([r["fund_code"] for r in rows])
        except Exception:live={}
        for r in rows:r.update(live.get(r["fund_code"],{}));save_estimate_snapshot(r)
        return {"code":0,"data":rows,"source":"postgres"}
    try:live=fetch_fund_valuations([x["fund_code"] for x in DEMO_FUNDS])
    except Exception:live={}
    data=[]
    for item in DEMO_FUNDS:
        x={**item,**live.get(item["fund_code"],{})};x["source"]=x.get("source") or "demo";x["data_quality"]="provider" if x.get("provider_status")=="available" else "demo-fallback"
        if x.get("provider_status")=="available":save_estimate_snapshot(x)
        data.append(x)
    return {"code":0,"data":data,"source":"live-provider-or-demo","data_quality":"mixed; every row is explicitly labelled"}
@app.get("/api/funds/{fund_code}/estimate")
def estimate(fund_code:str):
    fund=db_fund(fund_code)
    try:live=fetch_fund_valuations([fund_code]).get(fund_code,{})
    except Exception as exc:live={"provider_error":str(exc)}
    if fund:
        nav=float(fund["nav"] or 0)
        if live.get("estimated_nav") is not None:
            data={"fund_code":fund_code,"fund_name":fund["fund_name"],"fund_type":fund["fund_type"],"latest_nav":live.get("latest_nav") or nav,"estimated_nav":live["estimated_nav"],"estimated_change_pct":live.get("estimated_change_pct"),"valuation_time":live.get("valuation_time"),"confidence":"高" if fund.get("is_index") else "中","source":live.get("source","live-provider"),"snapshot_time":now_iso(),"data_quality":"provider"};save_estimate_snapshot(data);return {"code":0,"data":data}
        return {"code":0,"data":{"fund_code":fund_code,"fund_name":fund["fund_name"],"fund_type":fund["fund_type"],"latest_nav":nav,"estimated_nav":None,"estimated_change_pct":None,"confidence":"暂无盘中估值","source":"postgres","data_quality":"official-nav-only","snapshot_time":now_iso()}}
    fallback=demo_fund(fund_code)
    if live and (live.get("estimated_nav") is not None or live.get("latest_nav") is not None):
        data={**(fallback or {}),**live,"source":live.get("source","live-provider"),"data_quality":"provider","snapshot_time":now_iso()};save_estimate_snapshot(data);return {"code":0,"data":data}
    if fallback:return {"code":0,"data":{**fallback,"source":"demo-fallback","data_quality":"demo-fallback","snapshot_time":now_iso()}}
    raise HTTPException(404,"基金不存在")
@app.get("/api/fund-status")
def fund_status(fund_code:str=Query(...,min_length=6,max_length=6)):
    fund=db_fund(fund_code) or demo_fund(fund_code)
    if not fund:return {"code":404,"data":{"fund_code":fund_code,"banner":"基金不存在"}}
    return {"code":0,"data":market_status(fund_code,fund)}
@app.get("/api/funds/{fund_code}/nav-history")
def nav_history(fund_code:str,points:int=Query(default=60,ge=12,le=240)):
    snap=db_rows("SELECT snapshot_time,est_nav FROM estimated_nav_snapshot WHERE fund_code=%s AND snapshot_time>=NOW()-INTERVAL '2 days' ORDER BY snapshot_time ASC LIMIT %s",(fund_code,points))
    if snap:return {"code":0,"data":[{"time":r["snapshot_time"].isoformat() if hasattr(r["snapshot_time"],"isoformat") else str(r["snapshot_time"]),"nav":float(r["est_nav"])} for r in snap],"source":"postgres-estimate-snapshots","kind":"intraday_estimate"}
    rows=db_rows("SELECT nav_date,nav FROM fund_nav_history WHERE fund_code=%s ORDER BY nav_date DESC LIMIT %s",(fund_code,points))
    if rows:
        rows.reverse();return {"code":0,"data":[{"time":r["nav_date"].isoformat(),"nav":float(r["nav"])} for r in rows],"source":"postgres","kind":"official_nav_history"}
    if not demo_fund(fund_code):raise HTTPException(404,"基金不存在")
    return {"code":0,"data":demo_history(fund_code,points),"source":"demo-simulated","kind":"demo"}
@app.get("/api/funds/{fund_code}/holdings")
def holdings(fund_code:str):
    rows=db_rows("SELECT stock_code,stock_name,weight,is_top_ten,report_date FROM fund_holding WHERE fund_code=%s ORDER BY report_date DESC,weight DESC LIMIT 20",(fund_code,))
    if rows:
        for r in rows:r["weight"]=float(r["weight"]);r["is_top_ten"]=bool(r["is_top_ten"]);r["report_date"]=r["report_date"].isoformat() if r["report_date"] is not None else None
        return {"code":0,"data":rows,"source":"postgres"}
    f=demo_fund(fund_code);data=[{"stock_code":c,"stock_name":n,"weight":w,"is_top_ten":True,"current_change_pct":chg} for c,n,w,chg in DEMO_HOLDINGS.get(fund_code,[])]
    if not data and not f:raise HTTPException(404,"基金不存在")
    return {"code":0,"data":data,"source":"demo"}
@app.get("/api/funds/{fund_code}/industry-allocation")
def industry_allocation(fund_code:str):
    rows=db_rows("SELECT industry_name,weight FROM fund_industry_alloc WHERE fund_code=%s ORDER BY weight DESC",(fund_code,))
    if rows:return {"code":0,"data":[{"industry_name":r["industry_name"],"weight":float(r["weight"])} for r in rows],"source":"postgres"}
    data=[{"industry_name":n,"weight":w} for n,w in DEMO_INDUSTRY_ALLOCATION.get(fund_code,[])]
    if not data and not demo_fund(fund_code):raise HTTPException(404,"基金不存在")
    return {"code":0,"data":data,"source":"demo"}
@app.get("/api/funds/{fund_code}/contribution")
def contribution(fund_code:str):
    groups:dict[str,float]={}
    for h in holdings(fund_code)["data"]:
        code=h["stock_code"];industry="核心持仓"
        if code in {"688981","688111","688012","688008"}:industry="电子/科技"
        elif code in {"600519","000858","600887","000568"}:industry="食品饮料"
        groups[industry]=groups.get(industry,0)+float(h.get("weight",0))*float(h.get("current_change_pct",0) or 0)/100
    return {"code":0,"data":{"fund_code":fund_code,"industries":[{"industry_name":k,"contribution":round(v,4)} for k,v in sorted(groups.items(),key=lambda x:x[1],reverse=True)]}}
@app.get("/api/market/indices")
def indices():
    live=live_indices();return {"code":0,"data":live or DEMO_INDICES,"source":"eastmoney" if live else "demo","data_quality":"provider" if live else "demo-fallback"}
@app.get("/api/market/industries")
def industries():
    live=live_industries();return {"code":0,"data":live or DEMO_INDUSTRIES,"source":"eastmoney" if live else "demo","data_quality":"provider" if live else "demo-fallback"}
@app.get("/api/market/erp")
def erp():return {"code":0,"data":{"erp_pct":None,"percentile":None,"label":"等待实时估值与国债收益率数据","source":"unavailable","data_quality":"not_configured"}}
@app.get("/api/alerts")
def alerts():return {"code":0,"data":DEMO_ALERTS,"source":"demo-config","data_quality":"configuration-only"}
@app.get("/api/watchlist/groups")
def watchlist_groups():
    rows=db_rows("SELECT id,group_name,sort_order FROM watchlist_group WHERE user_id=1 ORDER BY sort_order,id")
    if rows:return {"code":0,"data":[{"id":r["id"],"name":r["group_name"]} for r in rows],"source":"postgres"}
    return {"code":0,"data":[{"id":"1","name":"我的自选"},{"id":"2","name":"定投组合"},{"id":"3","name":"观察清单"}],"source":"demo"}
@app.get("/api/watchlist/{group_id}")
def watchlist(group_id:int):
    rows=db_rows("SELECT fund_code FROM watchlist_item WHERE group_id=%s ORDER BY sort_order,id",(group_id,));codes=[r["fund_code"] for r in rows] if rows else [x["fund_code"] for x in DEMO_FUNDS];data=[]
    for c in codes:
        try:data.append(estimate(c)["data"])
        except HTTPException:pass
    avg=sum(float(x.get("estimated_change_pct") or x.get("change_pct") or 0) for x in data)/len(data) if data else 0
    return {"code":0,"data":data,"summary":{"fund_count":len(data),"avg_change_pct":round(avg,4)}}
@app.get("/api/backtest/dca")
def dca_backtest(fund_code:str|None=Query(default=None,min_length=6,max_length=6),start_nav:float|None=Query(default=None,gt=0),start_date:date|None=None,monthly_amount:float=Query(default=1000,gt=0),months:int=Query(default=36,ge=3,le=240),frequency:str=Query(default="monthly")):
    freq=frequency.lower().strip()
    if freq not in {"monthly","biweekly","weekly"}:raise HTTPException(400,"frequency must be monthly, biweekly, or weekly")
    code=fund_code
    if not code and start_nav is not None:
        candidates=sorted(((abs(float(x["nav"])-start_nav),x["fund_code"]) for x in DEMO_FUNDS),key=lambda x:x[0]);code=candidates[0][1] if candidates and candidates[0][0]<0.01 else None
    rows=db_rows("SELECT nav_date,nav FROM fund_nav_history WHERE fund_code=%s AND nav IS NOT NULL ORDER BY nav_date ASC",(code,)) if code else []
    normalized=[{"date":r["nav_date"],"nav":float(r["nav"])} for r in rows]
    if normalized:
        try:result=run_dca(normalized,monthly_amount,months,freq,start_date)
        except ValueError as exc:raise HTTPException(422,str(exc))
        if result:result["fund_code"]=code;return {"code":0,"data":result}
    return {"code":0,"data":dca_demo(start_nav or 1.0,monthly_amount,months,freq)}
@app.get("/api/cron/calibrate")
def cron_calibrate(authorization:str|None=Header(default=None)):
    secret=os.getenv("CRON_SECRET")
    if not secret or authorization!=f"Bearer {secret}":raise HTTPException(401,"Unauthorized")
    return {"code":0,"success":True,"message":"Calibration hook ready; official NAV collector can populate fund_nav_history.","time":now_iso()}
