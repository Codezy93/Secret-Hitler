/* ============ LOBBY ============ */
(() => {
    const copyBtn = document.getElementById("copyCode");
    const codeEl = document.getElementById("codeText");
    const lobbyRoot = document.querySelector(".lobbyScreen");
    const listEl = document.getElementById("playerList");
    const startBtn = document.getElementById("startGame");
    const roleModal = document.getElementById("roleModal");
    const roleNameEl = document.getElementById("roleName");
    const roleInfoEl = document.getElementById("roleInfo");
    const ackRoleBtn = document.getElementById("ackRole");

    if (copyBtn && codeEl) {
        copyBtn.addEventListener("click", async () => {
        try {
            await navigator.clipboard.writeText(codeEl.textContent.trim());
            copyBtn.textContent = "Copied!";
            setTimeout(() => (copyBtn.textContent = "Copy"), 900);
        } catch {
            alert("Copy failed. Select the code and copy manually.");
        }
        });
    }

    if (!lobbyRoot || !listEl) return;

    const code = lobbyRoot.getAttribute("data-game-code");
    if (!code) return;
    let started = false;
    let roleRevealed = false;
    let roleLoading = false;

    const openRoleModal = (data) => {
        if (!roleModal || !roleNameEl || !roleInfoEl) return;
        const role = (data.role || "").toUpperCase();
        roleNameEl.textContent = role || "ROLE";

        if (data.role === "fascist") {
            const others = (data.other_fascists || []).join(", ") || "None";
            const hitler = data.hitler || "Unknown";
            roleInfoEl.textContent = `Hitler: ${hitler}. Other fascist(s): ${others}.`;
        } else if (data.role === "hitler") {
            const others = (data.other_fascists || []).join(", ");
            roleInfoEl.textContent = others
                ? `Fascist(s): ${others}.`
                : "You are Hitler. You do not know the fascists.";
        } else {
            roleInfoEl.textContent = "You are a Liberal.";
        }

        roleModal.classList.add("open");
        roleModal.setAttribute("aria-hidden", "false");
    };

    if (ackRoleBtn) {
        ackRoleBtn.addEventListener("click", () => {
            window.location = `/room/${code}`;
        });
    }

    const revealRole = async () => {
        if (roleRevealed || roleLoading) return;
        roleLoading = true;
        try {
            const res = await fetch(`/api/game/${code}/role`, { cache: "no-store" });
            const data = await res.json();
            if (!res.ok || !data.ok) return;
            openRoleModal(data);
            roleRevealed = true;
        } catch {
            // ignore
        } finally {
            roleLoading = false;
        }
    };

    async function refresh() {
        try {
        const res = await fetch(`/api/game/${code}`, { cache: "no-store" });
        if (!res.ok) return;
        const data = await res.json();
        if (!data.ok) return;

        listEl.innerHTML = "";
        started = !!data.started;
        for (const p of data.players) {
            const li = document.createElement("li");
            li.className = "playerRow";

            const name = document.createElement("span");
            name.className = "playerName";
            name.textContent = p.name;

            if (p.id === data.host_id) {
                const b = document.createElement("span");
                b.className = "badge";
                b.textContent = "HOST";
                name.appendChild(b);
            }

            li.appendChild(name);
            listEl.appendChild(li);
        }

        if (started && !roleRevealed) {
            revealRole();
        }
        } catch {
        // ignore
        }
    }

    refresh();
    setInterval(refresh, 2000);

    if (startBtn) {
        startBtn.addEventListener("click", async () => {
            startBtn.disabled = true;
            try {
                const res = await fetch(`/api/game/${code}/start`, {
                    method: "POST",
                    headers: { "Content-Type": "application/json" },
                });
                const data = await res.json();
                if (!res.ok || !data.ok) {
                    alert(data.message || "Failed to start game.");
                    return;
                }
                started = true;
                revealRole();
            } catch {
                alert("Failed to start game.");
            } finally {
                startBtn.disabled = false;
            }
        });
    }
})();

/* ============ HOME MODALS ============ */
(() => {
    const setupModal = ({ openBtnId, modalId, closeBtnId, focusSelector, onInput }) => {
        const openBtn = document.getElementById(openBtnId);
        const modal = document.getElementById(modalId);
        const closeBtn = closeBtnId ? document.getElementById(closeBtnId) : null;

        if (!openBtn || !modal) return null;

        const open = () => {
            modal.classList.add("open");
            modal.setAttribute("aria-hidden", "false");
            const input = focusSelector ? modal.querySelector(focusSelector) : null;
            if (input) input.focus();
        };

        const close = () => {
            modal.classList.remove("open");
            modal.setAttribute("aria-hidden", "true");
        };

        openBtn.addEventListener("click", open);
        if (closeBtn) closeBtn.addEventListener("click", close);

        modal.addEventListener("click", (e) => {
            if (e.target === modal) close();
        });

        if (onInput) modal.addEventListener("input", onInput);

        return { modal, close };
    };

    const join = setupModal({
        openBtnId: "openJoin",
        modalId: "joinModal",
        closeBtnId: "closeJoin",
        focusSelector: "input[name='code']",
        onInput: (e) => {
            const t = e.target;
            if (t && t.name === "code") {
                t.value = t.value.replace(/\D/g, "").slice(0, 8);
            }
        },
    });

    const host = setupModal({
        openBtnId: "openHost",
        modalId: "hostModal",
        closeBtnId: "closeHost",
        focusSelector: "input[name='name']",
    });

    document.addEventListener("keydown", (e) => {
        if (e.key !== "Escape") return;
        if (join?.modal?.classList.contains("open")) join.close();
        if (host?.modal?.classList.contains("open")) host.close();
    });
})();

