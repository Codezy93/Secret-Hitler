import os
import random
import string
import secrets
from dataclasses import dataclass, field
from typing import Dict

from flask import Flask, render_template, request, redirect, url_for, session, flash, jsonify

from ai import (
    approve_veto,
    choose_chancellor,
    choose_chancellor_enact,
    choose_execution_target,
    choose_investigation_target,
    choose_president_discard,
    choose_special_election_target,
    request_veto,
    vote_government,
)

app = Flask(__name__)
app.secret_key = os.getenv("SECRET_KEY", secrets.token_hex(32))

# In-memory game store (perfectly fine for LAN + single server process)
# If you restart the server, games reset.
GAMES: Dict[str, dict] = {}
MAX_PLAYERS = 10
AI_NAMES = [
    "Avery", "Blake", "Casey", "Drew", "Emery",
    "Finley", "Gray", "Harper", "Indigo", "Jules",
    "Kai", "Logan", "Micah", "Nico", "Oak",
    "Parker", "Quinn", "Reese", "Sawyer", "Tate",
    "Wren", "Zion"
]

ROLE_COUNTS = {
    5: {"liberal": 3, "fascist": 1, "hitler": 1},
    6: {"liberal": 4, "fascist": 1, "hitler": 1},
    7: {"liberal": 4, "fascist": 2, "hitler": 1},
    8: {"liberal": 5, "fascist": 2, "hitler": 1},
    9: {"liberal": 5, "fascist": 3, "hitler": 1},
    10: {"liberal": 6, "fascist": 3, "hitler": 1},
}

FASCIST_POWERS = {
    "5-6": [None, None, "policy_peek", "execution", "execution"],
    "7-8": [None, "investigate", "special_election", "execution", "execution"],
    "9-10": ["investigate", "investigate", "special_election", "execution", "execution"],
}


def gen_8_digit_code() -> str:
    # Digits only, exactly 8 chars
    return "".join(random.choice(string.digits) for _ in range(8))


def create_unique_code() -> str:
    for _ in range(50):
        code = gen_8_digit_code()
        if code not in GAMES:
            return code
    # Fallback (extremely unlikely)
    while True:
        code = gen_8_digit_code()
        if code not in GAMES:
            return code


def ensure_player_id() -> str:
    if "player_id" not in session:
        session["player_id"] = secrets.token_urlsafe(12)
    return session["player_id"]


def default_player_name() -> str:
    return f"Player {random.randint(100, 999)}"


def build_deck() -> list:
    deck = ["liberal"] * 6 + ["fascist"] * 11
    random.shuffle(deck)
    return deck


def assign_roles(player_ids: list) -> dict:
    count = len(player_ids)
    dist = ROLE_COUNTS.get(count)
    if not dist:
        raise ValueError(f"Unsupported player count: {count}")
    roles = (["liberal"] * dist["liberal"]) + (["fascist"] * dist["fascist"]) + ["hitler"]
    random.shuffle(roles)
    return {pid: role for pid, role in zip(player_ids, roles)}


def party_for_role(role: str) -> str:
    return "fascist" if role in ("fascist", "hitler") else "liberal"


def hitler_id(game: dict) -> str | None:
    return next((pid for pid, r in game.get("roles", {}).items() if r == "hitler"), None)


def is_ai_player(game: dict, pid: str) -> bool:
    return bool(game.get("players", {}).get(pid, {}).get("is_ai"))


def is_alive(game: dict, pid: str) -> bool:
    return bool(game.get("players", {}).get(pid, {}).get("alive", True))


def known_fascists_for(game: dict, pid: str) -> list:
    role = game.get("roles", {}).get(pid)
    if role == "fascist":
        return [fid for fid, r in game.get("roles", {}).items() if r in ("fascist", "hitler")]
    if role == "hitler" and player_count(game) <= 6:
        return [fid for fid, r in game.get("roles", {}).items() if r == "fascist"]
    return []

def alive_ids(game: dict) -> list:
    return [pid for pid, p in game.get("players", {}).items() if p.get("alive", True)]


def player_count(game: dict) -> int:
    return int(game.get("player_count") or len(game.get("players", {})))


def fascist_track_key(count: int) -> str:
    if count <= 6:
        return "5-6"
    if count <= 8:
        return "7-8"
    return "9-10"


def fascist_power_for(game: dict, fascist_policies: int) -> str | None:
    if fascist_policies <= 0 or fascist_policies >= 6:
        return None
    key = fascist_track_key(player_count(game))
    return FASCIST_POWERS[key][fascist_policies - 1]


def eligible_chancellors(game: dict) -> list:
    alive = alive_ids(game)
    president_id = game.get("president_id")
    last_president_id = game.get("last_president_id")
    last_chancellor_id = game.get("last_chancellor_id")
    excluded = {president_id}

    if len(alive) == 5:
        excluded.add(last_chancellor_id)
    else:
        excluded.update({last_president_id, last_chancellor_id})

    return [pid for pid in alive if pid not in excluded]


def announce(game: dict, message: str) -> None:
    seq = int(game.get("announcement_seq", 0)) + 1
    game["announcement_seq"] = seq
    game["announcement"] = {"id": seq, "message": message}


def set_private_info(game: dict, pid: str, info_type: str, data: dict) -> None:
    seq = int(game.get("private_seq", 0)) + 1
    game["private_seq"] = seq
    game.setdefault("private_info", {})[pid] = {"id": seq, "type": info_type, "data": data}


