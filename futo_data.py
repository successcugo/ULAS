"""
futo_data.py — FUTO schools, departments and level counts.

Structure is stored live in ULASDATA at data/structure.json so ICT can
add/edit/delete schools, departments and levels without a code deploy.
The hardcoded SEED below is used only to initialise the file if it does
not yet exist in ULASDATA.
"""
from __future__ import annotations

_SEED: dict[str, dict[str, int]] = {
    "School of Agriculture and Agricultural Technology (SAAT)": {
        "Agribusiness": 4, "Agricultural Economics": 4, "Agricultural Extension": 4,
        "Animal Science and Technology": 4, "Crop Science and Technology": 4,
        "Fisheries and Aquaculture Technology": 4, "Forestry and Wildlife Technology": 4,
        "Soil Science and Technology": 4,
    },
    "School of Basic Medical Science (SBMS)": {
        "Human Anatomy": 5, "Human Physiology": 5,
    },
    "School of Biological Science (SOBS)": {
        "Biochemistry": 4, "Biology": 4, "Biotechnology": 4,
        "Microbiology": 4, "Forensic Science": 4,
    },
    "School of Engineering and Engineering Technology (SEET)": {
        "Agricultural and Bioresources Engineering": 5, "Biomedical Engineering": 5,
        "Chemical Engineering": 5, "Civil Engineering": 5, "Food Science and Technology": 4,
        "Material and Metallurgical Engineering": 5, "Mechanical Engineering": 5,
        "Petroleum Engineering": 5, "Polymer and Textile Engineering": 5,
    },
    "School of Electrical Systems and Engineering Technology (SESET)": {
        "Computer Engineering": 5, "Electrical (Power Systems) Engineering": 5,
        "Electronics Engineering": 5, "Mechatronics Engineering": 5,
        "Telecommunications Engineering": 5, "Electrical and Electronic Engineering": 5,
    },
    "School of Environmental Science (SOES)": {
        "Architecture": 5, "Building Technology": 5, "Environmental Management": 4,
        "Quantity Surveying": 5, "Surveying and Geoinformatics": 5,
        "Urban and Regional Planning": 5, "Environmental Management and Evaluation": 4,
    },
    "School of Health Technology (SOHT)": {
        "Dental Technology": 4, "Environmental Health Science": 4,
        "Optometry": 5, "Prosthetics and Orthotics": 4, "Public Health Technology": 4,
    },
    "School of Information and Communication Technology (SICT)": {
        "Computer Science": 4, "Cyber Security": 4,
        "Information Technology": 4, "Software Engineering": 4,
    },
    "School of Logistics and Innovation Technology (SLIT)": {
        "Entrepreneurship and Innovation": 4, "Logistics and Transport Technology": 4,
        "Maritime Technology and Logistics": 4, "Supply Chain Management": 4,
        "Project Management Technology": 4,
    },
    "School of Physical Science (SOPS)": {
        "Chemistry": 4, "Geology": 4, "Mathematics": 4,
        "Physics": 4, "Science Laboratory Technology": 4, "Statistics": 4,
    },
}

_SEED_ABBR: dict[str, str] = {
    "School of Agriculture and Agricultural Technology (SAAT)": "SAAT",
    "School of Basic Medical Science (SBMS)":                   "SBMS",
    "School of Biological Science (SOBS)":                      "SOBS",
    "School of Engineering and Engineering Technology (SEET)":  "SEET",
    "School of Electrical Systems and Engineering Technology (SESET)": "SESET",
    "School of Environmental Science (SOES)":                   "SOES",
    "School of Health Technology (SOHT)":                       "SOHT",
    "School of Information and Communication Technology (SICT)":"SICT",
    "School of Logistics and Innovation Technology (SLIT)":     "SLIT",
    "School of Physical Science (SOPS)":                        "SOPS",
}

_cache: dict | None = None


def _get() -> dict:
    global _cache
    if _cache is not None:
        return _cache
    try:
        from github_store import read_json, write_json
        data, _ = read_json("data/structure.json")
        if data and "schools" in data:
            _cache = data
            return _cache
        seed = {"schools": _SEED, "abbreviations": _SEED_ABBR}
        write_json("data/structure.json", seed, "Init structure from seed")
        _cache = seed
    except Exception:
        _cache = {"schools": _SEED, "abbreviations": _SEED_ABBR}
    return _cache


def invalidate_structure_cache() -> None:
    global _cache
    _cache = None


def save_structure(structure: dict) -> bool:
    global _cache
    try:
        from github_store import read_json, write_json
        # Always fetch the current SHA — GitHub requires it for updates
        _, sha = read_json("data/structure.json")
        ok = write_json("data/structure.json", structure,
                        "Update school/dept structure", sha)
        if ok:
            _cache = structure
        return bool(ok)
    except Exception:
        return False


def get_schools() -> list[str]:
    return sorted(_get()["schools"].keys())


def get_departments(school: str) -> list[str]:
    return list(_get()["schools"].get(school, {}).keys())


def get_levels(department: str, school: str) -> list[str]:
    num = _get()["schools"].get(school, {}).get(department, 4)
    return [str((i + 1) * 100) for i in range(int(num))]


def get_school_abbr(school: str) -> str:
    abbr = _get().get("abbreviations", {}).get(school)
    if abbr:
        return abbr.upper()
    if "(" in school and ")" in school:
        return school[school.rfind("(") + 1: school.rfind(")")].upper()
    return school[:4].upper()


def get_full_structure() -> dict:
    return _get()
