// =============================================================
// A.R.I.S.E. Online Attendance — Student JS
// OTP-based attendance marking with live session info
// =============================================================

(function () {
    'use strict';

    // DOM Elements
    const loadingState = document.getElementById('loading-state');
    const errorState = document.getElementById('error-state');
    const formState = document.getElementById('attendance-form');
    const successState = document.getElementById('success-state');

    const courseName = document.getElementById('course-name');
    const courseCode = document.getElementById('course-code');
    const teacherName = document.getElementById('teacher-name');
    const sessionTopic = document.getElementById('session-topic');
    const timerFill = document.getElementById('timer-fill');
    const timerText = document.getElementById('timer-text');
    const markedCount = document.getElementById('marked-count');
    const totalCount = document.getElementById('total-count');

    const rollInput = document.getElementById('roll-input');
    const otpInput = document.getElementById('otp-input');
    const submitBtn = document.getElementById('submit-btn');
    const submitText = document.getElementById('submit-text');
    const submitSpinner = document.getElementById('submit-spinner');
    const statusMsg = document.getElementById('status-message');
    const successName = document.getElementById('success-name');

    let totalSeconds = 0;
    let remainingSeconds = 0;
    let timerInterval = null;
    let refreshInterval = null;

    // =============================================================
    // Screen Management
    // =============================================================
    function showScreen(screen) {
        [loadingState, errorState, formState, successState].forEach(s => s.classList.remove('active'));
        screen.classList.add('active');
    }

    function showError(title, message) {
        document.getElementById('error-title').textContent = title;
        document.getElementById('error-message').textContent = message;
        showScreen(errorState);
    }

    // =============================================================
    // Load Session Info
    // =============================================================
    async function loadSessionInfo() {
        try {
            const res = await fetch(`/api/online/session/${TOKEN}/info`);
            const data = await res.json();

            if (!res.ok) {
                if (data.expired) {
                    showError('Session Ended', 'This class session has already ended.');
                } else {
                    showError('Session Not Found', data.error || 'This session link is invalid.');
                }
                return;
            }

            // Populate session info
            courseName.textContent = data.course_name;
            courseCode.textContent = data.course_code;
            teacherName.textContent = `👨‍🏫 ${data.teacher_name}`;
            sessionTopic.textContent = data.topic ? `📝 ${data.topic}` : '';
            markedCount.textContent = data.marked_count;
            totalCount.textContent = data.total_students;

            // Start timer
            remainingSeconds = data.time_remaining_seconds;
            totalSeconds = remainingSeconds;
            startTimer();

            // Show form
            showScreen(formState);

            // Refresh stats every 10s
            refreshInterval = setInterval(refreshStats, 10000);

        } catch (err) {
            console.error('Failed to load session:', err);
            showError('Connection Error', 'Could not connect to the server. Please check your internet and try again.');
        }
    }

    // =============================================================
    // Timer
    // =============================================================
    function startTimer() {
        updateTimerDisplay();
        timerInterval = setInterval(() => {
            remainingSeconds--;
            if (remainingSeconds <= 0) {
                clearInterval(timerInterval);
                showError('Session Expired', 'The attendance window has closed.');
                return;
            }
            updateTimerDisplay();
        }, 1000);
    }

    function updateTimerDisplay() {
        const mins = Math.floor(remainingSeconds / 60);
        const secs = remainingSeconds % 60;
        timerText.textContent = `⏱ ${mins}:${secs.toString().padStart(2, '0')} remaining`;

        const pct = totalSeconds > 0 ? (remainingSeconds / totalSeconds) * 100 : 0;
        timerFill.style.width = `${pct}%`;
    }

    // =============================================================
    // Refresh Stats
    // =============================================================
    async function refreshStats() {
        try {
            const res = await fetch(`/api/online/session/${TOKEN}/info`);
            if (res.ok) {
                const data = await res.json();
                markedCount.textContent = data.marked_count;
                totalCount.textContent = data.total_students;
            }
        } catch (_) { /* silent */ }
    }

    // =============================================================
    // Form Validation
    // =============================================================
    function validateForm() {
        const hasRoll = rollInput.value.trim().length > 0;
        const hasOtp = otpInput.value.trim().length === 6;
        submitBtn.disabled = !(hasRoll && hasOtp);
    }

    rollInput.addEventListener('input', validateForm);
    otpInput.addEventListener('input', () => {
        // Auto-submit when 6 digits entered
        validateForm();
        if (otpInput.value.trim().length === 6 && rollInput.value.trim().length > 0) {
            submitAttendance();
        }
    });

    // =============================================================
    // Submit Attendance
    // =============================================================
    let isSubmitting = false;

    async function submitAttendance() {
        if (isSubmitting) return;
        isSubmitting = true;

        submitBtn.disabled = true;
        submitText.style.display = 'none';
        submitSpinner.style.display = 'inline-block';
        statusMsg.textContent = '';
        statusMsg.className = 'status-msg';

        try {
            const res = await fetch('/api/online/mark-attendance', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    token: TOKEN,
                    university_roll_no: rollInput.value.trim(),
                    otp: otpInput.value.trim()
                })
            });

            const data = await res.json();

            if (data.status === 'success') {
                successName.textContent = data.student_name;
                showScreen(successState);
                clearInterval(timerInterval);
                clearInterval(refreshInterval);
                return;
            }

            if (data.status === 'duplicate') {
                successName.textContent = data.student_name;
                showScreen(successState);
                clearInterval(timerInterval);
                clearInterval(refreshInterval);
                return;
            }

            // Error
            statusMsg.textContent = data.message || 'Something went wrong.';
            statusMsg.className = 'status-msg error';
            otpInput.value = '';
            otpInput.focus();

        } catch (err) {
            statusMsg.textContent = 'Network error. Please try again.';
            statusMsg.className = 'status-msg error';
        } finally {
            isSubmitting = false;
            submitText.style.display = 'inline';
            submitSpinner.style.display = 'none';
            validateForm();
        }
    }

    submitBtn.addEventListener('click', submitAttendance);

    // Prevent form submission on Enter in roll input  
    rollInput.addEventListener('keydown', (e) => {
        if (e.key === 'Enter') {
            e.preventDefault();
            otpInput.focus();
        }
    });

    otpInput.addEventListener('keydown', (e) => {
        if (e.key === 'Enter') {
            e.preventDefault();
            if (!submitBtn.disabled) submitAttendance();
        }
    });

    // =============================================================
    // Initialize
    // =============================================================
    loadSessionInfo();
})();
