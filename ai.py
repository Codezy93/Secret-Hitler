import random
from typing import Any, Dict, List, Optional


def choose_chancellor(game_state: Dict[str, Any], role: str, known_fascists: List[str]) -> Optional[str]:
    """AI chooses a chancellor nominee from eligible candidates."""
    eligible = list(game_state.get("eligible_chancellors") or [])
    if not eligible:
        return None

    fascist_policies = int(game_state.get("fascist_policies", 0))
    hitler_id = game_state.get("hitler_id")
    suspicion = game_state.get("suspicion", {})

    # Fascist: try to get Hitler elected once 3+ fascist policies are enacted
    if role == "fascist" and fascist_policies >= 3 and hitler_id in eligible:
        return hitler_id

    # Fascist/Hitler: prefer known allies, but not too obviously
    if role in ("fascist", "hitler"):
        allies = [fid for fid in known_fascists if fid in eligible]
        # Don't always pick allies — occasionally pick someone else to avoid suspicion
        if allies and random.random() < 0.7:
            return random.choice(allies)
        # Pick least suspicious eligible player to seem trustworthy
        eligible.sort(key=lambda pid: suspicion.get(pid, 0))
        return eligible[0]

    # Liberal: pick least suspicious player
    eligible.sort(key=lambda pid: suspicion.get(pid, 0))
    return eligible[0]


def vote_government(game_state: Dict[str, Any], role: str, known_fascists: List[str]) -> bool:
    """AI votes on the proposed government."""
    nominee_id = game_state.get("nominee_id")
    president_id = game_state.get("president_id")
    suspicion = game_state.get("suspicion", {})
    election_tracker = int(game_state.get("election_tracker", 0))

    # If tracker is at 2, everyone tends to vote yes to avoid anarchy
    if election_tracker >= 2:
        if role in ("fascist", "hitler"):
            return True
        return random.random() < 0.75

    if role in ("fascist", "hitler"):
        # Vote yes if ally is involved
        if nominee_id in known_fascists or president_id in known_fascists:
            return True
        # Fascist: vote yes to get Hitler elected
        if role == "fascist" and game_state.get("fascist_policies", 0) >= 3:
            if nominee_id == game_state.get("hitler_id"):
                return True
        # Sometimes vote no to seem liberal
        return random.random() < 0.5

    # Liberal logic
    nominee_sus = suspicion.get(nominee_id, 0)
    president_sus = suspicion.get(president_id, 0)

    # If both are suspicious, vote no
    if nominee_sus > 1 and president_sus > 1:
        return False
    # If nominee is very suspicious, vote no
    if nominee_sus > 2:
        return False
    # Generally vote yes
    return random.random() < 0.8


def choose_president_discard(policies: List[str], role: str) -> int:
    """AI president chooses which policy to discard (0, 1, or 2)."""
    if role in ("fascist", "hitler"):
        # Fascist: discard liberal policies, but sometimes "accidentally" discard fascist
        # to build trust
        liberal_indices = [i for i, p in enumerate(policies) if p == "liberal"]
        fascist_indices = [i for i, p in enumerate(policies) if p == "fascist"]

        if liberal_indices:
            # Hitler is more cautious — sometimes passes liberal to avoid suspicion
            if role == "hitler" and len(liberal_indices) >= 2 and random.random() < 0.3:
                return random.choice(fascist_indices) if fascist_indices else liberal_indices[0]
            return random.choice(liberal_indices)
        return random.randrange(len(policies))
    else:
        # Liberal: discard fascist policies
        fascist_indices = [i for i, p in enumerate(policies) if p == "fascist"]
        if fascist_indices:
            return random.choice(fascist_indices)
        # All liberal — discard random
        return random.randrange(len(policies))


