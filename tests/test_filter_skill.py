from job_identifier.filter import find_skill_matches, build_excerpt


def test_find_skill_matches_foundry_only():
    desc = "We use Palantir Foundry for our data platform."
    matches = find_skill_matches(desc, r"\b(Foundry|AIP)\b")
    assert matches == ["Foundry"]


def test_find_skill_matches_both():
    desc = "Foundry and AIP experience required."
    matches = find_skill_matches(desc, r"\b(Foundry|AIP)\b")
    assert set(matches) == {"Foundry", "AIP"}
    # Deterministic order:
    assert matches == sorted(matches)


def test_find_skill_matches_word_boundary():
    desc = "Foundryville Pizza and FoundryName Co."
    matches = find_skill_matches(desc, r"\b(Foundry|AIP)\b")
    assert matches == []


def test_find_skill_matches_case_insensitive():
    desc = "We need foundry experience and aip skills."
    matches = find_skill_matches(desc, r"\b(Foundry|AIP)\b")
    assert set(matches) == {"Foundry", "AIP"}


def test_build_excerpt_centers_on_first_match():
    desc = "A" * 300 + " Foundry " + "B" * 300
    excerpt = build_excerpt(desc, ["Foundry"], width=200)
    assert "Foundry" in excerpt
    assert len(excerpt) <= 200 + 10  # ~200 plus ellipsis padding


def test_build_excerpt_no_matches_returns_head():
    desc = "Lorem ipsum dolor sit amet, consectetur adipiscing elit."
    excerpt = build_excerpt(desc, [], width=20)
    assert excerpt.startswith("Lorem")
    assert len(excerpt) <= 25
