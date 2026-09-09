import streamlit as st
import pandas as pd
import tempfile
import Project
import auth
import db

st.set_page_config(page_title="Lineup", layout="wide")

team_id = auth.require_login()

if "page" not in st.session_state:
    st.session_state.page = "home"

col1, col2 = st.columns([1, 10])

with col1:
    if st.button("🏠"):
        st.switch_page("app.py")

st.title("🚣 Lineup")

# ---------- Constants ----------
AUTO_OPTION = "-- Auto --"
CALLER_PLACEHOLDER = "-- Select Caller --"
STEER_PLACEHOLDER = "-- Select Steer --"


def dataframe_to_temp_csv(df: pd.DataFrame) -> str:
    tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".csv")
    df.to_csv(tmp.name, index=False)
    return tmp.name


def get_unique_paddler_names(paddlers):
    unique_name_map = {}
    for p in paddlers:
        key = Project.canonical_name(p.name)
        if key not in unique_name_map:
            unique_name_map[key] = p.name
    return sorted(list(unique_name_map.values()), key=str.lower)


def get_used_names(n_seats: int, exclude_key: str | None = None):
    used = set()

    caller_val = st.session_state.get("caller_role", CALLER_PLACEHOLDER)
    steer_val = st.session_state.get("steer_role", STEER_PLACEHOLDER)

    if exclude_key != "caller_role" and caller_val not in {CALLER_PLACEHOLDER, "", None}:
        used.add(caller_val)

    if exclude_key != "steer_role" and steer_val not in {STEER_PLACEHOLDER, "", None}:
        used.add(steer_val)

    for seat_num in range(1, n_seats + 1):
        key = f"seat_{seat_num}"
        if key == exclude_key:
            continue
        val = st.session_state.get(key, AUTO_OPTION)
        if val not in {AUTO_OPTION, "", None}:
            used.add(val)

    return used


def build_select_options(all_names, used_names, current_value, placeholder):
    options = [placeholder]
    for name in all_names:
        if name == current_value or name not in used_names:
            options.append(name)
    return options


def build_locked_from_seat_dropdowns(n_seats: int):
    locked = []
    for seat_num in range(1, n_seats + 1):
        val = st.session_state.get(f"seat_{seat_num}", AUTO_OPTION)
        if val not in {AUTO_OPTION, "", None}:
            locked.append({
                "name": val,
                "seat": seat_num
            })
    return locked


def parse_max_lr_diff(raw: str):
    raw = raw.strip().lower()
    if raw in {"", "null", "none", "no limit"}:
        return None
    return float(raw)


def render_boat(best, seats, caller="", steer=""):
    rows = {}
    for s in seats:
        r = Project.row_of_seat(s.idx)
        rows.setdefault(r, {})
        rows[r][s.side] = best[s.idx]

    st.markdown('<div class="section-title">Boat Lineup</div>', unsafe_allow_html=True)

    if caller:
        _, mid, _ = st.columns([1, 2, 1])
        with mid:
            st.markdown(
                f'<div class="role-pill bow-pill">🚩 <span>Caller:</span> {caller}</div>',
                unsafe_allow_html=True
            )

    for r in sorted(rows.keys()):
        spacer_l, left_col, right_col, spacer_r = st.columns([1, 2, 2, 1])

        left = rows[r].get("L")
        right = rows[r].get("R")

        left_text = "-" if not left else f"{left.name} ({left.gender})"
        right_text = "-" if not right else f"{right.name} ({right.gender})"

        with left_col:
            st.markdown(
                f"""
                <div class="seat-box seat-left">
                    <div class="seat-title">Bench {r} Left</div>
                    <div class="seat-value">{left_text}</div>
                </div>
                """,
                unsafe_allow_html=True
            )

        with right_col:
            st.markdown(
                f"""
                <div class="seat-box seat-right">
                    <div class="seat-title">Bench {r} Right</div>
                    <div class="seat-value">{right_text}</div>
                </div>
                """,
                unsafe_allow_html=True
            )

    if steer:
        _, mid2, _ = st.columns([1, 2, 1])
        with mid2:
            st.markdown(
                f'<div class="role-pill stern-pill">🛶 <span>Steer :</span> {steer}</div>',
                unsafe_allow_html=True
            )