def choose_chancellor_enact(policies: List[str], role: str) -> int:
    """AI chancellor chooses which policy to enact (0 or 1)."""
    if role in ("fascist", "hitler"):
        fascist_indices = [i for i, p in enumerate(policies) if p == "fascist"]
        # Hitler is more cautious early on
        if role == "hitler" and random.random() < 0.25:
            liberal_indices = [i for i, p in enumerate(policies) if p == "liberal"]
            if liberal_indices:
                return liberal_indices[0]
        if fascist_indices:
            return fascist_indices[0]
        return random.randrange(len(policies))
    else:
        liberal_indices = [i for i, p in enumerate(policies) if p == "liberal"]
        if liberal_indices:
            return liberal_indices[0]
        return random.randrange(len(policies))


def request_veto(policies: List[str], role: str) -> bool:
    """AI chancellor decides whether to request a veto."""
    if role in ("fascist", "hitler"):
        # Veto if all policies are liberal (don't want to enact them)
        return all(p == "liberal" for p in policies)
    # Liberal: veto if all fascist
    return all(p == "fascist" for p in policies)


def approve_veto(policies: List[str], role: str) -> bool:
    """AI president decides whether to approve a veto request."""
    if role in ("fascist", "hitler"):
        return all(p == "liberal" for p in policies)
    return all(p == "fascist" for p in policies)


def choose_investigation_target(game_state: Dict[str, Any], role: str, known_fascists: List[str]) -> Optional[str]:
    """AI president chooses who to investigate."""
    alive = list(game_state.get("alive_ids") or [])
    president_id = game_state.get("president_id")
    investigated = set(game_state.get("investigated") or [])
    suspicion = game_state.get("suspicion", {})
    candidates = [pid for pid in alive if pid != president_id and pid not in investigated]
    if not candidates:
        return None

    if role in ("fascist", "hitler"):
        # Don't investigate known fascists — investigate a liberal to "clear" them
        # or to gain false information
        safe = [pid for pid in candidates if pid not in known_fascists]
        if safe:
            return random.choice(safe)
        return random.choice(candidates)

    # Liberal: investigate most suspicious player
    candidates.sort(key=lambda pid: suspicion.get(pid, 0), reverse=True)
    return candidates[0]


def choose_execution_target(game_state: Dict[str, Any], role: str, known_fascists: List[str]) -> Optional[str]:
    """AI president chooses who to execute."""
    alive = list(game_state.get("alive_ids") or [])
    president_id = game_state.get("president_id")
    suspicion = game_state.get("suspicion", {})
    candidates = [pid for pid in alive if pid != president_id]
    if not candidates:
        return None

    if role in ("fascist", "hitler"):
        # Don't execute fellow fascists — execute a liberal
        safe = [pid for pid in candidates if pid not in known_fascists]
        if safe:
            # Target most trusted liberal (hurts liberals more)
            safe.sort(key=lambda pid: suspicion.get(pid, 0))
            return safe[0]
        return random.choice(candidates)

    # Liberal: execute most suspicious player
    candidates.sort(key=lambda pid: suspicion.get(pid, 0), reverse=True)
    return candidates[0]


def choose_special_election_target(game_state: Dict[str, Any], role: str, known_fascists: List[str]) -> Optional[str]:
    """AI president chooses next president for special election."""
    alive = list(game_state.get("alive_ids") or [])
    president_id = game_state.get("president_id")
    suspicion = game_state.get("suspicion", {})
    candidates = [pid for pid in alive if pid != president_id]
    if not candidates:
        return None

    hitler_id = game_state.get("hitler_id")

    if role == "fascist":
        # Try to get Hitler into power
        if hitler_id in candidates:
            return hitler_id
        # Otherwise pick a fellow fascist
        for fid in known_fascists:
            if fid in candidates:
                return fid

    if role == "hitler":
        # Pick a known fascist ally
        for fid in known_fascists:
            if fid in candidates:
                return fid

    if role in ("fascist", "hitler"):
        # Pick least suspicious candidate
        candidates.sort(key=lambda pid: suspicion.get(pid, 0))
        return candidates[0]

    # Liberal: pick a trusted player
    candidates.sort(key=lambda pid: suspicion.get(pid, 0))
    return candidates[0]
