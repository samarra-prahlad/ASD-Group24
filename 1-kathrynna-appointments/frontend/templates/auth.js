const SHARED_BACKEND = "http://localhost:5000";

function getSession() {
    const raw = localStorage.getItem("session");
    return raw ? JSON.parse(raw) : null;
}

function saveSession(session) {
    localStorage.setItem("session", JSON.stringify(session));
}

function goToLogin() {
    localStorage.removeItem("session");
    window.location.href = `${SHARED_BACKEND}/login`;
}

async function requireSession(allowedRoles) {
    const urlParams = new URLSearchParams(window.location.search);
    const urlToken = urlParams.get("token");

    let token = urlToken;
    if (!token) {
        const existing = getSession();
        token = existing ? existing.token : null;
    }

    if (!token) {
        goToLogin();
        return null;
    }

    let data;
    try {
        const res = await fetch(`${SHARED_BACKEND}/session/verify`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ token })
        });
        data = await res.json();

        if (!res.ok || !data.valid) {
            goToLogin();
            return null;
        }
    } catch (err) {
        alert("Could not reach the login service. Please try again.");
        goToLogin();
        return null;
    }

    const session = {
        token,
        role: data.role,
        patient_id: data.patient_id,
        first_name: data.first_name
    };
    saveSession(session);

    // Remove ?token= from the visible URL once it's safely stored.
    if (urlToken) {
        urlParams.delete("token");
        const cleanUrl = window.location.pathname +
            (urlParams.toString() ? `?${urlParams}` : "");
        window.history.replaceState({}, "", cleanUrl);
    }

    if (allowedRoles && !allowedRoles.includes(session.role)) {
        window.location.href = session.role === "admin" ? "admin.html" : "appointment.html";
        return null;
    }

    return session;
}

function logout() {
    const session = getSession();
    if (session && session.token) {
        fetch(`${SHARED_BACKEND}/logout`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ token: session.token })
        }).catch(() => {});
    }
    goToLogin();
}