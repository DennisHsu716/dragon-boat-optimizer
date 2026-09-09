import streamlit as st
import pandas as pd
from decimal import Decimal, getcontext

import auth
import db
from safe_eval import safe_eval, FormulaError

st.set_page_config(page_title="Upload Data", layout="wide")
getcontext().prec = 28

team_id = auth.require_login()

# ---------- Home ----------
col1, col2 = st.columns([1, 10])
with col1:
    if st.button("🏠", key="upload_home"):
        st.switch_page("app.py")

st.title("📂 Upload Data")
st.write("Upload roster/score CSV, or enter score data manually.")

# ---------- Settings defaults (shared per-team, from Formula Settings) ----------
DEFAULT_FORMULA = "((272.2 + 48.888)/(weight + 48.888))**0.1666 * time_trial"

team_settings = db.load_team_settings(team_id)
formula_mode = team_settings["formula_mode"]
custom_test_type = team_settings["custom_test_type"]
race_distance_m = team_settings["race_distance_m"]
custom_formula = team_settings["custom_formula"] or DEFAULT_FORMULA

# ---------- Helpers ----------
def normalize_columns(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    df.columns = [str(c).strip().lower() for c in df.columns]
    return df

def drop_unnamed(df: pd.DataFrame) -> pd.DataFrame:
    return df.loc[:, ~df.columns.str.contains(r"^unnamed", case=False, regex=True)].copy()

def standardize_known_columns(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()

    rename_map = {}

    if "time trial results" in df.columns:
        rename_map["time trial results"] = "time_trial"
    if "time trial" in df.columns:
        rename_map["time trial"] = "time_trial"
    if "time_trial_results" in df.columns:
        rename_map["time_trial_results"] = "time_trial"

    if "distance at 1:00" in df.columns:
        rename_map["distance at 1:00"] = "distance"
    if "distance at 1:00 " in df.columns:
        rename_map["distance at 1:00 "] = "distance"
    if "distance_1min" in df.columns:
        rename_map["distance_1min"] = "distance"

    if "side" in df.columns:
        rename_map["side"] = "side_pref"

    df = df.rename(columns=rename_map)
    return df

def parse_time_to_seconds(value):
    if pd.isna(value):
        return None

    s = str(value).strip()
    if s == "":
        return None

    # 先試純數字
    try:
        return float(s)
    except ValueError:
        pass

    # 支援 mm:ss 或 mm:ss.s
    if ":" in s:
        parts = s.split(":")
        if len(parts) == 2:
            try:
                minutes = float(parts[0])
                seconds = float(parts[1])
                return minutes * 60 + seconds
            except ValueError:
                return None

    return None

def parse_distance(value):
    if pd.isna(value):
        return None

    s = str(value).strip()
    if s == "":
        return None

    try:
        return float(s)
    except ValueError:
        return None

def compute_adj_default_time(weight, time_trial):
    weight = Decimal(str(weight))
    time_trial = Decimal(str(time_trial))
    numerator = Decimal("272.2") + Decimal("48.888")
    denominator = weight + Decimal("48.888")
    ratio = numerator / denominator
    return float((ratio ** Decimal("0.1666")) * time_trial)

def compute_adj_default_distance(weight, distance):
    # 預設 distance-based 公式
    weight = float(weight)
    distance = float(distance)
    return float(distance * (weight / 160.0) ** 0.12)

def compute_adj_from_settings(row: pd.Series):
    weight = row.get("weight", None)
    time_trial = row.get("time_trial", None)
    distance = row.get("distance", None)
    race_distance = race_distance_m

    if pd.isna(weight) or weight is None:
        return None

    if formula_mode == "default":
        if custom_test_type == "time":
            if pd.isna(time_trial) or time_trial is None:
                return None
            return compute_adj_default_time(weight, time_trial)

        if custom_test_type == "distance":
            if pd.isna(distance) or distance is None:
                return None
            return compute_adj_default_distance(weight, distance)

    if formula_mode == "custom":
        safe_vars = {
            "weight": float(weight) if weight is not None and not pd.isna(weight) else None,
            "time_trial": float(time_trial) if time_trial is not None and not pd.isna(time_trial) else None,
            "distance": float(distance) if distance is not None and not pd.isna(distance) else None,
            "race_distance": float(race_distance),
        }

        try:
            return safe_eval(custom_formula, safe_vars)
        except FormulaError:
            return None

    return None

def empty_manual_scores_df() -> pd.DataFrame:
    return pd.DataFrame(
        columns=[
            "date",
            "name",
            "gender",
            "weight",
            "side_pref",
            "time_trial",
            "distance",
            "adj",
        ]
    )

def append_manual_entry_to_session(new_row: dict):
    if "manual_scores_df" not in st.session_state:
        st.session_state["manual_scores_df"] = empty_manual_scores_df()

    df = st.session_state["manual_scores_df"].copy()
    df = pd.concat([df, pd.DataFrame([new_row])], ignore_index=True)
    st.session_state["manual_scores_df"] = df

def save_rank_data(df_to_save: pd.DataFrame):
    lower_is_better = custom_test_type == "time"
    best_scores_df = db.upsert_scores(team_id, df_to_save, lower_is_better=lower_is_better)

    st.session_state["score_df"] = df_to_save.copy()
    st.session_state["merged_df"] = df_to_save.copy()
    st.session_state["master_df"] = df_to_save.copy()
    st.session_state["best_scores_df"] = best_scores_df.copy()

    return best_scores_df

# ---------- Session init ----------
if "manual_scores_df" not in st.session_state:
    st.session_state["manual_scores_df"] = empty_manual_scores_df()

if "best_scores_df" not in st.session_state:
    st.session_state["best_scores_df"] = None

if "merged_df" not in st.session_state:
    st.session_state["merged_df"] = None

if "score_df" not in st.session_state:
    st.session_state["score_df"] = None

if "master_df" not in st.session_state:
    st.session_state["master_df"] = None

# ---------- Upload CSV ----------
st.subheader("Upload CSV")

upload_file = st.file_uploader(
    "Upload roster / score CSV",
    type=["csv"],
    key="roster_upload"
)

upload_df = st.session_state.get("roster_df", None)
roster_names = []

if upload_file is not None:
    try:
        upload_df = pd.read_csv(upload_file)
        upload_df = normalize_columns(upload_df)
        upload_df = drop_unnamed(upload_df)
        upload_df = standardize_known_columns(upload_df)

        # normalize columns
        if "weight" in upload_df.columns:
            upload_df["weight"] = pd.to_numeric(upload_df["weight"], errors="coerce")

        if "time_trial" in upload_df.columns:
            upload_df["time_trial"] = upload_df["time_trial"].apply(parse_time_to_seconds)

        if "distance" in upload_df.columns:
            upload_df["distance"] = upload_df["distance"].apply(parse_distance)

        if "adj" in upload_df.columns:
            upload_df["adj"] = upload_df["adj"].apply(parse_time_to_seconds)

        st.session_state["roster_df"] = upload_df.copy()

        # 1) already has adj -> direct save
        score_required = {"name", "gender", "side_pref", "adj"}
        if score_required.issubset(set(upload_df.columns)) and upload_df["adj"].notna().any():
            best_scores_df = save_rank_data(upload_df)
            st.success(f"Score CSV uploaded and saved to the team database.")

        # 2) no adj, but enough data to compute
        elif {"name", "gender", "weight", "side_pref"}.issubset(set(upload_df.columns)):
            if custom_test_type == "time" and "time_trial" in upload_df.columns:
                upload_df["adj"] = upload_df.apply(compute_adj_from_settings, axis=1)
                upload_df = upload_df.dropna(subset=["adj"]).copy()

                if upload_df.empty:
                    st.error("No valid rows found after computing time-based adjusted scores.")
                else:
                    best_scores_df = save_rank_data(upload_df)
                    st.success(f"Time-based CSV uploaded and saved to the team database.")

            elif custom_test_type == "distance" and "distance" in upload_df.columns:
                upload_df["adj"] = upload_df.apply(compute_adj_from_settings, axis=1)
                upload_df = upload_df.dropna(subset=["adj"]).copy()

                if upload_df.empty:
                    st.error("No valid rows found after computing distance-based adjusted scores.")
                else:
                    best_scores_df = save_rank_data(upload_df)
                    st.success(f"Distance-based CSV uploaded and saved to the team database.")
            else:
                st.success("Roster uploaded.")

        else:
            st.success("Roster uploaded.")

    except Exception as e:
        st.error(f"Failed to read roster CSV: {e}")
        upload_df = None

if upload_df is not None:
    if "name" in upload_df.columns:
        roster_names = sorted(
            upload_df["name"].dropna().astype(str).unique().tolist(),
            key=str.lower
        )

    st.subheader("Roster Preview")
    st.dataframe(upload_df, use_container_width=True, hide_index=True)
else:
    st.info("Upload a roster/score CSV first. You can still open the manual entry section below.")

# ---------- Manual input ----------
st.divider()
st.subheader("Manual Input")

with st.expander("Click to enter score data", expanded=False):
    st.write("Fill in the fields from top to bottom. Adjusted score will be calculated automatically.")

    date_val = st.text_input(
        "Date of TT",
        placeholder="e.g. 3/14/26",
        key="manual_date"
    )

    if roster_names:
        name_mode = st.radio(
            "Name input method",
            ["Select from roster", "Type manually"],
            horizontal=True,
            key="name_mode"
        )

        if name_mode == "Select from roster":
            name_val = st.selectbox(
                "Name",
                [""] + roster_names,
                key="manual_name_select"
            )
        else:
            name_val = st.text_input(
                "Name",
                key="manual_name_text"
            )
    else:
        name_val = st.text_input(
            "Name (Please enter the full name)",
            key="manual_name_text_only"
        )

    gender_val = st.selectbox(
        "Gender",
        ["", "Male", "Female"],
        key="manual_gender"
    )

    weight_val = st.number_input(
        "Weight (Weight should be taken directly before or after the test)",
        min_value=0.0,
        step=0.1,
        value=None,
        placeholder="Enter paddler weight in pounds (example: 150)",
        key="manual_weight"
    )

    side_val = st.selectbox(
        "Side",
        ["", "left", "right"],
        key="manual_side"
    )

    if custom_test_type == "time":
        time_trial_val = st.text_input(
            "Time Trial",
            placeholder="Example: 168.7 or 02:48.7",
            key="manual_time_trial"
        )
        distance_val = None
    else:
        distance_val = st.number_input(
            "Distance",
            min_value=0.0,
            step=1.0,
            value=None,
            placeholder="Example: 430",
            key="manual_distance"
        )
        time_trial_val = None

    if st.button("Add Entry", use_container_width=True, key="add_manual_entry"):
        if not date_val:
            st.error("Please enter date.")
            st.stop()

        if not name_val:
            st.error("Please enter/select name.")
            st.stop()

        if not gender_val:
            st.error("Please select gender.")
            st.stop()

        if weight_val is None or weight_val <= 0:
            st.error("Weight must be greater than 0.")
            st.stop()

        if not side_val:
            st.error("Please select side.")
            st.stop()

        if custom_test_type == "time":
            parsed_time = parse_time_to_seconds(time_trial_val)
            if parsed_time is None or parsed_time <= 0:
                st.error("Time Trial must be a valid number of seconds or mm:ss format.")
                st.stop()
            time_trial_val = parsed_time
        else:
            if distance_val is None or distance_val <= 0:
                st.error("Distance must be greater than 0.")
                st.stop()

        row_for_calc = pd.Series({
            "weight": float(weight_val),
            "time_trial": float(time_trial_val) if time_trial_val is not None else None,
            "distance": float(distance_val) if distance_val is not None else None,
        })

        adj_val = compute_adj_from_settings(row_for_calc)

        if adj_val is None:
            st.error("Unable to compute adjusted score with current settings.")
            st.stop()

        new_row = {
            "date": date_val,
            "name": str(name_val).strip(),
            "gender": gender_val,
            "weight": float(weight_val),
            "side_pref": side_val,
            "time_trial": float(time_trial_val) if time_trial_val is not None else None,
            "distance": float(distance_val) if distance_val is not None else None,
            "adj": float(adj_val),
        }

        append_manual_entry_to_session(new_row)
        st.success("Entry added.")
        st.rerun()

# ---------- Show current manual entries ----------
manual_score_df = st.session_state.get("manual_scores_df", empty_manual_scores_df())

if not manual_score_df.empty:
    st.subheader("Current Manual Entries")
    st.dataframe(manual_score_df, use_container_width=True, hide_index=True)

    col_a, col_b = st.columns([1, 1])

    with col_a:
        if st.button("Clear All Entries", use_container_width=True, key="clear_manual_entries"):
            st.session_state["manual_scores_df"] = empty_manual_scores_df()
            st.rerun()

    with col_b:
        if st.button("Save Manual Scores", use_container_width=True, key="save_manual_scores"):
            try:
                best_scores_df = save_rank_data(manual_score_df)
                st.success("Manual scores saved to the team database.")
                st.rerun()
            except Exception as e:
                st.error(f"Saving manual scores failed: {e}")
else:
    st.info("No manual entries yet.")