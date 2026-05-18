// ===========================
// ГЛОБАЛЬНЫЕ ПЕРЕМЕННЫЕ ИНВАЙТА
// ===========================
window.isPartnerInvite = false;
window.inviteToken = null;

// ===========================
// ПЕРЕКЛЮЧЕНИЕ ВКЛАДОК
// ===========================
function switchTab(tab) {
    const loginPanel = document.getElementById('login-panel');
    const registerPanel = document.getElementById('register-panel');
    const tabs = document.querySelectorAll('.tab');

    if (!loginPanel || !registerPanel) return;

    if (tab === 'login') {
        loginPanel.classList.add('active');
        registerPanel.classList.remove('active');
        tabs[0]?.classList.add('active');
        tabs[1]?.classList.remove('active');
    } else {
        loginPanel.classList.remove('active');
        registerPanel.classList.add('active');
        tabs[0]?.classList.remove('active');
        tabs[1]?.classList.add('active');
    }
    const loginMsg = document.getElementById('login_msg');
    const regMsg = document.getElementById('register_msg');
    if (loginMsg) loginMsg.innerHTML = '';
    if (regMsg) regMsg.innerHTML = '';
}

// ===========================
// ОБРАБОТКА ИНВАЙТ-ССЫЛКИ ПРИ ЗАГРУЗКЕ
// ===========================
document.addEventListener('DOMContentLoaded', () => {
    const params = new URLSearchParams(window.location.search);
    window.inviteToken = params.get('token');
    window.isPartnerInvite = !!window.inviteToken;

    if (window.isPartnerInvite) {
        // 1. Автоматически открываем вкладку регистрации
        switchTab('register');

        // 2. Скрываем поля: Email, Телефон, Пароль
        ['reg_email', 'reg_phone', 'reg_password', 'reg_age_group', 'reg_disclaimer_group'].forEach(id => {
            const input = document.getElementById(id);
            if (input) {
                const group = input.closest('.form-group') || input.parentElement;
                if (group) group.style.display = 'none';
                else input.style.display = 'none';
            }
        });

        // 3. Меняем интерфейс под партнёра
        const regPanel = document.getElementById('register-panel');
        if (regPanel) {
            const h2 = regPanel.querySelector('h2');
            if (h2) h2.textContent = '👥 Присоединиться как партнёр';

            const btn = regPanel.querySelector('.btn-primary, .btn');
            if (btn) btn.textContent = 'Получить доступ';
        }

        // 4. Скрываем переключатель вкладок (чтобы не сбежали)
        const tabsContainer = document.querySelector('.auth-tabs, .tabs');
        if (tabsContainer) tabsContainer.style.display = 'none';
    }
});

// ===========================
// ВХОД (БЕЗ ИЗМЕНЕНИЙ)
// ===========================
async function doLogin() {
    const email = document.getElementById('login_email').value;
    const password = document.getElementById('login_password').value;
    const msg = document.getElementById('login_msg');

    if (!msg) return;

    if (!email || !password) {
        msg.innerHTML = 'Заполните все поля'; msg.className = 'msg error'; return;
    }

    msg.innerHTML = 'Вход...'; msg.className = 'msg';
    const fd = new URLSearchParams();
    fd.append('username', email); fd.append('password', password);

    try {
        const res = await fetch('/auth/login', {
            method: 'POST',
            headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
            body: fd
        });
        const data = await res.json();

        if (res.ok) {
            localStorage.setItem('token', data.access_token);
            msg.innerHTML = 'Успешно!'; msg.className = 'msg success';
            setTimeout(() => { window.location.href = '/'; }, 1000);
        } else {
            msg.innerHTML = data.detail || 'Ошибка'; msg.className = 'msg error';
        }
    } catch (e) {
        msg.innerHTML = 'Ошибка соединения'; msg.className = 'msg error';
    }
}

// ===========================
// РЕГИСТРАЦИЯ / ПРИНЯТИЕ ИНВАЙТА
// ===========================
async function doRegister() {
    const msg = document.getElementById('register_msg');
    const nameInput = document.getElementById('reg_name');

    if (!msg || !nameInput) {
        console.error('❌ Не найдены элементы формы регистрации');
        return;
    }

    // 🔹 РЕЖИМ ПАРТНЁРА (ИНВАЙТ)
    if (window.isPartnerInvite) {
        const name = nameInput?.value.trim();
        if (!name) {
            msg.innerHTML = 'Введите ваше имя'; msg.className = 'msg error'; return;
        }
        msg.innerHTML = 'Подключение...'; msg.className = 'msg';

        try {
            const res = await fetch('/api/invite/accept', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ token: window.inviteToken, full_name: name })
            });
            const data = await res.json();

            if (res.ok) {
                if (data.access_token) localStorage.setItem('token', data.access_token);
                msg.innerHTML = '✅ Доступ получен! Перенаправление...';
                msg.className = 'msg success';
                setTimeout(() => window.location.href = '/', 1500);
            } else {
                msg.innerHTML = data.detail || 'Ошибка активации';
                msg.className = 'msg error';
            }
        } catch (e) {
            msg.innerHTML = 'Ошибка соединения'; msg.className = 'msg error';
        }
        return;
    }

    // 🔹 СТАНДАРТНАЯ РЕГИСТРАЦИЯ ПАЦИЕНТА
    const email = document.getElementById('reg_email').value;
    const name = nameInput.value;
    const phone = document.getElementById('reg_phone').value;
    const password = document.getElementById('reg_password').value;
    const age = document.getElementById('reg_age').value;
    const disclaimerChecked = document.getElementById('reg_disclaimer').checked ;

    if (!email || !name || !password || !age) {
        msg.innerHTML = 'Заполните обязательные поля'; msg.className = 'msg error'; return;
    }

    if (!disclaimerChecked) {
        msg.innerHTML = 'Необходимо принять медицинский дисклеймер'; msg.className = 'msg error'; return;
    }

    if (!age || age < 14 || age > 99) {
        msg.innerHTML = 'Введите корректный возраст (14–99)';
        msg.className = 'msg error';
        return;
    }

    if (password.length < 6) { msg.innerHTML = 'Пароль минимум 6 символов'; msg.className = 'msg error'; return; }
    if (password.length > 128) { msg.innerHTML = 'Пароль не более 128 символов'; msg.className = 'msg error'; return; }

    msg.innerHTML = 'Регистрация...'; msg.className = 'msg';
    try {
        const res = await fetch('/auth/register', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ email, full_name: name, phone: phone || '',
                password, role: 'patient', age, disclaimer_accepted: true })
        });
        const data = await res.json();

        if (res.ok) {
            msg.innerHTML = 'Успешно! Теперь войдите в систему.';
            msg.className = 'msg success';
            setTimeout(() => switchTab('login'), 2000);
        } else {
            msg.innerHTML = data.detail || 'Ошибка'; msg.className = 'msg error';
        }
    } catch (e) {
        msg.innerHTML = 'Ошибка соединения'; msg.className = 'msg error';
    }
}

// Экспорт функций для onclick в HTML
window.switchTab = switchTab;
window.doLogin = doLogin;
window.doRegister = doRegister;