def default_stats() -> dict:
    return {
        "elections": 0,
        "failed_elections": 0,
        "successful_elections": 0,
        "executions": 0,
        "investigations": 0,
        "special_elections": 0,
        "policy_peeks": 0,
        "vetos_requested": 0,
        "vetos_approved": 0,
    }


def ensure_stats(game: dict) -> dict:
    if "stats" not in game:
        game["stats"] = default_stats()
    return game["stats"]


def ensure_policy_deck(game: dict, count: int) -> None:
    deck = game.get("policy_deck", [])
    discard = game.get("policy_discard", [])
    if len(deck) < count and discard:
        deck.extend(discard)
        game["policy_discard"] = []
        random.shuffle(deck)
    game["policy_deck"] = deck


def draw_policies(game: dict, count: int) -> list:
    ensure_policy_deck(game, count)
    deck = game.get("policy_deck", [])
    drawn = deck[:count]
    game["policy_deck"] = deck[count:]
    return drawn


def reset_term_limits(game: dict) -> None:
    game["last_president_id"] = None
    game["last_chancellor_id"] = None


def reset_election_tracker(game: dict) -> None:
    game["election_tracker"] = 0


def clear_government(game: dict) -> None:
    game["nominee_id"] = None
    game["votes"] = {}
    game["pending_policies"] = []
    game["veto_requested"] = False
    game["veto_denied"] = False


def check_win(game: dict) -> None:
    if game.get("liberal_policies", 0) >= 5:
        game["winner"] = "liberal"
        game["phase"] = "game_over"
        game["victory_reason"] = "liberal_policies"
        announce(game, "Liberals win by enacting five Liberal Policies.")
        return
    if game.get("fascist_policies", 0) >= 6:
        game["winner"] = "fascist"
        game["phase"] = "game_over"
        game["victory_reason"] = "fascist_policies"
        announce(game, "Fascists win by enacting six Fascist Policies.")


def apply_policy(game: dict, policy: str, anarchy: bool = False) -> None:
    game["executive_action"] = None
    if not anarchy:
        pres = game.get("president_id")
        chanc = game.get("chancellor_id")
        delta = 1 if policy == "fascist" else -1
        for pid in (pres, chanc):
            if pid:
                game.setdefault("suspicion", {})[pid] = game.get("suspicion", {}).get(pid, 0) + delta
    if policy == "liberal":
        game["liberal_policies"] = int(game.get("liberal_policies", 0)) + 1
        announce(game, "A Liberal Policy was enacted.")
        reset_election_tracker(game)
        check_win(game)
        return

    game["fascist_policies"] = int(game.get("fascist_policies", 0)) + 1
    announce(game, "A Fascist Policy was enacted.")
    reset_election_tracker(game)
    check_win(game)
    if game.get("winner"):
        return

    if game.get("fascist_policies", 0) >= 5:
        game["veto_unlocked"] = True

    if anarchy:
        return

    power = fascist_power_for(game, game.get("fascist_policies", 0))
    if power:
        game["executive_action"] = {"type": power}
        game["phase"] = "executive_action"


def start_nomination(game: dict) -> None:
    clear_government(game)
    game["phase"] = "nominate"


def start_vote(game: dict, nominee_id: str) -> None:
    game["nominee_id"] = nominee_id
    game["votes"] = {}
    game["phase"] = "vote"
    announce(game, f"{game['players'][game['president_id']]['name']} nominated "
                   f"{game['players'][nominee_id]['name']} for Chancellor.")


def begin_legislative_session(game: dict) -> None:
    game["pending_policies"] = draw_policies(game, 3)
    game["veto_requested"] = False
    game["veto_denied"] = False
    game["phase"] = "legislative_president"


def enact_anarchy(game: dict) -> None:
    policy = draw_policies(game, 1)
    if policy:
        announce(game, "Anarchy! The top policy was enacted.")
        reset_term_limits(game)
        apply_policy(game, policy[0], anarchy=True)
    reset_election_tracker(game)


def resolve_vote(game: dict) -> None:
    alive = alive_ids(game)
    votes = game.get("votes", {})
    yes_votes = sum(1 for pid in alive if votes.get(pid) is True)
    no_votes = sum(1 for pid in alive if votes.get(pid) is False)
    passed = yes_votes > no_votes
    nominee_id = game.get("nominee_id")
    stats = ensure_stats(game)
    stats["elections"] += 1

    game["last_vote"] = {"yes": yes_votes, "no": no_votes, "votes": dict(votes)}

    if not passed:
        stats["failed_elections"] += 1
        announce(game, f"Election failed ({yes_votes} Ja / {no_votes} Nein).")
        game["election_tracker"] = int(game.get("election_tracker", 0)) + 1
        clear_government(game)
        advance_presidency(game)
        if game.get("election_tracker", 0) >= 3:
            enact_anarchy(game)
            if game.get("winner"):
                return
        start_nomination(game)
        return

    announce(game, f"Election passed ({yes_votes} Ja / {no_votes} Nein).")
    stats["successful_elections"] += 1
    reset_election_tracker(game)
    game["chancellor_id"] = nominee_id
    game["last_president_id"] = game.get("president_id")
    game["last_chancellor_id"] = nominee_id
    game["nominee_id"] = None
    game["votes"] = {}

    if game.get("fascist_policies", 0) >= 3 and game.get("roles", {}).get(nominee_id) == "hitler":
        game["winner"] = "fascist"
        game["phase"] = "game_over"
        game["victory_reason"] = "hitler_elected"
        announce(game, "Hitler was elected Chancellor. Fascists win.")
        return
    if game.get("fascist_policies", 0) >= 3:
        announce(game, "The Chancellor is not Hitler.")

    begin_legislative_session(game)


