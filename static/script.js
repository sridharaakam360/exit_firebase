/**
 * Pharmacy Exam Prep - Main script file
 * Contains all the frontend functionality for the application
 * Improved version with CSRF token handling, session management, and Socket.IO
 */

// Initialize on document load
document.addEventListener('DOMContentLoaded', function() {
    try {
        setupSocketConnection();
    } catch (error) {
        console.error('Error in setupSocketConnection:', error);
    }
    enhanceUI();
    setupQuizTimer();
    setupFormAnimations();
    addTooltips();
    enhanceResultsPage();
    setupDropdowns();
    setupFlashMessages();
    setupCSRFProtection();
    setupExportButtons();
    addTableExport();
    makeTablesResponsive();

    const quizForm = document.getElementById('quizForm');
    if (quizForm) {
        quizForm.addEventListener('submit', function(e) {
            // Don't prevent default - let the form submit naturally
        });
    }

    if (window.location.pathname.includes('/take-test')) {
        window.history.pushState(null, '', window.location.href);
        window.addEventListener('popstate', function(event) {
            window.history.pushState(null, '', window.location.href);
        });
    }
});

/**
 * Set up Socket.IO connection for real-time updates
 */
function setupSocketConnection() {
    if (!window.io) {
        console.warn('Socket.IO library not loaded, skipping connection');
        return;
    }

    // Connect on admin pages (check path or specific elements)
    if (window.location.pathname.startsWith('/admin/') || 
        document.getElementById('updates-list') || 
        document.getElementById('active-users')) {
        try {
            console.log('Connecting to /admin namespace');
            const socket = io('/admin', {
                reconnection: true,
                reconnectionAttempts: 5,
                reconnectionDelay: 1000,
                timeout: 10000
            });

            socket.on('connect', () => {
                console.log('Connected to /admin namespace');
                addUpdate('Connected to real-time updates');
            });

            socket.on('update', (data) => {
                console.log('Update received:', data);
                addUpdate(data.message || 'Update received');
                if (data.action === 'add' || data.action === 'edit' || 
                    data.action === 'delete' || data.action === 'bulk_import') {
                    location.reload();
                }
            });

            socket.on('active_users', (data) => {
                console.log('Active admins:', data.count);
                const activeUsers = document.getElementById('active-users');
                if (activeUsers) {
                    activeUsers.textContent = `Active Users: ${data.count}`;
                }
            });

            socket.on('disconnect', () => {
                console.warn('Socket disconnected');
                addUpdate('Disconnected from real-time updates');
            });

            socket.on('connect_error', (error) => {
                console.error('Socket connection error:', error);
                addUpdate('Error connecting to updates');
            });
        } catch (error) {
            console.error('Error setting up socket connection:', error);
        }
    } else {
        console.log('Not on admin page, skipping socket connection');
    }
}

/**
 * Add CSRF protection to all forms
 * Improved to handle token refreshing, skip GET forms, and prevent multiple executions
 */
