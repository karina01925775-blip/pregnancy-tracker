const monthNames = [
    'Январь', 'Февраль', 'Март', 'Апрель', 'Май', 'Июнь',
    'Июль', 'Август', 'Сентябрь', 'Октябрь', 'Ноябрь', 'Декабрь'
];

const categoryLabels = {
    general: 'Общее состояние',
    mood: 'Настроение',
    pain: 'Боль',
    energy: 'Энергия',
    sleep: 'Сон',
    symptoms: 'Симптомы',
    warning_signs: 'Тревожные признаки',
    nutrition: 'Питание',
    baby_movement: 'Шевеления',
    notes: 'Комментарий'
};

const state = {
    displayYear: new Date().getFullYear(),
    displayMonth: new Date().getMonth(),
    rangeStart: null,
    rangeEnd: null,
    currentInviteId: null,
    isDraggingMenu: false,
    dragOffsetX: 0,
    dragOffsetY: 0,
    testHistoryByDate: {}
};

function getToken() {
    return localStorage.getItem('token');
}

function authHeaders(withJson = false) {
    const headers = {};
    const token = getToken();

    if (withJson) {
        headers['Content-Type'] = 'application/json';
    }
    if (token) {
        headers['Authorization'] = `Bearer ${token}`;
    }

    return headers;
}

async function fetchJson(url, options = {}) {
    const response = await fetch(url, options);
    let data = null;

    try {
        data = await response.json();
    } catch (error) {
        data = null;
    }

    if (!response.ok) {
        const message = data?.detail || `Ошибка запроса (${response.status})`;
        throw new Error(message);
    }

    return data;
}

function parseDateOnly(value) {
    if (!value) {
        return null;
    }

    const [year, month, day] = value.split('-').map(Number);
    if (!year || !month || !day) {
        return null;
    }

    return new Date(year, month - 1, day);
}

function formatApiDate(year, month, day) {
    const normalizedMonth = String(month + 1).padStart(2, '0');
    const normalizedDay = String(day).padStart(2, '0');
    return `${year}-${normalizedMonth}-${normalizedDay}`;
}

function escapeHtml(value) {
    return String(value ?? '')
        .replaceAll('&', '&amp;')
        .replaceAll('<', '&lt;')
        .replaceAll('>', '&gt;')
        .replaceAll('"', '&quot;')
        .replaceAll("'", '&#39;');
}

function closeBanner() {
    const banner = document.getElementById('auth-banner');
    if (banner) {
        banner.classList.remove('visible');
    }
}

function switchPage(targetId, button) {
    document.querySelectorAll('.page').forEach((page) => page.classList.remove('active'));
    document.getElementById(targetId)?.classList.add('active');

    document.querySelectorAll('.floating-menu button[data-page]').forEach((menuButton) => {
        menuButton.classList.remove('active');
    });
    button?.classList.add('active');
}

function initMenuNavigation() {
    document.querySelectorAll('.floating-menu button[data-page]').forEach((button) => {
        button.addEventListener('click', () => switchPage(button.dataset.page, button));
    });
}

function setCalendarRange(startDateStr, endDateStr) {
    state.rangeStart = parseDateOnly(startDateStr);
    state.rangeEnd = parseDateOnly(endDateStr);
}

function updateCalendarFromDB(startDateStr, endDateStr) {
    const calendar = document.getElementById('calendar');
    if (!calendar) {
        return;
    }

    calendar.dataset.rangeStart = startDateStr || '';
    calendar.dataset.rangeEnd = endDateStr || '';
    setCalendarRange(startDateStr, endDateStr);
    renderCalendar();
}

function hasHistoryForDate(year, month, day) {
    const key = formatApiDate(year, month, day);
    const records = state.testHistoryByDate[key];
    return Array.isArray(records) && records.length > 0;
}

