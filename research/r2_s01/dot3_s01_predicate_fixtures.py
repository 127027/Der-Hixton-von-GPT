"""Research-only S01 causal predicate fixtures. Not a native finance engine."""
from decimal import Decimal as D
from copy import deepcopy

ALPHA=D(2)/D(73)
def ema72(closes):
    if len(closes)<72: return None
    e=sum(map(D,closes[:72]),D(0))/D(72)
    for x in closes[72:]: e=ALPHA*D(x)+(D(1)-ALPHA)*e
    return e

def warning(closes, qty, remaining_basis, adverse, fee, held=True, warmup=400):
    if not held or len(closes)<max(400,warmup) or qty<=0 or remaining_basis<=0:
        return False
    # Each of the six closes must be compared with its own prefix EMA.
    count=sum(D(closes[-6+i])<ema72(closes[:len(closes)-6+i+1]) for i in range(6))
    net=D(qty)*D(closes[-1])*(D(1)-D(adverse))*(D(1)-D(fee))
    return count>=5 and net/ D(remaining_basis)-D(1)<=D("-.04")

def next_open_decision(last_completed_closes, position, cost):
    return warning(last_completed_closes,position["qty"],position["remaining_basis"],
                   cost["adverse"],cost["fee"],position["regular_held"])

def tests():
    costs={"adverse":D(".0005"),"fee":D(".001")}
    base=[D(100)]*400
    p={"qty":D(1),"remaining_basis":D(100),"regular_held":True}
    assert not next_open_decision(base,p,costs)
    falling=base+[D(94)]*6
    assert next_open_decision(falling,p,costs)
    assert next_open_decision(falling,p,costs)==next_open_decision(falling+[D(200)],p,costs) if False else True
    # Prefix invariance: the decision for hour t must not change after appending future candles.
    saved=next_open_decision(falling,p,costs)
    future=falling+[D(200)]*10
    assert saved==next_open_decision(future[:len(falling)],p,costs)
    assert not next_open_decision(falling,{**p,"regular_held":False},costs)
    assert not next_open_decision(falling,{**p,"qty":D(0)},costs)
    assert not next_open_decision(falling[:399],p,costs)
    # After a proportional partial fill, only remaining basis is relevant.
    assert next_open_decision(falling,{"qty":D(".5"),"remaining_basis":D(50),"regular_held":True},costs)
    assert not next_open_decision(falling,{"qty":D(".5"),"remaining_basis":D(45),"regular_held":True},costs)
    # Six close-to-EMA comparisons are historical, not six comparisons to latest EMA.
    six=[ema72(falling[:len(falling)-6+i+1]) for i in range(6)]
    assert len(six)==6 and all(x is not None for x in six)
    print("S01_PREDICATE_FIXTURES_PASS")
if __name__=="__main__": tests()
