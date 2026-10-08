from unittest.mock import Mock
from live.fxpro_public import FxProPublicQuote

HTML='''<a>GOLD 4124.23 /4123.91 Trade</a> ... GOLD SPOT Gold Ounce vs US Dollar 4123.71 4124.03'''

def test_parse_ticker():
    feed=FxProPublicQuote()
    feed.session=Mock()
    resp=Mock(); resp.text=HTML; resp.raise_for_status=Mock()
    feed.session.get.return_value=resp
    q=feed.get_gold()
    assert q.symbol=='GOLD'
    assert q.bid==4123.91 and q.ask==4124.23
