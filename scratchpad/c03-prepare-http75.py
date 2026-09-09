from pathlib import Path
import json
import os
import sys

root = Path(__file__).resolve().parents[1]
base = root / 'artifacts/comprobaciones/C03'
old_name = 'files74-veto'
new_name = sys.argv[1] if len(sys.argv) > 1 else 'files75-http'
assert new_name in {'files75-http', 'files77-template', 'files78-roles', 'files81-nominal', 'files83-empty', 'files84-emptycause', 'files86-negation', 'files92-context'}
hook = 'c03-wire-hook75' if new_name == 'files75-http' else 'c03-wire-hook77'
out = base / ('astra-' + new_name)
out.mkdir(exist_ok=False)
old_profile = Path(os.environ['LOCALAPPDATA']) / ('BAXY/comprobaciones-c03-' + old_name)
profile = old_profile.with_name('comprobaciones-c03-' + new_name)
sandbox = profile / 'filesystem-sandbox'
sandbox.mkdir(parents=True, exist_ok=False)
cases = json.loads((base / ('astra-' + old_name) / 'CASES.json').read_text(encoding='utf-8'))
for name in ('c03-lectura.txt', 'c03-invalid-utf8.txt', 'c03-sombra.txt'):
    (sandbox / name).write_bytes((old_profile / 'filesystem-sandbox' / name).read_bytes())
cases = json.loads(json.dumps(cases).replace(str(old_profile).replace('\\', '\\\\'), str(profile).replace('\\', '\\\\')))
if new_name in {'files83-empty', 'files84-emptycause', 'files86-negation', 'files92-context'}:
    assert not (sandbox / 'c03-ausente.txt').exists()
    cases['texts'] = [
        'Lee el archivo "c03-ausente.txt" del sandbox.',
        "Why couldn't you read that file?",
        'Lee el contenido del archivo "c03-lectura.txt" del sandbox.',
        'Dime la hora.',
    ]
    cases['expectations'] = [
        'Explain a verified empty search within the requested sandbox, without claiming global absence or generic inability.',
        'Explain the preceding actual failure without a new read.',
        'Recover and read the exact real UTF8 fixture in the same process.',
        'Recover with a verified clock reading.',
    ]
    cases['absentSandboxPath'] = str(sandbox / 'c03-ausente.txt')
(out / 'CASES.json').write_text(json.dumps(cases, ensure_ascii=False, indent=2), encoding='utf-8')
out.with_suffix('.turns.jsonl').write_text(''.join(json.dumps({'cmd': 'turn', 'text': t}, ensure_ascii=False) + '\n' for t in cases['texts']), encoding='utf-8')
driver = (root / ('scratchpad/c03-' + old_name + '.py')).read_text(encoding='utf-8').replace(old_name, new_name).replace('c03-wire-hook47', hook)
start = driver.index("prereg['method'] =")
end = driver.index('\n', start)
method = ('Same source74/model override/ten requests and fixtures. Diagnostic hook75 additionally records HTTPError '
          'status and existing io.BytesIO body by getvalue, without consuming it or altering the request/response/error. '
          '72/74 t6/t7 fail at conversation_reply with HTTPError; t10 fails at turn_preparation. '
          'The prior hook logged only successes, so no rejected payload was captured. Find the first server rejection cause. '
          'No new source change, registry promotion, UI/audio or human acceptance. No volume level supplied; no mutation requested.')
if new_name == 'files77-template':
    method = ('Source74 plus runtime77 serializes only leading system messages into one prefix, retaining text/order, '
              'dialogue and every other payload field. No model/prompt/history/selector changes. Same ten technical inputs '
              'and Qwen3.5 isolated override as74/75. Native76 fixes9/9 server rejections; registered2507 main replies preserved. '
              'Hook77 observes post_chat_completion after serialization, including HTTP errors without consuming bodies. '
              'Record useful final/progress, failures and resources. No UI/audio/human reserve or model promotion.')