function setupCSRFProtection() {
    if (window.csrfProtectionInitialized) {
        console.log('CSRF protection already initialized, skipping');
        return;
    }
    window.csrfProtectionInitialized = true;

    const csrfToken = document.querySelector('meta[name="csrf-token"]')?.content;
    
    if (csrfToken) {
        console.log('CSRF token found:', csrfToken.substring(0, 10) + '...');
        
        // Log all forms for debugging
        document.querySelectorAll('form').forEach(form => {
            console.log(`Processing form: id=${form.id || 'unnamed'}, class=${form.className}, method=${form.method}, action=${form.action}`);
        });
        
        document.querySelectorAll('form').forEach(form => {
            if (form.dataset.skipCsrf === 'true' || form.method.toLowerCase() === 'get') {
                console.log(`Skipping CSRF token for form: ${form.id || 'unnamed'}, class=${form.className}, method=${form.method}, skipCsrf=${form.dataset.skipCsrf}`);
                return;
            }

            let existingToken = form.querySelector('input[name="csrf_token"]');
            if (existingToken) {
                console.log(`Form already has CSRF token: ${existingToken.value.substring(0, 10)}..., form: ${form.id || 'unnamed'}, class=${form.className}`);
                existingToken.value = csrfToken;
            } else {
                const csrfInput = document.createElement('input');
                csrfInput.type = 'hidden';
                csrfInput.name = 'csrf_token';
                csrfInput.value = csrfToken;
                form.appendChild(csrfInput);
                console.log(`Added CSRF token to form: ${form.id || 'unnamed'}, class=${form.className}`);
            }
        });
        
        const originalXhrOpen = XMLHttpRequest.prototype.open;
        XMLHttpRequest.prototype.open = function() {
            originalXhrOpen.apply(this, arguments);
            this.setRequestHeader('X-CSRF-Token', csrfToken);
        };
        
        const originalFetch = window.fetch;
        window.fetch = function(url, options = {}) {
            options = options || {};
            options.headers = options.headers || {};
            options.headers['X-CSRF-Token'] = csrfToken;
            return originalFetch(url, options);
        };
    } else {
        console.warn('CSRF token not found in meta tag. CSRF protection disabled.');
    }
}

/**
 * Add an update to the updates list
 */
function addUpdate(message) {
    const list = document.getElementById('updates-list');
    if (!list) return;
    
    const li = document.createElement('li');
    li.textContent = `${new Date().toLocaleTimeString()} - ${message}`;
    li.classList.add(
        'animate-slide-up', 
        'bg-gradient-to-r', 
        'from-blue-50', 
        'to-gray-50', 
        'dark:from-indigo-900', 
        'dark:to-gray-800', 
        'rounded-md', 
        'p-2', 
        'shadow-sm'
    );
    
    list.prepend(li);
    setTimeout(() => li.classList.add('opacity-100'), 10);
    
    if (list.children.length > 10) {
        list.removeChild(list.lastChild);
    }
}

/**
 * Set up the quiz timer
 */
function setupQuizTimer() {
    const timerElement = document.getElementById('timer');
    if (!timerElement) return;
    
    let startTime = new Date();
    timerElement.classList.remove('hidden');
    
    const interval = setInterval(() => {
        let now = new Date();
        let diff = Math.floor((now - startTime) / 1000);
        let minutes = Math.floor(diff / 60).toString().padStart(2, '0');
        let seconds = (diff % 60).toString().padStart(2, '0');
        
        timerElement.textContent = `Time: ${minutes}:${seconds}`;
        timerElement.dataset.time = diff;
        timerElement.classList.add('pulse');
        setTimeout(() => timerElement.classList.remove('pulse'), 200);
    }, 1000);
    
    const quizForm = document.querySelector('.quiz-form');
    if (quizForm) {
        quizForm.addEventListener('submit', () => {
            clearInterval(interval);
            const hiddenInput = document.createElement('input');
            hiddenInput.type = 'hidden';
            hiddenInput.name = 'time_taken';
            hiddenInput.value = timerElement.dataset.time || 0;
            quizForm.appendChild(hiddenInput);
        });
    }
}

/**
 * Add animations to forms
 */
