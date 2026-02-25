"""futo_data.py — FUTO schools, departments and level counts."""

FUTO_STRUCTURE = {
    "School of Agriculture and Agricultural Technology (SAAT)": {
        "Agribusiness": 4,
        "Agricultural Economics": 4,
        "Agricultural Extension": 4,
        "Animal Science and Technology": 4,
        "Crop Science and Technology": 4,
        "Fisheries and Aquaculture Technology": 4,
        "Forestry and Wildlife Technology": 4,
        "Soil Science and Technology": 4,
    },
    "School of Basic Medical Science (SBMS)": {
        "Human Anatomy": 5,
        "Human Physiology": 5,
    },
    "School of Biological Science (SOBS)": {
        "Biochemistry": 4,
        "Biology": 4,
        "Biotechnology": 4,
        "Microbiology": 4,
        "Forensic Science": 4,
    },
    "School of Engineering and Engineering Technology (SEET)": {
        "Agricultural and Bioresources Engineering": 5,
        "Biomedical Engineering": 5,
        "Chemical Engineering": 5,
        "Civil Engineering": 5,
        "Food Science and Technology": 4,
        "Material and Metallurgical Engineering": 5,
        "Mechanical Engineering": 5,
        "Petroleum Engineering": 5,
        "Polymer and Textile Engineering": 5,
    },
    "School of Electrical Systems and Engineering Technology (SESET)": {
        "Computer Engineering": 5,
        "Electrical (Power Systems) Engineering": 5,
        "Electronics Engineering": 5,
        "Mechatronics Engineering": 5,
        "Telecommunications Engineering": 5,
        "Electrical and Electronic Engineering": 5,
    },
    "School of Environmental Science (SOES)": {
        "Architecture": 5,
        "Building Technology": 5,
        "Environmental Management": 4,
        "Quantity Surveying": 5,
        "Surveying and Geoinformatics": 5,
        "Urban and Regional Planning": 5,
        "Environmental Management and Evaluation": 4,
    },
    "School of Health Technology (SOHT)": {
        "Dental Technology": 4,
        "Environmental Health Science": 4,
        "Optometry": 5,
        "Prosthetics and Orthotics": 4,
        "Public Health Technology": 4,
    },
    "School of Information and Communication Technology (SICT)": {
        "Computer Science": 4,
        "Cyber Security": 4,
        "Information Technology": 4,
        "Software Engineering": 4,
    },
    "School of Logistics and Innovation Technology (SLIT)": {
        "Entrepreneurship and Innovation": 4,
        "Logistics and Transport Technology": 4,
        "Maritime Technology and Logistics": 4,
        "Supply Chain Management": 4,
        "Project Management Technology": 4,
    },
    "School of Physical Science (SOPS)": {
        "Chemistry": 4,
        "Geology": 4,
        "Mathematics": 4,
        "Physics": 4,
        "Science Laboratory Technology": 4,
        "Statistics": 4,
    },
}

SCHOOL_ABBREVIATIONS = {
    "School of Agriculture and Agricultural Technology (SAAT)": "SAAT",
    "School of Basic Medical Science (SBMS)": "SBMS",
    "School of Biological Science (SOBS)": "SOBS",
    "School of Engineering and Engineering Technology (SEET)": "SEET",
    "School of Electrical Systems and Engineering Technology (SESET)": "SESET",
    "School of Environmental Science (SOES)": "SOES",
    "School of Health Technology (SOHT)": "SOHT",
    "School of Information and Communication Technology (SICT)": "SICT",
    "School of Logistics and Innovation Technology (SLIT)": "SLIT",
    "School of Physical Science (SOPS)": "SOPS",
}


def get_schools() -> list[str]:
    return list(FUTO_STRUCTURE.keys())


def get_departments(school: str) -> list[str]:
    return list(FUTO_STRUCTURE.get(school, {}).keys())


def get_levels(department: str, school: str) -> list[str]:
    num = FUTO_STRUCTURE.get(school, {}).get(department, 4)
    return [str((i + 1) * 100) for i in range(num)]


def get_school_abbr(school: str) -> str:
    return SCHOOL_ABBREVIATIONS.get(school, school[:4].upper())
