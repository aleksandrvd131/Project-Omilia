const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const test = require("node:test");
const vm = require("node:vm");

const source = path.join(__dirname, "../src/project_omilia/frontend/dynamic-clip.js");
const window = {};
vm.runInNewContext(fs.readFileSync(source, "utf8"), { window }, { filename: source });
const { selectFrames } = window.omiliaDynamicClip;

function landmarks(count) {
  return Array.from({ length: count }, (_, index) => ({ x: index / 50, y: 0.3, z: 0 }));
}

function frame(tMs, handsCount = 1) {
  return {
    t_ms: tMs,
    hands_data: Array.from({ length: handsCount }, () => landmarks(21)),
    pose_landmarks: landmarks(33),
  };
}

function clip(handsCount = 1) {
  return Array.from({ length: 8 }, (_, index) => frame((index + 0.5) * 125, handsCount));
}

test("uses a tracked frame when the nearest frame has lost the body", () => {
  const frames = clip();
  const replacement = frame(frames[3].t_ms + 15);
  frames[3].pose_landmarks = null;
  frames.splice(4, 0, replacement);

  const selected = selectFrames(frames, 1);
  assert.equal(selected.length, 8);
  assert.equal(selected[3], replacement);
});

test("keeps an eight-frame clip after a short tracking gap", () => {
  const frames = clip(2);
  frames[3].hands_data.pop();

  const selected = selectFrames(frames, 2);
  assert.equal(selected.length, 8);
  assert.ok(selected.every(item => item.hands_data.length === 2));
  assert.equal(new Set(selected).size, 7);
});

test("skips non-finite landmarks before choosing a frame", () => {
  const frames = clip();
  const replacement = frame(frames[2].t_ms - 10);
  frames[2].hands_data[0][12].x = NaN;
  frames.splice(2, 0, replacement);

  assert.equal(selectFrames(frames, 1)[2], replacement);
});

test("rejects a prolonged tracking gap and clips with too little tracked data", () => {
  const frames = clip();
  frames[2].hands_data = [];
  frames[3].hands_data = [];
  frames[4].hands_data = [];

  assert.throws(() => selectFrames(frames, 1), /слишком долго/);
  assert.throws(() => selectFrames(clip().slice(0, 4), 1), /мало кадров/);
});

test("can recover a brief loss at the end of a clip", () => {
  const frames = clip();
  frames[7].pose_landmarks = null;
  const selected = selectFrames(frames, 1);
  assert.equal(selected[7], frames[6]);
});

test("does not replace most of the clip with copies", () => {
  const frames = clip();
  for (const index of [1, 3, 5, 7]) frames[index].hands_data = [];
  assert.throws(() => selectFrames(frames, 1), /слишком долго/);
});

test("keeps all eight frames in a fully tracked clip", () => {
  const frames = clip();
  assert.deepEqual(Array.from(selectFrames(frames, 1)), frames);
});