function setupFormAnimations() {
    const quizTypeSelect = document.getElementById('quiz_type');
    const subjectGroup = document.getElementById('subject_group');
    
    if (quizTypeSelect && subjectGroup) {
        quizTypeSelect.addEventListener('change', (e) => {
            subjectGroup.style.display = e.target.value === 'subject_wise' ? 'block' : 'none';
        });
    }

    document.querySelectorAll('form').forEach(form => {
        form.addEventListener('submit', (e) => {
            const csrfToken = document.querySelector('meta[name="csrf-token"]')?.content;
            if (csrfToken) {
                let existingToken = form.querySelector('input[name="csrf_token"]');
                if (existingToken) {
                    existingToken.value = csrfToken;
                } else {
                    const csrfInput = document.createElement('input');
                    csrfInput.type = 'hidden';
                    csrfInput.name = 'csrf_token';
                    csrfInput.value = csrfToken;
                    form.appendChild(csrfInput);
                }
            }
        });
    });

    const quizForm = document.getElementById('quizForm');
    if (quizForm) {
        quizForm.addEventListener('submit', async (e) => {
            e.preventDefault();
            
            const quizType = document.getElementById('quiz_type').value;
            const examId = document.getElementById('exam_id').value;
            const subjectId = document.getElementById('subject_id').value;

            if (!quizType || !examId) {
                alert('Please select both Quiz Type and Exam');
                return;
            }

            if (quizType === 'subject_wise' && !subjectId) {
                alert('Please select a Subject for Subject-wise Practice');
                return;
            }

            const submitButton = quizForm.querySelector('button[type="submit"]');
            if (submitButton) {
                submitButton.disabled = true;
                submitButton.innerHTML = '<span class="spinner"></span> Generating Quiz...';
            }

            try {
                const formData = new FormData(quizForm);
                const response = await fetch(quizForm.action, {
                    method: 'POST',
                    body: formData,
                    headers: {
                        'X-Requested-With': 'XMLHttpRequest'
                    }
                });

                if (!response.ok) {
                    throw new Error('Network response was not ok');
                }

                const html = await response.text();
                const temp = document.createElement('div');
                temp.innerHTML = html;
                
                const questionsContainer = temp.querySelector('#questions-container');
                if (questionsContainer) {
                    quizForm.parentElement.innerHTML = questionsContainer.outerHTML;
                    setupQuizTimer();
                    questionsContainer.scrollIntoView({ behavior: 'smooth' });
                } else {
                    window.location.reload();
                }
            } catch (error) {
                console.error('Error generating quiz:', error);
                alert('An error occurred while generating the quiz. Please try again.');
                if (submitButton) {
                    submitButton.disabled = false;
                    submitButton.innerHTML = 'Generate Quiz';
                }
            }
        });
    }
}

/**
 * Show a flash message programmatically
 */
function showFlashMessage(message, category = 'info') {
    const flashContainer = document.querySelector('.flash-messages');
    if (!flashContainer) return;
    
    const flash = document.createElement('div');
    flash.classList.add('flash', category, 'animate-slide-down');
    flash.innerHTML = `
        ${message}
        <button class="close-flash" onclick="this.parentElement.style.display='none';">&times;</button>
    `;
    
    flashContainer.appendChild(flash);
    
    setTimeout(() => {
        flash.style.opacity = '0';
        setTimeout(() => flash.remove(), 500);
    }, 5000);
}

/**
 * Add tooltips to elements with data-tooltip attribute
 */
function addTooltips() {
    document.querySelectorAll('[data-tooltip]').forEach(el => {
        el.addEventListener('mouseenter', () => {
            const tooltip = document.createElement('div');
            tooltip.textContent = el.dataset.tooltip;
            tooltip.classList.add(
                'tooltip', 
                'absolute', 
                'bg-gray-800', 
                'text-white', 
                'p-2', 
                'rounded-md', 
                'text-sm', 
                'shadow-lg', 
                'dark:bg-gray-900', 
                'z-50'
            );
            
            document.body.appendChild(tooltip);
            
            const rect = el.getBoundingClientRect();
            tooltip.style.top = `${rect.top - tooltip.offsetHeight - 10 + window.scrollY}px`;
            tooltip.style.left = `${rect.left + rect.width / 2}px`;
            tooltip.style.transform = 'translateX(-50%)';
            
            tooltip.style.opacity = '0';
            setTimeout(() => tooltip.style.opacity = '1', 10);
        });
        
        el.addEventListener('mouseleave', () => {
            const tooltip = document.querySelector('.tooltip');
            if (tooltip) {
                tooltip.style.opacity = '0';
                setTimeout(() => tooltip.remove(), 200);
            }
        });
    });
}

