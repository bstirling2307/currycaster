def test_application_smoke_loads_a_tone():
    import currycaster
    assert currycaster.run_smoke() == 0
