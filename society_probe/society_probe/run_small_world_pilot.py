"""Run/resume one frozen, certified pilot with durable shared budget."""
import argparse
import hashlib
import json
import os
import sys
from pathlib import Path


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root',default='runs/mini_world_pilot_20261010')
    parser.add_argument('--pressure',type=int,choices=(0,1),required=True)
    parser.add_argument('--api-key-file',default='../api_key')
    args=parser.parse_args(); root=Path(args.root).resolve()
    manifest=json.loads((root/'manifest.json').read_text('utf-8'))
    if manifest.get('exclude_from_research_analysis'):
        raise ValueError('This pilot failed interface acceptance; historical traces are preserved. Prepare a separate corrected pilot rather than resume it.')
    os.environ['PATH']=str(Path(manifest['lean_executable']).parent)+os.pathsep+os.environ.get('PATH','')
    sys.path.insert(0,str(root/'engine_snapshot'))
    import sim
    sim.load_api_key(args.api_key_file)
    folder=root/f'p{args.pressure}_hidden'; cfg=json.loads((folder/'config.json').read_text('utf-8'))
    output=folder/'simulation'
    original_urlopen=sim.urllib.request.urlopen
    def diagnostic_urlopen(*arguments,**keywords):
        request=arguments[0] if arguments else None
        if isinstance(request,sim.urllib.request.Request) and request.data and request.full_url.endswith('/chat/completions'):
            body=json.loads(request.data)
            format_spec=body.get('response_format',{})
            if format_spec.get('type')=='json_schema' and format_spec.get('json_schema',{}).get('name')=='act':
                # Mistral accepts the dialogue schema but rejects this compound
                # action grammar (HTTP 400, provider code 3051). Keep actor input,
                # model, provider and simulator validation unchanged; relax only
                # remote grammar enforcement. This is an explicit audited override.
                from provider_schema import mistral_transport_schema
                body['response_format']['json_schema']['schema']=mistral_transport_schema(format_spec['json_schema']['schema'])
                request.data=json.dumps(body).encode()
                record={'kind':'act','from':'json_schema','to':'json_schema_structure_preserved_bounds_projected',
                    'reason':'Mistral compound action schema rejected with code 3051',
                    'wire_body_sha256':hashlib.sha256(request.data).hexdigest(),
                    'adapter_sha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest()}
                with (output/'transport_overrides.jsonl').open('a',encoding='utf-8') as handle:
                    handle.write(json.dumps(record)+'\n')
        try: return original_urlopen(*arguments,**keywords)
        except sim.urllib.error.HTTPError as error:
            try: message=json.loads(error.read().decode('utf-8')).get('error',{})
            except (ValueError,UnicodeError): message={'message':'Unparseable HTTP error body'}
            record={'code':error.code,'error':message,'adapter_sha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest()}
            text=json.dumps(record,ensure_ascii=False).replace(os.environ.get('OPENROUTER_API_KEY','UNSET_SECRET'),'[REDACTED]')
            with (output/'http_errors.jsonl').open('a',encoding='utf-8') as handle: handle.write(text+'\n')
            raise
    sim.urllib.request.urlopen=diagnostic_urlopen
    sim.run(cfg,output,mock=False,resume=(output/'checkpoint.json').exists())


if __name__=='__main__': main()
