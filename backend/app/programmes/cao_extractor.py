import json
import re
from collections import Counter
from pathlib import Path

import pdfplumber

PDF_START_PAGE = 57
PDF_END_PAGE = 213
SOURCE_YEAR = 2027

PROVIDER_HEADINGS = {
    "UNIVERSITIES AND UNIVERSITIES OF TECHNOLOGY": "public",
    "PRIVATE COLLEGES": "private",
}

INSTITUTIONS = {
    "DU": "Durban University of Technology",
    "MN": "Mangosuthu University of Technology",
    "KN": "University of KwaZulu-Natal",
    "ZU": "University of Zululand",
    "AA": "AAA School of Advertising",
    "BC": "Berea College of Technology",
    "BT": "Berea Technical College",
    "DC": "Central Technical College",
    "EM": "STADIO Institute of Higher Education",
    "IS": "iStudent",
    "MC": "MANCOSA",
    "PE": "Eduvos",
    "PX": "PAX College",
    "RB": "Regent Business School",
    "RG": "Richfield Graduate Institute of Technology",
}

CAMPUSES = {
    "DU": {"B": "Brickfield", "C": "City", "D": "ML Sultan/Steve Biko", "F": "EDU - Durban", "G": "EDU - PMB", "I": "Indumiso", "P": "Pietermaritzburg"},
    "MN": {"M": "Main"},
    "KN": {"E": "Edgewood", "H": "Howard College", "M": "Medical School", "P": "Pietermaritzburg", "W": "Westville"},
    "ZU": {"A": "Kwa-Dlangezwa (Main)", "M": "Kwa-Dlangezwa (Main)", "R": "Richards Bay"},
    "AA": {"B": "Bryanston", "C": "Cape Town"},
    "BC": {"D": "Durban"},
    "BT": {"D": "Durban"},
    "DC": {"D": "Durban"},
    "EM": {"B": "Bellville", "C": "Centurion", "D": "Durban (Musgrave)", "H": "Hatfield", "J": "Johannesburg", "K": "Krugersdorp", "P": "Pretoria", "R": "Randburg", "W": "Waterfall", "X": "Distance"},
    "IS": {"B": "Bloemfontein", "C": "Cape Town", "D": "Durban", "J": "Johannesburg", "P": "Pietermaritzburg"},
    "MC": {"C": "Cape Town", "D": "Durban"},
    "PE": {"B": "Bedfordview", "C": "Claremont", "D": "Durban", "E": "East London", "F": "Potchefstroom", "K": "Vanderbijlpark", "L": "Bloemfontein", "M": "Midrand", "N": "Nelson Mandela Bay", "O": "Mbombela", "P": "Pretoria", "T": "Tyger Valley", "V": "Durbanville"},
    "PX": {"D": "Durban"},
    "RB": {"D": "Durban"},
    "RG": {"D": "Durban"},
}

CODE_RE = re.compile(r"^[A-Z]{2}-[A-Z0-9]-[A-Z0-9]{3}$")
CAREER_RE = re.compile(r"^\d+\.\s+")


def clean(value):
    if value is None:
        return ""
    return " ".join(str(value).replace("\u00a0", " ").split())


def overlap_y(a, b):
    return max(0.0, min(a[3], b[3]) - max(a[1], b[1]))


def center_y(bbox):
    return (bbox[1] + bbox[3]) / 2


def decode_code(code):
    inst = code[:2]
    campus = code[3]
    return {
        "institution_code": inst,
        "institution": INSTITUTIONS.get(inst),
        "campus_code": campus,
        "campus": CAMPUSES.get(inst, {}).get(campus),
    }


def infer_exam_type(requirement):
    t = requirement.lower().strip()
    if t.startswith("nsc") or t.startswith("south african national senior certificate"):
        return "NSC"
    if t.startswith("senior cert") or t.startswith("matric") or t.startswith("sc matric"):
        return "Senior Certificate"
    if t.startswith("nc(v)") or t.startswith("ncv") or t.startswith("national certificate (vocational)"):
        return "NC(V)"
    if re.match(r"^n[2-6]\b", t) or t.startswith("nated"):
        return "NATED"
    if "igcse" in t or t.startswith("gce"):
        return "Foreign qualification"
    if t.startswith("consult institution"):
        return "Institution-specific"
    return "Other"


