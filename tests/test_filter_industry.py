from job_identifier.filter import matches_industry, is_denied, is_allowed


def test_industry_match_english():
    kw = ["insurance", "reinsurance"]
    assert matches_industry("Senior Engineer", "Acme Co", "We do insurance.", kw) is True
    assert matches_industry("Underwriting Analyst", "Re Co", "...", kw) is False


def test_industry_match_company_name():
    kw = ["insurance"]
    assert matches_industry("Engineer", "Acme Insurance", "Just code.", kw) is True


def test_industry_match_title():
    kw = ["insurance"]
    assert matches_industry("Senior Insurance Engineer", "Acme", "...", kw) is True


def test_industry_match_spanish():
    kw = ["seguros", "aseguradora"]
    assert matches_industry("Ingeniero", "Aseguradora MX", "Trabajamos en seguros.", kw) is True


def test_industry_no_match():
    kw = ["insurance"]
    assert matches_industry("Marketing", "Pets R Us", "We love pets.", kw) is False


def test_is_denied_exact():
    deny = ["Palantir Technologies", "Accenture"]
    assert is_denied("Palantir Technologies", deny) is True
    assert is_denied("Accenture", deny) is True
    assert is_denied("Acme Insurance", deny) is False


def test_is_denied_case_insensitive():
    deny = ["accenture"]
    assert is_denied("ACCENTURE", deny) is True


def test_is_allowed_substring_match():
    allow = ["Acrisure", "Munich Re"]
    # Exact match
    assert is_allowed("Acrisure", allow) is True
    # Substring match (suffix common on legal entity names)
    assert is_allowed("Acrisure Technology Group, LLC", allow) is True
    # Case insensitive
    assert is_allowed("MUNICH RE AMERICA SERVICES", allow) is True
    # Non-target company is not allowed
    assert is_allowed("Random Tech Inc", allow) is False


def test_is_allowed_empty_list_returns_false():
    assert is_allowed("Anyone", []) is False