/* ============ ROOM: CARD FLIP ============ */
(() => {
    const roomRoot = document.querySelector(".roomScreen");
    if (!roomRoot) return;

    const code = roomRoot.getAttribute("data-game-code");
    if (!code) return;

    const membershipCard = roomRoot.querySelector(".rFlipCard[data-card='membership']");
    const roleCard = roomRoot.querySelector(".rFlipCard[data-card='role']");
    const membershipFront = membershipCard ? membershipCard.querySelector(".flipFront") : null;
    const roleFront = roleCard ? roleCard.querySelector(".flipFront") : null;

    let revealed = false;
    let loading = false;

    const setFront = (card, img, role) => {
        if (!card || !img) return;
        const key = role === "hitler" ? "frontHitler" : role === "fascist" ? "frontFascist" : "frontLiberal";
        const src = card.dataset[key];
        if (src) img.src = src;
    };

    const reveal = async () => {
        if (revealed || loading) return revealed;
        loading = true;
        try {
            const res = await fetch(`/api/game/${code}/role`, { cache: "no-store" });
            const data = await res.json();
            if (!res.ok || !data.ok) return false;

            const role = data.role;
            const membership = role === "liberal" ? "liberal" : "fascist";
            setFront(membershipCard, membershipFront, membership);
            setFront(roleCard, roleFront, role);

            revealed = true;
            return true;
        } catch {
            return false;
        } finally {
            loading = false;
        }
    };

    const handleClick = async (card) => {
        if (!card) return;
        if (!revealed) {
            const ok = await reveal();
            if (!ok) return;
        }
        card.classList.toggle("is-flipped");
    };

    document.querySelectorAll(".rFlipCard").forEach((card) => {
        card.addEventListener("click", () => handleClick(card));
    });
})();

/* ============ AUDIO ============ */
const SFX = (() => {
    let ctx = null;
    const getCtx = () => {
        if (!ctx) {
            try { ctx = new (window.AudioContext || window.webkitAudioContext)(); }
            catch { return null; }
        }
        return ctx;
    };
    const play = (freq, type, duration, vol = 0.15) => {
        const c = getCtx();
        if (!c) return;
        const o = c.createOscillator();
        const g = c.createGain();
        o.type = type;
        o.frequency.value = freq;
        g.gain.value = vol;
        g.gain.exponentialRampToValueAtTime(0.001, c.currentTime + duration);
        o.connect(g).connect(c.destination);
        o.start(); o.stop(c.currentTime + duration);
    };
    return {
        notify: () => { play(880, "sine", 0.12); setTimeout(() => play(1100, "sine", 0.15), 130); },
        vote: () => play(660, "triangle", 0.1),
        policy: () => { play(440, "sine", 0.2); setTimeout(() => play(660, "sine", 0.25), 200); },
        alert: () => { play(300, "sawtooth", 0.15, 0.08); setTimeout(() => play(200, "sawtooth", 0.2, 0.08), 170); },
        win: () => { [523,659,784].forEach((f,i) => setTimeout(() => play(f, "sine", 0.3, 0.12), i*180)); },
    };
})();

