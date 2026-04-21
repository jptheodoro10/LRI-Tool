from app.domain.phases import DEFAULT_PHASE, MAX_PHASE, advance_phase


def test_phase_advances_until_max():
    assert advance_phase(DEFAULT_PHASE) == DEFAULT_PHASE + 1
    assert advance_phase(MAX_PHASE) == MAX_PHASE
