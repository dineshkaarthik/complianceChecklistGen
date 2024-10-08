document.addEventListener('DOMContentLoaded', function () {
    const uploadForm = document.getElementById('upload-form');
    if (uploadForm) {
        uploadForm.addEventListener('submit', handleUpload);
    }

    const deleteButtons = document.querySelectorAll('.delete-btn');
    deleteButtons.forEach(button => {
        button.addEventListener('click', handleDelete);
    });

    const showApiUsageButton = document.getElementById('show-api-usage');
    const apiUsageModal = document.getElementById('api-usage-modal');
    const closeButton = apiUsageModal.querySelector('.close');

    showApiUsageButton.addEventListener('click', function () {
        fetchApiUsage();
        apiUsageModal.style.display = 'block';
    });

    closeButton.addEventListener('click', function () {
        apiUsageModal.style.display = 'none';
    });

    window.addEventListener('click', function (event) {
        if (event.target === apiUsageModal) {
            apiUsageModal.style.display = 'none';
        }
    });

    const tabButtons = document.querySelectorAll('.tab-button');
    const tabPanes = document.querySelectorAll('.tab-pane');

    tabButtons.forEach(button => {
        button.addEventListener('click', () => {
            const tabName = button.getAttribute('data-tab');

            tabButtons.forEach(btn => btn.classList.remove('active'));
            tabPanes.forEach(pane => pane.classList.remove('active'));

            button.classList.add('active');
            document.getElementById(`${tabName}-tab`).classList.add('active');
        });
    });

    const chatForm = document.getElementById('chat-form');
    const chatInput = document.getElementById('chat-input');
    const chatMessages = document.getElementById('chat-messages');

    if (chatForm && chatInput && chatMessages) {
        chatForm.addEventListener('submit', function (e) {
            e.preventDefault();
            const message = chatInput.value.trim();
            if (message) {
                addMessageToChat('You', message);
                chatInput.value = '';
                sendMessageToBackend(message);
            }
        });
    }

    pollDocumentStatus();
});

async function handleUpload(e) {
    e.preventDefault();
    const form = e.target;
    const formData = new FormData(form);

    const loadingElement = document.getElementById('loading');
    const messageElement = document.getElementById('message');
    const errorMessageElement = document.getElementById('error-message');

    if (loadingElement) loadingElement.classList.remove('hidden');
    if (messageElement) messageElement.classList.add('hidden');
    if (errorMessageElement) errorMessageElement.classList.add('hidden');

    try {
        const response = await fetch('/upload', {
            method: 'POST',
            body: formData
        });

        const result = await response.json();

        if (response.ok) {
            if (messageElement) {
                messageElement.textContent = result.message;
                messageElement.classList.remove('hidden');
            }
            pollDocumentStatus();
        } else {
            throw new Error(result.error || 'An error occurred');
        }
    } catch (error) {
        handleError(error);
    } finally {
        if (loadingElement) loadingElement.classList.add('hidden');
    }
}

async function pollDocumentStatus() {
    const pollInterval = 5000;
    const maxAttempts = 120;
    let attempts = 0;

    const poll = async () => {
        try {
            const response = await fetch('/get_checklists');
            if (!response.ok) {
                throw new Error(`HTTP error! status: ${response.status}`);
            }
            const result = await response.json();

            displayResults(result);

            if (result.completed < result.total_documents) {
                attempts++;
                if (attempts < maxAttempts) {
                    setTimeout(poll, pollInterval);
                } else {
                    const messageElement = document.getElementById('message');
                    if (messageElement) {
                        messageElement.textContent = 'Document processing is taking longer than expected. Please check back later.';
                    }
                }
            }
        } catch (error) {
            handleError(error);
        }
    };

    poll();
}

function displayResults(result) {
    const resultContainer = document.getElementById('result-container');
    if (!resultContainer) return;

    let textOutput = '';
    for (const [filename, data] of Object.entries(result.results)) {
        textOutput += `Filename: ${filename}\n`;
        for (const [key, value] of Object.entries(data)) {
            textOutput += `  ${key}: ${value}\n`;
        }
        textOutput += '\n';
    }

    const textContainer = document.createElement('pre');
    textContainer.textContent = textOutput;
    resultContainer.innerHTML = '';
    resultContainer.appendChild(textContainer);

    resultContainer.classList.remove('hidden');
    displayDocumentStatus(result);
}

