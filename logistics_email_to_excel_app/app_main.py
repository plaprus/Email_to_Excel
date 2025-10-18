from __future__ import annotations
import os, io, re
from dataclasses import dataclass
from typing import Dict, List, Tuple, Optional

import streamlit as st
import pandas as pd
from rapidfuzz import process, fuzz
from dateutil import parser as dateparser

# ===================== PASSWORD =====================
APP_PASSWORD = st.secrets.get("APP_PASSWORD", os.environ.get("APP_PASSWORD", ""))

def password_gate() -> None:
    if not APP_PASSWORD:
        st.info("🔓 No password set (development). Add APP_PASSWORD secret for production.")
        return
    st.session_state.setdefault("auth_ok", False)
    if st.session_state["auth_ok"]:
        return
    st.title("🔒 Sign in")
    pwd = st.text_input("Password", type="password")
    if st.button("Unlock"):
        if pwd == APP_PASSWORD:
            st.session_state["auth_ok"] = True
            st.rerun()
        else:
            st.error("Wrong password.")
    st.stop()

# ===================== PARSER HELPERS =====================
NUM = r"(?P<num>\d+(?:[\.,]\d+)*)"
SPACE = r"[\s\u00A0]*"

@dataclass
class Parsed:
    fields: Dict[str, str]
    debug: Dict[str, str]

def norm_text(txt: str) -> str:
    t = txt.replace("\u00A0", " ")
    t = re.sub(r"[\t ]+", " ", t)
    return t

def norm_number(s: str) -> str:
    s = s.strip().replace(" ", "")
    return s.replace(",", ".")

def parse_date(text: str) -> Optional[str]:
    cand = re.findall(r"\b(\d{4}-\d{2}-\d{2}|\d{1,2}[./-]\d{1,2}[./-]\d{2,4})\b", text)
    for c in cand:
        for dayfirst in (True, False):
            try:
                dt = dateparser.parse(c, dayfirst=dayfirst, yearfirst=False)
                if dt:
                    return dt.date().isoformat()
            except Exception:
                pass
    return None

def first_token(val: str) -> str:
    # Cut on newline or when another key likely starts
    return re.split(r"\s{2,}|\n|,\s*(weight|volume|dims?|dimensions|rate|km|distance|total|cost|amount)", val, flags=re.I)[0].strip(" .")