async function renderCalendar() {
    const monthYearEl = document.getElementById('month-year');
    const daysContainer = document.getElementById('calendar-days');
    if (!monthYearEl || !daysContainer) return;

    monthYearEl.textContent = `${monthNames[state.displayMonth]} ${state.displayYear}`;
    daysContainer.innerHTML = '';

    const firstDay = new Date(state.displayYear, state.displayMonth, 1);
    const lastDay = new Date(state.displayYear, state.displayMonth + 1, 0);
    const today = new Date();

    let startWeekday = firstDay.getDay();
    startWeekday = startWeekday === 0 ? 6 : startWeekday - 1;

    const previousMonthLastDay = new Date(state.displayYear, state.displayMonth, 0).getDate();
    for (let offset = startWeekday - 1; offset >= 0; offset -= 1) {
        const dayCell = document.createElement('span');
        dayCell.classList.add('other-month');
        dayCell.textContent = previousMonthLastDay - offset;
        daysContainer.appendChild(dayCell);
    }

    // 🔹 1. ЗАГРУЖАЕМ СОБЫТИЯ ЗАРАНЕЕ (до отрисовки дней)
    const eventsMap = {};
    if (getToken()) {
        try {
            const dash = await fetchJson('/api/dashboard', { headers: authHeaders() });
            const pregId = dash.active_pregnancy?.id;
            if (pregId) {
                const events = await fetchJson(`/api/pregnancies/${pregId}/events`, { headers: authHeaders() });
                events.forEach(e => {
                    const [y, m, d] = e.event_date.split('-').map(Number);
                    const key = `${y}-${m-1}-${d}`; // месяц в JS: 0-11
                    if (!eventsMap[key]) eventsMap[key] = [];
                    eventsMap[key].push(e);
                });
            }
        } catch (e) { console.warn('Не удалось загрузить события для маркеров', e); }
    }

    const highlightedStart = state.rangeStart ? new Date(state.rangeStart.getFullYear(), state.rangeStart.getMonth(), state.rangeStart.getDate()) : null;
    const highlightedEnd = state.rangeEnd ? new Date(state.rangeEnd.getFullYear(), state.rangeEnd.getMonth(), state.rangeEnd.getDate()) : null;

    // 🔹 2. ОТРИСОВКА ДНЕЙ + МАРКЕРОВ СИНХРОННО
    for (let day = 1; day <= lastDay.getDate(); day += 1) {
        const dayCell = document.createElement('button');
        dayCell.type = 'button';
        dayCell.classList.add('calendar-day');
        dayCell.dataset.day = String(day);

        const dayNumber = document.createElement('span');
        dayNumber.classList.add('calendar-day-number');
        dayNumber.textContent = String(day);
        dayCell.appendChild(dayNumber);

        const cellDate = new Date(state.displayYear, state.displayMonth, day);
        const cellTime = cellDate.getTime();

        if (day === today.getDate() && state.displayMonth === today.getMonth() && state.displayYear === today.getFullYear()) {
            dayCell.classList.add('today');
        }

        if (highlightedStart && highlightedEnd) {
            if (cellTime >= highlightedStart.getTime() && cellTime <= highlightedEnd.getTime()) dayCell.classList.add('highlighted');
            if (cellTime === highlightedStart.getTime()) dayCell.classList.add('range-start');
            if (cellTime === highlightedEnd.getTime()) dayCell.classList.add('range-end');
        }

        if (hasHistoryForDate(state.displayYear, state.displayMonth, day)) {
            const dot = document.createElement('span');
            dot.classList.add('calendar-day-dot');
            dayCell.appendChild(dot);
            dayCell.classList.add('has-events');
        }

        daysContainer.appendChild(dayCell);

        // 🔹 ДОБАВЛЯЕМ ТОЧКУ-МАРКЕР
        const key = `${state.displayYear}-${state.displayMonth}-${day}`;
        if (eventsMap[key] && eventsMap[key].length > 0) {
            dayCell.classList.add('has-events');
            const todayZero = new Date(); todayZero.setHours(0, 0, 0, 0);
            const hasOverdue = eventsMap[key].some(ev => new Date(ev.event_date) < todayZero);

            const marker = document.createElement('span');
            marker.className = `event-marker ${hasOverdue ? 'overdue' : ''} ${eventsMap[key].length > 1 ? 'multiple' : ''}`;
            marker.title = `${eventsMap[key].length} событие(й): ${eventsMap[key].map(e => e.title).join(', ')}`;
            dayCell.appendChild(marker);
        }
    }

    const totalCells = startWeekday + lastDay.getDate();
    const remainingCells = totalCells % 7 === 0 ? 0 : 7 - (totalCells % 7);
    for (let day = 1; day <= remainingCells; day += 1) {
        const dayCell = document.createElement('span');
        dayCell.classList.add('other-month');
        dayCell.textContent = day;
        daysContainer.appendChild(dayCell);
    }
}

function changeMonth(offset) {
    state.displayMonth += offset;

    if (state.displayMonth < 0) {
        state.displayMonth = 11;
        state.displayYear -= 1;
    } else if (state.displayMonth > 11) {
        state.displayMonth = 0;
        state.displayYear += 1;
    }

    renderCalendar();
}

function closeResultsPanel() {
    document.getElementById('day-results-panel')?.classList.remove('visible');
}

function renderHistoryCard(item) {
    const category = categoryLabels[item.category] || 'Ответ';
    return `
        <div class="test-result-card">
            <div class="test-info">
                <h4>${escapeHtml(item.question)}</h4>
                <p>${escapeHtml(item.answer || 'Без ответа')}</p>
            </div>
            <div class="test-value">
                <span class="status normal">${escapeHtml(category)}</span>
            </div>
        </div>
    `;
}

