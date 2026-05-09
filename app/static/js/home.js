// ===========================
// ПЕРЕКЛЮЧЕНИЕ СТРАНИЦ
// ===========================
const menuButtons = document.querySelectorAll('.floating-menu button[data-page]');
const pages = document.querySelectorAll('.page');

menuButtons.forEach(btn => {
    btn.addEventListener('click', () => {
        const targetId = btn.dataset.page;

        pages.forEach(p => p.classList.remove('active'));
        document.getElementById(targetId).classList.add('active');

        menuButtons.forEach(b => b.classList.remove('active'));
        btn.classList.add('active');
    });
});

checkAuthState();

// Закрытие баннера вручную
function closeBanner() {
    const banner = document.getElementById('auth-banner');
    if (banner) {
        banner.classList.remove('visible');
    }
}
// Делаем функцию доступной для onclick в HTML
window.closeBanner = closeBanner;

// ===========================
// ПРОВЕРКА АВТОРИЗАЦИИ
// ===========================
function checkAuthState() {
    const token = localStorage.getItem('token');
    const banner = document.getElementById('auth-banner');
    const profileContent = document.getElementById('profile-content');
    const profilePrompt = document.getElementById('profile-auth-prompt');
    const setupCard = document.getElementById('preg-setup-card');
    const dateInput = document.getElementById('preg-start-date');
    const setBtn = document.getElementById('btn-set-pregnancy');

    // Ограничиваем выбор только прошедшими/текущими днями
    if (dateInput) {
        dateInput.max = new Date().toISOString().split("T")[0];
    }

    if (!token) {
        // 🔴 НЕ АВТОРИЗОВАН
        if (banner) banner.classList.add('visible');
        document.body.classList.add('banner-visible');

        if (profileContent) profileContent.style.display = 'none';
        if (profilePrompt) {
            profilePrompt.style.display = 'block';
            profilePrompt.innerHTML = `
                <h2>🔒 Профиль доступен только после входа</h2>
                <p>Войдите в аккаунт, чтобы видеть личную статистику и настройки.</p>
                <a href="/auth/login" class="btn-profile-login">Войти в систему</a>
            `;
        }
    } else {
        // 🟢 АВТОРИЗОВАН
        if (banner) banner.classList.remove('visible');
        document.body.classList.remove('banner-visible');

        if (profilePrompt) profilePrompt.style.display = 'none';
        if (profileContent) profileContent.style.display = 'block';

        // Опционально: здесь можно сделать fetch('/auth/me') и подставить реальное имя
        // Загружаем данные дашборда, чтобы узнать, есть ли беременность
        fetch('/api/dashboard', {
            headers: { 'Authorization': `Bearer ${token}` }
        })
        .then(res => res.json())
        .then(data => {
            const hasPregnancy = data.active_pregnancy && data.active_pregnancy.last_menstruation_date;

            if (setupCard) {
                if (hasPregnancy) {
                    setupCard.classList.remove('visible');
                    setupCard.classList.add('hidden');
                } else {
                    setupCard.classList.remove('hidden');
                    setupCard.classList.add('visible');
                }
            }

            // Обновляем статистику дней (если у вас уже есть логика вывода срока)
            if (hasPregnancy && document.getElementById('preg-days')) {
                const lmp = new Date(data.active_pregnancy.last_menstruation_date);
                const days = Math.floor((new Date() - lmp) / (1000 * 60 * 60 * 24));
                const weeks = Math.floor(days / 7);
                document.getElementById('preg-days').textContent = `${days} (${weeks})`;
                document.querySelector('#preg-stat-container .label').textContent = 'Дней (недель)';
            }

            if (hasPregnancy) {
                updateCalendarFromDB(
                    data.active_pregnancy.last_menstruation_date,
                    data.active_pregnancy.due_date
                );
            }
        })
        .catch(err => console.warn('Не удалось загрузить профиль:', err));

        // Обработчик кнопки сохранения
        if (setBtn && !setBtn.dataset.initialized) {
            setBtn.dataset.initialized = 'true';
            setBtn.addEventListener('click', async () => {
                const selectedDate = dateInput.value;
                if (!selectedDate) {
                    alert('Пожалуйста, выберите дату');
                    return;
                }

                setBtn.disabled = true;
                setBtn.textContent = 'Сохранение...';

                try {
                    const res = await fetch('/api/pregnancies', {
                        method: 'POST',
                        headers: {
                            'Content-Type': 'application/json',
                            'Authorization': `Bearer ${token}`
                        },
                        body: JSON.stringify({ last_menstruation_date: selectedDate })
                    });

                    if (res.ok) {
                        setupCard.classList.remove('visible');
                        setupCard.classList.add('hidden');
                        alert('✅ Дата успешно установлена! Срок пересчитан.');
                        // Перезагружаем дашборд для обновления статистики
                        checkAuthState();
                    } else {
                        const errData = await res.json();
                        alert(errData.detail || 'Ошибка сохранения');
                    }
                } catch (e) {
                    console.error(e);
                    alert('Ошибка соединения');
                } finally {
                    setBtn.disabled = false;
                    setBtn.textContent = 'Установить дату беременности';
                }
            });
        }
    }
}
// ===========================
// КЛИК ПО ДНЮ КАЛЕНДАРЯ
// ===========================
document.getElementById('calendar-days').addEventListener('click', (e) => {
    if (e.target.tagName !== 'SPAN') return;

    const day = parseInt(e.target.textContent);
    if (!day || e.target.classList.contains('other-month')) return;

    // Показываем панель результатов
    showDayResults(displayYear, displayMonth, day);
});

