from datetime import datetime,timedelta
from backend.nds_core import Bar,heikin_ashi,fib_levels

def test_ha_seed():
    b=Bar(datetime.now(),1,2,0,1.5)
    ho,hc=heikin_ashi([b])[0]
    assert hc==1.125 and ho==1.25

def test_long_fib():
    e,sl,tp=fib_levels(90,100,True)
    assert e<tp<100 and sl<e

def test_short_fib():
    e,sl,tp=fib_levels(100,90,False)
    assert e>tp>90 and sl>e