async function showDayResults(year, month, day) {
    const panel = document.getElementById('day-results-panel');
    const dateEl = document.getElementById('results-date');
    const emptyEl = document.getElementById('results-empty');
    const contentEl = document.getElementById('results-content');

    if (!panel || !dateEl || !emptyEl || !contentEl) {
        return;
    }

    const targetDate = new Date(year, month, day);
    dateEl.textContent = `📅 ${targetDate.toLocaleDateString('ru-RU', { day: 'numeric', month: 'long', year: 'numeric' })}`;
    contentEl.innerHTML = '<p>Загрузка результатов...</p>';
    emptyEl.style.display = 'none';
    contentEl.style.display = 'block';
    panel.classList.add('visible');

    if (!getToken()) {
        contentEl.innerHTML = '<p>Войдите в систему, чтобы видеть ответы по дням.</p>';
        return;
    }

    try {
        const history = await fetchJson(`/api/test/history?date=${formatApiDate(year, month, day)}`, {
            headers: authHeaders()
        });

        state.testHistoryByDate[formatApiDate(year, month, day)] = history;

        if (!history.length) {
            emptyEl.style.display = 'block';
            contentEl.style.display = 'none';
        } else {
            emptyEl.style.display = 'none';
            contentEl.style.display = 'block';
            contentEl.innerHTML = history.map(renderHistoryCard).join('');
        }
    } catch (error) {
        contentEl.innerHTML = `<p style="color: #e74c3c;">${escapeHtml(error.message)}</p>`;
    }

    renderCalendar();
    panel.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
}

async function loadDayEvents(year, month, day) {
    const panel = document.getElementById('day-events-panel');
    const dateEl = document.getElementById('events-date');
    const emptyEl = document.getElementById('events-empty');
    const contentEl = document.getElementById('events-content');

    if (!panel || !dateEl || !emptyEl || !contentEl) return;

    const targetDate = new Date(year, month, day);
    const today = new Date();
    today.setHours(0, 0, 0, 0);

    dateEl.textContent = `📅 ${targetDate.toLocaleDateString('ru-RU', { weekday: 'long', day: 'numeric', month: 'long' })}`;
    contentEl.innerHTML = '<p>Загрузка...</p>';
    emptyEl.classList.add('hidden');
    contentEl.style.display = 'block';
    panel.classList.add('visible');

    if (!getToken()) {
        contentEl.innerHTML = '<p>Войдите, чтобы видеть события</p>';
        return;
    }

    try {
        const dashboard = await fetchJson('/api/dashboard', { headers: authHeaders() });
        const pregnancyId = dashboard.active_pregnancy?.id;

        if (!pregnancyId) {
            contentEl.innerHTML = '<p>Укажите срок беременности в профиле</p>';
            return;
        }

        const events = await fetchJson(`/api/pregnancies/${pregnancyId}/events`, {
            headers: authHeaders()
        });

        // Фильтруем события на выбранный день
        const dayEvents = events.filter(e => {
            const eventDate = new Date(e.event_date);
            return eventDate.getDate() === day &&
                   eventDate.getMonth() === month &&
                   eventDate.getFullYear() === year;
        }).sort((a, b) => {
            // Сначала по времени, потом по названию
            if (a.time && b.time) return a.time.localeCompare(b.time);
            if (a.time) return -1;
            if (b.time) return 1;
            return a.title.localeCompare(b.title);
        });

        if (dayEvents.length === 0) {
            emptyEl.classList.remove('hidden');
            contentEl.style.display = 'none';
        } else {
            emptyEl.classList.add('hidden');
            contentEl.style.display = 'block';

            contentEl.innerHTML = dayEvents.map(event => {
                const eventDate = new Date(event.event_date);
                const isOverdue = eventDate < today && (!event.time || event.time < new Date().toTimeString().slice(0,5));
                const statusClass = isOverdue ? 'overdue' : 'upcoming';
                const statusText = isOverdue ? 'Просрочено' : 'Предстоит';

                const typeIcons = { visit: '🩺', test: '🧪', ultrasound: '🔍', other: '📌' };
                const typeIcon = typeIcons[event.event_type] || '📌';

                const timeStr = event.time ? `<span class="event-time">⏰ ${event.time}</span>` : '';
                const descStr = event.description ? `<p class="event-desc">${escapeHtml(event.description)}</p>` : '';

                return `
                    <div class="event-card ${isOverdue ? 'overdue' : ''}">
                        <h4>
                            <span class="event-type-icon">${typeIcon}</span>
                            ${escapeHtml(event.title)}
                        </h4>
                        ${timeStr}
                        ${descStr}
                        <span class="event-status ${statusClass}">${statusText}</span>
                    </div>
                `;
            }).join('');
        }

        panel.scrollIntoView({ behavior: 'smooth', block: 'nearest' });

    } catch (error) {
        contentEl.innerHTML = `<p style="color: #e74c3c;">⚠️ ${escapeHtml(error.message)}</p>`;
    }
}

function closeDayEvents() {
    document.getElementById('day-events-panel')?.classList.remove('visible');
}

function initCalendar() {
    const calendar = document.getElementById('calendar');
    if (!calendar) {
        return;
    }

    setCalendarRange(calendar.dataset.rangeStart, calendar.dataset.rangeEnd);
    renderCalendar();

    document.getElementById('prev-month')?.addEventListener('click', () => changeMonth(-1));
    document.getElementById('next-month')?.addEventListener('click', () => changeMonth(1));

    document.getElementById('calendar-days')?.addEventListener('click', (event) => {
        const target = event.target;
        if (!(target instanceof HTMLElement)) {
            return;
        }

        const dayButton = target.closest('.calendar-day');
        if (!(dayButton instanceof HTMLElement) || dayButton.classList.contains('other-month')) {
            return;
        }

        const day = Number.parseInt(dayButton.dataset.day || '', 10);
        if (!day) {
            return;
        }
        showDayResults(state.displayYear, state.displayMonth, day);
    });
}