function displayDocumentStatus(result) {
    const statusContainer = document.getElementById('document-status');
    if (!statusContainer) return;

    statusContainer.innerHTML = '';

    for (const [filename, status] of Object.entries(result.processing)) {
        const processingElement = createStatusElement(filename, 'processing', status);
        statusContainer.appendChild(processingElement);
    }

    for (const [filename, error] of Object.entries(result.errors)) {
        const failedElement = createStatusElement(filename, 'failed', error);
        statusContainer.appendChild(failedElement);
    }

    statusContainer.classList.remove('hidden');
}

function createStatusElement(filename, status, content) {
    const element = document.createElement('div');
    element.className = `status-item ${status}`;

    const header = document.createElement('h3');
    header.textContent = filename;
    element.appendChild(header);

    const statusText = document.createElement('p');
    statusText.textContent = content;
    element.appendChild(statusText);

    if (status === 'processing') {
        const spinner = document.createElement('div');
        spinner.className = 'spinner';
        element.appendChild(spinner);
    } else if (status === 'failed') {
        const errorText = document.createElement('p');
        errorText.textContent = content;
        element.appendChild(errorText);

        const retryButton = document.createElement('button');
        retryButton.textContent = 'Retry';
        retryButton.addEventListener('click', () => retryProcessing(filename));
        element.appendChild(retryButton);
    }

    return element;
}

async function retryProcessing(filename) {
    try {
        const response = await fetch(`/retry/${filename}`, { method: 'POST' });
        const result = await response.json();
        if (response.ok) {
            alert(`Retrying processing for ${filename}`);
            pollDocumentStatus();
        } else {
            throw new Error(result.error || 'An error occurred');
        }
    } catch (error) {
        handleError(error);
    }
}

function handleDelete(e) {
    e.preventDefault();
    const filename = e.target.dataset.filename;
    if (filename && confirm(`Are you sure you want to delete ${filename}?`)) {
        e.target.closest('form').submit();
    }
}

async function fetchApiUsage() {
    try {
        const response = await fetch('/api_usage');
        const data = await response.json();
        displayApiUsage(data);
    } catch (error) {
        console.error('Error fetching API usage:', error);
        document.getElementById('api-usage-content').innerHTML = '<p>Error fetching API usage data</p>';
    }
}

function displayApiUsage(data) {
    const container = document.getElementById('api-usage-content');
    let html = '<table><tr><th>API Name</th><th>Usage Count</th></tr>';
    for (const [apiName, count] of Object.entries(data)) {
        html += `<tr><td>${apiName}</td><td>${count}</td></tr>`;
    }
    html += '</table>';
    container.innerHTML = html;
}

function handleError(error) {
    console.error('Error:', error);
    const errorMessageElement = document.getElementById('error-message');
    if (errorMessageElement) {
        errorMessageElement.textContent = error.message;
        errorMessageElement.classList.remove('hidden');
    }
}

function addMessageToChat(sender, message) {
    const chatMessages = document.getElementById('chat-messages');
    if (chatMessages) {
        const messageElement = document.createElement('div');
        messageElement.className = 'chat-message';
        messageElement.innerHTML = `<strong>${sender}:</strong> ${message}`;
        chatMessages.appendChild(messageElement);
        chatMessages.scrollTop = chatMessages.scrollHeight;
    }
}

async function sendMessageToBackend(message) {
    try {
        const response = await fetch('/chatbot', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({ message: message }),
        });
        const data = await response.json();
        if (response.ok) {
            if (data.response) {
                addMessageToChat('Chatbot', data.response);
            } else {
                addMessageToChat('Chatbot', 'I\'m sorry, I couldn\'t find any relevant information. Can you please rephrase your question?');
            }
        } else {
            throw new Error(data.error || 'An error occurred');
        }
    } catch (error) {
        console.error('Error sending message to backend:', error);
        addMessageToChat('Chatbot', 'Sorry, an error occurred. Please try again.');
    }
}