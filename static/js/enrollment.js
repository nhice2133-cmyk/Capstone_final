/**
 * SMART ENTRY — Face Enrollment JavaScript
 * Three-step enrollment flow:
 *   1. Student info form & duplicate check → POST /admin/enroll/create (creates staging session, NOT db record)
 *   2. Auto-capture 20 quality-verified face images → POST /admin/enroll/capture (per frame in staging)
 *   3. Finalize & Train → POST /admin/enroll/train (atomic DB insert ONLY after all 20 images + retrain)
 */

const TOTAL_IMAGES = 20;
const CAPTURE_INTERVAL_MS = 800;   // ms between captures (allows subject to adjust pose)

// ── DOM refs ─────────────────────────────────────────────────────────────────
const step1       = document.getElementById("step1");
const step2       = document.getElementById("step2");
const step3       = document.getElementById("step3");
const step1Ind    = document.getElementById("step1Indicator");
const step2Ind    = document.getElementById("step2Indicator");
const step3Ind    = document.getElementById("step3Indicator");

const infoForm       = document.getElementById("studentInfoForm");
const firstNameInput = document.getElementById("firstName");
const lastNameInput  = document.getElementById("lastName");
const fullNameInput  = document.getElementById("fullName");
const lblFirstName   = document.getElementById("lblFirstName");
const lblLastName    = document.getElementById("lblLastName");
const groupFirstName = document.getElementById("groupFirstName");
const groupLastName  = document.getElementById("groupLastName");
const nameFormRow    = document.getElementById("nameFormRow");
const firstNameError     = document.getElementById("firstNameError");
const lastNameError      = document.getElementById("lastNameError");
const firstNameIcon      = document.getElementById("firstNameIcon");
const lastNameIcon       = document.getElementById("lastNameIcon");
const nameDuplicateAlert = document.getElementById("nameDuplicateAlert");
const studentIdInput = document.getElementById("studentId");
const idCharCounter  = document.getElementById("idCharCounter");
const studentIdIcon  = document.getElementById("studentIdIcon");
const studentIdError = document.getElementById("studentIdError");
const programInput   = document.getElementById("program");
const infoMessage    = document.getElementById("infoMessage");
const btnSaveInfo    = document.getElementById("btnSaveInfo");

const btnTypeStudent   = document.getElementById("btnTypeStudent");
const btnTypeGuest     = document.getElementById("btnTypeGuest");
const userTypeInput    = document.getElementById("userType");
const lblStudentId     = document.getElementById("lblStudentId");
const groupStudentId   = document.getElementById("groupStudentId");
const identityFormRow  = document.getElementById("identityFormRow");
const lblFullName      = document.getElementById("lblFullName");
const enrollCardHeader = document.getElementById("enrollCardHeader");

// ── Searchable Combobox DOM refs ─────────────────────────────────────────────
const programComboboxWrap = document.getElementById("programComboboxWrap");
const programMenu         = document.getElementById("programMenu");
const btnToggleProgram    = document.getElementById("btnToggleProgram");
const btnClearProgram     = document.getElementById("btnClearProgram");
const guestModeIndicator  = document.getElementById("guestModeIndicator");
const comboboxNoResults   = document.getElementById("comboboxNoResults");
const comboboxItems       = document.querySelectorAll(".combobox-item");

const enrollVideo    = document.getElementById("enrollVideo");
const enrollCanvas   = document.getElementById("enrollCanvas");
const captureCount   = document.getElementById("captureCount");
const captureMsg     = document.getElementById("captureMsg");
const guidanceBanner = document.getElementById("guidanceBanner");
const progressFill   = document.getElementById("captureProgressFill");
const btnStart       = document.getElementById("btnStartCapture");
const btnRetake      = document.getElementById("btnRetake");

const previewName = document.getElementById("previewName");
const previewId   = document.getElementById("previewId");
const previewProg = document.getElementById("previewProg");