function showDayResults(year, month, day) {
    const panel = document.getElementById('day-results-panel');
    const dateEl = document.getElementById('results-date');
    const emptyEl = document.getElementById('results-empty');
    const contentEl = document.getElementById('results-content');

    // Форматируем дату для заголовка
    const date = new Date(year, month, day);
    const options = { day: 'numeric', month: 'long', year: 'numeric' };
    dateEl.textContent = `📅 ${date.toLocaleDateString('ru-RU', options)}`;

    // 🔹 Здесь можно загрузить реальные данные с бэкенда:
    // fetch(`/api/results?date=${year}-${month+1}-${day}`)...

    // Для демо — генерируем тестовые данные
    const mockResults = getMockTestResults(year, month, day);

    if (mockResults.length === 0) {
        emptyEl.style.display = 'block';
        contentEl.style.display = 'none';
    } else {
        emptyEl.style.display = 'none';
        contentEl.style.display = 'block';
        contentEl.innerHTML = mockResults.map(renderTestCard).join('');
    }

    // Показываем панель с анимацией
    panel.classList.add('visible');

    // Плавный скролл к панели (если не видно)
    panel.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
}

function closeResultsPanel() {
    const panel = document.getElementById('day-results-panel');
    panel.classList.remove('visible');
}

// 🔹 Вспомогательные функции для демо-данных
function getMockTestResults(year, month, day) {
    // В реальном проекте здесь будет fetch к вашему API
    // Для примера возвращаем данные только для "сегодняшнего" дня
    const today = new Date();
    if (year === today.getFullYear() && month === today.getMonth() && day === today.getDate()) {
        return [
            { name: 'ХГЧ', value: 1250, unit: 'мЕд/мл', status: 'normal', note: '5-6 недель' },
            { name: 'Прогестерон', value: 28.4, unit: 'нг/мл', status: 'normal', note: 'в пределах нормы' },
            { name: 'ТТГ', value: 3.2, unit: 'мЕд/л', status: 'warning', note: 'контроль через 2 недели' }
        ];
    }
    // Для других дней — пусто (или можно сгенерировать случайные)
    return [];
}

function renderTestCard(test) {
    return `
        <div class="test-result-card">
            <div class="test-info">
                <h4>${test.name}</h4>
                <p>${test.note || ''}</p>
            </div>
            <div class="test-value">
                <span class="value">${test.value}</span>
                <span class="unit">${test.unit}</span>
                ${test.status ? `<span class="status ${test.status}">${getStatusText(test.status)}</span>` : ''}
            </div>
        </div>
    `;
}

function getStatusText(status) {
    const map = { normal: 'Норма', warning: 'Контроль', critical: 'Внимание' };
    return map[status] || '';
}

// Делаем функции доступными для onclick в HTML
window.closeResultsPanel = closeResultsPanel;
window.openTestModal = () => alert('Функция добавления теста будет доступна в следующей версии 👶');

