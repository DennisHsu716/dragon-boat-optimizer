import streamlit as st
import pandas as pd

import auth
import db

st.set_page_config(page_title="Rank", layout="wide")

team_id = auth.require_login()

if "page" not in st.session_state:
    st.session_state.page = "home"

col1, col2 = st.columns([1, 10])

with col1:
    if st.button("🏠", key="rank_home"):
        st.switch_page("app.py")

st.title("🏁 Rank")

best_df = db.load_best_scores(team_id)
st.session_state["best_scores_df"] = best_df

source_df = best_df

if source_df is None or source_df.empty:
    st.warning("No saved best scores yet. Please upload data first.")
    st.stop()

df = source_df.copy()
df.columns = [c.strip().lower() for c in df.columns]
df = df.loc[:, ~df.columns.str.contains(r"^unnamed", case=False, regex=True)]

required_cols = {"name", "gender", "side_pref", "adj"}
missing = required_cols - set(df.columns)
if missing:
    st.error(f"Missing required columns for ranking: {missing}")
    st.stop()

df["gender"] = df["gender"].astype(str).str.strip().str.lower()
df["side_pref"] = df["side_pref"].astype(str).str.strip().str.lower()
df["adj"] = pd.to_numeric(df["adj"], errors="coerce")
df["time_trial"] = pd.to_numeric(df["time_trial"], errors="coerce") if "time_trial" in df.columns else None
df = df.dropna(subset=["adj"])

if "date" not in df.columns:
    df["date"] = ""

if "time_trial" not in df.columns:
    df["time_trial"] = None


def normalize_gender(x: str):
    x = str(x).strip().lower()
    if x in {"male", "m"}:
        return "Male"
    if x in {"female", "f"}:
        return "Female"
    return x


def normalize_side(x: str):
    x = str(x).strip().lower()
    if x in {"left", "l"}:
        return "Left"
    if x in {"right", "r"}:
        return "Right"
    return x


def get_rank_sort_ascending():
    test_type = st.session_state.get("custom_test_type", "time")
    return True if test_type == "time" else False


def format_result_value(x, as_time: bool):
    if pd.isna(x) or x is None:
        return ""

    x = float(x)

    if not as_time:
        return f"{x:.2f}"

    minutes = int(x // 60)
    seconds = x - minutes * 60

    if abs(seconds - round(seconds)) < 1e-9:
        return f"{minutes}:{int(round(seconds)):02d}"

    return f"{minutes}:{seconds:04.1f}"


df["gender"] = df["gender"].map(normalize_gender)
df["side_pref"] = df["side_pref"].map(normalize_side)


def build_rank_table(data: pd.DataFrame, side: str, gender: str, title: str):
    sub = data[
        (data["side_pref"] == side) &
        (data["gender"] == gender)
    ].copy()

    is_time_based = st.session_state.get("custom_test_type", "time") == "time"
    ascending = get_rank_sort_ascending()

    sub = sub.sort_values(by="adj", ascending=ascending).reset_index(drop=True)
    sub["Rank"] = range(1, len(sub) + 1)

    sub["Date"] = sub["date"]
    sub["Name"] = sub["name"]
    sub["Side"] = sub["side_pref"]
    sub["Time Trial Results"] = sub["time_trial"].map(lambda x: format_result_value(x, is_time_based))

    adjusted_col_name = "Adjusted Time" if is_time_based else "Adjusted Score"
    sub[adjusted_col_name] = sub["adj"].map(lambda x: format_result_value(x, is_time_based))

    sub = sub[
        [
            "Rank",
            "Date",
            "Name",
            "Side",
            "Time Trial Results",
            adjusted_col_name,
        ]
    ]

    st.subheader(title)
    st.dataframe(sub, use_container_width=True, hide_index=True)

    return sub


col1, col2 = st.columns(2)
col3, col4 = st.columns(2)

with col1:
    left_male_df = build_rank_table(df, "Left", "Male", "Left Male Rank")

with col2:
    left_female_df = build_rank_table(df, "Left", "Female", "Left Female Rank")

with col3:
    right_male_df = build_rank_table(df, "Right", "Male", "Right Male Rank")

with col4:
    right_female_df = build_rank_table(df, "Right", "Female", "Right Female Rank")

download_df = pd.concat(
    [
        left_male_df.assign(Group="Left Male"),
        left_female_df.assign(Group="Left Female"),
        right_male_df.assign(Group="Right Male"),
        right_female_df.assign(Group="Right Female"),
    ],
    ignore_index=True
)

csv_bytes = download_df.to_csv(index=False).encode("utf-8")
st.download_button(
    "Download All Rankings CSV",
    data=csv_bytes,
    file_name="four_group_rankings.csv",
    mime="text/csv"
)

st.write("")

with st.expander("🗑 Delete All Saved Rankings"):
    st.warning(
        f"This permanently deletes **all** saved scores for team "
        f"**{auth.current_team_name()}**. This cannot be undone."
    )
    confirm_delete = st.checkbox(
        "I understand this will delete all rankings for my team.",
        key="confirm_delete_rankings",
    )
    if st.button("Confirm Delete", type="secondary", disabled=not confirm_delete):
        db.delete_team_scores(team_id)

        keys_to_clear = [
            "best_scores_df",
            "merged_df",
            "score_df",
            "master_df",
            "manual_scores_df",
            "roster_df",
            "uploaded_score_df",
            "uploaded_roster_df",
            "confirm_delete_rankings",
        ]

        for key in keys_to_clear:
            if key in st.session_state:
                del st.session_state[key]

        st.success("All saved rankings have been deleted.")
        st.rerun()