document.addEventListener('DOMContentLoaded', function() {
    // DOM Elements
    const chatMessages = document.getElementById('chat-messages');
    const userInput = document.getElementById('user-input');
    const sendButton = document.getElementById('send-button');
    const uploadArea = document.getElementById('upload-area');
    const fileUpload = document.getElementById('file-upload');
    const progressBar = document.getElementById('progress-bar');
    const completionPercentage = document.getElementById('completion-percentage');
    
    // Initialize user ID
    const userId = uuid.v4();
    
    // State variables
    let isUploadVisible = false;
    let completionPercent = 0;
    let userName = "";
    let isWaitingForResponse = false;
    
    // Initial message from the chatbot
    sendInitialMessage();
    
    // Event Listeners
    sendButton.addEventListener('click', sendMessage);
    userInput.addEventListener('keypress', function(e) {
        if (e.key === 'Enter') {
            sendMessage();
        }
    });
    
    uploadArea.addEventListener('click', function() {
        fileUpload.click();
    });
    
    fileUpload.addEventListener('change', function(e) {
        if (e.target.files.length > 0) {
            uploadResume(e.target.files[0]);
        }
    });
    
    // Drag and drop functionality
    uploadArea.addEventListener('dragover', function(e) {
        e.preventDefault();
        uploadArea.classList.add('active');
    });
    
    uploadArea.addEventListener('dragleave', function() {
        uploadArea.classList.remove('active');
    });
    
    uploadArea.addEventListener('drop', function(e) {
        e.preventDefault();
        uploadArea.classList.remove('active');
        
        if (e.dataTransfer.files.length > 0) {
            uploadResume(e.dataTransfer.files[0]);
        }
    });

    // Add missing functions
    function toggleUploadArea(show) {
        isUploadVisible = show;
        uploadArea.classList.toggle('d-none', !show);
    }

    function showTypingIndicator() {
        const typingDiv = document.createElement('div');
        typingDiv.id = 'typing-indicator';
        typingDiv.classList.add('typing-indicator');
        typingDiv.innerHTML = '<span></span><span></span><span></span>';
        chatMessages.appendChild(typingDiv);
        scrollToBottom();
    }

    function hideTypingIndicator() {
        const typingIndicator = document.getElementById('typing-indicator');
        if (typingIndicator) {
            typingIndicator.remove();
        }
    }

    function scrollToBottom() {
        chatMessages.scrollTop = chatMessages.scrollHeight;
    }

    function updateCompletionPercentage(percentage) {
        completionPercent = percentage;
        completionPercentage.textContent = `${percentage}%`;
        progressBar.style.width = `${percentage}%`;
        progressBar.setAttribute('aria-valuenow', percentage);
    }
    
    // Functions
    function sendInitialMessage() {
        showTypingIndicator();
        
        fetch('/api/chat', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({
                user_id: userId,
                message: 'start'
            })
        })
        .then(response => response.json())
        .then(data => {
            hideTypingIndicator();
            addBotMessage(data.response);
            toggleUploadArea(true);
            updateCompletionPercentage(data.completion_percentage || 0);
        })
        .catch(error => {
            hideTypingIndicator();
            console.error('Error:', error);
            addBotMessage('Sorry, there was an error connecting to the service. Please try again later.');
        });
    }
    
    function sendMessage() {
        if (isWaitingForResponse) return;
        
        const message = userInput.value.trim();
        if (message === '') return;
        
        addUserMessage(message);
        userInput.value = '';
        toggleUploadArea(false);
        showTypingIndicator();
        isWaitingForResponse = true;
        
        fetch('/api/chat', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({
                user_id: userId,
                message: message
            })
        })
        .then(response => response.json())
        .then(data => {
            hideTypingIndicator();
            isWaitingForResponse = false;
            addBotMessage(data.response);
            
            if (data.response.toLowerCase().includes('upload') || 
                data.response.toLowerCase().includes('resume')) {
                toggleUploadArea(true);
            }
            
            updateCompletionPercentage(data.completion_percentage || completionPercent);
        })
        .catch(error => {
            hideTypingIndicator();
            isWaitingForResponse = false;
            console.error('Error:', error);
            addBotMessage('Sorry, there was an error processing your message. Please try again.');
        });
    }
    
    function uploadResume(file) {
        const MAX_FILE_SIZE = 10 * 1024 * 1024; // 10MB limit
        
        if (file.size > MAX_FILE_SIZE) {
            addBotMessage('File size exceeds 10MB limit. Please upload a smaller file.');
            return;
        }
        
        if (!file.type.includes('pdf')) {
            addBotMessage('Please upload a PDF file.');
            return;
        }
        
        toggleUploadArea(false);
        showTypingIndicator();
        isWaitingForResponse = true;
        
        const formData = new FormData();
        formData.append('file', file);
        formData.append('user_id', userId);
        
        fetch('/api/upload-resume', {
            method: 'POST',
            body: formData
        })
        .then(response => response.json())
        .then(data => {
            setTimeout(() => {
                hideTypingIndicator();
                isWaitingForResponse = false;
                
                if (data.error) {
                    addBotMessage(`Error: ${data.error}`);
                    toggleUploadArea(true);
                } else {
                    if (data.name) {
                        userName = data.name;
                    }
                    
                    // Split the response if it contains contact info form request
                    if (data.response.toLowerCase().includes('your contact info is missing') && 
                        data.response.toLowerCase().includes('please provide your email and phone number below:')) {
                        
                        // Split at the form request
                        const parts = data.response.split('Please provide your email and phone number below:');
                        
                        // Show the main message first
                        addBotMessage(parts[0].trim(), false);
                        
                        // Then show the form message after a delay
                        setTimeout(() => {
                            addBotMessage('Please provide your email and phone number below:', true);
                        }, 1000);
                    } else {
                        // Normal message
                        addBotMessage(data.response);
                    }
                    
                    updateCompletionPercentage(data.completion_percentage || completionPercent);
                }
            }, 1500);
        })
        .catch(error => {
            setTimeout(() => {
                hideTypingIndicator();
                isWaitingForResponse = false;
                console.error('Error:', error);
                addBotMessage('Sorry, there was an error uploading your resume. Please try again.');
                toggleUploadArea(true);
            }, 1500);
        });
    }
    
    function addUserMessage(message) {
        const messageWrapper = document.createElement('div');
        messageWrapper.classList.add('message-wrapper', 'user');
        
        const userAvatar = document.createElement('div');
        userAvatar.classList.add('user-avatar');
        userAvatar.textContent = userName ? userName.charAt(0).toUpperCase() : 'U';
        
        const messageDiv = document.createElement('div');
        messageDiv.classList.add('message', 'user-message');
        
        const messageContent = document.createElement('div');
        messageContent.classList.add('message-content');
        messageContent.textContent = message;
        
        messageDiv.appendChild(messageContent);
        messageWrapper.appendChild(messageDiv);
        messageWrapper.appendChild(userAvatar);
        
        chatMessages.appendChild(messageWrapper);
        scrollToBottom();
    }
    
    function addBotMessage(message, isFormMessage = false) {
        showTypingIndicator();
        
        setTimeout(() => {
            hideTypingIndicator();
            
            const messageWrapper = document.createElement('div');
            messageWrapper.classList.add('message-wrapper');
            
            const botAvatar = document.createElement('div');
            botAvatar.classList.add('bot-avatar');
            const botImage = document.createElement('img');
            botImage.src = 'static/images/bot-avatar.jpg';
            botImage.alt = 'Bot Avatar';
            botAvatar.appendChild(botImage);
            
            const messageDiv = document.createElement('div');
            messageDiv.classList.add('message', 'bot-message');
            
            const messageContent = document.createElement('div');
            messageContent.classList.add('message-content');
            
            if (isFormMessage || (message.toLowerCase().includes('please provide your email and phone number below:'))) {
                messageContent.innerHTML = `
                    <p>${message}</p>
                    <div class="contact-form">
                        <div class="row g-3">
                            <div class="col-md-6">
                                <div class="form-floating mb-3">
                                    <input type="email" class="form-control" id="emailInput" placeholder="name@example.com" required>
                                    <label for="emailInput">Email address</label>
                                    <div class="invalid-feedback">Please enter a valid email address.</div>
                                </div>
                            </div>
                            <div class="col-md-6">
                                <div class="form-floating mb-3">
                                    <input type="tel" class="form-control" id="phoneInput" placeholder="1234567890" required>
                                    <label for="phoneInput">Phone number</label>
                                    <div class="invalid-feedback">Please enter a valid phone number.</div>
                                </div>
                            </div>
                            <div class="col-12">
                                <button class="btn btn-primary" onclick="submitContactInfo()">Submit</button>
                            </div>
                        </div>
                    </div>
                `;
            } else {
                messageContent.textContent = message;
            }
            
            messageDiv.appendChild(messageContent);
            messageWrapper.appendChild(botAvatar);
            messageWrapper.appendChild(messageDiv);
            
            chatMessages.appendChild(messageWrapper);
            scrollToBottom();
        }, 500);
    }

    // Add contact form submission function
    window.submitContactInfo = function() {
        const emailInput = document.getElementById('emailInput');
        const phoneInput = document.getElementById('phoneInput');
        
        const emailRegex = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
        const phoneRegex = /^\+?[\d\s-]{10,}$/;
        
        const isEmailValid = emailRegex.test(emailInput.value);
        const isPhoneValid = phoneRegex.test(phoneInput.value);
        
        emailInput.classList.toggle('is-invalid', !isEmailValid);
        phoneInput.classList.toggle('is-invalid', !isPhoneValid);
        
        if (isEmailValid && isPhoneValid) {
            // Show loading state
            const submitButton = document.querySelector('.contact-form button');
            const originalText = submitButton.textContent;
            submitButton.disabled = true;
            submitButton.innerHTML = '<span class="spinner-border spinner-border-sm" role="status" aria-hidden="true"></span> Submitting...';
            
            // Submit contact information to server
            fetch('/api/submit-contact', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify({
                    user_id: userId,
                    email: emailInput.value,
                    phone: phoneInput.value
                })
            })
            .then(response => response.json())
            .then(data => {
                // Reset button state
                submitButton.disabled = false;
                submitButton.textContent = originalText;
                
                // Add user message showing the submitted info
                addUserMessage(`Email: ${emailInput.value}, Phone: ${phoneInput.value}`);
                
                // Add bot response
                addBotMessage(data.response || 'Thank you for providing your contact information.');
                
                // Update completion percentage
                updateCompletionPercentage(data.completion_percentage || completionPercent);
            })
            .catch(error => {
                // Reset button state
                submitButton.disabled = false;
                submitButton.textContent = originalText;
                
                console.error('Error:', error);
                addBotMessage('Sorry, there was an error submitting your contact information. Please try again.');
            });
        }
    };
});