# ---------- CSS ----------
st.markdown("""
<style>
.block-container {
    max-width: 1100px;
    padding-top: 3rem;
    padding-bottom: 2rem;
    padding-left: 1rem;
    padding-right: 1rem;
}

[data-testid="collapsedControl"] {
    display: none;
}

.section-title {
    font-size: 2rem;
    font-weight: 800;
    color: #222637;
    margin: 0.4rem 0 1rem 0;
    letter-spacing: -0.5px;
}

div[data-testid="stMetric"] {
    background: linear-gradient(180deg, #ffffff 0%, #fbfcff 100%);
    border: 1px solid #e3e7f0;
    padding: 14px 16px;
    border-radius: 20px;
    box-shadow: 0 8px 22px rgba(30, 41, 59, 0.05);
}

div[data-testid="stMetricLabel"] {
    font-weight: 700;
    color: #5f6779;
}

div[data-testid="stMetricValue"] {
    font-weight: 800;
    color: #202433;
}

.role-pill {
    text-align: center;
    padding: 0.9rem 1rem;
    border-radius: 18px;
    border: 1px solid #e4e8f1;
    font-size: 1.15rem;
    font-weight: 700;
    margin: 0.5rem 0 1rem 0;
    box-shadow: 0 6px 18px rgba(30, 41, 59, 0.04);
}

.role-pill span {
    color: #4c5568;
    margin-right: 0.25rem;
}

.bow-pill {
    background: linear-gradient(180deg, #eef7ff 0%, #f8fbff 100%);
    color: #224f86;
}

.stern-pill {
    background: linear-gradient(180deg, #f4f7ff 0%, #fbfcff 100%);
    color: #314f87;
}

.seat-box {
    background: linear-gradient(180deg, #ffffff 0%, #f9fbff 100%);
    border: 1px solid #e4e8f1;
    border-radius: 18px;
    padding: 0.95rem 1rem;
    margin: 0.4rem 0;
    box-shadow: 0 6px 18px rgba(30, 41, 59, 0.04);
}

.seat-left {
    border-left: 6px solid #7aa8ef;
}

.seat-right {
    border-left: 6px solid #8cc9bb;
}

.seat-title {
    font-size: 0.95rem;
    font-weight: 700;
    color: #667085;
    margin-bottom: 0.3rem;
}

.seat-value {
    font-size: 1.05rem;
    font-weight: 700;
    color: #1f2a44;
    line-height: 1.35;
}

[data-baseweb="tag"] {
    background-color: #e0f2fe !important;
    color: #0369a1 !important;
    border-radius: 10px !important;
}
</style>
""", unsafe_allow_html=True)

# ---------- Data ----------
best_df = db.load_best_scores(team_id)
st.session_state["best_scores_df"] = best_df
merged_df = st.session_state.get("merged_df")

source_df = best_df if best_df is not None and not best_df.empty else merged_df

if source_df is None or source_df.empty:
    st.warning("Please upload data first.")
    st.stop()

source_df = source_df.copy()
source_df.columns = [c.strip().lower() for c in source_df.columns]
source_df = source_df.loc[:, ~source_df.columns.str.contains(r"^unnamed", case=False, regex=True)]

# ⭐ 先建立 csv_path，後面 eligible paddlers 會用到
csv_path = dataframe_to_temp_csv(source_df)

# ---------- Session defaults ----------
if "lineup_initialized" not in st.session_state:
    saved_config = db.load_team_settings(team_id).get("lineup_config") or {}
    st.session_state["n_seats"] = saved_config.get("n_seats", 0)
    st.session_state["male_count"] = saved_config.get("exact_male", 0)
    st.session_state["female_count"] = saved_config.get("exact_female", 0)
    st.session_state["caller_role"] = CALLER_PLACEHOLDER
    st.session_state["steer_role"] = STEER_PLACEHOLDER
    st.session_state["lineup_initialized"] = True

for i in range(1, 21):
    key = f"seat_{i}"
    if key not in st.session_state:
        st.session_state[key] = AUTO_OPTION

# ---------- Reset defaults ----------
reset_col1, reset_col2 = st.columns([1, 5])

with reset_col1:
    if st.button("Reset Defaults"):
        st.session_state["n_seats"] = 20
        st.session_state["male_count"] = 12
        st.session_state["female_count"] = 8
        st.session_state["caller_role"] = CALLER_PLACEHOLDER
        st.session_state["steer_role"] = STEER_PLACEHOLDER
        st.session_state["eligible_paddlers"] = []

        for i in range(1, 21):
            st.session_state[f"seat_{i}"] = AUTO_OPTION

        st.rerun()

# ---------- Eligible paddlers ----------
st.divider()
st.subheader("Eligible Paddlers")
st.caption("Select the paddlers to include in this lineup.")

all_paddlers = Project.read_paddlers_csv(csv_path)
all_paddler_names = get_unique_paddler_names(all_paddlers)

if "eligible_paddlers" not in st.session_state:
    st.session_state["eligible_paddlers"] = []

btn_col1, btn_col2 = st.columns(2)

with btn_col1:
    if st.button("Select All Eligible", key="select_all_eligible"):
        st.session_state["eligible_paddlers"] = all_paddler_names.copy()
        st.rerun()