def build_player_action(game: dict, pid: str) -> dict | None:
    if not is_alive(game, pid) or game.get("phase") == "game_over":
        return None

    phase = game.get("phase")
    if phase == "nominate" and pid == game.get("president_id"):
        return {
            "type": "nominate",
            "eligible": eligible_chancellors(game),
        }
    if phase == "vote" and pid not in game.get("votes", {}):
        return {"type": "vote"}
    if phase == "legislative_president" and pid == game.get("president_id"):
        return {
            "type": "president_discard",
            "policies": list(game.get("pending_policies", [])),
        }
    if phase == "legislative_chancellor" and pid == game.get("chancellor_id"):
        return {
            "type": "chancellor_enact",
            "policies": list(game.get("pending_policies", [])),
            "veto_available": bool(game.get("veto_unlocked")),
            "veto_allowed": not bool(game.get("veto_denied")),
        }
    if phase == "veto_pending" and pid == game.get("president_id"):
        return {"type": "veto_decision"}
    if phase == "executive_action" and pid == game.get("president_id"):
        action = (game.get("executive_action") or {}).get("type")
        alive = [pid2 for pid2 in alive_ids(game) if pid2 != pid]
        return {
            "type": "executive",
            "power": action,
            "targets": alive,
        }
    return None


def run_ai_turns(game: dict) -> None:
    for _ in range(8):
        if game.get("phase") == "game_over":
            return
        phase = game.get("phase")
        president_id = game.get("president_id")

        progressed = False
        if phase == "nominate":
            if president_id and is_ai_player(game, president_id):
                state = {
                    "eligible_chancellors": eligible_chancellors(game),
                    "fascist_policies": game.get("fascist_policies", 0),
                    "suspicion": game.get("suspicion", {}),
                    "hitler_id": hitler_id(game),
                }
                nominee = choose_chancellor(state, game["roles"][president_id], known_fascists_for(game, president_id))
                if nominee:
                    start_vote(game, nominee)
                    progressed = True

        elif phase == "vote":
            for pid, player in game.get("players", {}).items():
                if not player.get("alive", True):
                    continue
                if pid in game.get("votes", {}):
                    continue
                if not player.get("is_ai"):
                    continue
                state = {
                    "nominee_id": game.get("nominee_id"),
                    "president_id": president_id,
                    "fascist_policies": game.get("fascist_policies", 0),
                    "suspicion": game.get("suspicion", {}),
                    "hitler_id": hitler_id(game),
                }
                vote = vote_government(state, game["roles"][pid], known_fascists_for(game, pid))
                game.setdefault("votes", {})[pid] = bool(vote)
                progressed = True
            if len(game.get("votes", {})) == len(alive_ids(game)):
                resolve_vote(game)
                progressed = True

        elif phase == "legislative_president":
            if president_id and is_ai_player(game, president_id):
                policies = list(game.get("pending_policies", []))
                if len(policies) == 3:
                    discard_idx = choose_president_discard(policies, game["roles"][president_id])
                    discarded = policies.pop(discard_idx)
                    game.setdefault("policy_discard", []).append(discarded)
                    game["pending_policies"] = policies
                    game["phase"] = "legislative_chancellor"
                    progressed = True

        elif phase == "legislative_chancellor":
            chancellor_id = game.get("chancellor_id")
            if chancellor_id and is_ai_player(game, chancellor_id):
                policies = list(game.get("pending_policies", []))
                if len(policies) == 2:
                    if game.get("veto_unlocked") and not game.get("veto_denied"):
                        if request_veto(policies, game["roles"][chancellor_id]):
                            ensure_stats(game)["vetos_requested"] += 1
                            game["veto_requested"] = True
                            game["phase"] = "veto_pending"
                            announce(game, "Chancellor requested a veto.")
                            progressed = True
                            continue
                    enact_idx = choose_chancellor_enact(policies, game["roles"][chancellor_id])
                    enacted = policies.pop(enact_idx)
                    game.setdefault("policy_discard", []).extend(policies)
                    game["pending_policies"] = []
                    apply_policy(game, enacted)
                    if game.get("phase") == "executive_action" or game.get("winner"):
                        progressed = True
                        continue
                    advance_presidency(game)
                    start_nomination(game)
                    progressed = True

        elif phase == "veto_pending":
            if president_id and is_ai_player(game, president_id):
                policies = list(game.get("pending_policies", []))
                approve = approve_veto(policies, game["roles"][president_id])
                if approve:
                    ensure_stats(game)["vetos_approved"] += 1
                    game.setdefault("policy_discard", []).extend(policies)
                    game["pending_policies"] = []
                    game["veto_requested"] = False
                    game["veto_denied"] = False
                    game["election_tracker"] = int(game.get("election_tracker", 0)) + 1
                    announce(game, "Veto approved. The agenda was discarded.")
                    if game.get("election_tracker", 0) >= 3:
                        enact_anarchy(game)
                        if game.get("winner"):
                            return
                    advance_presidency(game)
                    start_nomination(game)
                else:
                    game["veto_requested"] = False
                    game["veto_denied"] = True
                    game["phase"] = "legislative_chancellor"
                    announce(game, "Veto denied. Chancellor must enact a policy.")
                progressed = True

        elif phase == "executive_action":
            if president_id and is_ai_player(game, president_id):
                action = (game.get("executive_action") or {}).get("type")
                state = {
                    "alive_ids": alive_ids(game),
                    "president_id": president_id,
                    "suspicion": game.get("suspicion", {}),
                    "hitler_id": hitler_id(game),
                }
                if action == "policy_peek":
                    ensure_policy_deck(game, 3)
                    top = game.get("policy_deck", [])[:3]
                    set_private_info(game, president_id, "policy_peek", {"policies": top})
                    ensure_stats(game)["policy_peeks"] += 1
                    announce(game, "President used Policy Peek.")
                elif action == "investigate":
                    target_id = choose_investigation_target(
                        state, game["roles"][president_id], known_fascists_for(game, president_id)
                    )
                    if target_id:
                        party = party_for_role(game["roles"][target_id])
                        set_private_info(game, president_id, "investigation", {"target_id": target_id, "party": party})
                        ensure_stats(game)["investigations"] += 1
                        announce(game, f"President investigated {game['players'][target_id]['name']}.")
                elif action == "special_election":
                    target_id = choose_special_election_target(
                        state, game["roles"][president_id], known_fascists_for(game, president_id)
                    )
                    if target_id:
                        ensure_stats(game)["special_elections"] += 1
                        order = game.get("order") or alive_ids(game)
                        if president_id in order:
                            idx = order.index(president_id)
                            return_id = order[(idx + 1) % len(order)]
                        else:
                            return_id = order[0] if order else None
                        game["special_election_return_id"] = return_id
                        game["president_id"] = target_id
                        game["president_index"] = order.index(target_id) if target_id in order else 0
                        announce(game, f"Special Election: {game['players'][target_id]['name']} is next President.")
                        game["executive_action"] = None
                        start_nomination(game)
                        progressed = True
                        continue
                elif action == "execution":
                    target_id = choose_execution_target(
                        state, game["roles"][president_id], known_fascists_for(game, president_id)
                    )
                    if target_id:
                        ensure_stats(game)["executions"] += 1
                        game["players"][target_id]["alive"] = False
                        announce(game, f"{game['players'][target_id]['name']} was executed.")
                        if game.get("roles", {}).get(target_id) == "hitler":
                            game["winner"] = "liberal"
                            game["phase"] = "game_over"
                            game["victory_reason"] = "hitler_executed"
                            announce(game, "Hitler was executed. Liberals win.")
                            return
                else:
                    return

                game["executive_action"] = None
                if game.get("winner"):
                    return
                advance_presidency(game)
                start_nomination(game)
                progressed = True

        if not progressed:
            return

