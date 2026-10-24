"""Pure SOURCE fixtures; not run by author and not added to the 66 outer contracts."""
from pathlib import Path
import ast,copy,unittest
SOURCE=Path(__file__).with_name('prepare_binding.py')
def helper():
    tree=ast.parse(SOURCE.read_text('utf-8'))
    nodes=[n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name in {'need','class_cut_protection'}]
    assert len(nodes)==2
    scope={};exec(compile(ast.Module(body=nodes,type_ignores=[]),str(SOURCE),'exec'),scope)
    return scope['class_cut_protection']
class ClassCutProtectionContracts(unittest.TestCase):
    def diagnostic(self,phase='primary'):
        return dict(phase=phase,metric='macro_f1',split_file_sha256='a'*64,feature_groups_disjoint=True,
            independent_fitting_groups={'first':7,'second':7,'third':100},rarest_fitting_class='first')
    def test_exact_two_fields_are_copied_from_same_phase_split_and_canonical_tie(self):
        fn=helper();classes=['first','second','third']
        for phase in ('primary','confirmation'):
            d=self.diagnostic(phase);before=copy.deepcopy(d);value=fn(d,classes,phase,'a'*64)
            self.assertEqual(value,{'independent_fitting_groups':d['independent_fitting_groups'],'rarest_fitting_class':'first'})
            self.assertEqual(d,before);value['independent_fitting_groups']['first']=99
            self.assertEqual(d['independent_fitting_groups']['first'],7)
        source=SOURCE.read_text('utf-8');self.assertIn("if kind=='classification':cut.update(class_cut_protection",source)
    def test_missing_malformed_different_cut_or_wrong_rarest_never_defaults(self):
        fn=helper();classes=['first','second','third']
        for mode in ('missing','negative','bool','float','tie','phase','split','disjoint'):
            d=self.diagnostic()
            if mode=='missing':del d['independent_fitting_groups']['third']
            elif mode=='negative':d['independent_fitting_groups']['third']=-1
            elif mode=='bool':d['independent_fitting_groups']['third']=True
            elif mode=='float':d['independent_fitting_groups']['third']=100.0
            elif mode=='tie':d['rarest_fitting_class']='second'
            elif mode=='phase':d['phase']='confirmation'
            elif mode=='split':d['split_file_sha256']='b'*64
            else:d['feature_groups_disjoint']=False
            with self.subTest(mode=mode),self.assertRaises(RuntimeError):fn(d,classes,'primary','a'*64)
if __name__=='__main__':unittest.main(verbosity=2)
