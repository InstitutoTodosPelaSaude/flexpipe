#!/usr/bin/env python3
"""
Auxiliary curation: Nextclade join, region, clade_truncated, source, dedup.

Column renaming  → augur curate rename
Date formatting  → augur curate format-dates
QC/coverage/seq  → augur filter
"""

import argparse
import os
import re
import sys

import pandas as pd
import yaml

REGION_MAP = {
    # Africa
    "Algeria": "Africa", "Angola": "Africa", "Benin": "Africa",
    "Botswana": "Africa", "Burkina Faso": "Africa", "Burundi": "Africa",
    "Cameroon": "Africa", "Cape Verde": "Africa", "Central African Republic": "Africa",
    "Chad": "Africa", "Comoros": "Africa", "Congo": "Africa",
    "Democratic Republic of the Congo": "Africa", "Djibouti": "Africa",
    "Egypt": "Africa", "Equatorial Guinea": "Africa", "Eritrea": "Africa",
    "Ethiopia": "Africa", "Gabon": "Africa", "Gambia": "Africa",
    "Ghana": "Africa", "Guinea": "Africa", "Guinea-Bissau": "Africa",
    "Ivory Coast": "Africa", "Cote d'Ivoire": "Africa",
    "Kenya": "Africa", "Lesotho": "Africa", "Liberia": "Africa",
    "Libya": "Africa", "Madagascar": "Africa", "Malawi": "Africa",
    "Mali": "Africa", "Mauritania": "Africa", "Mauritius": "Africa",
    "Morocco": "Africa", "Mozambique": "Africa", "Namibia": "Africa",
    "Niger": "Africa", "Nigeria": "Africa", "Rwanda": "Africa",
    "Senegal": "Africa", "Sierra Leone": "Africa", "Somalia": "Africa",
    "South Africa": "Africa", "South Sudan": "Africa", "Sudan": "Africa",
    "Tanzania": "Africa", "Togo": "Africa", "Tunisia": "Africa",
    "Uganda": "Africa", "Zambia": "Africa", "Zimbabwe": "Africa",
    # Asia
    "Afghanistan": "Asia", "Armenia": "Asia", "Azerbaijan": "Asia",
    "Bahrain": "Asia", "Bangladesh": "Asia", "Bhutan": "Asia",
    "Brunei": "Asia", "Cambodia": "Asia", "China": "Asia",
    "Cyprus": "Asia", "Georgia": "Asia", "India": "Asia",
    "Indonesia": "Asia", "Iran": "Asia", "Iraq": "Asia",
    "Israel": "Asia", "Japan": "Asia", "Jordan": "Asia",
    "Kazakhstan": "Asia", "Kuwait": "Asia", "Kyrgyzstan": "Asia",
    "Laos": "Asia", "Lebanon": "Asia", "Malaysia": "Asia",
    "Maldives": "Asia", "Mongolia": "Asia", "Myanmar": "Asia",
    "Nepal": "Asia", "North Korea": "Asia", "Oman": "Asia",
    "Pakistan": "Asia", "Palestine": "Asia", "Philippines": "Asia",
    "Qatar": "Asia", "Saudi Arabia": "Asia", "Singapore": "Asia",
    "South Korea": "Asia", "Sri Lanka": "Asia", "Syria": "Asia",
    "Taiwan": "Asia", "Tajikistan": "Asia", "Thailand": "Asia",
    "Timor-Leste": "Asia", "Turkey": "Asia", "Turkmenistan": "Asia",
    "United Arab Emirates": "Asia", "Uzbekistan": "Asia",
    "Vietnam": "Asia", "Viet Nam": "Asia",
    "Hong Kong": "Asia", "Yemen": "Asia",
    # Europe
    "Albania": "Europe", "Andorra": "Europe", "Austria": "Europe",
    "Belarus": "Europe", "Belgium": "Europe",
    "Bosnia and Herzegovina": "Europe", "Bulgaria": "Europe",
    "Croatia": "Europe", "Czech Republic": "Europe", "Czechia": "Europe",
    "Denmark": "Europe", "Estonia": "Europe", "Finland": "Europe",
    "France": "Europe", "Germany": "Europe", "Greece": "Europe",
    "Hungary": "Europe", "Iceland": "Europe", "Ireland": "Europe",
    "Italy": "Europe", "Kosovo": "Europe", "Latvia": "Europe",
    "Liechtenstein": "Europe", "Lithuania": "Europe", "Luxembourg": "Europe",
    "Malta": "Europe", "Moldova": "Europe", "Monaco": "Europe",
    "Montenegro": "Europe", "Netherlands": "Europe",
    "North Macedonia": "Europe", "Norway": "Europe", "Poland": "Europe",
    "Portugal": "Europe", "Romania": "Europe", "Russia": "Europe",
    "Serbia": "Europe", "Slovakia": "Europe", "Slovenia": "Europe",
    "Spain": "Europe", "Sweden": "Europe", "Switzerland": "Europe",
    "Ukraine": "Europe", "United Kingdom": "Europe", "UK": "Europe",
    # North America
    "Antigua and Barbuda": "North America", "Bahamas": "North America",
    "Barbados": "North America", "Belize": "North America",
    "Canada": "North America", "Costa Rica": "North America",
    "Cuba": "North America", "Dominica": "North America",
    "Dominican Republic": "North America", "El Salvador": "North America",
    "Grenada": "North America", "Guatemala": "North America",
    "Haiti": "North America", "Honduras": "North America",
    "Jamaica": "North America", "Mexico": "North America",
    "Nicaragua": "North America", "Panama": "North America",
    "Trinidad and Tobago": "North America",
    "United States": "North America", "USA": "North America",
    "Puerto Rico": "North America", "Guam": "North America",
    "US Virgin Islands": "North America", "American Samoa": "North America",
    # South America
    "Argentina": "South America", "Bolivia": "South America",
    "Brazil": "South America", "Chile": "South America",
    "Colombia": "South America", "Ecuador": "South America",
    "Guyana": "South America", "Paraguay": "South America",
    "Peru": "South America", "Suriname": "South America",
    "Uruguay": "South America", "Venezuela": "South America",
    # Oceania
    "Australia": "Oceania", "Fiji": "Oceania", "Kiribati": "Oceania",
    "Marshall Islands": "Oceania", "Micronesia": "Oceania",
    "Nauru": "Oceania", "New Zealand": "Oceania", "Palau": "Oceania",
    "Papua New Guinea": "Oceania", "Samoa": "Oceania",
    "Solomon Islands": "Oceania", "Tonga": "Oceania",
    "Tuvalu": "Oceania", "Vanuatu": "Oceania",
}


