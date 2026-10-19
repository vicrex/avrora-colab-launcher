"""Independent historical five-wave signal and portfolio verification (CHECK2).

Independent formulas/state machine; no imports from the production signal or
fill engine. Caller supplies parsed SHA-verified research-only M15 candles.
No order placement, no network, no reading private data from this module.
"""


def true_range_sma(bars, moment, span=14):
    values=[]
    for n in range(moment-span+1,moment+1):
        high,low=bars[n][2],bars[n][3]
        prev_close=bars[n-1][4]
        values.append(max(high-low,high-prev_close,prev_close-low))
    return sum(values)/span


def independent_signals(bars, params):
    wing=params["wing"]
    window=wing*2+1
    swings=[]
    emitted=set()
    out=[]
    for t in range(window-1,len(bars)-1):
        k=t-wing
        segment=bars[k-wing:k+wing+1]
        peak=sum(candle[2]>=bars[k][2] for candle in segment)==1
        trough=sum(candle[3]<=bars[k][3] for candle in segment)==1
        if peak != trough:
            direction="H" if peak else "L"
            price=bars[k][2] if peak else bars[k][3]
            item=(direction,k,price,t)
            if swings and swings[-1][0]==direction:
                prior=swings[-1]
                improve=price>prior[2] if peak else price<prior[2]
                if improve:
                    swings[-1]=item
            else:
                swings.append(item)
                swings=swings[-6:]
        if len(swings)!=6 or t<15:
            continue
        types=tuple(a[0] for a in swings)
        prices=[a[2] for a in swings]
        for side in (1,-1):
            desired=("L","H","L","H","L","H") if side==1 else ("H","L","H","L","H","L")
            if types!=desired:
                continue
            tag=(side,swings[5][1])
            if tag in emitted or t-swings[5][3]>8:
                continue
            first=side*(prices[1]-prices[0])
            third=side*(prices[3]-prices[2])
            fifth=side*(prices[5]-prices[4])
            if min(first,third,fifth)<=0:
                continue
            if third<params["wave3_min_ratio"]*first or third+1e-12<min(first,fifth):
                continue
            if side*(prices[2]-prices[0])<=0 or side*(prices[4]-prices[1])<=0:
                continue
            volatility=true_range_sma(bars,t)
            if volatility<=0:
                continue
            if side*(bars[t][4]-prices[5])<=params["buffer_atr"]*volatility:
                continue
            out.append({
                "signal_i":t, "entry_i":t+1, "side":side,
                "p4":prices[4], "pivot5_confirm_i":swings[5][3],
                "signal_t":bars[t][0], "atr":volatility,
            })
            emitted.add(tag)
    return out


def independent_fill(bars, signal, params):
    entry_index=signal["entry_i"]
    entry=bars[entry_index][1]
    side=signal["side"]
    stop=signal["p4"]
    risk_distance=(entry-stop)*side
    if risk_distance<=0 or risk_distance>=0.12*entry:
        return None
    exposure=min(500.0,5.0*entry/risk_distance)
    if exposure<1.0:
        return None
    limit=entry+side*params["reward_r"]*risk_distance
    exit_index=min(len(bars)-1,entry_index+params["max_bars"])
    fill=bars[exit_index][4]
    cause="TIME"
    for t in range(entry_index,exit_index+1):
        open_,high,low=bars[t][1:4]
        if side*(open_-stop)<=0:
            exit_index=t
            fill=open_
            cause="GAP_STOP"
            break
        if (low<=stop) if side==1 else (high>=stop):
            exit_index=t
            fill=stop
            cause="STOP_FIRST"
            break
        if (high>=limit) if side==1 else (low<=limit):
            exit_index=t
            fill=limit
            cause="TARGET"
            break
    gross=side*(fill/entry-1.0)*exposure
    return {
        "entry_t":bars[entry_index][0],"exit_t":bars[exit_index][0],
        "entry":entry,"exit":fill,"side":side,"reason":cause,
        "signal_t":signal["signal_t"],"p5_confirm_t":bars[signal["pivot5_confirm_i"]][0],
        "stop_risk":exposure*risk_distance/entry,
        "notional":exposure,"gross":gross,
        "net20":gross-exposure*(20.0/10000),
        "net25":gross-exposure*(25.0/10000),
    }


def independent_portfolio(series,params):
    proposals=[]
    for (period,symbol),bars in sorted(series.items()):
        for sig in independent_signals(bars,params):
            proposals.append((sig["signal_t"],symbol,period,bars,sig))
    proposals.sort(key=lambda x:(x[0],x[1],x[2]))
    ledger=[]
    for _,symbol,period,bars,sig in proposals:
        trade=independent_fill(bars,sig,params)
        if trade is None:
            continue
        currently_open=[old for old in ledger
                        if old["entry_t"]<=trade["entry_t"]<=old["exit_t"]]
        if len(currently_open)>=2 or any(old["symbol"]==symbol for old in currently_open):
            continue
        ledger.append({**trade,"symbol":symbol,"period":period})
    return proposals,ledger


def same_fields(actual,expected,location):
    if len(actual)!=len(expected):
        raise ValueError("BLOCKED_CHECK2_COUNT_"+location)
    for i,(a,b) in enumerate(zip(actual,expected)):
        if set(a)!=set(b):
            raise ValueError("BLOCKED_CHECK2_FIELD_SET_"+location)
        for k in a:
            va,vb=a[k],b[k]
            if type(va) is not type(vb):
                raise ValueError("BLOCKED_CHECK2_TYPE_"+location+"_"+k)
            if isinstance(va,float):
                if abs(va-vb)>max(1e-9,1e-12*max(abs(va),abs(vb))):
                    raise ValueError("BLOCKED_CHECK2_VALUE_"+location+"_"+k)
            elif va!=vb:
                raise ValueError("BLOCKED_CHECK2_VALUE_"+location+"_"+k)


def verify_all(series,params,proposals,ledger):
    """Both independent signals and complete portfolio fill ledger must agree."""
    expected_proposals,expected_ledger=independent_portfolio(series,params)
    def strip_proposal(p):
        _,symbol,period,bars,signal=p
        return {"symbol":symbol,"period":period,**signal}
    same_fields([strip_proposal(p) for p in proposals],
                [strip_proposal(p) for p in expected_proposals],"signals")
    same_fields(ledger,expected_ledger,"ledger")
    return {"check2":"PASS_FULL_SIGNAL_AND_LEDGER_PARITY",
            "proposals":len(expected_proposals),"closed_trades":len(expected_ledger)}
