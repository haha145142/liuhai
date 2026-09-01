from datetime import datetime
from typing import Any
from fastapi import FastAPI, WebSocket
from fastapi.middleware.cors import CORSMiddleware

app = FastAPI(title="Fund Watch API", version="0.1.0")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_credentials=False, allow_methods=["*"], allow_headers=["*"])

FUNDS = {
    "110022": {"fund_code":"110022","fund_name":"易方达消费行业股票","fund_type":1,"manager":"萧楠","company":"易方达基金","nav":3.2150,"nav_date":"2026-08-31","management_fee":1.5,"is_index":0},
    "000001": {"fund_code":"000001","fund_name":"华夏成长混合","fund_type":2,"manager":"代瑞亮","company":"华夏基金","nav":1.7420,"nav_date":"2026-08-31","management_fee":1.5,"is_index":0},
}
INDUSTRIES = [
    {"industry_name":"食品饮料","weight":62.3,"change_pct":1.25},
    {"industry_name":"家用电器","weight":12.5,"change_pct":0.80},
    {"industry_name":"农林牧渔","weight":8.2,"change_pct":-0.30},
    {"industry_name":"医药生物","weight":7.0,"change_pct":0.55},
]
STOCKS = [
    {"stock_code":"600519","stock_name":"贵州茅台","weight":9.82,"change_pct":2.10,"contribution":0.21},
    {"stock_code":"000858","stock_name":"五粮液","weight":8.15,"change_pct":1.75,"contribution":0.14},
    {"stock_code":"600887","stock_name":"伊利股份","weight":5.60,"change_pct":0.92,"contribution":0.05},
    {"stock_code":"000568","stock_name":"泸州老窖","weight":4.90,"change_pct":-0.40,"contribution":-0.02},
]
INDICES = [
    {"code":"sh000001","name":"上证指数","last_price":3340.21,"change_pct":0.48},
    {"code":"sh000300","name":"沪深300","last_price":3861.17,"change_pct":0.71},
    {"code":"sz399905","name":"中证500","last_price":5350.44,"change_pct":0.92},
    {"code":"sz399006","name":"创业板指","last_price":2520.18,"change_pct":1.31},
    {"code":"hkHSI","name":"恒生指数","last_price":25872.60,"change_pct":-0.22},
    {"code":"nasdaq","name":"纳斯达克","last_price":21580.40,"change_pct":0.36},
]

def envelope(data: Any): return {"code":0,"msg":"ok","data":data}

def estimate(code: str):
    fund = FUNDS[code]
    change = 0.83 if code == "110022" else 0.56
    return {"fund_code":code,"trade_date":"2026-09-01","nav_previous":fund["nav"],"est_nav":round(fund["nav"]*(1+change/100),4),"est_change_pct":change,"confidence":"medium","deviation_recent":0.31,"top_contributors":STOCKS[:2],"updated_at":datetime.now().strftime("%Y-%m-%d %H:%M:%S")}

@app.get("/health")
def health(): return {"status":"ok","service":"fund-watch-api","time":datetime.now().isoformat()}

@app.get("/api/v1/funds/search")
def search_funds(keyword: str="", page: int=1, size: int=20):
    rows=[f for f in FUNDS.values() if not keyword or keyword in f["fund_code"] or keyword in f["fund_name"]]
    return envelope({"items":rows[(page-1)*size:page*size],"page":page,"size":size,"total":len(rows)})

@app.get("/api/v1/funds/{fund_code}")
def fund_detail(fund_code: str): return envelope(FUNDS.get(fund_code,{"fund_code":fund_code,"fund_name":"演示基金","nav":1.0,"nav_date":"2026-08-31"}))

@app.get("/api/v1/estimate/{fund_code}")
def fund_estimate(fund_code: str): return envelope(estimate(fund_code if fund_code in FUNDS else "110022"))

@app.get("/api/v1/estimate/{fund_code}/timeline")
def estimate_timeline(fund_code: str, date: str="2026-09-01"):
    base=FUNDS.get(fund_code,FUNDS["110022"])["nav"]
    points=[]
    for minute,delta in [(0,-0.15),(30,0.05),(60,0.22),(90,0.18),(120,0.51),(150,0.65),(180,0.83),(210,0.72),(240,0.83),(270,0.91),(300,0.83)]:
        hh=9+(30+minute)//60; mm=(30+minute)%60
        points.append({"time":f"{hh:02d}:{mm:02d}","est_nav":round(base*(1+delta/100),4),"change_pct":delta,"benchmark_pct":round(delta*0.78,2)})
    return envelope({"fund_code":fund_code,"date":date,"points":points})

@app.get("/api/v1/funds/{fund_code}/holdings")
def holdings(fund_code: str): return envelope({"fund_code":fund_code,"report_date":"2026-06-30","holdings":STOCKS})
@app.get("/api/v1/funds/{fund_code}/industries")
def industries(fund_code: str): return envelope({"fund_code":fund_code,"report_date":"2026-06-30","industries":INDUSTRIES})
@app.get("/api/v1/funds/{fund_code}/top-stocks")
def top_stocks(fund_code: str): return envelope({"fund_code":fund_code,"stocks":STOCKS})
@app.get("/api/v1/market/indices")
def market_indices(): return envelope(INDICES)
@app.get("/api/v1/market/industries/heatmap")
def industry_heatmap(): return envelope(INDUSTRIES+[ {"industry_name":"电子","weight":0,"change_pct":1.72},{"industry_name":"计算机","weight":0,"change_pct":-0.38},{"industry_name":"电力设备","weight":0,"change_pct":0.94} ])
@app.get("/api/v1/watchlists")
def watchlists(): return envelope([{ "id":1,"group_name":"我的组合","items":["110022","000001"]},{"id":2,"group_name":"观察清单","items":["110022"]}])
@app.get("/api/v1/watchlists/{group_id}/quotes")
def watchlist_quotes(group_id: int):
    codes=["110022","000001"] if group_id==1 else ["110022"]
    items=[]
    for code in codes: items.append({**FUNDS[code],**estimate(code)})
    return envelope({"group_id":group_id,"group_name":"我的组合" if group_id==1 else "观察清单","total_est_change_pct":round(sum(x["est_change_pct"] for x in items)/len(items),2),"items":items})
@app.get("/api/v1/accuracy/{fund_code}")
def accuracy(fund_code: str, days: int=20): return envelope({"fund_code":fund_code,"days":days,"mean_absolute_error":0.31,"records":[]})

@app.websocket("/api/v1/ws/estimate/{fund_code}")
async def ws_estimate(websocket: WebSocket, fund_code: str):
    await websocket.accept()
    try:
        while True:
            await websocket.send_json(envelope(estimate(fund_code if fund_code in FUNDS else "110022")))
            await websocket.receive_text()
    except Exception:
        await websocket.close()