const trainingAnim   = document.getElementById("trainingAnim");
const trainingResult = document.getElementById("trainingResult");
const btnEnrollAnother = document.getElementById("btnEnrollAnother");
const btnGoStudents  = document.getElementById("btnGoStudents");

let enrollToken   = null;
let captureTimer  = null;
let capturedCount = 0;
let stream        = null;

// ── Combobox Helper Functions ───────────────────────────────────────────────
function updateClearBtn() {
  if (btnClearProgram && programInput) {
    btnClearProgram.classList.toggle("hidden", !programInput.value);
  }
}

function openProgramMenu() {
  if (programMenu && programComboboxWrap) {
    programMenu.classList.remove("hidden");
    programComboboxWrap.classList.add("open");
    programMenu.scrollTop = 0;
  }
}

function closeProgramMenu() {
  if (programMenu && programComboboxWrap) {
    programMenu.classList.add("hidden");
    programComboboxWrap.classList.remove("open");
    comboboxItems.forEach(item => item.classList.remove("focused"));
  }
}

function highlightActiveComboboxItem(val) {
  comboboxItems.forEach(item => {
    const isMatch = val && (item.dataset.value === val || item.dataset.name === val);
    item.classList.toggle("selected", !!isMatch);
  });
}

function filterProgramOptions(query) {
  const q = (query || "").trim().toLowerCase();
  const currentType = (userTypeInput && userTypeInput.value) || "student";
  let totalVisible = 0;

  document.querySelectorAll(".combobox-group").forEach(group => {
    let groupVisible = 0;
    const items = group.querySelectorAll(".combobox-item");

    items.forEach(item => {
      const isGuestItem = item.classList.contains("guest-item") || item.dataset.type === "guest";
      const val = (item.dataset.value || "").toLowerCase();
      const name = (item.dataset.name || "").toLowerCase();
      const text = item.textContent.toLowerCase();

      // In student mode, hide guest options unless query specifically matches
      if (!q && currentType === "student" && isGuestItem) {
        item.classList.add("hidden");
        return;
      }
      // In guest mode, hide academic degree programs unless query specifically matches
      if (!q && currentType === "guest" && !isGuestItem) {
        item.classList.add("hidden");
        return;
      }

      const match = !q || val.includes(q) || name.includes(q) || text.includes(q);
      item.classList.toggle("hidden", !match);
      if (match) {
        groupVisible++;
        totalVisible++;
      }
    });
    group.classList.toggle("hidden", groupVisible === 0);
  });

  if (comboboxNoResults) {
    comboboxNoResults.classList.toggle("hidden", totalVisible > 0);
  }
}