function updateGreeting() {
    const heading = document.getElementById('greeting-text');
    const subheading = document.getElementById('greeting-sub');
    const greetingSection = document.getElementById('greeting-section');

    if (!heading || !subheading || !greetingSection) {
        return;
    }

    const hour = new Date().getHours();
    const username = greetingSection.dataset.username || 'Гость';

    if (hour >= 5 && hour < 12) {
        heading.textContent = `Доброе утро, ${username}!`;
        subheading.textContent = 'Пусть день будет спокойным и лёгким.';
        return;
    }

    if (hour >= 12 && hour < 18) {
        heading.textContent = `Добрый день, ${username}!`;
        subheading.textContent = 'Проверьте самочувствие и важные события на сегодня.';
        return;
    }

    if (hour >= 18 && hour < 23) {
        heading.textContent = `Добрый вечер, ${username}!`;
        subheading.textContent = 'Самое время подвести итоги дня.';
        return;
    }

    heading.textContent = `Доброй ночи, ${username}!`;
    subheading.textContent = 'Отдых тоже важная часть заботы о себе.';
}

function updateProfileSummary(data) {
    const greetingSection = document.getElementById('greeting-section');
    const profileCard = document.getElementById('profile-content');
    const profileName = profileCard?.querySelector('h2');
    const profileEmail = profileCard?.querySelector('.email');
    const pregDays = document.getElementById('preg-days');
    const pregLabel = document.querySelector('#preg-stat-container .label');

    if (greetingSection) {
        greetingSection.dataset.username = data.user.full_name || 'Гость';
    }
    if (profileName) {
        profileName.textContent = data.user.full_name || 'Гость';
    }
    if (profileEmail) {
        profileEmail.textContent = data.user.email || '';
    }

    if (pregDays && pregLabel) {
        if (data.active_pregnancy?.current_week) {
            pregDays.textContent = `${data.active_pregnancy.current_week} неделя`;
            pregLabel.textContent = 'Текущий срок';
        } else {
            pregDays.textContent = '--';
            pregLabel.textContent = 'Срок беременности';
        }
    }

    updateGreeting();
}

async function checkAuthState() {
    const rawToken = getToken();
    const token = (rawToken && rawToken !== 'null' && rawToken !== 'undefined') ? rawToken : null;

    const banner = document.getElementById('auth-banner');
    const profileContent = document.getElementById('profile-content');
    const profilePrompt = document.getElementById('profile-auth-prompt');
    const setupCard = document.getElementById('preg-setup-card');
    const dateInput = document.getElementById('preg-start-date');
    const testButton = document.getElementById('test-widget');
    const partnerBlock = document.getElementById('partner-profile');
    const partnerInviteSection = document.getElementById('partner-invite-section');
    const aiWidget = document.getElementById('ai-widget');

    if (dateInput) dateInput.max = new Date().toISOString().split('T')[0];

    if (profileContent) profileContent.style.display = 'none';
    if (profilePrompt) profilePrompt.style.display = 'none';
    if (banner) banner.classList.remove('visible');
    document.body.classList.remove('banner-visible');
    if (testButton) testButton.style.display = 'none';
    if (partnerBlock) partnerBlock.classList.add('hidden');
    if (partnerInviteSection) partnerInviteSection.style.display = 'none';
    if (aiWidget) aiWidget.classList.add('hidden');

    if (!token) {
        if (banner) { banner.classList.add('visible'); document.body.classList.add('banner-visible'); }
        if (profilePrompt) {
            profilePrompt.style.display = 'block';
            profilePrompt.innerHTML = `
                <h2>Профиль доступен после входа</h2>
                <p>Авторизуйтесь, чтобы увидеть срок беременности, ежедневный тест и историю ответов.</p>
                <a href="/auth/login" class="btn-profile-login">Войти в систему</a>
            `;
        }
        if (setupCard) setupCard.classList.add('hidden');
        return;
    }

    try {
        const data = await fetchJson('/api/dashboard', { headers: authHeaders() });

        if (aiWidget) aiWidget.classList.remove('hidden');

        if (profilePrompt) profilePrompt.style.display = 'none';
        if (profileContent) profileContent.style.display = 'block';

        document.body.classList.remove('is-patient', 'is-partner', 'is-doctor');
        document.body.classList.add(`is-${data.user.role}`);
        updateProfileSummary(data);

        const hasPregnancy = Boolean(data.active_pregnancy?.last_menstruation_date);
        if (hasPregnancy) {
            updateCalendarFromDB(data.active_pregnancy.last_menstruation_date, data.active_pregnancy.due_date);
        } else {
            updateCalendarFromDB('', '');
        }

        if (data.user.role === 'partner') {
            profileContent?.classList.add('hidden');
            partnerBlock?.classList.remove('hidden');
            if (document.getElementById('partner-name')) document.getElementById('partner-name').textContent = data.user.full_name || 'Партнёр';
            if (document.getElementById('following-name')) document.getElementById('following-name').textContent = data.followed_patient_name || 'Не назначен';
            if (setupCard) setupCard.classList.add('hidden');
            if (testButton) testButton.style.display = 'none';
            if (partnerInviteSection) partnerInviteSection.style.display = 'none';
            return;
        }

        partnerBlock?.classList.add('hidden');
        profileContent?.classList.remove('hidden');

        if (setupCard) {
            setupCard.classList.toggle('visible', !hasPregnancy);
            setupCard.classList.toggle('hidden', hasPregnancy);
        }
        if (testButton) testButton.style.display = hasPregnancy ? 'inline-flex' : 'none';
        if (partnerInviteSection) partnerInviteSection.style.display = hasPregnancy ? 'block' : 'none';
        if (data.user.role === 'patient' && hasPregnancy) await loadPartnerInvites();

    } catch (error) {
        console.warn('Токен невалиден, очищаем localStorage:', error.message);
        localStorage.removeItem('token');
        sessionStorage.clear();
        checkAuthState();
    }
}

