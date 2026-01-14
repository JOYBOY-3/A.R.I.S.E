# Code Audit Report: batchcode → course_code Renaming

## ✅ VERIFIED CORRECT

### 1. **database_setup.py** ✅ CORRECT
```python
course_code TEXT UNIQUE NOT NULL,  // ✅ CORRECT
```
- Database schema properly uses `course_code`
- No remaining `batchcode` references

---

### 2. **teacher.html** ✅ CORRECT
```html
<label for="course-code-input">Course Code</label>  // ✅ CORRECT
<select id="course-code-input">  // ✅ CORRECT
```
- HTML form IDs updated correctly
- Labels updated correctly

---

### 3. **admin.html** ✅ CORRECT
```html
<label for="course-code">Course Code (Unique)</label>  // ✅ CORRECT
<input type="text" id="course-code" required />  // ✅ CORRECT

<th data-field="course_code">Course Code</th>  // ✅ CORRECT
<td data-label="Course Code">${item.course_code}</td>  // ✅ CORRECT

<!-- Enrollment Roster -->
<th>Enrolled Courses (Course Codes)</th>  // ✅ CORRECT
```

---

## ⚠️ ERRORS FOUND

### 4. **teacher.js** ❌ ISSUES FOUND

#### Issue 1: Variable name still uses "batchcode"
```javascript
const batchcodeInput = document.getElementById('course-code-input');
// ❌ WRONG: Variable name doesn't match purpose

// SHOULD BE:
const courseCodeInput = document.getElementById('course-code-input');
```

#### Issue 2: Function name not updated
```javascript
async function loadBatchCodes() {  // ❌ WRONG NAME
// SHOULD BE:
async function loadCourseCodes() {
```

#### Issue 3: Fetch endpoint wrong
```javascript
const response = await fetch('/api/teacher/batchcodes');  // ❌ WRONG ENDPOINT
// SHOULD BE:
const response = await fetch('/api/teacher/course-codes');
```

#### Issue 4: Variable assignments using old name
```javascript
const batchcodeInput = document.getElementById('course-code-input');
batchcodeInput.innerHTML = '<option value="">-- Select Batch Code --</option>';
// ❌ Both the variable name AND the text are wrong

// SHOULD BE:
const courseCodeInput = document.getElementById('course-code-input');
courseCodeInput.innerHTML = '<option value="">-- Select Course Code --</option>';
```

#### Issue 5: Event listener using wrong variable
```javascript
batchcodeInput.addEventListener('change', () => {
  loginButton.disabled = !batchcodeInput.value || !pinInput.value;
});

pinInput.addEventListener('input', () => {
  loginButton.disabled = !batchcodeInput.value || !pinInput.value;
});
// ❌ ALL of these reference the wrong variable

// SHOULD BE:
courseCodeInput.addEventListener('change', () => {
  loginButton.disabled = !courseCodeInput.value || !pinInput.value;
});

pinInput.addEventListener('input', () => {
  loginButton.disabled = !courseCodeInput.value || !pinInput.value;
});
```

#### Issue 6: Login endpoint data wrong
```javascript
loginButton.addEventListener('click', async () => {
  const batchcode = batchcodeInput.value.trim();  // ❌ WRONG
  const pin = pinInput.value.trim();
  
  // ...
  body: JSON.stringify({ batchcode, pin }),  // ❌ WRONG key name
```
**SHOULD BE:**
```javascript
loginButton.addEventListener('click', async () => {
  const courseCode = courseCodeInput.value.trim();
  const pin = pinInput.value.trim();
  
  // ...
  body: JSON.stringify({ courseCode, pin }),
```

---

### 5. **admin.js** ❌ ISSUES FOUND

#### Issue 1: Display text error
```javascript
if (entity === 'courses') {
  cells = `
    <td data-label="Course Code">${item.course_code}</td>  // ✅ This is correct
    // ... but later:
  `;
}
```

#### Issue 2: Form population error
```javascript
if (entity === 'courses') {
  api.get(`courses/${id}`).then((course) => {
    form.querySelector('#course-code').value = course.course - code;  // ❌ WRONG!
    // MISSING HYPHEN! This will subtract instead of accessing the property
```
**SHOULD BE:**
```javascript
form.querySelector('#course-code').value = course.course_code;
```

#### Issue 3: Dropdown population error
```javascript
courses.forEach(
  (c) =>
    (enrollmentCourseSelect.innerHTML += `<option value="${c.id}">${
      c.course_name
    } (${c.course - code})</option>`)  // ❌ WRONG! course - code (subtraction)
);
```
**SHOULD BE:**
```javascript
courses.forEach(
  (c) =>
    (enrollmentCourseSelect.innerHTML += `<option value="${c.id}">${
      c.course_name
    } (${c.course_code})</option>`)
);
```