// ── Proper Name Validation & Helpers ───────────────────────────────────────
const NAME_REGEX = /^[A-Za-zÀ-ÿñÑ\s\.\-']+$/;
let nameCheckDebounce = null;

function getCombinedFullName() {
  const first = firstNameInput ? firstNameInput.value.trim() : "";
  const last  = lastNameInput  ? lastNameInput.value.trim()  : "";
  return [first, last].filter(Boolean).join(" ");
}

function updateFullNameHidden() {
  const full = getCombinedFullName();
  if (fullNameInput) fullNameInput.value = full;
}

function formatTitleCase(str) {
  if (!str) return str;
  if (str === str.toLowerCase() || (str === str.toUpperCase() && str.length > 2)) {
    return str.replace(/\b([a-zÀ-ÿñÑ])/g, (c) => c.toUpperCase());
  }
  return str;
}

function setFieldInvalid(inputEl, errorEl, iconEl, msg) {
  inputEl.classList.add("is-invalid");
  inputEl.classList.remove("is-valid");
  if (errorEl) {
    errorEl.textContent = `⚠️ ${msg}`;
    errorEl.classList.remove("hidden");
  }
  if (iconEl) {
    iconEl.textContent = "✕";
    iconEl.className = "input-status-icon invalid";
  }
}

function setFieldValid(inputEl, errorEl, iconEl) {
  inputEl.classList.remove("is-invalid");
  inputEl.classList.add("is-valid");
  if (errorEl) {
    errorEl.textContent = "";
    errorEl.classList.add("hidden");
  }
  if (iconEl) {
    iconEl.textContent = "✓";
    iconEl.className = "input-status-icon valid";
  }
}

function validateNameField(inputEl, errorEl, iconEl, fieldLabel, isSilent = false) {
  if (!inputEl) return true;
  const val = inputEl.value.trim();

  if (!val) {
    if (isSilent) {
      inputEl.classList.remove("is-valid", "is-invalid");
      if (errorEl) { errorEl.textContent = ""; errorEl.classList.add("hidden"); }
      if (iconEl) { iconEl.textContent = ""; iconEl.className = "input-status-icon"; }
      return false;
    }
    setFieldInvalid(inputEl, errorEl, iconEl, `${fieldLabel} is required.`);
    return false;
  }

  if (val.length < 2) {
    setFieldInvalid(inputEl, errorEl, iconEl, `${fieldLabel} must be at least 2 characters.`);
    return false;
  }

  if (/\d/.test(val)) {
    setFieldInvalid(inputEl, errorEl, iconEl, `${fieldLabel} cannot contain numbers.`);
    return false;
  }

  if (!NAME_REGEX.test(val)) {
    setFieldInvalid(inputEl, errorEl, iconEl, `${fieldLabel} cannot contain special symbols (letters, spaces, hyphens only).`);
    return false;
  }

  if (/[-'.]{2,}/.test(val)) {
    setFieldInvalid(inputEl, errorEl, iconEl, `${fieldLabel} cannot have consecutive symbols.`);
    return false;
  }

  if (/^[-']|[-']$/.test(val)) {
    setFieldInvalid(inputEl, errorEl, iconEl, `${fieldLabel} cannot start or end with a hyphen or apostrophe.`);
    return false;
  }

  setFieldValid(inputEl, errorEl, iconEl);
  return true;
}

function checkNamesRealTime() {
  updateFullNameHidden();

  const firstValid = validateNameField(firstNameInput, firstNameError, firstNameIcon, "First Name", true);
  const lastValid  = validateNameField(lastNameInput,  lastNameError,  lastNameIcon,  "Last Name",  true);

  if (!firstValid || !lastValid) {
    if (nameDuplicateAlert) nameDuplicateAlert.classList.add("hidden");
    return;
  }

  clearTimeout(nameCheckDebounce);
  nameCheckDebounce = setTimeout(async () => {
    const first = firstNameInput.value.trim();
    const last  = lastNameInput.value.trim();
    if (!first || !last) return;

    try {
      const res = await fetch(`/admin/enroll/check_name?first_name=${encodeURIComponent(first)}&last_name=${encodeURIComponent(last)}`);
      const data = await res.json();
      if (!nameDuplicateAlert) return;

      if (data.duplicate) {
        nameDuplicateAlert.className = "name-duplicate-alert warning";
        nameDuplicateAlert.innerHTML = `<span>⚠️ ${data.message}</span>`;
        nameDuplicateAlert.classList.remove("hidden");
      } else if (data.valid) {
        nameDuplicateAlert.className = "name-duplicate-alert available";
        nameDuplicateAlert.innerHTML = `<span>✓ Name '${first} ${last}' is valid and available.</span>`;
        nameDuplicateAlert.classList.remove("hidden");
      } else {
        nameDuplicateAlert.className = "name-duplicate-alert error";
        nameDuplicateAlert.innerHTML = `<span>⚠️ ${data.message}</span>`;
        nameDuplicateAlert.classList.remove("hidden");
      }
    } catch {
      // Ignore network errors in silent check
    }
  }, 350);
}

if (firstNameInput) {
  firstNameInput.addEventListener("input", () => {
    checkNamesRealTime();
  });
  firstNameInput.addEventListener("blur", () => {
    firstNameInput.value = formatTitleCase(firstNameInput.value.trim());
    validateNameField(firstNameInput, firstNameError, firstNameIcon, "First Name", false);
    checkNamesRealTime();
  });
}

if (lastNameInput) {
  lastNameInput.addEventListener("input", () => {
    checkNamesRealTime();
  });
  lastNameInput.addEventListener("blur", () => {
    lastNameInput.value = formatTitleCase(lastNameInput.value.trim());
    validateNameField(lastNameInput, lastNameError, lastNameIcon, "Last Name", false);
    checkNamesRealTime();
  });
}

// ── Student / Employee ID Validation & Char Counter (10 Chars Max) ───────────
function updateIdCharCounter() {
  if (!studentIdInput || !idCharCounter) return;
  const val = studentIdInput.value;
  const len = val.length;
  idCharCounter.textContent = `${len} / 10`;
  if (len > 10) {
    studentIdInput.value = val.slice(0, 10);
    idCharCounter.textContent = "10 / 10";
    idCharCounter.className = "char-counter limit-reached";
  } else if (len === 10) {
    idCharCounter.className = "char-counter limit-reached";
  } else {
    idCharCounter.className = "char-counter";
  }
}

function validateStudentId(isSilent = false) {
  if (!studentIdInput) return true;
  const isGuest = userTypeInput && userTypeInput.value === "guest";
  if (isGuest) {
    studentIdInput.classList.remove("is-valid", "is-invalid");
    if (studentIdError) {
      studentIdError.textContent = "";
      studentIdError.classList.add("hidden");
    }
    if (studentIdIcon) {
      studentIdIcon.textContent = "";
      studentIdIcon.className = "input-status-icon";
    }
    return true;
  }

  const val = studentIdInput.value.trim();
  if (!val) {
    if (isSilent) {
      studentIdInput.classList.remove("is-valid", "is-invalid");
      if (studentIdError) {
        studentIdError.textContent = "";
        studentIdError.classList.add("hidden");
      }
      if (studentIdIcon) {
        studentIdIcon.textContent = "";
        studentIdIcon.className = "input-status-icon";
      }
      return false;
    }
    setFieldInvalid(studentIdInput, studentIdError, studentIdIcon, "Student / Employee ID is required.");
    return false;
  }

  if (val.length > 10) {
    setFieldInvalid(studentIdInput, studentIdError, studentIdIcon, "ID number cannot exceed 10 characters.");
    return false;
  }

  setFieldValid(studentIdInput, studentIdError, studentIdIcon);
  return true;
}

if (studentIdInput) {
  studentIdInput.addEventListener("input", () => {
    updateIdCharCounter();
    if (studentIdInput.value.trim().length > 0) {
      validateStudentId(true);
    }
  });

  studentIdInput.addEventListener("blur", () => {
    updateIdCharCounter();
    validateStudentId(false);
  });
  updateIdCharCounter();
}

// ── User Category Toggle (Student vs Guest) ─────────────────────────────────
function setUserType(type) {
  if (type === "guest") {
    if (userTypeInput) userTypeInput.value = "guest";
    if (btnTypeGuest) btnTypeGuest.classList.add("active", "guest-active");
    if (btnTypeStudent) btnTypeStudent.classList.remove("active");

    // Completely remove/hide the input ID field for guests
    if (groupStudentId) groupStudentId.style.display = "none";
    if (studentIdInput) {
      studentIdInput.removeAttribute("required");
      studentIdInput.value = "";
      studentIdInput.classList.remove("is-valid", "is-invalid");
    }
    if (studentIdError) {
      studentIdError.textContent = "";
      studentIdError.classList.add("hidden");
    }
    if (studentIdIcon) {
      studentIdIcon.textContent = "";
      studentIdIcon.className = "input-status-icon";
    }
    if (idCharCounter) {
      idCharCounter.textContent = "0 / 10";
      idCharCounter.className = "char-counter";
    }
    if (lblFirstName) lblFirstName.textContent = "Guest First Name *";
    if (lblLastName)  lblLastName.textContent  = "Guest Last Name *";
    if (firstNameInput) firstNameInput.placeholder = "e.g. Maria";
    if (lastNameInput)  lastNameInput.placeholder  = "e.g. Santos";
    if (lblFullName) lblFullName.textContent = "Guest Full Name *";
    if (fullNameInput) fullNameInput.placeholder = "e.g. Maria Santos";
    if (enrollCardHeader) enrollCardHeader.textContent = "📝 Guest Information";

    if (programInput && (!programInput.value || programInput.value.startsWith("BS") || programInput.value.startsWith("BT") || programInput.value.startsWith("EET") || programInput.value.startsWith("Faculty") || programInput.value.startsWith("Library"))) {
      programInput.value = "Guest";
    }
    const lblProg = document.getElementById("lblProgram");
    if (lblProg) lblProg.textContent = "Guest Category *";
    if (programInput) programInput.placeholder = "Select guest category...";
    if (guestModeIndicator) guestModeIndicator.classList.remove("hidden");
    highlightActiveComboboxItem("Guest");
    updateClearBtn();
    filterProgramOptions("");
  } else {
    if (userTypeInput) userTypeInput.value = "student";
    if (btnTypeStudent) btnTypeStudent.classList.add("active");
    if (btnTypeGuest) btnTypeGuest.classList.remove("active", "guest-active");

    // Restore the input ID field for students/personnel
    if (groupStudentId) groupStudentId.style.display = "";
    if (studentIdInput) {
      studentIdInput.setAttribute("required", "required");
      studentIdInput.setAttribute("maxlength", "10");
      studentIdInput.placeholder = "e.g. 211-00123 or EMP-2026";
      updateIdCharCounter();
    }
    if (lblFirstName) lblFirstName.textContent = "First Name *";
    if (lblLastName)  lblLastName.textContent  = "Last Name *";
    if (firstNameInput) firstNameInput.placeholder = "e.g. Juan";
    if (lastNameInput)  lastNameInput.placeholder  = "e.g. Dela Cruz";
    if (lblFullName) lblFullName.textContent = "Full Name *";
    if (fullNameInput) fullNameInput.placeholder = "e.g. Juan C. Dela Cruz";
    if (enrollCardHeader) enrollCardHeader.textContent = "📝 User Information";

    const lblProg = document.getElementById("lblProgram");
    if (lblProg) lblProg.textContent = "Program / Department *";
    if (programInput) programInput.placeholder = "Search program or department...";

    if (programInput && (programInput.value === "Guest" || programInput.value === "Visiting-Researcher" || programInput.value === "Community-User")) {
      programInput.value = "";
    }
    if (guestModeIndicator) guestModeIndicator.classList.add("hidden");
    highlightActiveComboboxItem("");
    updateClearBtn();
    filterProgramOptions("");
  }
}

if (btnTypeStudent) {
  btnTypeStudent.addEventListener("click", () => setUserType("student"));
}
if (btnTypeGuest) {
  btnTypeGuest.addEventListener("click", () => setUserType("guest"));
}

// ── Combobox Event Listeners ────────────────────────────────────────────────
comboboxItems.forEach(item => {
  item.addEventListener("click", () => {
    const val = item.dataset.value;
    const isGuest = item.dataset.type === "guest" || val === "Guest" || val === "Visiting-Researcher" || val === "Community-User";

    if (programInput) {
      programInput.value = val;
      updateClearBtn();
    }
    highlightActiveComboboxItem(val);
    closeProgramMenu();

    if (isGuest) {
      setUserType("guest");
    } else {
      setUserType("student");
    }
  });
});

if (programInput) {
  programInput.addEventListener("focus", () => {
    filterProgramOptions(programInput.value);
    openProgramMenu();
  });

  programInput.addEventListener("click", () => {
    filterProgramOptions(programInput.value);
    openProgramMenu();
  });

  programInput.addEventListener("input", () => {
    updateClearBtn();
    filterProgramOptions(programInput.value);
    openProgramMenu();

    const val = programInput.value.trim().toLowerCase();
    if (val === "guest" || val.includes("guest") || val.includes("visitor") || val.includes("researcher")) {
      if (userTypeInput && userTypeInput.value !== "guest") {
        setUserType("guest");
      }
    } else if (val.startsWith("bs") || val.startsWith("bt") || val.startsWith("eet") || val.includes("engineering") || val.includes("technology") || val.includes("education") || val.includes("faculty") || val.includes("employee") || val.includes("staff")) {
      if (userTypeInput && userTypeInput.value !== "student") {
        setUserType("student");
      }
    }
  });

  programInput.addEventListener("keydown", (e) => {
    if (e.key === "ArrowDown") {
      e.preventDefault();
      openProgramMenu();
      const visibleItems = Array.from(comboboxItems).filter(item => !item.classList.contains("hidden") && !item.parentElement.classList.contains("hidden"));
      if (visibleItems.length > 0) {
        const curIdx = visibleItems.findIndex(item => item.classList.contains("focused"));
        visibleItems.forEach(i => i.classList.remove("focused"));
        const nextIdx = (curIdx + 1) % visibleItems.length;
        visibleItems[nextIdx].classList.add("focused");
        visibleItems[nextIdx].scrollIntoView({ block: "nearest" });
      }
    } else if (e.key === "ArrowUp") {
      e.preventDefault();
      openProgramMenu();
      const visibleItems = Array.from(comboboxItems).filter(item => !item.classList.contains("hidden") && !item.parentElement.classList.contains("hidden"));
      if (visibleItems.length > 0) {
        const curIdx = visibleItems.findIndex(item => item.classList.contains("focused"));
        visibleItems.forEach(i => i.classList.remove("focused"));
        const nextIdx = (curIdx - 1 + visibleItems.length) % visibleItems.length;
        visibleItems[nextIdx].classList.add("focused");
        visibleItems[nextIdx].scrollIntoView({ block: "nearest" });
      }
    } else if (e.key === "Enter") {
      const focused = programMenu ? programMenu.querySelector(".combobox-item.focused:not(.hidden)") : null;
      if (focused && programMenu && !programMenu.classList.contains("hidden")) {
        e.preventDefault();
        focused.click();
      } else {
        closeProgramMenu();
      }
    } else if (e.key === "Escape") {
      closeProgramMenu();
    }
  });
}

if (btnToggleProgram) {
  btnToggleProgram.addEventListener("click", (e) => {
    e.preventDefault();
    e.stopPropagation();
    if (programMenu && programMenu.classList.contains("hidden")) {
      filterProgramOptions("");
      openProgramMenu();
      if (programInput) programInput.focus();
    } else {
      closeProgramMenu();
    }
  });
}

if (btnClearProgram) {
  btnClearProgram.addEventListener("click", (e) => {
    e.preventDefault();
    e.stopPropagation();
    if (programInput) {
      programInput.value = "";
      programInput.focus();
    }
    updateClearBtn();
    highlightActiveComboboxItem("");
    filterProgramOptions("");
    setUserType("student");
  });
}

document.addEventListener("click", (e) => {
  if (programComboboxWrap && !programComboboxWrap.contains(e.target)) {
    closeProgramMenu();
  }
});

// ── Step 1: Save student info (Validation only, no DB insert yet) ─────────────
infoForm.addEventListener("submit", async (e) => {
  e.preventDefault();
  setMsg(infoMessage, "", "");

  const userType = userTypeInput ? userTypeInput.value : "student";
  const isFirstValid = validateNameField(firstNameInput, firstNameError, firstNameIcon, "First Name", false);
  const isLastValid  = validateNameField(lastNameInput,  lastNameError,  lastNameIcon,  "Last Name",  false);
  const isIdValid    = userType === "guest" ? true : validateStudentId(false);

  if (!isFirstValid || !isLastValid || !isIdValid) {
    if (!isIdValid && (!isFirstValid || !isLastValid)) {
      setMsg(infoMessage, "Please correct the highlighted form errors before proceeding.", "error");
    } else if (!isIdValid) {
      setMsg(infoMessage, "Please enter a valid Student / Employee ID (max 10 characters).", "error");
      if (studentIdInput) studentIdInput.focus();
    } else {
      setMsg(infoMessage, "Please correct the name errors before proceeding.", "error");
      if (!isFirstValid && firstNameInput) firstNameInput.focus();
      else if (!isLastValid && lastNameInput) lastNameInput.focus();
    }
    return;
  }

  btnSaveInfo.disabled = true;
  btnSaveInfo.textContent = "Verifying…";

  const firstName = firstNameInput ? firstNameInput.value.trim() : "";
  const lastName  = lastNameInput  ? lastNameInput.value.trim()  : "";
  const fullName  = getCombinedFullName() || (fullNameInput ? fullNameInput.value.trim() : "");
  if (fullNameInput) fullNameInput.value = fullName;

  const payload = {
    first_name: firstName,
    last_name:  lastName,
    full_name:  fullName,
    student_id: studentIdInput ? studentIdInput.value.trim() : "",
    program:    programInput ? programInput.value.trim() : "",
    user_type:  userType,
  };

  try {
    const res = await fetch("/admin/enroll/create", {
      method: "POST",
      body: new URLSearchParams(payload),
    });
    const data = await res.json();
    if (data.success) {
      enrollToken = data.enroll_token || data.student_db_id;
      previewName.textContent = data.full_name || payload.full_name;
      previewId.textContent   = data.student_id || payload.student_id;
      previewProg.textContent = data.is_guest ? `${data.program} (Guest)` : (data.program || payload.program);
      goToStep(2);
      initWebcam();
    } else {
      setMsg(infoMessage, data.message, "error");
    }
  } catch (err) {
    setMsg(infoMessage, "Network error. Please try again.", "error");
  }

  btnSaveInfo.disabled = false;
  btnSaveInfo.textContent = "Proceed to Capture →";
});

// ── Webcam init ───────────────────────────────────────────────────────────────
async function initWebcam() {
  try {
    stream = await navigator.mediaDevices.getUserMedia({ video: { width: 640, height: 480 } });
    enrollVideo.srcObject = stream;
    enrollVideo.onloadedmetadata = () => {
      enrollCanvas.width  = enrollVideo.videoWidth;
      enrollCanvas.height = enrollVideo.videoHeight;
    };
  } catch (err) {
    setMsg(captureMsg, "Camera not accessible. Check webcam permissions.", "err");
  }
}

// ── Step 2: Auto-capture 20 Quality Images ─────────────────────────────────────
btnStart.addEventListener("click", () => {
  if (!enrollToken) {
    if (window.csuccAlert) {
      window.csuccAlert("Please save and verify student information in Step 1 before starting capture.", "Verification Required", "warning");
    } else {
      alert("Please save and verify student info first.");
    }
    return;
  }
  capturedCount = 0;
  updateProgress(0);
  if (guidanceBanner) {
    guidanceBanner.textContent = "🎯 Phase 1/4: Look straight at camera with neutral expression (5 frontal images).";
  }
  setMsg(captureMsg, "Hold still and look at the camera…", "ok");
  btnStart.classList.add("hidden");
  btnRetake.classList.add("hidden");
  captureTimer = setInterval(captureFrame, CAPTURE_INTERVAL_MS);
});

btnRetake.addEventListener("click", () => {
  capturedCount = 0;
  updateProgress(0);
  if (guidanceBanner) {
    guidanceBanner.textContent = "🎯 Phase 1/4: Look straight at camera with neutral expression (5 frontal images).";
  }
  setMsg(captureMsg, "Ready to capture again.", "ok");
  btnStart.classList.remove("hidden");
  btnRetake.classList.add("hidden");
});

async function captureFrame() {
  const ctx = enrollCanvas.getContext("2d");
  ctx.drawImage(enrollVideo, 0, 0, enrollCanvas.width, enrollCanvas.height);
  const imageData = enrollCanvas.toDataURL("image/jpeg", 0.85);

  try {
    const res = await fetch("/admin/enroll/capture", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        enroll_token: enrollToken,
        token: enrollToken,
        student_db_id: enrollToken,
        image: imageData,
        img_index: capturedCount,
      }),
    });
    const data = await res.json();
    if (data.success) {
      capturedCount++;
      updateProgress(capturedCount);
      setMsg(captureMsg, `✅ Sample ${capturedCount} of ${TOTAL_IMAGES} accepted.`, "ok");

      if (data.guidance && guidanceBanner) {
        guidanceBanner.textContent = `🎯 ${data.guidance}`;
      }

      if (capturedCount >= TOTAL_IMAGES) {
        clearInterval(captureTimer);
        captureTimer = null;
        setMsg(captureMsg, "✅ All 20 images captured! Finalizing student enrollment…", "ok");
        setTimeout(() => goToStep(3), 800);
        setTimeout(trainModel, 1200);
      }
    } else {
      setMsg(captureMsg, `⚠️ ${data.message}`, "err");
    }
  } catch {
    setMsg(captureMsg, "Network error. Retrying…", "err");
  }
}

