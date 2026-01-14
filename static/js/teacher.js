//=========================================================
// A.R.I.S.E. Teacher Dashboard - FIXED VERSION with Modal System
// - Replaced all alert/confirm/prompt with custom modals
// - Improved error handling and UX
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

  // --- 1. GLOBAL STATE & REFERENCES ---
  const views = {
    login: document.getElementById('login-view'),
    setup: document.getElementById('setup-view'),
    type: document.getElementById('type-view'),
    liveOffline: document.getElementById('live-offline-view'),
    report: document.getElementById('report-view'),
  };

  let sessionState = {
    courseId: null,
    sessionId: null,
    allStudents: [],
    liveUpdateInterval: null,
    endTime: null,
    countdownInterval: null,
  };

  // Get references to all interactive elements
  const loginButton = document.getElementById('login-button');
  const courseCodeInput = document.getElementById('course-code-input');
  const pinInput = document.getElementById('pin-input');
  const loginMessage = document.getElementById('login-message');
  const setupCourseName = document.getElementById('setup-course-name');
  const sessionDateInput = document.getElementById('session-date-input');
  const durationInput = document.getElementById('duration-input');
  const confirmSetupButton = document.getElementById('confirm-setup-button');
  const startOfflineButton = document.getElementById('start-offline-button');
  const startOnlineButton = document.getElementById('start-online-button');
  const liveCourseName = document.getElementById('live-course-name');
  const attendanceCountSpan = document.getElementById('attendance-count');
  const totalStudentsSpan = document.getElementById('total-students');
  const deviceStatusText = document.getElementById('device-status-text');
  const searchInput = document.getElementById('search-input');
  const unmarkedStudentsTbody = document.querySelector(
    '#unmarked-students-table tbody'
  );
  const extendSessionButton = document.getElementById('extend-session-button');
  const endSessionButton = document.getElementById('end-session-button');
  const reportCourseName = document.getElementById('report-course-name');
  const exportExcelButton = document.getElementById('export-excel-button');
  const newSessionButton = document.getElementById('new-session-button');
  const reportTable = document.getElementById('report-table');

  // Populate Course_Code dropdown
  async function loadCourseCodes() {
    try {
      const response = await fetch('/api/teacher/course-codes');
      const courseCodes = await response.json();
      courseCodeInput.innerHTML =
        '<option value="">-- Select Course Code --</option>';
      courseCodes.forEach((code) => {
        const option = document.createElement('option');
        option.value = code;
        option.textContent = code;
        courseCodeInput.appendChild(option);
      });
    } catch (err) {
      courseCodeInput.innerHTML = '<option value="">(Failed to load)</option>';
    }
  }

  loadCourseCodes();

  courseCodeInput.addEventListener('change', () => {
    loginButton.disabled = !courseCodeInput.value || !pinInput.value;
  });

  pinInput.addEventListener('input', () => {
    loginButton.disabled = !courseCodeInput.value || !pinInput.value;
  });

  loginButton.disabled = true;

  // --- 2. VIEW MANAGEMENT ---
  function showView(viewName) {
    Object.values(views).forEach((view) => {
      if (view) view.style.display = 'none';
    });
    if (views[viewName]) {
      views[viewName].style.display = 'block';
    }
  }

  // --- 3. LOGIN WORKFLOW ---
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
        setupCourseName.textContent = data.course_name;
        durationInput.value = data.default_duration;
        sessionDateInput.value = new Date().toISOString().split('T')[0];
        validateSetupForm();
        showView('setup');
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

  // --- 4. SESSION SETUP & START WORKFLOW ---
  function validateSetupForm() {
    const isValid =
      sessionDateInput.value &&
      durationInput.value &&
      parseInt(durationInput.value) > 0;
    confirmSetupButton.disabled = !isValid;
  }

  sessionDateInput.addEventListener('input', validateSetupForm);
  durationInput.addEventListener('input', validateSetupForm);

  confirmSetupButton.addEventListener('click', () => {
    showView('type');
  });

  startOfflineButton.addEventListener('click', () => {
    startSession('offline');
  });

  // FIXED: Use Modal instead of alert
  startOnlineButton.addEventListener('click', async () => {
    await Modal.alert(
      'Online session functionality will be implemented in a future module.',
      'Coming Soon',
      'info'
    );
  });

  async function startSession(sessionType) {
    const sessionDate = sessionDateInput.value;
    const now = new Date();
    const start_time = new Date(
      `${sessionDate}T${now.toTimeString().split(' ')[0]}`
    ).toISOString();
    const duration_minutes = durationInput.value;

    try {
      const response = await fetch('/api/teacher/start-session', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          course_id: sessionState.courseId,
          start_datetime: start_time,
          duration_minutes,
          session_type: sessionType,
        }),
      });

      const data = await response.json();

      if (response.ok) {
        sessionState.sessionId = data.session_id;
        sessionState.allStudents = data.students;
        const endTimeStr = data.end_time;
        sessionState.endTime = new Date(endTimeStr.replace(' ', 'T'));

        liveCourseName.textContent = setupCourseName.textContent;
        totalStudentsSpan.textContent = sessionState.allStudents.length;
        searchInput.value = '';
        renderUnmarkedStudents(sessionState.allStudents);
        startLiveUpdates();
        startCountdownTimer();
        showView('liveOffline');
      } else {
        // FIXED: Use Modal instead of alert
        await Modal.alert(
          `Error starting session: ${data.message}`,
          'Error',
          'error'
        );
      }
    } catch (error) {
      console.error('Start session error:', error);
      // FIXED: Use Modal instead of alert
      await Modal.alert(
        'A network error occurred while starting the session.',
        'Network Error',
        'error'
      );
    }
  }

  // --- 5. LIVE DASHBOARD WORKFLOW ---
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

    if (timeLeft <= 0) {
      document.getElementById('countdown-display').textContent = 'Expired';
      document.getElementById('countdown-display').style.color =
        'var(--danger-color)';
      clearInterval(sessionState.countdownInterval);
      console.log('Countdown reached 0:00 - triggering expire check');
      checkAndExpireSession();
      return;
    }

    const totalSeconds = Math.floor(timeLeft / 1000);
    const minutes = Math.floor(totalSeconds / 60);
    const seconds = totalSeconds % 60;
    const display = `${minutes}:${seconds.toString().padStart(2, '0')}`;

    document.getElementById('countdown-display').textContent = display;

    const countdownEl = document.getElementById('countdown-display');
    if (minutes < 5) {
      countdownEl.style.color = 'var(--danger-color)';
    } else {
      countdownEl.style.color = 'var(--primary-color)';
    }
  }

  async function checkAndExpireSession() {
    if (!sessionState.sessionId) return;

    try {
      const response = await fetch(
        `/api/teacher/session/${sessionState.sessionId}/check-expire`,
        {
          method: 'POST',
        }
      );
      const data = await response.json();

      if (data.expired) {
        console.log('Session confirmed expired by server');
        stopLiveUpdates();
        stopCountdownTimer();
        // FIXED: Use Modal instead of alert
        await Modal.alert(
          'Session has automatically ended due to time expiration.',
          'Session Expired',
          'warning'
        );
        loadReport(sessionState.sessionId);
      } else if (data.status === 'active') {
        console.warn(
          'Countdown expired but server says session still active. Seconds remaining:',
          data.seconds_remaining
        );
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

  // ✅ UPDATED: Better device status handling with timestamp validation
  async function updateLiveStatus() {
    if (!sessionState.sessionId) return;

    try {
      // Get attendance status
      const statusResponse = await fetch(
        `/api/teacher/session/${sessionState.sessionId}/status`
      );
      const statusData = await statusResponse.json();

      if (statusResponse.ok) {
        // Check if session auto-expired
        if (statusData.session_active === false) {
          console.log('Session auto-expired detected');
          stopLiveUpdates();
          stopCountdownTimer();
          await Modal.alert(
            'Session has automatically ended due to time expiration.',
            'Session Expired',
            'warning'
          );
          loadReport(sessionState.sessionId);
          return;
        }

        // Update unmarked students list
        const markedUnivRollNos = new Set(statusData.marked_students);
        const unmarkedStudents = sessionState.allStudents.filter(
          (s) => !markedUnivRollNos.has(s.university_roll_no)
        );
        renderUnmarkedStudents(unmarkedStudents);
        attendanceCountSpan.textContent = markedUnivRollNos.size;
      }

      // ✅ NEW: Enhanced device status with offline detection
      const deviceResponse = await fetch('/api/teacher/device-status');
      const deviceData = await deviceResponse.json();

      if (deviceResponse.ok) {
        if (deviceData.status === 'online') {
          // Device is online and heartbeat is fresh
          const strength =
            deviceData.wifi_strength > -67
              ? 'Strong'
              : deviceData.wifi_strength > -80
              ? 'Okay'
              : 'Weak';

          deviceStatusText.innerHTML = `✅ Online (${strength})<br>🔋 ${deviceData.battery}% | 📝 Q: ${deviceData.queue_count} | 🔄 S: ${deviceData.sync_count}`;
        } else if (deviceData.status === 'offline') {
          // Device is offline (heartbeat stale or missing)
          if (deviceData.last_seen !== undefined) {
            // Show last known data with offline indicator
            deviceStatusText.innerHTML = `❌ Offline (${
              deviceData.last_seen
            }s ago)<br>🔋 Last: ${deviceData.battery || '?'}% | 📝 Q: ${
              deviceData.queue_count || 0
            }`;
          } else {
            deviceStatusText.innerHTML = `❌ Offline / No Data<br>Waiting for device...`;
          }
        } else {
          // Error or unknown status
          deviceStatusText.innerHTML = `⚠️ Status Unknown<br>${
            deviceData.message || 'Check connection'
          }`;
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
      .filter(
        (s) =>
          s.student_name.toLowerCase().includes(searchTerm) ||
          s.class_roll_id.toString().includes(searchTerm)
      )
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

  // FIXED: Use Modal.prompt instead of prompt
  unmarkedStudentsTbody.addEventListener('click', async (event) => {
    if (event.target.classList.contains('manual-mark-btn')) {
      const univ_roll_no = event.target.dataset.univRoll;

      // Find student name for better UX
      const student = sessionState.allStudents.find(
        (s) => s.university_roll_no === univ_roll_no
      );
      const studentName = student ? student.student_name : 'this student';

      const reason = await Modal.prompt(
        `Marking attendance for <strong>${studentName}</strong>.<br><br>Please provide a brief reason:`,
        'Manual Attendance Entry',
        '',
        'info'
      );

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
            await Modal.alert(
              'Attendance marked successfully!',
              'Success',
              'success'
            );
            updateLiveStatus();
          } else {
            const errorData = await response.json();
            await Modal.alert(
              `Failed to mark attendance: ${errorData.message}`,
              'Error',
              'error'
            );
          }
        } catch (error) {
          console.error('Manual override error:', error);
          await Modal.alert(
            'A network error occurred.',
            'Network Error',
            'error'
          );
        }
      }
    }
  });

  // --- 6. SESSION CONTROL & REPORTING ---
  // FIXED: Use Modal.confirm instead of confirm
  endSessionButton.addEventListener('click', async () => {
    const confirmed = await Modal.confirm(
      'Are you sure you want to end this session? This action cannot be undone.',
      'Confirm End Session',
      'warning'
    );

    if (!confirmed) return;

    stopLiveUpdates();
    stopCountdownTimer();

    await fetch(`/api/teacher/session/${sessionState.sessionId}/end`, {
      method: 'POST',
    });

    loadReport(sessionState.sessionId);
  });

  // FIXED: Use Modal.confirm and Modal.alert instead of alert/confirm
  extendSessionButton.addEventListener('click', async () => {
    const countdownEl = document.getElementById('countdown-display');
    if (countdownEl && countdownEl.textContent === 'Expired') {
      await Modal.alert(
        'Cannot extend - session has already expired. Please end the session and start a new one.',
        'Session Expired',
        'warning'
      );
      return;
    }

    const confirmed = await Modal.confirm(
      'Do you want to extend this session by 10 minutes?',
      'Extend Session',
      'info'
    );

    if (!confirmed) return;

    try {
      const response = await fetch(
        `/api/teacher/session/${sessionState.sessionId}/extend`,
        {
          method: 'POST',
        }
      );

      if (response.ok) {
        const data = await response.json();
        const newEndTimeStr = data.new_end_time;
        sessionState.endTime = new Date(newEndTimeStr.replace(' ', 'T'));
        console.log('Session extended. New end time:', sessionState.endTime);
        await Modal.alert(
          'Session extended by 10 minutes successfully!',
          'Success',
          'success'
        );
      } else {
        const error = await response.json();
        await Modal.alert(
          error.message || 'Failed to extend session.',
          'Error',
          'error'
        );
      }
    } catch (error) {
      console.error('Extend session error:', error);
      await Modal.alert(
        'Network error while extending session.',
        'Network Error',
        'error'
      );
    }
  });

  async function loadReport(sessionId) {
    try {
      const response = await fetch(`/api/teacher/report/${sessionId}`);
      const data = await response.json();

      if (response.ok) {
        renderReportTable(data);
        reportCourseName.textContent = liveCourseName.textContent;
        showView('report');
      } else {
        await Modal.alert('Failed to load report.', 'Error', 'error');
      }
    } catch (error) {
      console.error('Report loading error:', error);
    }
  }

  function renderReportTable(data) {
    reportTable.innerHTML = '';

    const thead = document.createElement('thead');
    let headerHtml =
      '<tr><th>Class Roll</th><th>Name</th><th>Univ. Roll No.</th>';

    const sortedSessions = data.sessions.sort(
      (a, b) => new Date(a.start_time) - new Date(b.start_time)
    );

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
    reportTable.appendChild(thead);

    const tbody = document.createElement('tbody');
    const presentSet = new Set(data.present_set.map((p) => `${p[0]}_${p[1]}`));

    data.students.forEach((student) => {
      let rowHtml = `<tr><td data-label="Class Roll">${student.class_roll_id}</td><td data-label="Name">${student.student_name}</td><td data-label="Univ. Roll No.">${student.university_roll_no}</td>`;

      sortedSessions.forEach((session) => {
        const sessionLabel = new Date(session.start_time).toLocaleDateString(
          'en-GB',
          { day: '2-digit', month: 'short' }
        );
        if (presentSet.has(`${session.id}_${student.id}`)) {
          rowHtml += `<td data-label="${sessionLabel}"><span title="Present">✅</span></td>`;
        } else {
          rowHtml += `<td data-label="${sessionLabel}"><span title="Absent">❌</span></td>`;
        }
      });

      rowHtml += '</tr>';
      tbody.innerHTML += rowHtml;
    });

    reportTable.appendChild(tbody);

    const tableContainer = document.querySelector(
      '.responsive-table-container'
    );
    if (tableContainer) {
      requestAnimationFrame(() => {
        tableContainer.scrollTo({
          left: tableContainer.scrollWidth,
          behavior: 'smooth',
        });
      });
    }
  }

  exportExcelButton.addEventListener('click', () => {
    window.open(`/api/teacher/report/export/${sessionState.sessionId}`);
  });

  newSessionButton.addEventListener('click', () => {
    sessionState = {
      courseId: null,
      sessionId: null,
      allStudents: [],
      liveUpdateInterval: null,
    };
    loginMessage.textContent = '';
    courseCodeInput.value = '';
    pinInput.value = '';
    showView('login');
  });

  // --- INITIALIZATION ---
  showView('login');
});
