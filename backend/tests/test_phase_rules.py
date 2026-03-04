from app.models import Phase


def test_phase_order_lock():
    order = [Phase.F1, Phase.F2, Phase.F3, Phase.F4, Phase.F5]
    assert order.index(Phase.F3) > order.index(Phase.F2)