def classify_heading(text):
    if not text:
        return None
    if CAREER_RE.match(text):
        return "career"
    if text in PROVIDER_HEADINGS:
        return "provider"
    if text == "Programme name":
        return "columns"
    if text.isupper() or text.startswith("PROGRAMMES FOR"):
        return "study_level"
    return None


def table_cells_with_text(table, extracted_rows):
    cells = []
    seen = set()
    for ri, row_obj in enumerate(table.rows):
        row_text = extracted_rows[ri] if ri < len(extracted_rows) else []
        for ci, bbox in enumerate(row_obj.cells):
            if bbox is None:
                continue
            key = tuple(round(v, 5) for v in bbox)
            if key in seen:
                continue
            seen.add(key)
            text = clean(row_text[ci] if ci < len(row_text) else "")
            cells.append({"row": ri, "col": ci, "bbox": bbox, "text": text})
    return cells


def choose_group_span(program_cell, cells):
    y = center_y(program_cell["bbox"])
    candidates = []
    for c in cells:
        if c["col"] not in {2, 5, 6, 7, 8}:
            continue
        if c["bbox"][1] - 0.2 <= y <= c["bbox"][3] + 0.2:
            span = (round(c["bbox"][1], 2), round(c["bbox"][3], 2))
            candidates.append(span)

    if not candidates:
        return (program_cell["bbox"][1], program_cell["bbox"][3])

    counts = Counter(candidates)
    # Prefer the most common metadata span; on a tie choose the taller span.
    return max(counts, key=lambda s: (counts[s], s[1] - s[0]))


def best_cell_at_y(cells, col, y):
    matches = [c for c in cells if c["col"] == col and c["bbox"][1] - 0.2 <= y <= c["bbox"][3] + 0.2]
    if not matches:
        return None
    return min(matches, key=lambda c: c["bbox"][3] - c["bbox"][1])


def best_min_points_for_requirement(req_cell, cells):
    candidates = []
    for c in cells:
        if c["col"] != 3 or not c["text"]:
            continue
        ov = overlap_y(req_cell["bbox"], c["bbox"])
        if ov > 0:
            candidates.append((ov, c))
    if not candidates:
        return ""
    candidates.sort(key=lambda x: x[0], reverse=True)
    return candidates[0][1]["text"]


def extract_page_table(page, pdf_page_number):
    results = []
    tables = page.find_tables()

    for table in tables:
        extracted = table.extract()
        if not extracted or len(extracted) < 2:
            continue
        cells = table_cells_with_text(table, extracted)

        career = None
        provider = None
        study_level = None

        for ri, row in enumerate(extracted):
            values = [clean(x) for x in (row or [])]
            if not values:
                continue
            first = values[0] if values else ""
            heading = classify_heading(first) if all(not clean(x) for x in values[1:]) else None

            if heading == "career":
                career = first
                provider = None
                study_level = None
                continue
            if heading == "provider":
                provider = first
                study_level = None
                continue
            if heading == "study_level":
                study_level = first
                continue
            if first == "Programme name":
                continue

            # Programme-name cells are the anchor for each logical programme.
            name_cell = next((c for c in cells if c["row"] == ri and c["col"] == 0 and c["text"] == first), None)
            if not name_cell or not first:
                continue
            if CODE_RE.fullmatch(first):
                continue

            group_y0, group_y1 = choose_group_span(name_cell, cells)
            group_bbox = (table.bbox[0], group_y0, table.bbox[2], group_y1)

            # Programme codes belong to the programme-name cell. A name cell can span
            # several campuses or entry terms, so collect every code whose centre lies
            # inside the name cell's vertical range.
            name_y0, name_y1 = name_cell["bbox"][1], name_cell["bbox"][3]
            code_cells = [
                c for c in cells
                if c["col"] == 1 and CODE_RE.fullmatch(c["text"])
                and name_y0 - 0.2 <= center_y(c["bbox"]) <= name_y1 + 0.2
            ]

            # Requirements are sometimes stacked inside a wider metadata block and
            # sometimes a single merged requirement cell spans several programme names.
            # Taking the union handles both CAO layouts.
            req_cells = [
                c for c in cells
                if c["col"] == 4 and c["text"]
                and (
                    group_y0 - 0.2 <= center_y(c["bbox"]) <= group_y1 + 0.2
                    or overlap_y(c["bbox"], name_cell["bbox"]) > 0
                )
            ]
            requirements = []
            seen_req = set()
            for rc in req_cells:
                key = rc["text"]
                if key in seen_req:
                    continue
                seen_req.add(key)
                requirements.append({
                    "exam_type": infer_exam_type(rc["text"]),
                    "minimum_points_raw": best_min_points_for_requirement(rc, cells),
                    "raw_requirement": rc["text"],
                })

            offerings = []
            for code_cell in code_cells:
                y = center_y(code_cell["bbox"])
                code = code_cell["text"]
                closing = best_cell_at_y(cells, 2, y)
                entry = best_cell_at_y(cells, 5, y)
                duration = best_cell_at_y(cells, 6, y)
                access = best_cell_at_y(cells, 7, y)
                notes = best_cell_at_y(cells, 8, y)
                offerings.append({
                    "programme_code": code,
                    **decode_code(code),
                    "closing_date_raw": closing["text"] if closing else "",
                    "entry_term": entry["text"] if entry else "",
                    "course_duration": duration["text"] if duration else "",
                    "access_route": access["text"] if access else "",
                    "notes": notes["text"] if notes else "",
                })

            if not offerings:
                continue

            results.append({
                "programme_name": first,
                "career_direction": career,
                "provider_category": provider,
                "study_level": study_level,
                "offerings": offerings,
                "requirements": requirements,
                "source": "CAO Handbook 2027",
                "source_year": SOURCE_YEAR,
                "source_pdf_page": pdf_page_number,
                "source_handbook_page": pdf_page_number - 12,
            })

    return results