function updateProgress(count) {
  const pct = (count / TOTAL_IMAGES) * 100;
  progressFill.style.width = pct + "%";
  captureCount.textContent = count;
}

// ── Step 3: Finalize Enrollment & Train Model ─────────────────────────────────
async function trainModel() {
  trainingAnim.classList.remove("hidden");
  trainingResult.classList.add("hidden");
  btnEnrollAnother.classList.add("hidden");
  btnGoStudents.classList.add("hidden");

  // Stop webcam stream
  if (stream) { stream.getTracks().forEach(t => t.stop()); stream = null; }

  try {
    const res = await fetch("/admin/enroll/train", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        enroll_token: enrollToken,
        token: enrollToken,
        student_db_id: enrollToken,
      }),
    });
    const data = await res.json();

    trainingAnim.classList.add("hidden");
    trainingResult.classList.remove("hidden");

    if (data.success) {
      trainingResult.className = "training-result ok";
      trainingResult.innerHTML = `<strong>✅ Student Enrolled Successfully!</strong><br/>
        <div style="margin: 6px 0; color: #60a5fa; font-weight: 700; font-size: 1.05rem;">${data.full_name} (${data.student_id})</div>
        <small>${data.num_images} quality-verified face samples enrolled • Biometric models retrained</small>`;

      // Hot-reload model in recognition module
      await fetch("/kiosk/reload_model", { method: "POST" });

      step3Ind.classList.add("done");
    } else {
      trainingResult.className = "training-result err";
      trainingResult.innerHTML = `<strong>❌ Enrollment Finalization Failed</strong><br/><small>${data.message}</small>`;
    }
  } catch {
    trainingAnim.classList.add("hidden");
    trainingResult.classList.remove("hidden");
    trainingResult.className = "training-result err";
    trainingResult.innerHTML = "<strong>❌ Network error during enrollment finalization.</strong>";
  }

  btnEnrollAnother.classList.remove("hidden");
  btnGoStudents.classList.remove("hidden");
}

// ── Helpers ───────────────────────────────────────────────────────────────────
function goToStep(n) {
  [step1, step2, step3].forEach((el, i) => el.classList.toggle("hidden", i !== n - 1));
  [step1Ind, step2Ind, step3Ind].forEach((el, i) => {
    el.classList.toggle("active", i === n - 1);
    if (i < n - 1) el.classList.add("done");
  });
}

function setMsg(el, text, cls) {
  if (!el) return;
  el.textContent = text;
  const base = el.dataset.baseClass || el.className.split(" ")[0] || "form-msg";
  el.dataset.baseClass = base;
  el.className = cls ? `${base} ${cls}` : base;
}