def extract_fields(email_text: str) -> Parsed:
    txt = norm_text(email_text)
    lower = txt.lower()
    fields: Dict[str, str] = {}
    debug: Dict[str, str] = {}

    # Destination (Country/City) and Origin (Country/City)
    # We try lines like: Destination: Luanda, Angola / Origin: Indore, India
    dest = re.search(r"(?:destination|to|delivery|port\s*of\s*destination)\s*[:=-]\s*(.+)", lower, re.I)
    if dest:
        raw = first_token(dest.group(1))
        debug["destination_raw"] = raw
        parts = [p.strip(" ,.;") for p in re.split(r"[,/]", raw) if p.strip()]
        if len(parts) >= 2:
            fields["destination_city"] = parts[0]; fields["destination_country"] = parts[1]
        elif parts:
            # if single token, assume city; country will be filled from defaults
            fields["destination_city"] = parts[0]

    orig = re.search(r"(?:origin|from|pickup|port\s*of\s*loading)\s*[:=-]\s*(.+)", lower, re.I)
    if orig:
        raw = first_token(orig.group(1))
        debug["origin_raw"] = raw
        parts = [p.strip(" ,.;") for p in re.split(r"[,/]", raw) if p.strip()]
        if len(parts) >= 2:
            fields["origin_city"] = parts[0]; fields["origin_country"] = parts[1]
        elif parts:
            fields["origin_city"] = parts[0]

    # Weight
    m = re.search(rf"(?:weight|waga|masa){SPACE}[:=-]?{SPACE}({NUM}){SPACE}(kg|kilogram|kilograms|t|ton)\b", lower)
    if m:
        num = norm_number(m.group(1)); unit = m.group(2)
        kg = float(num) * (1000.0 if unit in {'t','ton'} else 1.0)
        fields["weight_kg"] = f"{kg:.3f}".rstrip("0").rstrip("."); debug["weight_kg"] = m.group(0)

    # Volume
    m = re.search(rf"(?:volume|cbm|m3|m³|obj(?:ętość|etosc)?)\s*[:=-]?\s*({NUM})\s*(m3|m³|m\^3|cbm)?\b", lower)
    if m:
        fields["volume_m3"] = norm_number(m.group(1)); debug["volume_m3"] = m.group(0)

    # Dimensions
    m = re.search(rf"(?:dims?|dimensions|wymiary){SPACE}[:=-]?{SPACE}({NUM}){SPACE}[x×]{SPACE}({NUM}){SPACE}[x×]{SPACE}({NUM}){SPACE}(mm|cm|m)?\b", lower)
    if m:
        L, W, H = map(norm_number, [m.group(1), m.group(2), m.group(3)])
        unit = m.group(4) or ""
        fields["dimensions"] = f"{L}x{W}x{H}{unit}"; debug["dimensions"] = m.group(0)

    # Rate per km
    m = re.search(rf"(?:rate|price|stawka|cena){SPACE}[:=-]?{SPACE}({NUM}){SPACE}(?:pln|zł|zl|eur|€|usd|\$)?{SPACE}/?{SPACE}km\b", lower)
    if m:
        fields["rate_per_km"] = norm_number(m.group(1)); debug["rate_per_km"] = m.group(0)

    # Distance
    m = re.search(rf"(?:distance|dystans|odleg){SPACE}[:=-]?{SPACE}({NUM}){SPACE}km\b", lower)
    if m:
        fields["distance_km"] = norm_number(m.group(1)); debug["distance_km"] = m.group(0)

    # Date
    dt = parse_date(txt)
    if dt:
        fields["date"] = dt; debug["date"] = dt

    # Total
    m = re.search(rf"(?:total|cost|amount|razem|koszt){SPACE}[:=-]?{SPACE}({NUM})\b", lower)
    if m:
        fields["total_cost"] = norm_number(m.group(1)); debug["total_cost"] = m.group(0)

    # Shipment mode (heuristics)
    if re.search(r"\bair\b", lower): fields["shipment_mode"] = "AIR (GEN/Ambient)"
    elif re.search(r"\b(sea|ocean|container)\b", lower): fields["shipment_mode"] = "SEA (FF)"

    return Parsed(fields=fields, debug=debug)

def make_unique_headers(columns) -> List[str]:
    seen = {}
    fixed = []
    for c in columns:
        name = "" if c is None else str(c).strip()
        if name == "":
            name = "col"
        if name in seen:
            seen[name] += 1
            name = f"{name}_{seen[name]}"
        else:
            seen[name] = 0
        fixed.append(name)
    return fixed

def parse_band_ranges(bands_str_list):
    out = []
    for b in bands_str_list:
        b = b.strip()
        if "-" in b:
            lo, hi = b.split("-", 1)
            try:
                out.append((float(lo.replace(",", ".").strip()), float(hi.replace(",", ".").strip())))
            except:
                pass
    return out

def pick_weight_band(weight_kg: float, band_ranges: list[tuple[float,float]]) -> str:
    for lo, hi in band_ranges:
        if lo <= weight_kg <= hi:
            return f"{int(lo)}-{int(hi)} kg"
    return ""

# ===================== APP =====================
st.set_page_config(page_title="Email → Excel (secure)", page_icon="📨➡️📊", layout="wide")
password_gate()

st.title("📨 → 📊 Email → Excel: secure logistics parser (EN)")
st.caption("Upload your Excel template, paste email(s), review preview, download updated XLSX.")

# ---------- Left column: Inputs ----------
colL, colR = st.columns([1,1])