/**
 * Enhance results page
 */
function enhanceResultsPage() {
    document.querySelectorAll('.question').forEach(question => {
        question.addEventListener('click', (e) => {
            if (e.target.tagName === 'INPUT' || e.target.tagName === 'SELECT' || 
                e.target.tagName === 'BUTTON' || e.target.tagName === 'A' ||
                e.target.closest('form')) return;
                
            const details = question.querySelector('.question-details');
            if (details) {
                details.classList.toggle('hidden');
                question.classList.toggle('expanded');
                
                const expandIcon = question.querySelector('.expand-icon');
                if (expandIcon) {
                    expandIcon.style.transform = details.classList.contains('hidden') ? '' : 'rotate(180deg)';
                }
                
                if (!details.classList.contains('hidden')) {
                    setTimeout(() => {
                        if (!isElementInViewport(details)) {
                            details.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
                        }
                    }, 100);
                }
            }
        });
    });
    
    document.querySelectorAll('.review-form select').forEach(select => {
        select.addEventListener('change', (e) => {
            const rating = e.target.value;
            const preview = select.parentElement.querySelector('.rating-preview') || document.createElement('span');
            
            preview.classList.add(
                'rating-preview', 
                'text-sm', 
                'ml-2', 
                'inline-block',
                'transition-all',
                'duration-300'
            );
            
            if (rating) {
                const starCount = parseInt(rating);
                let stars = '';
                for (let i = 0; i < 5; i++) {
                    stars += i < starCount 
                        ? '<span class="text-yellow-500">★</span>' 
                        : '<span class="text-gray-400">☆</span>';
                }
                preview.innerHTML = stars;
            } else {
                preview.textContent = '';
            }
            
            if (!select.parentElement.querySelector('.rating-preview')) {
                select.parentElement.appendChild(preview);
            }
        });
    });
    
    const confettiContainer = document.querySelector('.confetti');
    if (confettiContainer) {
        for (let i = 0; i < 50; i++) {
            const confetti = document.createElement('div');
            const colors = ['bg-indigo-500', 'bg-purple-500', 'bg-pink-500', 'bg-blue-500', 'bg-green-500', 'bg-yellow-500'];
            const randomColor = colors[Math.floor(Math.random() * colors.length)];
            
            const size = Math.random() * 10 + 5;
            
            confetti.classList.add(
                'absolute', 
                'rounded-full', 
                'animate-confetti',
                randomColor
            );
            
            confetti.style.width = `${size}px`;
            confetti.style.height = `${size}px`;
            confetti.style.left = `${Math.random() * 100}%`;
            confetti.style.top = '0';
            confetti.style.animationDelay = `${Math.random() * 2}s`;
            confetti.style.animationDuration = `${Math.random() * 3 + 2}s`;
            
            confettiContainer.appendChild(confetti);
        }
    }
}

/**
 * Set up dropdown menus with improved event handling
 */
function setupDropdowns() {
    document.querySelectorAll('.dropdown').forEach(dropdown => {
        const button = dropdown.querySelector('button');
        const menu = dropdown.querySelector('.dropdown-menu');
        
        if (!button || !menu) return;
        
        const newButton = button.cloneNode(true);
        button.parentNode.replaceChild(newButton, button);
        
        newButton.addEventListener('click', (e) => {
            e.stopPropagation();
            menu.classList.toggle('hidden');
        });
        
        const closeDropdown = (event) => {
            if (!dropdown.contains(event.target)) {
                menu.classList.add('hidden');
            }
        };
        
        document.removeEventListener('click', closeDropdown);
        document.addEventListener('click', closeDropdown);
        
        menu.addEventListener('click', (e) => {
            e.stopPropagation();
        });
    });
}

/**
 * Set up flash messages auto-dismiss
 */
