const assert = require("node:assert/strict");
const test = require("node:test");
const path = require("node:path");

const OmiliaInference = require(path.join(__dirname, "../src/project_omilia/frontend/inference.js"));
const { OmiliaFeatureExtractor } = OmiliaInference;

function generateSyntheticHand(scale = 1.0, offsetX = 0.5, offsetY = 0.5) {
  const points = [[0, 0, 0]];
  const fingerAngles = [-0.4, -0.15, 0.0, 0.15, 0.35];
  const fingerLengths = [0.08, 0.11, 0.12, 0.11, 0.09];

  for (let f = 0; f < 5; f++) {
    const angle = fingerAngles[f];
    const totalLen = fingerLengths[f];
    const baseDir = [Math.sin(angle), -Math.cos(angle), 0.02 * f];
    const segLen = totalLen / 4.0;

    const mcp = [baseDir[0] * segLen * 1.5, baseDir[1] * segLen * 1.5, baseDir[2] * segLen * 1.5];
    points.push(mcp);

    const pip = [mcp[0] + baseDir[0] * segLen, mcp[1] + baseDir[1] * segLen, mcp[2] + baseDir[2] * segLen];
    points.push(pip);

    const dip = [pip[0] + baseDir[0] * segLen * 0.8, pip[1] + baseDir[1] * segLen * 0.8, pip[2] + baseDir[2] * segLen * 0.8];
    points.push(dip);

    const tip = [dip[0] + baseDir[0] * segLen * 0.7, dip[1] + baseDir[1] * segLen * 0.7, dip[2] + baseDir[2] * segLen * 0.7];
    points.push(tip);
  }

  return points.map(([x, y, z]) => ({
    x: x * scale + offsetX,
    y: y * scale + offsetY,
    z: z * scale,
  }));
}

function generateSyntheticBody(scale = 1.0) {
  const cx = 0.5;
  const cy = 0.4;
  const body = Array.from({ length: 33 }, () => ({ x: cx, y: cy, z: 0 }));

  const halfShoulder = (0.35 / 2.0) * scale;
  body[0] = { x: cx, y: cy - 0.15 * scale, z: 0 };
  body[11] = { x: cx - halfShoulder, y: cy + 0.05 * scale, z: 0 };
  body[12] = { x: cx + halfShoulder, y: cy + 0.05 * scale, z: 0 };
  body[15] = { x: cx + 0.15 * scale, y: cy + 0.02 * scale, z: 0 };
  body[16] = { x: cx - 0.15 * scale, y: cy + 0.02 * scale, z: 0 };

  return body;
}

test("OmiliaFeatureExtractor: scale and distance invariance in JS", () => {
  const extractor = new OmiliaFeatureExtractor();

  // Дистанция 1: нормальный масштаб
  const body1 = generateSyntheticBody(1.0);
  const hand1 = generateSyntheticHand(2.5, body1[15].x, body1[15].y);
  const vec1 = extractor.extract([hand1], body1, 1);

  // Дистанция 2: 1.6x ближе к камере
  const body2 = generateSyntheticBody(1.6);
  const hand2 = generateSyntheticHand(2.5 * 1.6, body2[15].x, body2[15].y);
  const vec2 = extractor.extract([hand2], body2, 1);

  assert.equal(vec1.length, 141);
  assert.equal(vec2.length, 141);

  let maxDiff = 0;
  for (let i = 0; i < 141; i++) {
    const diff = Math.abs(vec1[i] - vec2[i]);
    if (diff > maxDiff) maxDiff = diff;
  }

  // Признаки должны совпадать с точностью до тысячных
  assert.ok(maxDiff < 1e-3, `Max feature difference too high: ${maxDiff}`);
});
