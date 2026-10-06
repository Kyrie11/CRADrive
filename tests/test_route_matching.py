from pathlib import Path
from tools.check_matched import canonical


def test_canonical_ignores_only_cra_treatment(tmp_path: Path):
    a=tmp_path/"a.xml"; b=tmp_path/"b.xml"
    a.write_text('''<routes><route id="1"><scenarios><scenario name="x" type="PedestrianCrossing"><foo value="1"/></scenario></scenarios></route></routes>''')
    b.write_text('''<routes><route id="1"><scenarios><scenario name="y" type="CRAPedestrianCrossing"><foo value="1"/><cra_ped_yaw_offset value="90"/></scenario></scenarios></route></routes>''')
    assert canonical(a,"PedestrianCrossing")==canonical(b,"PedestrianCrossing")


def test_canonical_detects_non_treatment_change(tmp_path: Path):
    a=tmp_path/"a.xml"; b=tmp_path/"b.xml"
    a.write_text('''<routes><route id="1"><scenarios><scenario name="x" type="PedestrianCrossing"><foo value="1"/></scenario></scenarios></route></routes>''')
    b.write_text('''<routes><route id="1"><scenarios><scenario name="y" type="CRAPedestrianCrossing"><foo value="2"/><cra_ped_yaw_offset value="90"/></scenario></scenarios></route></routes>''')
    assert canonical(a,"PedestrianCrossing")!=canonical(b,"PedestrianCrossing")
