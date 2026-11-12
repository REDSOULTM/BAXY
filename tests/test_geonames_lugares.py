"""WEB1: el nomenclátor local se arma desde los volcados de GeoNames, igual byte a byte con las mismas entradas."""
from __future__ import annotations

import gzip
import importlib.util
import zipfile
from pathlib import Path

SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "datos" / "geonames_lugares.py"


def _load():
    spec = importlib.util.spec_from_file_location("geonames_lugares", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _row(ident, name, ascii_name, feature_class, code, cc, admin1, admin2, population, zone, lat="-33.03932", lon="-71.62725"):
    return "\t".join([str(ident), name, ascii_name, "", lat, lon, feature_class, code, cc, "", admin1, admin2, "", "",
                      str(population), "", "", zone, "2026-01-01"])


def _inputs(folder: Path) -> None:
    with zipfile.ZipFile(folder / "cities1000.zip", "w") as archive:
        archive.writestr("cities1000.txt", _row(3868626, "Valparaíso", "Valparaiso", "P", "PPLA", "CL", "01", "051",
                                                282448, "America/Santiago") + "\n")
    with zipfile.ZipFile(folder / "allCountries.zip", "w") as archive:
        archive.writestr("allCountries.txt", "\n".join([
            _row(3868621, "Valparaíso Region", "Valparaiso Region", "A", "ADM1", "CL", "01", "", 1790219, "America/Santiago"),
            _row(3895114, "Republic of Chile", "Republic of Chile", "A", "PCLI", "CL", "00", "", 19859921, ""),
            _row(3868600, "Some Hill", "Some Hill", "T", "HLL", "CL", "01", "", 0, "America/Santiago"),
        ]) + "\n")
    with zipfile.ZipFile(folder / "alternateNamesV2.zip", "w") as archive:
        archive.writestr("alternateNamesV2.txt", "\n".join([
            "1\t3868621\tes\tRegión de Valparaíso\t1\t\t\t\t\t",
            "2\t3868621\ten\tValparaiso\t\t\t\t\t\t",
            "3\t3895114\tes\tChile\t1\t\t\t\t\t",
            "4\t3895114\ten\tChile\t1\t1\t\t\t\t",
            "5\t3868626\tes\tValpo\t\t\t1\t\t\t",
            "6\t3868626\tes\tAncient Name\t\t\t\t1\t\t",
            "7\t3868623\tes\tProvincia de Valparaíso\t1\t\t\t\t\t",
        ]) + "\n")
    (folder / "admin1CodesASCII.txt").write_text("CL.01\tValparaiso\tValparaiso\t3868621\n", encoding="utf-8")
    (folder / "admin2Codes.txt").write_text("CL.01.051\tValparaiso Province\tValparaiso Province\t3868623\n",
                                            encoding="utf-8")


def test_the_places_their_names_and_their_divisions_are_kept_and_the_output_is_reproducible(tmp_path: Path) -> None:
    module = _load()
    _inputs(tmp_path)
    first, second = tmp_path / "a.tsv.gz", tmp_path / "b.tsv.gz"

    module.main(str(tmp_path), str(first))
    module.main(str(tmp_path), str(second))

    assert first.read_bytes() == second.read_bytes()
    lines = gzip.decompress(first.read_bytes()).decode("utf-8").splitlines()
    rows = {line.split("\t")[1]: line.split("\t") for line in lines if line.startswith("P\t")}
    assert "C\tCL\t3895114" in lines
    assert "N\t3868623\tProvincia de Valparaíso\tValparaiso Province" in lines
    assert set(rows) == {"3868626", "3868621", "3895114"}, "a hill is no place of the weather"
    city = rows["3868626"]
    assert city[2:12] == ["PPLA", "-33.0393", "-71.6273", "CL", "3868621", "3868623", "282448", "America/Santiago",
                          "Valparaíso", "Valparaíso"], "a colloquial or historic name is not its name"
    assert city[13] == "Valparaiso"
    assert rows["3868621"][10:13] == ["Región de Valparaíso", "Valparaiso", "Valparaíso Region"]
    assert rows["3895114"][6] == "" and rows["3895114"][9] == "", "a country has no region and, here, no zone"
    assert any("cities1000.zip sha256=" in line for line in lines if line.startswith("#"))


def test_a_division_people_name_as_a_town_is_a_place_unless_a_town_of_its_region_bears_its_name(tmp_path: Path) -> None:
    # WEB2 (2026-11-07): «¿qué temperatura hay en Las Condes?» → weather_place_not_found. Las comunas (ADM3) y los
    # municipios (ADM2 o ADM3) vienen casi siempre sin población y fuera de cities1000.
    module = _load()
    _inputs(tmp_path)
    divisions = [
        _row(8261428, "Comuna Alta", "Comuna Alta", "A", "ADM3", "CL", "01", "051", 0, "America/Santiago"),
        _row(8261500, "Valparaíso", "Valparaiso", "A", "ADM3", "CL", "01", "051", 296655, "America/Santiago"),
        _row(8261600, "Dos Veces", "Dos Veces", "A", "ADM2", "CL", "01", "052", 10, "America/Santiago"),
        _row(8261601, "Dos Veces", "Dos Veces", "A", "ADM3", "CL", "01", "052", 900, "America/Santiago"),
        _row(8261700, "Un Cerro", "Un Cerro", "T", "ADM3H", "CL", "01", "051", 0, "America/Santiago"),
        # A province named in Spanish as its only comuna, of the same population: the comuna is the place.
        _row(4030752, "Provincia de Isla Lejana", "Provincia de Isla Lejana", "A", "ADM2", "CL", "01", "053", 7750,
             "Pacific/Easter"),
        _row(8261466, "Isla Lejana", "Isla Lejana", "A", "ADM3", "CL", "01", "053", 7750, "Pacific/Easter"),
        # A name a better-known place of another region bears (a historic name of a large city, a region) is that
        # place's, not a small division's; a hamlet elsewhere is not better known than a comuna without population.
        _row(1275339, "Ciudad Grande", "Ciudad Grande", "P", "PPLA", "IN", "16", "", 12691836, "Asia/Kolkata"),
        _row(11495707, "Nombre Viejo", "Nombre Viejo", "A", "ADM2", "JM", "08", "", 1902, "America/Jamaica"),
        _row(1490624, "Region Fria", "Region Fria", "L", "RGN", "RU", "00", "", 0, ""),
        _row(11855799, "Region Fria", "Region Fria", "A", "ADM3", "PY", "07", "", 0, "America/Asuncion"),
        _row(3500000, "Comuna Alta", "Comuna Alta", "P", "PPL", "MX", "22", "", 40, "America/Mexico_City"),
    ]
    with zipfile.ZipFile(tmp_path / "allCountries.zip") as archive:
        base = archive.read("allCountries.txt").decode("utf-8")
    with zipfile.ZipFile(tmp_path / "allCountries.zip", "w") as archive:
        archive.writestr("allCountries.txt", base + "\n".join(divisions) + "\n")
    with zipfile.ZipFile(tmp_path / "alternateNamesV2.zip") as archive:
        names = archive.read("alternateNamesV2.txt").decode("utf-8")
    with zipfile.ZipFile(tmp_path / "alternateNamesV2.zip", "w") as archive:
        archive.writestr("alternateNamesV2.txt", names + "8\t4030752\tes\tIsla Lejana\t1\t\t\t\t\t\n"
                         + "9\t1275339\ten\tNombre Viejo\t\t\t\t1\t\t\n")
    output = tmp_path / "out.tsv.gz"

    module.main(str(tmp_path), str(output))

    lines = gzip.decompress(output.read_bytes()).decode("utf-8").splitlines()
    rows = {line.split("\t")[1]: line.split("\t") for line in lines if line.startswith("P\t")}
    assert rows["8261428"][2:8] == ["ADM3", "-33.0393", "-71.6273", "CL", "3868621", "3868623"], "a comuna is a place"
    assert "8261500" not in rows, "the comuna of a town of its name is that town"
    assert "8261601" in rows and "8261600" not in rows, "of two divisions of one name in a region, the most populated"
    assert "8261700" not in rows, "a historic division is not a place"
    assert "8261466" in rows and "4030752" not in rows, "a province named as its comuna is that comuna"
    assert "11495707" not in rows, "a historic name of a large city elsewhere is that city's"
    assert "11855799" not in rows, "a region's name elsewhere is that region's"
    assert "1275339" not in rows and "1490624" not in rows, "a better-known place is not added for it"
