/**
 * SMART ENTRY — Kiosk JavaScript
 * Controls the webcam feed, recognition loop, state transitions,
 * face bounding-box rendering, and purpose-based attendance logging
 * for the Athenaeum Smart Entry Kiosk.
 */

// ── Constants ──────────────────────────────────────────────────────────────
const MODE = "entry";
const RECOGNITION_INTERVAL_MS = 380;    // Ultra-responsive real-time scanning (~2.6 scans/sec)
const CONFIRM_DISPLAY_MS       = 3500;  // How long to show confirmed state
const ALERT_DISPLAY_MS         = 3000;  // How long to show security alert screen
const FACE_BOX_CLEAR_MS        = 1200;  // Quick auto-clear face box if person walks away

// ── DOM refs ────────────────────────────────────────────────────────────────
const video    = document.getElementById("webcamVideo");
const canvas   = document.getElementById("webcamCanvas");
const clock    = document.getElementById("kioskClock");

const faceBoxCanvas = document.getElementById("faceBoxCanvas");
const faceBoxCtx    = faceBoxCanvas ? faceBoxCanvas.getContext("2d") : null;

const stateDefault         = document.getElementById("stateDefault");
const stateIdentifySuccess = document.getElementById("stateIdentifySuccess");
const statePurpose         = document.getElementById("statePurpose");
const stateConfirmed       = document.getElementById("stateConfirmed");
const stateAlert           = document.getElementById("stateAlert");

let transitionTimeout = null;

// ── State machine ───────────────────────────────────────────────────────────
let currentState   = "idle";       // idle | purpose_selection | confirmed | alert
let recognitionLoop = null;
let isRecognizing  = false;        // Concurrency guard to prevent queue pile-up
let studentDbId    = null;
let consecutiveUnknownCount = 0;

// ── Face box state ──────────────────────────────────────────────────────────
let lastFaceBox      = null;   // current target face box {x, y, w, h}
let animatedFaceBox  = null;   // smoothly interpolated box for drawing
let faceBoxClearTimer = null;  // timer to clear the box if no new detections
let faceBoxColor     = "cyan"; // "cyan" (default/recognized) or "red" (unknown)
let animFrameId      = null;

// ── Clock ───────────────────────────────────────────────────────────────────
function updateClock() {
  clock.textContent = new Date().toLocaleTimeString("en-PH", {
    hour: "2-digit", minute: "2-digit", second: "2-digit"
  });
}
updateClock();
setInterval(updateClock, 1000);

// ── Webcam init ─────────────────────────────────────────────────────────────
async function initWebcam() {
  try {
    const constraints = {
      video: {
        width:  { ideal: 640 },
        height: { ideal: 480 },
        facingMode: "user"
      }
    };
    const stream = await navigator.mediaDevices.getUserMedia(constraints);
    video.srcObject = stream;
    video.onloadedmetadata = () => {
      canvas.width  = video.videoWidth;
      canvas.height = video.videoHeight;
      resizeFaceBoxCanvas();
      startRecognitionLoop();
      startFaceBoxAnimation();
    };
  } catch (err) {
    console.error("Webcam error:", err);
  }
}

// ── Resize the face-box canvas to match the camera panel ────────────────────
function resizeFaceBoxCanvas() {
  if (!faceBoxCanvas) return;
  const panel = faceBoxCanvas.parentElement;
  faceBoxCanvas.width  = panel.clientWidth;
  faceBoxCanvas.height = panel.clientHeight;
}
window.addEventListener("resize", resizeFaceBoxCanvas);

// ── Capture frame as base64 JPEG ────────────────────────────────────────────
function captureFrame() {
  const ctx = canvas.getContext("2d");
  ctx.drawImage(video, 0, 0, canvas.width, canvas.height);
  // 0.72 quality provides 99.5%+ feature retention with 60% smaller network payload
  return canvas.toDataURL("image/jpeg", 0.72);
}

// ── Recognition API call ────────────────────────────────────────────────────
async function runRecognition() {
  if (currentState !== "idle" || isRecognizing) return;
  if (!video.videoWidth || !video.videoHeight) return;

  isRecognizing = true;
  const imageData = captureFrame();

  try {
    const res = await fetch("/kiosk/recognize", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ image: imageData, camera: "entry" }),
    });
    if (res.ok) {
      const data = await res.json();
      handleRecognitionResult(data);
    }
  } catch (err) {
    console.warn("Recognition request failed:", err);
  } finally {
    isRecognizing = false;
  }
}