function openTestModal() {
    const modal = document.getElementById('test-modal');
    if (!modal) {
        return;
    }

    modal.classList.remove('hidden');
    loadTestQuestions();
}

function closeTestModal() {
    document.getElementById('test-modal')?.classList.add('hidden');
    document.getElementById('test-form')?.reset();
}

async function loadTestQuestions() {
    const container = document.getElementById('test-questions-container');
    if (!container) {
        return;
    }

    container.innerHTML = '<p>Загрузка вопросов...</p>';

    try {
        const questions = await fetchJson('/api/test/questions', {
            headers: authHeaders()
        });

        container.innerHTML = questions.map((question) => {
            if (question.type === 'text') {
                return `
                    <div class="test-question">
                        <label>${escapeHtml(question.text)}${question.required ? ' *' : ''}</label>
                        <textarea
                            name="q_${question.id}"
                            rows="3"
                            placeholder="Ваш ответ..."
                            ${question.required ? 'required' : ''}
                        ></textarea>
                    </div>
                `;
            }

            const options = (question.options || []).map((option) => `
                <label>
                    <input type="radio" name="q_${question.id}" value="${escapeHtml(option)}" ${question.required ? 'required' : ''}>
                    ${escapeHtml(option)}
                </label>
            `).join('');

            return `
                <div class="test-question">
                    <label>${escapeHtml(question.text)}${question.required ? ' *' : ''}</label>
                    <div class="test-options">${options}</div>
                </div>
            `;
        }).join('');
    } catch (error) {
        container.innerHTML = `<p style="color: #e74c3c;">${escapeHtml(error.message)}</p>`;
    }
}

function initSymptomChecker() {
    const toggle = document.getElementById('symptom-toggle');
    const panel = document.getElementById('symptom-panel');
    const input = document.getElementById('symptom-input');
    const btn = document.getElementById('symptom-btn');
    const output = document.getElementById('symptom-output');

    if (!toggle || !panel || !input || !btn || !output) return;

    // Раскрытие/скрытие панели
    toggle.addEventListener('click', () => {
        panel.classList.toggle('hidden');
        if (!panel.classList.contains('hidden')) input.focus();
    });

    // Отправка на анализ
    btn.addEventListener('click', async () => {
        const text = input.value.trim();
        if (!text) return;

        btn.disabled = true;
        btn.textContent = 'Анализ...';
        output.className = 'symptom-output hidden';

        try {
            const res = await fetchJson('/api/symptom/analyze', {
                method: 'POST',
                headers: authHeaders(true),
                body: JSON.stringify({ symptom_text: text })
            });

            output.className = `symptom-output ${res.classification}`;
            let html = `<strong>${res.classification === 'critical' ? '🚨' : res.classification === 'concerning' ? '⚠️' : '✅'} Результат анализа:</strong>
                        <p>${res.recommendation}</p>`;
            if (res.actions) {
                html += `<hr style="border:0; border-top:1px solid currentColor; margin:10px 0; opacity:0.3;"><pre>${res.actions}</pre>`;
            }
            output.innerHTML = html;
            output.classList.remove('hidden');
        } catch (error) {
            output.className = 'symptom-output concerning';
            output.innerHTML = `<p>⚠️ ${error.message}</p>`;
            output.classList.remove('hidden');
        } finally {
            btn.disabled = false;
            btn.textContent = 'Анализировать ИИ';
        }
    });

    input.addEventListener('keydown', (e) => {
        if (e.key === 'Enter') btn.click();
    });
}

function initTestForm() {
    document.getElementById('test-form')?.addEventListener('submit', async (event) => {
        event.preventDefault();

        const answers = [];
        document.querySelectorAll('#test-questions-container .test-question').forEach((questionBlock) => {
            const field = questionBlock.querySelector('[name]');
            const questionId = field?.name?.replace('q_', '');
            const answer =
                questionBlock.querySelector('input:checked')?.value ||
                questionBlock.querySelector('textarea')?.value?.trim();

            if (questionId && answer) {
                answers.push({ question_id: Number.parseInt(questionId, 10), answer });
            }
        });

        if (!answers.length) {
            alert('Пожалуйста, заполните хотя бы один ответ.');
            return;
        }

        try {
            await fetchJson('/api/test/submit', {
                method: 'POST',
                headers: authHeaders(true),
                body: JSON.stringify({ answers })
            });

            alert('Спасибо! Ваше самочувствие сохранено.');
            closeTestModal();

            const today = new Date();
            await showDayResults(today.getFullYear(), today.getMonth(), today.getDate());
        } catch (error) {
            alert(error.message);
        }
    });
}