def truncate_clade(clade, levels, sep="."):
    parts = [p for p in str(clade).strip().split(sep) if p]
    return sep.join(parts[:levels]) if parts else ""


def main():
    parser = argparse.ArgumentParser(
        description="Nextclade join + region + clade_truncated"
    )
    parser.add_argument("--config",    required=True)
    parser.add_argument("--metadata",  required=True)
    parser.add_argument("--nextclade", required=False, default=None)
    parser.add_argument("--output",    required=True)
    args = parser.parse_args()

    cfg     = yaml.safe_load(open(args.config))
    nc_cfg  = cfg.get("viralqc", cfg.get("nextclade", {}))
    cur_cfg = cfg.get("curation", {})

    _ds = cfg.get("data_source", "pathoplexus").lower()
    default_source = "NCBI" if _ds == "ncbi" else "Pathoplexus"

    clade_col    = nc_cfg.get("clade_column", "clade")
    clade_levels = int(cur_cfg.get("clade_levels", 3))
    clade_sep    = str(cur_cfg.get("clade_separator", "."))

    os.makedirs(os.path.dirname(os.path.abspath(args.output)), exist_ok=True)

    df = pd.read_csv(args.metadata, sep="\t", dtype=str).fillna("")
    print(f"Loaded: {len(df)} rows")

    # ── join ViralQC (BLAST + Nextclade) ─────────────────────────────────────
    # ViralQC roda em todas as sequências; left join preserva clade Pathoplexus/NCBI
    # quando ViralQC não atribui um. Colunas-chave:
    #   genomeQuality → genome_quality  (A/B = aprovado; C/D = excluído em augur filter)
    #   coverage      → coverage        (filtrado >= min_coverage em augur filter)
    #   clade_col     → clade           (override se ViralQC atribuiu um)
    if args.nextclade and os.path.isfile(args.nextclade):
        nc = pd.read_csv(args.nextclade, sep="\t", dtype=str, keep_default_na=False).fillna("")
        if "seqName" in nc.columns:
            nc_cols = {"seqName": "strain"}
            if clade_col         in nc.columns: nc_cols[clade_col]         = "_nc_clade"
            if "genomeQuality"   in nc.columns: nc_cols["genomeQuality"]   = "_nc_genome_quality"
            if "coverage"        in nc.columns: nc_cols["coverage"]        = "_nc_coverage"
            if "qc.overallStatus" in nc.columns: nc_cols["qc.overallStatus"] = "_nc_qc"
            if "virus"           in nc.columns: nc_cols["virus"]           = "_nc_virus"
            if "segment"         in nc.columns: nc_cols["segment"]         = "_nc_segment"

            nc_sub = nc[list(nc_cols)].rename(columns=nc_cols)
            df = df.merge(nc_sub, on="strain", how="left")

            if "_nc_clade" in df.columns:
                existing = df.get("clade", pd.Series("", index=df.index)).fillna("")
                has_nc_clade = df["_nc_clade"].notna() & (df["_nc_clade"].str.strip() != "")
                df["clade"] = df["_nc_clade"].where(has_nc_clade, existing)
                df.drop(columns=["_nc_clade"], inplace=True)

            if "_nc_genome_quality" in df.columns:
                df["genome_quality"] = df["_nc_genome_quality"].fillna("")
                df.drop(columns=["_nc_genome_quality"], inplace=True)

            if "_nc_qc" in df.columns:
                df["qc_overall_status"] = df["_nc_qc"].fillna("")
                df.drop(columns=["_nc_qc"], inplace=True)

            if "_nc_coverage" in df.columns:
                df["coverage"] = pd.to_numeric(df["_nc_coverage"], errors="coerce")
                df.drop(columns=["_nc_coverage"], inplace=True)

            # ── filter by expected virus / segment (prevents cross-subtype contamination)
            expected_virus   = nc_cfg.get("expected_virus",   None)
            expected_segment = nc_cfg.get("expected_segment", None)

            if "_nc_virus" in df.columns:
                if expected_virus:
                    present      = df["_nc_virus"].str.strip() != ""
                    bad_virus    = present & (df["_nc_virus"].str.strip() != expected_virus)
                    unclassified = present & df["_nc_virus"].str.lower().str.contains("unclassified", na=False)
                    exclude = bad_virus | unclassified
                    n = int(exclude.sum())
                    if n:
                        print(f"Excluding {n} sequences with wrong/unclassified virus (expected: {expected_virus})")
                        if "genome_quality" not in df.columns:
                            df["genome_quality"] = ""
                        df.loc[exclude, "genome_quality"] = "D"
                df.drop(columns=["_nc_virus"], inplace=True)

            if "_nc_segment" in df.columns:
                if expected_segment:
                    present  = df["_nc_segment"].str.strip() != ""
                    bad_seg  = present & (df["_nc_segment"].str.strip() != expected_segment)
                    n = int(bad_seg.sum())
                    if n:
                        print(f"Excluding {n} sequences with wrong segment (expected: {expected_segment})")
                        if "genome_quality" not in df.columns:
                            df["genome_quality"] = ""
                        df.loc[bad_seg, "genome_quality"] = "D"
                df.drop(columns=["_nc_segment"], inplace=True)

    if "genome_quality" not in df.columns:
        df["genome_quality"] = ""
    if "qc_overall_status" not in df.columns:
        df["qc_overall_status"] = ""
    if "coverage" not in df.columns:
        df["coverage"] = float("nan")

    # ── harmonize duplicate columns (PPX field → standard name) ──────────────

    def _merge(df, src, dst):
        """Fill empty dst values from src, then drop src."""
        if src not in df.columns:
            return df
        if dst not in df.columns:
            df[dst] = ""
        src_vals = df[src].fillna("")
        dst_vals = df[dst].fillna("")
        df[dst] = dst_vals.where(dst_vals.str.strip() != "", src_vals)
        df.drop(columns=[src], inplace=True)
        return df

    # coverage: fill PPX rows (NaN) from LAPIS completeness
    if "completeness" in df.columns:
        completeness_num = pd.to_numeric(df["completeness"], errors="coerce")
        df["coverage"] = df["coverage"].where(df["coverage"].notna(), completeness_num)
        df.drop(columns=["completeness"], inplace=True)

    df = _merge(df, "hostNameCommon",          "host")
    df = _merge(df, "hostGender",              "sex")
    df = _merge(df, "hostAge",                 "age")
    df = _merge(df, "author",                  "authors")
    df = _merge(df, "authorAffiliations",      "affiliations")
    df = _merge(df, "specimenCollectorSampleId", "sample_id")
    df = _merge(df, "specimen_id",             "sample_id")
    df = _merge(df, "depthOfCoverage",         "depth_of_coverage")
    df = _merge(df, "sampleType",              "sample_type")
    df = _merge(df, "sequencingInstrument",    "seq_instrument")
    df = _merge(df, "sequencingProtocol",      "seq_tech")

    # ── drop redundant / always-empty columns ─────────────────────────────────
    DROP = {
        # Internal Pathoplexus structure
        "submissionId", "isRevocation", "version", "versionStatus", "versionComment",
        "pipelineVersion", "displayName", "submittedAtTimestamp", "releasedAtTimestamp",
        "groupId", "earliestReleaseDate", "dataBecameOpenAt", "dataUseTermsUrl",
        "dataUseTermsRestrictedUntil",
        # Redundant accessions
        "insdcAccessionFull", "insdcVersion",
        # Redundant host fields (merged above)
        "hostNameScientific", "hostTaxonId",
        # Redundant coverage (merged above)
        "breadthOfCoverage",
        # Geography computed by get_coordinates.py
        "geoLocLatitude", "geoLocLongitude", "geoLocCity", "geoLocSite",
        # Very sparse / low-value LAPIS technical
        "ampliconPcrPrimerScheme", "ampliconSize", "assemblyReferenceGenomeAccession",
        "consensusSequenceSoftwareName", "consensusSequenceSoftwareVersion",
        "collectionDevice", "collectionMethod", "hostRole", "hostVaccinationStatus",
        "isLabHost", "sequencingAssayType",
        # Detailed mutation lists (redundant with counts)
        "frameShifts", "stopCodons",
        "totalDeletedNucs", "totalInsertedNucs", "totalFrameShifts",
        "totalStopCodons", "totalUnknownNucs",
        # NCBI cross-refs (low value, partially filled)
        "ncbiReleaseDate", "ncbiSourceDb", "ncbiUpdateDate",
        "ncbiVirusName", "ncbiVirusTaxId", "ncbiSubmitterCountry", "gcaAccession",
        # ITpS-specific already harmonized or not needed
        "pathogen_common_name", "sample_code",
        "orig_lab_address", "subm_lab_address",
        # Always-empty clinical / environmental fields
        "anatomicalMaterial", "anatomicalPart", "bodyProduct", "cellLine", "comment",
        "cultureId", "dehostingMethod", "diagnosticMeasurementMethod",
        "diagnosticMeasurementUnit", "diagnosticMeasurementValue",
        "diagnosticTargetGeneName", "diagnosticTargetPresence",
        "environmentalMaterial", "environmentalSite", "experimentalSpecimenRoleType",
        "exposureDetails", "exposureEvent", "exposureSetting",
        "foodProduct", "foodProductProperties", "hostAgeBin", "hostDisease",
        "hostHealthOutcome", "hostHealthState", "hostOriginCountry",
        "passageMethod", "passageNumber", "presamplingActivity",
        "previousInfectionDisease", "previousInfectionOrganism",
        "purposeOfSampling", "purposeOfSequencing", "qualityControlDetails",
        "qualityControlDetermination", "qualityControlIssues",
        "qualityControlMethodName", "qualityControlMethodVersion",
        "rawSequenceDataProcessingMethod", "sampleReceivedDate",
        "sequencedByContactEmail", "sequencedByContactName", "sequencedByOrganization",
        "sequencingDate", "signsAndSymptoms", "specimenProcessing",
        "specimenProcessingDetails", "travelHistory", "travel_history",
        # ITpS health fields (no PPX equivalent, very sparse)
        "health_state", "health_outcome", "signs_and_symptoms", "host_disease",
    }
    df.drop(columns=[c for c in DROP if c in df.columns], inplace=True)

    # ── region ────────────────────────────────────────────────────────────────
    if "country" in df.columns:
        df["region"] = df["country"].apply(
            lambda c: REGION_MAP.get(str(c).strip(), "")
        )
        missing = df[df["region"] == ""]["country"].unique()
        if len(missing):
            print(f"WARNING: no region mapping for: {list(missing)}")

    # ── clade_truncated ───────────────────────────────────────────────────────
    if "clade" in df.columns:
        df["clade_truncated"] = df["clade"].apply(
            lambda x: truncate_clade(x, clade_levels, clade_sep) if str(x).strip() else ""
        )

    # ── source ────────────────────────────────────────────────────────────────
    if "source" not in df.columns:
        df["source"] = default_source
    else:
        df["source"] = df["source"].replace("", default_source)

    # ── normalise host ────────────────────────────────────────────────────────
    _HUMAN_RE = re.compile(r'^ho[mn][eo][\s_]?sapien|^hom\s+sapien', re.I)
    _SWINE_RE = re.compile(r'^(sus scrofa|swine|pig|wild boar|feral pig)\b', re.I)
    _AVIAN_RE = re.compile(
        r'^(anas|avian|gallus|duck|turkey|teal|shoveler|anatidae|'
        r'bucephala|calidris|arenaria|microcarbo|charadrius|tringa|'
        r'anser|branta|cygnus|larus|fulica|porzana|grus|cairina)', re.I
    )
    _AVIAN_KW = ('bird', 'duck', 'goose', 'crane', 'waterfowl', 'waterbird',
                 'mallard', 'pintail', 'teal', 'shoveler', 'fowl', 'avian',
                 'heron', 'wader', 'shorebird', 'plover', 'stork', 'spoonbill',
                 'chick', 'quail', 'pigeon', 'dove', 'gull', 'pelican',
                 'cormorant', 'sparrow', 'finch', 'swan')

    def _norm_host(raw: str) -> str:
        s = raw.strip()
        if not s:
            return s
        base = s.split(';')[0].strip()
        bl = base.lower()
        if _HUMAN_RE.match(bl) or bl.startswith('human') or bl.startswith('homosapien') or bl in ('people', 'person'):
            return 'human'
        if _SWINE_RE.match(bl):
            return 'swine'
        if _AVIAN_RE.match(bl) or any(kw in bl for kw in _AVIAN_KW):
            return 'avian'
        if 'mus musculus' in bl or bl in ('mouse', 'house mouse'):
            return 'mouse'
        if 'mustela' in bl or 'neogale' in bl or bl in ('ferret', 'mink'):
            return 'ferret'
        if 'camelus' in bl or bl == 'camel':
            return 'camel'
        if 'mdck' in bl or bl in ('reverse genetics', 'cell line', 'env', 'environmental'):
            return ''
        if "canis lupus" in bl or bl == "canine":
            return "dog"
        return bl

    if "host" in df.columns:
        df["host"] = df["host"].apply(_norm_host)

    # ── rename lab columns to display-friendly names ─────────────────────────
    df.rename(columns={
        "orig_lab_name": "Originating Lab",
        "subm_lab_name": "Submitting Lab",
    }, inplace=True)

    # ── normalise data_use to uppercase (OPEN / RESTRICTED) ───────────────────
    if "data_use" in df.columns:
        df["data_use"] = df["data_use"].str.strip().str.upper()

    # ── dedup ─────────────────────────────────────────────────────────────────
    before = len(df)
    df = df.drop_duplicates("strain")
    if len(df) < before:
        print(f"Deduplication: {before} → {len(df)}")

    df.to_csv(args.output, sep="\t", index=False)
    print(f"Output: {len(df)} rows → {args.output}")


if __name__ == "__main__":
    main()