def advance_presidency(game: dict) -> None:
    normalize_order(game)
    order = game.get("order") or list(game.get("players", {}).keys())
    if not order:
        return
    return_id = game.get("special_election_return_id")
    if return_id and return_id in order:
        game["special_election_return_id"] = None
        return_idx = order.index(return_id)
        game["president_index"] = return_idx
        game["president_id"] = return_id
        return

    current_president = game.get("president_id")
    if current_president in order:
        current_idx = order.index(current_president)
        next_idx = (current_idx + 1) % len(order)
    else:
        next_idx = 0

    game["president_index"] = next_idx
    game["president_id"] = order[next_idx]


def normalize_order(game: dict) -> None:
    players = [pid for pid, p in game.get("players", {}).items() if p.get("alive", True)]
    seen = set()
    order = []
    for pid in (game.get("order") or []):
        if pid in players and pid not in seen:
            order.append(pid)
            seen.add(pid)
    for pid in players:
        if pid not in seen:
            order.append(pid)
            seen.add(pid)
    game["order"] = order
    if game.get("president_id") not in order:
        game["president_index"] = 0
        game["president_id"] = order[0] if order else None



def add_ai_players(players: dict, count: int) -> list:
    ai_ids = []
    used_names = {p["name"] for p in players.values() if "name" in p}
    for i in range(count):
        base = random.choice(AI_NAMES)
        name = base
        suffix = 2
        while name in used_names:
            name = f"{base} {suffix}"
            suffix += 1
        used_names.add(name)
        ai_id = f"ai_{secrets.token_urlsafe(8)}"
        players[ai_id] = {"name": name, "is_host": False, "is_ai": True, "alive": True}
        ai_ids.append(ai_id)
    return ai_ids


@app.get("/")
def index():
    existing_code = session.get("game_code")
    existing_game = existing_code in GAMES if existing_code else False
    return render_template("index.html", existing_game=existing_game, existing_code=existing_code)


