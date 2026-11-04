"""S01 research-only predicate unit fixtures. NOT native fill/finance QA."""
from decimal import Decimal as D

def predicates(closes, quantity, basis, adverse, fee):
    if len(closes) < 72: return []
    alpha=D(2)/D(73)
    ema=sum(closes[:72])/D(72)
    below=[]
    out=[]
    for i,c in enumerate(closes):
        if i>=72: ema=alpha*c+(1-alpha)*ema
        if i>=71: below.append(c<ema)
        if i>=76:
            valid=quantity[i]>0 and basis[i]>0
            net=quantity[i]*c*(1-adverse)*(1-fee)
            out.append((i,valid and sum(below[-6:])>=5 and net/basis[i]-1<=D("-.04")))
    return out

def test():
    prices=[D(100)]*80+[D(90)]*12
    qty=[D(1)]*len(prices);basis=[D(100)]*len(prices)
    f=lambda p:predicates(p,[D(1)]*len(p),[D(100)]*len(p),D(".0005"),D(".001"))
    original=f(prices)
    assert any(v for _,v in original)
    assert original==f(prices+[D(1000000)])[:len(original)]
    assert not any(v for _,v in predicates(prices,[D(0)]*len(prices),basis,D(".0005"),D(".001")))
    assert not any(v for _,v in predicates([D(100)]*len(prices),qty,basis,D(".0005"),D(".001")))
    assert predicates(prices[:71],qty[:71],basis[:71],D(".0005"),D(".001"))==[]
    assert [v for _,v in original]==[v for _,v in predicates(prices,[D(".5")]*len(prices),[D(50)]*len(prices),D(".0005"),D(".001"))]
    print("S01_PREDICATE_FIXTURES_PASS (NOT NATIVE_METHOD_QA)")
if __name__=="__main__":test()
