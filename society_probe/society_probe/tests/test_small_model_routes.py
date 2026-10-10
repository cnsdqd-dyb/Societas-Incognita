import copy
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from concurrent.futures import ThreadPoolExecutor

import sim
from hybrid_codex import router_class


class SmallModelRoutes(unittest.TestCase):
    def test_external_only_routes_keep_provider_schema_and_reasoning_independent(self):
        cfg=json.loads(Path('configs/cheap_small8_v4_20261009/M2_cheap_small8_p1.json').read_text('utf-8'))
        cfg['max_estimated_cost_usd']=1
        original=copy.deepcopy(cfg)
        catalog=json.loads(Path('reports/cheap_small_model_plan/model_catalog.json').read_text('utf-8'))
        captured=[]
        class Response:
            def __init__(self,value):self.value=value
            def __enter__(self):return self
            def __exit__(self,*args):pass
            def read(self,*args):return json.dumps(self.value).encode()
        def fake_open(request,**kwargs):
            if request.full_url.endswith('/models'):return Response(catalog)
            body=json.loads(request.data);captured.append(body)
            return Response({'id':'mock','choices':[{'message':{'content':'{"communication":{"op":"silent"}}'}}],'usage':{'cost':0}})
        class ForbiddenNative:
            def __init__(self,*args,**kwargs):raise AssertionError('Native backend must not be initialized')
        with tempfile.TemporaryDirectory() as d,patch.dict('os.environ',{'OPENROUTER_API_KEY':'test-placeholder'}),patch('urllib.request.urlopen',side_effect=fake_open):
            cls=router_class(sim.API,native_class=ForbiddenNative,external_only=True)
            api=cls(cfg,Path(d),mock=False)
            selected=['meta-llama/llama-3.1-8b-instruct','meta-llama/llama-3.2-3b-instruct','qwen/qwen3.5-9b']
            with ThreadPoolExecutor(max_workers=3) as pool:
                replies=list(pool.map(lambda mid:api.request(mid,'communicate','test',{'available_tools':[],'zones':[]},request_key=mid),selected))
            self.assertTrue(all(r=={'communication':{'op':'silent'}} for r in replies))
        for body in captured:
            route=cfg['model_routes'][body['model']]['parameters']
            self.assertEqual(body['provider']['only'],route['provider_only'])
            self.assertEqual(body['response_format']['type'],'json_schema' if route['structured_outputs'] else 'json_object')
            self.assertEqual(body.get('reasoning'),route.get('reasoning'))
        self.assertEqual(cfg,original)


if __name__=='__main__':unittest.main()