@app.post("/host")
def host():
    player_id = ensure_player_id()
    code = create_unique_code()

    host_name = request.form.get("name", "").strip()
    if not host_name:
        flash("Enter a host name.")
        return redirect(url_for("index"))

    players = {
        player_id: {"name": host_name, "is_host": True, "is_ai": False, "alive": True}
    }
    ai_count = max(0, MAX_PLAYERS - len(players))
    add_ai_players(players, ai_count)
    player_ids = list(players.keys())

    GAMES[code] = {
        "code": code,
        "host_id": player_id,
        "players": players,
        "player_count": 0,
        "policy_deck": [],
        "policy_discard": [],
        "roles": {},
        "president_id": None,
        "order": [],
        "president_index": 0,
        "chancellor_id": None,
        "last_president_id": None,
        "last_chancellor_id": None,
        "nominee_id": None,
        "votes": {},
        "phase": "lobby",
        "liberal_policies": 0,
        "fascist_policies": 0,
        "election_tracker": 0,
        "pending_policies": [],
        "executive_action": None,
        "veto_unlocked": False,
        "veto_requested": False,
        "veto_denied": False,
        "special_election_return_id": None,
        "private_info": {},
        "private_seq": 0,
        "suspicion": {},
        "winner": None,
        "victory_reason": None,
        "last_vote": None,
        "announcement_seq": 0,
        "announcement": None,
        "stats": default_stats(),
        "end_ack": set(),
        "started": False,
    }

    session["game_code"] = code
    session["is_host"] = True

    return redirect(url_for("lobby", code=code))


@app.post("/join")
def join():
    player_id = ensure_player_id()

    code = (request.form.get("code", "") or "").strip()
    name = (request.form.get("name", "") or "").strip()

    if not (code.isdigit() and len(code) == 8):
        flash("Enter a valid 8-digit code.")
        return redirect(url_for("index"))
    if not name:
        flash("Enter a player name.")
        return redirect(url_for("index"))

    game = GAMES.get(code)
    if not game:
        flash("Game not found. Check the code and try again.")
        return redirect(url_for("index"))

    # Enforce max players, replacing AI slots when possible
    if player_id not in game["players"] and len(game["players"]) >= MAX_PLAYERS:
        ai_id = next((pid for pid, p in game["players"].items() if p.get("is_ai")), None)
        if ai_id:
            game["players"].pop(ai_id, None)
            if "roles" in game:
                ai_role = game["roles"].pop(ai_id, None)
                if ai_role:
                    game["roles"][player_id] = ai_role
        else:
            flash("That lobby is full (max 10 players).")
            return redirect(url_for("index"))

    # Add/update player
    if player_id not in game["players"]:
        game["players"][player_id] = {"name": name, "is_host": False, "is_ai": False, "alive": True}
        if "roles" in game and player_id not in game["roles"]:
            game["roles"][player_id] = "liberal"
    else:
        game["players"][player_id]["name"] = name

    session["game_code"] = code
    session["is_host"] = False

    return redirect(url_for("lobby", code=code))


@app.get("/lobby/<code>")
def lobby(code: str):
    game = GAMES.get(code)
    if not game:
        flash("That game no longer exists.")
        return redirect(url_for("index"))

    # Prevent accidental cross-lobby viewing if user isn't in this game
    pid = ensure_player_id()
    if pid not in game["players"]:
        flash("You are not in that lobby. Join with the code first.")
        return redirect(url_for("index"))

    is_host = (pid == game["host_id"])
    return render_template("lobby.html", game=game, is_host=is_host, player_id=pid)

@app.get("/room/<code>")
def room(code: str):
    game = GAMES.get(code)
    if not game:
        flash("That game no longer exists.")
        return redirect(url_for("index"))

    if not game.get("started"):
        flash("Game has not started yet.")
        return redirect(url_for("lobby", code=code))

    pid = ensure_player_id()
    if pid not in game["players"]:
        flash("You are not in that room.")
        return redirect(url_for("index"))

    is_host = (pid == game["host_id"])
    return render_template("room.html", game=game, is_host=is_host, player_id=pid)


@app.post("/leave")
def leave():
    code = session.get("game_code")
    pid = session.get("player_id")

    if code and pid and code in GAMES:
        game = GAMES[code]
        game["players"].pop(pid, None)

        # If host leaves, delete the game (simple rule for now)
        if pid == game["host_id"]:
            GAMES.pop(code, None)
        else:
            # If no players left, delete
            if not game["players"]:
                GAMES.pop(code, None)

    session.pop("game_code", None)
    session.pop("is_host", None)

    return redirect(url_for("index"))


@app.get("/api/game/<code>")
def api_game(code: str):
    game = GAMES.get(code)
    if not game:
        return jsonify({"ok": False}), 404

    players = [{"id": pid, **p} for pid, p in game["players"].items()]
    return jsonify({
        "ok": True,
        "code": code,
        "host_id": game["host_id"],
        "started": game.get("started", False),
        "players": players
    })


@app.post("/api/game/<code>/start")
def api_start_game(code: str):
    game = GAMES.get(code)
    if not game:
        return jsonify({"ok": False, "message": "Game not found."}), 404

    pid = ensure_player_id()
    if pid != game["host_id"]:
        return jsonify({"ok": False, "message": "Only the host can start the game."}), 403

    player_ids = list(game["players"].keys())
    game["player_count"] = len(player_ids)
    game["policy_deck"] = build_deck()
    game["policy_discard"] = []
    game["roles"] = assign_roles(player_ids)
    order = player_ids[:]
    random.shuffle(order)
    game["order"] = order
    game["president_index"] = 0
    game["president_id"] = order[0] if order else None
    game["chancellor_id"] = None
    game["last_president_id"] = None
    game["last_chancellor_id"] = None
    game["nominee_id"] = None
    game["votes"] = {}
    game["phase"] = "nominate"
    game["liberal_policies"] = 0
    game["fascist_policies"] = 0
    game["election_tracker"] = 0
    game["pending_policies"] = []
    game["executive_action"] = None
    game["veto_unlocked"] = False
    game["veto_requested"] = False
    game["veto_denied"] = False
    game["special_election_return_id"] = None
    game["private_info"] = {}
    game["private_seq"] = 0
    game["suspicion"] = {pid: 0 for pid in player_ids}
    game["winner"] = None
    game["victory_reason"] = None
    game["last_vote"] = None
    game["announcement_seq"] = 0
    game["announcement"] = None
    game["stats"] = default_stats()
    game["end_ack"] = set()
    game["started"] = True

    return jsonify({
        "ok": True,
        "started": True,
    })