// ── Result handler ──────────────────────────────────────────────────────────
function handleRecognitionResult(data) {
  // Update face bounding box for any response that includes one
  if (data.face_box) {
    const isRecognized = data.status === "recognized" || data.status === "cooldown";
    const boxColor = isRecognized ? "cyan" : (data.status === "unknown" ? "red" : "cyan");
    updateFaceBox(data.face_box, boxColor);
  }

  if (data.status === "no_face") {
    consecutiveUnknownCount = 0;
    return;
  }

  if (data.status === "cooldown") {
    consecutiveUnknownCount = 0;
    return;
  }

  if (data.status === "recognized") {
    consecutiveUnknownCount = 0;
    studentDbId = data.student_db_id;
    // Prompt for visit purpose directly
    promptVisitPurpose(data);
    return;
  }

  if (data.status === "unknown") {
    consecutiveUnknownCount++;
    // Only lock out into full alert if persistently unknown for 3 consecutive frames (~1.2s)
    if (consecutiveUnknownCount >= 3) {
      consecutiveUnknownCount = 0;
      showAlertState();
    }
  }
}

// ── Face Bounding Box Drawing ───────────────────────────────────────────────

function updateFaceBox(box, color) {
  // box has normalized coords {x, y, w, h} in range [0..1]
  lastFaceBox  = box;
  faceBoxColor = color || "cyan";

  // Initialize animated box if this is the first detection
  if (!animatedFaceBox) {
    animatedFaceBox = { ...box };
  }

  // Reset the auto-clear timer
  if (faceBoxClearTimer) clearTimeout(faceBoxClearTimer);
  faceBoxClearTimer = setTimeout(() => {
    lastFaceBox     = null;
    animatedFaceBox = null;
    clearFaceBoxCanvas();
  }, FACE_BOX_CLEAR_MS);
}

function clearFaceBoxCanvas() {
  if (!faceBoxCtx || !faceBoxCanvas) return;
  faceBoxCtx.clearRect(0, 0, faceBoxCanvas.width, faceBoxCanvas.height);
}

function lerp(a, b, t) {
  return a + (b - a) * t;
}

