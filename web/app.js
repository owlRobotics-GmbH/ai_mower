(() => {
  const $ = (sel) => document.querySelector(sel);
  const api = async (path, body) => {
    const res = await fetch(path, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body || {}),
    });
    const data = await res.json();
    if (!data.ok) throw new Error(data.error || "API error");
    return data;
  };

  const translations = {
    de: {
      "actions.clear": "Leeren",
      "actions.copy": "Kopieren",
      "actions.refresh": "Aktualisieren",
      "actions.stop": "Stop",
      "camera.autoExposure": "Automatische Belichtung",
      "camera.controlsAuto": "Auto-Belichtung aktiv",
      "camera.controlsManual": "Manuelle Belichtung",
      "camera.controlsUnavailable": "Belichtungssteuerung nicht verfuegbar",
      "camera.errorPrefix": "Kamera",
      "camera.dynamicFramerate": "Dynamische Framerate",
      "camera.exposureTime": "Belichtungszeit",
      "camera.live": "Live-Kamera",
      "camera.resolution": "Auflösung",
      "camera.resolutionNone": "Keine Aufloesungen gelesen",
      "camera.resolutionRange": "Bereich: {ranges}",
      "camera.resolutionsFound": "{count} Kamera-Aufloesungen gefunden",
      "camera.resolutionUnavailable": "Aufloesungen nicht verfuegbar",
      "camera.settings": "Kamera-Einstellungen",
      "camera.streamAlt": "Kamerastream",
      "camera.viewDepth": "Depth",
      "camera.viewRgb": "RGB",
      "camera.viewSeg": "Seg",
      "capture.addCameraImage": "Bild von Kamera hinzufügen",
      "capture.class": "Klasse",
      "capture.dataset": "Datensatz",
      "capture.heading": "Daten erfassen",
      "crop.heading": "Kamera-Ausschnitt",
      "crop.height": "Hoehe %",
      "crop.hint": "Der Ausschnitt wird beim Kamera-Capture und beim Live-Test vor der Klassifikation angewendet.",
      "crop.reset": "Reset",
      "crop.save": "Ausschnitt speichern",
      "crop.use": "Ausschnitt verwenden",
      "crop.width": "Breite %",
      "crop.x": "X %",
      "crop.y": "Y %",
      "drive.active": "aktiv",
      "drive.inactive": "aus",
      "drive.noCan": "kein CAN",
      "images.confirmDelete": "Bild wirklich loeschen?\n\n{name}",
      "images.collapse": "Einklappen",
      "images.delete": "Loeschen",
      "images.expand": "Ausklappen",
      "images.heading": "Trainingsbilder",
      "images.hint": "Bilder per Auswahl nach Klasse und Split verschieben.",
      "images.toggleLabel": "Klasse",
      "images.toggleSplit": "Train/Valid",
      "label.lawn": "Lawn",
      "label.nonLawn": "Non-lawn",
      "language.label": "Sprache",
      "log.heading": "Session-Log",
      "log.hint": "Kopierbarer Verlauf fuer Training und Roboter-Steuerung.",
      "metrics.epoch": "Epoche",
      "metrics.heading": "Metriken",
      "metrics.noTraining": "Noch keine Trainingsmetriken",
      "metrics.noValues": "Noch keine Werte",
      "metrics.robotClassification": "Klassifizierung 30 s",
      "metrics.robotMotion": "Optischer Fluss 30 s",
      "motor.heading": "Motor-Zuordnung",
      "motor.invertLeft": "Linken Motor invertieren",
      "motor.invertRight": "Rechten Motor invertieren",
      "motor.mowerEnabled": "Mähmotor aktiv",
      "motor.mowerPwm": "Mähmotor PWM",
      "motor.mowerPwmRamp": "Mähmotor PWM-Rampe",
      "motor.pwmRamp": "Fahrmotor PWM-Rampe",
      "motor.swapSides": "Links/rechts tauschen",
      "profile.create": "Profil anlegen",
      "profile.heading": "Profil",
      "profile.name": "Profilname",
      "robot.cameraFps": "Kamera FPS",
      "robot.battery": "Akku",
      "robot.cameraHint": "Verwendet die Kamera-Einstellungen aus der Roboter-Steuerung.",
      "robot.cameraStreamAlt": "Roboter-Kamerastream",
      "robot.classificationMs": "Klassifikation ms",
      "robot.command": "Kommando",
      "robot.controlHeading": "Roboter-Steuerung",
      "robot.driveCurrent": "Getriebestrom",
      "robot.joystick": "Joystick",
      "robot.mode": "Modus",
      "robot.motors": "Motoren",
      "robot.mowerCurrent": "Mähstrom",
      "robot.readoutHeading": "Auswertung",
      "robot.sayMaeh": "Sag mäh!",
      "robot.showClassificationPlot": "Klassifizierungsplot anzeigen",
      "robot.stopButtonPressed": "Hardware-STOP gedrueckt",
      "robot.stopButtonReleased": "Hardware-STOP frei",
      "robot.stopButtonUnknown": "Hardware-STOP unbekannt",
      "robot.tab.camera": "Kamera",
      "robot.tab.computer": "Computer",
      "robot.tab.motor": "Motor",
      "robot.tab.robot": "Roboter",
      "robot.tab.speed": "Geschwindigkeit",
      "split.training": "Training",
      "split.validation": "Validierung",
      "speed.driveStallRecovery": "Fahrblockaden erkennen",
      "speed.forward": "Vorwärts",
      "speed.heading": "Auto-Geschwindigkeit",
      "speed.reverseBeforeTurn": "Rueckfahrt vor Drehung",
      "speed.reverseOnStall": "Rueckfahrt bei Blockade",
      "speed.turn": "Drehen",
      "speed.turnPause": "Dreh-Impulspause",
      "speed.turnStallMinDelta": "Drehblockade Mindestbewegung",
      "speed.turnStallMinSeconds": "Drehblockade aktive Dauer",
      "speed.turnStallRecovery": "Drehblockaden erkennen",
      "speed.driveStallMinPoints": "Fahrblockade Trackingpunkte",
      "speed.driveStallMinSeconds": "Fahrblockade Dauer",
      "speed.driveStallMinVelocity": "Fahrblockade Geschwindigkeit",
      "status.connecting": "Verbinde...",
      "status.error": "Fehler: {message}",
      "status.loading": "Wird geladen...",
      "status.ready": "Bereit",
      "status.trainingRunning": "Training laeuft",
      "system.cpu": "CPU",
      "system.cpuTemp": "CPU Temp",
      "system.disk": "Disk",
      "system.ram": "RAM",
      "system.confirm": "{label} wirklich ausführen?",
      "system.requested": "{label} angefordert",
      "tab.robot": "Roboter-Steuerung",
      "tab.training": "Training",
      "tabs.views": "Ansichten",
      "test.streamAlt": "Teststream",
      "test.active": "Test aktiv",
      "test.stopped": "Live-Test gestoppt",
      "test.start": "Klassifikation starten",
      "training.active": "Epoche {epoch}/{epochs}  acc {accuracy}%  val {valAccuracy}%",
      "training.batch": "Batch",
      "training.epochs": "Epochen",
      "training.heading": "Training",
      "training.inactive": "Kein Training aktiv",
      "training.start": "Training starten",
      "value.off": "aus",
    },
    en: {
      "actions.clear": "Clear",
      "actions.copy": "Copy",
      "actions.refresh": "Refresh",
      "actions.stop": "Stop",
      "camera.autoExposure": "Automatic exposure",
      "camera.controlsAuto": "Auto exposure active",
      "camera.controlsManual": "Manual exposure",
      "camera.controlsUnavailable": "Exposure controls unavailable",
      "camera.errorPrefix": "Camera",
      "camera.dynamicFramerate": "Dynamic framerate",
      "camera.exposureTime": "Exposure time",
      "camera.live": "Live camera",
      "camera.resolution": "Resolution",
      "camera.resolutionNone": "No resolutions read",
      "camera.resolutionRange": "Range: {ranges}",
      "camera.resolutionsFound": "{count} camera resolutions found",
      "camera.resolutionUnavailable": "Resolutions unavailable",
      "camera.settings": "Camera settings",
      "camera.streamAlt": "Camera stream",
      "camera.viewDepth": "Depth",
      "camera.viewRgb": "RGB",
      "camera.viewSeg": "Seg",
      "capture.addCameraImage": "Add image from camera",
      "capture.class": "Class",
      "capture.dataset": "Dataset",
      "capture.heading": "Capture data",
      "crop.heading": "Camera crop",
      "crop.height": "Height %",
      "crop.hint": "The crop is applied before classification for camera capture and live testing.",
      "crop.reset": "Reset",
      "crop.save": "Save crop",
      "crop.use": "Use crop",
      "crop.width": "Width %",
      "crop.x": "X %",
      "crop.y": "Y %",
      "drive.active": "active",
      "drive.inactive": "off",
      "drive.noCan": "no CAN",
      "images.confirmDelete": "Delete this image?\n\n{name}",
      "images.collapse": "Collapse",
      "images.delete": "Delete",
      "images.expand": "Expand",
      "images.heading": "Training images",
      "images.hint": "Use the controls to move images between class and split.",
      "images.toggleLabel": "Class",
      "images.toggleSplit": "Train/Valid",
      "label.lawn": "Lawn",
      "label.nonLawn": "Non-lawn",
      "language.label": "Language",
      "log.heading": "Session log",
      "log.hint": "Copyable history for training and robot control.",
      "metrics.epoch": "Epoch",
      "metrics.heading": "Metrics",
      "metrics.noTraining": "No training metrics yet",
      "metrics.noValues": "No values yet",
      "metrics.robotClassification": "Classification 30 s",
      "metrics.robotMotion": "Optical flow 30 s",
      "motor.heading": "Motor mapping",
      "motor.invertLeft": "Invert left motor",
      "motor.invertRight": "Invert right motor",
      "motor.mowerEnabled": "Mower motor active",
      "motor.mowerPwm": "Mower motor PWM",
      "motor.mowerPwmRamp": "Mower motor PWM ramp",
      "motor.pwmRamp": "Drive motor PWM ramp",
      "motor.swapSides": "Swap left/right",
      "profile.create": "Create profile",
      "profile.heading": "Profile",
      "profile.name": "Profile name",
      "robot.cameraFps": "Camera FPS",
      "robot.battery": "Battery",
      "robot.cameraHint": "Uses the camera settings from robot control.",
      "robot.cameraStreamAlt": "Robot camera stream",
      "robot.classificationMs": "Classification ms",
      "robot.command": "Command",
      "robot.controlHeading": "Robot control",
      "robot.driveCurrent": "Drive current",
      "robot.joystick": "Joystick",
      "robot.mode": "Mode",
      "robot.motors": "Motors",
      "robot.mowerCurrent": "Mower current",
      "robot.readoutHeading": "Readout",
      "robot.sayMaeh": "Say mow!",
      "robot.showClassificationPlot": "Show classification plot",
      "robot.stopButtonPressed": "Hardware STOP pressed",
      "robot.stopButtonReleased": "Hardware STOP released",
      "robot.stopButtonUnknown": "Hardware STOP unknown",
      "robot.tab.camera": "Camera",
      "robot.tab.computer": "Computer",
      "robot.tab.motor": "Motor",
      "robot.tab.robot": "Robot",
      "robot.tab.speed": "Speed",
      "split.training": "Training",
      "split.validation": "Validation",
      "speed.driveStallRecovery": "Detect drive stalls",
      "speed.forward": "Forward",
      "speed.heading": "Auto speed",
      "speed.reverseBeforeTurn": "Reverse before turn",
      "speed.reverseOnStall": "Reverse on stall",
      "speed.turn": "Turn",
      "speed.turnPause": "Turn impulse pause",
      "speed.turnStallMinDelta": "Turn stall minimum movement",
      "speed.turnStallMinSeconds": "Turn stall active duration",
      "speed.turnStallRecovery": "Detect turn stalls",
      "speed.driveStallMinPoints": "Drive stall tracking points",
      "speed.driveStallMinSeconds": "Drive stall duration",
      "speed.driveStallMinVelocity": "Drive stall velocity",
      "status.connecting": "Connecting...",
      "status.error": "Error: {message}",
      "status.loading": "Loading...",
      "status.ready": "Ready",
      "status.trainingRunning": "Training running",
      "system.cpu": "CPU",
      "system.cpuTemp": "CPU temp",
      "system.disk": "Disk",
      "system.ram": "RAM",
      "system.confirm": "Really execute {label}?",
      "system.requested": "{label} requested",
      "tab.robot": "Robot control",
      "tab.training": "Training",
      "tabs.views": "Views",
      "test.streamAlt": "Test stream",
      "test.active": "Test active",
      "test.stopped": "Live test stopped",
      "test.start": "Start classification",
      "training.active": "Epoch {epoch}/{epochs}  acc {accuracy}%  val {valAccuracy}%",
      "training.batch": "Batch",
      "training.epochs": "Epochs",
      "training.heading": "Training",
      "training.inactive": "No training active",
      "training.start": "Start training",
      "value.off": "off",
    },
  };
  const supportedLanguages = Object.keys(translations);
  let currentLanguage = supportedLanguages.includes(localStorage.getItem("aiMowerLanguage"))
    ? localStorage.getItem("aiMowerLanguage")
    : ((navigator.language || "").toLowerCase().startsWith("de") ? "de" : "en");
  const t = (key, values = {}) => {
    const template = translations[currentLanguage]?.[key] || translations.en[key] || key;
    return template.replace(/\{(\w+)\}/g, (_, name) => values[name] ?? "");
  };
  const applyI18n = () => {
    document.documentElement.lang = currentLanguage;
    document.querySelectorAll("[data-i18n]").forEach((el) => {
      el.textContent = t(el.dataset.i18n);
    });
    document.querySelectorAll("[data-i18n-attr]").forEach((el) => {
      for (const spec of el.dataset.i18nAttr.split(";")) {
        const [attr, key] = spec.split(":");
        if (attr && key) el.setAttribute(attr, t(key));
      }
    });
    document.querySelectorAll("[data-language]").forEach((button) => {
      button.classList.toggle("active", button.dataset.language === currentLanguage);
      button.setAttribute("aria-pressed", button.dataset.language === currentLanguage ? "true" : "false");
    });
    const languageMenuButton = $("#languageMenuButton");
    if (languageMenuButton) {
      languageMenuButton.classList.toggle("flag-de", currentLanguage === "de");
      languageMenuButton.classList.toggle("flag-en", currentLanguage === "en");
      const label = currentLanguage.toUpperCase();
      languageMenuButton.querySelector("span").textContent = label;
    }
  };

  let state = null;
  let selectedLabel = "gras";
  let selectedSplit = "train";
  let imageListKey = "";
  let imagesCollapsed = localStorage.getItem("aiMowerImagesCollapsed") === "1";
  let cameraSettingsApplied = false;
  let cameraResolutionOptionsKey = "";
  let cameraSettingsSaving = false;
  let cropDirty = false;
  const streamViews = {
    training: "rgb",
    robot: "rgb",
  };
  const displayLabel = (label) => ({ gras: t("label.lawn"), pavement: t("label.nonLawn") }[label] || label);
  const classScore = (detection, label) => Number(detection?.probabilities?.[label] || 0);
  const wrapSigned = (value, limit) => {
    const span = 2 * limit;
    if (!Number.isFinite(value) || span <= 0) return 0;
    return ((((value + limit) % span) + span) % span) - limit;
  };
  const detectionText = (detection) => {
    if (!detection) return "";
    const pavement = classScore(detection, "pavement");
    const grass = classScore(detection, "gras") || Number(detection.grass_score || 0);
    const top = `${displayLabel(detection.label)} ${(100 * Number(detection.score || 0)).toFixed(1)}%`;
    const lookahead = detection.lookahead_grass_score === undefined ? "" : ` | V ${(100 * Number(detection.lookahead_grass_score || 0)).toFixed(1)}%`;
    return `${t("label.nonLawn")} ${(100 * pavement).toFixed(1)}% | ${t("label.lawn")} ${(100 * grass).toFixed(1)}%${lookahead} (${top})`;
  };
  const newestDetection = (...items) => {
    return items
      .filter((item) => item && Number(item.updated || 0) > 0)
      .sort((a, b) => Number(b.updated || 0) - Number(a.updated || 0))[0] || {};
  };

  const statusEl = $("#status");
  const profileSelect = $("#profileSelect");
  const profileStats = $("#profileStats");
  const trainingImageCounts = $("#trainingImageCounts");
  const imageGrid = $("#imageGrid");
  const toggleImagesBtn = $("#toggleImagesBtn");
  const trainState = $("#trainState");
  const testState = $("#testState");
  const robotMode = $("#robotMode");
  const robotStatus = $("#robotStatus");
  const robotProfile = $("#robotProfile");
  const robotCamera = $("#robotCamera");
  const robotBattery = $("#robotBattery");
  const robotDriveCurrent = $("#robotDriveCurrent");
  const robotMowerCurrent = $("#robotMowerCurrent");
  const robotCpu = $("#robotCpu");
  const robotCpuTemp = $("#robotCpuTemp");
  const robotRam = $("#robotRam");
  const robotDisk = $("#robotDisk");
  const robotLabel = $("#robotLabel");
  const robotLawn = $("#robotLawn");
  const robotCommand = $("#robotCommand");
  const robotJoystickState = $("#robotJoystickState");
  const robotDriveState = $("#robotDriveState");
  const robotError = $("#robotError");
  const sessionLog = $("#sessionLog");
  const plot = $("#metricPlot");
  const ctx = plot.getContext("2d");
  const robotScorePlot = $("#robotScorePlot");
  const robotScoreCtx = robotScorePlot.getContext("2d");
  const robotMotionPlot = $("#robotMotionPlot");
  const robotMotionCtx = robotMotionPlot.getContext("2d");
  const robotScorePlotToggle = $("#robotScorePlotToggle");
  const robotStopBtn = $("#robotStopBtn");
  const robotScoreHistory = [];
  const robotScoreWindowSeconds = 30;
  const robotHorizontalPositionPlotMaxPx = 300;
  const robotVerticalVelocityPlotMaxPxS = 120;
  let robotScoreLastUpdated = 0;
  let robotPlotPollInFlight = false;
  let robotPlotServerTime = 0;
  let robotPlotServerTimeSyncedAtMs = 0;
  const cropInputs = {
    enabled: $("#cropEnabled"),
    x: $("#cropX"),
    y: $("#cropY"),
    w: $("#cropW"),
    h: $("#cropH"),
  };
  const cameraControlInputs = {
    auto_exposure: $("#cameraAutoExposure"),
    dynamic_framerate: $("#cameraDynamicFramerate"),
    exposure_time: $("#cameraExposureTime"),
  };
  const cameraExposureValue = $("#cameraExposureValue");
  const cameraControlsState = $("#cameraControlsState");
  const cameraResolutionState = $("#cameraResolutionState");
  const joystick = {
    active: false,
    x: 0,
    y: 0,
    lastSent: 0,
    seq: 0,
    inFlight: 0,
    maxInFlight: 4,
    pending: null,
  };
  const roiDrag = {
    active: false,
    pointerId: null,
    startX: 0,
    startY: 0,
    crop: null,
  };
  const driveOptionInputs = {
    swap_sides: $("#driveSwapSides"),
    invert_left: $("#driveInvertLeft"),
    invert_right: $("#driveInvertRight"),
    pwm_ramp_rate: $("#driveRampRate"),
    mower_pwm_ramp_rate: $("#mowerRampRate"),
    mower_enabled: $("#mowerEnabled"),
    mower_pwm: $("#mowerPwm"),
  };
  const driveOptionLabels = {
    pwm_ramp_rate: $("#driveRampValue"),
    mower_pwm_ramp_rate: $("#mowerRampValue"),
    mower_pwm: $("#mowerPwmValue"),
  };
  const autoOptionInputs = {
    forward_speed: $("#autoForwardSpeed"),
    turn_speed: $("#autoTurnSpeed"),
    turn_reverse_seconds: $("#autoTurnReverseSeconds"),
    turn_stall_reverse_seconds: $("#autoTurnStallReverseSeconds"),
    turn_stall_min_seconds: $("#autoTurnStallMinSeconds"),
    turn_stall_min_position_delta: $("#autoTurnStallMinDelta"),
    turn_pause_seconds: $("#autoTurnPauseSeconds"),
    turn_stall_recovery_enabled: $("#autoTurnStallRecovery"),
    drive_stall_recovery_enabled: $("#autoDriveStallRecovery"),
    drive_stall_min_seconds: $("#autoDriveStallMinSeconds"),
    drive_stall_min_velocity: $("#autoDriveStallMinVelocity"),
    drive_stall_min_points: $("#autoDriveStallMinPoints"),
  };
  const autoOptionLabels = {
    forward_speed: $("#autoForwardValue"),
    turn_speed: $("#autoTurnValue"),
    turn_reverse_seconds: $("#autoTurnReverseValue"),
    turn_stall_reverse_seconds: $("#autoTurnStallReverseValue"),
    turn_stall_min_seconds: $("#autoTurnStallMinSecondsValue"),
    turn_stall_min_position_delta: $("#autoTurnStallMinDeltaValue"),
    turn_pause_seconds: $("#autoTurnPauseValue"),
    drive_stall_min_seconds: $("#autoDriveStallMinSecondsValue"),
    drive_stall_min_velocity: $("#autoDriveStallMinVelocityValue"),
    drive_stall_min_points: $("#autoDriveStallMinPointsValue"),
  };

  function autoOptionText(key, value) {
    const number = Number(value || 0);
    if (key === "forward_speed" || key === "turn_speed") return `${number}%`;
    if (key.endsWith("_seconds")) return `${number.toFixed(1)} s`;
    if (key === "turn_stall_min_position_delta") return `${number.toFixed(0)} px`;
    if (key === "drive_stall_min_velocity") return `${number.toFixed(0)} px/s`;
    if (key === "drive_stall_min_points") return `${number.toFixed(0)} pts`;
    return `${number}`;
  }

  function syncRobotPlotClock(serverTime) {
    const value = Number(serverTime || 0);
    if (value > 0) {
      robotPlotServerTime = value;
      robotPlotServerTimeSyncedAtMs = Date.now();
    }
  }

  function robotPlotNow() {
    if (robotPlotServerTime > 0 && robotPlotServerTimeSyncedAtMs > 0) {
      return robotPlotServerTime + ((Date.now() - robotPlotServerTimeSyncedAtMs) / 1000);
    }
    return Date.now() / 1000;
  }

  function selectedProfile() {
    return profileSelect.value || state?.selected_profile || "garten";
  }

  function setActive(container, attr, value) {
    container.querySelectorAll("button").forEach((btn) => {
      btn.classList.toggle("active", btn.dataset[attr] === value);
    });
  }

  document.querySelectorAll(".tabs button[data-tab]").forEach((btn) => {
    btn.onclick = () => {
      document.querySelectorAll(".tabs button[data-tab]").forEach((tab) => {
        tab.classList.toggle("active", tab === btn);
      });
      document.querySelectorAll(".tab-panel").forEach((panel) => {
        panel.classList.toggle("active", panel.id === btn.dataset.tab);
      });
      refreshCameraStreams();
    };
  });

  document.querySelectorAll(".robot-control-tabs button[data-robot-panel]").forEach((btn) => {
    btn.onclick = () => {
      document.querySelectorAll(".robot-control-tabs button[data-robot-panel]").forEach((tab) => {
        tab.classList.toggle("active", tab === btn);
      });
      document.querySelectorAll(".robot-control-panel").forEach((panel) => {
        panel.classList.toggle("active", panel.id === btn.dataset.robotPanel);
      });
    };
  });

  document.querySelectorAll(".stream-mode button[data-view]").forEach((btn) => {
    btn.onclick = () => {
      const group = btn.closest("[data-stream-mode]")?.dataset.streamMode;
      if (!group) return;
      streamViews[group] = btn.dataset.view || "rgb";
      btn.closest(".stream-mode").querySelectorAll("button[data-view]").forEach((item) => {
        item.classList.toggle("active", item === btn);
      });
      refreshCameraStreams();
    };
  });

  $("#labelButtons").addEventListener("click", (ev) => {
    const btn = ev.target.closest("button[data-label]");
    if (!btn) return;
    selectedLabel = btn.dataset.label;
    setActive($("#labelButtons"), "label", selectedLabel);
  });

  $("#splitButtons").addEventListener("click", (ev) => {
    const btn = ev.target.closest("button[data-split]");
    if (!btn) return;
    selectedSplit = btn.dataset.split;
    setActive($("#splitButtons"), "split", selectedSplit);
  });

  async function refresh() {
    const res = await fetch("/api/state");
    state = await res.json();
    render();
  }

  function render() {
    if (!state) return;
    syncRobotPlotClock(state.time);
    applyI18n();
    statusEl.textContent = state.training?.running ? t("status.trainingRunning") : t("status.ready");
    if (state.camera_error) statusEl.textContent += ` | ${t("camera.errorPrefix")}: ${state.camera_error}`;

    const old = profileSelect.value;
    profileSelect.innerHTML = "";
    for (const p of state.profiles || []) {
      const opt = document.createElement("option");
      opt.value = p.id;
      opt.textContent = p.name || p.id;
      profileSelect.appendChild(opt);
    }
    profileSelect.value = state.selected_profile || old || profileSelect.options[0]?.value || "";
    renderCameraResolutions();
    applyCameraSettings();
    renderCameraControls();

    const prof = (state.profiles || []).find((p) => p.id === selectedProfile());
    const c = prof?.counts || {};
    const crop = prof?.camera_crop || state.camera_crop || { enabled: false, x: 0, y: 0, w: 1, h: 1 };
    if (!cropDirty && (!document.activeElement || !Object.values(cropInputs).includes(document.activeElement))) {
      cropInputs.enabled.checked = !!crop.enabled;
      cropInputs.x.value = Math.round((crop.x || 0) * 100);
      cropInputs.y.value = Math.round((crop.y || 0) * 100);
      cropInputs.w.value = Math.round((crop.w || 1) * 100);
      cropInputs.h.value = Math.round((crop.h || 1) * 100);
    }
    renderRoiOverlay(cropDirty ? readCropInputs() : crop);
    profileStats.innerHTML = ["train", "valid"].map((split) => {
      const gras = c[split]?.gras || 0;
      const pavement = c[split]?.pavement || 0;
      return `<div class="stat"><b>${split}</b><br>${t("label.lawn")} ${gras}<br>${t("label.nonLawn")} ${pavement}</div>`;
    }).join("");
    const trainCount = Object.values(c.train || {}).reduce((sum, value) => sum + Number(value || 0), 0);
    const validCount = Object.values(c.valid || {}).reduce((sum, value) => sum + Number(value || 0), 0);
    trainingImageCounts.textContent = `train ${trainCount} / valid ${validCount}`;
    renderImagesCollapsedState();

    const training = state.training || {};
    const last = training.last || {};
    trainState.textContent = training.running
      ? t("training.active", {
        epoch: last.epoch || 0,
        epochs: last.epochs || "?",
        accuracy: (100 * (last.accuracy || 0)).toFixed(1),
        valAccuracy: (100 * (last.val_accuracy || 0)).toFixed(1),
      })
      : (training.error ? t("status.error", { message: training.error }) : t("training.inactive"));
    $("#trainBtn").disabled = !!training.running;

    const testing = state.testing || {};
    const tr = testing.last;
    testState.textContent = testing.running
      ? (tr ? detectionText(tr) : t("test.active"))
      : (testing.error ? t("status.error", { message: testing.error }) : t("test.stopped"));
    renderRobot(state.firmware || {});

    renderImages(state.images || []);
    renderLog(state.logs || []);
    drawPlot(training.metrics || []);
  }

  function renderRobot(firmware) {
    const detection = newestDetection(state.testing?.last, firmware.last);
    const command = firmware.command || detection.command || {};
    const js = state.joystick || {};
    const drive = state.drive || {};
    const options = drive.options || {};
    const autoOptions = firmware.auto_options || state.settings?.auto_options || {};
    const cameraStats = state.camera_stats || {};
    const system = state.system || {};
    const stopButtonKnown = Number(drive.stop_button_updated || 0) > 0;
    const stopButtonPressed = !!drive.stop_button_pressed;
    robotStopBtn.classList.toggle("hardware-stop-active", stopButtonPressed);
    robotStopBtn.classList.toggle("hardware-stop-unknown", !stopButtonKnown && !!drive.can_connected);
    robotStopBtn.title = stopButtonKnown
      ? (stopButtonPressed ? t("robot.stopButtonPressed") : t("robot.stopButtonReleased"))
      : t("robot.stopButtonUnknown");
    robotStopBtn.setAttribute("aria-pressed", stopButtonPressed ? "true" : "false");
    setText(robotMode, state.robot_state || (state.robot_auto_enabled ? "AUTO" : "IDLE"));
    setText(robotStatus, `${Number(state.classification_ms || 0).toFixed(0)} ms`);
    setText(robotProfile, firmware.profile || selectedProfile());
    setText(robotCamera, `${Number(cameraStats.fps || 0).toFixed(1)} fps`);
    const batteryVoltage = Number(drive.battery_voltage || 0);
    setText(robotBattery, batteryVoltage > 0 ? `${batteryVoltage.toFixed(1)} V` : "-");
    setText(robotDriveCurrent, `${formatAmp(drive.drive_current)} (L ${formatAmp(drive.left_current)} / R ${formatAmp(drive.right_current)})`);
    setText(robotMowerCurrent, formatAmp(drive.mower_current));
    setText(robotCpu, formatPercent(system.cpu_percent));
    setText(robotCpuTemp, formatTemperature(system.cpu_temperature_c));
    setText(robotRam, formatPercent(system.ram_percent));
    setText(robotDisk, formatPercent(system.disk_percent));
    setText(robotLabel, detection.label ? detectionText(detection) : "-");
    setText(robotLawn, detection.grass_score === undefined ? "-" : `${(100 * Number(detection.grass_score || 0)).toFixed(1)}%`);
    updateRobotScorePlot(detection);
    setText(robotCommand, command.state || "-");
    setText(robotJoystickState, `${Number(js.x || 0).toFixed(2)} / ${Number(js.y || 0).toFixed(2)}`);
    const canState = drive.can_connected ? "CAN" : t("drive.noCan");
    setText(robotDriveState, `${drive.enabled ? t("drive.active") : t("drive.inactive")} ${canState} L ${Number(drive.left || 0).toFixed(2)} R ${Number(drive.right || 0).toFixed(2)} M ${Number(drive.mower || 0).toFixed(2)}`);
    setText(robotError, firmware.error || "");
    if (!Object.values(driveOptionInputs).includes(document.activeElement)) {
      const rampRate = Math.round(100 * Number(options.pwm_ramp_rate ?? 1.0));
      const mowerRampRate = Math.round(100 * Number(options.mower_pwm_ramp_rate ?? 0.25));
      const mowerPwm = Math.round(100 * Number(options.mower_pwm ?? 1.0));
      driveOptionInputs.swap_sides.checked = !!options.swap_sides;
      driveOptionInputs.invert_left.checked = !!options.invert_left;
      driveOptionInputs.invert_right.checked = !!options.invert_right;
      driveOptionInputs.mower_enabled.checked = options.mower_enabled !== false;
      driveOptionInputs.mower_pwm.value = `${mowerPwm}`;
      driveOptionInputs.pwm_ramp_rate.value = `${rampRate}`;
      driveOptionInputs.mower_pwm_ramp_rate.value = `${mowerRampRate}`;
      driveOptionLabels.mower_pwm.textContent = `${mowerPwm}%`;
      driveOptionLabels.pwm_ramp_rate.textContent = rampRate <= 0 ? t("value.off") : `${rampRate}%/s`;
      driveOptionLabels.mower_pwm_ramp_rate.textContent = mowerRampRate <= 0 ? t("value.off") : `${mowerRampRate}%/s`;
    }
    if (!Object.values(autoOptionInputs).includes(document.activeElement)) {
      const forward = Math.round(100 * Number(autoOptions.forward_speed || 0.3));
      const turn = Math.round(100 * Number(autoOptions.turn_speed || 0.3));
      const turnReverse = Number(autoOptions.turn_reverse_seconds || 0.0);
      const turnStallReverse = Number(autoOptions.turn_stall_reverse_seconds ?? 2.0);
      const turnStallMinSeconds = Number(autoOptions.turn_stall_min_seconds ?? 2.5);
      const turnStallMinDelta = Number(autoOptions.turn_stall_min_position_delta ?? 15);
      const turnPause = Number(autoOptions.turn_pause_seconds || 2.0);
      const driveStallMinSeconds = Number(autoOptions.drive_stall_min_seconds ?? 2.5);
      const driveStallMinVelocity = Number(autoOptions.drive_stall_min_velocity ?? 12);
      const driveStallMinPoints = Number(autoOptions.drive_stall_min_points ?? 40);
      autoOptionInputs.forward_speed.value = `${forward}`;
      autoOptionInputs.turn_speed.value = `${turn}`;
      autoOptionInputs.turn_reverse_seconds.value = `${turnReverse.toFixed(1)}`;
      autoOptionInputs.turn_stall_reverse_seconds.value = `${turnStallReverse.toFixed(1)}`;
      autoOptionInputs.turn_stall_min_seconds.value = `${turnStallMinSeconds.toFixed(1)}`;
      autoOptionInputs.turn_stall_min_position_delta.value = `${turnStallMinDelta.toFixed(0)}`;
      autoOptionInputs.turn_pause_seconds.value = `${turnPause.toFixed(1)}`;
      autoOptionInputs.turn_stall_recovery_enabled.checked = autoOptions.turn_stall_recovery_enabled !== false;
      autoOptionInputs.drive_stall_recovery_enabled.checked = autoOptions.drive_stall_recovery_enabled !== false;
      autoOptionInputs.drive_stall_min_seconds.value = `${driveStallMinSeconds.toFixed(1)}`;
      autoOptionInputs.drive_stall_min_velocity.value = `${driveStallMinVelocity.toFixed(0)}`;
      autoOptionInputs.drive_stall_min_points.value = `${driveStallMinPoints.toFixed(0)}`;
      autoOptionLabels.forward_speed.textContent = autoOptionText("forward_speed", forward);
      autoOptionLabels.turn_speed.textContent = autoOptionText("turn_speed", turn);
      autoOptionLabels.turn_reverse_seconds.textContent = autoOptionText("turn_reverse_seconds", turnReverse);
      autoOptionLabels.turn_stall_reverse_seconds.textContent = autoOptionText("turn_stall_reverse_seconds", turnStallReverse);
      autoOptionLabels.turn_stall_min_seconds.textContent = autoOptionText("turn_stall_min_seconds", turnStallMinSeconds);
      autoOptionLabels.turn_stall_min_position_delta.textContent = autoOptionText("turn_stall_min_position_delta", turnStallMinDelta);
      autoOptionLabels.turn_pause_seconds.textContent = autoOptionText("turn_pause_seconds", turnPause);
      autoOptionLabels.drive_stall_min_seconds.textContent = autoOptionText("drive_stall_min_seconds", driveStallMinSeconds);
      autoOptionLabels.drive_stall_min_velocity.textContent = autoOptionText("drive_stall_min_velocity", driveStallMinVelocity);
      autoOptionLabels.drive_stall_min_points.textContent = autoOptionText("drive_stall_min_points", driveStallMinPoints);
    }
  }

  function formatPercent(value) {
    const number = Number(value);
    return Number.isFinite(number) ? `${number.toFixed(0)}%` : "-";
  }

  function formatTemperature(value) {
    const number = Number(value);
    return Number.isFinite(number) ? `${number.toFixed(1)} °C` : "-";
  }

  function formatAmp(value) {
    const number = Number(value);
    return Number.isFinite(number) ? `${number.toFixed(1)} A` : "-";
  }

  function setText(el, value) {
    if (el) el.textContent = value;
  }

  function imageContentRect(img) {
    const rect = img.getBoundingClientRect();
    const naturalW = img.naturalWidth || rect.width;
    const naturalH = img.naturalHeight || rect.height;
    const imgRatio = naturalW / Math.max(1, naturalH);
    const boxRatio = rect.width / Math.max(1, rect.height);
    let width = rect.width;
    let height = rect.height;
    let left = 0;
    let top = 0;
    if (boxRatio > imgRatio) {
      width = rect.height * imgRatio;
      left = (rect.width - width) / 2;
    } else {
      height = rect.width / imgRatio;
      top = (rect.height - height) / 2;
    }
    return { left, top, width, height };
  }

  function renderRoiOverlay(crop) {
    const box = $("#roiDragBox");
    const img = $("#cameraStream");
    crop = crop || readCropInputs();
    if (!crop.enabled) {
      box.style.display = "none";
      return;
    }
    const r = imageContentRect(img);
    box.style.display = "block";
    box.style.left = `${r.left + crop.x * r.width}px`;
    box.style.top = `${r.top + crop.y * r.height}px`;
    box.style.width = `${crop.w * r.width}px`;
    box.style.height = `${crop.h * r.height}px`;
  }

  function writeCropInputs(crop) {
    cropInputs.enabled.checked = !!crop.enabled;
    cropInputs.x.value = Math.round(crop.x * 100);
    cropInputs.y.value = Math.round(crop.y * 100);
    cropInputs.w.value = Math.round(crop.w * 100);
    cropInputs.h.value = Math.round(crop.h * 100);
  }

  function setJoystickVisual(x, y) {
    const base = $("#robotJoystick");
    const knob = $("#joystickKnob");
    const limitX = (base.clientWidth - knob.clientWidth) / 2 - 8;
    const limitY = (base.clientHeight - knob.clientHeight) / 2 - 8;
    knob.style.transform = `translate(calc(-50% + ${x * limitX}px), calc(-50% + ${y * limitY}px))`;
  }

  function queueJoystickSend(x, y, active, force = false) {
    const now = Date.now();
    if (!force && now - joystick.lastSent < 90) return;
    joystick.lastSent = now;
    const message = {
      x,
      y,
      active,
      seq: ++joystick.seq,
      client_time_ms: now,
    };
    if (force && !active) {
      sendJoystickNow(message);
      return;
    }
    sendOrQueueJoystick(message);
  }

  async function sendJoystickNow(message) {
    try {
      await api("/api/robot/joystick", message);
    } catch (err) {
      robotError.textContent = err.message;
    }
  }

  function sendOrQueueJoystick(message) {
    if (joystick.inFlight >= joystick.maxInFlight) {
      joystick.pending = message;
      return;
    }
    joystick.inFlight += 1;
    sendJoystickNow(message).finally(() => {
      joystick.inFlight = Math.max(0, joystick.inFlight - 1);
      if (!joystick.pending) return;
      const next = joystick.pending;
      joystick.pending = null;
      sendOrQueueJoystick(next);
    });
  }

  function updateJoystickFromPointer(ev) {
    const base = $("#robotJoystick");
    const rect = base.getBoundingClientRect();
    const cx = rect.left + rect.width / 2;
    const cy = rect.top + rect.height / 2;
    let x = (ev.clientX - cx) / (rect.width / 2);
    let y = (ev.clientY - cy) / (rect.height / 2);
    x = Math.max(-1, Math.min(1, x));
    y = Math.max(-1, Math.min(1, y));
    joystick.x = x;
    joystick.y = y;
    setJoystickVisual(x, y);
    robotJoystickState.textContent = `${x.toFixed(2)} / ${y.toFixed(2)}`;
    queueJoystickSend(x, y, true);
  }

  $("#robotJoystick").addEventListener("pointerdown", (ev) => {
    joystick.active = true;
    $("#robotJoystick").setPointerCapture(ev.pointerId);
    updateJoystickFromPointer(ev);
    queueJoystickSend(joystick.x, joystick.y, true, true);
  });

  $("#robotJoystick").addEventListener("pointermove", (ev) => {
    if (!joystick.active) return;
    updateJoystickFromPointer(ev);
  });

  function releaseJoystick(ev) {
    if (!joystick.active) return;
    joystick.active = false;
    joystick.x = 0;
    joystick.y = 0;
    setJoystickVisual(0, 0);
    robotJoystickState.textContent = "0.00 / 0.00";
    if (ev?.pointerId !== undefined && $("#robotJoystick").hasPointerCapture(ev.pointerId)) {
      $("#robotJoystick").releasePointerCapture(ev.pointerId);
    }
    queueJoystickSend(0, 0, false, true);
  }

  $("#robotJoystick").addEventListener("pointerup", releaseJoystick);
  $("#robotJoystick").addEventListener("pointercancel", releaseJoystick);
  $("#robotJoystick").addEventListener("lostpointercapture", releaseJoystick);

  setInterval(() => {
    if (!joystick.active) return;
    queueJoystickSend(joystick.x, joystick.y, true, true);
  }, 250);

  function formatTime(ts) {
    const d = new Date(Number(ts || 0) * 1000);
    if (!Number.isFinite(d.getTime())) return "--:--:--";
    return d.toLocaleTimeString(currentLanguage === "de" ? "de-DE" : "en-US", { hour12: false });
  }

  function renderLog(logs) {
    const formatFieldValue = (value) => {
      if (typeof value === "number") {
        return Number.isInteger(value) ? `${value}` : `${Number(value).toFixed(3)}`;
      }
      if (typeof value === "boolean") return value ? "true" : "false";
      if (typeof value === "object") return JSON.stringify(value);
      return `${value}`;
    };
    const lines = logs.map((entry) => {
      const fields = [];
      for (const [key, value] of Object.entries(entry)) {
        if (["time", "kind", "message"].includes(key)) continue;
        if (value === undefined || value === null || value === "") continue;
        fields.push(`${key}=${formatFieldValue(value)}`);
      }
      const suffix = fields.length ? ` | ${fields.join(" ")}` : "";
      return `[${formatTime(entry.time)}] ${entry.kind || "info"}: ${entry.message || ""}${suffix}`;
    });
    const text = lines.join("\n");
    const atBottom = sessionLog.scrollTop + sessionLog.clientHeight >= sessionLog.scrollHeight - 10;
    sessionLog.textContent = text;
    if (atBottom) sessionLog.scrollTop = sessionLog.scrollHeight;
  }

  function renderImages(images) {
    const nextKey = images.map((img) => `${img.path}|${img.split}|${img.label}|${img.mtime}`).join(";");
    if (nextKey === imageListKey) return;
    imageListKey = nextKey;
    imageGrid.innerHTML = "";
    for (const img of images) {
      const el = document.createElement("article");
      el.className = "thumb";
      el.innerHTML = `
        <div class="thumb-image">
          <img src="${img.url}" alt="">
          <div class="badge-row">
            <span class="badge ${img.label}">${displayLabel(img.label)}</span>
            <span class="badge ${img.split}">${img.split}</span>
          </div>
        </div>
        <div class="thumb-body">
          <div class="thumb-actions">
            <button data-act="toggle-label">${t("images.toggleLabel")}</button>
            <button data-act="toggle-split">${t("images.toggleSplit")}</button>
            <button class="danger" data-act="delete">${t("images.delete")}</button>
          </div>
        </div>`;
      el.querySelector('[data-act="toggle-label"]').onclick = async () => {
        await api("/api/move_image", {
          profile: selectedProfile(),
          path: img.path,
          split: img.split,
          label: img.label === "gras" ? "pavement" : "gras",
        });
        await refresh();
      };
      el.querySelector('[data-act="toggle-split"]').onclick = async () => {
        await api("/api/move_image", {
          profile: selectedProfile(),
          path: img.path,
          split: img.split === "train" ? "valid" : "train",
          label: img.label,
        });
        await refresh();
      };
      el.querySelector('[data-act="delete"]').onclick = async () => {
        const name = img.name || img.path;
        if (!window.confirm(t("images.confirmDelete", { name }))) return;
        await api("/api/delete_image", { profile: selectedProfile(), path: img.path });
        await refresh();
      };
      imageGrid.appendChild(el);
    }
  }

  function renderImagesCollapsedState() {
    imageGrid.classList.toggle("collapsed", imagesCollapsed);
    toggleImagesBtn.textContent = imagesCollapsed ? t("images.expand") : t("images.collapse");
    toggleImagesBtn.setAttribute("aria-expanded", imagesCollapsed ? "false" : "true");
  }

  function drawPlot(metrics) {
    const w = plot.width;
    const h = plot.height;
    const left = 44;
    const right = w - 14;
    const top = 24;
    const bottom = h - 32;
    ctx.clearRect(0, 0, w, h);
    ctx.fillStyle = "#fff";
    ctx.fillRect(0, 0, w, h);
    ctx.font = "11px system-ui";
    ctx.textBaseline = "middle";
    ctx.textAlign = "right";
    ctx.strokeStyle = "#d9e0dc";
    ctx.lineWidth = 1;
    for (let i = 0; i <= 4; i++) {
      const value = 1 - i * 0.25;
      const y = top + i * ((bottom - top) / 4);
      ctx.beginPath();
      ctx.moveTo(left, y);
      ctx.lineTo(right, y);
      ctx.stroke();
      ctx.fillStyle = "#60706a";
      ctx.fillText(value.toFixed(2), left - 7, y);
    }
    ctx.strokeStyle = "#87948f";
    ctx.beginPath();
    ctx.moveTo(left, top);
    ctx.lineTo(left, bottom);
    ctx.lineTo(right, bottom);
    ctx.stroke();
    ctx.fillStyle = "#60706a";
    ctx.textAlign = "left";
    ctx.fillText("accuracy / loss", left, 12);
    if (!metrics.length) {
      ctx.fillText(t("metrics.noTraining"), left, 118);
      return;
    }
    const maxLoss = Math.max(1, ...metrics.flatMap((m) => [Number(m.loss || 0), Number(m.val_loss || 0)]));
    const xFor = (i) => left + i * ((right - left) / Math.max(1, metrics.length - 1));
    const yAcc = (v) => bottom - Math.max(0, Math.min(1, v)) * (bottom - top);
    const yLoss = (v) => bottom - Math.max(0, Math.min(1, v / maxLoss)) * (bottom - top);
    const line = (key, color, yFor) => {
      ctx.strokeStyle = color;
      ctx.lineWidth = 2;
      ctx.beginPath();
      metrics.forEach((m, i) => {
        const x = xFor(i);
        const y = yFor(Number(m[key] || 0));
        if (i === 0) ctx.moveTo(x, y);
        else ctx.lineTo(x, y);
      });
      ctx.stroke();
    };
    line("accuracy", "#2d7d46", yAcc);
    line("val_accuracy", "#245f9f", yAcc);
    line("loss", "#9a6a18", yLoss);
    line("val_loss", "#b83d45", yLoss);
    ctx.textAlign = "center";
    ctx.fillStyle = "#60706a";
    ctx.fillText(t("metrics.epoch"), (left + right) / 2, h - 10);
    const firstEpoch = metrics[0]?.epoch || 1;
    const lastEpoch = metrics[metrics.length - 1]?.epoch || metrics.length;
    ctx.fillText(String(firstEpoch), left, bottom + 14);
    ctx.fillText(String(lastEpoch), right, bottom + 14);
    ctx.textAlign = "right";
    ctx.fillText(`loss max ${maxLoss.toFixed(2)}`, right, 12);
    ctx.textAlign = "left";
    ctx.fillStyle = "#2d7d46";
    ctx.fillText("acc", left + 104, 12);
    ctx.fillStyle = "#245f9f";
    ctx.fillText("val acc", left + 132, 12);
    ctx.fillStyle = "#9a6a18";
    ctx.fillText("loss", left + 184, 12);
    ctx.fillStyle = "#b83d45";
    ctx.fillText("val loss", left + 222, 12);
  }

  function updateRobotScorePlot(detection) {
    if (detection?.updated && detection.updated !== robotScoreLastUpdated) {
      const lawn = Number(detection.grass_score ?? detection.lawn_score ?? 0);
      const nonLawn = Number(detection.probabilities?.pavement ?? (1 - lawn));
      const horizontalPositionPx = Number(detection.motion?.position_dx ?? 0);
      const verticalVelocityPxS = Number(detection.motion?.vertical_velocity_px_s ?? 0);
      robotScoreHistory.push({
        time: Number(detection.updated),
        lawn: Math.max(0, Math.min(1, lawn)),
        nonLawn: Math.max(0, Math.min(1, nonLawn)),
        horizontalPosition: wrapSigned(horizontalPositionPx, robotHorizontalPositionPlotMaxPx) / robotHorizontalPositionPlotMaxPx,
        horizontalPositionPx,
        verticalVelocity: Math.max(-1, Math.min(1, verticalVelocityPxS / robotVerticalVelocityPlotMaxPxS)),
        verticalVelocityPxS,
      });
      robotScoreLastUpdated = detection.updated;
    }
    const newest = robotPlotNow();
    while (robotScoreHistory.length && robotScoreHistory[0].time < newest - robotScoreWindowSeconds) {
      robotScoreHistory.shift();
    }
    drawRobotScorePlot();
  }

  async function refreshRobotScorePlot() {
    if (robotPlotPollInFlight) return;
    robotPlotPollInFlight = true;
    try {
      const res = await fetch("/api/robot/plot_state", { cache: "no-store" });
      if (!res.ok) throw new Error(`plot state ${res.status}`);
      const plotState = await res.json();
      syncRobotPlotClock(plotState.time);
      const detection = newestDetection(plotState.testing_last, plotState.firmware_last);
      updateRobotScorePlot(detection);
      if (plotState.classification_ms !== undefined) {
        setText(robotStatus, `${Number(plotState.classification_ms || 0).toFixed(0)} ms`);
      }
      const cameraStats = plotState.camera_stats || {};
      setText(robotCamera, `${Number(cameraStats.fps || 0).toFixed(1)} fps`);
    } catch (err) {
      drawRobotScorePlot();
    } finally {
      robotPlotPollInFlight = false;
    }
  }

  function drawRobotScorePlot() {
    const hidden = !robotScorePlotToggle.checked;
    robotScorePlot.hidden = hidden;
    robotMotionPlot.hidden = hidden;
    if (hidden) return;
    drawRobotClassificationPlot();
    drawRobotMotionPlot();
  }

  function drawRobotClassificationPlot() {
    const w = robotScorePlot.width;
    const h = robotScorePlot.height;
    const left = 42;
    const right = w - 14;
    const top = 18;
    const bottom = h - 24;
    robotScoreCtx.clearRect(0, 0, w, h);
    robotScoreCtx.fillStyle = "#fff";
    robotScoreCtx.fillRect(0, 0, w, h);
    robotScoreCtx.font = "11px system-ui";
    robotScoreCtx.textBaseline = "middle";
    robotScoreCtx.textAlign = "right";
    robotScoreCtx.strokeStyle = "#d9e0dc";
    robotScoreCtx.lineWidth = 1;
    for (let i = 0; i <= 4; i++) {
      const value = 1 - i * 0.25;
      const y = top + i * ((bottom - top) / 4);
      robotScoreCtx.beginPath();
      robotScoreCtx.moveTo(left, y);
      robotScoreCtx.lineTo(right, y);
      robotScoreCtx.stroke();
      robotScoreCtx.fillStyle = "#60706a";
      robotScoreCtx.fillText(`${Math.round(value * 100)}%`, left - 7, y);
    }
    robotScoreCtx.strokeStyle = "#87948f";
    robotScoreCtx.beginPath();
    robotScoreCtx.moveTo(left, top);
    robotScoreCtx.lineTo(left, bottom);
    robotScoreCtx.lineTo(right, bottom);
    robotScoreCtx.stroke();
    robotScoreCtx.textAlign = "left";
    robotScoreCtx.fillStyle = "#60706a";
    robotScoreCtx.fillText(t("metrics.robotClassification"), left, 10);
    if (!robotScoreHistory.length) {
      robotScoreCtx.fillText(t("metrics.noValues"), left, h / 2);
      return;
    }
    const newest = robotPlotNow();
    const oldest = newest - robotScoreWindowSeconds;
    const span = robotScoreWindowSeconds;
    const xFor = (point) => left + ((point.time - oldest) / span) * (right - left);
    const yFor = (v) => bottom - v * (bottom - top);
    const line = (key, color) => {
      robotScoreCtx.strokeStyle = color;
      robotScoreCtx.lineWidth = 2;
      robotScoreCtx.beginPath();
      robotScoreHistory.forEach((point, i) => {
        const x = xFor(point);
        const y = yFor(point[key]);
        if (i === 0) robotScoreCtx.moveTo(x, y);
        else robotScoreCtx.lineTo(x, y);
      });
      robotScoreCtx.stroke();
      robotScoreCtx.fillStyle = color;
      robotScoreHistory.forEach((point) => {
        const x = xFor(point);
        const y = yFor(point[key]);
        robotScoreCtx.beginPath();
        robotScoreCtx.arc(x, y, 2.5, 0, Math.PI * 2);
        robotScoreCtx.fill();
      });
    };
    line("lawn", "#2d7d46");
    line("nonLawn", "#b83d45");
    robotScoreCtx.textAlign = "left";
    robotScoreCtx.fillStyle = "#2d7d46";
    robotScoreCtx.fillText("Lawn", left + 110, 10);
    robotScoreCtx.fillStyle = "#b83d45";
    robotScoreCtx.fillText("Non-lawn", left + 152, 10);
    const last = robotScoreHistory[robotScoreHistory.length - 1];
    robotScoreCtx.textAlign = "right";
    robotScoreCtx.fillStyle = "#60706a";
    robotScoreCtx.fillText(`L ${(last.lawn * 100).toFixed(1)}%  N ${(last.nonLawn * 100).toFixed(1)}%`, right, 10);
  }

  function drawRobotMotionPlot() {
    const w = robotMotionPlot.width;
    const h = robotMotionPlot.height;
    const left = 42;
    const right = w - 14;
    const top = 18;
    const bottom = h - 24;
    robotMotionCtx.clearRect(0, 0, w, h);
    robotMotionCtx.fillStyle = "#fff";
    robotMotionCtx.fillRect(0, 0, w, h);
    robotMotionCtx.font = "11px system-ui";
    robotMotionCtx.textBaseline = "middle";
    robotMotionCtx.textAlign = "right";
    robotMotionCtx.strokeStyle = "#d9e0dc";
    robotMotionCtx.lineWidth = 1;
    for (let i = 0; i <= 4; i++) {
      const value = 1 - i * 0.5;
      const y = top + i * ((bottom - top) / 4);
      robotMotionCtx.beginPath();
      robotMotionCtx.moveTo(left, y);
      robotMotionCtx.lineTo(right, y);
      robotMotionCtx.stroke();
      robotMotionCtx.fillStyle = "#60706a";
      robotMotionCtx.fillText(`${value.toFixed(1)}`, left - 7, y);
    }
    robotMotionCtx.strokeStyle = "#87948f";
    robotMotionCtx.beginPath();
    robotMotionCtx.moveTo(left, top);
    robotMotionCtx.lineTo(left, bottom);
    robotMotionCtx.lineTo(right, bottom);
    robotMotionCtx.stroke();
    robotMotionCtx.textAlign = "left";
    robotMotionCtx.fillStyle = "#60706a";
    robotMotionCtx.fillText(t("metrics.robotMotion"), left, 10);
    if (!robotScoreHistory.length) {
      robotMotionCtx.fillText(t("metrics.noValues"), left, h / 2);
      return;
    }
    const newest = robotPlotNow();
    const oldest = newest - robotScoreWindowSeconds;
    const span = robotScoreWindowSeconds;
    const xFor = (point) => left + ((point.time - oldest) / span) * (right - left);
    const yForSigned = (v) => top + ((1 - Math.max(-1, Math.min(1, v))) / 2) * (bottom - top);
    const wrappedPosition = (point) => wrapSigned(point.horizontalPositionPx, robotHorizontalPositionPlotMaxPx) / robotHorizontalPositionPlotMaxPx;
    robotMotionCtx.strokeStyle = "#c4cbc7";
    robotMotionCtx.setLineDash([4, 4]);
    robotMotionCtx.beginPath();
    robotMotionCtx.moveTo(left, yForSigned(0));
    robotMotionCtx.lineTo(right, yForSigned(0));
    robotMotionCtx.stroke();
    robotMotionCtx.setLineDash([]);
    robotMotionCtx.strokeStyle = "#7b4cc2";
    robotMotionCtx.lineWidth = 2;
    robotMotionCtx.beginPath();
    robotScoreHistory.forEach((point, i) => {
      const x = xFor(point);
      const current = wrappedPosition(point);
      const previous = i > 0 ? wrappedPosition(robotScoreHistory[i - 1]) : current;
      const y = yForSigned(current);
      if (i === 0 || Math.abs(current - previous) > 1.0) robotMotionCtx.moveTo(x, y);
      else robotMotionCtx.lineTo(x, y);
    });
    robotMotionCtx.stroke();
    robotMotionCtx.fillStyle = "#7b4cc2";
    robotScoreHistory.forEach((point) => {
      const x = xFor(point);
      const y = yForSigned(wrappedPosition(point));
      robotMotionCtx.beginPath();
      robotMotionCtx.arc(x, y, 2.5, 0, Math.PI * 2);
      robotMotionCtx.fill();
    });
    robotMotionCtx.strokeStyle = "#c46a1a";
    robotMotionCtx.lineWidth = 2;
    robotMotionCtx.beginPath();
    robotScoreHistory.forEach((point, i) => {
      const x = xFor(point);
      const y = yForSigned(point.verticalVelocity);
      if (i === 0) robotMotionCtx.moveTo(x, y);
      else robotMotionCtx.lineTo(x, y);
    });
    robotMotionCtx.stroke();
    robotMotionCtx.fillStyle = "#c46a1a";
    robotScoreHistory.forEach((point) => {
      const x = xFor(point);
      const y = yForSigned(point.verticalVelocity);
      robotMotionCtx.beginPath();
      robotMotionCtx.arc(x, y, 2.5, 0, Math.PI * 2);
      robotMotionCtx.fill();
    });
    robotMotionCtx.textAlign = "left";
    robotMotionCtx.fillStyle = "#7b4cc2";
    robotMotionCtx.fillText(`H-Pos +/-${robotHorizontalPositionPlotMaxPx}px`, left + 110, 10);
    robotMotionCtx.fillStyle = "#c46a1a";
    robotMotionCtx.fillText(`V +/-${robotVerticalVelocityPlotMaxPxS}px/s`, left + 232, 10);
    const last = robotScoreHistory[robotScoreHistory.length - 1];
    robotMotionCtx.textAlign = "right";
    robotMotionCtx.fillStyle = "#60706a";
    robotMotionCtx.fillText(`H ${last.horizontalPositionPx.toFixed(1)}px  V ${last.verticalVelocityPxS.toFixed(1)}px/s`, right, 10);
  }

  robotScorePlotToggle.onchange = drawRobotScorePlot;

  $("#createProfile").onclick = async () => {
    const name = $("#profileName").value.trim();
    if (!name) return;
    await api("/api/profiles", { name });
    $("#profileName").value = "";
    await refresh();
  };

  profileSelect.onchange = async () => {
    cropDirty = false;
    await api("/api/select_profile", { profile: selectedProfile() });
    await refresh();
  };

  $("#captureBtn").onclick = async () => {
    await api("/api/capture_image", {
      profile: selectedProfile(),
      split: selectedSplit,
      label: selectedLabel,
      camera: cameraIndex(),
      resolution: cameraResolution(),
    });
    await refresh();
  };

  function cameraIndex() {
    const value = ($("#cameraIndex").value || "auto").trim();
    return value || "auto";
  }

  function cameraResolution() {
    return $("#cameraResolution").value || state?.settings?.camera?.resolution || "1280x720";
  }

  function formatResolution(value) {
    const match = String(value || "").match(/^(\d+)x(\d+)$/);
    return match ? `${match[1]} x ${match[2]}` : value;
  }

  function renderCameraResolutions() {
    const select = $("#cameraResolution");
    const info = state?.camera_resolutions || {};
    const resolutions = Array.isArray(info.resolutions) ? info.resolutions : [];
    const ranges = Array.isArray(info.ranges) ? info.ranges : [];
    const key = JSON.stringify({
      resolutions: resolutions.map((item) => [item.value, item.label]),
      ranges,
      error: info.error || "",
    });

    if (document.activeElement !== select && key !== cameraResolutionOptionsKey) {
      const previous = select.value;
      select.innerHTML = "";

      for (const item of resolutions) {
        const opt = document.createElement("option");
        opt.value = item.value;
        opt.textContent = item.label || formatResolution(item.value);
        select.appendChild(opt);
      }

      if (!resolutions.length) {
        const opt = document.createElement("option");
        opt.value = "";
        opt.textContent = t("camera.resolutionNone");
        select.appendChild(opt);
      }
      cameraResolutionOptionsKey = key;
      if (previous) select.value = previous;
    }

    const values = new Set(resolutions.map((item) => item.value));
    const saved = state?.settings?.camera?.resolution || "1280x720";
    const wanted = cameraSettingsSaving ? select.value : saved;
    if (values.has(wanted)) {
      if (document.activeElement !== select) select.value = wanted;
      select.disabled = false;
    } else if (resolutions.length) {
      if (document.activeElement !== select && !values.has(select.value)) select.value = resolutions[0].value;
      select.disabled = false;
    } else {
      if (document.activeElement !== select) select.value = "";
      select.disabled = true;
    }

    const rangeText = ranges.length
      ? t("camera.resolutionRange", {
        ranges: ranges.map((range) => `${formatResolution(range.min?.value)} ${currentLanguage === "de" ? "bis" : "to"} ${formatResolution(range.max?.value)}`).join(", "),
      })
      : "";
    cameraResolutionState.textContent = resolutions.length
      ? `${t("camera.resolutionsFound", { count: resolutions.length })}${rangeText ? ` | ${rangeText}` : ""}`
      : (rangeText || info.error || t("camera.resolutionUnavailable"));
  }

  function applyCameraSettings() {
    if (cameraSettingsApplied) return;
    const camera = state?.settings?.camera || {};
    if (camera.index !== undefined) $("#cameraIndex").value = camera.index;
    if (camera.resolution !== undefined && [...$("#cameraResolution").options].some((opt) => opt.value === camera.resolution)) {
      $("#cameraResolution").value = camera.resolution;
    }
    cameraSettingsApplied = true;
    refreshCameraStreams();
  }

  function renderCameraControls() {
    const controls = state?.camera_controls || {};
    const autoControl = controls.auto_control;
    const exposureControl = controls.exposure_control;
    const dynamicControl = controls.dynamic_framerate_control;
    cameraControlInputs.auto_exposure.disabled = !autoControl;
    cameraControlInputs.dynamic_framerate.disabled = !dynamicControl;
    cameraControlInputs.exposure_time.disabled = !exposureControl || !!controls.auto_enabled;
    if (autoControl && document.activeElement !== cameraControlInputs.auto_exposure) {
      cameraControlInputs.auto_exposure.checked = !!controls.auto_enabled;
    }
    if (dynamicControl && document.activeElement !== cameraControlInputs.dynamic_framerate) {
      cameraControlInputs.dynamic_framerate.checked = !!controls.dynamic_framerate_enabled;
    }
    if (exposureControl) {
      cameraControlInputs.exposure_time.min = exposureControl.min ?? 1;
      cameraControlInputs.exposure_time.max = exposureControl.max ?? 5000;
      cameraControlInputs.exposure_time.step = exposureControl.step ?? 1;
      if (document.activeElement !== cameraControlInputs.exposure_time) {
        cameraControlInputs.exposure_time.value = exposureControl.value ?? exposureControl.default ?? 1;
      }
      cameraExposureValue.textContent = `${cameraControlInputs.exposure_time.value}`;
    } else {
      cameraExposureValue.textContent = "-";
    }
    cameraControlsState.textContent = controls.available
      ? (controls.auto_enabled ? t("camera.controlsAuto") : t("camera.controlsManual"))
      : (controls.error || t("camera.controlsUnavailable"));
  }

  async function saveCameraSettings() {
    cameraSettingsSaving = true;
    try {
      await api("/api/camera_settings", {
        camera: cameraIndex(),
        resolution: cameraResolution(),
      });
      await refresh();
      refreshCameraStreams();
    } finally {
      cameraSettingsSaving = false;
    }
  }

  function refreshCameraStreams() {
    if (!state) return;
    const camera = cameraIndex();
    const resolution = cameraResolution();
    const trainingActive = $("#trainingTab").classList.contains("active");
    const robotActive = $("#robotTab").classList.contains("active");
    const testRunning = !!state?.testing?.running;
    const cameraUrl = `/api/camera.mjpg?camera=${encodeURIComponent(camera)}&resolution=${encodeURIComponent(resolution)}&view=${encodeURIComponent(streamViews.training)}&t=${Date.now()}`;
    const testUrl = (view) => `/api/test.mjpg?camera=${encodeURIComponent(camera)}&resolution=${encodeURIComponent(resolution)}&view=${encodeURIComponent(view)}&t=${Date.now()}`;
    setStreamSource($("#cameraStream"), trainingActive ? cameraUrl : "");
    setStreamSource($("#testStream"), trainingActive && testRunning ? testUrl("rgb") : "");
    setStreamSource($("#robotCameraStream"), robotActive ? testUrl(streamViews.robot) : "");
  }

  function setStreamSource(img, url) {
    if (!url) {
      img.removeAttribute("src");
      return;
    }
    if (img.getAttribute("src") !== url) img.src = url;
  }

  $("#cameraIndex").onchange = saveCameraSettings;
  $("#cameraResolution").onchange = saveCameraSettings;

  async function saveCameraControls() {
    await api("/api/camera_controls", {
      auto_exposure: cameraControlInputs.auto_exposure.checked,
      dynamic_framerate: cameraControlInputs.dynamic_framerate.checked,
      exposure_time: Number(cameraControlInputs.exposure_time.value || 0),
    });
    await refresh();
  }

  cameraControlInputs.auto_exposure.onchange = saveCameraControls;
  cameraControlInputs.dynamic_framerate.onchange = saveCameraControls;
  cameraControlInputs.exposure_time.oninput = () => {
    cameraExposureValue.textContent = `${cameraControlInputs.exposure_time.value}`;
  };
  cameraControlInputs.exposure_time.onchange = saveCameraControls;

  function readCropInputs() {
    let x = Number(cropInputs.x.value || 0) / 100;
    let y = Number(cropInputs.y.value || 0) / 100;
    let w = Number(cropInputs.w.value || 100) / 100;
    let h = Number(cropInputs.h.value || 100) / 100;
    x = Math.max(0, Math.min(0.95, x));
    y = Math.max(0, Math.min(0.95, y));
    w = Math.max(0.05, Math.min(1 - x, w));
    h = Math.max(0.05, Math.min(1 - y, h));
    return { enabled: cropInputs.enabled.checked, x, y, w, h };
  }

  async function saveCrop(crop) {
    await api("/api/camera_crop", { profile: selectedProfile(), crop });
    cropDirty = false;
    refreshCameraStreams();
    await refresh();
  }

  $("#saveCropBtn").onclick = async () => {
    await saveCrop(readCropInputs());
  };

  $("#resetCropBtn").onclick = async () => {
    await saveCrop({ enabled: true, x: 0.25, y: 0.5, w: 0.5, h: 0.5 });
  };

  $("#cameraStream").onload = () => renderRoiOverlay(readCropInputs());
  window.addEventListener("resize", () => renderRoiOverlay(readCropInputs()));

  Object.values(cropInputs).forEach((input) => {
    input.addEventListener("input", () => {
      cropDirty = true;
      renderRoiOverlay(readCropInputs());
    });
    input.addEventListener("change", () => {
      cropDirty = true;
      renderRoiOverlay(readCropInputs());
    });
  });

  $("#roiDragBox").addEventListener("pointerdown", (ev) => {
    const crop = readCropInputs();
    if (!crop.enabled) return;
    roiDrag.active = true;
    roiDrag.pointerId = ev.pointerId;
    roiDrag.startX = ev.clientX;
    roiDrag.startY = ev.clientY;
    roiDrag.crop = crop;
    $("#roiDragBox").setPointerCapture(ev.pointerId);
  });

  $("#roiDragBox").addEventListener("pointermove", (ev) => {
    if (!roiDrag.active) return;
    const imgRect = imageContentRect($("#cameraStream"));
    const dx = (ev.clientX - roiDrag.startX) / Math.max(1, imgRect.width);
    const dy = (ev.clientY - roiDrag.startY) / Math.max(1, imgRect.height);
    const crop = {
      ...roiDrag.crop,
      x: Math.max(0, Math.min(1 - roiDrag.crop.w, roiDrag.crop.x + dx)),
      y: Math.max(0, Math.min(1 - roiDrag.crop.h, roiDrag.crop.y + dy)),
    };
    cropDirty = true;
    writeCropInputs(crop);
    renderRoiOverlay(crop);
  });

  async function releaseRoiDrag(ev) {
    if (!roiDrag.active) return;
    roiDrag.active = false;
    if (ev?.pointerId !== undefined && $("#roiDragBox").hasPointerCapture(ev.pointerId)) {
      $("#roiDragBox").releasePointerCapture(ev.pointerId);
    }
    await saveCrop(readCropInputs());
  }

  $("#roiDragBox").addEventListener("pointerup", releaseRoiDrag);
  $("#roiDragBox").addEventListener("pointercancel", releaseRoiDrag);

  $("#uploadInput").onchange = async (ev) => {
    const files = Array.from(ev.target.files || []);
    for (const file of files) {
      const data = await new Promise((resolve, reject) => {
        const r = new FileReader();
        r.onload = () => resolve(r.result);
        r.onerror = reject;
        r.readAsDataURL(file);
      });
      await api("/api/upload_image", {
        profile: selectedProfile(),
        split: selectedSplit,
        label: selectedLabel,
        data,
      });
    }
    ev.target.value = "";
    await refresh();
  };

  $("#trainBtn").onclick = async () => {
    await api("/api/train", {
      profile: selectedProfile(),
      epochs: Number($("#epochs").value || 16),
      batch_size: Number($("#batchSize").value || 16),
    });
    await refresh();
    refreshCameraStreams();
  };

  $("#startTestBtn").onclick = async () => {
    await api("/api/test/start", { profile: selectedProfile() });
    await refresh();
    refreshCameraStreams();
  };

  $("#stopTestBtn").onclick = async () => {
    await api("/api/test/stop", {});
    await refresh();
    refreshCameraStreams();
  };

  $("#robotStartBtn").onclick = async () => {
    await api("/api/robot/start", {});
    await refresh();
  };

  $("#robotStopBtn").onclick = async () => {
    await api("/api/robot/stop", {});
    await refresh();
  };

  $("#robotSayMaehBtn").onclick = async () => {
    await api("/api/robot/say_maeh", {});
  };

  async function requestSystemPowerAction(action, label) {
    if (!window.confirm(t("system.confirm", { label }))) return;
    await api("/api/system/power", { action, play_sound: true });
    statusEl.textContent = t("system.requested", { label });
  }

  $("#systemRebootBtn").onclick = async () => {
    await requestSystemPowerAction("reboot", "Reboot");
  };

  $("#systemShutdownBtn").onclick = async () => {
    await requestSystemPowerAction("shutdown", "Shutdown");
  };

  async function saveDriveOptions() {
    const rampRate = Number(driveOptionInputs.pwm_ramp_rate.value || 0);
    const mowerRampRate = Number(driveOptionInputs.mower_pwm_ramp_rate.value || 0);
    const mowerPwm = Number(driveOptionInputs.mower_pwm.value || 0);
    driveOptionLabels.pwm_ramp_rate.textContent = rampRate <= 0 ? t("value.off") : `${rampRate}%/s`;
    driveOptionLabels.mower_pwm_ramp_rate.textContent = mowerRampRate <= 0 ? t("value.off") : `${mowerRampRate}%/s`;
    driveOptionLabels.mower_pwm.textContent = `${mowerPwm}%`;
    await api("/api/robot/drive_options", {
      swap_sides: driveOptionInputs.swap_sides.checked,
      invert_left: driveOptionInputs.invert_left.checked,
      invert_right: driveOptionInputs.invert_right.checked,
      pwm_ramp_rate: rampRate / 100,
      mower_pwm_ramp_rate: mowerRampRate / 100,
      mower_enabled: driveOptionInputs.mower_enabled.checked,
      mower_pwm: mowerPwm / 100,
    });
    await refresh();
  }

  driveOptionInputs.pwm_ramp_rate.oninput = () => {
    const rampRate = Number(driveOptionInputs.pwm_ramp_rate.value || 0);
    driveOptionLabels.pwm_ramp_rate.textContent = rampRate <= 0 ? t("value.off") : `${rampRate}%/s`;
  };
  driveOptionInputs.mower_pwm_ramp_rate.oninput = () => {
    const rampRate = Number(driveOptionInputs.mower_pwm_ramp_rate.value || 0);
    driveOptionLabels.mower_pwm_ramp_rate.textContent = rampRate <= 0 ? t("value.off") : `${rampRate}%/s`;
  };
  driveOptionInputs.mower_pwm.oninput = () => {
    driveOptionLabels.mower_pwm.textContent = `${Number(driveOptionInputs.mower_pwm.value || 0)}%`;
  };

  Object.values(driveOptionInputs).forEach((input) => {
    input.onchange = saveDriveOptions;
  });

  async function saveAutoOptions() {
    const forward = Number(autoOptionInputs.forward_speed.value || 30);
    const turn = Number(autoOptionInputs.turn_speed.value || 30);
    const turnReverse = Number(autoOptionInputs.turn_reverse_seconds.value || 0.0);
    const turnStallReverse = Number(autoOptionInputs.turn_stall_reverse_seconds.value || 2.0);
    const turnStallMinSeconds = Number(autoOptionInputs.turn_stall_min_seconds.value || 2.5);
    const turnStallMinDelta = Number(autoOptionInputs.turn_stall_min_position_delta.value || 15);
    const turnPause = Number(autoOptionInputs.turn_pause_seconds.value || 2.0);
    const driveStallMinSeconds = Number(autoOptionInputs.drive_stall_min_seconds.value || 2.5);
    const driveStallMinVelocity = Number(autoOptionInputs.drive_stall_min_velocity.value || 12);
    const driveStallMinPoints = Number(autoOptionInputs.drive_stall_min_points.value || 40);
    autoOptionLabels.forward_speed.textContent = autoOptionText("forward_speed", forward);
    autoOptionLabels.turn_speed.textContent = autoOptionText("turn_speed", turn);
    autoOptionLabels.turn_reverse_seconds.textContent = autoOptionText("turn_reverse_seconds", turnReverse);
    autoOptionLabels.turn_stall_reverse_seconds.textContent = autoOptionText("turn_stall_reverse_seconds", turnStallReverse);
    autoOptionLabels.turn_stall_min_seconds.textContent = autoOptionText("turn_stall_min_seconds", turnStallMinSeconds);
    autoOptionLabels.turn_stall_min_position_delta.textContent = autoOptionText("turn_stall_min_position_delta", turnStallMinDelta);
    autoOptionLabels.turn_pause_seconds.textContent = autoOptionText("turn_pause_seconds", turnPause);
    autoOptionLabels.drive_stall_min_seconds.textContent = autoOptionText("drive_stall_min_seconds", driveStallMinSeconds);
    autoOptionLabels.drive_stall_min_velocity.textContent = autoOptionText("drive_stall_min_velocity", driveStallMinVelocity);
    autoOptionLabels.drive_stall_min_points.textContent = autoOptionText("drive_stall_min_points", driveStallMinPoints);
    await api("/api/robot/auto_options", {
      forward_speed: forward / 100,
      turn_speed: turn / 100,
      turn_reverse_seconds: turnReverse,
      turn_stall_reverse_seconds: turnStallReverse,
      turn_stall_min_seconds: turnStallMinSeconds,
      turn_stall_min_position_delta: turnStallMinDelta,
      turn_pause_seconds: turnPause,
      turn_stall_recovery_enabled: autoOptionInputs.turn_stall_recovery_enabled.checked,
      drive_stall_recovery_enabled: autoOptionInputs.drive_stall_recovery_enabled.checked,
      drive_stall_min_seconds: driveStallMinSeconds,
      drive_stall_min_velocity: driveStallMinVelocity,
      drive_stall_min_points: driveStallMinPoints,
    });
    await refresh();
  }

  Object.entries(autoOptionInputs).forEach(([key, input]) => {
    input.oninput = () => {
      if (input.type === "checkbox") return;
      autoOptionLabels[key].textContent = autoOptionText(key, input.value);
    };
    input.onchange = saveAutoOptions;
  });

  $("#refreshBtn").onclick = refresh;

  toggleImagesBtn.onclick = () => {
    imagesCollapsed = !imagesCollapsed;
    localStorage.setItem("aiMowerImagesCollapsed", imagesCollapsed ? "1" : "0");
    renderImagesCollapsedState();
  };

  $("#copyLogBtn").onclick = async () => {
    const text = sessionLog.textContent || "";
    if (navigator.clipboard?.writeText) {
      await navigator.clipboard.writeText(text);
    } else {
      const range = document.createRange();
      range.selectNodeContents(sessionLog);
      const sel = window.getSelection();
      sel.removeAllRanges();
      sel.addRange(range);
      document.execCommand("copy");
      sel.removeAllRanges();
    }
  };

  $("#clearLogBtn").onclick = async () => {
    await api("/api/logs/clear", {});
    await refresh();
  };

  const closeLanguageMenu = () => {
    $("#languageMenu")?.classList.remove("open");
    $("#languageMenuButton")?.setAttribute("aria-expanded", "false");
  };

  $("#languageMenuButton").onclick = (ev) => {
    ev.stopPropagation();
    const menu = $("#languageMenu");
    const open = !menu.classList.contains("open");
    menu.classList.toggle("open", open);
    $("#languageMenuButton").setAttribute("aria-expanded", open ? "true" : "false");
  };

  document.querySelectorAll("[data-language]").forEach((button) => {
    button.onclick = () => {
      const language = button.dataset.language;
      if (!supportedLanguages.includes(language)) return;
      currentLanguage = language;
      localStorage.setItem("aiMowerLanguage", currentLanguage);
      imageListKey = "";
      cameraResolutionOptionsKey = "";
      applyI18n();
      render();
      closeLanguageMenu();
    };
  });

  document.addEventListener("click", closeLanguageMenu);
  document.addEventListener("keydown", (ev) => {
    if (ev.key === "Escape") closeLanguageMenu();
  });

  function connectWS() {
    const proto = location.protocol === "https:" ? "wss" : "ws";
    const ws = new WebSocket(`${proto}://${location.host}/ws`);
    ws.onmessage = (ev) => {
      state = JSON.parse(ev.data);
      render();
    };
    ws.onclose = () => setTimeout(connectWS, 1000);
  }

  applyI18n();
  refresh().catch((err) => { statusEl.textContent = err.message; });
  setInterval(refreshRobotScorePlot, 500);
  setInterval(drawRobotScorePlot, 1000);
  connectWS();
})();