@app.get("/api/game/<code>/state")
def api_state(code: str):
    game = GAMES.get(code)
    if not game:
        return jsonify({"ok": False, "message": "Game not found."}), 404
    if not game.get("started"):
        return jsonify({"ok": False, "message": "Game not started."}), 400

    pid = ensure_player_id()
    if pid not in game["players"]:
        return jsonify({"ok": False, "message": "Not in this lobby."}), 403

    normalize_order(game)
    run_ai_turns(game)
    ensure_stats(game)

    players = [{"id": pid2, **p} for pid2, p in game["players"].items()]
    alive = alive_ids(game)
    votes = game.get("votes", {})
    vote_cast = len(votes)
    vote_total = len(alive)
    vote_complete = vote_cast == vote_total and game.get("phase") == "vote"

    response = {
        "ok": True,
        "phase": game.get("phase"),
        "players": players,
        "order": game.get("order"),
        "president_id": game.get("president_id"),
        "chancellor_id": game.get("chancellor_id"),
        "nominee_id": game.get("nominee_id"),
        "last_president_id": game.get("last_president_id"),
        "last_chancellor_id": game.get("last_chancellor_id"),
        "liberal_policies": game.get("liberal_policies", 0),
        "fascist_policies": game.get("fascist_policies", 0),
        "election_tracker": game.get("election_tracker", 0),
        "policy_deck_count": len(game.get("policy_deck", [])),
        "policy_discard_count": len(game.get("policy_discard", [])),
        "veto_unlocked": game.get("veto_unlocked", False),
        "executive_action": game.get("executive_action"),
        "eligible_chancellors": eligible_chancellors(game),
        "vote": {
            "total": vote_total,
            "cast": vote_cast,
            "revealed": vote_complete,
            "votes": votes if vote_complete else None,
        },
        "last_vote": game.get("last_vote"),
        "announcement": game.get("announcement"),
        "winner": game.get("winner"),
        "victory_reason": game.get("victory_reason"),
        "stats": game.get("stats", {}),
        "you_id": pid,
    }

    if game.get("winner"):
        response["final_roles"] = [
            {
                "id": pid2,
                "name": p.get("name"),
                "role": game.get("roles", {}).get(pid2),
                "party": party_for_role(game.get("roles", {}).get(pid2, "")),
                "alive": p.get("alive", True),
                "is_ai": p.get("is_ai", False),
            }
            for pid2, p in game.get("players", {}).items()
        ]

    action = build_player_action(game, pid)
    private_info = game.get("private_info", {}).get(pid)
    response["self"] = {"action": action, "private_info": private_info}
    return jsonify(response)


@app.post("/api/game/<code>/nominate")
def api_nominate(code: str):
    game = GAMES.get(code)
    if not game:
        return jsonify({"ok": False, "message": "Game not found."}), 404
    if not game.get("started"):
        return jsonify({"ok": False, "message": "Game not started."}), 400
    if game.get("phase") != "nominate":
        return jsonify({"ok": False, "message": "Not in nomination phase."}), 400

    pid = ensure_player_id()
    if pid != game.get("president_id"):
        return jsonify({"ok": False, "message": "Only the President can nominate."}), 403
    if not game["players"][pid].get("alive", True):
        return jsonify({"ok": False, "message": "President is not alive."}), 403

    data = request.get_json(silent=True) or {}
    nominee_id = data.get("chancellor_id")
    if not nominee_id:
        return jsonify({"ok": False, "message": "Chancellor is required."}), 400
    if nominee_id not in game["players"]:
        return jsonify({"ok": False, "message": "Player not found."}), 400
    if nominee_id not in eligible_chancellors(game):
        return jsonify({"ok": False, "message": "Chancellor is not eligible."}), 400

    start_vote(game, nominee_id)
    return jsonify({"ok": True})


@app.post("/api/game/<code>/vote")
def api_vote(code: str):
    game = GAMES.get(code)
    if not game:
        return jsonify({"ok": False, "message": "Game not found."}), 404
    if not game.get("started"):
        return jsonify({"ok": False, "message": "Game not started."}), 400
    if game.get("phase") != "vote":
        return jsonify({"ok": False, "message": "Not in voting phase."}), 400

    pid = ensure_player_id()
    if pid not in game["players"]:
        return jsonify({"ok": False, "message": "Not in this lobby."}), 403
    if not game["players"][pid].get("alive", True):
        return jsonify({"ok": False, "message": "You are not alive."}), 403
    if pid in game.get("votes", {}):
        return jsonify({"ok": False, "message": "Vote already cast."}), 400

    data = request.get_json(silent=True) or {}
    vote_raw = data.get("vote")
    if isinstance(vote_raw, str):
        vote_raw = vote_raw.lower()
    if vote_raw not in ("ja", "nein", True, False):
        return jsonify({"ok": False, "message": "Vote must be Ja or Nein."}), 400

    game.setdefault("votes", {})[pid] = (vote_raw is True) or (vote_raw == "ja")
    if len(game["votes"]) == len(alive_ids(game)):
        resolve_vote(game)
    return jsonify({"ok": True})


