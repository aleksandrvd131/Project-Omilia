const assert = require("node:assert/strict");
const test = require("node:test");
const path = require("node:path");

const OmiliaInference = require(path.join(__dirname, "../src/project_omilia/frontend/inference.js"));
const { OmiliaDiagnostics } = OmiliaInference;

function createBaseVector(handsCount = 1) {
  const dim = 141 * handsCount;
  const vec = new Float32Array(dim);

  for (let h = 0; h < handsCount; h++) {
    const offset = h * 135;
    // Нормаль смотрит на экран
    vec[offset + 60] = 0;
    vec[offset + 61] = 0;
    vec[offset + 62] = 1.0;

    for (let f = 0; f < 5; f++) {
      const base = offset + 63 + f * 9;
      vec[base] = 0.2;
      vec[base + 3] = 0.2;
      vec[base + 6] = 0.2;
    }
  }

  vec[138] = 0.15;
  vec[139] = -0.05;
  vec[140] = 0;
  return vec;
}

test("OmiliaDiagnostics (JS): palm orientation hint", () => {
  const target = createBaseVector(1);
  target[60] = 0;
  target[61] = 0;
  target[62] = 1.0; // К экрану

  const user = createBaseVector(1);
  user[60] = 0;
  user[61] = 0;
  user[62] = -1.0; // От экрана

  const diag = OmiliaDiagnostics.diagnose(user, target, 1);
  assert.equal(diag.isMatching, false);
  assert.ok(diag.hints.some(h => h.includes("Поверните ладонь к экрану")));
  assert.ok(diag.primaryHint.includes("Поверните ладонь к экрану"));
});

test("OmiliaDiagnostics (JS): finger straighten and problem_fingers highlight", () => {
  const target = createBaseVector(1);
  // Указательный палец прямой
  target[72] = 0.05;
  target[75] = 0.05;
  target[78] = 0.05;

  const user = createBaseVector(1);
  // Указательный палец согнут
  user[72] = 0.35;
  user[75] = 0.35;
  user[78] = 0.35;

  const diag = OmiliaDiagnostics.diagnose(user, target, 1);
  assert.equal(diag.isMatching, false);
  assert.ok(diag.problemFingers.includes(1)); // Палец 1 = указательный
  assert.ok(diag.hints.some(h => h.includes("Выпрямите указательный палец")));
  assert.equal(diag.fingerStatus.index, "straighten");
});

test("OmiliaDiagnostics (JS): matching gesture", () => {
  const target = createBaseVector(1);
  const user = createBaseVector(1); // Идентичный

  const diag = OmiliaDiagnostics.diagnose(user, target, 1);
  assert.equal(diag.isMatching, true);
  assert.ok(diag.primaryHint.includes("✨"));
  assert.equal(diag.problemFingers.length, 0);
});
