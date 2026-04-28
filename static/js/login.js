// ===== ПЕРЕКЛЮЧЕНИЕ ВКЛАДОК =====
function switchTab(tab) {
    const loginPanel = document.getElementById('login-panel');
    const registerPanel = document.getElementById('register-panel');
    const tabs = document.querySelectorAll('.tab');

    if (tab === 'login') {
        loginPanel.classList.add('active');
        registerPanel.classList.remove('active');
        tabs[0].classList.add('active');
        tabs[1].classList.remove('active');
    } else {
        loginPanel.classList.remove('active');
        registerPanel.classList.add('active');
        tabs[0].classList.remove('active');
        tabs[1].classList.add('active');
    }
    document.getElementById('login_msg').innerHTML = '';
    document.getElementById('register_msg').innerHTML = '';
}

// ===== ВХОД =====
async function doLogin() {
    const email = document.getElementById('login_email').value;
    const password = document.getElementById('login_password').value;
    const msg = document.getElementById('login_msg');

    if (!email || !password) {
        msg.innerHTML = 'Заполните все поля';
        msg.className = 'msg error';
        return;
    }

    msg.innerHTML = 'Вход...';
    msg.className = 'msg';

    const fd = new URLSearchParams();
    fd.append('username', email);
    fd.append('password', password);

    try {
        const res = await fetch('/auth/login', {
            method: 'POST',
            headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
            body: fd
        });
        const data = await res.json();

        if (res.ok) {
            localStorage.setItem('token', data.access_token);
            msg.innerHTML = 'Успешно!';
            msg.className = 'msg success';
            setTimeout(() => { window.location.href = '/'; }, 1000);
        } else {
            msg.innerHTML = data.detail || 'Ошибка';
            msg.className = 'msg error';
        }
    } catch (e) {
        msg.innerHTML = 'Ошибка соединения';
        msg.className = 'msg error';
    }
}

// ===== РЕГИСТРАЦИЯ =====
async function doRegister() {
    const email = document.getElementById('reg_email').value;
    const name = document.getElementById('reg_name').value;
    const phone = document.getElementById('reg_phone').value;
    const password = document.getElementById('reg_password').value;
    const msg = document.getElementById('register_msg');

    if (!email || !name || !password) {
        msg.innerHTML = 'Заполните обязательные поля';
        msg.className = 'msg error';
        return;
    }
    if (password.length < 6) {
    msg.innerHTML = 'Пароль минимум 6 символов';
    msg.className = 'msg error';
    return;
    }
    if (password.length > 128) {
        msg.innerHTML = 'Пароль не более 128 символов';
        msg.className = 'msg error';
        return;
    }

    msg.innerHTML = 'Регистрация...';
    msg.className = 'msg';

    try {
        const res = await fetch('/auth/register', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                email, full_name: name, phone: phone || '', password, role: 'patient'
            })
        });
        const data = await res.json();

        if (res.ok) {
            msg.innerHTML = 'Успешно!';
            msg.className = 'msg success';
            setTimeout(() => switchTab('login'), 2000);
        } else {
            msg.innerHTML = data.detail || 'Ошибка';
            msg.className = 'msg error';
        }
    } catch (e) {
        msg.innerHTML = 'Ошибка соединения';
        msg.className = 'msg error';
    }
}

// Делаем функции глобальными для onclick
window.switchTab = switchTab;
window.doLogin = doLogin;
window.doRegister = doRegister;