@app.post("/api/game/<code>/legis/president")
def api_legis_president(code: str):
    game = GAMES.get(code)
    if not game:
        return jsonify({"ok": False, "message": "Game not found."}), 404
    if not game.get("started"):
        return jsonify({"ok": False, "message": "Game not started."}), 400
    if game.get("phase") != "legislative_president":
        return jsonify({"ok": False, "message": "Not in President legislative phase."}), 400

    pid = ensure_player_id()
    if pid != game.get("president_id"):
        return jsonify({"ok": False, "message": "Only the President can discard."}), 403

    data = request.get_json(silent=True) or {}
    discard_index = data.get("discard_index")
    if discard_index is None:
        return jsonify({"ok": False, "message": "Discard choice required."}), 400

    policies = list(game.get("pending_policies", []))
    if len(policies) != 3:
        return jsonify({"ok": False, "message": "No policies to discard."}), 400

    if not isinstance(discard_index, int) or discard_index < 0 or discard_index >= len(policies):
        return jsonify({"ok": False, "message": "Invalid discard choice."}), 400

    discarded = policies.pop(discard_index)
    game.setdefault("policy_discard", []).append(discarded)
    game["pending_policies"] = policies
    game["phase"] = "legislative_chancellor"
    return jsonify({"ok": True})


@app.post("/api/game/<code>/legis/chancellor")
def api_legis_chancellor(code: str):
    game = GAMES.get(code)
    if not game:
        return jsonify({"ok": False, "message": "Game not found."}), 404
    if not game.get("started"):
        return jsonify({"ok": False, "message": "Game not started."}), 400
    if game.get("phase") != "legislative_chancellor":
        return jsonify({"ok": False, "message": "Not in Chancellor legislative phase."}), 400

    pid = ensure_player_id()
    if pid != game.get("chancellor_id"):
        return jsonify({"ok": False, "message": "Only the Chancellor can enact."}), 403

    data = request.get_json(silent=True) or {}
    if data.get("veto"):
        if not game.get("veto_unlocked"):
            return jsonify({"ok": False, "message": "Veto power not unlocked."}), 400
        if game.get("veto_denied"):
            return jsonify({"ok": False, "message": "Veto already denied."}), 400
        ensure_stats(game)["vetos_requested"] += 1
        game["veto_requested"] = True
        game["phase"] = "veto_pending"
        announce(game, "Chancellor requested a veto.")
        return jsonify({"ok": True})

    enact_index = data.get("enact_index")
    if enact_index is None:
        return jsonify({"ok": False, "message": "Enact choice required."}), 400

    policies = list(game.get("pending_policies", []))
    if len(policies) != 2:
        return jsonify({"ok": False, "message": "No policies to enact."}), 400
    if not isinstance(enact_index, int) or enact_index < 0 or enact_index >= len(policies):
        return jsonify({"ok": False, "message": "Invalid enact choice."}), 400

    enacted = policies.pop(enact_index)
    game.setdefault("policy_discard", []).extend(policies)
    game["pending_policies"] = []
    apply_policy(game, enacted)
    game["executive_action"] = game.get("executive_action")

    if game.get("phase") == "executive_action" or game.get("winner"):
        return jsonify({"ok": True})

    advance_presidency(game)
    start_nomination(game)
    return jsonify({"ok": True})


@app.post("/api/game/<code>/veto")
def api_veto(code: str):
    game = GAMES.get(code)
    if not game:
        return jsonify({"ok": False, "message": "Game not found."}), 404
    if not game.get("started"):
        return jsonify({"ok": False, "message": "Game not started."}), 400
    if game.get("phase") != "veto_pending":
        return jsonify({"ok": False, "message": "No veto pending."}), 400

    pid = ensure_player_id()
    if pid != game.get("president_id"):
        return jsonify({"ok": False, "message": "Only the President can decide the veto."}), 403

    data = request.get_json(silent=True) or {}
    approve = bool(data.get("approve"))

    if approve:
        ensure_stats(game)["vetos_approved"] += 1
        game.setdefault("policy_discard", []).extend(game.get("pending_policies", []))
        game["pending_policies"] = []
        game["veto_requested"] = False
        game["veto_denied"] = False
        game["election_tracker"] = int(game.get("election_tracker", 0)) + 1
        announce(game, "Veto approved. The agenda was discarded.")
        if game.get("election_tracker", 0) >= 3:
            enact_anarchy(game)
            if game.get("winner"):
                return jsonify({"ok": True})
        advance_presidency(game)
        start_nomination(game)
        return jsonify({"ok": True})

    game["veto_requested"] = False
    game["veto_denied"] = True
    game["phase"] = "legislative_chancellor"
    announce(game, "Veto denied. Chancellor must enact a policy.")
    return jsonify({"ok": True})