#### Issue 4: Course form submission
```javascript
courseForm.addEventListener('submit', async (e) => {
  e.preventDefault();
  const body = {
    course_name: document.getElementById('course-name').value,
    course_code: document.getElementById('course-code').value,  // ✅ Correct ID
    // ... rest looks good
  };
```
**Status:** ✅ This section is CORRECT

---

### 6. **server.py** ✅ MOSTLY CORRECT (with 1 typo)

#### Issue: Endpoint name typo
```python
@app.route('/api/teacher/coursecodes', methods=['GET'])
def get_coursecodes():  // ❌ Missing hyphen in endpoint
```
**Status:** Your teacher.js tries to call `/api/teacher/course-codes` (with hyphen)
but your server defines `/api/teacher/coursecodes` (without hyphen)

**SHOULD MATCH ONE OF THESE:**

Option 1 (with hyphen - recommended):
```python
@app.route('/api/teacher/course-codes', methods=['GET'])  // ✅ MATCHES teacher.js
def get_course_codes():
    """Returns all course codes for the teacher login dropdown."""
    conn = get_db_connection()
    course_codes = [row['course_code'] for row in conn.execute("SELECT course_code FROM courses ORDER BY course_code").fetchall()]
    conn.close()
    return jsonify(course_codes)
```

Option 2 (without hyphen - simpler):
```python
@app.route('/api/teacher/course-codes', methods=['GET'])
def get_course_codes():
```

Rest of server.py: ✅ All SQL queries and JSON responses use `course_code` correctly

---

## Summary of Required Fixes

| File | Issue | Severity | Line(s) |
|------|-------|----------|---------|
| teacher.js | Variable name `batchcodeInput` should be `courseCodeInput` | HIGH | Multiple |
| teacher.js | Function `loadBatchCodes()` should be `loadCourseCodes()` | HIGH | ~1 |
| teacher.js | Endpoint `/api/teacher/batchcodes` → `/api/teacher/course-codes` | HIGH | ~1 |
| teacher.js | JSON key `{ batchcode, pin }` → `{ courseCode, pin }` | HIGH | ~1 |
| admin.js | `course.course - code` → `course.course_code` | CRITICAL | 1 location |
| admin.js | `c.course - code` → `c.course_code` | CRITICAL | 1 location |
| server.py | Endpoint path `/coursecodes` → `/course-codes` | HIGH | 1 line |

---

## ERRORS THAT WILL CAUSE RUNTIME FAILURES

### 1. **Teacher Login Will Fail** 🔴
**Reason:** Wrong API endpoint in teacher.js
- Code calls: `/api/teacher/batchcodes`
- Server provides: `/api/teacher/coursecodes`
- Result: 404 Not Found, dropdown won't populate

### 2. **Admin Course Edit Will Crash** 🔴
**Reason:** Syntax error `course.course - code` (subtraction operator)
- Code: `course.course - code` 
- Result: JavaScript tries to subtract "code" from course object → `NaN` or TypeError

### 3. **Admin Course Enrollment Will Crash** 🔴
**Reason:** Syntax error `c.course - code`
- Code tries to generate dropdown with `${c.course - code}`
- Result: Shows NaN or undefined in dropdown

---

## COMPLETE FIX NEEDED FOR teacher.js

Replace this section (around line 50-80):
```javascript
// WRONG:
const courseCodeInput = document.getElementById('course-code-input');
async function loadBatchCodes() {
  try {
    const response = await fetch('/api/teacher/batchcodes');
```

With this:
```javascript
// CORRECT:
const courseCodeInput = document.getElementById('course-code-input');
async function loadCourseCodes() {
  try {
    const response = await fetch('/api/teacher/course-codes');
```

And replace login handler:
```javascript
// WRONG:
const batchcode = batchcodeInput.value.trim();
const pin = pinInput.value.trim();
// ...
body: JSON.stringify({ batchcode, pin }),

// CORRECT:
const courseCode = courseCodeInput.value.trim();
const pin = pinInput.value.trim();
// ...
body: JSON.stringify({ courseCode, pin }),
```

---

## COMPLETE FIX NEEDED FOR admin.js

Line with course edit - replace:
```javascript
// WRONG:
form.querySelector('#course-code').value = course.course - code;

// CORRECT:
form.querySelector('#course-code').value = course.course_code;
```

Line with enrollment dropdown - replace:
```javascript
// WRONG:
} (${c.course - code})</option>`)

// CORRECT:
} (${c.course_code})</option>`)
```

---

## COMPLETE FIX NEEDED FOR server.py

Replace:
```python
# WRONG:
@app.route('/api/teacher/coursecodes', methods=['GET'])
def get_coursecodes():

# CORRECT:
@app.route('/api/teacher/course-codes', methods=['GET'])
def get_course_codes():
```