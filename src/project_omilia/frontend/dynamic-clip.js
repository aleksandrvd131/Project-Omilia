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

  function replaceMissingFrame(trackedFrames, time) {
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
    return nearest && Math.abs(nearest.t_ms - time) <= interval ? nearest : null;
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

    const selected = Array.from({ length: frameCount }, (_, index) => {
      const start = index * interval;
      const candidates = trackedFrames.filter(frame => frame.t_ms >= start && frame.t_ms < start + interval);
      return nearestFrame(candidates, start + interval / 2);
    });

    const trackingError = "Руки или тело пропадали из кадра слишком долго. Держите кисти и плечи в кадре и повторите попытку.";
    if (selected.filter(Boolean).length < minTrackedIntervals) {
      throw new Error(trackingError);
    }

    return selected.map((frame, index) => {
      if (frame) return frame;
      const replacement = replaceMissingFrame(trackedFrames, (index + 0.5) * interval);
      if (!replacement) throw new Error(trackingError);
      return replacement;
    });
  }

  window.omiliaDynamicClip = { prepSeconds: 3, durationMs, selectFrames };
})();
