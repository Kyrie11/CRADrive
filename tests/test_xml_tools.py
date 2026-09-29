import tempfile
import unittest
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from cradrive.xml_tools import clone_single_route_tree, find_scenario, set_scenario_parameter, set_weather, write_tree


XML = """<?xml version='1.0'?>
<routes>
  <route id='1' town='Town01'>
    <weathers><weather route_percentage='0' cloudiness='10'/></weathers>
    <waypoints><position x='0' y='0' z='0'/><position x='10' y='0' z='0'/></waypoints>
    <scenarios>
      <scenario name='DynamicObjectCrossing_1' type='DynamicObjectCrossing'>
        <distance value='30'/><trigger_point x='5' y='0' z='0' yaw='0'/>
      </scenario>
    </scenarios>
  </route>
  <route id='2' town='Town02'><waypoints/><scenarios/></route>
</routes>
"""


class XMLToolsTest(unittest.TestCase):
    def test_clone_and_modify(self):
        with tempfile.TemporaryDirectory() as td:
            src = Path(td) / "src.xml"
            dst = Path(td) / "dst.xml"
            src.write_text(XML)
            tree, route = clone_single_route_tree(src, "1")
            s = find_scenario(route, "DynamicObjectCrossing", "DynamicObjectCrossing_1")
            set_scenario_parameter(s, "reaction_time", 1.5)
            set_weather(route, {"cloudiness": 90})
            write_tree(tree, dst)
            text = dst.read_text()
            self.assertIn('reaction_time value="1.5"', text)
            self.assertIn('cloudiness="90"', text)
            self.assertNotIn('id="2"', text)


if __name__ == "__main__":
    unittest.main()