with btn_col2:
    if st.button("Clear Eligible Selection", key="clear_eligible"):
        st.session_state["eligible_paddlers"] = []
        st.rerun()

eligible_names = st.multiselect(
    "Choose paddlers for this lineup",
    options=all_paddler_names,
    default=st.session_state["eligible_paddlers"],
    key="eligible_paddlers"
)

if not eligible_names:
    st.info("Select paddlers for this lineup.")
    st.stop()

paddlers = [p for p in all_paddlers if p.name in eligible_names]
paddlers_names = get_unique_paddler_names(paddlers)

selected_males = sum(
    1 for p in paddlers if str(p.gender).strip().lower() in {"male", "m"}
)
selected_females = sum(
    1 for p in paddlers if str(p.gender).strip().lower() in {"female", "f"}
)

st.caption(
    f"Selected paddlers: {len(paddlers)} "
    f"(Male: {selected_males}, Female: {selected_females})"
)

# ---------- Settings ----------
left_col, right_col = st.columns(2)

with left_col:
    st.subheader("Boat Settings")

    n_seats = st.number_input(
        "Number of paddler seats (required)",
        min_value=0,
        max_value=20,
        step=2,
        key="n_seats",
    )

    if st.session_state["male_count"] + st.session_state["female_count"] > st.session_state["n_seats"]:
        overflow = (
            st.session_state["male_count"]
            + st.session_state["female_count"]
            - st.session_state["n_seats"]
        )
        st.session_state["female_count"] = max(0, st.session_state["female_count"] - overflow)

    exact_male = st.number_input(
        "Male paddlers (required)",
        min_value=0,
        max_value=int(st.session_state["n_seats"] - st.session_state["female_count"]),
        step=1,
        key="male_count",
    )

    exact_female = st.number_input(
        "Female paddlers (required)",
        min_value=0,
        max_value=int(st.session_state["n_seats"] - st.session_state["male_count"]),
        step=1,
        key="female_count",
    )

    st.caption(
        f"Current total paddlers: "
        f"{st.session_state['male_count'] + st.session_state['female_count']} / {st.session_state['n_seats']}"
    )

    #max_lr_diff_raw = st.text_input("Max left-right weight diff (kg)", value="")