function setupFlashMessages() {
    document.querySelectorAll('.flash').forEach(flash => {
        setTimeout(() => {
            flash.style.opacity = '0';
            setTimeout(() => flash.remove(), 500);
        }, 5000);
        
        const closeBtn = flash.querySelector('.close-flash');
        if (closeBtn) {
            closeBtn.addEventListener('click', () => {
                flash.style.opacity = '0';
                setTimeout(() => flash.remove(), 500);
            });
        }
    });
}

/**
 * General UI enhancements
 */
function enhanceUI() {
    const currentLocation = window.location.pathname;
    document.querySelectorAll('nav a').forEach(link => {
        if (link.getAttribute('href') === currentLocation) {
            link.classList.add('bg-blue-500', 'dark:bg-blue-600', 'rounded-lg');
        }
    });
    
    const header = document.querySelector('nav .container');
    if (header) {
        const darkModeToggle = document.createElement('button');
        darkModeToggle.classList.add(
            'flex', 'items-center', 'justify-center', 
            'w-8', 'h-8', 'rounded-full', 
            'bg-gray-700', 'dark:bg-gray-200', 
            'text-gray-200', 'dark:text-gray-700',
            'transition-colors', 'duration-200'
        );
        
        darkModeToggle.innerHTML = document.documentElement.classList.contains('dark') 
            ? '<svg xmlns="http://www.w3.org/2000/svg" class="h-5 w-5" viewBox="0 0 20 20" fill="currentColor"><path fill-rule="evenodd" d="M10 2a1 1 0 011 1v1a1 1 0 11-2 0V3a1 1 0 011-1zm4 8a4 4 0 11-8 0 4 4 0 018 0zm-.464 4.95l.707.707a1 1 0 001.414-1.414l-.707-.707a1 1 0 00-1.414 1.414zm2.12-10.607a1 1 0 010 1.414l-.706.707a1 1 0 11-1.414-1.414l.707-.707a1 1 0 011.414 0zM17 11a1 1 0 100-2h-1a1 1 0 100 2h1zm-7 4a1 1 0 011 1v1a1 1 0 11-2 0v-1a1 1 0 011-1zM5.05 6.464A1 1 0 106.465 5.05l-.708-.707a1 1 0 00-1.414 1.414l.707.707zm1.414 8.486l-.707.707a1 1 0 01-1.414-1.414l.707-.707a1 1 0 011.414 1.414zM4 11a1 1 0 100-2H3a1 1 0 000 2h1z" clip-rule="evenodd" /></svg>'
            : '<svg xmlns="http://www.w3.org/2000/svg" class="h-5 w-5" viewBox="0 0 20 20" fill="currentColor"><path d="M17.293 13.293A8 8 0 016.707 2.707a8.001 8.001 0 1010.586 10.586z" /></svg>';
        
        darkModeToggle.addEventListener('click', toggleDarkMode);
        
        header.appendChild(darkModeToggle);
    }
}

/**
 * Toggle dark mode
 */
function toggleDarkMode() {
    const isDarkMode = document.documentElement.classList.toggle('dark');
    localStorage.setItem('darkMode', isDarkMode);
    
    const toggle = document.querySelector('nav button');
    if (toggle) {
        toggle.innerHTML = isDarkMode
            ? '<svg xmlns="http://www.w3.org/2000/svg" class="h-5 w-5" viewBox="0 0 20 20" fill="currentColor"><path fill-rule="evenodd" d="M10 2a1 1 0 011 1v1a1 1 0 11-2 0V3a1 1 0 011-1zm4 8a4 4 0 11-8 0 4 4 0 018 0zm-.464 4.95l.707.707a1 1 0 001.414-1.414l-.707-.707a1 1 0 00-1.414 1.414zm2.12-10.607a1 1 0 010 1.414l-.706.707a1 1 0 11-1.414-1.414l.707-.707a1 1 0 011.414 0zM17 11a1 1 0 100-2h-1a1 1 0 100 2h1zm-7 4a1 1 0 011 1v1a1 1 0 11-2 0v-1a1 1 0 011-1zM5.05 6.464A1 1 0 106.465 5.05l-.708-.707a1 1 0 00-1.414 1.414l.707.707zm1.414 8.486l-.707.707a1 1 0 01-1.414-1.414l.707-.707a1 1 0 011.414 1.414zM4 11a1 1 0 100-2H3a1 1 0 000 2h1z" clip-rule="evenodd" /></svg>'
            : '<svg xmlns="http://www.w3.org/2000/svg" class="h-5 w-5" viewBox="0 0 20 20" fill="currentColor"><path d="M17.293 13.293A8 8 0 016.707 2.707a8.001 8.001 0 1010.586 10.586z" /></svg>';
    }
}

