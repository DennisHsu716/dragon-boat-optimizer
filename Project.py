from __future__ import annotations
import csv
import json
import math
import random
from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple


# -----------------------------
# Data classes
# -----------------------------
@dataclass(frozen=True)
class Paddler:
    name: str
    time_trial: float
    gender: str          # internal: "M" / "F"
    weight: float
    side_pref: str       # internal: "L" / "R" / "B"
    adj: Optional[float] = None


@dataclass(frozen=True)
class Seat:
    idx: int
    side: str            # "L" if odd seat, "R" if even seat


# -----------------------------
# Normalization helpers
# -----------------------------
def canonical_name(value: str) -> str:
    return " ".join(value.strip().lower().split())


def normalize_gender(value: str) -> str:
    v = value.strip().lower()
    if v in {"male", "m"}:
        return "M"
    if v in {"female", "f"}:
        return "F"
    raise ValueError(f"Invalid gender value: {value}")


def normalize_side_pref(value: str) -> str:
    v = value.strip().lower()
    if v in {"left", "l"}:
        return "L"
    if v in {"right", "r"}:
        return "R"
    if v in {"both", "b", "any", ""}:
        return "B"
    raise ValueError(f"Invalid side_pref value: {value}")


# -----------------------------
# IO
# -----------------------------
def read_paddlers_csv(path: str) -> List[Paddler]:
    paddlers: List[Paddler] = []

    with open(path, "r", newline="", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)

        if not reader.fieldnames:
            raise ValueError("CSV is empty or missing header row.")

        reader.fieldnames = [h.strip().lower() for h in reader.fieldnames]

        required = {"name", "gender", "weight", "side_pref"}
        missing = required - set(reader.fieldnames)
        if missing:
            raise ValueError(f"CSV missing columns: {missing}. Required: {sorted(required)}")

        has_time_trial = "time_trial" in reader.fieldnames
        has_adj = "adj" in reader.fieldnames

        if not has_time_trial and not has_adj:
            raise ValueError("CSV must contain at least one of: time_trial or adj")

        for row in reader:
            # skip fully blank rows
            if not any((v or "").strip() for v in row.values()):
                continue

            name = (row.get("name") or "").strip()
            if not name:
                continue

            gender = normalize_gender(row["gender"])
            weight = float(row["weight"])
            side_pref = normalize_side_pref(row["side_pref"])

            time_trial = 9999.0
            if has_time_trial and (row.get("time_trial") or "").strip():
                time_trial = float(row["time_trial"])

            adj = None
            if has_adj and (row.get("adj") or "").strip():
                adj = float(row["adj"])

            paddlers.append(
                Paddler(
                    name=name,
                    time_trial=time_trial,
                    gender=gender,
                    weight=weight,
                    side_pref=side_pref,
                    adj=adj,
                )
            )

    if not paddlers:
        raise ValueError("No valid paddlers found in CSV.")

    return paddlers


def read_config(path: Optional[str]) -> dict:
    if not path:
        return {}
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


# -----------------------------
# Seat model
# -----------------------------
def build_seats(n_seats: int) -> List[Seat]:
    if n_seats % 2 != 0:
        raise ValueError("n_seats must be even.")
    return [Seat(i, "L" if i % 2 == 1 else "R") for i in range(1, n_seats + 1)]


def row_of_seat(seat_idx: int) -> int:
    return (seat_idx + 1) // 2


