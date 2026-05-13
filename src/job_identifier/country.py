US_STATE_ABBREVS = {
    "AL","AK","AZ","AR","CA","CO","CT","DE","FL","GA","HI","ID","IL","IN","IA","KS",
    "KY","LA","ME","MD","MA","MI","MN","MS","MO","MT","NE","NV","NH","NJ","NM","NY",
    "NC","ND","OH","OK","OR","PA","RI","SC","SD","TN","TX","UT","VT","VA","WA","WV",
    "WI","WY","DC",
}
CA_PROVINCE_ABBREVS = {"ON","QC","BC","AB","MB","SK","NS","NB","NL","PE","NT","YT","NU"}


def country_from_location(loc: str) -> str:
    s = loc.lower()
    if "bermuda" in s:
        return "BM"
    if any(t in s for t in ("united kingdom", "england", "scotland", "wales", "uk", ", uk")):
        return "GB"
    if any(t in s for t in ("canada", "canadá")):
        return "CA"
    if any(t in s for t in ("mexico", "méxico", "cdmx")):
        return "MX"
    if "united states" in s or "usa" in s or ", us" in s:
        return "US"

    parts = [p.strip().upper() for p in loc.split(",")]
    for p in parts:
        if p in CA_PROVINCE_ABBREVS:
            return "CA"
        if p in US_STATE_ABBREVS:
            return "US"
    return "XX"
