"""Future no-fit fixed-point contract for the actual saved recipe/control.
This validates recipe identity on a synthetic compatible schema, not task data
or predictions. A future full agent audit must still verify actual fitting scope.
"""
from pathlib import Path
import hashlib,json,sys,unittest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'src'))
from automl.search.policy import normalize,portfolio,signature
from automl.search.stages import load_champion_recipe,prepare_preserved_four_stage_recipes

class PinnedChampionSeedContracts(unittest.TestCase):
    def test_saved_champion_fixed_point_and_exact_control_anchor(self):
        root=Path(__file__).resolve().parent/'fixtures/champion_seed'
        source=root/'champion.json';control_path=root/'protected_control.json'
        before=source.read_bytes();control_bytes=control_path.read_bytes()
        self.assertEqual(hashlib.sha256(before).hexdigest(),
            '914880505ed751da9fd0a38d7f1724dd860c20d98456ff3efd16a195a0709ad4')
        self.assertEqual(hashlib.sha256(control_bytes).hexdigest(),
            '0480d5e60c6aa42be4a78e300c3baf7a0346d431707ce79cb6850c73d84adf1b')
        spec=dict(kind='regression',metric='rmse',greater_is_better=False,
            features=['category','value','period'],categorical_features=['category'],
            text_features=[],time_column='period')
        champion,receipt=load_champion_recipe(source,spec)
        original=json.loads(before)
        self.assertEqual(champion,original)
        self.assertEqual(normalize(normalize(champion)),champion)
        expected='959a9b8fed203d71bafbbd4770b6bfb5b6aa5da79d08ee568b93979d7f795421'
        self.assertEqual(signature(champion),expected)
        self.assertEqual(receipt['recipe_signature'],expected)
        control=json.loads(control_bytes)
        self.assertEqual(signature(control),'773dfb566afd9b2ad6c47853ffaa6898392c009fd41c9202d89184b3c50ceb9e')
        anchor_key='2fc0e515e31ac01c2557cb4f9b255ac81a99478c33810021ef5f02ebf7a47b79'
        self.assertEqual(signature(control['components'][0]),anchor_key)
        baseline=prepare_preserved_four_stage_recipes(spec,portfolio(spec),[],control)
        seeded=prepare_preserved_four_stage_recipes(spec,portfolio(spec),[],control,champion=champion)
        self.assertEqual(baseline[0],seeded[0][:5])
        self.assertEqual(baseline[2],seeded[2])
        self.assertEqual(signature(seeded[2]),anchor_key)
        self.assertEqual(signature(seeded[0][5]),expected)
        self.assertEqual(source.read_bytes(),before)
        self.assertEqual(control_path.read_bytes(),control_bytes)

if __name__=='__main__':unittest.main(verbosity=2)
