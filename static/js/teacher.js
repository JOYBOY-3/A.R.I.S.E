//=========================================================
// A.R.I.S.E. Teacher Dashboard - Enhanced SPA Version
// - Tab-based navigation with localStorage persistence
// - Analytics, History, and Reports tabs
// - Session detail modal with retroactive editing
//=========================================================

// Initialize dark mode BEFORE page loads
(function () {
  const theme = localStorage.getItem('theme') || 'light';
  document.documentElement.setAttribute('data-theme', theme);
})();

// Dark Mode Toggle
function toggleTheme() {
  const html = document.documentElement;
  const current = html.getAttribute('data-theme');
  const newTheme = current === 'dark' ? 'light' : 'dark';
  const icon = document.getElementById('theme-icon');
  html.setAttribute('data-theme', newTheme);
  localStorage.setItem('theme', newTheme);
  if (icon) icon.textContent = newTheme === 'dark' ? '☀️' : '🌙';
}

document.addEventListener('DOMContentLoaded', () => {
  // Set icon on load
  const theme = localStorage.getItem('theme') || 'light';
  const icon = document.getElementById('theme-icon');
  if (icon) icon.textContent = theme === 'dark' ? '☀️' : '🌙';

  // =============================================================
  // 1. GLOBAL STATE & REFERENCES
  // =============================================================
  const STORAGE_KEY = 'arise_teacher_session';

  let sessionState = {
    courseId: null,
    courseName: null,
    courseCode: null,
    sessionId: null,
    allStudents: [],
    liveUpdateInterval: null,
    endTime: null,
    countdownInterval: null,
    currentTab: 'home',
    currentHomeScreen: 'setup', // setup, type, live, post-session
    isLoggedIn: false,
  };

  // DOM References - Login View
  const loginView = document.getElementById('login-view');
  const dashboardContainer = document.getElementById('dashboard-container');
  const loginButton = document.getElementById('login-button');
  const courseCodeInput = document.getElementById('course-code-input');
  const pinInput = document.getElementById('pin-input');
  const loginMessage = document.getElementById('login-message');

  // DOM References - Dashboard Header
  const dashboardCourseName = document.getElementById('dashboard-course-name');
  const dashboardCourseCode = document.getElementById('dashboard-course-code');
  const logoutButton = document.getElementById('logout-button');

  // DOM References - Tabs
  const mainTabs = document.getElementById('main-tabs');
  const tabButtons = mainTabs.querySelectorAll('.tab-button');
  const tabContents = document.querySelectorAll('.tab-content');

  // DOM References - Home Tab Screens
  const homeScreens = document.querySelectorAll('.home-screen');
  const setupScreen = document.getElementById('setup-screen');
  const typeScreen = document.getElementById('type-screen');
  const liveScreen = document.getElementById('live-screen');
  const postSessionScreen = document.getElementById('post-session-screen');

  // DOM References - Session Setup
  const sessionDateInput = document.getElementById('session-date-input');
  const durationInput = document.getElementById('duration-input');
  const topicInput = document.getElementById('topic-input');
  const confirmSetupButton = document.getElementById('confirm-setup-button');
  const backToSetupButton = document.getElementById('back-to-setup-button');
  const startOfflineButton = document.getElementById('start-offline-button');
  const startOnlineButton = document.getElementById('start-online-button');

  // DOM References - Live Session
  const attendanceCountSpan = document.getElementById('attendance-count');
  const totalStudentsSpan = document.getElementById('total-students');
  const deviceStatusText = document.getElementById('device-status-text');
  const searchInput = document.getElementById('search-input');
  const unmarkedStudentsTbody = document.querySelector('#unmarked-students-table tbody');
  const extendSessionButton = document.getElementById('extend-session-button');
  const endSessionButton = document.getElementById('end-session-button');

  // DOM References - Post Session
  const postSessionTopic = document.getElementById('post-session-topic');
  const exportExcelButton = document.getElementById('export-excel-button');
  const newSessionButton = document.getElementById('new-session-button');
  const reportTable = document.getElementById('report-table');

  // DOM References - Analytics Tab
  const analyticsLoading = document.getElementById('analytics-loading');
  const analyticsContent = document.getElementById('analytics-content');
  const avgAttendanceEl = document.getElementById('avg-attendance');
  const totalSessionsEl = document.getElementById('total-sessions');
  const enrolledCountEl = document.getElementById('enrolled-count');
  const atRiskCountEl = document.getElementById('at-risk-count');
  const trendGraphImage = document.getElementById('trend-graph-image');
  const trendGraphPlaceholder = document.getElementById('trend-graph-placeholder');
  const atRiskTbody = document.getElementById('at-risk-tbody');
  const noAtRiskMessage = document.getElementById('no-at-risk-message');

  // DOM References - History Tab
  const historyLoading = document.getElementById('history-loading');
  const historyContent = document.getElementById('history-content');
  const historyList = document.getElementById('history-list');
  const noHistoryMessage = document.getElementById('no-history-message');

  // DOM References - Reports Tab
  const reportsLoading = document.getElementById('reports-loading');
  const reportsContent = document.getElementById('reports-content');
  const reportsExportButton = document.getElementById('reports-export-excel-button');
  const reportsMatrixTable = document.getElementById('reports-matrix-table');
  const noReportsMessage = document.getElementById('no-reports-message');

  // DOM References - Session Detail Modal
  const sessionDetailModal = document.getElementById('session-detail-modal');
  const closeSessionModalBtn = document.getElementById('close-session-modal');
  const modalSessionTitle = document.getElementById('modal-session-title');
  const modalSessionDate = document.getElementById('modal-session-date');
  const modalSessionTopic = document.getElementById('modal-session-topic');
  const modalSessionType = document.getElementById('modal-session-type');
  const modalPresentCount = document.getElementById('modal-present-count');
  const modalAbsentCount = document.getElementById('modal-absent-count');
  const modalPresentList = document.getElementById('modal-present-list');
  const modalAbsentList = document.getElementById('modal-absent-list');
  const modalTabBtns = document.querySelectorAll('.modal-tab-btn');

  // =============================================================
  // 2. LOCALSTORAGE PERSISTENCE (SPA Engine)
  // =============================================================
  function saveState() {
    const persistentState = {
      courseId: sessionState.courseId,
      courseName: sessionState.courseName,
      courseCode: sessionState.courseCode,
      sessionId: sessionState.sessionId,
      currentTab: sessionState.currentTab,
      currentHomeScreen: sessionState.currentHomeScreen,
      isLoggedIn: sessionState.isLoggedIn,
      endTime: sessionState.endTime ? sessionState.endTime.toISOString() : null,
    };
    localStorage.setItem(STORAGE_KEY, JSON.stringify(persistentState));
  }

  function loadState() {
    const stored = localStorage.getItem(STORAGE_KEY);
    if (stored) {
      try {
        const parsed = JSON.parse(stored);
        return parsed;
      } catch (e) {
        console.error('Failed to parse stored state:', e);
        return null;
      }
    }
    return null;
  }

  function clearState() {
    localStorage.removeItem(STORAGE_KEY);
    sessionState = {
      courseId: null,
      courseName: null,
      courseCode: null,
      sessionId: null,
      allStudents: [],
      liveUpdateInterval: null,
      endTime: null,
      countdownInterval: null,
      currentTab: 'home',
      currentHomeScreen: 'setup',
      isLoggedIn: false,
    };
  }

  // =============================================================
  // 3. VIEW MANAGEMENT
  // =============================================================
  function showLoginView() {
    loginView.classList.add('active');
    loginView.style.display = 'block';
    dashboardContainer.style.display = 'none';
  }

  function showDashboard() {
    loginView.classList.remove('active');
    loginView.style.display = 'none';
    dashboardContainer.style.display = 'block';

    // Update header
    dashboardCourseName.textContent = sessionState.courseName || 'Course Dashboard';
    dashboardCourseCode.textContent = sessionState.courseCode ? `Code: ${sessionState.courseCode}` : '';
  }

  function switchTab(tabName) {
    sessionState.currentTab = tabName;
    saveState();

    // Update tab buttons
    tabButtons.forEach(btn => {
      btn.classList.toggle('active', btn.dataset.tab === tabName);
    });

    // Update tab content
    tabContents.forEach(content => {
      content.classList.toggle('active', content.id === `${tabName}-tab`);
    });

    // Load tab data if needed
    if (tabName === 'analytics') {
      loadAnalyticsTab();
    } else if (tabName === 'history') {
      loadHistoryTab();
    } else if (tabName === 'reports') {
      loadReportsTab();
    }
  }

  function switchHomeScreen(screenName) {
    sessionState.currentHomeScreen = screenName;
    saveState();

    homeScreens.forEach(screen => {
      screen.classList.remove('active');
      screen.style.display = 'none';
    });

    const targetScreen = document.getElementById(`${screenName}-screen`);
    if (targetScreen) {
      targetScreen.classList.add('active');
      targetScreen.style.display = 'block';
    }
  }

  // 4. INITIALIZATION & SESSION RESTORE
  // =============================================================

  // Searchable dropdown elements
  const courseSearchInput = document.getElementById('course-search-input');
  const courseDropdownContainer = document.getElementById('course-dropdown-container');
  const courseDropdownOptions = document.getElementById('course-dropdown-options');
  let allCourses = []; // Store all courses for filtering

  async function loadCourseCodes() {
    try {
      const response = await fetch('/api/teacher/course-codes');
      const courses = await response.json();
      allCourses = courses; // Store for filtering
      renderDropdownOptions(courses);
    } catch (err) {
      courseDropdownOptions.innerHTML = '<div class="no-results-message">Failed to load courses</div>';
    }
  }

  function renderDropdownOptions(courses) {
    courseDropdownOptions.innerHTML = '';

    if (courses.length === 0) {
      courseDropdownOptions.innerHTML = '<div class="no-results-message">No matching courses found</div>';
      return;
    }

    courses.forEach(course => {
      const optionDiv = document.createElement('div');
      optionDiv.className = 'dropdown-option';
      optionDiv.dataset.code = course.code;
      optionDiv.dataset.name = course.name;
      optionDiv.innerHTML = `<span class="course-code">${course.code}</span><span class="course-name">(${course.name})</span>`;

      optionDiv.addEventListener('click', () => {
        selectCourse(course);
      });

      courseDropdownOptions.appendChild(optionDiv);
    });
  }

  function selectCourse(course) {
    courseCodeInput.value = course.code;
    courseSearchInput.value = `${course.code} (${course.name})`;
    courseDropdownContainer.classList.remove('open');
    validateLoginForm();
  }

  function filterCourses(searchTerm) {
    const term = searchTerm.toLowerCase().trim();
    if (!term) {
      renderDropdownOptions(allCourses);
      return;
    }

    const filtered = allCourses.filter(c =>
      c.code.toLowerCase().includes(term) ||
      c.name.toLowerCase().includes(term)
    );
    renderDropdownOptions(filtered);
  }

  // Dropdown event handlers
  courseSearchInput.addEventListener('click', () => {
    courseDropdownContainer.classList.add('open');
  });

  courseSearchInput.addEventListener('input', (e) => {
    courseDropdownContainer.classList.add('open');
    filterCourses(e.target.value);
    // Clear selection if user types
    if (courseCodeInput.value && !e.target.value.includes(courseCodeInput.value)) {
      courseCodeInput.value = '';
      validateLoginForm();
    }
  });

  courseSearchInput.addEventListener('focus', () => {
    courseDropdownContainer.classList.add('open');
  });

  // Close dropdown when clicking outside
  document.addEventListener('click', (e) => {
    if (!courseDropdownContainer.contains(e.target)) {
      courseDropdownContainer.classList.remove('open');
    }
  });

  // Keyboard navigation for dropdown
  courseSearchInput.addEventListener('keydown', (e) => {
    const options = courseDropdownOptions.querySelectorAll('.dropdown-option');
    let highlighted = courseDropdownOptions.querySelector('.dropdown-option.highlighted');

    if (e.key === 'ArrowDown') {
      e.preventDefault();
      courseDropdownContainer.classList.add('open');
      if (!highlighted) {
        options[0]?.classList.add('highlighted');
      } else {
        highlighted.classList.remove('highlighted');
        const next = highlighted.nextElementSibling;
        if (next && next.classList.contains('dropdown-option')) {
          next.classList.add('highlighted');
          next.scrollIntoView({ block: 'nearest' });
        } else {
          options[0]?.classList.add('highlighted');
        }
      }
    } else if (e.key === 'ArrowUp') {
      e.preventDefault();
      if (highlighted) {
        highlighted.classList.remove('highlighted');
        const prev = highlighted.previousElementSibling;
        if (prev && prev.classList.contains('dropdown-option')) {
          prev.classList.add('highlighted');
          prev.scrollIntoView({ block: 'nearest' });
        } else {
          options[options.length - 1]?.classList.add('highlighted');
        }
      }
    } else if (e.key === 'Enter') {
      e.preventDefault();
      if (highlighted) {
        selectCourse({ code: highlighted.dataset.code, name: highlighted.dataset.name });
      }
    } else if (e.key === 'Escape') {
      courseDropdownContainer.classList.remove('open');
    }
  });

  async function initializeApp() {
    await loadCourseCodes();

    const storedState = loadState();

    if (storedState && storedState.isLoggedIn && storedState.courseId) {
      // Validate the stored session with the server
      try {
        const response = await fetch(`/api/teacher/validate-session/${storedState.courseId}`);
        const data = await response.json();

        if (data.valid) {
          // Restore session state
          sessionState.courseId = storedState.courseId;
          sessionState.courseName = data.course.course_name;
          sessionState.courseCode = data.course.course_code;
          sessionState.isLoggedIn = true;
          sessionState.currentTab = storedState.currentTab || 'home';

          // Check for active session
          if (data.has_active_session) {
            sessionState.sessionId = data.active_session.id;
            sessionState.endTime = new Date(data.active_session.end_time.replace(' ', 'T'));
            sessionState.currentHomeScreen = 'live';

            // Use the students returned from validate-session
            if (data.students && data.students.length > 0) {
              sessionState.allStudents = data.students;
              totalStudentsSpan.textContent = sessionState.allStudents.length;
            }

            // Clear search input to prevent browser autofill issues
            searchInput.value = '';

            showDashboard();
            switchTab(sessionState.currentTab);
            switchHomeScreen('live');

            // Start live updates which will populate the unmarked list
            startLiveUpdates();
            startCountdownTimer();
            console.log('Restored active session from localStorage with', sessionState.allStudents.length, 'students');
          } else {
            sessionState.currentHomeScreen = storedState.currentHomeScreen || 'setup';
            sessionState.sessionId = null;

            showDashboard();
            switchTab(sessionState.currentTab);
            switchHomeScreen(sessionState.currentHomeScreen);
            console.log('Restored dashboard state (no active session)');
          }
          return;
        }
      } catch (error) {
        console.error('Session validation failed:', error);
      }
    }

    // Default: show login
    clearState();
    showLoginView();
    sessionDateInput.value = new Date().toISOString().split('T')[0];
  }

  // =============================================================
  // 5. LOGIN WORKFLOW
  // =============================================================
  function validateLoginForm() {
    loginButton.disabled = !courseCodeInput.value || !pinInput.value;
  }

  courseCodeInput.addEventListener('change', validateLoginForm);
  pinInput.addEventListener('input', validateLoginForm);

  loginButton.disabled = true;

  loginButton.addEventListener('click', async () => {
    const courseCode = courseCodeInput.value.trim();
    const pin = pinInput.value.trim();

    if (!courseCode || !pin) {
      loginMessage.textContent = 'Please enter both Course Code and PIN.';
      return;
    }

    loginMessage.textContent = 'Logging in...';
    loginButton.disabled = true;

    try {
      const response = await fetch('/api/teacher/login', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ course_code: courseCode, pin }),
      });

      const data = await response.json();

      if (response.ok) {
        loginMessage.textContent = '';
        sessionState.courseId = data.course_id;
        sessionState.courseName = data.course_name;
        sessionState.courseCode = courseCode;
        sessionState.isLoggedIn = true;
        sessionState.currentTab = 'home';
        sessionState.currentHomeScreen = 'setup';

        durationInput.value = data.default_duration;
        sessionDateInput.value = new Date().toISOString().split('T')[0];

        saveState();
        showDashboard();
        switchTab('home');
        switchHomeScreen('setup');
        validateSetupForm();
      } else {
        loginMessage.textContent = data.message || 'Login failed.';
      }
    } catch (error) {
      console.error('Login error:', error);
      loginMessage.textContent = 'An error occurred. Is the server running?';
    } finally {
      loginButton.disabled = false;
    }
  });

  // =============================================================
  // 6. LOGOUT
  // =============================================================
  logoutButton.addEventListener('click', async () => {
    const confirmed = await Modal.confirm(
      'Are you sure you want to logout? Any unsaved changes will be lost.',
      'Confirm Logout',
      'warning'
    );

    if (!confirmed) return;

    stopLiveUpdates();
    stopCountdownTimer();
    clearState();

    // Reset form fields
    loginMessage.textContent = '';
    courseCodeInput.value = '';
    courseSearchInput.value = '';
    pinInput.value = '';
    loginButton.disabled = true;

    showLoginView();
  });

  // =============================================================
  // 7. TAB NAVIGATION
  // =============================================================
  tabButtons.forEach(btn => {
    btn.addEventListener('click', () => {
      switchTab(btn.dataset.tab);
    });
  });

  // =============================================================
  // 8. HOME TAB - SESSION SETUP & START
  // =============================================================
  function validateSetupForm() {
    const isValid = sessionDateInput.value && durationInput.value && parseInt(durationInput.value) > 0;
    confirmSetupButton.disabled = !isValid;
  }

  sessionDateInput.addEventListener('input', validateSetupForm);
  durationInput.addEventListener('input', validateSetupForm);

  confirmSetupButton.addEventListener('click', () => {
    switchHomeScreen('type');
  });

  backToSetupButton.addEventListener('click', () => {
    switchHomeScreen('setup');
  });

  startOfflineButton.addEventListener('click', async () => {
    const confirmed = await Modal.confirm(
      `Are you sure you want to start an <strong>Offline Class</strong> session?<br><br>
       <span style="color: var(--text-secondary); font-size: 0.9em;">
       📅 Date: ${sessionDateInput.value}<br>
       ⏱️ Duration: ${durationInput.value} minutes<br>
       ${topicInput.value ? '📝 Topic: ' + topicInput.value : ''}
       </span>`,
      'Start Offline Session',
      'info'
    );

    if (confirmed) {
      startSession('offline');
    }
  });

  startOnlineButton.addEventListener('click', async () => {
    const confirmed = await Modal.confirm(
      `Are you sure you want to start an <strong>Online Class</strong> session?<br><br>
       <span style="color: var(--text-secondary); font-size: 0.9em;">
       📅 Date: ${sessionDateInput.value}<br>
       ⏱️ Duration: ${durationInput.value} minutes<br>
       ${topicInput.value ? '📝 Topic: ' + topicInput.value : ''}
       </span>`,
      'Start Online Session',
      'info'
    );

    if (confirmed) {
      await Modal.alert(
        'Online session functionality will be implemented in a future module.',
        'Coming Soon',
        'info'
      );
    }
  });

  async function startSession(sessionType) {
    const sessionDate = sessionDateInput.value;
    const now = new Date();
    const start_time = new Date(`${sessionDate}T${now.toTimeString().split(' ')[0]}`).toISOString();
    const duration_minutes = durationInput.value;
    const topic = topicInput ? topicInput.value.trim() : '';

    try {
      const response = await fetch('/api/teacher/start-session', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          course_id: sessionState.courseId,
          start_datetime: start_time,
          duration_minutes,
          session_type: sessionType,
          topic: topic,
        }),
      });

      const data = await response.json();

      if (response.ok) {
        sessionState.sessionId = data.session_id;
        sessionState.allStudents = data.students;
        const endTimeStr = data.end_time;
        sessionState.endTime = new Date(endTimeStr.replace(' ', 'T'));
        sessionState.currentHomeScreen = 'live';

        totalStudentsSpan.textContent = sessionState.allStudents.length;
        searchInput.value = '';
        renderUnmarkedStudents(sessionState.allStudents);

        saveState();
        switchHomeScreen('live');
        startLiveUpdates();
        startCountdownTimer();
      } else {
        await Modal.alert(`Error starting session: ${data.message}`, 'Error', 'error');
      }
    } catch (error) {
      console.error('Start session error:', error);
      await Modal.alert('A network error occurred while starting the session.', 'Network Error', 'error');
    }
  }

  // =============================================================
  // 9. LIVE DASHBOARD
  // =============================================================
  function startLiveUpdates() {
    if (sessionState.liveUpdateInterval) {
      clearInterval(sessionState.liveUpdateInterval);
    }
    updateLiveStatus();
    sessionState.liveUpdateInterval = setInterval(() => {
      updateLiveStatus();
    }, 5000);
  }

  function stopLiveUpdates() {
    if (sessionState.liveUpdateInterval) {
      clearInterval(sessionState.liveUpdateInterval);
      sessionState.liveUpdateInterval = null;
    }
  }

  function startCountdownTimer() {
    if (sessionState.countdownInterval) {
      clearInterval(sessionState.countdownInterval);
    }

    let countdownDisplay = document.getElementById('countdown-display');
    if (!countdownDisplay) {
      const livePanel = document.querySelector('.live-info-panel');
      const countdownCard = document.createElement('div');
      countdownCard.className = 'stat-card';
      countdownCard.innerHTML = `
        <h4>Time Remaining</h4>
        <p id="countdown-display" style="font-size: 2rem; font-weight: bold; color: var(--primary-color);">--:--</p>
      `;
      livePanel.insertBefore(countdownCard, livePanel.children[1]);
      countdownDisplay = document.getElementById('countdown-display');
    }

    updateCountdown();
    sessionState.countdownInterval = setInterval(updateCountdown, 1000);
  }

  function updateCountdown() {
    if (!sessionState.endTime) return;

    const now = new Date();
    const timeLeft = sessionState.endTime - now;
    const countdownEl = document.getElementById('countdown-display');

    if (timeLeft <= 0) {
      if (countdownEl) {
        countdownEl.textContent = 'Expired';
        countdownEl.style.color = 'var(--danger-color)';
      }
      clearInterval(sessionState.countdownInterval);
      console.log('Countdown reached 0:00 - triggering expire check');
      checkAndExpireSession();
      return;
    }

    const totalSeconds = Math.floor(timeLeft / 1000);
    const minutes = Math.floor(totalSeconds / 60);
    const seconds = totalSeconds % 60;
    const display = `${minutes}:${seconds.toString().padStart(2, '0')}`;

    if (countdownEl) {
      countdownEl.textContent = display;
      countdownEl.style.color = minutes < 5 ? 'var(--danger-color)' : 'var(--primary-color)';
    }
  }

  async function checkAndExpireSession() {
    if (!sessionState.sessionId) return;

    try {
      const response = await fetch(`/api/teacher/session/${sessionState.sessionId}/check-expire`, { method: 'POST' });
      const data = await response.json();

      if (data.expired) {
        console.log('Session confirmed expired by server');
        stopLiveUpdates();
        stopCountdownTimer();
        await Modal.alert('Session has automatically ended due to time expiration.', 'Session Expired', 'warning');
        loadPostSessionReport(sessionState.sessionId);
      } else if (data.status === 'active') {
        console.warn('Countdown expired but server says session still active. Seconds remaining:', data.seconds_remaining);
        setTimeout(checkAndExpireSession, 10000);
      }
    } catch (error) {
      console.error('Error checking session expiry:', error);
      setTimeout(checkAndExpireSession, 10000);
    }
  }

  function stopCountdownTimer() {
    if (sessionState.countdownInterval) {
      clearInterval(sessionState.countdownInterval);
      sessionState.countdownInterval = null;
    }
  }

  async function updateLiveStatus() {
    if (!sessionState.sessionId) return;

    try {
      // Get attendance status
      const statusResponse = await fetch(`/api/teacher/session/${sessionState.sessionId}/status`);
      const statusData = await statusResponse.json();

      if (statusResponse.ok) {
        if (statusData.session_active === false) {
          console.log('Session auto-expired detected');
          stopLiveUpdates();
          stopCountdownTimer();
          await Modal.alert('Session has automatically ended due to time expiration.', 'Session Expired', 'warning');
          loadPostSessionReport(sessionState.sessionId);
          return;
        }

        // Update allStudents if we don't have them yet
        if (sessionState.allStudents.length === 0 && statusData.all_students) {
          sessionState.allStudents = statusData.all_students;
          totalStudentsSpan.textContent = sessionState.allStudents.length;
        }

        const markedUnivRollNos = new Set(statusData.marked_students);
        const unmarkedStudents = sessionState.allStudents.filter(s => !markedUnivRollNos.has(s.university_roll_no));
        renderUnmarkedStudents(unmarkedStudents);
        attendanceCountSpan.textContent = markedUnivRollNos.size;
      }

      // Device status
      const deviceResponse = await fetch('/api/teacher/device-status');
      const deviceData = await deviceResponse.json();

      if (deviceResponse.ok) {
        if (deviceData.status === 'online') {
          const strength = deviceData.wifi_strength > -67 ? 'Strong' : deviceData.wifi_strength > -80 ? 'Okay' : 'Weak';
          deviceStatusText.innerHTML = `✅ Online (${strength})<br>🔋 ${deviceData.battery}% | 📝 Q: ${deviceData.queue_count} | 🔄 S: ${deviceData.sync_count}`;
        } else if (deviceData.status === 'offline') {
          if (deviceData.last_seen !== undefined) {
            deviceStatusText.innerHTML = `❌ Offline (${deviceData.last_seen}s ago)<br>🔋 Last: ${deviceData.battery || '?'}% | 📝 Q: ${deviceData.queue_count || 0}`;
          } else {
            deviceStatusText.innerHTML = `❌ Offline / No Data<br>Waiting for device...`;
          }
        } else {
          deviceStatusText.innerHTML = `⚠️ Status Unknown<br>${deviceData.message || 'Check connection'}`;
        }
      } else {
        deviceStatusText.innerHTML = `❌ Error<br>Cannot fetch status`;
      }
    } catch (error) {
      console.error('Error updating live status:', error);
      deviceStatusText.innerHTML = `❌ Error<br>Network issue`;
    }
  }

  function renderUnmarkedStudents(students) {
    unmarkedStudentsTbody.innerHTML = '';
    const searchTerm = searchInput.value.toLowerCase();

    students
      .filter(s => s.student_name.toLowerCase().includes(searchTerm) || s.class_roll_id.toString().includes(searchTerm))
      .forEach((student) => {
        const row = document.createElement('tr');
        row.innerHTML = `
          <td data-label="Class Roll">${student.class_roll_id}</td>
          <td data-label="Name">${student.student_name}</td>
          <td data-label="Univ. Roll No.">${student.university_roll_no}</td>
          <td data-label="Action"><button class="manual-mark-btn" data-univ-roll="${student.university_roll_no}">Mark Manually</button></td>
        `;
        unmarkedStudentsTbody.appendChild(row);
      });
  }

  searchInput.addEventListener('input', () => {
    updateLiveStatus();
  });

  unmarkedStudentsTbody.addEventListener('click', async (event) => {
    if (event.target.classList.contains('manual-mark-btn')) {
      const univ_roll_no = event.target.dataset.univRoll;
      const student = sessionState.allStudents.find(s => s.university_roll_no === univ_roll_no);
      const studentName = student ? student.student_name : 'this student';

      // Show custom reason selection modal
      const reason = await showReasonSelectionModal(studentName);

      if (reason && reason.trim() !== '') {
        try {
          const response = await fetch('/api/teacher/manual-override', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
              session_id: sessionState.sessionId,
              univ_roll_no,
              reason,
            }),
          });

          if (response.ok) {
            await Modal.alert('Attendance marked successfully!', 'Success', 'success');
            updateLiveStatus();
          } else {
            const errorData = await response.json();
            await Modal.alert(`Failed to mark attendance: ${errorData.message}`, 'Error', 'error');
          }
        } catch (error) {
          console.error('Manual override error:', error);
          await Modal.alert('A network error occurred.', 'Network Error', 'error');
        }
      }
    }
  });

  // Custom reason selection modal for manual attendance
  function showReasonSelectionModal(studentName) {
    return new Promise((resolve) => {
      const predefinedReasons = [
        { icon: '🤕', label: 'Finger Injury', value: 'Finger Injury - Unable to use biometric scanner' },
        { icon: '📱', label: 'Device Malfunction', value: 'Device Malfunction - Scanner not working properly' },
        { icon: '🏥', label: 'Medical Condition', value: 'Medical Condition - Skin condition affecting fingerprint' },
        { icon: '⏰', label: 'Late Arrival', value: 'Late Arrival - Verified by teacher' },
        { icon: '⚡', label: 'Technical Issue', value: 'Technical Issue - System connectivity problem' },
        { icon: '✏️', label: 'Other', value: 'OTHER' }
      ];

      // Create modal overlay
      const overlay = document.createElement('div');
      overlay.className = 'reason-modal-overlay';
      overlay.innerHTML = `
        <div class="reason-modal">
          <div class="reason-modal-header">
            <h3>📝 Manual Attendance</h3>
            <p>Marking attendance for <strong>${studentName}</strong></p>
          </div>
          <div class="reason-modal-body">
            <p class="reason-instruction">Select a reason for manual entry:</p>
            <div class="reason-options">
              ${predefinedReasons.map((r, i) => `
                <div class="reason-option" data-index="${i}" data-value="${r.value}">
                  <span class="reason-icon">${r.icon}</span>
                  <span class="reason-label">${r.label}</span>
                </div>
              `).join('')}
            </div>
            <div class="other-reason-container" style="display: none;">
              <label for="other-reason-input">Please specify the reason:</label>
              <textarea id="other-reason-input" placeholder="Enter custom reason..." rows="2"></textarea>
            </div>
          </div>
          <div class="reason-modal-footer">
            <button class="btn-cancel">Cancel</button>
            <button class="btn-confirm" disabled>Confirm</button>
          </div>
        </div>
      `;

      document.body.appendChild(overlay);

      let selectedReason = '';
      const reasonOptions = overlay.querySelectorAll('.reason-option');
      const otherContainer = overlay.querySelector('.other-reason-container');
      const otherInput = overlay.querySelector('#other-reason-input');
      const confirmBtn = overlay.querySelector('.btn-confirm');
      const cancelBtn = overlay.querySelector('.btn-cancel');

      // Handle reason selection
      reasonOptions.forEach(option => {
        option.addEventListener('click', () => {
          // Remove previous selection
          reasonOptions.forEach(o => o.classList.remove('selected'));
          option.classList.add('selected');

          const value = option.dataset.value;

          if (value === 'OTHER') {
            otherContainer.style.display = 'block';
            otherInput.focus();
            selectedReason = '';
            confirmBtn.disabled = true;
          } else {
            otherContainer.style.display = 'none';
            selectedReason = value;
            confirmBtn.disabled = false;
          }
        });
      });

      // Handle other input
      otherInput.addEventListener('input', () => {
        selectedReason = otherInput.value.trim() ? `Other: ${otherInput.value.trim()}` : '';
        confirmBtn.disabled = !selectedReason;
      });

      // Handle confirm
      confirmBtn.addEventListener('click', () => {
        overlay.remove();
        resolve(selectedReason);
      });

      // Handle cancel
      cancelBtn.addEventListener('click', () => {
        overlay.remove();
        resolve(null);
      });

      // Close on overlay click
      overlay.addEventListener('click', (e) => {
        if (e.target === overlay) {
          overlay.remove();
          resolve(null);
        }
      });

      // ESC to close
      const escHandler = (e) => {
        if (e.key === 'Escape') {
          overlay.remove();
          document.removeEventListener('keydown', escHandler);
          resolve(null);
        }
      };
      document.addEventListener('keydown', escHandler);
    });
  }

  // =============================================================
  // 10. SESSION CONTROLS - End & Extend
  // =============================================================
  endSessionButton.addEventListener('click', async () => {
    const confirmed = await Modal.confirm(
      'Are you sure you want to end this session? This action cannot be undone.',
      'Confirm End Session',
      'warning'
    );

    if (!confirmed) return;

    stopLiveUpdates();
    stopCountdownTimer();

    await fetch(`/api/teacher/session/${sessionState.sessionId}/end`, { method: 'POST' });

    loadPostSessionReport(sessionState.sessionId);
  });

  extendSessionButton.addEventListener('click', async () => {
    const countdownEl = document.getElementById('countdown-display');
    if (countdownEl && countdownEl.textContent === 'Expired') {
      await Modal.alert('Cannot extend - session has already expired. Please end the session and start a new one.', 'Session Expired', 'warning');
      return;
    }

    const confirmed = await Modal.confirm('Do you want to extend this session by 10 minutes?', 'Extend Session', 'info');
    if (!confirmed) return;

    try {
      const response = await fetch(`/api/teacher/session/${sessionState.sessionId}/extend`, { method: 'POST' });

      if (response.ok) {
        const data = await response.json();
        const newEndTimeStr = data.new_end_time;
        sessionState.endTime = new Date(newEndTimeStr.replace(' ', 'T'));
        saveState();
        console.log('Session extended. New end time:', sessionState.endTime);
        await Modal.alert('Session extended by 10 minutes successfully!', 'Success', 'success');
      } else {
        const error = await response.json();
        await Modal.alert(error.message || 'Failed to extend session.', 'Error', 'error');
      }
    } catch (error) {
      console.error('Extend session error:', error);
      await Modal.alert('Network error while extending session.', 'Network Error', 'error');
    }
  });

  // =============================================================
  // EMERGENCY MODE - Bulk Manual Attendance
  // =============================================================
  const emergencyModeButton = document.getElementById('emergency-mode-button');

  emergencyModeButton.addEventListener('click', async () => {
    const confirmed = await Modal.confirm(
      `<strong>⚠️ Emergency Mode</strong><br><br>
       This mode is for device failures only. It allows you to manually mark multiple students as Present or Absent.<br><br>
       <span style="color: var(--warning-color);">Use this only when the Smart Scanner is not working.</span>`,
      'Activate Emergency Mode',
      'warning'
    );

    if (confirmed) {
      showEmergencyModeModal();
    }
  });

  function showEmergencyModeModal() {
    // Get current attendance status
    const markedStudents = new Set();

    // Create modal
    const overlay = document.createElement('div');
    overlay.className = 'emergency-modal-overlay';
    overlay.innerHTML = `
      <div class="emergency-modal">
        <div class="emergency-modal-header">
          <h3>⚠️ Emergency Attendance Mode</h3>
          <p>Select students and mark them Present or Absent</p>
        </div>
        
        <div class="emergency-mode-toggle">
          <button class="mode-btn present-mode active" data-mode="present">
            ✅ Mark Present
          </button>
          <button class="mode-btn absent-mode" data-mode="absent">
            ❌ Mark Absent
          </button>
        </div>
        
        <div class="emergency-student-list">
          <div class="emergency-select-all">
            <label>
              <input type="checkbox" id="select-all-students" />
              Select All Unmarked
            </label>
            <span class="selection-count">0 selected</span>
          </div>
          <div class="student-grid" id="emergency-student-grid">
            <!-- Students will be populated here -->
          </div>
        </div>
        
        <div class="emergency-modal-footer">
          <button class="btn-close-emergency">Cancel</button>
          <div class="emergency-actions">
            <button class="btn-mark-selected" disabled>Apply to Selected (0)</button>
          </div>
        </div>
      </div>
    `;

    document.body.appendChild(overlay);

    let currentMode = 'present'; // 'present' or 'absent'
    let selectedStudents = new Set();

    const studentGrid = overlay.querySelector('#emergency-student-grid');
    const modeBtns = overlay.querySelectorAll('.mode-btn');
    const selectAllCheckbox = overlay.querySelector('#select-all-students');
    const selectionCount = overlay.querySelector('.selection-count');
    const markSelectedBtn = overlay.querySelector('.btn-mark-selected');
    const closeBtn = overlay.querySelector('.btn-close-emergency');

    // Fetch current status and populate grid
    fetchAndPopulateStudents();

    async function fetchAndPopulateStudents() {
      try {
        const statusResponse = await fetch(`/api/teacher/session/${sessionState.sessionId}/status`);
        const statusData = await statusResponse.json();

        const markedRollNos = new Set(statusData.marked_students || []);
        const absentRollNos = new Set(statusData.absent_students || []);
        let allStudents = sessionState.allStudents || [];

        // Sort by class roll ID for easy scrolling
        allStudents = [...allStudents].sort((a, b) => {
          const rollA = parseInt(a.class_roll_id) || 0;
          const rollB = parseInt(b.class_roll_id) || 0;
          return rollA - rollB;
        });

        studentGrid.innerHTML = '';

        allStudents.forEach(student => {
          const isPresent = markedRollNos.has(student.university_roll_no);
          const isAbsent = absentRollNos.has(student.university_roll_no);
          const isProcessed = isPresent || isAbsent;

          const div = document.createElement('div');
          div.className = `student-item ${isPresent ? 'marked-present' : ''} ${isAbsent ? 'marked-absent' : ''}`;
          div.dataset.univRoll = student.university_roll_no;
          div.dataset.marked = isProcessed ? 'true' : 'false';

          // Show ✅ for present, ❌ for absent, empty for unmarked
          let statusIcon = '';
          if (isPresent) statusIcon = '✅';
          else if (isAbsent) statusIcon = '❌';

          div.innerHTML = `
            <input type="checkbox" ${isProcessed ? 'disabled' : ''} />
            <div class="student-info">
              <span class="student-roll">${student.class_roll_id}</span>
              <span class="student-name">${student.student_name}</span>
              <span class="student-univ-roll">${student.university_roll_no}</span>
            </div>
            <span class="student-status">${statusIcon}</span>
          `;

          if (!isProcessed) {
            div.addEventListener('click', (e) => {
              if (e.target.tagName !== 'INPUT') {
                const checkbox = div.querySelector('input[type="checkbox"]');
                checkbox.checked = !checkbox.checked;
              }
              toggleStudentSelection(student.university_roll_no, div);
            });
          }

          studentGrid.appendChild(div);
        });
      } catch (error) {
        console.error('Error fetching students:', error);
        studentGrid.innerHTML = '<p style="text-align:center;color:var(--danger-color)">Failed to load students</p>';
      }
    }

    function toggleStudentSelection(univRollNo, element) {
      const checkbox = element.querySelector('input[type="checkbox"]');
      if (checkbox.checked) {
        selectedStudents.add(univRollNo);
        element.classList.add('selected');
      } else {
        selectedStudents.delete(univRollNo);
        element.classList.remove('selected');
      }
      updateSelectionCount();
    }

    function updateSelectionCount() {
      const count = selectedStudents.size;
      selectionCount.textContent = `${count} selected`;
      markSelectedBtn.textContent = `Apply ${currentMode === 'present' ? '✅ Present' : '❌ Absent'} to Selected (${count})`;
      markSelectedBtn.disabled = count === 0;

      // Update select all checkbox state
      const unmarkedItems = studentGrid.querySelectorAll('.student-item:not(.marked-present)');
      const allChecked = unmarkedItems.length > 0 && selectedStudents.size === unmarkedItems.length;
      selectAllCheckbox.checked = allChecked;
    }

    // Mode toggle
    modeBtns.forEach(btn => {
      btn.addEventListener('click', () => {
        modeBtns.forEach(b => b.classList.remove('active'));
        btn.classList.add('active');
        currentMode = btn.dataset.mode;
        updateSelectionCount();
      });
    });

    // Select all
    selectAllCheckbox.addEventListener('change', () => {
      const unmarkedItems = studentGrid.querySelectorAll('.student-item:not(.marked-present)');
      unmarkedItems.forEach(item => {
        const checkbox = item.querySelector('input[type="checkbox"]');
        checkbox.checked = selectAllCheckbox.checked;
        const univRollNo = item.dataset.univRoll;
        if (selectAllCheckbox.checked) {
          selectedStudents.add(univRollNo);
          item.classList.add('selected');
        } else {
          selectedStudents.delete(univRollNo);
          item.classList.remove('selected');
        }
      });
      updateSelectionCount();
    });

    // Apply marking
    markSelectedBtn.addEventListener('click', async () => {
      if (selectedStudents.size === 0) return;

      let confirmMessage = '';
      let studentsToMark = [];

      if (currentMode === 'present') {
        // Present mode: only mark selected students as present
        confirmMessage = `Mark <strong>${selectedStudents.size} selected students</strong> as <strong>PRESENT</strong>?`;
        studentsToMark = Array.from(selectedStudents).map(roll => ({ roll, status: 'present' }));
      } else {
        // Absent mode: mark selected as absent, ALL unselected as present
        const unmarkedItems = studentGrid.querySelectorAll('.student-item:not(.marked-present):not(.marked-absent)');
        const allUnmarkedRolls = Array.from(unmarkedItems).map(item => item.dataset.univRoll);
        const unselectedCount = allUnmarkedRolls.length - selectedStudents.size;

        confirmMessage = `
          <strong>Absent Mode Summary:</strong><br><br>
          ❌ <strong>${selectedStudents.size}</strong> selected students → ABSENT<br>
          ✅ <strong>${unselectedCount}</strong> unselected students → PRESENT<br><br>
          <span style="font-size: 0.9em; color: var(--text-secondary);">
          This will mark ALL remaining students.
          </span>`;

        // Build list: selected = absent, unselected = present
        studentsToMark = allUnmarkedRolls.map(roll => ({
          roll,
          status: selectedStudents.has(roll) ? 'absent' : 'present'
        }));
      }

      const confirmed = await Modal.confirm(
        confirmMessage,
        'Confirm Bulk Marking',
        currentMode === 'present' ? 'success' : 'warning'
      );

      if (!confirmed) return;

      markSelectedBtn.disabled = true;
      markSelectedBtn.textContent = 'Applying...';

      try {
        const response = await fetch('/api/teacher/emergency-bulk-mark', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            session_id: sessionState.sessionId,
            students: studentsToMark,
            reason: 'Emergency Mode - Device Failure'
          })
        });

        if (response.ok) {
          const data = await response.json();
          const totalMarked = (data.present_count || 0) + (data.absent_count || 0);
          let successMessage = '';

          if (currentMode === 'present') {
            successMessage = `Successfully marked ${data.present_count || totalMarked} students as PRESENT!`;
          } else {
            successMessage = `✅ ${data.present_count || 0} marked PRESENT<br>❌ ${data.absent_count || 0} marked ABSENT`;
          }

          await Modal.alert(successMessage, 'Success', 'success');

          // Refresh the student list
          selectedStudents.clear();
          await fetchAndPopulateStudents();
          updateSelectionCount();

          // Update live dashboard
          updateLiveStatus();
        } else {
          const error = await response.json();
          await Modal.alert(error.message || 'Failed to mark students', 'Error', 'error');
        }
      } catch (error) {
        console.error('Bulk mark error:', error);
        await Modal.alert('Network error while marking students', 'Error', 'error');
      }

      markSelectedBtn.disabled = false;
      updateSelectionCount();
    });

    // Close modal
    closeBtn.addEventListener('click', () => {
      overlay.remove();
    });

    overlay.addEventListener('click', (e) => {
      if (e.target === overlay) {
        overlay.remove();
      }
    });

    // ESC to close
    const escHandler = (e) => {
      if (e.key === 'Escape') {
        overlay.remove();
        document.removeEventListener('keydown', escHandler);
      }
    };
    document.addEventListener('keydown', escHandler);
  }

  // =============================================================
  // 11. POST-SESSION REPORT (Within Home Tab)
  // =============================================================
  async function loadPostSessionReport(sessionId) {
    try {
      const response = await fetch(`/api/teacher/report/${sessionId}`);
      const data = await response.json();

      if (response.ok) {
        renderReportTable(data, reportTable);
        postSessionTopic.textContent = topicInput.value || 'Session completed';
        sessionState.currentHomeScreen = 'post-session';
        saveState();
        switchHomeScreen('post-session');
      } else {
        await Modal.alert('Failed to load report.', 'Error', 'error');
      }
    } catch (error) {
      console.error('Report loading error:', error);
    }
  }

  function renderReportTable(data, tableEl) {
    tableEl.innerHTML = '';

    const thead = document.createElement('thead');
    let headerHtml = '<tr><th>Class Roll</th><th>Name</th><th>Univ. Roll No.</th>';

    const sortedSessions = data.sessions.sort((a, b) => new Date(a.start_time) - new Date(b.start_time));

    sortedSessions.forEach((session) => {
      const dt = new Date(session.start_time);
      const day = dt.getDate().toString().padStart(2, '0');
      const month = dt.toLocaleString('en-GB', { month: 'short' });
      const hour = dt.getHours().toString().padStart(2, '0');
      const minute = dt.getMinutes().toString().padStart(2, '0');
      const dateTime = `${day} ${month} - ${hour}:${minute}`;
      headerHtml += `<th>${dateTime}</th>`;
    });

    headerHtml += '</tr>';
    thead.innerHTML = headerHtml;
    tableEl.appendChild(thead);

    const tbody = document.createElement('tbody');
    const presentSet = new Set(data.present_set.map(p => `${p[0]}_${p[1]}`));

    data.students.forEach((student) => {
      let rowHtml = `<tr><td data-label="Class Roll">${student.class_roll_id}</td><td data-label="Name">${student.student_name}</td><td data-label="Univ. Roll No.">${student.university_roll_no}</td>`;

      sortedSessions.forEach((session) => {
        const sessionLabel = new Date(session.start_time).toLocaleDateString('en-GB', { day: '2-digit', month: 'short' });
        if (presentSet.has(`${session.id}_${student.id}`)) {
          rowHtml += `<td data-label="${sessionLabel}"><span title="Present">✅</span></td>`;
        } else {
          rowHtml += `<td data-label="${sessionLabel}"><span title="Absent">❌</span></td>`;
        }
      });

      rowHtml += '</tr>';
      tbody.innerHTML += rowHtml;
    });

    tableEl.appendChild(tbody);

    // Auto-scroll to latest session
    const tableContainer = tableEl.closest('.responsive-table-container');
    if (tableContainer) {
      requestAnimationFrame(() => {
        tableContainer.scrollTo({ left: tableContainer.scrollWidth, behavior: 'smooth' });
      });
    }
  }

  exportExcelButton.addEventListener('click', () => {
    window.open(`/api/teacher/report/export/${sessionState.sessionId}`);
  });

  newSessionButton.addEventListener('click', () => {
    sessionState.sessionId = null;
    sessionState.allStudents = [];
    sessionState.endTime = null;
    sessionState.currentHomeScreen = 'setup';
    topicInput.value = '';
    sessionDateInput.value = new Date().toISOString().split('T')[0];
    saveState();
    switchHomeScreen('setup');
    validateSetupForm();
  });

  // =============================================================
  // 12. ANALYTICS TAB
  // =============================================================
  async function loadAnalyticsTab() {
    if (!sessionState.courseId) return;

    analyticsLoading.style.display = 'flex';
    analyticsContent.style.display = 'none';

    try {
      const response = await fetch(`/api/teacher/analytics/${sessionState.courseId}`);
      const data = await response.json();

      if (response.ok) {
        // Update stat cards
        avgAttendanceEl.textContent = `${data.avg_attendance_percent}%`;
        totalSessionsEl.textContent = data.total_sessions;
        enrolledCountEl.textContent = data.enrolled_count || '--';
        atRiskCountEl.textContent = data.at_risk_students ? data.at_risk_students.length : 0;

        // Trend graph
        if (data.trend_graph_base64) {
          // Backend returns full data URI, use directly
          trendGraphImage.src = data.trend_graph_base64;
          trendGraphImage.style.display = 'block';
          trendGraphPlaceholder.style.display = 'none';
        } else {
          trendGraphImage.style.display = 'none';
          trendGraphPlaceholder.style.display = 'block';
        }

        // At-risk students table
        atRiskTbody.innerHTML = '';
        if (data.at_risk_students && data.at_risk_students.length > 0) {
          noAtRiskMessage.style.display = 'none';
          document.getElementById('at-risk-table').style.display = 'table';

          data.at_risk_students.forEach(student => {
            const statusClass = student.attendance_percent < 50 ? 'status-critical' : 'status-warning';
            const row = document.createElement('tr');
            row.innerHTML = `
              <td>${student.class_roll_id}</td>
              <td>${student.student_name}</td>
              <td>${student.attendance_percent}%</td>
              <td><span class="${statusClass}">${student.status}</span></td>
              <td>${student.sessions_needed}</td>
            `;
            atRiskTbody.appendChild(row);
          });
        } else {
          document.getElementById('at-risk-table').style.display = 'none';
          noAtRiskMessage.style.display = 'block';
        }

        analyticsLoading.style.display = 'none';
        analyticsContent.style.display = 'block';
      } else {
        await Modal.alert('Failed to load analytics.', 'Error', 'error');
        analyticsLoading.innerHTML = '<p>Failed to load analytics.</p>';
      }
    } catch (error) {
      console.error('Analytics loading error:', error);
      analyticsLoading.innerHTML = '<p>Error loading analytics.</p>';
    }
  }

  // =============================================================
  // 13. HISTORY TAB
  // =============================================================
  async function loadHistoryTab() {
    if (!sessionState.courseId) return;

    historyLoading.style.display = 'flex';
    historyContent.style.display = 'none';

    try {
      const response = await fetch(`/api/teacher/history/${sessionState.courseId}`);
      const data = await response.json();

      if (response.ok) {
        historyList.innerHTML = '';

        if (data.sessions && data.sessions.length > 0) {
          noHistoryMessage.style.display = 'none';

          data.sessions.forEach(session => {
            const badgeClass = session.attendance_percent >= 75 ? 'good' : session.attendance_percent >= 50 ? 'warning' : 'critical';
            const activeClass = session.is_active ? 'active-session' : '';

            const card = document.createElement('div');
            card.className = `session-history-card ${activeClass}`;
            card.dataset.sessionId = session.id;
            card.innerHTML = `
              <div class="session-card-info">
                <h4>${session.date} at ${session.time}</h4>
                <p class="session-topic">${session.topic}</p>
                <p>${session.session_type === 'offline' ? '📍 Offline' : '🌐 Online'}${session.is_active ? ' • 🟢 Active' : ''}</p>
              </div>
              <div class="session-card-stats">
                <span class="attendance-badge ${badgeClass}">${session.present_count}/${session.total_students} (${session.attendance_percent}%)</span>
              </div>
            `;
            card.addEventListener('click', () => showSessionDetailModal(session.id));
            historyList.appendChild(card);
          });
        } else {
          noHistoryMessage.style.display = 'block';
        }

        historyLoading.style.display = 'none';
        historyContent.style.display = 'block';
      } else {
        await Modal.alert('Failed to load session history.', 'Error', 'error');
        historyLoading.innerHTML = '<p>Failed to load history.</p>';
      }
    } catch (error) {
      console.error('History loading error:', error);
      historyLoading.innerHTML = '<p>Error loading history.</p>';
    }
  }

  // =============================================================
  // 14. SESSION DETAIL MODAL (For History Tab)
  // =============================================================
  let currentModalSessionId = null;

  async function showSessionDetailModal(sessionId) {
    currentModalSessionId = sessionId;
    sessionDetailModal.style.display = 'flex';

    try {
      const response = await fetch(`/api/teacher/session-detail/${sessionId}`);
      const data = await response.json();

      if (response.ok) {
        modalSessionTitle.textContent = 'Session Details';
        modalSessionDate.textContent = data.start_time;
        modalSessionTopic.textContent = data.topic;
        modalSessionType.textContent = data.session_type === 'offline' ? 'Offline Class' : 'Online Class';
        modalPresentCount.textContent = data.present_count;
        modalAbsentCount.textContent = data.absent_count;

        // Render present students
        modalPresentList.innerHTML = '';
        data.present_students.forEach(student => {
          const item = document.createElement('div');
          item.className = 'modal-student-item';
          item.innerHTML = `
            <div class="modal-student-info">
              <div class="student-name">${student.student_name}</div>
              <div class="student-roll">Roll: ${student.class_roll_id} | Univ: ${student.university_roll_no}</div>
              ${student.method ? `<div class="attendance-method">via ${student.method}</div>` : ''}
            </div>
          `;
          modalPresentList.appendChild(item);
        });

        // Render absent students with mark present button
        modalAbsentList.innerHTML = '';
        data.absent_students.forEach(student => {
          const item = document.createElement('div');
          item.className = 'modal-student-item';
          item.innerHTML = `
            <div class="modal-student-info">
              <div class="student-name">${student.student_name}</div>
              <div class="student-roll">Roll: ${student.class_roll_id} | Univ: ${student.university_roll_no}</div>
            </div>
            <button class="mark-present-btn" data-student-id="${student.student_id}" data-student-name="${student.student_name}">
              Mark Present
            </button>
          `;
          modalAbsentList.appendChild(item);
        });

        // Reset to present tab
        switchModalTab('present');
      } else {
        await Modal.alert('Failed to load session details.', 'Error', 'error');
        sessionDetailModal.style.display = 'none';
      }
    } catch (error) {
      console.error('Session detail error:', error);
      sessionDetailModal.style.display = 'none';
    }
  }

  function switchModalTab(tabName) {
    modalTabBtns.forEach(btn => {
      btn.classList.toggle('active', btn.dataset.modalTab === tabName);
    });
    modalPresentList.classList.toggle('active', tabName === 'present');
    modalPresentList.style.display = tabName === 'present' ? 'block' : 'none';
    modalAbsentList.classList.toggle('active', tabName === 'absent');
    modalAbsentList.style.display = tabName === 'absent' ? 'block' : 'none';
  }

  modalTabBtns.forEach(btn => {
    btn.addEventListener('click', () => switchModalTab(btn.dataset.modalTab));
  });

  closeSessionModalBtn.addEventListener('click', () => {
    sessionDetailModal.style.display = 'none';
  });

  // Close modal on overlay click
  sessionDetailModal.addEventListener('click', (e) => {
    if (e.target === sessionDetailModal) {
      sessionDetailModal.style.display = 'none';
    }
  });

  // Retroactive attendance marking
  modalAbsentList.addEventListener('click', async (event) => {
    if (event.target.classList.contains('mark-present-btn')) {
      const studentId = event.target.dataset.studentId;
      const studentName = event.target.dataset.studentName;

      const reason = await Modal.prompt(
        `Mark <strong>${studentName}</strong> as present retroactively.<br><br>Please provide a reason (required for audit):`,
        'Retroactive Attendance',
        '',
        'info'
      );

      if (reason && reason.trim() !== '') {
        try {
          const response = await fetch('/api/teacher/update-attendance', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
              session_id: currentModalSessionId,
              student_id: parseInt(studentId),
              action: 'mark_present',
              manual_reason: reason.trim(),
            }),
          });

          const data = await response.json();

          if (response.ok) {
            await Modal.alert('Attendance updated successfully!', 'Success', 'success');
            // Refresh the modal
            showSessionDetailModal(currentModalSessionId);
            // Also refresh history tab in background
            loadHistoryTab();
          } else {
            await Modal.alert(data.error || 'Failed to update attendance.', 'Error', 'error');
          }
        } catch (error) {
          console.error('Update attendance error:', error);
          await Modal.alert('Network error while updating attendance.', 'Network Error', 'error');
        }
      }
    }
  });

  // =============================================================
  // 15. REPORTS TAB
  // =============================================================
  async function loadReportsTab() {
    if (!sessionState.courseId) return;

    reportsLoading.style.display = 'flex';
    reportsContent.style.display = 'none';

    try {
      // Get history to find a session for the report
      const historyResponse = await fetch(`/api/teacher/history/${sessionState.courseId}`);
      const historyData = await historyResponse.json();

      if (!historyData.sessions || historyData.sessions.length === 0) {
        reportsLoading.style.display = 'none';
        reportsContent.style.display = 'block';
        noReportsMessage.style.display = 'block';
        reportsMatrixTable.style.display = 'none';
        return;
      }

      // Use the most recent session for the full matrix
      const latestSessionId = historyData.sessions[0].id;

      const response = await fetch(`/api/teacher/report/${latestSessionId}`);
      const data = await response.json();

      if (response.ok && data.sessions && data.sessions.length > 0) {
        noReportsMessage.style.display = 'none';
        reportsMatrixTable.style.display = 'table';
        renderReportTable(data, reportsMatrixTable);

        // Store latest session for export
        sessionState.latestSessionId = latestSessionId;
      } else {
        noReportsMessage.style.display = 'block';
        reportsMatrixTable.style.display = 'none';
      }

      reportsLoading.style.display = 'none';
      reportsContent.style.display = 'block';
    } catch (error) {
      console.error('Reports loading error:', error);
      reportsLoading.innerHTML = '<p>Error loading reports.</p>';
    }
  }

  reportsExportButton.addEventListener('click', () => {
    if (sessionState.latestSessionId) {
      window.open(`/api/teacher/report/export/${sessionState.latestSessionId}`);
    } else if (sessionState.sessionId) {
      window.open(`/api/teacher/report/export/${sessionState.sessionId}`);
    } else {
      Modal.alert('No session available for export.', 'Export Error', 'warning');
    }
  });

  // =============================================================
  // INITIALIZATION
  // =============================================================
  initializeApp();
});