async function loadPartnerInvites() {
    const section = document.getElementById('partner-invite-section');
    if (!section || !getToken()) {
        return;
    }

    try {
        const invites = await fetchJson('/api/partner-invites', {
            headers: authHeaders()
        });

        section.style.display = 'block';
        if (invites.length > 0) {
            showActiveInvite(invites[0]);
        } else {
            document.getElementById('no-invite-msg').style.display = 'block';
            document.getElementById('active-invite-box').style.display = 'none';
        }
    } catch (error) {
        console.warn('Не удалось загрузить приглашения:', error);
        section.style.display = 'none';
    }
}

function showActiveInvite(invite) {
    state.currentInviteId = invite.id;
    document.getElementById('invite-link-input').value = invite.link;
    document.getElementById('invite-expire').textContent = `Истекает: ${new Date(invite.expires_at).toLocaleDateString('ru-RU')}`;
    document.getElementById('no-invite-msg').style.display = 'none';
    document.getElementById('active-invite-box').style.display = 'block';
}

function showInviteMsg(text, type = '') {
    const element = document.getElementById('invite-msg');
    if (!element) {
        return;
    }

    element.textContent = text;
    element.className = `invite-msg ${type}`.trim();

    if (type) {
        setTimeout(() => {
            element.textContent = '';
            element.className = 'invite-msg';
        }, 3000);
    }
}

async function generateInvite() {
    showInviteMsg('Создание ссылки...');

    try {
        const invite = await fetchJson('/api/partner-invites', {
            method: 'POST',
            headers: authHeaders(true),
            body: JSON.stringify({})
        });
        showActiveInvite(invite);
        showInviteMsg('Ссылка готова.', 'success');
    } catch (error) {
        showInviteMsg(error.message, 'error');
    }
}

async function revokeInvite(id, silent = false) {
    if (!id) {
        return;
    }
    if (!silent && !confirm('Отозвать приглашение? Ссылка перестанет работать.')) {
        return;
    }

    try {
        await fetchJson(`/api/partner-invites/${id}`, {
            method: 'DELETE',
            headers: authHeaders()
        });

        if (!silent) {
            document.getElementById('active-invite-box').style.display = 'none';
            document.getElementById('no-invite-msg').style.display = 'block';
            showInviteMsg('Приглашение удалено.', 'success');
        }
    } catch (error) {
        showInviteMsg(error.message, 'error');
    }
}

async function regenerateInvite() {
    if (state.currentInviteId) {
        await revokeInvite(state.currentInviteId, true);
    }
    await generateInvite();
}

async function copyInviteLink() {
    const input = document.getElementById('invite-link-input');
    if (!input) {
        return;
    }

    try {
        await navigator.clipboard.writeText(input.value);
        showInviteMsg('Ссылка скопирована.', 'success');
    } catch (error) {
        input.select();
        document.execCommand('copy');
        showInviteMsg('Ссылка скопирована.', 'success');
    }
}

function logout() {
    if (!confirm('Вы действительно хотите выйти из аккаунта?')) {
        return;
    }

    localStorage.removeItem('token');
    sessionStorage.clear();
    window.location.href = '/auth/login';
}

function updateMenuPosition(clientX, clientY, floatingMenu) {
    let newX = clientX - state.dragOffsetX;
    let newY = clientY - state.dragOffsetY;

    newX = Math.max(0, Math.min(newX, window.innerWidth - floatingMenu.offsetWidth));
    newY = Math.max(0, Math.min(newY, window.innerHeight - floatingMenu.offsetHeight));

    floatingMenu.style.left = `${newX}px`;
    floatingMenu.style.top = `${newY}px`;
    floatingMenu.style.right = 'auto';
}

// ===== СОБЫТИЯ НЕДЕЛИ =====
async function deleteEvent(id) {
    if (!confirm('Удалить событие?')) return;
    try {
        const dash = await fetchJson('/api/dashboard', { headers: authHeaders() });
        await fetch(`/api/pregnancies/${dash.active_pregnancy.id}/events/${id}`, { method: 'DELETE', headers: authHeaders() });
        loadWeeklyEvents();
    } catch(err) { alert(err.message); }
}