def seat_power_weight(seat_idx: int, n_seats: int, engine_rows: Tuple[int, int]) -> float:
    r = row_of_seat(seat_idx)
    n_rows = n_seats // 2
    lo, hi = engine_rows

    if lo <= r <= hi:
        return 1.6
    if r == lo - 1 or r == hi + 1:
        return 1.25
    if r <= max(2, n_rows // 5):
        return 1.10
    if r >= n_rows - max(1, n_rows // 6):
        return 1.15
    return 1.0


# -----------------------------
# Validation
# -----------------------------
def get_unique_people(paddlers: List[Paddler]) -> Dict[str, List[Paddler]]:
    grouped: Dict[str, List[Paddler]] = {}
    for p in paddlers:
        grouped.setdefault(canonical_name(p.name), []).append(p)
    return grouped


def validate_paddlers(
    paddlers: List[Paddler],
    n_seats: int,
    exact_male: Optional[int],
    exact_female: Optional[int],
) -> None:
    grouped = get_unique_people(paddlers)
    unique_people = [options[0] for options in grouped.values()]

    if len(unique_people) < n_seats:
        raise ValueError(f"Not enough unique paddlers: need {n_seats}, got {len(unique_people)}")

    male_count = sum(1 for p in unique_people if p.gender == "M")
    female_count = sum(1 for p in unique_people if p.gender == "F")

    print("\n=== Roster Check ===")
    print(f"Unique paddlers: {len(unique_people)}")
    print(f"Male: {male_count}")
    print(f"Female: {female_count}")

    left_only = sum(1 for p in paddlers if p.side_pref == "L")
    right_only = sum(1 for p in paddlers if p.side_pref == "R")
    both = sum(1 for p in paddlers if p.side_pref == "B")

    print(f"Left only: {left_only}")
    print(f"Right only: {right_only}")
    print(f"Both: {both}")

    if exact_male is not None and male_count < exact_male:
        raise ValueError(f"Not enough male paddlers: need {exact_male}, got {male_count}")

    if exact_female is not None and female_count < exact_female:
        raise ValueError(f"Not enough female paddlers: need {exact_female}, got {female_count}")


# -----------------------------
# Power scoring
# -----------------------------
def normalize_power(paddlers: List[Paddler]) -> Dict[Tuple[str, str], float]:
    raw: Dict[Tuple[str, str], float] = {}

    for p in paddlers:
        key = (canonical_name(p.name), p.side_pref)
        if p.adj is not None:
            raw[key] = p.adj
        else:
            raw[key] = 1.0 / max(1e-9, p.time_trial)

    mean = sum(raw.values()) / max(1, len(raw))
    return {k: v / mean for k, v in raw.items()}


# -----------------------------
# Constraints
# -----------------------------
def check_exact_gender_constraint(
    assignment: Dict[int, Paddler],
    seats: List[Seat],
    exact_female: Optional[int],
    exact_male: Optional[int],
) -> bool:
    females = sum(1 for s in seats if assignment[s.idx].gender == "F")
    males = sum(1 for s in seats if assignment[s.idx].gender == "M")

    if exact_female is not None and females != exact_female:
        return False
    if exact_male is not None and males != exact_male:
        return False
    return True


def check_roll_constraint(
    assignment: Dict[int, Paddler],
    seats: List[Seat],
    max_lr_diff: Optional[float],
) -> bool:
    if max_lr_diff is None:
        return True
    left_w = sum(assignment[s.idx].weight for s in seats if s.side == "L")
    right_w = sum(assignment[s.idx].weight for s in seats if s.side == "R")
    return abs(left_w - right_w) <= max_lr_diff


def check_unique_people_constraint(
    assignment: Dict[int, Paddler],
    seats: List[Seat],
) -> bool:
    chosen = [canonical_name(assignment[s.idx].name) for s in seats]
    return len(chosen) == len(set(chosen))


# -----------------------------
# Locked seats
# -----------------------------
def apply_locks(
    paddlers: List[Paddler],
    seats: List[Seat],
    locked: List[dict],
    caller: Optional[str] = None,
    steer: Optional[str] = None,
) -> Tuple[Dict[int, Paddler], List[Paddler], set]:
    grouped = get_unique_people(paddlers)
    base_assignment: Dict[int, Paddler] = {}
    locked_seats = set()
    used_names = set()
    excluded_names = set()
    if caller:
        excluded_names.add(canonical_name(caller))
    if steer:
        excluded_names.add(canonical_name(steer))

    for item in locked or []:
        raw_name = str(item["name"]).strip()
        name_key = canonical_name(raw_name)
        if name_key in excluded_names:
            raise ValueError(
                f"{raw_name} is caller/steer and cannot also be locked as paddler."
            )
        seat = int(item["seat"])

        if seat < 1 or seat > len(seats):
            raise ValueError(f"Locked seat out of range: {seat}")

        seat_side = "L" if seat % 2 == 1 else "R"

        if name_key not in grouped:
            raise ValueError(f"Locked paddler not found in CSV: {raw_name}")
        if name_key in used_names:
            raise ValueError(f"Paddler locked twice: {raw_name}")
        if seat in locked_seats:
            raise ValueError(f"Seat locked twice: {seat}")

        candidates = grouped[name_key]
        compatible = [p for p in candidates if p.side_pref in {seat_side, "B"}]
        if not compatible:
            raise ValueError(f"No compatible candidate for locked paddler {raw_name} on side {seat_side}")

        # choose best compatible candidate
        compatible.sort(key=lambda p: (-(p.adj if p.adj is not None else -1), p.time_trial))
        chosen = compatible[0]

        base_assignment[seat] = chosen
        locked_seats.add(seat)
        used_names.add(name_key)

    remaining = [p for p in paddlers if canonical_name(p.name) not in used_names]
    return base_assignment, remaining, locked_seats


# -----------------------------
# Initial assignment
# -----------------------------
def choose_best_candidate_for_seat(
    seat: Seat,
    grouped: Dict[str, List[Paddler]],
    used_names: set,
) -> Optional[Paddler]:
    best = None
    best_rank = None

    for name_key, options in grouped.items():
        if name_key in used_names:
            continue

        compatible = [p for p in options if p.side_pref in {seat.side, "B"}]
        if not compatible:
            continue

        compatible.sort(key=lambda p: (-(p.adj if p.adj is not None else float("-inf")), p.time_trial))
        candidate = compatible[0]

        rank = (-(candidate.adj if candidate.adj is not None else float("-inf")), candidate.time_trial)
        if best is None or rank < best_rank:
            best = candidate
            best_rank = rank

    return best

def build_feasible_initial_assignment(
    seats: List[Seat],
    base_assignment: Dict[int, Paddler],
    remaining_paddlers: List[Paddler],
    exact_male: Optional[int],
    exact_female: Optional[int],
) -> Dict[int, Paddler]:
    grouped = get_unique_people(remaining_paddlers)
    assignment = dict(base_assignment)
    used_names = {canonical_name(p.name) for p in base_assignment.values()}

    locked_males = sum(1 for p in base_assignment.values() if p.gender == "M")
    locked_females = sum(1 for p in base_assignment.values() if p.gender == "F")

    need_males = 0 if exact_male is None else exact_male - locked_males
    need_females = 0 if exact_female is None else exact_female - locked_females

    unlocked_seats = [s for s in seats if s.idx not in assignment]

    # 候選人依 seat side 過濾
    seat_candidates: Dict[int, List[Paddler]] = {}
    for seat in unlocked_seats:
        candidates = []
        for name_key, options in grouped.items():
            if name_key in used_names:
                continue
            for p in options:
                if p.side_pref in {seat.side, "B"}:
                    candidates.append(p)

        # 先讓強的人排前面，回溯會比較快
        candidates.sort(
            key=lambda p: (-(p.adj if p.adj is not None else (1.0 / max(1e-9, p.time_trial)))),
            reverse=False
        )
        seat_candidates[seat.idx] = candidates

    # 最難的 seat 先放
    unlocked_seats.sort(key=lambda s: len(seat_candidates[s.idx]))

    def backtrack(i: int, males_left: int, females_left: int) -> bool:
        if i == len(unlocked_seats):
            return males_left == 0 and females_left == 0

        seat = unlocked_seats[i]

        # 剩下 seat 數量不足以滿足 gender quota，直接剪枝
        seats_left = len(unlocked_seats) - i
        if males_left + females_left > seats_left:
            return False
        if males_left < 0 or females_left < 0:
            return False

        for p in seat_candidates[seat.idx]:
            name_key = canonical_name(p.name)
            if name_key in used_names:
                continue

            if p.gender == "M" and males_left <= 0:
                continue
            if p.gender == "F" and females_left <= 0:
                continue

            assignment[seat.idx] = p
            used_names.add(name_key)

            next_m = males_left - 1 if p.gender == "M" else males_left
            next_f = females_left - 1 if p.gender == "F" else females_left

            if backtrack(i + 1, next_m, next_f):
                return True

            del assignment[seat.idx]
            used_names.remove(name_key)

        return False

    ok = backtrack(0, need_males, need_females)
    if not ok:
        raise ValueError("Unable to construct a feasible initial assignment.")

    return assignment


def make_initial_assignment(
    seats: List[Seat],
    base_assignment: Dict[int, Paddler],
    remaining_paddlers: List[Paddler],
    exact_male: Optional[int],
    exact_female: Optional[int],
) -> Dict[int, Paddler]:
    return build_feasible_initial_assignment(
        seats=seats,
        base_assignment=base_assignment,
        remaining_paddlers=remaining_paddlers,
        exact_male=exact_male,
        exact_female=exact_female,
    )


# -----------------------------
# Scoring
# -----------------------------
def score_assignment(
    assignment: Dict[int, Paddler],
    seats: List[Seat],
    power: Dict[Tuple[str, str], float],
    *,
    engine_rows: Tuple[int, int],
    exact_female: Optional[int],
    exact_male: Optional[int],
    max_lr_diff: Optional[float],
    stern_heavier_bonus_w: float,
    w_pitch_gap: float,
    w_sidepref: float,
    hard_penalty: float = 1e9,
) -> float:
    if not check_unique_people_constraint(assignment, seats):
        return -hard_penalty

    if not check_exact_gender_constraint(assignment, seats, exact_female, exact_male):
        return -hard_penalty

    if not check_roll_constraint(assignment, seats, max_lr_diff):
        return -hard_penalty

    n_seats = len(seats)
    n_rows = n_seats // 2

    perf = 0.0
    for s in seats:
        p = assignment[s.idx]
        key = (canonical_name(p.name), p.side_pref)
        perf += power[key] * seat_power_weight(s.idx, n_seats, engine_rows)

    left_w = sum(assignment[s.idx].weight for s in seats if s.side == "L")
    right_w = sum(assignment[s.idx].weight for s in seats if s.side == "R")
    lr_diff = abs(left_w - right_w)
    left_power = sum(
        power[(canonical_name(assignment[s.idx].name), assignment[s.idx].side_pref)]
        for s in seats if s.side == "L")
    right_power = sum(
        power[(canonical_name(assignment[s.idx].name), assignment[s.idx].side_pref)]
        for s in seats if s.side == "R")
    power_diff = abs(left_power - right_power)

    bow_rows = set(range(1, n_rows // 2 + 1))
    bow_w = sum(assignment[s.idx].weight for s in seats if row_of_seat(s.idx) in bow_rows)
    stern_w = sum(assignment[s.idx].weight for s in seats if row_of_seat(s.idx) not in bow_rows)

    stern_minus_bow = stern_w - bow_w
    stern_bonus = stern_heavier_bonus_w * stern_minus_bow

    if stern_minus_bow <= 0:
        pitch_pen = w_pitch_gap * abs(stern_minus_bow) * 3.0
    else:
        pitch_pen = w_pitch_gap * (1.0 / max(1.0, stern_minus_bow))

    side_pen = 0.0
    for s in seats:
        p = assignment[s.idx]
        if p.side_pref in {"L", "R"} and p.side_pref != s.side:
            side_pen += 10.0

    return perf + stern_bonus - lr_diff - pitch_pen - w_sidepref * side_pen - 20.0 * power_diff


# -----------------------------
# Optimization
# -----------------------------
def optimize(
    paddlers: List[Paddler],
    config: dict,
    *,
    iterations: int = 120000,
    start_temp: float = 1.0,
    end_temp: float = 0.01,
    seed: int = 42,
) -> Tuple[Dict[int, Paddler], float, List[Seat]]:
    random.seed(seed)

    n_seats = int(config.get("n_seats", 20))
    seats = build_seats(n_seats)
    power = normalize_power(paddlers)

    engine_rows = tuple(config.get("engine_rows", [3, 8]))
    engine_rows = (int(engine_rows[0]), int(engine_rows[1]))

    exact_female = config.get("exact_female", 8)
    exact_male = config.get("exact_male", 12)
    exact_female = None if exact_female is None else int(exact_female)
    exact_male = None if exact_male is None else int(exact_male)

    max_lr_diff = config.get("max_lr_diff", 5.0)
    max_lr_diff = None if max_lr_diff is None else float(max_lr_diff)

    weights = config.get("weights", {}) or {}
    stern_heavier_bonus_w = float(weights.get("stern_heavier_bonus", 0.15))
    w_pitch_gap = float(weights.get("pitch_gap", 1.0))
    w_sidepref = float(weights.get("side_pref", 1.0))

    validate_paddlers(paddlers, n_seats, exact_male, exact_female)

    base_assignment, remaining_paddlers, locked_seats = apply_locks(
    paddlers,
    seats,
    config.get("locked", []),
    caller=config.get("caller"),
    steer=config.get("steer"),
    )

    current = None
    current_score = -1e18

    for _ in range(200):
        try:
            trial_assignment = make_initial_assignment(
                seats,
                base_assignment,
                remaining_paddlers,
                exact_male=exact_male,
                exact_female=exact_female,
            )
        except ValueError:
            continue

        trial_score = score_assignment(
            trial_assignment,
            seats,
            power,
            engine_rows=engine_rows,
            exact_female=exact_female,
            exact_male=exact_male,
            max_lr_diff=max_lr_diff,
            stern_heavier_bonus_w=stern_heavier_bonus_w,
            w_pitch_gap=w_pitch_gap,
            w_sidepref=w_sidepref,
        )

        if trial_score > current_score:
            current = trial_assignment
            current_score = trial_score

    if current is None or current_score <= -1e8:
        left_only = sum(1 for p in paddlers if p.side_pref == "L")
        right_only = sum(1 for p in paddlers if p.side_pref == "R")
        both = sum(1 for p in paddlers if p.side_pref == "B")

        raise ValueError(
            f"No feasible lineup found.\n"
            f"Roster: male={sum(1 for p in get_unique_people(paddlers).values() if p[0].gender == 'M')}, "
            f"female={sum(1 for p in get_unique_people(paddlers).values() if p[0].gender == 'F')}\n"
            f"Side options: left_only={left_only}, right_only={right_only}, both={both}\n"
            f"Config: exact_male={exact_male}, exact_female={exact_female}, max_lr_diff={max_lr_diff}, locked={len(config.get('locked', []))}"
        )

    best = dict(current)
    best_score = current_score

    unlocked = [s.idx for s in seats if s.idx not in locked_seats]
    if len(unlocked) < 2:
        return best, best_score, seats

    for t in range(iterations):
        alpha = t / max(1, iterations - 1)
        temp = start_temp * ((end_temp / start_temp) ** alpha)

        a, b = random.sample(unlocked, 2)
        new_assign = dict(current)
        new_assign[a], new_assign[b] = new_assign[b], new_assign[a]

        new_score = score_assignment(
            new_assign,
            seats,
            power,
            engine_rows=engine_rows,
            exact_female=exact_female,
            exact_male=exact_male,
            max_lr_diff=max_lr_diff,
            stern_heavier_bonus_w=stern_heavier_bonus_w,
            w_pitch_gap=w_pitch_gap,
            w_sidepref=w_sidepref,
        )

        delta = new_score - current_score
        if delta >= 0 or random.random() < math.exp(delta / max(1e-9, temp)):
            current = new_assign
            current_score = new_score

            if new_score > best_score:
                best = dict(new_assign)
                best_score = new_score

    return best, best_score, seats


# -----------------------------
# Reporting
# -----------------------------
def summarize(assignment: Dict[int, Paddler], seats: List[Seat], power: Dict[str, float]) -> dict:
    left_w = sum(assignment[s.idx].weight for s in seats if s.side == "L")
    right_w = sum(assignment[s.idx].weight for s in seats if s.side == "R")
    left_power = sum(
    power[(canonical_name(assignment[s.idx].name), assignment[s.idx].side_pref)]
    for s in seats if s.side == "L")
    right_power = sum(
        power[(canonical_name(assignment[s.idx].name), assignment[s.idx].side_pref)]
        for s in seats if s.side == "R")
    power_diff = abs(left_power - right_power)

    n_rows = len(seats) // 2
    bow_rows = set(range(1, n_rows // 2 + 1))
    bow_w = sum(assignment[s.idx].weight for s in seats if row_of_seat(s.idx) in bow_rows)
    stern_w = sum(assignment[s.idx].weight for s in seats if row_of_seat(s.idx) not in bow_rows)

    females = sum(1 for s in seats if assignment[s.idx].gender == "F")
    males = sum(1 for s in seats if assignment[s.idx].gender == "M")

    return {
    "total": len(seats),
    "unique_people": len(set(p.name for p in assignment.values())),
    "females": females,
    "males": males,
    "left_weight": left_w,
    "right_weight": right_w,
    "lr_diff": abs(left_w - right_w),
    "left_power": left_power,
    "right_power": right_power,
    "power_diff": power_diff,
    "bow_weight": bow_w,
    "stern_weight": stern_w,
    "stern_minus_bow": stern_w - bow_w,
    }


def print_plan(assignment: Dict[int, Paddler], seats: List[Seat], config: dict) -> None:
    print("\nCaller (Bow):", config.get("caller", "None"))
    rows: Dict[int, Dict[str, Paddler]] = {}
    for s in seats:
        rows.setdefault(row_of_seat(s.idx), {})
        rows[row_of_seat(s.idx)][s.side] = assignment[s.idx]

    print("\n=== Seat Plan (Bow -> Stern) ===")
    print("Row | Left (odd seat)                      | Right (even seat)")
    print("-" * 78)

    def fmt(p: Optional[Paddler]) -> str:
        if not p:
            return "-"
        return f"{p.name} ({p.gender})"

    for r in sorted(rows.keys()):
        lp = rows[r].get("L")
        rp = rows[r].get("R")
        print(f"{r:>3} | {fmt(lp):34} | {fmt(rp):34}")
    
    print("\nSteer (Stern):", config.get("steer", "None"))


# -----------------------------
# CLI
# -----------------------------
def main():
    import argparse

    parser = argparse.ArgumentParser("Dragon boat seating optimizer")
    parser.add_argument("--csv", required=True, help="paddlers.csv")
    parser.add_argument("--config", default="", help="config.json (optional)")
    parser.add_argument("--iters", type=int, default=120000)
    parser.add_argument("--seed", type=int, default=42)
    args = parser.parse_args()

    paddlers = read_paddlers_csv(args.csv)
    config = read_config(args.config) if args.config else {}
    power = normalize_power(paddlers)

    excluded_names = set()
    if config.get("caller"):
        excluded_names.add(canonical_name(config["caller"]))
    if config.get("steer"):
        excluded_names.add(canonical_name(config["steer"]))

    paddlers = [p for p in paddlers if canonical_name(p.name) not in excluded_names]

    best, best_score, seats = optimize(
        paddlers,
        config,
        iterations=args.iters,
        seed=args.seed,
    )

    print(f"\nBest score: {best_score:.4f}")
    print_plan(best, seats, config)

    s = summarize(best, seats, power)
    print("\n=== Summary ===")
    for k, v in s.items():
        if isinstance(v, float):
            print(f"{k:>18}: {v:.2f}")
        else:
            print(f"{k:>18}: {v}")


if __name__ == "__main__":
    main()