"""Unit tests: extraction, parsing and answer safety (no database needed)."""
from app.extract.pdf import chunk_pages, clean, title_from_file
from app.extract.test_rows import extract_rows, numbers_in, pressure_factor
from app.rag.answer import extractive, number_guard
from app.rag.retriever import Passage
from app.text import numbers, sentences, tokenize


def test_numbers_in_messy_cells():
    assert numbers_in("21.5 - 21.7") == [21.5, 21.7]
    assert numbers_in("~ 21.5") == [21.5]
    assert numbers_in("0.17; 0.21;0.25") == [0.17, 0.21, 0.25]
    assert numbers_in("1.25 atm") == [1.25]
    assert numbers_in("3400%") == [34.0]  # Excel percent artifact
    assert numbers_in("") == []


def test_pressure_units():
    assert pressure_factor("Ambient pressure; mmHg", "757.7", 757.7) == 0.133322
    assert pressure_factor("approx p (bar)", "0.94", 0.94) == 100.0
    assert pressure_factor("Pressure", "1 atm", 1) == 101.325
    assert pressure_factor("Pressure", "1", 1) == 101.325  # unlabelled small values are atmospheres


def test_flex_row_is_normalized():
    cols = ["FLEX Test #", "Fuel", "Ambient pressure; mmHg", "O initial ambient composition; mole fraction", "N initial ambient composition; mole fraction",
            "CO initial ambient composition; mole fraction", "He initial ambient composition; mole fraction", "Droplet initial diameter; mm",
            "Burning rate; mm", "Test end"]
    rows = extract_rows(cols, [["1", "Methanol", "757.7", "0.21", "0.64", "0.15", "0", "1.69", "0.52", "Extinction"]])
    r = rows[0]
    assert r["fuel"] == "Methanol" and r["o2_pct"] == 21.0 and abs(r["pressure_kpa"] - 101.02) < 0.01
    assert r["diluents"] == {"N2": 64.0, "CO2": 15.0}
    assert r["outcome"] == "Test end: Extinction" and r["measures"]["Burning rate; mm"] == 0.52


def test_final_values_are_not_used_as_conditions():
    rows = extract_rows(["XO2 (init)", "XO2 (final)", "pinit (atm)", "pfinal (atm)"], [["0.30", "0.25", "1.0", "1.3"]])
    assert rows[0]["o2_pct"] == 30.0 and abs(rows[0]["pressure_kpa"] - 101.325) < 0.01


def test_fuel_from_header_when_no_fuel_column():
    rows = extract_rows(["XO2", "XC2H4 initial"], [["0.37", "0.27"]])
    assert rows[0]["fuel"] == "C2H4" and rows[0]["o2_pct"] == 37.0


def test_tokenize_and_stem():
    assert tokenize("Flames spreading over burning samples") == ["flame", "spread", "burn", "sample"]


def test_sentences_split_lists():
    s = sentences("Aims: 1) Develop a new diagram of flame limits. 2) Bridge the knowledge gap between limits.")
    assert "Develop a new diagram of flame limits." in s and "Bridge the knowledge gap between limits." in s


def test_pdf_cleaning_and_chunking():
    raw = "Flame spread over thin fuels was meas-\nured in the Microgravity Science\nGlovebox at 21% oxygen. " * 30
    t = clean(raw)
    assert "measured" in t and "Microgravity Science Glovebox" in t
    chunks = chunk_pages([raw, "", raw])
    assert chunks and {c["page"] for c in chunks} == {1, 3}
    assert all(len(c["text"]) <= 1200 for c in chunks)
    assert title_from_file("PSI-159", "PSI-159_Reports_FinalRpt_ACME.CFI-G.pdf") == "FinalRpt ACME.CFI-G"


def _p(i, text):
    return Passage(id=i, document_id=f"PSI-69/doc{i}.pdf", accession="PSI-69", title=f"Doc {i}", kind="pdf", category="Reports", page=i, section="", text=text)


def test_extractive_answer_cites_and_is_grounded():
    ps = [_p(1, "Helium dilution raised the extinction diameter of heptane droplets. The tests ran at 1 atm."),
          _p(2, "Carbon dioxide dilution caused radiative extinction of large droplets at 21% oxygen.")]
    out = extractive("How does carbon dioxide dilution cause extinction of droplets?", ps)
    assert "[1]" in out["answer"] or "[2]" in out["answer"]
    assert number_guard(out["answer"], "q", out["cited"]) == []


def test_number_guard_flags_invented_numbers():
    ps = [_p(1, "Flames extinguished at 15% oxygen.")]
    assert number_guard("Flames extinguished at 15% oxygen [1].", "q", ps) == []
    assert number_guard("Flames extinguished at 12% oxygen [1].", "q", ps) == ["12"]
    assert numbers("1,000 and 21.50") == {"1000", "21.5"}