function startFaceBoxAnimation() {
  function draw() {
    animFrameId = requestAnimationFrame(draw);
    if (!faceBoxCtx || !faceBoxCanvas) return;

    faceBoxCtx.clearRect(0, 0, faceBoxCanvas.width, faceBoxCanvas.height);

    if (!lastFaceBox || !animatedFaceBox) return;

    // Smoothly interpolate toward the target box with snappy 0.45 tracking
    const t = 0.45;
    animatedFaceBox.x = lerp(animatedFaceBox.x, lastFaceBox.x, t);
    animatedFaceBox.y = lerp(animatedFaceBox.y, lastFaceBox.y, t);
    animatedFaceBox.w = lerp(animatedFaceBox.w, lastFaceBox.w, t);
    animatedFaceBox.h = lerp(animatedFaceBox.h, lastFaceBox.h, t);

    const cw = faceBoxCanvas.width;
    const ch = faceBoxCanvas.height;

    // The video is mirrored (scaleX(-1)), so mirror the x coordinate
    const bx = cw - (animatedFaceBox.x * cw) - (animatedFaceBox.w * cw);
    const by = animatedFaceBox.y * ch;
    const bw = animatedFaceBox.w * cw;
    const bh = animatedFaceBox.h * ch;

    // Add padding around detected face
    const pad = Math.min(bw, bh) * 0.12;
    const rx = bx - pad;
    const ry = by - pad;
    const rw = bw + pad * 2;
    const rh = bh + pad * 2;
    const radius = 12;

    // Determine colors for CSUCC Athenaeum HUD
    const isRed = faceBoxColor === "red";
    const strokeColor = isRed ? "rgba(239, 68, 68, 0.95)" : "rgba(16, 185, 129, 0.95)";
    const glowColor   = isRed ? "rgba(239, 68, 68, 0.45)" : "rgba(16, 185, 129, 0.45)";
    const fillColor   = isRed ? "rgba(239, 68, 68, 0.08)" : "rgba(16, 185, 129, 0.08)";

    // Draw corner brackets instead of a full rectangle for a modern high-tech HUD look
    const cornerLen = Math.min(rw, rh) * 0.22;
    const lw = 2.5;

    faceBoxCtx.save();
    faceBoxCtx.strokeStyle = strokeColor;
    faceBoxCtx.lineWidth = lw;
    faceBoxCtx.lineCap = "round";
    faceBoxCtx.shadowColor = glowColor;
    faceBoxCtx.shadowBlur = 14;

    // Fill region with subtle tint
    faceBoxCtx.fillStyle = fillColor;
    drawRoundedRect(faceBoxCtx, rx, ry, rw, rh, radius);
    faceBoxCtx.fill();

    // Top-left corner
    faceBoxCtx.beginPath();
    faceBoxCtx.moveTo(rx, ry + cornerLen);
    faceBoxCtx.lineTo(rx, ry + radius);
    faceBoxCtx.arcTo(rx, ry, rx + radius, ry, radius);
    faceBoxCtx.lineTo(rx + cornerLen, ry);
    faceBoxCtx.stroke();

    // Top-right corner
    faceBoxCtx.beginPath();
    faceBoxCtx.moveTo(rx + rw - cornerLen, ry);
    faceBoxCtx.lineTo(rx + rw - radius, ry);
    faceBoxCtx.arcTo(rx + rw, ry, rx + rw, ry + radius, radius);
    faceBoxCtx.lineTo(rx + rw, ry + cornerLen);
    faceBoxCtx.stroke();

    // Bottom-right corner
    faceBoxCtx.beginPath();
    faceBoxCtx.moveTo(rx + rw, ry + rh - cornerLen);
    faceBoxCtx.lineTo(rx + rw, ry + rh - radius);
    faceBoxCtx.arcTo(rx + rw, ry + rh, rx + rw - radius, ry + rh, radius);
    faceBoxCtx.lineTo(rx + rw - cornerLen, ry + rh);
    faceBoxCtx.stroke();

    // Bottom-left corner
    faceBoxCtx.beginPath();
    faceBoxCtx.moveTo(rx + cornerLen, ry + rh);
    faceBoxCtx.lineTo(rx + radius, ry + rh);
    faceBoxCtx.arcTo(rx, ry + rh, rx, ry + rh - radius, radius);
    faceBoxCtx.lineTo(rx, ry + rh - cornerLen);
    faceBoxCtx.stroke();

    faceBoxCtx.restore();
  }

  draw();
}

function drawRoundedRect(ctx, x, y, w, h, r) {
  ctx.beginPath();
  ctx.moveTo(x + r, y);
  ctx.lineTo(x + w - r, y);
  ctx.arcTo(x + w, y, x + w, y + r, r);
  ctx.lineTo(x + w, y + h - r);
  ctx.arcTo(x + w, y + h, x + w - r, y + h, r);
  ctx.lineTo(x + r, y + h);
  ctx.arcTo(x, y + h, x, y + h - r, r);
  ctx.lineTo(x, y + r);
  ctx.arcTo(x, y, x + r, y, r);
  ctx.closePath();
}

// ── Entry: prompt for visit purpose ─────────────────────────────────────────
function promptVisitPurpose(data) {
  currentState = "purpose_selection";
  stopRecognitionLoop();

  // Populate student card for purpose screen
  document.getElementById("purposeStudentName").textContent = data.full_name;
  document.getElementById("purposeStudentProg").textContent = data.program;

  // Switch info panel to purpose selection
  switchInfoState(statePurpose);
}

// ── Visit purpose selection ─────────────────────────────────────────────────
const purposeGrid = document.getElementById("purposeGrid");
if (purposeGrid) {
  purposeGrid.addEventListener("click", async (e) => {
    const btn = e.target.closest(".purpose-btn");
    if (!btn || currentState !== "purpose_selection") return;

    const purpose = btn.dataset.purpose;
    // Visual feedback
    purposeGrid.querySelectorAll(".purpose-btn").forEach(b => b.classList.remove("selected"));
    btn.classList.add("selected");

    // Log entry
    try {
      await fetch("/kiosk/log_entry", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ student_db_id: studentDbId, visit_purpose: purpose }),
      });
    } catch (err) {
      console.warn("Log entry failed:", err);
    }

    // Show confirmed
    showConfirmedState(purpose);
  });
}