function initFloatingMenu() {
    const floatingMenu = document.getElementById('floating-menu');
    const dragHandle = floatingMenu?.querySelector('.drag-handle');

    if (!floatingMenu || !dragHandle) {
        return;
    }

    dragHandle.addEventListener('mousedown', (event) => {
        state.isDraggingMenu = true;
        state.dragOffsetX = event.clientX - floatingMenu.getBoundingClientRect().left;
        state.dragOffsetY = event.clientY - floatingMenu.getBoundingClientRect().top;
        floatingMenu.classList.add('dragging');
    });

    document.addEventListener('mousemove', (event) => {
        if (!state.isDraggingMenu) {
            return;
        }
        updateMenuPosition(event.clientX, event.clientY, floatingMenu);
    });

    document.addEventListener('mouseup', () => {
        state.isDraggingMenu = false;
        floatingMenu.classList.remove('dragging');
    });

    dragHandle.addEventListener('touchstart', (event) => {
        const touch = event.touches[0];
        state.isDraggingMenu = true;
        state.dragOffsetX = touch.clientX - floatingMenu.getBoundingClientRect().left;
        state.dragOffsetY = touch.clientY - floatingMenu.getBoundingClientRect().top;
        floatingMenu.classList.add('dragging');
    }, { passive: true });

    document.addEventListener('touchmove', (event) => {
        if (!state.isDraggingMenu) {
            return;
        }
        const touch = event.touches[0];
        updateMenuPosition(touch.clientX, touch.clientY, floatingMenu);
    }, { passive: true });

    document.addEventListener('touchend', () => {
        state.isDraggingMenu = false;
        floatingMenu.classList.remove('dragging');
    });
}

// ===== МОДАЛЬНОЕ ОКНО: СОБЫТИЯ НЕДЕЛИ =====

function openWeeklyModal() {
    const modal = document.getElementById('weekly-modal');
    if (!modal) return;
    modal.classList.remove('hidden');
    loadWeeklyEvents();

    // Установите минимальную дату = сегодня
    const dateInput = document.getElementById('event-date');
    if (dateInput) {
        dateInput.min = new Date().toISOString().split('T')[0];
        dateInput.value = dateInput.min;
    }
}

function closeWeeklyModal() {
    const modal = document.getElementById('weekly-modal');
    if (modal) modal.classList.add('hidden');

    // Сброс формы
    const form = document.querySelector('.add-event-form');
    if (form) form.reset();
}

async function loadWeeklyEvents() {
    const container = document.getElementById('weekly-events-list');
    if (!container) return;

    container.innerHTML = '<p class="loading">Загрузка событий...</p>';

    try {
        // Получаем активную беременность из dashboard
        const dashboard = await fetchJson('/api/dashboard', { headers: authHeaders() });
        const pregnancyId = dashboard.active_pregnancy?.id;

        if (!pregnancyId) {
            container.innerHTML = '<p class="weekly-empty">📭 Сначала укажите дату беременности в профиле</p>';
            return;
        }

        // Загружаем события
        const events = await fetchJson(`/api/pregnancies/${pregnancyId}/events`, {
            headers: authHeaders()
        });

        // Фильтруем: только события текущей недели
        const today = new Date();
        const weekStart = new Date(today);
        weekStart.setDate(today.getDate() - today.getDay() + 1); // Понедельник
        weekStart.setHours(0, 0, 0, 0);
        const weekEnd = new Date(weekStart);
        weekEnd.setDate(weekStart.getDate() + 6);

        const weeklyEvents = events.filter(e => {
            const eventDate = new Date(e.event_date);
            return eventDate >= weekStart && eventDate <= weekEnd;
        }).sort((a, b) => new Date(a.event_date) - new Date(b.event_date));

        if (weeklyEvents.length === 0) {
            container.innerHTML = `
                <p class="weekly-empty">
                    📭 На этой неделе нет запланированных событий.<br>
                    Добавьте визит, анализ или УЗИ ниже.
                </p>
            `;
            return;
        }

        container.innerHTML = weeklyEvents.map(event => {
            const eventDate = new Date(event.event_date);
            const dateStr = eventDate.toLocaleDateString('ru-RU', { weekday: 'short', day: 'numeric', month: 'short' });
            const timeStr = event.time ? ` в ${event.time}` : '';
            const typeClass = `type-${event.type || 'other'}`;
            const typeIcon = { visit: '🩺', test: '🧪', ultrasound: '🔍', other: '📌' }[event.type || 'other'];

            return `
                <div class="weekly-event-card ${typeClass}">
                    <div class="event-info">
                        <h4>${typeIcon} ${escapeHtml(event.title)}</h4>
                        <span class="event-time">${dateStr}${timeStr}</span>
                        ${event.description ? `<p>${escapeHtml(event.description)}</p>` : ''}
                    </div>
                    <div class="event-actions">
                        <button class="btn-event-action" onclick="editEvent(${event.id})" title="Редактировать">✏️</button>
                        <button class="btn-event-action delete" onclick="deleteEvent(${event.id})" title="Удалить">🗑️</button>
                    </div>
                </div>
            `;
        }).join('');

    } catch (error) {
        container.innerHTML = `<p style="color: #e74c3c;">⚠️ ${escapeHtml(error.message)}</p>`;
    }
}