with right_col:
    st.subheader("Optimization Settings")

    max_engine_row = max(1, int(n_seats // 2))

    engine_start = st.number_input(
        "Engine row start",
        min_value=1,
        max_value=max_engine_row,
        value=min(3, max_engine_row),
    )

    engine_end = st.number_input(
        "Engine row end",
        min_value=int(engine_start),
        max_value=max_engine_row,
        value=min(max(8, int(engine_start)), max_engine_row),
    )

st.divider()
st.subheader("Roles")

caller_current = st.session_state.get("caller_role", CALLER_PLACEHOLDER)
caller_used = get_used_names(int(n_seats), exclude_key="caller_role")
caller_options = build_select_options(
    paddlers_names,
    caller_used,
    caller_current,
    CALLER_PLACEHOLDER
)

caller = st.selectbox(
    "Caller (required)",
    caller_options,
    key="caller_role",
)

for row in range(1, int(n_seats // 2) + 1):
    left_seat = row * 2 - 1
    right_seat = row * 2

    c1, c2 = st.columns(2)

    with c1:
        left_key = f"seat_{left_seat}"
        left_current = st.session_state.get(left_key, AUTO_OPTION)

        caller_val = st.session_state.get("caller_role", CALLER_PLACEHOLDER)
        steer_val = st.session_state.get("steer_role", STEER_PLACEHOLDER)

        if left_current in {caller_val, steer_val}:
            st.session_state[left_key] = AUTO_OPTION
            left_current = AUTO_OPTION

        left_used = get_used_names(int(n_seats), exclude_key=left_key)
        left_options = build_select_options(
            paddlers_names,
            left_used,
            left_current,
            AUTO_OPTION
        )

        st.selectbox(
            f"Bench {row} Left",
            left_options,
            key=left_key,
        )

    with c2:
        right_key = f"seat_{right_seat}"
        right_current = st.session_state.get(right_key, AUTO_OPTION)

        caller_val = st.session_state.get("caller_role", CALLER_PLACEHOLDER)
        steer_val = st.session_state.get("steer_role", STEER_PLACEHOLDER)

        if right_current in {caller_val, steer_val}:
            st.session_state[right_key] = AUTO_OPTION
            right_current = AUTO_OPTION

        right_used = get_used_names(int(n_seats), exclude_key=right_key)
        right_options = build_select_options(
            paddlers_names,
            right_used,
            right_current,
            AUTO_OPTION
        )

        st.selectbox(
            f"Bench {row} Right",
            right_options,
            key=right_key,
        )

steer_current = st.session_state.get("steer_role", STEER_PLACEHOLDER)
steer_used = get_used_names(int(n_seats), exclude_key="steer_role")
steer_options = build_select_options(
    paddlers_names,
    steer_used,
    steer_current,
    STEER_PLACEHOLDER
)

steer = st.selectbox(
    "Steer (required)",
    steer_options,
    key="steer_role",
)

generate = st.button("Generate Lineup")
if generate:

    if n_seats == 0:
        st.error("Please select number of paddler seats.")
        st.stop()

    if exact_male == 0:
        st.error("Please enter number of male paddlers.")
        st.stop()

    if exact_female == 0:
        st.error("Please enter number of female paddlers.")
        st.stop()

    if exact_male + exact_female != n_seats:
        st.error("Male paddlers + Female paddlers must equal total seats.")
        st.stop()

    max_lr_diff = None
# ---------- Generate ----------
if generate:
    if len(paddlers) < n_seats + 2:
        st.error("Not enough selected paddlers. Caller and Steer are separate from paddler seats.")
        st.stop()

    if selected_males < exact_male:
        st.error("Not enough selected male paddlers for the requested lineup.")
        st.stop()

    if selected_females < exact_female:
        st.error("Not enough selected female paddlers for the requested lineup.")
        st.stop()

    if caller in {"", CALLER_PLACEHOLDER} or steer in {"", STEER_PLACEHOLDER}:
        st.error("Caller and Steer must be specified.")
        st.stop()

    if caller == steer:
        st.error("Caller and Steer cannot be the same person.")
        st.stop()

    if exact_male + exact_female != n_seats:
        st.error("Male paddlers + Female paddlers must equal total paddler seats.")
        st.stop()

    locked = build_locked_from_seat_dropdowns(int(n_seats))
    #max_lr_diff = parse_max_lr_diff(max_lr_diff_raw)
    max_lr_diff = None

    config = {
        "n_seats": int(n_seats),
        "exact_male": int(exact_male),
        "exact_female": int(exact_female),
        "max_lr_diff": max_lr_diff,
        "engine_rows": [int(engine_start), int(engine_end)],
        "caller": caller,
        "steer": steer,
        "locked": locked,
        "weights": {
            "stern_heavier_bonus": 0.15,
            "pitch_gap": 1.0,
            "side_pref": 1.0,
        },
    }

    excluded_names = {
        Project.canonical_name(caller),
        Project.canonical_name(steer),
    }

    paddlers_for_opt = [
        p for p in paddlers
        if Project.canonical_name(p.name) not in excluded_names
    ]

    power = Project.normalize_power(paddlers_for_opt)

    try:
        best, best_score, seats = Project.optimize(
            paddlers_for_opt,
            config,
            iterations=50000,
            seed=42,
        )
    except ValueError as e:
        st.error(f"Could not generate a lineup with the current settings:\n\n{e}")
        st.stop()

    db.save_lineup_config(team_id, config)

    st.success("Lineup generated.")

    summary = Project.summarize(best, seats, power)

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Best Score", f"{best_score:.2f}")
    c2.metric("Left and Right Different", f"{summary.get('lr_diff', 0):.2f}")
    c3.metric("Power Different", f"{summary.get('power_diff', 0):.2f}")
    c4.metric("Stern - Bow", f"{summary.get('stern_minus_bow', 0):.2f}")

    st.divider()

    render_boat(best, seats, caller=caller, steer=steer)

    st.divider()

    st.subheader("Summary")

    summary_df = pd.DataFrame([
        {"Metric": "Total", "Value": summary.get("total")},
        {"Metric": "Unique People", "Value": summary.get("unique_people")},
        {"Metric": "Females", "Value": summary.get("females")},
        {"Metric": "Males", "Value": summary.get("males")},
        {"Metric": "Left Weight", "Value": f"{summary.get('left_weight', 0):.2f}"},
        {"Metric": "Right Weight", "Value": f"{summary.get('right_weight', 0):.2f}"},
        {"Metric": "Left and Right Different", "Value": f"{summary.get('lr_diff', 0):.2f}"},
        {"Metric": "Left Power", "Value": f"{summary.get('left_power', 0):.2f}"},
        {"Metric": "Right Power", "Value": f"{summary.get('right_power', 0):.2f}"},
        {"Metric": "Power Different", "Value": f"{summary.get('power_diff', 0):.2f}"},
        {"Metric": "Bow Weight", "Value": f"{summary.get('bow_weight', 0):.2f}"},
        {"Metric": "Stern Weight", "Value": f"{summary.get('stern_weight', 0):.2f}"},
        {"Metric": "Stern Minus Bow", "Value": f"{summary.get('stern_minus_bow', 0):.2f}"},
    ])

    st.dataframe(summary_df, use_container_width=True, hide_index=True)
