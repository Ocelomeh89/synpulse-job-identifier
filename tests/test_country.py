from job_identifier.country import country_from_location


def test_us_locations():
    assert country_from_location("New York, NY") == "US"
    assert country_from_location("Chicago, IL") == "US"
    assert country_from_location("Remote, United States") == "US"


def test_canada_locations():
    assert country_from_location("Toronto, ON") == "CA"
    assert country_from_location("Vancouver, BC, Canada") == "CA"


def test_uk_locations():
    assert country_from_location("London, UK") == "GB"
    assert country_from_location("Manchester, England") == "GB"


def test_bermuda_locations():
    assert country_from_location("Hamilton, Bermuda") == "BM"


def test_mexico_locations():
    assert country_from_location("Ciudad de México, CDMX") == "MX"
    assert country_from_location("México, Mexico") == "MX"


def test_unknown_location_returns_xx():
    assert country_from_location("Atlantis") == "XX"