async function saveEvent() {
    const title = document.getElementById('event-title')?.value.trim();
    const description = document.getElementById('event-desc')?.value.trim();
    const eventDate = document.getElementById('event-date')?.value;
    const eventTime = document.getElementById('event-time')?.value;
    const eventType = document.getElementById('event-type')?.value;

    if (!title || !eventDate) {
        alert('Заполните название и дату события');
        return;
    }

    try {
        const dashboard = await fetchJson('/api/dashboard', { headers: authHeaders() });
        const pregnancyId = dashboard.active_pregnancy?.id;

        if (!pregnancyId) {
            alert('Сначала укажите дату беременности в профиле');
            return;
        }

        // Рассчитываем неделю беременности для события
        const lmp = new Date(dashboard.active_pregnancy.last_menstruation_date);
        const eventDt = new Date(eventDate);
        const daysDiff = Math.floor((eventDt - lmp) / (1000 * 60 * 60 * 24));
        const weekOfPregnancy = Math.max(1, Math.floor(daysDiff / 7) + 1);

        await fetchJson(`/api/pregnancies/${pregnancyId}/events`, {
            method: 'POST',
            headers: { ...authHeaders(true) },
            body: JSON.stringify({
                title,
                description: description || null,
                event_date: eventDate,
                time: eventTime || null,
                type: eventType,
                week_of_pregnancy: weekOfPregnancy
            })
        });

        alert('✅ Событие добавлено!');
        loadWeeklyEvents();

        // Сброс формы
        document.getElementById('event-title').value = '';
        document.getElementById('event-desc').value = '';
        document.getElementById('event-time').value = '';

    } catch (error) {
        alert(`❌ ${error.message}`);
    }
}

async function deleteEvent(eventId) {
    if (!confirm('Удалить это событие?')) return;

    try {
        const dashboard = await fetchJson('/api/dashboard', { headers: authHeaders() });
        const pregnancyId = dashboard.active_pregnancy?.id;

        if (!pregnancyId) return;

        // В вашем API нет DELETE, поэтому используем флаг или просто перезагружаем
        // Если нужно — добавьте эндпоинт DELETE в backend/main.py
        await fetchJson(`/api/pregnancies/${pregnancyId}/events/${eventId}`, {
            method: 'DELETE',
            headers: authHeaders()
        });

        loadWeeklyEvents();
    } catch (error) {
        alert(`❌ ${error.message}`);
    }
}

function editEvent(eventId) {
    // Заглушка: можно расширить для редактирования
    alert('Редактирование события (функция в разработке)');
}

function initWeeklyEvents() {
    // Закрытие по клику вне окна
    document.getElementById('weekly-modal')?.addEventListener('click', e => {
        if (e.target.id === 'weekly-modal') closeWeeklyModal();
    });
    // Enter в поле названия
    document.getElementById('event-title')?.addEventListener('keydown', e => {
        if (e.key === 'Enter') { e.preventDefault(); saveEvent(); }
    });
}

function initPregnancySetup() {
    const dateInput = document.getElementById('preg-start-date');
    const weekInput = document.getElementById('preg-week');
    const setButton = document.getElementById('btn-set-pregnancy');
    const setupCard = document.getElementById('preg-setup-card');
    if (!dateInput || !setButton || !setupCard) return;

    setButton.addEventListener('click', async () => {
        const lmp = dateInput.value;
        const week = weekInput?.value ? parseInt(weekInput.value) : null;
        if (!lmp && !week) { alert('Выберите дату или укажите срок в неделях.'); return; }

        setButton.disabled = true;
        setButton.textContent = 'Сохранение...';

        try {
            const payload = {};
            if (lmp) payload.last_menstruation_date = lmp;
            if (week) payload.gestational_week = week;

            const res = await fetchJson('/api/pregnancies', {
                method: 'POST',
                headers: authHeaders(true),
                body: JSON.stringify(payload)
            });

            // Обновляем профиль новым периодом
            const pregDays = document.getElementById('preg-days');
            const pregLabel = document.querySelector('#preg-stat-container .label');
            if (pregDays) pregDays.textContent = `${res.current_week} неделя`;
            if (pregLabel) pregLabel.textContent = res.period;

            setupCard.classList.remove('visible');
            setupCard.classList.add('hidden');
            dateInput.value = '';
            if (weekInput) weekInput.value = '';

            alert(`✅ Данные сохранены!\n📅 Период: ${res.period}\n🍼 ПДР: ${new Date(res.due_date).toLocaleDateString('ru-RU')}`);
            await checkAuthState();
        } catch (error) {
            alert(error.message);
        } finally {
            setButton.disabled = false;
            setButton.textContent = 'Установить';
        }
    });
}
function initApp() {
    initMenuNavigation();
    initCalendar();
    initTestForm();
    initFloatingMenu();
    initPregnancySetup();
    initWeeklyEvents();
    initSymptomChecker();
    updateGreeting();
    checkAuthState();

    document.addEventListener('click', (e) => {
        const panel = document.getElementById('day-events-panel');
        const calendar = document.getElementById('calendar');
        if (panel?.classList.contains('visible') &&
            !panel.contains(e.target) &&
            !calendar?.contains(e.target)) {
            closeDayEvents();
        }
    });
}

window.closeBanner = closeBanner;
window.closeResultsPanel = closeResultsPanel;
window.openTestModal = openTestModal;
window.closeTestModal = closeTestModal;
window.generateInvite = generateInvite;
window.regenerateInvite = regenerateInvite;
window.revokeInvite = revokeInvite;
window.copyInviteLink = copyInviteLink;
window.logout = logout;

initApp();