def extract(pdf_path):
    output = []
    with pdfplumber.open(pdf_path) as pdf:
        for page_num in range(PDF_START_PAGE, PDF_END_PAGE + 1):
            output.extend(extract_page_table(pdf.pages[page_num - 1], page_num))
    return output


def validation(records):
    from collections import Counter, defaultdict

    offerings = [o for r in records for o in r["offerings"]]
    composite = [(o["programme_code"], o["entry_term"], o["closing_date_raw"]) for o in offerings]
    duplicate_counts = Counter(composite)

    duplicate_details = []
    for key, count in sorted(duplicate_counts.items()):
        if count <= 1:
            continue
        code, entry_term, closing = key
        matches = []
        for r in records:
            if any(
                o["programme_code"] == code
                and o["entry_term"] == entry_term
                and o["closing_date_raw"] == closing
                for o in r["offerings"]
            ):
                matches.append({
                    "programme_name": r["programme_name"],
                    "career_direction": r["career_direction"],
                    "source_handbook_page": r["source_handbook_page"],
                })
        duplicate_details.append({
            "programme_code": code,
            "entry_term": entry_term,
            "closing_date_raw": closing,
            "count": count,
            "matches": matches,
        })

    institution_counts = Counter(o["institution"] or "UNKNOWN" for o in offerings)
    career_counts = Counter(r["career_direction"] or "UNKNOWN" for r in records)

    return {
        "programme_records": len(records),
        "programme_offerings": len(offerings),
        "unique_programme_codes": len({o["programme_code"] for o in offerings}),
        "unique_code_term_closing_combinations": len(set(composite)),
        "exact_duplicate_offering_keys": duplicate_details,
        "records_without_requirements": [r["programme_name"] for r in records if not r["requirements"]],
        "unknown_institution_codes": sorted({o["programme_code"] for o in offerings if not o["institution"]}),
        "unknown_campus_codes": sorted({o["programme_code"] for o in offerings if not o["campus"]}),
        "offerings_by_institution": dict(sorted(institution_counts.items())),
        "programme_records_by_career_direction": dict(sorted(career_counts.items())),
    }


def main():
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("pdf", type=Path)
    parser.add_argument("--out", type=Path, default=Path("cao_programmes_2027.json"))
    parser.add_argument("--report", type=Path, default=Path("cao_programmes_2027_validation.json"))
    args = parser.parse_args()

    records = extract(args.pdf)
    report = validation(records)
    args.out.write_text(json.dumps(records, ensure_ascii=False, indent=2), encoding="utf-8")
    args.report.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")

    print(json.dumps({k: v if not isinstance(v, list) else len(v) for k, v in report.items()}, indent=2))
    print(f"Saved: {args.out}")
    print(f"Saved: {args.report}")


if __name__ == "__main__":
    main()