/* ============ ROOM: GAME STATE ============ */
(() => {
    const roomRoot = document.querySelector(".roomScreen");
    if (!roomRoot) return;

    const code = roomRoot.getAttribute("data-game-code");
    if (!code) return;

    // Element references
    const listEl = document.getElementById("roomPlayerList");
    const presidentEl = document.getElementById("presidentName");
    const chancellorEl = document.getElementById("chancellorName");
    const lastPresidentEl = document.getElementById("lastPresidentName");
    const lastChancellorEl = document.getElementById("lastChancellorName");
    const toastEl = document.getElementById("roomToast");
    const electionModal = document.getElementById("electionModal");
    const closeElectionBtn = document.getElementById("closeElection");
    const electionHint = document.getElementById("electionHint");
    const voteJaBtn = document.getElementById("voteJa");
    const voteNeinBtn = document.getElementById("voteNein");
    const voteModal = document.getElementById("voteModal");
    const voteModalNominee = document.getElementById("voteModalNominee");
    const voteModalPresident = document.getElementById("voteModalPresident");
    const voteModalProgress = document.getElementById("voteModalProgress");
    const voteModalBtns = document.getElementById("voteModalBtns");
    const voteModalWait = document.getElementById("voteModalWait");
    const phaseText = document.getElementById("phaseText");
    const nomineeName = document.getElementById("nomineeName");
    const trackerCount = document.getElementById("trackerCount");
    const liberalCount = document.getElementById("liberalCount");
    const fascistCount = document.getElementById("fascistCount");
    const deckCount = document.getElementById("deckCount");
    const discardCount = document.getElementById("discardCount");
    const fascistPolicyRow = document.getElementById("fascistPolicyRow");
    const liberalPolicyRow = document.getElementById("liberalPolicyRow");
    const drawPileStack = document.getElementById("drawPileStack");
    const discardPileStack = document.getElementById("discardPileStack");
    const drawPileCount = document.getElementById("drawPileCount");
    const discardPileCount = document.getElementById("discardPileCount");
    const voteStatus = document.getElementById("voteStatus");
    const actionModal = document.getElementById("actionModal");
    const actionTitle = document.getElementById("actionTitle");
    const actionBody = document.getElementById("actionBody");
    const actionActions = document.getElementById("actionActions");
    const plaqueImg = document.getElementById("roomPlaque");
    const endModal = document.getElementById("endModal");
    const endBadge = document.getElementById("endBadge");
    const endTitle = document.getElementById("endTitle");
    const endSubtitle = document.getElementById("endSubtitle");
    const endStats = document.getElementById("endStats");
    const endRoleList = document.getElementById("endRoleList");
    const endAcknowledge = document.getElementById("endAcknowledge");
    const seatList = document.getElementById("seatList");
    const gameLogList = document.getElementById("gameLogList");
    const phaseBanner = document.getElementById("phaseBanner");
    const phaseBannerText = document.getElementById("phaseBannerText");
    const voteResultOverlay = document.getElementById("voteResultOverlay");
    const voteResultTitle = document.getElementById("voteResultTitle");
    const voteResultTally = document.getElementById("voteResultTally");
    const voteResultGrid = document.getElementById("voteResultGrid");
    const voteResultDismiss = document.getElementById("voteResultDismiss");

    let toastTimer = null;
    let lastAnnouncementId = null;
    let lastPrivateId = null;
    let currentAction = null;
    let actionBusy = false;
    let endShown = false;
    let lastLogCount = 0;
    let lastVoteId = null;
    let voteResultShown = false;

    const PHASE_NAMES = {
        nominate: "Nomination",
        vote: "Election",
        legislative_president: "Legislative Session",
        legislative_chancellor: "Legislative Session",
        veto_pending: "Veto Decision",
        executive_action: "Executive Action",
        game_over: "Game Over",
    };

    const BOARD_SLOTS = {
        fascist: [
            { x: 23.17, y: 50.8 },
            { x: 36.57, y: 50.8 },
            { x: 49.98, y: 50.8 },
            { x: 63.55, y: 50.6 },
            { x: 77.12, y: 50.6 },
            { x: 90.58, y: 50.6 },
        ],
        liberal: [
            { x: 29.77, y: 49.5 },
            { x: 43.19, y: 49.5 },
            { x: 56.61, y: 49.5 },
            { x: 69.87, y: 49.5 },
            { x: 83.29, y: 49.5 },
        ],
    };

    const showToast = (message) => {
        if (!toastEl || !message) return;
        toastEl.textContent = message;
        toastEl.classList.add("show");
        if (toastTimer) clearTimeout(toastTimer);
        toastTimer = setTimeout(() => {
            toastEl.classList.remove("show");
        }, 2800);
    };

    const openModal = (modal) => {
        if (!modal) return;
        modal.classList.add("open");
        modal.setAttribute("aria-hidden", "false");
    };

    const closeModal = (modal) => {
        if (!modal) return;
        modal.classList.remove("open");
        modal.setAttribute("aria-hidden", "true");
    };

    const nameFor = (id, map) => (id && map.has(id) ? map.get(id) : "-");

    const postJson = async (path, body) => {
        const res = await fetch(path, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify(body || {}),
        });
        const data = await res.json();
        if (!res.ok || !data.ok) {
            alert(data.message || "Action failed.");
            return false;
        }
        return true;
    };

    // ---- Seat Board (Player List) ----
    const renderSeatBoard = (data, byId) => {
        if (!seatList) return;
        seatList.innerHTML = "";
        const order = data.order || [];
        for (const pid of order) {
            const player = data.players.find((p) => p.id === pid);
            if (!player) continue;
            const li = document.createElement("li");
            li.className = "seatRow";

            if (pid === data.you_id) li.classList.add("seatYou");
            if (!player.alive) li.classList.add("seatDead");
            if (pid === data.president_id || pid === data.chancellor_id) li.classList.add("seatActive");

            const nameSpan = document.createElement("span");
            nameSpan.className = "seatName";
            nameSpan.textContent = player.name;
            li.appendChild(nameSpan);

            if (!player.alive) {
                const tag = document.createElement("span");
                tag.className = "seatBadge seatBadgeDead";
                tag.textContent = "Dead";
                li.appendChild(tag);
            } else {
                if (pid === data.president_id) {
                    const tag = document.createElement("span");
                    tag.className = "seatBadge seatBadgePres";
                    tag.textContent = "P";
                    tag.title = "President";
                    li.appendChild(tag);
                }
                if (pid === data.chancellor_id) {
                    const tag = document.createElement("span");
                    tag.className = "seatBadge seatBadgeChanc";
                    tag.textContent = "C";
                    tag.title = "Chancellor";
                    li.appendChild(tag);
                }
                if (pid === data.nominee_id && data.phase === "vote") {
                    const tag = document.createElement("span");
                    tag.className = "seatBadge seatBadgeNom";
                    tag.textContent = "N";
                    tag.title = "Nominee";
                    li.appendChild(tag);
                }
            }

            seatList.appendChild(li);
        }
    };

    // ---- Game Log ----
    const renderGameLog = (log) => {
        if (!gameLogList || !log) return;
        if (log.length === lastLogCount) return;
        lastLogCount = log.length;
        gameLogList.innerHTML = "";
        for (const entry of log) {
            const li = document.createElement("li");
            li.className = "gameLogItem";
            li.textContent = entry.message;
            gameLogList.appendChild(li);
        }
        gameLogList.scrollTop = gameLogList.scrollHeight;
    };

    // ---- Phase Banner ----
    const renderPhaseBanner = (data, byId) => {
        if (!phaseBanner || !phaseBannerText) return;
        const phase = data.phase;
        const phaseName = PHASE_NAMES[phase] || phase;
        let text = phaseName;
        let style = "bannerNeutral";

        if (phase === "nominate") {
            const presName = nameFor(data.president_id, byId);
            if (data.you_id === data.president_id) {
                text = "Your turn: Nominate a Chancellor";
                style = "bannerFascist";
            } else {
                text = `${presName} is choosing a Chancellor...`;
            }
        } else if (phase === "vote") {
            const nomName = nameFor(data.nominee_id, byId);
            if (data.self && data.self.action && data.self.action.type === "vote") {
                text = `Vote on ${nomName} for Chancellor`;
                style = "bannerFascist";
            } else {
                text = `Voting on ${nomName}... (${data.vote.cast}/${data.vote.total})`;
            }
        } else if (phase === "legislative_president") {
            if (data.you_id === data.president_id) {
                text = "Your turn: Discard a policy";
                style = "bannerFascist";
            } else {
                text = `${nameFor(data.president_id, byId)} is reviewing policies...`;
            }
        } else if (phase === "legislative_chancellor") {
            if (data.you_id === data.chancellor_id) {
                text = "Your turn: Enact a policy";
                style = "bannerFascist";
            } else {
                text = `${nameFor(data.chancellor_id, byId)} is choosing a policy...`;
            }
        } else if (phase === "veto_pending") {
            if (data.you_id === data.president_id) {
                text = "Veto requested: Approve or Deny?";
                style = "bannerFascist";
            } else {
                text = "Chancellor requested a veto...";
            }
        } else if (phase === "executive_action") {
            const power = (data.executive_action || {}).type || "";
            const powerName = power.replace(/_/g, " ");
            if (data.you_id === data.president_id) {
                text = `Your turn: ${powerName}`;
                style = "bannerFascist";
            } else {
                text = `${nameFor(data.president_id, byId)} is using ${powerName}...`;
            }
        } else if (phase === "game_over") {
            const winner = data.winner === "liberal" ? "Liberals" : "Fascists";
            text = `${winner} Win!`;
            style = data.winner === "liberal" ? "bannerLiberal" : "bannerFascist";
        }

        phaseBannerText.textContent = text;
        phaseBanner.className = "rPhaseBanner " + style;
    };

    // ---- Vote Result Overlay ----
    const showVoteResult = (data, byId) => {
        if (!voteResultOverlay || !data.last_vote) return;
        const lv = data.last_vote;
        const voteId = `${lv.yes}-${lv.no}-${data.announcement?.id || 0}`;
        if (voteId === lastVoteId) return;
        lastVoteId = voteId;

        const passed = lv.yes > lv.no;
        if (voteResultTitle) {
            voteResultTitle.textContent = passed ? "PASSED" : "FAILED";
            voteResultTitle.className = "voteResultTitle " + (passed ? "passed" : "failed");
        }
        if (voteResultTally) {
            voteResultTally.textContent = `${lv.yes} Ja / ${lv.no} Nein`;
        }
        if (voteResultGrid && lv.votes) {
            voteResultGrid.innerHTML = "";
            for (const [pid, vote] of Object.entries(lv.votes)) {
                const div = document.createElement("div");
                div.className = "voteResultEntry " + (vote ? "voteResultJa" : "voteResultNein");
                div.textContent = `${nameFor(pid, byId)}: ${vote ? "Ja" : "Nein"}`;
                voteResultGrid.appendChild(div);
            }
        }
        voteResultOverlay.classList.add("open");
        voteResultShown = true;
    };

    if (voteResultDismiss) {
        voteResultDismiss.addEventListener("click", () => {
            voteResultOverlay.classList.remove("open");
            voteResultShown = false;
        });
    }

    // ---- Nomination ----
    const renderNomination = (data, byId) => {
        if (!listEl) return;
        listEl.innerHTML = "";
        const eligible = new Set(data.self.action.eligible || []);
        for (const pid of data.order || []) {
            if (!eligible.has(pid)) continue;
            const li = document.createElement("li");
            li.className = "playerRow";
            const nameSpan = document.createElement("span");
            nameSpan.className = "playerName";
            nameSpan.textContent = nameFor(pid, byId);
            li.appendChild(nameSpan);

            const btn = document.createElement("button");
            btn.type = "button";
            btn.className = "electBtn electBtnPrimary";
            btn.textContent = "Nominate";
            btn.addEventListener("click", async () => {
                if (actionBusy) return;
                actionBusy = true;
                await postJson(`/api/game/${code}/nominate`, { chancellor_id: pid });
                actionBusy = false;
            });
            li.appendChild(btn);
            listEl.appendChild(li);
        }
        if (electionHint) {
            electionHint.textContent = "Choose an eligible Chancellor.";
        }
    };

    let voteCast = false;

    const showVoteModal = (data, byId) => {
        if (!voteModal) return;
        if (voteModalNominee) voteModalNominee.textContent = nameFor(data.nominee_id, byId);
        if (voteModalPresident) voteModalPresident.textContent = nameFor(data.president_id, byId);
        if (voteModalProgress && data.vote) {
            voteModalProgress.textContent = `${data.vote.cast} / ${data.vote.total} votes cast`;
        }
        if (voteModalBtns) voteModalBtns.classList.toggle("hidden", voteCast);
        if (voteModalWait) voteModalWait.classList.toggle("hidden", !voteCast);
        voteModal.classList.add("open");
    };

    const hideVoteModal = () => {
        if (!voteModal) return;
        voteModal.classList.remove("open");
        voteCast = false;
    };

    // ---- Policy Rendering ----
    const renderPolicyChoices = (policies, onSelect) => {
        if (!actionBody) return;
        actionBody.innerHTML = "";
        const row = document.createElement("div");
        row.className = "policyRow";
        policies.forEach((policy, idx) => {
            const card = document.createElement("button");
            card.type = "button";
            card.className = "policyCard";
            const img = document.createElement("img");
            img.src = policy === "liberal"
                ? "/static/assets/policy.liberal.svg"
                : "/static/assets/policy.fascist.svg";
            img.alt = policy;
            card.appendChild(img);
            card.addEventListener("click", () => onSelect(idx));
            row.appendChild(card);
        });
        actionBody.appendChild(row);
    };

    const renderPolicyTrack = (container, count) => {
        if (!container) return;
        const type = container.dataset.policy || "liberal";
        const slots = BOARD_SLOTS[type] || [];
        const max = slots.length || Number(container.dataset.max || 0);
        const safeMax = Number.isFinite(max) ? max : 0;
        const safeCount = Math.max(0, Math.min(Number(count || 0), safeMax));
        container.innerHTML = "";
        if (!safeMax) return;

        const src = type === "fascist"
            ? "/static/assets/policy.fascist.svg"
            : "/static/assets/policy.liberal.svg";

        for (let i = 0; i < safeMax; i += 1) {
            const slot = document.createElement("div");
            slot.className = "boardSlot";
            const position = slots[i];
            if (position) {
                slot.style.setProperty("--slot-x", `${position.x}%`);
                slot.style.setProperty("--slot-y", `${position.y}%`);
            } else {
                const x = ((i + 0.5) / safeMax) * 100;
                slot.style.setProperty("--slot-x", `${x}%`);
            }
            if (i < safeCount) {
                const img = document.createElement("img");
                img.className = "boardPolicyCard";
                img.src = src;
                img.alt = `${type} policy`;
                slot.appendChild(img);
            }
            container.appendChild(slot);
        }
    };

    const renderPileStack = (container, count) => {
        if (!container) return;
        container.innerHTML = "";
        const total = Math.min(Math.max(Number(count || 0), 0), 3);
        for (let i = 0; i < total; i += 1) {
            const img = document.createElement("img");
            img.className = "pileStackCard";
            img.src = "/static/assets/policy.back.svg";
            img.alt = "Policy card";
            img.style.setProperty("--stack-x", `${i * 4}px`);
            img.style.setProperty("--stack-y", `${i * -3}px`);
            img.style.setProperty("--stack-rotate", `${(i - 1) * 3}deg`);
            container.appendChild(img);
        }
    };

    const setPlaque = (phase) => {
        if (!plaqueImg) return;
        let key = "citizen";
        if (phase === "legislative_chancellor") {
            key = "chancellor";
        } else if (["nominate", "vote", "legislative_president", "executive_action", "veto_pending"].includes(phase)) {
            key = "president";
        } else if (phase === "game_over") {
            key = "citizen";
        }
        const src = plaqueImg.dataset[key];
        if (src) {
            plaqueImg.src = src;
            plaqueImg.alt = key.charAt(0).toUpperCase() + key.slice(1);
        }
    };

    // ---- End Dashboard ----
    const renderEndDashboard = (data) => {
        if (!endModal || !endTitle || !endSubtitle || !endStats || !endRoleList) return;
        closeModal(actionModal);
        closeModal(electionModal);
        hideVoteModal();
        const winner = data.winner || "unknown";
        const winnerLabel = winner === "liberal" ? "Liberals" : "Fascists";
        const reasonMap = {
            liberal_policies: "by enacting five Liberal Policies",
            fascist_policies: "by enacting six Fascist Policies",
            hitler_elected: "Hitler was elected Chancellor",
            hitler_executed: "Hitler was executed",
        };
        const subtitle = reasonMap[data.victory_reason] || "The game has ended.";
        if (endBadge) {
            endBadge.textContent = `${winnerLabel.toUpperCase()} VICTORY`;
        }
        endTitle.textContent = `${winnerLabel} Win`;
        endSubtitle.textContent = subtitle;

        const stats = data.stats || {};
        const statItems = [
            { label: "Liberal Policies", value: data.liberal_policies ?? 0 },
            { label: "Fascist Policies", value: data.fascist_policies ?? 0 },
            { label: "Elections", value: stats.elections ?? 0 },
            { label: "Failed Elections", value: stats.failed_elections ?? 0 },
            { label: "Executions", value: stats.executions ?? 0 },
            { label: "Investigations", value: stats.investigations ?? 0 },
            { label: "Vetoes Approved", value: stats.vetos_approved ?? 0 },
            { label: "Deck / Discard", value: `${data.policy_deck_count ?? 0} / ${data.policy_discard_count ?? 0}` },
        ];
        endStats.innerHTML = "";
        statItems.forEach((item) => {
            const card = document.createElement("div");
            card.className = "endStatCard";
            const label = document.createElement("div");
            label.className = "endStatLabel";
            label.textContent = item.label;
            const value = document.createElement("div");
            value.className = "endStatValue";
            value.textContent = item.value;
            card.appendChild(label);
            card.appendChild(value);
            endStats.appendChild(card);
        });

        endRoleList.innerHTML = "";
        const roles = data.final_roles || [];
        roles.forEach((player) => {
            const li = document.createElement("li");
            li.className = "endRoleRow";
            const name = document.createElement("span");
            name.className = "endRoleName";
            name.textContent = player.name;

            const meta = document.createElement("div");
            meta.className = "endRoleMeta";

            const roleTag = document.createElement("span");
            roleTag.className = "roleTag";
            if (player.role === "hitler") {
                roleTag.classList.add("roleTagHitler");
                roleTag.textContent = "Hitler";
            } else if (player.role === "fascist") {
                roleTag.classList.add("roleTagFascist");
                roleTag.textContent = "Fascist";
            } else {
                roleTag.classList.add("roleTagLiberal");
                roleTag.textContent = "Liberal";
            }
            meta.appendChild(roleTag);

            if (!player.alive) {
                const deadTag = document.createElement("span");
                deadTag.className = "roleTag roleTagDead";
                deadTag.textContent = "Executed";
                meta.appendChild(deadTag);
            }

            li.appendChild(name);
            li.appendChild(meta);
            endRoleList.appendChild(li);
        });

        openModal(endModal);
        endShown = true;
        SFX.win();
    };

    const dissolveRoom = () => {
        if (roomRoot) roomRoot.classList.add("is-dissolving");
        setTimeout(() => {
            window.location = "/";
        }, 800);
    };

    if (endAcknowledge) {
        endAcknowledge.addEventListener("click", async () => {
            try {
                await fetch(`/api/game/${code}/end_ack`, {
                    method: "POST",
                    headers: { "Content-Type": "application/json" },
                    body: JSON.stringify({}),
                });
            } catch {
                // ignore
            } finally {
                dissolveRoom();
            }
        });
    }

    // ---- Action Modal ----
    const renderActionModal = (data, byId) => {
        if (!actionModal || !actionTitle || !actionBody || !actionActions) return;
        actionBody.innerHTML = "";
        actionActions.innerHTML = "";

        const action = data.self.action;
        if (!action) {
            closeModal(actionModal);
            return;
        }

        if (action.type === "president_discard") {
            actionTitle.textContent = "President: Discard a Policy";
            renderPolicyChoices(action.policies, async (idx) => {
                if (actionBusy) return;
                actionBusy = true;
                await postJson(`/api/game/${code}/legis/president`, { discard_index: idx });
                actionBusy = false;
            });
        } else if (action.type === "chancellor_enact") {
            actionTitle.textContent = "Chancellor: Enact a Policy";
            renderPolicyChoices(action.policies, async (idx) => {
                if (actionBusy) return;
                actionBusy = true;
                await postJson(`/api/game/${code}/legis/chancellor`, { enact_index: idx });
                actionBusy = false;
            });
            if (action.veto_available && action.veto_allowed) {
                const vetoBtn = document.createElement("button");
                vetoBtn.type = "button";
                vetoBtn.className = "btnSmall btnVeto";
                vetoBtn.textContent = "Request Veto";
                vetoBtn.addEventListener("click", async () => {
                    if (actionBusy) return;
                    actionBusy = true;
                    await postJson(`/api/game/${code}/legis/chancellor`, { veto: true });
                    actionBusy = false;
                });
                actionActions.appendChild(vetoBtn);
            }
        } else if (action.type === "veto_decision") {
            actionTitle.textContent = "Veto Request";
            const hint = document.createElement("div");
            hint.className = "actionHint";
            hint.textContent = "The Chancellor has requested to veto this agenda.";
            actionBody.appendChild(hint);

            const approveBtn = document.createElement("button");
            approveBtn.type = "button";
            approveBtn.className = "btnSmall btnSmallPrimary";
            approveBtn.textContent = "Approve Veto";
            approveBtn.addEventListener("click", async () => {
                if (actionBusy) return;
                actionBusy = true;
                await postJson(`/api/game/${code}/veto`, { approve: true });
                actionBusy = false;
            });
            const denyBtn = document.createElement("button");
            denyBtn.type = "button";
            denyBtn.className = "btnSmall";
            denyBtn.textContent = "Deny Veto";
            denyBtn.addEventListener("click", async () => {
                if (actionBusy) return;
                actionBusy = true;
                await postJson(`/api/game/${code}/veto`, { approve: false });
                actionBusy = false;
            });
            actionActions.appendChild(approveBtn);
            actionActions.appendChild(denyBtn);
        } else if (action.type === "executive") {
            const power = action.power || "executive";
            const powerNames = {
                policy_peek: "Policy Peek",
                investigate: "Investigate Loyalty",
                special_election: "Special Election",
                execution: "Execution",
            };
            actionTitle.textContent = powerNames[power] || power.replace(/_/g, " ").toUpperCase();
            const targets = action.targets || [];
            if (power === "policy_peek") {
                const hint = document.createElement("div");
                hint.className = "actionHint";
                hint.textContent = "View the top 3 policies in the draw pile.";
                actionBody.appendChild(hint);
                const btn = document.createElement("button");
                btn.type = "button";
                btn.className = "btnSmall btnSmallPrimary";
                btn.textContent = "View Top 3 Policies";
                btn.addEventListener("click", async () => {
                    if (actionBusy) return;
                    actionBusy = true;
                    await postJson(`/api/game/${code}/executive`, {});
                    actionBusy = false;
                });
                actionActions.appendChild(btn);
            } else {
                const hint = document.createElement("div");
                hint.className = "actionHint";
                if (power === "investigate") {
                    hint.textContent = "Choose a player to investigate their party membership.";
                } else if (power === "special_election") {
                    hint.textContent = "Choose the next Presidential candidate.";
                } else if (power === "execution") {
                    hint.textContent = "Choose a player to execute.";
                }
                actionBody.appendChild(hint);

                const list = document.createElement("ul");
                list.className = "actionList";
                const label = power === "execution"
                    ? "Execute"
                    : power === "investigate"
                        ? "Investigate"
                        : "Choose";
                for (const pid of targets) {
                    const li = document.createElement("li");
                    li.className = "playerRow";
                    const nameSpan = document.createElement("span");
                    nameSpan.className = "playerName";
                    nameSpan.textContent = nameFor(pid, byId);
                    li.appendChild(nameSpan);
                    const btn = document.createElement("button");
                    btn.type = "button";
                    btn.className = "actionBtn actionBtnPrimary";
                    btn.textContent = label;
                    btn.addEventListener("click", async () => {
                        if (actionBusy) return;
                        actionBusy = true;
                        await postJson(`/api/game/${code}/executive`, { target_id: pid });
                        actionBusy = false;
                    });
                    li.appendChild(btn);
                    list.appendChild(li);
                }
                actionBody.appendChild(list);
            }
        }

        openModal(actionModal);
    };

    const renderPrivateInfo = (info) => {
        if (!info || !actionModal || !actionTitle || !actionBody || !actionActions) return;
        if (info.id === lastPrivateId) return;
        lastPrivateId = info.id;

        actionTitle.textContent = "Private Information";
        actionBody.innerHTML = "";
        actionActions.innerHTML = "";

        const msg = document.createElement("div");
        msg.className = "actionHint";
        if (info.type === "policy_peek") {
            msg.textContent = "Top 3 policies in the draw pile:";
            actionBody.appendChild(msg);
            renderPolicyChoices(info.data.policies || [], () => {});
        } else if (info.type === "investigation") {
            const party = (info.data.party || "").toUpperCase();
            msg.textContent = `Investigation result: ${party}`;
            msg.style.fontSize = "18px";
            msg.style.color = info.data.party === "fascist" ? "#f26a50" : "#65b3bf";
            actionBody.appendChild(msg);
        }

        const okBtn = document.createElement("button");
        okBtn.type = "button";
        okBtn.className = "btnSmall btnSmallPrimary";
        okBtn.textContent = "OK";
        okBtn.addEventListener("click", () => {
            closeModal(actionModal);
        });
        actionActions.appendChild(okBtn);
        openModal(actionModal);
    };

    if (closeElectionBtn) {
        closeElectionBtn.addEventListener("click", () => closeModal(electionModal));
    }

    if (voteJaBtn) {
        voteJaBtn.addEventListener("click", async () => {
            if (!currentAction || currentAction.type !== "vote") return;
            if (actionBusy) return;
            actionBusy = true;
            const ok = await postJson(`/api/game/${code}/vote`, { vote: "ja" });
            if (ok) {
                voteCast = true;
                if (voteModalBtns) voteModalBtns.classList.add("hidden");
                if (voteModalWait) voteModalWait.classList.remove("hidden");
            }
            actionBusy = false;
        });
    }

    if (voteNeinBtn) {
        voteNeinBtn.addEventListener("click", async () => {
            if (!currentAction || currentAction.type !== "vote") return;
            if (actionBusy) return;
            actionBusy = true;
            const ok = await postJson(`/api/game/${code}/vote`, { vote: "nein" });
            if (ok) {
                voteCast = true;
                if (voteModalBtns) voteModalBtns.classList.add("hidden");
                if (voteModalWait) voteModalWait.classList.remove("hidden");
            }
            actionBusy = false;
        });
    }

    // ---- Main Render ----
    const renderState = (data) => {
        const byId = new Map(data.players.map((p) => [p.id, p.name]));

        if (presidentEl) presidentEl.textContent = nameFor(data.president_id, byId);
        if (chancellorEl) chancellorEl.textContent = nameFor(data.chancellor_id, byId);
        if (lastPresidentEl) lastPresidentEl.textContent = nameFor(data.last_president_id, byId);
        if (lastChancellorEl) lastChancellorEl.textContent = nameFor(data.last_chancellor_id, byId);
        if (phaseText) phaseText.textContent = PHASE_NAMES[data.phase] || data.phase || "-";
        setPlaque(data.phase);
        if (nomineeName) nomineeName.textContent = nameFor(data.nominee_id, byId);
        if (trackerCount) trackerCount.textContent = data.election_tracker ?? 0;
        if (liberalCount) liberalCount.textContent = data.liberal_policies ?? 0;
        if (fascistCount) fascistCount.textContent = data.fascist_policies ?? 0;
        if (deckCount) deckCount.textContent = data.policy_deck_count ?? 0;
        if (discardCount) discardCount.textContent = data.policy_discard_count ?? 0;
        renderPolicyTrack(fascistPolicyRow, data.fascist_policies ?? 0);
        renderPolicyTrack(liberalPolicyRow, data.liberal_policies ?? 0);
        if (voteStatus) {
            if (data.phase === "vote") {
                voteStatus.textContent = `${data.vote.cast}/${data.vote.total}`;
            } else if (data.last_vote) {
                voteStatus.textContent = `${data.last_vote.yes} Ja / ${data.last_vote.no} Nein`;
            } else {
                voteStatus.textContent = "-";
            }
        }

        // Seat board + game log + phase banner
        renderSeatBoard(data, byId);
        renderGameLog(data.log);
        renderPhaseBanner(data, byId);

        if (data.announcement && data.announcement.message) {
            if (data.announcement.id !== lastAnnouncementId) {
                lastAnnouncementId = data.announcement.id;
                const msg = data.announcement.message;
                showToast(msg);

                // Sound effects based on event type
                if (msg.includes("Policy was enacted")) SFX.policy();
                else if (msg.includes("Election passed") || msg.includes("Election failed")) SFX.vote();
                else if (msg.includes("executed") || msg.includes("win")) SFX.alert();
                else SFX.notify();

                // Show vote result overlay when election resolves
                if (data.last_vote && data.last_vote.votes &&
                    (msg.includes("Election passed") || msg.includes("Election failed"))) {
                    showVoteResult(data, byId);
                }
            }
        }

        if (data.winner) {
            renderEndDashboard(data);
            return;
        }

        const prevAction = currentAction;
        currentAction = data.self ? data.self.action : null;

        // Play notification when it becomes your turn
        if (currentAction && (!prevAction || prevAction.type !== currentAction.type)) {
            SFX.notify();
        }

        if (currentAction && currentAction.type === "nominate") {
            openModal(electionModal);
            renderNomination(data, byId);
        } else {
            closeModal(electionModal);
        }

        if (currentAction && currentAction.type === "vote") {
            showVoteModal(data, byId);
        } else if (data.phase === "vote") {
            // Show vote modal with progress even after casting vote
            if (voteModal) {
                if (voteModalNominee) voteModalNominee.textContent = nameFor(data.nominee_id, byId);
                if (voteModalPresident) voteModalPresident.textContent = nameFor(data.president_id, byId);
                if (voteModalProgress && data.vote) {
                    voteModalProgress.textContent = `${data.vote.cast} / ${data.vote.total} votes cast`;
                }
                if (voteModalBtns) voteModalBtns.classList.add("hidden");
                if (voteModalWait) voteModalWait.classList.remove("hidden");
                voteModal.classList.add("open");
            }
        } else {
            hideVoteModal();
        }

        if (currentAction && currentAction.type !== "nominate" && currentAction.type !== "vote") {
            renderActionModal(data, byId);
        } else {
            closeModal(actionModal);
        }

        if (!currentAction && data.self && data.self.private_info) {
            renderPrivateInfo(data.self.private_info);
        }
    };

    const refresh = async () => {
        try {
            const res = await fetch(`/api/game/${code}/state`, { cache: "no-store" });
            if (!res.ok) {
                if (res.status === 404) {
                    dissolveRoom();
                }
                return;
            }
            const data = await res.json();
            if (!data.ok) return;
            renderState(data);
        } catch {
            // ignore
        }
    };

    refresh();
    setInterval(refresh, 1500);
})();