with colL:
    with st.expander("⚙️ Settings", expanded=True):
        st.write("Paste **multiple emails** separated by a line with three dashes: `---`.")
        auto_compute = st.checkbox("Compute Total = Rate × Distance if Total is missing", value=True)

    with st.expander("🌍 Routing & Defaults", expanded=True):
        st.caption("If an email misses these, defaults below will be used.")
        default_country = st.text_input("Default Country (Destination)", value="Angola")
        default_city = st.text_input("Default City (Destination)", value="Luanda")
        default_origin_country = st.text_input("Default Origin Country", value="India")
        default_origin_city = st.text_input("Default Origin City", value="Indore")

    with st.expander("📦 Shipment classification", expanded=False):
        force_mode = st.selectbox("Force Shipment mode (optional)", ["(auto)", "AIR (GEN/Ambient)", "SEA (FF)", "SEA (USF)"], index=0)

    with st.expander("⚖️ Weight bands", expanded=False):
        bands = [
            st.text_input("Band 1", value="0-500"),
            st.text_input("Band 2", value="501-1000"),
            st.text_input("Band 3", value="1001-3000"),
            st.text_input("Band 4", value="3001-5000"),
        ]
        band_ranges = parse_band_ranges(bands)

    xlsx_file = st.file_uploader("Upload your Excel template (XLSX)", type=["xlsx"])
    sheet_name = st.text_input("Sheet name (leave empty to use the first one)", value="")
    email_blob = st.text_area("Paste email text here", height=280, placeholder=(
        "Origin: Indore, India\nDestination: Luanda, Angola\nWeight: 120 kg\nRate: 3.20 PLN/km\nDistance: 170 km\nDate: 2025-10-18\n---\n(Second email here...)"
    ))

def load_excel_to_df(file) -> Tuple[pd.DataFrame, str]:
    if file is None:
        cols = [
            "Country","City","Shipment mode","Weight Band","Origin Country","Origin City*",
            "Origin Rate per Shipment","Origin Rate per KG / Per Container",
            "Port -to Port Air (per KG) Ocean (per Cntr)","Transit time",
            "Port to Door Rate (Destination per KG for AIR / per CNTR for OCEAN)**",
            "Port to Door Rate (Destination per shipment)**",
            # plus commonly parsed fields for convenience:
            "Date","Weight (kg)","Volume (m3)","Dimensions","Rate (PLN/km)","Distance (km)","Total (PLN)"
        ]
        return pd.DataFrame(columns=cols), "Sheet1"
    else:
        with pd.ExcelFile(file) as xls:
            sn = sheet_name or xls.sheet_names[0]
            df = pd.read_excel(xls, sheet_name=sn)
            df.columns = make_unique_headers(df.columns)
            return df, sn

def suggest_mapping(df_cols: List[str]) -> Dict[str, str]:
    targets = {
        # schema columns
        "destination_country": ["Country"],
        "destination_city": ["City"],
        "shipment_mode": ["Shipment mode"],
        "weight_band": ["Weight Band"],
        "origin_country": ["Origin Country"],
        "origin_city": ["Origin City*","Origin City"],
        # parsed extras
        "date": ["Date"],
        "weight_kg": ["Weight (kg)","Weight"],
        "volume_m3": ["Volume (m3)","CBM"],
        "dimensions": ["Dimensions","Dims"],
        "rate_per_km": ["Rate (PLN/km)","Price/km"],
        "distance_km": ["Distance (km)","KM"],
        "total_cost": ["Total (PLN)","Total","Amount"],
    }
    mapping: Dict[str, str] = {}
    for k, aliases in targets.items():
        if df_cols:
            match, score, _ = process.extractOne("|".join(aliases), df_cols, scorer=fuzz.WRatio)
            mapping[k] = match or ""
        else:
            mapping[k] = ""
    return mapping

