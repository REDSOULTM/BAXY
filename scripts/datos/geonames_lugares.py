"""Arma el nomenclátor local de BAXY (src/Baxy.Providers.Windows/Data/geonames_places.v1.tsv.gz) desde GeoNames.

WEB1 (2026-11-07): el clima y la hora de otro lugar preguntaban el nombre del lugar al geocodificador gratuito de
Open-Meteo, cuyo uso gratuito es «only ... for non-commercial purposes» (https://open-meteo.com/en/terms). Los datos de
ese geocodificador son los de GeoNames, que se publican para descargar bajo CC BY 4.0
(https://download.geonames.org/export/dump/readme.txt): BAXY los lleva dentro y el nombre del lugar ya no sale del PC.

Entra lo que un lugar nombrado puede ser: los poblados de más de 1000 habitantes o cabeceras (cities1000), las regiones
de primer orden (ADM1) y los países (PCL*, TERR); de las provincias (ADM2) sólo sus nombres, para «Lugar, Provincia».
WEB2 (2026-11-07): también las divisiones de segundo y tercer orden (ADM2, ADM3: comunas, municipios, distritos), que
la gente nombra como a un pueblo y GeoNames da casi siempre sin población, fuera de cities1000 («las comunas de
Santiago»). Una división que se llama como un poblado de su misma región es ese poblado y no entra; de las divisiones
de una región que se llaman igual, entra la más poblada.
Cada lugar lleva su nombre en español y en inglés como los da GeoNames (el preferido de la lengua, si no el corto, si no
el primero, si no el nombre principal), su nombre principal y su forma ASCII, coordenadas con 4 decimales, país,
región, provincia, población y zona horaria IANA. Los nombres históricos o coloquiales no entran.

    py -3.12 -X utf8 -I scripts/datos/geonames_lugares.py <carpeta con las descargas> <salida .tsv.gz>

La carpeta tiene (o se bajan allí) cities1000.zip, allCountries.zip, alternateNamesV2.zip, admin1CodesASCII.txt y
admin2Codes.txt de https://download.geonames.org/export/dump/. El fichero sale igual byte a byte con las mismas
entradas (gzip sin fecha), y su cabecera dice el SHA-256 de cada una.
"""

import gzip
import hashlib
import io
import os
import sys
import unicodedata
import urllib.request
import zipfile

DUMP = "https://download.geonames.org/export/dump/"
INPUTS = ["cities1000.zip", "allCountries.zip", "alternateNamesV2.zip", "admin1CodesASCII.txt", "admin2Codes.txt"]
COUNTRY_CODES = {"PCLI", "PCLD", "PCLF", "PCLS", "PCL", "PCLIX", "TERR"}
# Un país con varias entradas (PCLI y un territorio) se nombra por la primera de esta lista.
COUNTRY_ORDER = ["PCLI", "PCLD", "PCLF", "PCLS", "PCL", "PCLIX", "TERR"]
DIVISION_CODES = {"ADM2", "ADM3"}
# Lo que se conoce por su nombre más que una división: una región, un país o un continente.
KNOWN_AREAS = {"ADM1", "RGN", "RGNE", "CONT"} | COUNTRY_CODES
KNOWN_TOWN = 1000


def fold(text: str) -> str:
    """Mayúsculas, tildes y puntuación plegadas, como GeoNamesGazetteer.Fold."""
    decomposed = unicodedata.normalize("NFD", text)
    kept = "".join(" " if not c.isalnum() else c.lower() for c in decomposed if unicodedata.category(c) != "Mn")
    return " ".join(kept.split())


def fetch(folder: str, name: str) -> str:
    path = os.path.join(folder, name)
    if not os.path.exists(path):
        request = urllib.request.Request(DUMP + name, headers={"User-Agent": "BAXY geonames_lugares.py"})
        with urllib.request.urlopen(request, timeout=600) as response, open(path + ".part", "wb") as out:
            while chunk := response.read(1 << 20):
                out.write(chunk)
        os.replace(path + ".part", path)
    return path