if new_name == 'files78-roles':
    method = ('Source77 plus78: use the classified clarification role for the existing invitation guard while preserving '
              'its family-coverage checks; knowledge conversation can explain an earlier failure without reversing a new '
              'operation outcome. Same controls and Qwen3.5 override as77. No extra prompt, catalog, selector or history change. '
              '77 publishes7/10 useful; why answer was vetoed as failure and the correct volume-level question was vetoed '
              'as unsolicited_catalog. Those exact drafts drive owner tests. Record all turns; t9 partial recognition remains '
              'unrepaired. No audio value supplied, actual volume mutation, model promotion, UI/audio or human reserve claim.')
if new_name == 'files81-nominal':
    method = ('Source78 plus81: extend the existing whole-clause coordinated status grammar to bare domain nouns and '
              'CPU usage/uso de CPU, and split all comma/conjunction items only after that complete grammar matches. '
              'Preserve the governing observation verb, requested order and catalog completeness. No new selector/prompt/model '
              'or history layer. Same ten technical controls and isolated Qwen3.5 override as78 (9/10 useful, t9 partial audio only). '
              '79 used an inapplicable file shortlist;80 isolated the three actual observation leaves and reproduced the early '
              'strict return. Unit controls cover missing leaves and an unknown extra segment. No UI/audio/human reserve or promotion.')
if new_name == 'files83-empty':
    method = ('Source81 unchanged; isolated Qwen3.5 override remains unpromoted. Four technical readonly controls: '
              'missing named file inside the sandbox, why question, a real readable file and clock recovery. '
              'A filename search returning0 differs from the unsupported absolute path already solved. No files are deleted '
              'to manufacture absence; this isolated profile contains only the listed hashed fixtures. No fabricated '
              'provider answers, model/prompt/history changes, UI/audio or human reserve claim. Judge facts and complete turns.')
if new_name == 'files84-emptycause':
    method = ('Source81 plus84: reuse the verified identity-producer projection to distinguish an explicit zero-result '
              'sandbox file search/list from missing or unverified data. MindPlanSession stops the dependent read with '
              'file_search_no_matches before requesting an impossible identity from the model. No provider/catalog/model '
              'or prompt change, no basename substitution or global absence claim. Same four readonly inputs/fixtures and '
              'Qwen3.5 isolated override as83 (2/4 useful, cause lost to step_data_missing). No UI/audio/human reserve or promotion.')
if new_name == 'files86-negation':
    method = ('Source84 plus86: the existing Python/C# failure-polarity checks recognize Spanish negative '
              'result forms with omitted/impersonal subjects, while removing only negated failures before '
              'testing independent failure assertions. No new prompt, model, selector, history or provider change. '
              'Same four readonly requests/fixtures and Qwen3.5 isolated override as84 (2/4 useful; faithful '
              'empty-search drafts vetoed, next why answer invented encryption). Record all outcomes. '
              'No UI/audio/human reserve or model promotion.')
if new_name == 'files92-context':
    method = ('Source86 plus92: preserve the existing bounded previous published answer as situation.previousResponse '
              'data for conversation recovery, not an assistant turn. User-supplied identifier vocabulary includes '
              'priorRequests in Python/C#; this does not change current intent or exempt identifiers from assistant '
              'context alone. Native89/91 recovers cause and latency, preserves arithmetic/checksum. Same four '
              'readonly controls and Qwen3.5 override as86 (3/4 useful; fallback lost context and invented encryption). '
              'No progress changes, model/prompt/provider/selector change, UI/audio/reserve or promotion.')
driver = driver[:start] + "prereg['method'] = " + repr(method) + driver[end:]
if new_name in {'files86-negation', 'files92-context'}:
    driver = driver.replace("prereg['wireMethod']='Ten technical requests; hook47 records actual unchanged packets for inherited model override. See method for the five-case prefix and transfer cases.'",
        "prereg['wireMethod']='Four readonly technical requests from84; hook77 records actual HTTP payloads after system-prefix serialization without changing them.'")
(root / ('scratchpad/c03-' + new_name + '.py')).write_text(driver, encoding='utf-8')
print(f'Prepared {new_name}; not executed.')
