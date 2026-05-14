from job_identifier.filter import classify_role_type, classify_seniority
from job_identifier.models import RoleType, Seniority


def test_role_type_engineering():
    assert classify_role_type("Senior Software Engineer", "...") == RoleType.ENGINEERING
    assert classify_role_type("Solutions Architect", "DevOps work") == RoleType.ENGINEERING


def test_role_type_data_ai():
    assert classify_role_type("Data Scientist", "...") == RoleType.DATA_AI
    assert classify_role_type("ML Engineer", "...") == RoleType.DATA_AI
    assert classify_role_type("Senior Data Engineer", "...") == RoleType.DATA_AI


def test_role_type_leadership():
    assert classify_role_type("Head of Data", "...") == RoleType.LEADERSHIP
    assert classify_role_type("VP Engineering", "...") == RoleType.LEADERSHIP
    assert classify_role_type("Director of Foundry", "...") == RoleType.LEADERSHIP


def test_role_type_business_ops():
    assert classify_role_type("Business Analyst", "...") == RoleType.BUSINESS_OPS
    assert classify_role_type("Operations Manager", "...") == RoleType.BUSINESS_OPS


def test_role_type_other_fallback():
    assert classify_role_type("Designer", "...") == RoleType.OTHER


def test_seniority_vp_plus():
    assert classify_seniority("VP of Data") == Seniority.VP_PLUS
    assert classify_seniority("Chief Data Officer") == Seniority.VP_PLUS


def test_seniority_director():
    assert classify_seniority("Director, Data Platform") == Seniority.DIRECTOR
    assert classify_seniority("Head of Engineering") == Seniority.DIRECTOR


def test_seniority_lead():
    assert classify_seniority("Lead Engineer") == Seniority.LEAD
    assert classify_seniority("Principal Architect") == Seniority.LEAD
    assert classify_seniority("Staff Engineer") == Seniority.LEAD


def test_seniority_senior_ic():
    assert classify_seniority("Senior Software Engineer") == Seniority.SENIOR_IC
    assert classify_seniority("Sr. Data Scientist") == Seniority.SENIOR_IC


def test_seniority_ic_fallback():
    assert classify_seniority("Software Engineer") == Seniority.IC
    assert classify_seniority("Data Analyst") == Seniority.IC