// ===========================
// ПРИВЕТСТВИЕ ПО ВРЕМЕНИ СУТОК
// ===========================
function updateGreeting() {
    const hour = new Date().getHours();
    const heading = document.getElementById('greeting-text');
    const sub = document.getElementById('greeting-sub');

    const username = document.getElementById('greeting-section')?.dataset.username || 'Гость';

    let greetingText = '';

    if (hour >= 5 && hour < 12) {
        greetingText = `Доброе утро, ${username}!`;
        sub.textContent = 'Начните день с продуктивностью 🌅';
    } else if (hour >= 12 && hour < 18) {
        greetingText = `Добрый день, ${username}!`;
        sub.textContent = 'Продолжайте в том же духе ☀️';
    } else if (hour >= 18 && hour < 23) {
        greetingText = `Добрый вечер, ${username}!`;
        sub.textContent = 'Время подвести итоги дня 🌆';
    } else {
        greetingText = `Доброй ночи, ${username}!`;
        sub.textContent = 'Пора отдохнуть 🌙';
    }

    heading.textContent = greetingText;
}

updateGreeting();

// ===========================
// ФУНКЦИЯ ОБНОВЛЕНИЯ КАЛЕНДАРЯ
// ===========================
function updateCalendarFromDB(startDateStr, endDateStr) {
    const cal = document.getElementById('calendar');
    if (!cal) return;

    // Обновляем data-атрибуты для совместимости
    cal.dataset.rangeStart = startDateStr;
    cal.dataset.rangeEnd = endDateStr;

    // Парсим даты
    const rStart = new Date(startDateStr + 'T00:00:00');
    const rEnd = new Date(endDateStr + 'T00:00:00');

    // Перерисовываем календарь с новым диапазоном
    renderCalendar(rStart, rEnd);
}

// ===========================
// КАЛЕНДАРЬ
// ===========================
const monthNames = [
    'Январь', 'Февраль', 'Март', 'Апрель', 'Май', 'Июнь',
    'Июль', 'Август', 'Сентябрь', 'Октябрь', 'Ноябрь', 'Декабрь'
];

let currentDate = new Date();
let displayYear = currentDate.getFullYear();
let displayMonth = currentDate.getMonth();

function renderCalendar(rangeStart = null, rangeEnd = null) {
    const monthYearEl = document.getElementById('month-year');
    const daysContainer = document.getElementById('calendar-days');

    monthYearEl.textContent = `${monthNames[displayMonth]} ${displayYear}`;
    daysContainer.innerHTML = '';

    const firstDay = new Date(displayYear, displayMonth, 1);
    const lastDay = new Date(displayYear, displayMonth + 1, 0);

    let startWeekday = firstDay.getDay();
    startWeekday = startWeekday === 0 ? 6 : startWeekday - 1;

    const today = new Date();

    // 🔹 Нормализуем даты диапазона (убираем время, оставляем только день)
    const hStart = rangeStart ? new Date(rangeStart.getFullYear(), rangeStart.getMonth(), rangeStart.getDate()) : null;
    const hEnd   = rangeEnd   ? new Date(rangeEnd.getFullYear(), rangeEnd.getMonth(), rangeEnd.getDate())   : null;

    // 1️⃣ Дни предыдущего месяца
    const prevMonthLast = new Date(displayYear, displayMonth, 0).getDate();
    for (let i = startWeekday - 1; i >= 0; i--) {
        const span = document.createElement('span');
        span.classList.add('other-month');
        span.textContent = prevMonthLast - i;
        daysContainer.appendChild(span);
    }

    // 2️⃣ Дни текущего месяца
    for (let d = 1; d <= lastDay.getDate(); d++) {
        const span = document.createElement('span');
        span.textContent = d;
        const currentDate = new Date(displayYear, displayMonth, d);

        // Сегодняшний день
        if (d === today.getDate() && displayMonth === today.getMonth() && displayYear === today.getFullYear()) {
            span.classList.add('today');
        }

        // 🔹 Проверка попадания в выделенный диапазон
        if (hStart && hEnd) {
            const time = currentDate.getTime();
            if (time >= hStart.getTime() && time <= hEnd.getTime()) {
                span.classList.add('highlighted');
                if (time === hStart.getTime()) span.classList.add('range-start');
                if (time === hEnd.getTime())   span.classList.add('range-end');
            }
        }

        daysContainer.appendChild(span);
    }

    // 3️⃣ Дни следующего месяца
    const totalCells = startWeekday + lastDay.getDate();
    const remaining = totalCells % 7 === 0 ? 0 : 7 - (totalCells % 7);
    for (let i = 1; i <= remaining; i++) {
        const span = document.createElement('span');
        span.classList.add('other-month');
        span.textContent = i;
        daysContainer.appendChild(span);
    }
}
const cal = document.getElementById('calendar');
const rStart = cal.dataset.rangeStart ? new Date(cal.dataset.rangeStart + 'T00:00:00') : null;
const rEnd   = cal.dataset.rangeEnd   ? new Date(cal.dataset.rangeEnd   + 'T00:00:00') : null;

