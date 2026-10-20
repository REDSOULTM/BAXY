"""The cached prefix in tokens (the server's prompt_tokens at warm-up) of one mind copy and catalog under each
BAXY_AYUDAS setting, one llama-server for all. Usage: py prefijo.py <mind src> <catalog> <gguf> <server> <setting>..."""
import json, os, sys, tempfile
from pathlib import Path
src, catalog, gguf, server_exe, settings = sys.argv[1], sys.argv[2], sys.argv[3], sys.argv[4], sys.argv[5:]
sys.path.insert(0, src)
from baxy_mind.llm_server import LlmServer
from baxy_mind.mind import Mind
server = LlmServer(gguf, server_exe, context=49152, extra_args=[], log_name="prefijo.log")
server.start()
try:
    server.wait_ready(600)
    for setting in settings:
        os.environ["BAXY_AYUDAS"] = setting
        mind = Mind(server, Path(tempfile.mkdtemp()) / "t.jsonl")
        mind.configure(json.loads(Path(catalog).read_text(encoding="utf-8")))
        mind.warm()
        print(f"BAXY_AYUDAS={setting}: prefix {mind.prefix_tokens} tokens")
finally:
    server.close()
