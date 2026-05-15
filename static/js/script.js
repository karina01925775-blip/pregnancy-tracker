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

// Хранилище событий (в localStorage)
let weekEvents = JSON.parse(localStorage.getItem('weekEvents')) || [];

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
        
        // Формируем дату в формате YYYY-MM-DD
        const currentDayDate = new Date(displayYear, displayMonth, d);
        const dateStr = currentDayDate.toISOString().split('T')[0];
        
        // Проверяем события на этот день
        const dayEvents = weekEvents.filter(e => e.date === dateStr);
        
        if (dayEvents.length > 0) {
            span.classList.add('has-events');
            span.setAttribute('data-event-count', dayEvents.length);
            
            // Проверяем, есть ли просроченные события
            const now = new Date();
            const hasOverdue = dayEvents.some(e => {
                const eventDateTime = new Date(`${e.date}T${e.time}`);
                return eventDateTime < now;
            });
            
            // Добавляем точку-индикатор
            const dot = document.createElement('span');
            dot.classList.add('event-dot');
            if (hasOverdue) {
                dot.classList.add('overdue');
            }
            span.appendChild(dot);
        }
        
        // Обработчик клика на день
        span.addEventListener('click', () => {
            showDayEvents(dateStr);
        });
        
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

// Показ событий выбранного дня
function showDayEvents(dateStr) {
    const dayEventsModalOverlay = document.getElementById('day-events-modal-overlay');
    const dayEventsList = document.getElementById('day-events-list');
    const dayEventsTitle = document.getElementById('day-events-title');
    
    const selectedDate = new Date(dateStr);
    const options = { day: 'numeric', month: 'long', year: 'numeric' };
    dayEventsTitle.textContent = `События на ${selectedDate.toLocaleDateString('ru-RU', options)}`;
    
    dayEventsList.innerHTML = '';
    
    const dayEvents = weekEvents.filter(e => e.date === dateStr).sort((a, b) => {
        const timeA = new Date(`${a.date}T${a.time}`);
        const timeB = new Date(`${b.date}T${b.time}`);
        return timeA - timeB;
    });
    
    if (dayEvents.length === 0) {
        dayEventsList.innerHTML = '<li class="no-events-message">Нет событий на этот день</li>';
    } else {
        dayEvents.forEach(event => {
            const li = document.createElement('li');
            
            let typeIcon = '📝';
            let typeName = event.title;
            switch(event.type) {
                case 'visit':
                    typeIcon = '🩺';
                    typeName = 'Визит к врачу';
                    break;
                case 'analysis':
                    typeIcon = '🧪';
                    typeName = 'Анализы';
                    break;
                case 'ultrasound':
                    typeIcon = '📷';
                    typeName = 'УЗИ';
                    break;
                case 'other':
                    typeIcon = '📝';
                    typeName = event.title || 'Другое';
                    break;
            }
            
            const eventDateTime = new Date(`${event.date}T${event.time}`);
            const now = new Date();
            const isOverdue = eventDateTime < now;
            
            li.innerHTML = `
                <span class="event-type">${typeIcon} ${typeName}</span>
                <span class="event-date">⏰ ${event.time}</span>
                ${event.notes ? `<span class="event-notes">${event.notes}</span>` : ''}
                ${isOverdue ? '<span style="color: #ffeb3b; font-size: 0.8rem;">⚠️ Просрочено</span>' : ''}
                <button class="delete-event-btn" data-event-id="${event.id}">🗑️ Удалить</button>
            `;
            
            dayEventsList.appendChild(li);
        });
        
        // Добавляем обработчики удаления
        dayEventsList.querySelectorAll('.delete-event-btn').forEach(btn => {
            btn.addEventListener('click', (e) => {
                const eventId = parseInt(e.target.getAttribute('data-event-id'));
                if (confirm('Удалить это событие?')) {
                    weekEvents = weekEvents.filter(e => e.id !== eventId);
                    localStorage.setItem('weekEvents', JSON.stringify(weekEvents));
                    showDayEvents(dateStr);
                    renderCalendar();
                }
            });
        });
    }
    
    dayEventsModalOverlay.classList.add('active');
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

// Закрытие модального окна просмотра событий дня
const closeDayEventsBtn = document.getElementById('close-day-events-btn');
const dayEventsModalOverlay = document.getElementById('day-events-modal-overlay');

closeDayEventsBtn.addEventListener('click', () => {
    dayEventsModalOverlay.classList.remove('active');
});

dayEventsModalOverlay.addEventListener('click', (e) => {
    if (e.target === dayEventsModalOverlay) {
        dayEventsModalOverlay.classList.remove('active');
    }
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

// ===========================
// ОБРАБОТЧИК КНОПКИ ДОБАВЛЕНИЯ СОБЫТИЯ В МЕНЮ
// ===========================
const addEventBtnNav = document.getElementById('add-event-btn-nav');
const eventModalOverlay = document.getElementById('event-modal-overlay');
const cancelEventBtn = document.getElementById('cancel-event-btn');
const eventForm = document.getElementById('event-form');
const eventTypeSelect = document.getElementById('event-type');
const eventTitleInput = document.getElementById('event-title');

// Открытие модального окна добавления события
addEventBtnNav.addEventListener('click', () => {
    eventModalOverlay.classList.add('active');
    // Устанавливаем сегодняшнюю дату по умолчанию
    const today = new Date().toISOString().split('T')[0];
    document.getElementById('event-date').value = today;
});

// Закрытие модального окна
cancelEventBtn.addEventListener('click', () => {
    eventModalOverlay.classList.remove('active');
    eventForm.reset();
});

// Закрытие по клику вне окна
eventModalOverlay.addEventListener('click', (e) => {
    if (e.target === eventModalOverlay) {
        eventModalOverlay.classList.remove('active');
        eventForm.reset();
    }
});

// Обработка отправки формы
eventForm.addEventListener('submit', (e) => {
    e.preventDefault();
    
    const type = eventTypeSelect.value;
    const title = eventTitleInput.value.trim();
    const date = document.getElementById('event-date').value;
    const time = document.getElementById('event-time').value;
    const notes = document.getElementById('event-notes').value.trim();
    
    if (!type || !date || !time) {
        alert('Пожалуйста, заполните все обязательные поля');
        return;
    }
    
    const newEvent = {
        id: Date.now(),
        type: type,
        title: title,
        date: date,
        time: time,
        notes: notes
    };
    
    weekEvents.push(newEvent);
    localStorage.setItem('weekEvents', JSON.stringify(weekEvents));
    
    eventModalOverlay.classList.remove('active');
    eventForm.reset();
    renderCalendar(); // Перерисовываем календарь для обновления индикаторов
});

// Синхронизация типа события с полем названия
eventTypeSelect.addEventListener('change', () => {
    const selectedType = eventTypeSelect.value;
    if (selectedType === 'other') {
        eventTitleInput.placeholder = 'Введите название события';
        eventTitleInput.value = '';
        eventTitleInput.disabled = false;
    } else {
        const typeNames = {
            'visit': 'Визит к врачу',
            'analysis': 'Анализы',
            'ultrasound': 'УЗИ'
        };
        eventTitleInput.value = typeNames[selectedType] || '';
        eventTitleInput.placeholder = 'Название события';
        eventTitleInput.disabled = false;
    }
});