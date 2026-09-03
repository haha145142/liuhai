"""Historical-NAV DCA calculation shared by Fund Watch."""
from __future__ import annotations
from calendar import monthrange
from datetime import date, datetime, timedelta
from typing import Any

def add_months(d: date, months: int) -> date:
    total=d.year*12+d.month-1+months; year,month0=divmod(total,12); month=month0+1
    return date(year,month,min(d.day,monthrange(year,month)[1]))

def nearest(rows:list[dict[str,Any]],target:date)->dict[str,Any]|None:
    candidate=None
    for row in rows:
        d=row["date"].date() if isinstance(row["date"],datetime) else row["date"]
        if d<=target: candidate=row
        else: break
    return candidate or (rows[0] if rows else None)

def xirr(cashflows:list[tuple[date,float]])->float|None:
    if len(cashflows)<2:return None
    t0=cashflows[0][0]
    def npv(rate:float)->float:
        return sum(cf/((1+rate)**((d-t0).days/365.0)) for d,cf in cashflows)
    lo,hi=-0.9999,10.0; flo,fhi=npv(lo),npv(hi)
    for _ in range(16):
        if flo*fhi<=0: break
        hi*=2; fhi=npv(hi)
    else:return None
    for _ in range(120):
        mid=(lo+hi)/2; fmid=npv(mid)
        if abs(fmid)<1e-10:return mid
        if flo*fmid<=0:hi=mid
        else:lo,flo=mid,fmid
    return (lo+hi)/2

def demo(start_nav:float,monthly_amount:float,months:int,frequency:str)->dict[str,Any]:
    ppm={"monthly":1,"biweekly":2,"weekly":4}[frequency]; periods=months*ppm
    annual_return=0.08; period_return=(1+annual_return)**(1/(12*ppm))-1
    nav=start_nav; shares=invested=0.0; series=[]
    for i in range(periods):
        nav*=1+period_return; contribution=monthly_amount/ppm
        shares+=contribution/nav; invested+=contribution
        if i%max(1,periods//12)==0 or i==periods-1:
            series.append({"period":i+1,"nav":round(nav,6),"value":round(shares*nav,2),"invested":round(invested,2)})
    final_value=shares*nav
    return {"frequency":frequency,"months":months,"total_invested":round(invested,2),"final_value":round(final_value,2),"profit":round(final_value-invested,2),"return_pct":round((final_value/invested-1)*100,2) if invested else 0,"irr_pct":8.0,"series":series,"source":"demo-model","data_quality":"demo; no historical NAV database configured"}

def run(rows:list[dict[str,Any]],monthly_amount:float,months:int,frequency:str,start_date:date|None=None)->dict[str,Any]|None:
    if not rows:return None
    first=rows[0]["date"].date() if isinstance(rows[0]["date"],datetime) else rows[0]["date"]
    last=rows[-1]["date"].date() if isinstance(rows[-1]["date"],datetime) else rows[-1]["date"]
    start=start_date or add_months(last,-months)
    if start<first: raise ValueError(f"历史数据不足：可用区间 {first} 至 {last}")
    end=min(add_months(start,months),last); ppm={"monthly":1,"biweekly":2,"weekly":4}[frequency]; dates=[]
    if frequency=="monthly":
        for i in range(months):
            d=add_months(start,i)
            if d<=end:dates.append(d)
    else:
        step=14 if frequency=="biweekly" else 7; d=start
        while d<=end: dates.append(d); d+=timedelta(days=step)
    if not dates:raise ValueError("没有可用回测区间")
    per_period=monthly_amount/ppm; shares=invested=0.0; flows=[]; series=[]
    for i,target in enumerate(dates):
        row=nearest(rows,target)
        if not row or float(row["nav"])<=0:continue
        used=row["date"].date() if isinstance(row["date"],datetime) else row["date"]; nav=float(row["nav"])
        shares+=per_period/nav; invested+=per_period; flows.append((used,-per_period))
        if i%max(1,len(dates)//12)==0 or i==len(dates)-1:
            series.append({"period":i+1,"date":used.isoformat(),"nav":round(nav,6),"value":round(shares*nav,2),"invested":round(invested,2)})
    if not flows:raise ValueError("没有有效历史净值")
    final_date=flows[-1][0]; final_row=nearest(rows,final_date); final_value=shares*float(final_row["nav"]); flows.append((final_date,final_value)); irr=xirr(flows); profit=final_value-invested
    return {"frequency":frequency,"months":months,"start_date":start.isoformat(),"end_date":final_date.isoformat(),"total_invested":round(invested,2),"final_value":round(final_value,2),"profit":round(profit,2),"return_pct":round(profit/invested*100,2) if invested else 0,"irr_pct":round((irr or 0)*100,2),"series":series,"source":"postgres-history","data_quality":"historical NAV"}
