import pytest
from backend.app.engines.source_resolver import SourceResolver, haversine_distance_m

def test_haversine_distance():
    # Test ~111km per degree latitude
    d = haversine_distance_m(20.0, 78.0, 21.0, 78.0)
    assert 111000.0 < d < 112000.0

def test_source_resolver_matching():
    resolver = SourceResolver(eps_m=750.0, min_samples=3)
    sites = [
        {'site_id': 'SITE_001', 'latitude': 22.0, 'longitude': 72.0},
        {'site_id': 'SITE_002', 'latitude': 22.05, 'longitude': 72.05}
    ]
    resolver.load_sites(sites)

    # 1. Very close to SITE_001 (~45m), far from SITE_002
    r1 = resolver.resolve_detection(22.0003, 72.0003, 'DET_1')
    assert r1['status'] == 'MATCHED'
    assert r1['site_id'] == 'SITE_001'
    assert r1['distance_m'] < 100.0
    assert not r1['is_ambiguous']

    # 2. Far away -> new candidate
    r2 = resolver.resolve_detection(24.0, 75.0, 'DET_2')
    assert r2['status'] == 'NEW_CANDIDATE'
    cand_id = r2['candidate_id']

    # 3. Second detection near candidate
    r3 = resolver.resolve_detection(24.0005, 75.0005, 'DET_3')
    assert r3['status'] == 'CANDIDATE_ACCUMULATED'
    assert r3['candidate_id'] == cand_id
    assert r3['detection_count'] == 2

    # 4. Third detection near candidate -> Promoted!
    r4 = resolver.resolve_detection(24.0002, 75.0002, 'DET_4')
    assert r4['status'] == 'PROMOTED'
    assert 'INDIA_PROMOTED_' in r4['site_id']
    promoted_site_id = r4['site_id']

    # 5. Subsequent detection matches the newly promoted site
    r5 = resolver.resolve_detection(24.0003, 75.0003, 'DET_5')
    assert r5['status'] == 'MATCHED'
    assert r5['site_id'] == promoted_site_id

def test_source_resolver_ambiguity():
    resolver = SourceResolver(eps_m=750.0, min_samples=3)
    sites = [
        {'site_id': 'SITE_001', 'latitude': 22.0, 'longitude': 72.0},
        {'site_id': 'SITE_002', 'latitude': 22.005, 'longitude': 72.005}
    ]
    resolver.load_sites(sites)

    # Detection situated within 750m of both SITE_001 and SITE_002
    r = resolver.resolve_detection(22.002, 72.002, 'DET_AMBIG')
    assert r['status'] == 'MATCHED'
    assert r['is_ambiguous'] is True
    assert set(r['candidate_site_ids']) == {'SITE_001', 'SITE_002'}

