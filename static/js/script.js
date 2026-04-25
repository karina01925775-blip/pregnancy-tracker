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
// КАЛЕНДАРЬ
// ===========================
const monthNames = [
    'Январь', 'Февраль', 'Март', 'Апрель', 'Май', 'Июнь',
    'Июль', 'Август', 'Сентябрь', 'Октябрь', 'Ноябрь', 'Декабрь'
];

let currentDate = new Date();
let displayYear = currentDate.getFullYear();
let displayMonth = currentDate.getMonth();

function renderCalendar() {
    const monthYearEl = document.getElementById('month-year');
    const daysContainer = document.getElementById('calendar-days');

    monthYearEl.textContent = `${monthNames[displayMonth]} ${displayYear}`;
    daysContainer.innerHTML = '';

    const firstDay = new Date(displayYear, displayMonth, 1);
    const lastDay = new Date(displayYear, displayMonth + 1, 0);

    // Пн=0 ... Вс=6
    let startWeekday = firstDay.getDay();
    startWeekday = startWeekday === 0 ? 6 : startWeekday - 1;

    const today = new Date();

    // Дни предыдущего месяца
    const prevMonthLast = new Date(displayYear, displayMonth, 0).getDate();
    for (let i = startWeekday - 1; i >= 0; i--) {
        const span = document.createElement('span');
        span.classList.add('other-month');
        span.textContent = prevMonthLast - i;
        daysContainer.appendChild(span);
    }

    // Дни текущего месяца
    for (let d = 1; d <= lastDay.getDate(); d++) {
        const span = document.createElement('span');
        span.textContent = d;
        if (
            d === today.getDate() &&
            displayMonth === today.getMonth() &&
            displayYear === today.getFullYear()
        ) {
            span.classList.add('today');
        }
        daysContainer.appendChild(span);
    }

    // Дни следующего месяца
    const totalCells = startWeekday + lastDay.getDate();
    const remaining = totalCells % 7 === 0 ? 0 : 7 - (totalCells % 7);
    for (let i = 1; i <= remaining; i++) {
        const span = document.createElement('span');
        span.classList.add('other-month');
        span.textContent = i;
        daysContainer.appendChild(span);
    }
}

document.getElementById('prev-month').addEventListener('click', () => {
    displayMonth--;
    if (displayMonth < 0) { displayMonth = 11; displayYear--; }
    renderCalendar();
});

document.getElementById('next-month').addEventListener('click', () => {
    displayMonth++;
    if (displayMonth > 11) { displayMonth = 0; displayYear++; }
    renderCalendar();
});

renderCalendar();

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