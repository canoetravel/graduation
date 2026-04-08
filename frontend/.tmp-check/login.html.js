
    const STORAGE_KEY = "os_judge_users_v1";
    const SESSION_KEY = "os_judge_session_v1";

    const tabs = document.querySelectorAll(".tab-btn");
    const forms = {
      login: document.getElementById("loginForm"),
      register: document.getElementById("registerForm")
    };
    const messageBox = document.getElementById("message");

    function showMessage(text) {
      messageBox.textContent = text;
      messageBox.classList.add("show");
    }

    function clearMessage() {
      messageBox.textContent = "";
      messageBox.classList.remove("show");
    }

    function switchTab(tab) {
      tabs.forEach(btn => btn.classList.toggle("active", btn.dataset.tab === tab));
      Object.keys(forms).forEach(key => forms[key].classList.toggle("active", key === tab));
      clearMessage();
    }

    function loadUsers() {
      try {
        return JSON.parse(localStorage.getItem(STORAGE_KEY)) || {};
      } catch {
        return {};
      }
    }

    function saveUsers(users) {
      localStorage.setItem(STORAGE_KEY, JSON.stringify(users));
    }

    function saveSession(session) {
      sessionStorage.setItem(SESSION_KEY, JSON.stringify(session));
    }

    function restoreSession() {
      try {
        return JSON.parse(sessionStorage.getItem(SESSION_KEY));
      } catch {
        return null;
      }
    }

    function redirectByRole(role) {
      if (role === "teacher") {
        window.location.href = "teacher.html";
      } else {
        window.location.href = "student.html";
      }
    }

    tabs.forEach(btn => {
      btn.addEventListener("click", () => switchTab(btn.dataset.tab));
    });

    document.getElementById("fillDemo").addEventListener("click", () => {
      document.getElementById("loginUsername").value = "demo";
      document.getElementById("loginPassword").value = "123456";
      document.getElementById("loginRole").value = "auto";
      clearMessage();
    });

    document.getElementById("goLogin").addEventListener("click", () => {
      switchTab("login");
    });

    forms.register.addEventListener("submit", event => {
      event.preventDefault();
      clearMessage();

      const username = document.getElementById("regUsername").value.trim();
      const password = document.getElementById("regPassword").value.trim();
      const role = document.getElementById("regRole").value;

      if (!username || !password || !role) {
        showMessage("璇峰～鍐欏畬鏁存敞鍐屼俊鎭€?);
        return;
      }

      const users = loadUsers();
      if (users[username]) {
        showMessage("璇ヨ处鍙峰凡瀛樺湪锛岃鐩存帴鐧诲綍銆?);
        return;
      }
      if (Object.values(users).some(user => user.password === password)) {
        showMessage("璇ュ瘑鐮佸凡琚娇鐢紝璇锋洿鎹㈠瘑鐮併€?);
        return;
      }

      users[username] = { password, role };
      saveUsers(users);
      showMessage("娉ㄥ唽鎴愬姛锛岃鐧诲綍銆?);
      switchTab("login");
      document.getElementById("loginUsername").value = username;
      document.getElementById("loginRole").value = "auto";
    });

    forms.login.addEventListener("submit", event => {
      event.preventDefault();
      clearMessage();

      const username = document.getElementById("loginUsername").value.trim();
      const password = document.getElementById("loginPassword").value.trim();
      const roleSelected = document.getElementById("loginRole").value;

      if (!username || !password) {
        showMessage("璇峰～鍐欒处鍙峰拰瀵嗙爜銆?);
        return;
      }

      const users = loadUsers();
      const user = users[username];
      if (!user || user.password !== password) {
        showMessage("璐﹀彿鎴栧瘑鐮侀敊璇€?);
        return;
      }

      if (roleSelected !== "auto" && user.role !== roleSelected) {
        showMessage("韬唤閫夋嫨涓庢敞鍐屾椂涓嶄竴鑷淬€?);
        return;
      }

      saveSession({ username, role: user.role, loginAt: Date.now() });
      redirectByRole(user.role);
    });

    const existingSession = restoreSession();
    if (existingSession && existingSession.role) {
      redirectByRole(existingSession.role);
    }
  
