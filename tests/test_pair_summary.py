
import unittest
from ddinter_lookup import safety_categories

class PairSummaryTests(unittest.TestCase):
    def test_mixed_sources_same_pair_count_once(self):
        alerts=[{'first':'Co-trimoxazole','second':'Warfarin','finding_type':'ddinter_severity_only'},
                {'first':'warfarin','second':'CO-TRIMOXAZOLE','finding_type':'documented_interaction'}]
        result=safety_categories(alerts,[],[])
        self.assertEqual(result['documented_interactions'],1)
        self.assertFalse(result['no_documented_interactions'])
    def test_distinct_pairs_stay_distinct(self):
        alerts=[{'first':'Co-trimoxazole','second':'Warfarin','finding_type':'documented_interaction'},
                {'first':'Anarex','second':'Warfarin','finding_type':'documented_interaction'},
                {'first':'Co-trimoxazole','second':'Warfarin','finding_type':'duplicate_ingredient'}]
        result=safety_categories(alerts,[],[])
        self.assertEqual(result['documented_interactions'],2)
        self.assertEqual(result['duplicate_ingredients'],1)
if __name__=='__main__':unittest.main()
