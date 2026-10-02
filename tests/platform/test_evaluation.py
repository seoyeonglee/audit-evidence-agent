def test_evaluation_reports_unknowns_and_quarantines_separately(tmp_path):
    from scripts.evaluate_platform import evaluate_corpus
    corpus=[
      {'id':'valid','media_type':'text/plain','content':'system: prod\nperiod: 2026-Q3\nreviewed_users: 2\nexceptions: 0','expected':{'system':'prod','period':'2026-Q3','reviewed_users':2,'exceptions':0},'expected_codes':[],'quarantine':False},
      {'id':'missing','media_type':'text/plain','content':'system: prod','expected':{'system':'prod'},'expected_codes':['MISSING_FIELDS'],'quarantine':False},
      {'id':'malformed','media_type':'text/plain','content':'reviewed_users: two','expected':{},'expected_codes':[],'quarantine':True},
    ]
    r=evaluate_corpus(corpus)
    assert r['cases']==3
    assert r['field_exact_match']==1.0
    assert r['quarantine_recall']==1.0
    assert r['exception_recall']==1.0
    assert r['unsupported_field_rate']==0.0