@app.post("/api/game/<code>/executive")
def api_executive(code: str):
    game = GAMES.get(code)
    if not game:
        return jsonify({"ok": False, "message": "Game not found."}), 404
    if not game.get("started"):
        return jsonify({"ok": False, "message": "Game not started."}), 400
    if game.get("phase") != "executive_action":
        return jsonify({"ok": False, "message": "No executive action pending."}), 400

    pid = ensure_player_id()
    if pid != game.get("president_id"):
        return jsonify({"ok": False, "message": "Only the President can act."}), 403

    action = (game.get("executive_action") or {}).get("type")
    data = request.get_json(silent=True) or {}

    if action == "policy_peek":
        ensure_policy_deck(game, 3)
        top = game.get("policy_deck", [])[:3]
        set_private_info(game, pid, "policy_peek", {"policies": top})
        ensure_stats(game)["policy_peeks"] += 1
        announce(game, "President used Policy Peek.")
    elif action == "investigate":
        target_id = data.get("target_id")
        if not target_id or target_id not in game["players"]:
            return jsonify({"ok": False, "message": "Target required."}), 400
        if not game["players"][target_id].get("alive", True):
            return jsonify({"ok": False, "message": "Target is not alive."}), 400
        party = party_for_role(game["roles"][target_id])
        set_private_info(game, pid, "investigation", {"target_id": target_id, "party": party})
        ensure_stats(game)["investigations"] += 1
        announce(game, f"President investigated {game['players'][target_id]['name']}.")
    elif action == "special_election":
        target_id = data.get("target_id")
        if not target_id or target_id not in game["players"]:
            return jsonify({"ok": False, "message": "Target required."}), 400
        if not game["players"][target_id].get("alive", True):
            return jsonify({"ok": False, "message": "Target is not alive."}), 400
        ensure_stats(game)["special_elections"] += 1
        order = game.get("order") or alive_ids(game)
        if game.get("president_id") in order:
            idx = order.index(game.get("president_id"))
            return_id = order[(idx + 1) % len(order)]
        else:
            return_id = order[0] if order else None
        game["special_election_return_id"] = return_id
        game["president_id"] = target_id
        game["president_index"] = order.index(target_id) if target_id in order else 0
        announce(game, f"Special Election: {game['players'][target_id]['name']} is next President.")
        game["executive_action"] = None
        start_nomination(game)
        return jsonify({"ok": True})
    elif action == "execution":
        target_id = data.get("target_id")
        if not target_id or target_id not in game["players"]:
            return jsonify({"ok": False, "message": "Target required."}), 400
        if target_id == pid:
            return jsonify({"ok": False, "message": "Cannot execute yourself."}), 400
        if not game["players"][target_id].get("alive", True):
            return jsonify({"ok": False, "message": "Target is not alive."}), 400
        ensure_stats(game)["executions"] += 1
        game["players"][target_id]["alive"] = False
        announce(game, f"{game['players'][target_id]['name']} was executed.")
        if game.get("roles", {}).get(target_id) == "hitler":
            game["winner"] = "liberal"
            game["phase"] = "game_over"
            game["victory_reason"] = "hitler_executed"
            announce(game, "Hitler was executed. Liberals win.")
            return jsonify({"ok": True})
    else:
        return jsonify({"ok": False, "message": "Unknown executive action."}), 400

    game["executive_action"] = None
    if game.get("winner"):
        return jsonify({"ok": True})
    advance_presidency(game)
    start_nomination(game)
    return jsonify({"ok": True})


@app.get("/api/game/<code>/role")
def api_role(code: str):
    game = GAMES.get(code)
    if not game:
        return jsonify({"ok": False, "message": "Game not found."}), 404
    if not game.get("started"):
        return jsonify({"ok": False, "message": "Game not started."}), 400

    pid = ensure_player_id()
    if pid not in game["players"]:
        return jsonify({"ok": False, "message": "Not in this lobby."}), 403

    role = game.get("roles", {}).get(pid)
    if not role:
        return jsonify({"ok": False, "message": "Role not assigned."}), 400

    response = {
        "ok": True,
        "role": role,
        "self_name": game["players"][pid]["name"],
    }

    if role == "fascist":
        fascists = [pid2 for pid2, r in game["roles"].items() if r == "fascist"]
        hitler_id = next((pid2 for pid2, r in game["roles"].items() if r == "hitler"), None)
        other_fascist_ids = [fid for fid in fascists if fid != pid]
        response["other_fascists"] = [game["players"][fid]["name"] for fid in other_fascist_ids]
        response["hitler"] = game["players"][hitler_id]["name"] if hitler_id else None
    elif role == "hitler" and player_count(game) <= 6:
        fascists = [pid2 for pid2, r in game["roles"].items() if r == "fascist"]
        response["other_fascists"] = [game["players"][fid]["name"] for fid in fascists]

    return jsonify(response)


@app.post("/api/game/<code>/end_ack")
def api_end_ack(code: str):
    game = GAMES.get(code)
    if not game:
        return jsonify({"ok": False, "message": "Game not found."}), 404
    if not game.get("winner"):
        return jsonify({"ok": False, "message": "Game is not over."}), 400

    pid = ensure_player_id()
    if pid not in game["players"]:
        return jsonify({"ok": False, "message": "Not in this lobby."}), 403

    acked = game.setdefault("end_ack", set())
    acked.add(pid)
    humans = [pid2 for pid2, p in game.get("players", {}).items() if not p.get("is_ai")]
    dissolved = all(pid2 in acked for pid2 in humans)
    if dissolved:
        GAMES.pop(code, None)
    return jsonify({"ok": True, "dissolved": dissolved})


if __name__ == "__main__":
    # For LAN hosting: run with host="0.0.0.0"
    app.run(host="0.0.0.0", port=5000, debug=True)
