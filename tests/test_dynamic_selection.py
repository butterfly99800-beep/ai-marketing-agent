import unittest
from app.planning import require_dynamic_scene
from app.main import render_options,Confirm
class DynamicSelectionTests(unittest.TestCase):
 def test_opt_in_requires_actual_video(self):
  with self.assertRaisesRegex(ValueError,'至少1段'):require_dynamic_scene({'shots':[{'video':False}]},True)
 def test_no_budget_keeps_static(self):require_dynamic_scene({'shots':[{'video':False}]},False)
 def test_actual_video_satisfies_intent(self):require_dynamic_scene({'shots':[{'video':True}]},True)
 def test_dynamic_toggle_invalidates_completed_render_options(self):
  p={'video_budget':False}
  self.assertNotEqual(render_options(p),render_options(p,Confirm(revision=1,allow_video=True)))