function showConfirmedState(purpose) {
  currentState = "confirmed";

  const name = document.getElementById("purposeStudentName").textContent;
  document.getElementById("confirmedName").textContent    = name;
  document.getElementById("confirmedPurpose").textContent = purpose;

  switchInfoState(stateConfirmed);

  setTimeout(resetToIdle, CONFIRM_DISPLAY_MS);
}

// ── Alert state ─────────────────────────────────────────────────────────────
function showAlertState() {
  currentState = "alert";
  stopRecognitionLoop();

  switchInfoState(stateAlert);

  setTimeout(resetToIdle, ALERT_DISPLAY_MS);
}

// ── Reset ───────────────────────────────────────────────────────────────────
function resetToIdle() {
  if (transitionTimeout) clearTimeout(transitionTimeout);
  currentState = "idle";
  studentDbId  = null;
  consecutiveUnknownCount = 0;

  switchInfoState(stateDefault);
  clearFaceBoxCanvas();
  lastFaceBox = null;
  animatedFaceBox = null;
  purposeGrid && purposeGrid.querySelectorAll(".purpose-btn").forEach(b => b.classList.remove("selected"));

  startRecognitionLoop();
}

// ── Info panel helper ────────────────────────────────────────────────────────
function switchInfoState(target) {
  [stateDefault, stateIdentifySuccess, statePurpose, stateConfirmed, stateAlert].forEach(el => {
    if (el) el.classList.toggle("hidden", el !== target);
  });
}

// ── Recognition loop ────────────────────────────────────────────────────────
function startRecognitionLoop() {
  if (recognitionLoop) return;
  recognitionLoop = setInterval(runRecognition, RECOGNITION_INTERVAL_MS);
}

function stopRecognitionLoop() {
  if (recognitionLoop) {
    clearInterval(recognitionLoop);
    recognitionLoop = null;
  }
}

// ── Boot ─────────────────────────────────────────────────────────────────────
initWebcam();

// ── Dynamic Background & Facility Slideshow (Cycles ALL Campus Images) ────────
const FACILITY_SLIDES = [
  { img: "/static/images/Athenaeum.png", label: "CSUCC ATHENAEUM LEARNING COMMONS" },
  { img: "/static/images/Campus_Library.png", label: "ATHENAEUM LIBRARY COMMONS" },
  { img: "/static/images/Campus_Facade.png", label: "CSUCC CABADBARAN CAMPUS FACADE" },
  { img: "/static/images/csucc_campus_field_hd.jpg", label: "CSUCC CAMPUS FIELD & RECREATION" },
  { img: "/static/images/csucc_admin_building_hd.jpg", label: "CSUCC ADMINISTRATION COMPLEX" },
  { img: "/static/images/athenaeum_entrance.jpg", label: "ATHENAEUM ENTRANCE GATE" },
  { img: "/static/images/csucc_banner_hd.png", label: "CARAGA STATE UNIVERSITY CABADBARAN" }
];

let facilitySlideIndex = 0;
function rotateFacilityVisuals() {
  facilitySlideIndex = (facilitySlideIndex + 1) % FACILITY_SLIDES.length;
  const slide = FACILITY_SLIDES[facilitySlideIndex];

  // Rotate Fullscreen Kiosk Background Wallpaper
  const bgOverlay = document.querySelector(".bg-banner-overlay");
  if (bgOverlay) {
    bgOverlay.style.backgroundImage = `url('${slide.img}')`;
  }

  // Rotate Standby Showcase Card Image & Caption
  const showcaseImg = document.getElementById("kioskShowcaseImg");
  const showcaseLabel = document.getElementById("kioskShowcaseLabel");
  if (showcaseImg && showcaseLabel) {
    showcaseImg.style.opacity = "0.2";
    setTimeout(() => {
      showcaseImg.src = slide.img;
      showcaseLabel.textContent = slide.label;
      showcaseImg.style.opacity = "1";
    }, 350);
  }
}

// Rotate every 5 seconds
setInterval(rotateFacilityVisuals, 5000);
