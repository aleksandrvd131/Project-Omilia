(() => {
  const durationMs = 1000;
  const frameCount = 8;
  const interval = durationMs / frameCount;
  const minTrackedIntervals = 5;
  const maxTrackingGapMs = 300;

  function hasLandmarks(points, expectedCount) {
    if (!Array.isArray(points) || points.length !== expectedCount) return false;

    for (const point of points) {
      if (!Number.isFinite(point?.x) || !Number.isFinite(point.y) ||
          (point.z !== undefined && !Number.isFinite(point.z))) {
        return false;
      }
    }
    return true;
  }

  function hasValidHand(hand) {
    if (!hasLandmarks(hand, 21)) return false;

    const wrist = hand[0];
    const middleFingerBase = hand[9];
    // The server divides by this distance when extracting hand features.
    return wrist.x !== middleFingerBase.x || wrist.y !== middleFingerBase.y ||
      (wrist.z ?? 0) !== (middleFingerBase.z ?? 0);
  }

  function nearestFrame(frames, time) {
    let nearest = null;
    for (const frame of frames) {
      if (nearest === null || Math.abs(frame.t_ms - time) < Math.abs(nearest.t_ms - time)) {
        nearest = frame;
      }
    }
    return nearest;
  }

  function replaceMissingFrame(trackedFrames, time, allowedGapMs = interval) {
    let before = null;
    let after = null;
    for (const frame of trackedFrames) {
      if (frame.t_ms >= time) {
        after = frame;
        break;
      }
      before = frame;
    }

    if (before && after && after.t_ms - before.t_ms > maxTrackingGapMs) return null;

    const nearest = nearestFrame([before, after].filter(Boolean), time);
    // Bound extrapolation at the ends and avoid stretching one frame across a long gap.
    return nearest && Math.abs(nearest.t_ms - time) <= allowedGapMs ? nearest : null;
  }

  /**
   * Estimate wrist velocity between consecutive frames.
   * velocity = hypot(dx, dy) / dt
   * Supports:
   *   - estimateWristVelocity(frame1, frame2)
   *   - estimateWristVelocity(point1, point2, dt)
   *   - estimateWristVelocity(dx, dy, dt)
   */
  function estimateWristVelocity(first, second, customDt) {
    // Overload: estimateWristVelocity(dx, dy, dt)
    if (typeof first === "number" && typeof second === "number") {
      const dt = customDt !== undefined ? customDt : 1;
      return dt > 0 ? Math.hypot(first, second) / dt : 0;
    }

    // Overload: estimateWristVelocity(point1, point2, dt)
    if (first && second && Number.isFinite(first.x) && Number.isFinite(first.y) &&
        Number.isFinite(second.x) && Number.isFinite(second.y)) {
      const dx = second.x - first.x;
      const dy = second.y - first.y;
      const dt = customDt !== undefined ? customDt : (Math.abs(second.t_ms - first.t_ms) || 1);
      return dt > 0 ? Math.hypot(dx, dy) / dt : 0;
    }

    // Overload: estimateWristVelocity(frame1, frame2, [customDt])
    if (!first || !second) return 0;
    const dt = customDt !== undefined ? customDt : Math.abs(second.t_ms - first.t_ms);
    if (dt <= 0) return 0;

    const hands1 = Array.isArray(first.hands_data) ? first.hands_data : [];
    const hands2 = Array.isArray(second.hands_data) ? second.hands_data : [];
    const numHands = Math.min(hands1.length, hands2.length);

    let maxVelocity = 0;
    for (let h = 0; h < numHands; h++) {
      const w1 = hands1[h]?.[0];
      const w2 = hands2[h]?.[0];
      if (w1 && w2 && Number.isFinite(w1.x) && Number.isFinite(w1.y) &&
          Number.isFinite(w2.x) && Number.isFinite(w2.y)) {
        const dx = w2.x - w1.x;
        const dy = w2.y - w1.y;
        const v = Math.hypot(dx, dy) / dt;
        if (v > maxVelocity) maxVelocity = v;
      }
    }
    return maxVelocity;
  }

  /**
   * Gesture Activity Detection (VAD for signs):
   * Detect dynamic movement start and stop thresholds to filter out idle resting pose
   * before and after the actual gesture.
   */
  function detectMotionSegment(trackedFrames) {
    if (!Array.isArray(trackedFrames) || trackedFrames.length < 2) return null;

    const frameVelocities = [];
    for (let i = 0; i < trackedFrames.length - 1; i++) {
      const f1 = trackedFrames[i];
      const f2 = trackedFrames[i + 1];
      const v = estimateWristVelocity(f1, f2);
      frameVelocities.push({
        index: i,
        t_start: f1.t_ms,
        t_end: f2.t_ms,
        velocity: v,
      });
    }

    const maxVelocity = Math.max(...frameVelocities.map(fv => fv.velocity), 0);
    // Baseline noise floor: gestures with max velocity below 0.00015 (screen/ms) are stationary
    const motionNoiseFloor = 0.00015;
    if (maxVelocity < motionNoiseFloor) {
      return null;
    }

    // Dynamic threshold: 25% of peak velocity, bounded below by noise floor
    const threshold = Math.max(motionNoiseFloor, maxVelocity * 0.25);
    const activeIndices = [];
    for (const fv of frameVelocities) {
      if (fv.velocity >= threshold) {
        activeIndices.push(fv.index);
      }
    }

    if (activeIndices.length === 0) return null;

    const firstActive = activeIndices[0];
    const lastActive = activeIndices[activeIndices.length - 1];

    // Include 1 frame pre-roll and post-roll margin to preserve gesture boundaries
    const startIndex = Math.max(0, firstActive - 1);
    const endIndex = Math.min(trackedFrames.length - 1, lastActive + 2);

    let startMs = trackedFrames[startIndex].t_ms;
    let endMs = trackedFrames[endIndex].t_ms;

    // Minimum motion duration to avoid selecting degenerate windows
    const minSpanMs = 250;
    if (endMs - startMs < minSpanMs) {
      const center = (startMs + endMs) / 2;
      startMs = Math.max(0, center - minSpanMs / 2);
      endMs = Math.min(durationMs, center + minSpanMs / 2);
    }

    return {
      startMs,
      endMs,
      maxVelocity,
      threshold,
      startIndex,
      endIndex,
    };
  }

  function selectFrames(frames, handsCount) {
    const capturedFrames = frames.filter(frame => Number.isFinite(frame.t_ms) &&
      frame.t_ms >= 0 && frame.t_ms < durationMs);
    if (capturedFrames.length < minTrackedIntervals) {
      throw new Error("Камера успела снять слишком мало кадров. Повторите попытку.");
    }

    const trackedFrames = capturedFrames.filter(frame =>
      Array.isArray(frame.hands_data) && frame.hands_data.length === handsCount &&
      frame.hands_data.every(hasValidHand) && hasLandmarks(frame.pose_landmarks, 33)
    ).sort((first, second) => first.t_ms - second.t_ms);

    // VAD: detect high-energy active motion segment to filter out idle resting poses
    const motionSegment = detectMotionSegment(trackedFrames);
    let segStart = 0;
    let segEnd = durationMs;

    if (motionSegment && motionSegment.endMs > motionSegment.startMs) {
      segStart = Math.max(0, motionSegment.startMs);
      segEnd = Math.min(durationMs, motionSegment.endMs);
    }

    const activeSpan = segEnd - segStart;
    const activeInterval = activeSpan / frameCount;

    const selected = Array.from({ length: frameCount }, (_, index) => {
      const start = segStart + index * activeInterval;
      const candidates = trackedFrames.filter(frame => frame.t_ms >= start && frame.t_ms < start + activeInterval);
      return nearestFrame(candidates, start + activeInterval / 2);
    });

    const trackingError = "Руки или тело пропадали из кадра слишком долго. Держите кисти и плечи в кадре и повторите попытку.";
    if (selected.filter(Boolean).length < minTrackedIntervals) {
      throw new Error(trackingError);
    }

    return selected.map((frame, index) => {
      if (frame) return frame;
      const targetTime = segStart + (index + 0.5) * activeInterval;
      const replacement = replaceMissingFrame(trackedFrames, targetTime, activeInterval);
      if (!replacement) throw new Error(trackingError);
      return replacement;
    });
  }

  const api = {
    prepSeconds: 3,
    durationMs,
    frameCount,
    estimateWristVelocity,
    detectMotionSegment,
    selectFrames,
  };

  if (typeof window !== "undefined") {
    window.omiliaDynamicClip = api;
  }
  if (typeof module !== "undefined" && module.exports) {
    module.exports = api;
  }
})();