/**
 * Check if element is in viewport
 */
function isElementInViewport(el) {
    const rect = el.getBoundingClientRect();
    return (
        rect.top >= 0 &&
        rect.left >= 0 &&
        rect.bottom <= (window.innerHeight || document.documentElement.clientHeight) &&
        rect.right <= (window.innerWidth || document.documentElement.clientWidth)
    );
}

/**
 * Set up export buttons
 */
function setupExportButtons() {
    document.querySelectorAll('.export-button').forEach(button => {
        button.addEventListener('click', function(e) {
            e.preventDefault();
            const exportMenu = this.nextElementSibling;
            exportMenu.classList.toggle('hidden');
            
            document.addEventListener('click', function closeMenu(event) {
                if (!exportMenu.contains(event.target) && !button.contains(event.target)) {
                    exportMenu.classList.add('hidden');
                    document.removeEventListener('click', closeMenu);
                }
            });
        });
    });
}

/**
 * Add export functionality to all tables
 */
function addTableExport() {
    document.querySelectorAll('.data-table').forEach(table => {
        const tableId = table.id || 'data-table';
        const container = table.parentElement;
        
        const exportContainer = document.createElement('div');
        exportContainer.className = 'export-container relative mb-4 mt-2 flex justify-end';
        exportContainer.innerHTML = `
            <button class="export-button btn-secondary flex items-center px-3 py-2 text-sm">
                <svg xmlns="http://www.w3.org/2000/svg" class="h-5 w-5 mr-1" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                    <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M4 16v1a3 3 0 003 3h10a3 3 0 003-3v-1m-4-4l-4 4m0 0l-4-4m4 4V4" />
                </svg>
                Export
            </button>
            <div class="export-menu hidden absolute right-0 mt-10 py-2 w-48 bg-white dark:bg-gray-700 rounded-md shadow-xl z-10">
                <a href="#" class="export-csv block px-4 py-2 text-sm text-gray-700 dark:text-gray-200 hover:bg-gray-100 dark:hover:bg-gray-600">
                    Export as CSV
                </a>
                <a href="#" class="export-pdf block px-4 py-2 text-sm text-gray-700 dark:text-gray-200 hover:bg-gray-100 dark:hover:bg-gray-600">
                    Export as PDF
                </a>
            </div>
        `;
        
        if (container.firstChild) {
            container.insertBefore(exportContainer, container.firstChild);
        } else {
            container.appendChild(exportContainer);
        }
        
        exportContainer.querySelector('.export-csv').addEventListener('click', function(e) {
            e.preventDefault();
            exportTableToCSV(table, tableId + '.csv');
        });
        
        exportContainer.querySelector('.export-pdf').addEventListener('click', function(e) {
            e.preventDefault();
            exportTableToPDF(table, tableId + '.pdf');
        });
    });
    
    setupExportButtons();
}

/**
 * Export table to CSV
 */
function exportTableToCSV(table, filename) {
    const rows = table.querySelectorAll('tr');
    let csv = [];
    
    for (let i = 0; i < rows.length; i++) {
        const row = [], cols = rows[i].querySelectorAll('td, th');
        
        for (let j = 0; j < cols.length; j++) {
            let text = cols[j].innerText.replace(/,/g, ' ');
            text = text.replace(/\s+/g, ' ').trim();
            row.push('"' + text + '"');
        }
        
        csv.push(row.join(','));
    }
    
    downloadFile(csv.join('\n'), filename, 'text/csv');
}

