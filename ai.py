import random
from typing import Any, Dict, List, Optional


def choose_chancellor(game_state: Dict[str, Any], role: str, known_fascists: List[str]) -> Optional[str]:
    eligible = list(game_state.get("eligible_chancellors") or [])
    if not eligible:
        return None

    fascist_policies = int(game_state.get("fascist_policies", 0))
    hitler_id = game_state.get("hitler_id")
    suspicion = game_state.get("suspicion", {})

    if role == "fascist" and fascist_policies >= 3 and hitler_id in eligible:
        return hitler_id

    if role in ("fascist", "hitler"):
        for fid in known_fascists:
            if fid in eligible:
                return fid

    eligible.sort(key=lambda pid: suspicion.get(pid, 0))
    return eligible[0]


def vote_government(game_state: Dict[str, Any], role: str, known_fascists: List[str]) -> bool:
    nominee_id = game_state.get("nominee_id")
    president_id = game_state.get("president_id")
    suspicion = game_state.get("suspicion", {})

    if role in ("fascist", "hitler"):
        if nominee_id in known_fascists or president_id in known_fascists:
            return True
        if role == "fascist" and game_state.get("fascist_policies", 0) >= 3:
            if nominee_id == game_state.get("hitler_id"):
                return True
        return random.random() < 0.6

    if nominee_id and suspicion.get(nominee_id, 0) > 1:
        return False
    return True


def choose_president_discard(policies: List[str], role: str) -> int:
    if role in ("fascist", "hitler"):
        for idx, policy in enumerate(policies):
            if policy == "liberal":
                return idx
    else:
        for idx, policy in enumerate(policies):
            if policy == "fascist":
                return idx
    return random.randrange(len(policies))


def choose_chancellor_enact(policies: List[str], role: str) -> int:
    if role in ("fascist", "hitler"):
        for idx, policy in enumerate(policies):
            if policy == "fascist":
                return idx
    else:
        for idx, policy in enumerate(policies):
            if policy == "liberal":
                return idx
    return random.randrange(len(policies))


def request_veto(policies: List[str], role: str) -> bool:
    if role in ("fascist", "hitler"):
        return all(policy == "liberal" for policy in policies)
    return all(policy == "fascist" for policy in policies)


def approve_veto(policies: List[str], role: str) -> bool:
    if role in ("fascist", "hitler"):
        return all(policy == "liberal" for policy in policies)
    return all(policy == "fascist" for policy in policies)


def choose_investigation_target(game_state: Dict[str, Any], role: str, known_fascists: List[str]) -> Optional[str]:
    alive = list(game_state.get("alive_ids") or [])
    president_id = game_state.get("president_id")
    suspicion = game_state.get("suspicion", {})
    candidates = [pid for pid in alive if pid != president_id]
    if not candidates:
        return None

    if role in ("fascist", "hitler"):
        candidates = [pid for pid in candidates if pid not in known_fascists]
        if not candidates:
            candidates = [pid for pid in alive if pid != president_id]
        return random.choice(candidates)

    candidates.sort(key=lambda pid: suspicion.get(pid, 0), reverse=True)
    return candidates[0]


def choose_execution_target(game_state: Dict[str, Any], role: str, known_fascists: List[str]) -> Optional[str]:
    alive = list(game_state.get("alive_ids") or [])
    president_id = game_state.get("president_id")
    suspicion = game_state.get("suspicion", {})
    candidates = [pid for pid in alive if pid != president_id]
    if not candidates:
        return None

    if role in ("fascist", "hitler"):
        candidates = [pid for pid in candidates if pid not in known_fascists]
        if not candidates:
            candidates = [pid for pid in alive if pid != president_id]
        return random.choice(candidates)

    candidates.sort(key=lambda pid: suspicion.get(pid, 0), reverse=True)
    return candidates[0]


def choose_special_election_target(game_state: Dict[str, Any], role: str, known_fascists: List[str]) -> Optional[str]:
    alive = list(game_state.get("alive_ids") or [])
    president_id = game_state.get("president_id")
    candidates = [pid for pid in alive if pid != president_id]
    if not candidates:
        return None

    hitler_id = game_state.get("hitler_id")
    if role == "fascist" and hitler_id in candidates:
        return hitler_id
    if role in ("fascist", "hitler"):
        for fid in known_fascists:
            if fid in candidates:
                return fid
    return random.choice(candidates)