renderCalendar(rStart, rEnd);

// Привяжите к кнопкам переключения месяцев:
document.getElementById('prev-month').addEventListener('click', () => {
    displayMonth--;
    if (displayMonth < 0) { displayMonth = 11; displayYear--; }
    renderCalendar(rStart, rEnd);
});

document.getElementById('next-month').addEventListener('click', () => {
    displayMonth++;
    if (displayMonth > 11) { displayMonth = 0; displayYear++; }
    renderCalendar(rStart, rEnd);
});

// ===========================
// ПЛАВАЮЩЕЕ МЕНЮ (DRAG & DROP)
// ===========================
const floatingMenu = document.getElementById('floating-menu');
let isDragging = false;
let offsetX = 0, offsetY = 0;

// Мышь
floatingMenu.addEventListener('mousedown', (e) => {
    isDragging = true;
    floatingMenu.classList.add('dragging');
    offsetX = e.clientX - floatingMenu.getBoundingClientRect().left;
    offsetY = e.clientY - floatingMenu.getBoundingClientRect().top;
});

document.addEventListener('mousemove', (e) => {
    if (!isDragging) return;
    let x = e.clientX - offsetX;
    let y = e.clientY - offsetY;

    // Не даём выйти за пределы экрана
    x = Math.max(0, Math.min(x, window.innerWidth - floatingMenu.offsetWidth));
    y = Math.max(0, Math.min(y, window.innerHeight - floatingMenu.offsetHeight));

    floatingMenu.style.left = x + 'px';
    floatingMenu.style.top = y + 'px';
    floatingMenu.style.right = 'auto';
});

document.addEventListener('DOMContentLoaded', () => {
    const cal = document.getElementById('calendar');
    if (cal) {
        const rStart = cal.dataset.rangeStart ? new Date(cal.dataset.rangeStart + 'T00:00:00') : null;
        const rEnd   = cal.dataset.rangeEnd   ? new Date(cal.dataset.rangeEnd   + 'T00:00:00') : null;
        renderCalendar(rStart, rEnd);
    }

    const prevBtn = document.getElementById('prev-month');
    const nextBtn = document.getElementById('next-month');

    // Кнопки переключения месяцев
    prevBtn?.addEventListener('click', () => {
        displayMonth--;
        if (displayMonth < 0) { displayMonth = 11; displayYear--; }
        // При переключении месяцев нужно снова передать текущий диапазон из БД, если он есть
        const cal = document.getElementById('calendar');
        const rStart = cal?.dataset.rangeStart ? new Date(cal.dataset.rangeStart + 'T00:00:00') : null;
        const rEnd   = cal?.dataset.rangeEnd   ? new Date(cal.dataset.rangeEnd   + 'T00:00:00') : null;
        renderCalendar(rStart, rEnd);
    });

    nextBtn?.addEventListener('click', () => {
        displayMonth++;
        if (displayMonth > 11) { displayMonth = 0; displayYear++; }
        const cal = document.getElementById('calendar');
        const rStart = cal?.dataset.rangeStart ? new Date(cal.dataset.rangeStart + 'T00:00:00') : null;
        const rEnd   = cal?.dataset.rangeEnd   ? new Date(cal.dataset.rangeEnd   + 'T00:00:00') : null;
        renderCalendar(rStart, rEnd);
    });

    checkAuthState();
    updateGreeting();
});

document.addEventListener('mouseup', () => {
    isDragging = false;
    floatingMenu.classList.remove('dragging');
});

// Тач (мобильные устройства)
floatingMenu.addEventListener('touchstart', (e) => {
    const touch = e.touches[0];
    isDragging = true;
    floatingMenu.classList.add('dragging');
    offsetX = touch.clientX - floatingMenu.getBoundingClientRect().left;
    offsetY = touch.clientY - floatingMenu.getBoundingClientRect().top;
});

document.addEventListener('touchmove', (e) => {
    if (!isDragging) return;
    const touch = e.touches[0];
    let x = touch.clientX - offsetX;
    let y = touch.clientY - offsetY;

    x = Math.max(0, Math.min(x, window.innerWidth - floatingMenu.offsetWidth));
    y = Math.max(0, Math.min(y, window.innerHeight - floatingMenu.offsetHeight));

    floatingMenu.style.left = x + 'px';
    floatingMenu.style.top = y + 'px';
    floatingMenu.style.right = 'auto';
});

document.addEventListener('touchend', () => {
    isDragging = false;
    floatingMenu.classList.remove('dragging');
});