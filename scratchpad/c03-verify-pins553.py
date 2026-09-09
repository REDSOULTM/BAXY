from pathlib import Path
import hashlib,json,subprocess
root=Path(__file__).resolve().parents[1]
base=Path('artifacts/comprobaciones/C03')
folders=['astra-coordinate-queries545','astra-e5-assets544','astra-coordinate-product546','astra-e5-backend547','astra-e5-retrieval549','astra-e5-avx2550','astra-e5-avx2551','astra-native-quantities552','astra-native-quantities553']
checked=0
bad=[]
for folder in folders:
    path=base/folder
    pins=json.loads((root/path/'PINS.json').read_text(encoding='utf-8'))
    for name,expected in pins.items():
        raw=subprocess.run(['git','show',':'+(path/name).as_posix()],cwd=root,capture_output=True,check=True).stdout
        checked+=1
        if hashlib.sha256(raw).hexdigest()!=expected:bad.append(str(path/name))
print({'staged_pins_checked':checked,'mismatches':bad})
assert not bad
