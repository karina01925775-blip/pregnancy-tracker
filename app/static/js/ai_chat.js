let aiRoomId = null;
let isAILoading = false;

function toggleAIChat() {
    const win = document.getElementById('ai-chat-window');
    win.classList.toggle('hidden');

    if (!win.classList.contains('hidden') && !aiRoomId) {
        initAIChat();
    }
}

async function initAIChat() {
    const token = localStorage.getItem('token');
    if (!token) {
        addMessage('bot', 'Пожалуйста, войдите в систему, чтобы общаться с ИИ.');
        return;
    }

    try {
        const res = await fetch('/api/chat/ai/create', {
            method: 'POST',
            headers: { 'Authorization': `Bearer ${token}` }
        });
        const data = await res.json();
        if (res.ok) {
            aiRoomId = data.room_id;
        } else {
            addMessage('bot', 'Не удалось создать чат. Попробуйте позже.');
        }
    } catch (e) {
        console.error(e);
    }
}

function handleAIEnter(e) {
    if (e.key === 'Enter') sendAIMessage();
}

async function sendAIMessage() {
    const input = document.getElementById('ai-input');
    const text = input.value.trim();
    if (!text) return;

    addMessage('user', text);
    input.value = '';

    // Создаем сообщение-загрузчик и получаем САМ ЭЛЕМЕНТ (не ID!)
    const loaderDiv = addMessage('bot', 'Печатает...', true);
    const token = localStorage.getItem('token');

    try {
        const res = await fetch(`/api/chat/ai/${aiRoomId}/ask`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'Authorization': `Bearer ${token}`
            },
            body: JSON.stringify({ message: text })
        });

        if (!res.ok) {
            const err = await res.json();
            throw new Error(err.detail || `Ошибка сервера: ${res.status}`);
        }

        const data = await res.json();
        console.log('✅ Получен ответ:', data);

        // ✅ Удаляем загрузчик (теперь это работает!)
        if (loaderDiv && loaderDiv.parentNode) {
            loaderDiv.parentNode.removeChild(loaderDiv);
        }

        // Показываем настоящий ответ
        addMessage('bot', data.reply);

    } catch (e) {
        console.error('❌ Ошибка:', e);
        if (loaderDiv && loaderDiv.parentNode) {
            loaderDiv.parentNode.removeChild(loaderDiv);
        }
        addMessage('bot', `⚠️ ${e.message}`);
    }
}

function addMessage(sender, text, isLoader = false) {
    const container = document.getElementById('ai-messages');
    const div = document.createElement('div');
    div.className = `message ${sender}`;

    // Если это загрузчик - даем ему ID для поиска
    if (isLoader) {
        div.id = 'ai-loader-' + Date.now();
    }

    // Преобразуем переносы строк в <br>
    div.innerHTML = `<p>${text.replace(/\n/g, '<br>')}</p>`;

    container.appendChild(div);
    container.scrollTop = container.scrollHeight;

    // ✅ ВОЗВРАЩАЕМ САМ ЭЛЕМЕНТ, а не его ID!
    return div;
}