/**
 * Export table to PDF
 */
function exportTableToPDF(table, filename) {
    alert('Please use the browser print dialog to save as PDF');
    
    const printWindow = window.open('', '_blank');
    const rows = table.querySelectorAll('tr');
    let tableHTML = '<table border="1" cellpadding="8" cellspacing="0" style="border-collapse: collapse; width: 100%;">';
    
    for (let i = 0; i < rows.length; i++) {
        const cols = rows[i].querySelectorAll('td, th');
        tableHTML += '<tr>';
        for (let j = 0; j < cols.length; j++) {
            const isHeader = cols[j].tagName === 'TH';
            const style = isHeader ? 'background-color: #f3f4f6; font-weight: bold;' : '';
            tableHTML += `<${isHeader ? 'th' : 'td'} style="${style}">${cols[j].innerText}</${isHeader ? 'th' : 'td'}>`;
        }
        tableHTML += '</tr>';
    }
    
    tableHTML += '</table>';
    
    printWindow.document.write(`
        <!DOCTYPE html>
        <html>
        <head>
            <title>${filename}</title>
            <style>
                body { font-family: Arial, sans-serif; margin: 20px; }
                h1 { color: #333; margin-bottom: 20px; }
                table { border-collapse: collapse; width: 100%; }
                th, td { padding: 8px; text-align: left; border: 1px solid #ddd; }
                th { background-color: #f3f4f6; }
                @media print {
                    .no-print { display: none; }
                    body { margin: 0; }
                }
            </style>
        </head>
        <body>
            <div class="no-print" style="margin-bottom: 20px;">
                <h1>${filename.replace('.pdf', '')}</h1>
                <button onclick="window.print();" style="padding: 8px 16px; background: #4f46e5; color: white; border: none; border-radius: 4px; cursor: pointer;">Print/Save as PDF</button>
            </div>
            ${tableHTML}
        </body>
        </html>
    `);
    
    printWindow.document.close();
}

/**
 * Helper function to download file
 */
function downloadFile(content, filename, contentType) {
    const a = document.createElement('a');
    const file = new Blob([content], { type: contentType });
    
    a.href = URL.createObjectURL(file);
    a.download = filename;
    a.click();
    
    URL.revokeObjectURL(a.href);
}

/**
 * Make tables responsive on mobile
 */
function makeTablesResponsive() {
    const tables = document.querySelectorAll('table:not(.responsive)');
    tables.forEach(table => {
        table.classList.add('responsive');
        
        if (!table.parentElement.classList.contains('overflow-x-auto')) {
            const wrapper = document.createElement('div');
            wrapper.className = 'overflow-x-auto';
            table.parentNode.insertBefore(wrapper, table);
            wrapper.appendChild(table);
        }
    });
}

/**
 * Session check and refresh functionality
 */
function checkSession() {
    setInterval(() => {
        fetch('/ping', {
            method: 'GET',
            credentials: 'same-origin',
            headers: {
                'Accept': 'application/json',
                'X-Requested-With': 'XMLHttpRequest'
            }
        })
        .then(response => response.json())
        .then(data => {
            if (!data.authenticated) {
                console.warn('Session expired, redirecting to login');
                window.location.href = '/auth/choose_login';
            }
        })
        .catch(error => {
            console.error('Session check failed:', error);
        });
    }, 300000);
}

// Initialize session checking
checkSession();

/**
 * Globally accessible export functions
 */
window.exportTools = {
    exportTableToCSV: function(tableId, filename) {
        const table = document.getElementById(tableId);
        if (table) exportTableToCSV(table, filename);
    },
    
    exportToPDF: function(elementId) {
        const element = document.getElementById(elementId);
        if (element) exportTableToPDF(element, elementId + '.pdf');
    }
};