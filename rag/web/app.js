document.addEventListener('DOMContentLoaded', () => {
    const dropZone = document.getElementById('drop-zone');
    const fileInput = document.getElementById('file-input');
    const uploadStatus = document.getElementById('upload-status');
    const chatForm = document.getElementById('chat-form');
    const messageInput = document.getElementById('message-input');
    const chatContainer = document.getElementById('chat-container');

    // --- File Upload Logic ---

    dropZone.addEventListener('click', () => fileInput.click());

    dropZone.addEventListener('dragover', (e) => {
        e.preventDefault();
        dropZone.classList.add('border-cta', 'bg-slate-50');
    });

    dropZone.addEventListener('dragleave', () => {
        dropZone.classList.remove('border-cta', 'bg-slate-50');
    });

    dropZone.addEventListener('drop', (e) => {
        e.preventDefault();
        dropZone.classList.remove('border-cta', 'bg-slate-50');
        if (e.dataTransfer.files.length) {
            handleUpload(e.dataTransfer.files[0]);
        }
    });

    fileInput.addEventListener('change', (e) => {
        if (e.target.files.length) {
            handleUpload(e.target.files[0]);
        }
    });

    async function handleUpload(file) {
        showStatus('Uploading...', 'text-slate-500');
        
        const formData = new FormData();
        formData.append('file', file);

        try {
            const response = await fetch('/upload', {
                method: 'POST',
                body: formData
            });

            if (!response.ok) throw new Error('Upload failed');

            const result = await response.json();
            showStatus(`✓ ${file.name} ingested`, 'text-emerald-600');
        } catch (error) {
            showStatus('❌ Upload failed', 'text-red-500');
            console.error(error);
        }
    }

    function showStatus(message, colorClass) {
        uploadStatus.innerHTML = `<p class="text-sm font-medium ${colorClass} animate-pulse">${message}</p>`;
        uploadStatus.classList.remove('hidden');
        
        if (message.includes('ingested') || message.includes('failed')) {
            setTimeout(() => {
                uploadStatus.innerHTML = message.replace('animate-pulse', '');
            }, 2000);
        }
    }

    // --- Chat Logic ---

    // Auto-resize textarea
    messageInput.addEventListener('input', function() {
        this.style.height = 'auto';
        this.style.height = (this.scrollHeight) + 'px';
        if (this.value === '') this.style.height = 'auto';
    });

    // Submit on Enter (without shift)
    messageInput.addEventListener('keydown', (e) => {
        if (e.key === 'Enter' && !e.shiftKey) {
            e.preventDefault();
            chatForm.dispatchEvent(new Event('submit'));
        }
    });

    chatForm.addEventListener('submit', async (e) => {
        e.preventDefault();
        const message = messageInput.value.trim();
        if (!message) return;

        // Reset input
        messageInput.value = '';
        messageInput.style.height = 'auto';

        // Add user message
        appendMessage(message, 'user');

        // Add loading placeholder
        const loadingId = appendLoading();

        try {
            const response = await fetch('/chat', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ query: message })
            });

            if (!response.ok) throw new Error('Chat failed');

            const data = await response.json();
            
            // Remove loading and add bot response
            removeLoading(loadingId);
            appendMessage(data.answer, 'bot');

        } catch (error) {
            removeLoading(loadingId);
            appendMessage("Sorry, I encountered an error processing your request.", 'bot', true);
            console.error(error);
        }
    });

    function appendMessage(text, sender, isError = false) {
        const div = document.createElement('div');
        div.className = 'flex gap-4 max-w-3xl mx-auto animate-fade-in';
        
        if (sender === 'user') {
            div.innerHTML = `
                <div class="flex-1"></div>
                <div class="bg-cta text-white p-4 rounded-2xl rounded-tr-none shadow-sm text-sm leading-relaxed max-w-[80%]">
                    <p>${escapeHtml(text)}</p>
                </div>
                <div class="w-8 h-8 rounded-full bg-slate-200 flex items-center justify-center flex-shrink-0">
                    <svg xmlns="http://www.w3.org/2000/svg" class="h-5 w-5 text-slate-500" viewBox="0 0 20 20" fill="currentColor">
                        <path fill-rule="evenodd" d="M10 9a3 3 0 100-6 3 3 0 000 6zm-7 9a7 7 0 1114 0H3z" clip-rule="evenodd" />
                    </svg>
                </div>
            `;
        } else {
            const contentColor = isError ? 'text-red-600' : 'text-slate-700';
            div.innerHTML = `
                <div class="w-8 h-8 rounded-full bg-cta/10 flex items-center justify-center flex-shrink-0">
                    <svg xmlns="http://www.w3.org/2000/svg" class="h-5 w-5 text-cta" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M13 10V3L4 14h7v7l9-11h-7z" />
                    </svg>
                </div>
                <div class="bg-white p-4 rounded-2xl rounded-tl-none shadow-sm border border-slate-100 ${contentColor} text-sm leading-relaxed">
                    <p>${formatText(text)}</p>
                </div>
                <div class="flex-1"></div>
            `;
        }
        
        chatContainer.appendChild(div);
        scrollToBottom();
    }

    function appendLoading() {
        const id = 'loading-' + Date.now();
        const div = document.createElement('div');
        div.id = id;
        div.className = 'flex gap-4 max-w-3xl mx-auto';
        div.innerHTML = `
            <div class="w-8 h-8 rounded-full bg-cta/10 flex items-center justify-center flex-shrink-0">
                <svg xmlns="http://www.w3.org/2000/svg" class="h-5 w-5 text-cta animate-pulse" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                    <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M13 10V3L4 14h7v7l9-11h-7z" />
                </svg>
            </div>
            <div class="bg-white p-4 rounded-2xl rounded-tl-none shadow-sm border border-slate-100 text-slate-500 text-sm flex items-center gap-1">
                <span class="w-2 h-2 bg-slate-400 rounded-full animate-bounce"></span>
                <span class="w-2 h-2 bg-slate-400 rounded-full animate-bounce" style="animation-delay: 0.1s"></span>
                <span class="w-2 h-2 bg-slate-400 rounded-full animate-bounce" style="animation-delay: 0.2s"></span>
            </div>
        `;
        chatContainer.appendChild(div);
        scrollToBottom();
        return id;
    }

    function removeLoading(id) {
        const el = document.getElementById(id);
        if (el) el.remove();
    }

    function scrollToBottom() {
        chatContainer.scrollTop = chatContainer.scrollHeight;
    }

    function escapeHtml(text) {
        const div = document.createElement('div');
        div.textContent = text;
        return div.innerHTML.replace(/\n/g, '<br>');
    }

    function formatText(text) {
        // Simple formatter for basic markdown-like features
        let formatted = escapeHtml(text);
        // Bold
        formatted = formatted.replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>');
        // Source citations
        formatted = formatted.replace(/ \[Source: (.*?)\]/g, '<span class="text-xs bg-slate-100 text-slate-500 px-1 rounded border border-slate-200">Source: $1</span>');
        return formatted;
    }
});