def sha256(path: str) -> str:
    digest = hashlib.sha256()
    with open(path, "rb") as source:
        while chunk := source.read(1 << 20):
            digest.update(chunk)
    return digest.hexdigest()


def zipped_lines(path: str, member: str):
    with zipfile.ZipFile(path) as archive, archive.open(member) as raw:
        yield from io.TextIOWrapper(raw, encoding="utf-8")


def clean(text: str) -> str:
    return " ".join(text.replace("\t", " ").split())


def main(folder: str, output: str) -> None:
    paths = {name: fetch(folder, name) for name in INPUTS}

    places: dict[int, list[str]] = {}
    for line in zipped_lines(paths["cities1000.zip"], "cities1000.txt"):
        row = line.rstrip("\n").split("\t")
        places[int(row[0])] = row
    countries: dict[str, tuple[int, int]] = {}
    divisions: dict[int, list[str]] = {}
    # Los lugares más conocidos que una división (un poblado de 1000 habitantes o más, como los de cities1000, una
    # región, un país): su país, su región y su peso (su población; una región, un país o un continente pesan más que
    # cualquier división), y cada uno de sus nombres, también los históricos y los coloquiales («Bombay» es Mumbai).
    # GeoNames da casi todas las comunas sin población: un caserío de 40 habitantes no es más conocido que ellas.
    known: dict[int, tuple[str, str, float]] = {}
    known_names: dict[str, list[tuple[str, str, float]]] = {}

    def know(ident: int, spelling: str) -> None:
        if ident in known and (name := fold(spelling)):
            known_names.setdefault(name, []).append(known[ident])

    for line in zipped_lines(paths["allCountries.zip"], "allCountries.txt"):
        row = line.rstrip("\n").split("\t")
        if row[7] in KNOWN_AREAS or (row[6] == "P" and int(row[14] or 0) >= KNOWN_TOWN):
            known[int(row[0])] = (row[8], row[10], float("inf") if row[7] in KNOWN_AREAS else float(row[14]))
            know(int(row[0]), row[1])
            know(int(row[0]), row[2])
        if row[7] == "ADM1" or row[7] in COUNTRY_CODES:
            places[int(row[0])] = row
            if row[7] in COUNTRY_CODES and row[8]:
                rank = COUNTRY_ORDER.index(row[7])
                if row[8] not in countries or rank < countries[row[8]][1]:
                    countries[row[8]] = (int(row[0]), rank)
        elif row[7] in DIVISION_CODES:
            divisions[int(row[0])] = row

    admin1: dict[str, int] = {}
    with open(paths["admin1CodesASCII.txt"], encoding="utf-8") as source:
        for line in source:
            code, _name, _ascii, ident = line.rstrip("\n").split("\t")
            admin1[code] = int(ident)
    admin2: dict[str, tuple[int, str]] = {}
    with open(paths["admin2Codes.txt"], encoding="utf-8") as source:
        for line in source:
            code, name, _ascii, ident = line.rstrip("\n").split("\t")
            admin2[code] = (int(ident), name)

    names: dict[int, dict[str, list[tuple[int, str]]]] = {}
    wanted = set(places) | set(divisions) | {ident for ident, _name in admin2.values()}
    for order, line in enumerate(zipped_lines(paths["alternateNamesV2.zip"], "alternateNamesV2.txt")):
        row = line.rstrip("\n").split("\t")
        ident = int(row[1])
        if row[2] in ("es", "en"):
            know(ident, row[3])
        if ident not in wanted or row[2] not in ("es", "en") or row[6] == "1" or row[7] == "1":
            continue
        # El preferido de la lengua primero, luego el corto, luego el orden del fichero.
        rank = (0 if row[4] == "1" else 2) + (0 if row[5] == "1" else 1)
        names.setdefault(ident, {}).setdefault(row[2], []).append((rank * 100_000_000 + order, clean(row[3])))

    def display(ident: int, language: str, fallback: str) -> str:
        found = sorted(names.get(ident, {}).get(language, []))
        return found[0][1] if found else fallback

    def spelled(ident: int, row: list[str]) -> set[tuple[str, str, str]]:
        """Cada nombre por el que se encuentra el lugar, con su país y su región."""
        main_name = clean(row[1])
        forms = (display(ident, "es", main_name), display(ident, "en", main_name), main_name, clean(row[2]))
        return {(row[8], row[10], fold(form)) for form in forms if fold(form)}

    # Una división que se llama como un poblado de su región es ese poblado. De las divisiones de una región que se
    # llaman igual, entra la más poblada (a igual población, la de tercer orden, que es la más cercana al lugar). Una
    # división no es lo que un nombre quiere decir si lo lleva un lugar más conocido de otra región: con «Bombay» se
    # leía una parroquia de Jamaica, y con «Siberia» un distrito de Paraguay (held-out WEB2 w2-12, w2-46).
    towns = set().union(*(spelled(ident, row) for ident, row in places.items() if row[6] == "P"))
    taken: set[tuple[str, str, str]] = set()

    def better_known(spellings: set[tuple[str, str, str]], people: float) -> bool:
        return any((cc, a1) != (where_cc, where_a1) and weight > people
                   for where_cc, where_a1, name in spellings for cc, a1, weight in known_names.get(name, ()))

    for row in sorted(divisions.values(), key=lambda row: (-int(row[14] or 0), row[7] != "ADM3", int(row[0]))):
        spellings = spelled(int(row[0]), row)
        if spellings & towns or spellings & taken or better_known(spellings, float(row[14] or 0)):
            continue
        taken |= spellings
        places[int(row[0])] = row

    place_admins: dict[int, tuple[int | None, int | None]] = {}
    used_admin2: dict[int, str] = {}
    for ident, row in places.items():
        cc, a1, a2 = row[8], row[10], row[11]
        first = ident if row[7] == "ADM1" else admin1.get(f"{cc}.{a1}") if cc and a1 else None
        second = admin2.get(f"{cc}.{a1}.{a2}") if cc and a1 and a2 and row[7] not in COUNTRY_CODES else None
        if second is not None:
            used_admin2[second[0]] = second[1]
        if row[7] in COUNTRY_CODES:
            first = None
        place_admins[ident] = (first if first in places else None, second[0] if second else None)

    lines = [
        "# Lugares de GeoNames (https://www.geonames.org/), CC BY 4.0 (https://creativecommons.org/licenses/by/4.0/).",
        "# Modificado por BAXY: seleccion de campos y de nombres, coordenadas a 4 decimales (scripts/datos/geonames_lugares.py).",
        "# Entradas: " + ", ".join(f"{name} sha256={sha256(paths[name])}" for name in INPUTS),
        "# C pais lugar | N id nombre_es nombre_en | "
        "P id clase lat lon pais region provincia poblacion zona nombre_es nombre_en nombre ascii",
    ]
    for cc in sorted(countries):
        lines.append(f"C\t{cc}\t{countries[cc][0]}")
    for ident in sorted(used_admin2):
        name = clean(used_admin2[ident])
        lines.append(f"N\t{ident}\t{display(ident, 'es', name)}\t{display(ident, 'en', name)}")
    for ident in sorted(places):
        row = places[ident]
        main_name, ascii_name = clean(row[1]), clean(row[2])
        es, en = display(ident, "es", main_name), display(ident, "en", main_name)
        first, second = place_admins[ident]
        lines.append("\t".join([
            "P", str(ident), row[7], f"{float(row[4]):.4f}", f"{float(row[5]):.4f}", row[8],
            str(first or ""), str(second or ""), row[14] or "0", row[17], es, en,
            "" if main_name in (es, en) else main_name,
            "" if ascii_name in (es, en, main_name) else ascii_name,
        ]))
    data = ("\n".join(lines) + "\n").encode("utf-8")
    with open(output, "wb") as out:
        out.write(gzip.compress(data, compresslevel=9, mtime=0))
    print(f"{len(places)} lugares, {len(countries)} paises, {len(used_admin2)} provincias, "
          f"{len(data)} bytes, {os.path.getsize(output)} comprimidos -> {output}")


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2])
