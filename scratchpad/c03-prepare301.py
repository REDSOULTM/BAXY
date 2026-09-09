from pathlib import Path
root = Path(__file__).resolve().parents[1]
script=(root/'scratchpad/c03-product300.py').read_text(encoding='utf-8')
script=script.replace('300','301')
script=script.replace("str(private/'profile')", "str(private.parent/'C03-memory-profile301')")
script=script.replace("'criteria':'Serve", "'prior_failure':'300 never reached a turn: nested profile rejected by WindowsPrivateStorage direct-child policy.301 changes only profile location to an owned direct child of LOCALAPPDATA/BAXY; no product source/config change.',\n    'criteria':'Serve")
(root/'scratchpad/c03-product301.py').write_text(script,encoding='utf-8')
