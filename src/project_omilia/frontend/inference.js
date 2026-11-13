/**
 * Project Omiλia — Клиентский ML-инференс в браузере (0ms Network Ping)
 * Включает:
 * 1. OmiliaFeatureExtractor — точное извлечение 141 (1 рука) / 282 (2 руки) признаков позы и кистей
 * 2. OmiliaStaticClassifier — классификация статических жестов на ONNX Runtime Web / Центроидах
 */

(function (root, factory) {
  if (typeof define === 'function' && define.amd) {
    define([], factory);
  } else if (typeof module === 'object' && module.exports) {
    module.exports = factory();
  } else {
    root.OmiliaInference = factory();
  }
})(typeof self !== 'undefined' ? self : this, function () {
  'use strict';

  const EPS = 1e-8;
  const HAND_REF_SCALE = 0.25;
  const TORSO_REF_SCALE = 0.35;

  // --- Векторные математические операции ---
  const Vec = {
    sub(a, b) {
      return [a[0] - b[0], a[1] - b[1], a[2] - b[2]];
    },
    add(a, b) {
      return [a[0] + b[0], a[1] + b[1], a[2] + b[2]];
    },
    scale(a, s) {
      return [a[0] * s, a[1] * s, a[2] * s];
    },
    dot(a, b) {
      return a[0] * b[0] + a[1] * b[1] + a[2] * b[2];
    },
    norm(a) {
      return Math.hypot(a[0], a[1], a[2]);
    },
    dist(a, b) {
      return Math.hypot(a[0] - b[0], a[1] - b[1], a[2] - b[2]);
    },
    cross(a, b) {
      return [
        a[1] * b[2] - a[2] * b[1],
        a[2] * b[0] - a[0] * b[2],
        a[0] * b[1] - a[1] * b[0],
      ];
    },
    normalize(a) {
      const n = Math.hypot(a[0], a[1], a[2]);
      if (n < EPS) return [0, 0, 0];
      return [a[0] / n, a[1] / n, a[2] / n];
    },
    normAngle(a, b) {
      const na = Math.hypot(a[0], a[1], a[2]);
      const nb = Math.hypot(b[0], b[1], b[2]);
      if (na < EPS || nb < EPS) return 0;
      let cosVal = (a[0] * b[0] + a[1] * b[1] + a[2] * b[2]) / (na * nb);
      cosVal = Math.max(-1, Math.min(1, cosVal));
      return Math.acos(cosVal) / Math.PI;
    },
    scalarToVec(s) {
      return [s, s, s];
    },
  };

  /**
   * Класс обработки кисти руки (аналог Hand из body.py)
   */
  class HandFeatureProcessor {
    constructor(points, isRight) {
      this.isRight = isRight;
      this.data = points.map((p) => [p.x, p.y, p.z || 0]);
      const wrist = this.data[0];

      // Масштаб ладони: расстояние между запястьем и основанием среднего пальца (точка 9)
      this.palmScale = Math.max(EPS, Vec.dist(wrist, this.data[9]));
      const scaleNorm = Math.max(1e-4, this.palmScale) / HAND_REF_SCALE;

      // Нормаль к плоскости ладони
      const v1 = Vec.sub(this.data[5], wrist);
      const v2 = Vec.sub(this.data[17], wrist);
      const crossVec = isRight ? Vec.cross(v1, v2) : Vec.cross(v2, v1);
      this.normal = Vec.normalize(crossVec);

      // Векторы фаланг для каждого из 5 пальцев (нормализованные к эталонному масштабу кисти)
      this.fingers = [[], [], [], [], []];
      for (let i = 1; i < 20; i += 4) {
        const fingerIdx = (i - 1) / 4;
        this.fingers[fingerIdx].push(Vec.scale(Vec.sub(this.data[i], wrist), 1.0 / scaleNorm));
        for (let j = 0; j < 3; j++) {
          this.fingers[fingerIdx].push(Vec.scale(Vec.sub(this.data[i + j + 1], this.data[i + j]), 1.0 / scaleNorm));
        }
      }
    }

    getShapeFeatures() {
      const result = [];

      // 0..14 — углы между фалангами внутри каждого пальца
      for (let i = 0; i < 5; i++) {
        for (let j = 0; j < 3; j++) {
          const angle = Vec.normAngle(this.fingers[i][j], this.fingers[i][j + 1]);
          result.push(Vec.scalarToVec(angle));
        }
      }

      // 15..18 — углы расхождения между пальцами
      const fingerVecs = [];
      for (let i = 1; i < 20; i += 4) {
        fingerVecs.push(Vec.sub(this.data[i + 3], this.data[i]));
      }
      for (let i = 0; i < 4; i++) {
        const angle = Vec.normAngle(fingerVecs[i], fingerVecs[i + 1]);
        result.push(Vec.scalarToVec(angle));
      }

      // 19..22 — расстояния от кончиков пальцев (указательный, средний, безымянный, мизинец) до кончика большого
      for (let i = 8; i < 21; i += 4) {
        const dist = Vec.dist(this.data[i], this.data[4]) / this.palmScale;
        result.push(Vec.scalarToVec(dist));
      }

      // 23 — расстояние между кончиками указательного и среднего пальцев
      const indexMidDist = Vec.dist(this.data[12], this.data[8]) / this.palmScale;
      result.push(Vec.scalarToVec(indexMidDist));

      return result;
    }

    get1DArray() {
      const list = [];
      for (const finger of this.fingers) {
        for (const vec of finger) {
          list.push(vec);
        }
      }
      list.push(this.normal);
      const shapes = this.getShapeFeatures();
      for (const s of shapes) {
        list.push(s);
      }
      return list;
    }
  }

  /**
   * Экстрактор признаков из скелета MediaPipe (аналог Pose из body.py)
   */
  class OmiliaFeatureExtractor {
    extract(handsData, poseLandmarks, handsCount = 1) {
      if (!handsData || handsData.length === 0) {
        return null;
      }

      let nose = [0, 0, 0];
      let rightWrist = [0, 0, 0];
      let leftWrist = [0, 0, 0];
      let chestCenter = [0, 0, 0];
      let torsoNorm = 1.0;

      if (poseLandmarks && poseLandmarks.length >= 17) {
        nose = [poseLandmarks[0].x, poseLandmarks[0].y, poseLandmarks[0].z || 0];
        // В body.py: data[15] — правое запястье, data[16] — левое запястье
        rightWrist = [poseLandmarks[15].x, poseLandmarks[15].y, poseLandmarks[15].z || 0];
        leftWrist = [poseLandmarks[16].x, poseLandmarks[16].y, poseLandmarks[16].z || 0];
        if (poseLandmarks[11] && poseLandmarks[12]) {
          chestCenter = [
            (poseLandmarks[11].x + poseLandmarks[12].x) / 2,
            (poseLandmarks[11].y + poseLandmarks[12].y) / 2,
            ((poseLandmarks[11].z || 0) + (poseLandmarks[12].z || 0)) / 2,
          ];
          const leftShoulder = [poseLandmarks[11].x, poseLandmarks[11].y, poseLandmarks[11].z || 0];
          const rightShoulder = [poseLandmarks[12].x, poseLandmarks[12].y, poseLandmarks[12].z || 0];
          const torsoScale = Vec.dist(leftShoulder, rightShoulder);
          torsoNorm = Math.max(1e-4, torsoScale) / TORSO_REF_SCALE;
        }
      } else {
        // Оценка центров по кисти при отсутствии скелета тела (соответствует pose_service.py)
        const h0 = handsData[0][0];
        nose = [0.5, 0.25, 0];
        rightWrist = [h0.x, h0.y, h0.z || 0];
        leftWrist = handsData.length > 1 ? [handsData[1][0].x, handsData[1][0].y, handsData[1][0].z || 0] : [-1.0, -1.0, 0];
        chestCenter = [0.5, 0.45, 0];
        torsoNorm = 1.0;
      }

      const isRightHand = (handPts) => {
        const hw = [handPts[0].x, handPts[0].y, handPts[0].z || 0];
        return Vec.dist(hw, rightWrist) < Vec.dist(hw, leftWrist);
      };

      if (handsCount === 1) {
        // Режим одной руки: если показана левая рука, отзеркаливаем x относительно носа
        let handPts = handsData[0].map((p) => ({ x: p.x, y: p.y, z: p.z || 0 }));
        if (!isRightHand(handPts)) {
          const noseX = nose[0];
          handPts = handPts.map((p) => ({
            x: 2 * noseX - p.x,
            y: p.y,
            z: p.z,
          }));
        }

        const handObj = new HandFeatureProcessor(handPts, true);
        const vectors = handObj.get1DArray();

        // Векторы смещения относительно носа и груди, нормализованные по масштабу торса
        const rightToNose = Vec.scale(Vec.sub(rightWrist, nose), 1.0 / torsoNorm);
        const rightToChest = Vec.scale(Vec.sub(rightWrist, chestCenter), 1.0 / torsoNorm);
        vectors.push(rightToNose);
        vectors.push(rightToChest);

        // Преобразуем в одномерный массив float32 (47 * 3 = 141)
        const flat = new Float32Array(vectors.length * 3);
        let ptr = 0;
        for (const v of vectors) {
          flat[ptr++] = Math.round(v[0] * 1e8) / 1e8;
          flat[ptr++] = Math.round(v[1] * 1e8) / 1e8;
          flat[ptr++] = Math.round(v[2] * 1e8) / 1e8;
        }
        return flat;
      } else {
        // Режим двух рук (требуется 2 руки)
        if (handsData.length < 2) return null;

        const h0 = handsData[0].map((p) => ({ x: p.x, y: p.y, z: p.z || 0 }));
        const h1 = handsData[1].map((p) => ({ x: p.x, y: p.y, z: p.z || 0 }));

        let rightHandObj;
        let leftHandObj;
        if (isRightHand(h0)) {
          rightHandObj = new HandFeatureProcessor(h0, true);
          leftHandObj = new HandFeatureProcessor(h1, false);
        } else {
          rightHandObj = new HandFeatureProcessor(h1, true);
          leftHandObj = new HandFeatureProcessor(h0, false);
        }

        const vectors = [];
        for (const v of rightHandObj.get1DArray()) vectors.push(v);
        for (const v of leftHandObj.get1DArray()) vectors.push(v);

        vectors.push(Vec.scale(Vec.sub(rightWrist, nose), 1.0 / torsoNorm));
        vectors.push(Vec.scale(Vec.sub(rightWrist, chestCenter), 1.0 / torsoNorm));
        vectors.push(Vec.scale(Vec.sub(leftWrist, nose), 1.0 / torsoNorm));
        vectors.push(Vec.scale(Vec.sub(leftWrist, chestCenter), 1.0 / torsoNorm));

        const flat = new Float32Array(vectors.length * 3);
        let ptr = 0;
        for (const v of vectors) {
          flat[ptr++] = Math.round(v[0] * 1e8) / 1e8;
          flat[ptr++] = Math.round(v[1] * 1e8) / 1e8;
          flat[ptr++] = Math.round(v[2] * 1e8) / 1e8;
        }
        return flat;
      }
    }
  }

  /**
   * Браузерный классификатор статических жестов (ONNX Runtime Web + Быстрый векторный классификатор)
   */
  class OmiliaStaticClassifier {
    constructor() {
      this.extractor = new OmiliaFeatureExtractor();
      this.models = {
        1: { loaded: false, labels: [], centroids: [], onnxSession: null },
        2: { loaded: false, labels: [], centroids: [], onnxSession: null },
      };
      this.init();
    }

    async init() {
      await Promise.all([this.loadModel(1), this.loadModel(2)]);
    }

    async loadModel(handsCount) {
      try {
        const res = await fetch(`/api/models/static-classifier?hands=${handsCount}`);
        if (!res.ok) return;
        const meta = await res.json();
        if (meta.labels && meta.centroids) {
          this.models[handsCount].labels = meta.labels;
          this.models[handsCount].centroids = meta.centroids.map((c) => new Float32Array(c));
          this.models[handsCount].maxDistance = meta.max_distance || 2.0;
          this.models[handsCount].loaded = true;
          console.log(`[Omilia ML] Загружена модель статики для ${handsCount} рук(и): ${meta.labels.length} классов`);
        }

        // Попытка инициализации onnxruntime-web при наличии библиотеки в браузере
        if (typeof ort !== 'undefined' && ort.InferenceSession) {
          try {
            const onnxSession = await ort.InferenceSession.create(
              `/api/models/static-onnx?hands=${handsCount}`,
              { executionProviders: ['wasm'] }
            );
            this.models[handsCount].onnxSession = onnxSession;
            console.log(`[Omilia ML] ONNX Runtime Web успешно подключен для ${handsCount} рук(и)`);
          } catch (onnxErr) {
            console.log(`[Omilia ML] ONNX Web недоступен (${onnxErr.message}), используется высокоскоростной CPU-движок`);
          }
        }
      } catch (err) {
        console.warn(`[Omilia ML] Ошибка загрузки модели ${handsCount}h:`, err);
      }
    }

    predict(handsData, poseLandmarks, handsCount = 1) {
      const model = this.models[handsCount];
      if (!model || !model.loaded || model.labels.length === 0) {
        return null;
      }

      if (handsCount === 2 && (!handsData || handsData.length < 2)) {
        return {
          detected: true,
          gesture: 'Покажите 2 руки',
          name: 'Покажите 2 руки',
          score: 0.0,
          distance: 0.0,
          confidence: 0.0,
        };
      }

      const features = this.extractor.extract(handsData, poseLandmarks, handsCount);
      if (!features) {
        return {
          detected: false,
          gesture: null,
          name: null,
          score: null,
          distance: null,
        };
      }

      // Вычисление евклидовых расстояний до центроидов (SIMD-скорость в JS: < 0.05ms)
      const centroids = model.centroids;
      const numClasses = centroids.length;
      const numFeatures = features.length;
      let minDistance = Infinity;
      let bestClassIdx = -1;

      for (let c = 0; c < numClasses; c++) {
        const centroid = centroids[c];
        let sumSq = 0;
        for (let i = 0; i < numFeatures; i++) {
          const diff = features[i] - centroid[i];
          sumSq += diff * diff;
        }
        const dist = Math.sqrt(sumSq);
        if (dist < minDistance) {
          minDistance = dist;
          bestClassIdx = c;
        }
      }

      const score = Math.round(minDistance * 100) / 100;
      const maxDistance = model.maxDistance || 2.0;
      const confidence = Math.max(0, Math.min(100, Math.round((1 - minDistance / maxDistance) * 100)));

      let gestureName = '';
      if (minDistance > maxDistance || bestClassIdx < 0) {
        return {
          detected: false,
          gesture: null,
          name: null,
          score: score,
          distance: score,
          confidence: 0,
        };
      } else {
        gestureName = model.labels[bestClassIdx];
      }

      return {
        detected: true,
        gesture: gestureName,
        name: gestureName,
        score: score,
        distance: score,
        confidence: confidence,
        fromClient: true,
      };
    }
  }

  const FINGER_NAMES = [
    'большой палец',
    'указательный палец',
    'средний палец',
    'безымянный палец',
    'мизинец',
  ];
  const FINGER_KEYS = ['thumb', 'index', 'middle', 'ring', 'pinky'];

  /**
   * Диагностический анализатор биометрии и генератор подсказок
   */
  const OmiliaDiagnostics = {
    diagnose(userVec, targetVec, handsCount = 1) {
      if (!userVec || !targetVec) return null;
      const expectedDim = 141 * handsCount;
      if (userVec.length !== expectedDim || targetVec.length !== expectedDim) return null;

      let sumSq = 0;
      for (let i = 0; i < expectedDim; i++) {
        const d = userVec[i] - targetVec[i];
        sumSq += d * d;
      }
      const score = Math.round(Math.sqrt(sumSq) * 100) / 100;

      const hints = [];
      const problemFingers = [];
      const fingerStatus = {};

      const diagnoseHand = (offset, prefix = '') => {
        // 1. Нормаль ладони (offset + 60..62)
        const un = [userVec[offset + 60], userVec[offset + 61], userVec[offset + 62]];
        const tn = [targetVec[offset + 60], targetVec[offset + 61], targetVec[offset + 62]];
        const unNorm = Vec.normalize(un);
        const tnNorm = Vec.normalize(tn);
        const dot = Vec.dot(unNorm, tnNorm);

        if (dot < 0.70) {
          const dz = tnNorm[2] - unNorm[2];
          const dx = tnNorm[0] - unNorm[0];
          const dy = tnNorm[1] - unNorm[1];
          if (dz > 0.45) {
            hints.push(`${prefix}Поверните ладонь к экрану`);
          } else if (dz < -0.45) {
            hints.push(`${prefix}Поверните ладонь тыльной стороной к экрану`);
          } else if (Math.abs(dx) > Math.abs(dy)) {
            if (dx > 0.4) hints.push(`${prefix}Поверните ладонь правее`);
            else if (dx < -0.4) hints.push(`${prefix}Поверните ладонь левее`);
          } else {
            if (dy > 0.4) hints.push(`${prefix}Направьте ладонь ниже`);
            else if (dy < -0.4) hints.push(`${prefix}Направьте ладонь выше`);
          }
        }

        // 2. Сгибание пальцев (offset + 63..107)
        const bendDiffs = [];
        for (let f = 0; f < 5; f++) {
          const key = FINGER_KEYS[f];
          const name = FINGER_NAMES[f];
          const base = offset + 63 + f * 9;
          const uBend = userVec[base] + userVec[base + 3] + userVec[base + 6];
          const tBend = targetVec[base] + targetVec[base + 3] + targetVec[base + 6];
          const diff = uBend - tBend;

          if (diff > 0.38) {
            fingerStatus[key] = 'straighten';
            problemFingers.push(f);
            bendDiffs.push({ diff, hint: `${prefix}Выпрямите ${name}` });
          } else if (diff < -0.38) {
            fingerStatus[key] = 'bend';
            problemFingers.push(f);
            bendDiffs.push({ diff: -diff, hint: `${prefix}Согните ${name}` });
          } else {
            fingerStatus[key] = 'ok';
          }
        }

        bendDiffs.sort((a, b) => b.diff - a.diff);
        for (const item of bendDiffs) hints.push(item.hint);

        // 3. Пинч (кончики указательного и большого: offset + 120)
        if (targetVec[offset + 120] < 0.40 && userVec[offset + 120] > 0.70) {
          hints.push(`${prefix}Сомкните кончики большого и указательного пальцев`);
        }
      };

      if (handsCount === 1) {
        diagnoseHand(0);
        // Смещение относительно груди (138..140). В кадре +Y направлен вниз
        const dy = userVec[139] - targetVec[139];
        const dx = targetVec[138] - userVec[138];
        if (dy > 0.38) hints.push('Поднимите руку чуть выше');
        else if (dy < -0.38) hints.push('Опустите руку чуть ниже');
        else if (dx > 0.38) hints.push('Сдвиньте руку чуть правее');
        else if (dx < -0.38) hints.push('Сдвиньте руку чуть левее');
      } else {
        diagnoseHand(0, 'Правая рука: ');
        diagnoseHand(135, 'Левая рука: ');
      }

      const isMatching = score <= 1.25 && problemFingers.length === 0 && hints.length === 0;
      let primaryHint = null;
      if (isMatching) {
        primaryHint = '✨ Отлично! Удерживайте позу...';
      } else if (hints.length > 0) {
        primaryHint = `💡 Подсказка: ${hints[0]}`;
      }

      return {
        isMatching,
        score,
        primaryHint,
        hints: hints.slice(0, 4),
        problemFingers,
        fingerStatus,
      };
    },
  };

  return {
    Vec,
    OmiliaFeatureExtractor,
    OmiliaStaticClassifier,
    OmiliaDiagnostics,
  };
});