# ---------- Right column: Processing & Preview ----------
with colR:
    if email_blob.strip():
        parts = [p.strip() for p in email_blob.split("\n---\n") if p.strip()]
        base_df, sn = load_excel_to_df(xlsx_file)
        prop_map = suggest_mapping(list(base_df.columns))

        rows = []
        debugs = []
        for mail in parts:
            parsed = extract_fields(mail)
            d = parsed.fields

            # Fill defaults if missing
            dest_country = d.get("destination_country") or default_country
            dest_city = d.get("destination_city") or default_city
            orig_country = d.get("origin_country") or default_origin_country
            orig_city = d.get("origin_city") or default_origin_city

            # Shipment mode
            mode = d.get("shipment_mode", "")
            if force_mode and force_mode != "(auto)":
                mode = force_mode
            if not mode:
                mode = "AIR (GEN/Ambient)"

            # Weight band
            weight_kg_val = None
            if d.get("weight_kg"):
                try:
                    weight_kg_val = float(norm_number(d["weight_kg"]))
                except Exception:
                    pass
            band = pick_weight_band(weight_kg_val, band_ranges) if weight_kg_val is not None else ""

            # Compute total
            if ("total_cost" not in d) and d.get("rate_per_km") and d.get("distance_km"):
                try:
                    total = float(norm_number(d["rate_per_km"])) * float(norm_number(d["distance_km"]))
                    d["total_cost"] = f"{total:.2f}"
                except Exception:
                    pass

            # Compose row matching user's Excel column names
            row = {col: None for col in base_df.columns}
            key_to_col = {
                "destination_country": prop_map.get("destination_country",""),
                "destination_city":    prop_map.get("destination_city",""),
                "shipment_mode":       prop_map.get("shipment_mode",""),
                "weight_band":         prop_map.get("weight_band",""),
                "origin_country":      prop_map.get("origin_country",""),
                "origin_city":         prop_map.get("origin_city",""),
                "date":                prop_map.get("date",""),
                "weight_kg":           prop_map.get("weight_kg",""),
                "volume_m3":           prop_map.get("volume_m3",""),
                "dimensions":          prop_map.get("dimensions",""),
                "rate_per_km":         prop_map.get("rate_per_km",""),
                "distance_km":         prop_map.get("distance_km",""),
                "total_cost":          prop_map.get("total_cost",""),
            }

            # Fill fixed values/defaults first
            if key_to_col["destination_country"]:
                row[key_to_col["destination_country"]] = dest_country
            if key_to_col["destination_city"]:
                row[key_to_col["destination_city"]] = dest_city
            if key_to_col["origin_country"]:
                row[key_to_col["origin_country"]] = orig_country
            if key_to_col["origin_city"]:
                row[key_to_col["origin_city"]] = orig_city
            if key_to_col["shipment_mode"]:
                row[key_to_col["shipment_mode"]] = mode
            if key_to_col["weight_band"]:
                row[key_to_col["weight_band"]] = band

            # Now fill parsed numeric/text fields
            for k in ("date","weight_kg","volume_m3","dimensions","rate_per_km","distance_km","total_cost"):
                colname = key_to_col.get(k,"")
                if colname:
                    val = d.get(k)
                    if val is not None:
                        row[colname] = val

            rows.append(row)
            debugs.append(parsed.debug)

        preview_df = pd.DataFrame(rows)
        st.subheader("Detected rows (preview)")
        st.dataframe(preview_df, use_container_width=True)

        new_df = pd.concat([base_df, preview_df], ignore_index=True)
        buf = io.BytesIO()
        with pd.ExcelWriter(buf, engine="openpyxl") as writer:
            new_df.to_excel(writer, index=False, sheet_name=sn)
        buf.seek(0)
        st.success(f"✅ Prepared {len(rows)} row(s). Download updated Excel below.")
        st.download_button(
            "⬇️ Download updated Excel",
            data=buf.getvalue(),
            file_name="orders_updated.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        )

        with st.expander("🔎 Matching details (debug)"):
            for i, dbg in enumerate(debugs, start=1):
                st.markdown(f"**Email {i}:**")
                st.code("\\n".join(f"{k}: {v}" for k, v in dbg.items()) or "(none)")

# Optional manual mapping UI (advanced users)
st.subheader("🧭 Column mapping (optional)")
st.caption("If a column name in your Excel is different, you can adjust mappings here and re‑paste emails to reprocess.")
base_df_tmp, _ = load_excel_to_df(xlsx_file)
df_cols = [str(c) for c in base_df_tmp.columns]
prop_map = suggest_mapping(df_cols) if df_cols else {}
for key, default_col in prop_map.items():
    st.selectbox(f"Map '{key}' →", [""] + df_cols, index=(df_cols.index(default_col)+1 if default_col in df_cols else 0), key=f"map_{key}")
st.info("💡 Changes here are for reference; this lightweight version uses suggested mapping during processing. For fixed mapping, rename your Excel headers to match the suggestions, or ask us to bake them in permanently.")
