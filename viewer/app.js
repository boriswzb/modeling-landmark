import * as THREE from 'three';
import { OrbitControls } from 'three/addons/controls/OrbitControls.js';
import { GLTFLoader } from 'three/addons/loaders/GLTFLoader.js';

// ---------------------------------------------------------------------------
// Scene
// ---------------------------------------------------------------------------
const stage = document.getElementById('stage');
const loading = document.getElementById('loading');
const loaderFill = document.getElementById('loaderFill');
const loaderPct = document.getElementById('loaderPct');
const explodeInput = document.getElementById('explode');
const explodeValue = document.getElementById('explodeValue');
const hotspotsLayer = document.getElementById('hotspots');
const compassNeedle = document.getElementById('compassNeedle');
const fpsEl = document.getElementById('fps');

const renderer = new THREE.WebGLRenderer({ antialias: true, powerPreference: 'high-performance' });
renderer.setPixelRatio(Math.min(window.devicePixelRatio || 1, 1.8));
renderer.setSize(window.innerWidth, window.innerHeight);
renderer.outputColorSpace = THREE.SRGBColorSpace;
renderer.toneMapping = THREE.ACESFilmicToneMapping;
renderer.toneMappingExposure = 1.08;
renderer.shadowMap.enabled = true;
renderer.shadowMap.type = THREE.PCFSoftShadowMap;
stage.appendChild(renderer.domElement);

const scene = new THREE.Scene();
scene.fog = new THREE.FogExp2(0xd8af85, 0.000032);

function makeEnvironment() {
  const c = document.createElement('canvas');
  c.width = 1024;
  c.height = 512;
  const ctx = c.getContext('2d');
  const g = ctx.createLinearGradient(0, 0, 0, c.height);
  g.addColorStop(0.0, '#5f94c8');
  g.addColorStop(0.38, '#b8d1e4');
  g.addColorStop(0.5, '#f2c894');
  g.addColorStop(0.58, '#b58c5d');
  g.addColorStop(1.0, '#59412d');
  ctx.fillStyle = g;
  ctx.fillRect(0, 0, c.width, c.height);

  const glow = ctx.createRadialGradient(c.width * 0.68, c.height * 0.42, 4, c.width * 0.68, c.height * 0.42, 150);
  glow.addColorStop(0, 'rgba(255,236,198,0.95)');
  glow.addColorStop(0.25, 'rgba(255,196,128,0.45)');
  glow.addColorStop(1, 'rgba(255,180,100,0)');
  ctx.fillStyle = glow;
  ctx.fillRect(0, 0, c.width, c.height);

  const tex = new THREE.CanvasTexture(c);
  tex.mapping = THREE.EquirectangularReflectionMapping;
  tex.colorSpace = THREE.SRGBColorSpace;
  const pmrem = new THREE.PMREMGenerator(renderer);
  const env = pmrem.fromEquirectangular(tex).texture;
  pmrem.dispose();
  tex.dispose();
  return env;
}

scene.environment = makeEnvironment();
scene.environmentIntensity = 0.14;

const camera = new THREE.PerspectiveCamera(40, window.innerWidth / window.innerHeight, 1, 30000);
camera.position.set(850, 280, 1350);

const controls = new OrbitControls(camera, renderer.domElement);
controls.target.set(-550, 80, 300);
controls.enableDamping = true;
controls.dampingFactor = 0.065;
controls.minDistance = 90;
controls.maxDistance = 5200;
controls.maxPolarAngle = Math.PI * 0.495;
controls.autoRotate = true;
controls.autoRotateSpeed = 0.42;
controls.screenSpacePanning = false;
controls.update();

// ---------------------------------------------------------------------------
// Sky, lights and atmosphere
// ---------------------------------------------------------------------------
const skyUniforms = {
  topColor: { value: new THREE.Color(0x214b78) },
  midColor: { value: new THREE.Color(0x8fb6d8) },
  horizonColor: { value: new THREE.Color(0xe7ad72) },
  sunColor: { value: new THREE.Color(0xffb66e) },
  sunDirection: { value: new THREE.Vector3(0.78, 0.30, -0.55).normalize() },
};
const sky = new THREE.Mesh(
  new THREE.SphereGeometry(19000, 48, 24),
  new THREE.ShaderMaterial({
    side: THREE.BackSide,
    depthWrite: false,
    uniforms: skyUniforms,
    vertexShader: `
      varying vec3 vWorldPosition;
      void main() {
        vec4 worldPosition = modelMatrix * vec4(position, 1.0);
        vWorldPosition = worldPosition.xyz;
        gl_Position = projectionMatrix * modelViewMatrix * vec4(position, 1.0);
      }
    `,
    fragmentShader: `
      uniform vec3 topColor;
      uniform vec3 midColor;
      uniform vec3 horizonColor;
      uniform vec3 sunColor;
      uniform vec3 sunDirection;
      varying vec3 vWorldPosition;
      void main() {
        vec3 dir = normalize(vWorldPosition);
        float h = clamp(dir.y, 0.0, 1.0);
        float t1 = smoothstep(0.0, 0.10, h);
        float t2 = smoothstep(0.03, 0.28, h);
        vec3 col = mix(horizonColor, midColor, t1);
        col = mix(col, topColor, t2);
        float d = max(dot(dir, normalize(sunDirection)), 0.0);
        col += sunColor * (pow(d, 900.0) * 2.4 + pow(d, 14.0) * 0.16);
        gl_FragColor = vec4(col, 1.0);
        #include <tonemapping_fragment>
        #include <colorspace_fragment>
      }
    `,
  })
);
sky.frustumCulled = false;
scene.add(sky);

const hemi = new THREE.HemisphereLight(0xa9c2e2, 0x5e4632, 0.45);
scene.add(hemi);

const ambient = new THREE.AmbientLight(0x8c7b65, 0.16);
scene.add(ambient);

const sun = new THREE.DirectionalLight(0xffb878, 4.2);
sun.position.set(1200, 900, 1200);
sun.target.position.set(0, 0, 300);
sun.castShadow = true;
sun.shadow.mapSize.set(2048, 2048);
sun.shadow.camera.left = -1200;
sun.shadow.camera.right = 1200;
sun.shadow.camera.top = 1200;
sun.shadow.camera.bottom = -1200;
sun.shadow.camera.near = 80;
sun.shadow.camera.far = 5000;
sun.shadow.bias = -0.0008;
sun.shadow.normalBias = 1.2;
scene.add(sun);
scene.add(sun.target);

// A very low warm bounce from the sand
const bounce = new THREE.DirectionalLight(0xff9860, 0.25);
bounce.position.set(-900, 160, -700);
bounce.target.position.set(0, 0, 300);
scene.add(bounce);
scene.add(bounce.target);

const SKY_PRESETS = {
  dusk: {
    top: 0x214b78, mid: 0x8fb6d8, horizon: 0xe7ad72, sun: 0xffb66e,
    sunDir: new THREE.Vector3(0.78, 0.30, -0.55),
    sunColor: 0xffb878, sunIntensity: 4.2,
    hemiSky: 0xa9c2e2, hemiGround: 0x5e4632, hemiIntensity: 0.45,
    ambient: 0.16, exposure: 1.0, fog: 0xcfae87, density: 0.000018,
    bounce: 0.22, label: '日间',
  },
  day: {
    top: 0x3f7fbe, mid: 0xbcd7ea, horizon: 0xdfe9ef, sun: 0xfff3d9,
    sunDir: new THREE.Vector3(0.55, 0.62, -0.35),
    sunColor: 0xfff5e2, sunIntensity: 4.0,
    hemiSky: 0xcfe3ff, hemiGround: 0x9c7a52, hemiIntensity: 0.85,
    ambient: 0.34, exposure: 1.0, fog: 0xd9d2c3, density: 0.000014,
    bounce: 0.18, label: '黄昏',
  },
};

// ---------------------------------------------------------------------------
// Model
// ---------------------------------------------------------------------------
const loader = new GLTFLoader();
const modelRoot = new THREE.Group();
scene.add(modelRoot);

const meshRecords = [];
const materialSet = new Set();
let model = null;

const GROUP_OFFSETS = {
  terrain: new THREE.Vector3(0, 0, 0),
  khufu: new THREE.Vector3(0, 300, 0),
  khafre: new THREE.Vector3(0, 238, 0),
  menkaure: new THREE.Vector3(0, 168, 0),
  queens: new THREE.Vector3(0, 104, 0),
  sphinx: new THREE.Vector3(0, 86, 0),
  temples: new THREE.Vector3(0, 46, 0),
  mastabas: new THREE.Vector3(0, 20, 0),
  rocks: new THREE.Vector3(0, 8, 0),
  other: new THREE.Vector3(0, 0, 0),
};

const EXTRA_LIFTS = [
  { re: /casing cap/i, offset: new THREE.Vector3(0, 66, 0) },
  { re: /granite facing/i, offset: new THREE.Vector3(0, 52, 0) },
  { re: /entrance/i, offset: new THREE.Vector3(0, 14, 0) },
];

function categoryFor(name) {
  if (/queen/i.test(name)) return 'queens';
  if (/temple|causeway|boat pits/i.test(name)) return 'temples';
  if (/mastaba/i.test(name)) return 'mastabas';
  if (/boulder/i.test(name)) return 'rocks';
  if (/^Sphinx/i.test(name)) return 'sphinx';
  if (/^Khufu/i.test(name)) return 'khufu';
  if (/^Khafre/i.test(name)) return 'khafre';
  if (/^Menkaure/i.test(name)) return 'menkaure';
  if (/plateau|edge/i.test(name)) return 'terrain';
  return 'other';
}

function extraOffset(name) {
  const out = new THREE.Vector3();
  for (const item of EXTRA_LIFTS) if (item.re.test(name)) out.add(item.offset);
  return out;
}

const MONUMENTS = {
  khufu: {
    index: '01', name: '胡夫金字塔', en: 'PYRAMID OF KHUFU / CHEOPS',
    dims: '230.33 × 230.33 m · 原高 146.6 m · 现高 138.5 m · 51°50′40″',
    text: '吉萨三大金字塔中最大、最古老的一座，约建于公元前 2560 年。内部保留国王室、王后室与大走廊；白色图拉石灰岩外壳几乎全部被剥离，形成今日所见的阶梯状石砌体与平顶。',
    anchor: new THREE.Vector3(0, 150, 0),
    focus: { pos: new THREE.Vector3(320, 205, 360), target: new THREE.Vector3(0, 76, 0) },
  },
  khafre: {
    index: '02', name: '哈夫拉金字塔', en: 'PYRAMID OF KHAFRE / CHEPHREN',
    dims: '215.25 × 215.25 m · 原高 143.5 m · 现高 136.4 m · 53°10′',
    text: '哈夫拉是胡夫之子。金字塔坐落于略高的基岩台地上，顶部仍保留约 10 m 高的白色图拉石灰岩外壳，是三大金字塔中最具辨识度的轮廓。',
    anchor: new THREE.Vector3(-321, 158, 340),
    focus: { pos: new THREE.Vector3(-80, 205, 680), target: new THREE.Vector3(-321, 78, 340) },
  },
  menkaure: {
    index: '03', name: '门卡乌拉金字塔', en: 'PYRAMID OF MENKAURE / MYKERINOS',
    dims: '102.2 × 104.6 m · 原高 65 m · 现高 61 m · 51°20′25″',
    text: '三大金字塔中最小的一座，底部保留红色阿斯旺花岗岩饰面，上部曾覆盖白色石灰岩。南侧并列三座王后金字塔，形成完整的葬祭建筑群。',
    anchor: new THREE.Vector3(-562, 78, 741),
    focus: { pos: new THREE.Vector3(-310, 160, 1010), target: new THREE.Vector3(-562, 38, 741) },
  },
  sphinx: {
    index: '04', name: '大狮身人面像', en: 'THE GREAT SPHINX',
    dims: '长 73 m · 宽 19 m · 高 20 m · 面向正东',
    text: '由吉萨高原的石灰岩基岩就地雕刻而成，位于哈夫拉河谷神庙东侧。模型采用低多边形扫描体块，按 73 m 长、20 m 高重新贴合围坑；适合中远距离观看。',
    anchor: new THREE.Vector3(329, 26, 434),
    focus: { pos: new THREE.Vector3(470, 80, 620), target: new THREE.Vector3(330, 5, 434) },
  },
};

const hotspotRecords = [];
let selectedKey = 'khufu';
let explodeTarget = 0;
let explode = 0;
let isDay = false;
let wireframe = false;
let flying = null;
let autoRotateResume = false;

function setInfo(key) {
  const d = MONUMENTS[key];
  if (!d) return;
  selectedKey = key;
  document.getElementById('infoIndex').textContent = d.index;
  document.getElementById('infoName').textContent = d.name;
  document.getElementById('infoEn').textContent = d.en;
  document.getElementById('infoDims').textContent = d.dims;
  document.getElementById('infoText').textContent = d.text;
  hotspotRecords.forEach((h) => h.el.classList.toggle('active', h.key === key));
}

function buildHotspots() {
  Object.entries(MONUMENTS).forEach(([key, data]) => {
    const el = document.createElement('button');
    el.className = 'hotspot';
    el.type = 'button';
    el.innerHTML = `<span class="dot"></span><span class="label"><b>${data.name}</b><em>${data.en.split(' / ')[0]}</em></span>`;
    el.addEventListener('click', (ev) => {
      ev.stopPropagation();
      setInfo(key);
      if (window.innerWidth < 900) {
        document.getElementById('panel').classList.remove('collapsed');
      }
      flyTo(data.focus.pos, data.focus.target);
    });
    hotspotsLayer.appendChild(el);
    hotspotRecords.push({ key, el, anchor: data.anchor.clone() });
  });
  setInfo(selectedKey);
}

function collectModel(root) {
  root.updateMatrixWorld(true);
  const maxAniso = renderer.capabilities.getMaxAnisotropy();
  root.traverse((obj) => {
    if (!obj.isMesh) return;
    const name = obj.name || '';
    const cat = categoryFor(name);
    obj.castShadow = !/plateau|edge|Far desert/i.test(name);
    obj.receiveShadow = true;
    obj.frustumCulled = true;

    const mats = Array.isArray(obj.material) ? obj.material : [obj.material];
    for (const mat of mats) {
      if (!mat) continue;
      materialSet.add(mat);
      if (mat.map) {
        mat.map.anisotropy = maxAniso;
        mat.map.needsUpdate = true;
      }
      mat.envMapIntensity = 0.55;
    }

    meshRecords.push({
      mesh: obj,
      base: obj.position.clone(),
      groupOffset: GROUP_OFFSETS[cat] || GROUP_OFFSETS.other,
      extra: extraOffset(name),
    });
  });
}

function makeFootprints() {
  const specs = [
    { cx: 0, cz: 0, w: 230.33, d: 230.33 },
    { cx: -321, cz: 340, w: 215.25, d: 215.25 },
    { cx: -562, cz: 741, w: 102.2, d: 104.6 },
    { cx: 329, cz: 434, w: 74, d: 35 },
  ];
  const mat = new THREE.LineBasicMaterial({
    color: 0xe0b975, transparent: true, opacity: 0, depthWrite: false,
  });
  specs.forEach((s) => {
    const pts = [
      new THREE.Vector3(s.cx - s.w / 2, 1.2, s.cz - s.d / 2),
      new THREE.Vector3(s.cx + s.w / 2, 1.2, s.cz - s.d / 2),
      new THREE.Vector3(s.cx + s.w / 2, 1.2, s.cz + s.d / 2),
      new THREE.Vector3(s.cx - s.w / 2, 1.2, s.cz + s.d / 2),
    ];
    const geo = new THREE.BufferGeometry().setFromPoints(pts);
    const line = new THREE.LineLoop(geo, mat);
    line.renderOrder = 2;
    scene.add(line);
  });
  return mat;
}

let footprintMaterial = null;

loader.load(
  '../Giza_Pyramids.glb?v=3',
  (gltf) => {
    model = gltf.scene;
    model.traverse((o) => {
      if (o.isMesh) o.receiveShadow = true;
    });
    modelRoot.add(model);
    collectModel(model);
    footprintMaterial = makeFootprints();
    buildHotspots();

    // Small delay lets the loading overlay fade rather than pop.
    setTimeout(() => {
      loading.classList.add('hidden');
    }, 420);
  },
  (xhr) => {
    const pct = xhr.lengthComputable && xhr.total ? Math.min(100, (xhr.loaded / xhr.total) * 100) : 0;
    loaderFill.style.width = `${pct.toFixed(1)}%`;
    loaderPct.textContent = `${pct.toFixed(0)}%`;
  },
  (err) => {
    console.error(err);
    document.querySelector('.loader-title').textContent = '模型加载失败';
    document.querySelector('.loader-note').textContent = '请确认 Giza_Pyramids.glb 与 viewer 文件夹处于同一目录，并通过本地服务器打开。';
    loaderPct.textContent = 'ERROR';
  }
);

// ---------------------------------------------------------------------------
// Camera flights, view presets
// ---------------------------------------------------------------------------
const VIEWS = {
  aerial: { pos: new THREE.Vector3(1180, 1250, 1600), target: new THREE.Vector3(-260, 0, 340) },
  sphinx: { pos: new THREE.Vector3(470, 80, 620), target: new THREE.Vector3(330, 5, 434) },
  plan: { pos: new THREE.Vector3(0, 1800, 1150), target: new THREE.Vector3(-80, 0, 350) },
};

function heroView() {
  if (window.innerWidth < 900) {
    return {
      pos: new THREE.Vector3(1450, 520, 2600),
      target: new THREE.Vector3(-430, 100, 300),
    };
  }
  return {
    pos: new THREE.Vector3(850, 280, 1350),
    target: new THREE.Vector3(-550, 80, 300),
  };
}

let isMobileLayout = null;

function applyResponsiveCamera() {
  const mobile = window.innerWidth < 900;
  if (mobile === isMobileLayout) return;
  isMobileLayout = mobile;
  camera.fov = mobile ? 52 : 40;
  camera.updateProjectionMatrix();
  const v = heroView();
  camera.position.copy(v.pos);
  controls.target.copy(v.target);
  controls.update();
}

function easeInOut(t) {
  return t < 0.5 ? 4 * t * t * t : 1 - Math.pow(-2 * t + 2, 3) / 2;
}

function flyTo(pos, target, duration = 1.25) {
  autoRotateResume = controls.autoRotate;
  controls.autoRotate = false;
  flying = {
    fromPos: camera.position.clone(),
    toPos: pos.clone(),
    fromTarget: controls.target.clone(),
    toTarget: target.clone(),
    t: 0,
    duration,
  };
  controls.enabled = false;
}

function updateFlight(dt) {
  if (!flying) return;
  flying.t += dt / flying.duration;
  const t = Math.min(1, flying.t);
  const e = easeInOut(t);
  camera.position.lerpVectors(flying.fromPos, flying.toPos, e);
  controls.target.lerpVectors(flying.fromTarget, flying.toTarget, e);
  if (t >= 1) {
    flying = null;
    controls.enabled = true;
    controls.autoRotate = autoRotateResume;
  }
}

function setView(key) {
  const v = key === 'hero' ? heroView() : VIEWS[key];
  if (!v) return;
  controls.autoRotate = false;
  document.querySelector('[data-action="orbit"]').classList.remove('active');
  flyTo(v.pos, v.target);
  document.querySelectorAll('[data-view]').forEach((b) => b.classList.toggle('active', b.dataset.view === key));
}

document.querySelectorAll('[data-view]').forEach((btn) => {
  btn.addEventListener('click', () => setView(btn.dataset.view));
});

document.getElementById('focusSelected').addEventListener('click', () => {
  const d = MONUMENTS[selectedKey];
  if (d) flyTo(d.focus.pos, d.focus.target);
});

// ---------------------------------------------------------------------------
// Display controls
// ---------------------------------------------------------------------------
const orbitBtn = document.querySelector('[data-action="orbit"]');
const labelsBtn = document.querySelector('[data-action="labels"]');
const wireBtn = document.querySelector('[data-action="wire"]');
const lightBtn = document.querySelector('[data-action="light"]');

orbitBtn.classList.add('active');
orbitBtn.addEventListener('click', () => {
  controls.autoRotate = !controls.autoRotate;
  orbitBtn.classList.toggle('active', controls.autoRotate);
});

labelsBtn.addEventListener('click', () => {
  document.body.classList.toggle('labels-off');
  labelsBtn.classList.toggle('active', !document.body.classList.contains('labels-off'));
});

wireBtn.addEventListener('click', () => {
  wireframe = !wireframe;
  materialSet.forEach((m) => {
    m.wireframe = wireframe;
    m.needsUpdate = true;
  });
  wireBtn.classList.toggle('active', wireframe);
});

function applyLight(preset) {
  const p = SKY_PRESETS[preset];
  skyUniforms.topColor.value.setHex(p.top);
  skyUniforms.midColor.value.setHex(p.mid);
  skyUniforms.horizonColor.value.setHex(p.horizon);
  skyUniforms.sunColor.value.setHex(p.sun);
  skyUniforms.sunDirection.value.copy(p.sunDir).normalize();

  sun.color.setHex(p.sunColor);
  sun.intensity = p.sunIntensity;
  sun.position.copy(p.sunDir).normalize().multiplyScalar(1800);
  sun.target.position.set(0, 0, 300);

  hemi.color.setHex(p.hemiSky);
  hemi.groundColor.setHex(p.hemiGround);
  hemi.intensity = p.hemiIntensity;
  ambient.intensity = p.ambient;
  bounce.intensity = p.bounce;
  renderer.toneMappingExposure = p.exposure;
  scene.environmentIntensity = preset === 'day' ? 0.24 : 0.14;

  scene.fog.color.setHex(p.fog);
  scene.fog.density = p.density;

  lightBtn.innerHTML = `<span class="ico">☀</span>${p.label}`;
  lightBtn.classList.toggle('active', preset === 'day');
}

lightBtn.addEventListener('click', () => {
  isDay = !isDay;
  applyLight(isDay ? 'day' : 'dusk');
});

// Explode slider
function updateExplodeUI() {
  const v = Math.round(explodeTarget * 100);
  explodeValue.textContent = `${v}%`;
  explodeInput.style.setProperty('--fill', `${v}%`);
}
explodeInput.addEventListener('input', () => {
  explodeTarget = Number(explodeInput.value) / 100;
  updateExplodeUI();
});
updateExplodeUI();

// Mobile panel
const panel = document.getElementById('panel');
document.getElementById('panelToggle').addEventListener('click', () => {
  panel.classList.toggle('collapsed');
});
if (window.innerWidth < 900) panel.classList.add('collapsed');

// Keyboard shortcuts
window.addEventListener('keydown', (e) => {
  if (e.target instanceof HTMLInputElement) return;
  const k = e.key.toLowerCase();
  if (k === 'r') setView('hero');
  if (k === 'e') {
    explodeTarget = explodeTarget > 0.05 ? 0 : 0.78;
    explodeInput.value = String(Math.round(explodeTarget * 100));
    updateExplodeUI();
  }
  if (k === 'l') labelsBtn.click();
  if (k === 'w') wireBtn.click();
  if (e.code === 'Space') {
    e.preventDefault();
    orbitBtn.click();
  }
});

// ---------------------------------------------------------------------------
// Animation
// ---------------------------------------------------------------------------
const clock = new THREE.Clock();
let fpsAccum = 0;
let fpsFrames = 0;

function updateExplode(dt) {
  explode = THREE.MathUtils.damp(explode, explodeTarget, 4.5, dt);
  if (Math.abs(explode - explodeTarget) < 0.0005) explode = explodeTarget;

  const e = easeInOut(explode);

  for (const rec of meshRecords) {
    const offset = rec.groupOffset.clone().multiplyScalar(e).add(rec.extra.clone().multiplyScalar(e));
    rec.mesh.position.copy(rec.base).add(offset);
  }

  if (footprintMaterial) footprintMaterial.opacity = 0.28 * e;

  hotspotRecords.forEach((h) => {
    const data = MONUMENTS[h.key];
    const group = GROUP_OFFSETS[h.key] || GROUP_OFFSETS.other;
    h.anchor.copy(data.anchor).add(group.clone().multiplyScalar(e));
  });
}

const projected = new THREE.Vector3();

function updateHotspots() {
  const w = window.innerWidth;
  const h = window.innerHeight;
  for (const rec of hotspotRecords) {
    projected.copy(rec.anchor).project(camera);
    const behind = projected.z > 1;
    const x = (projected.x * 0.5 + 0.5) * w;
    const y = (-projected.y * 0.5 + 0.5) * h;
    const visible = !behind && x > 10 && x < w - 10 && y > 40 && y < h - 40 && !(w >= 900 && x < 405);
    rec.el.style.opacity = visible ? '1' : '0';
    rec.el.style.pointerEvents = visible ? 'auto' : 'none';
    rec.el.style.left = `${x}px`;
    rec.el.style.top = `${y}px`;
    rec.el.style.zIndex = String(1000 - Math.round(projected.z * 100));
  }
}

function updateCompass() {
  const dir = new THREE.Vector3();
  camera.getWorldDirection(dir);
  const angle = Math.atan2(-dir.x, -dir.z);
  compassNeedle.style.transform = `rotate(${angle}rad)`;
}

function animate() {
  const dt = Math.min(clock.getDelta(), 0.06);

  updateFlight(dt);
  updateExplode(dt);
  controls.update();
  updateHotspots();
  updateCompass();

  renderer.render(scene, camera);

  fpsAccum += dt;
  fpsFrames += 1;
  if (fpsAccum > 0.6) {
    fpsEl.textContent = `${Math.round(fpsFrames / fpsAccum)} FPS`;
    fpsAccum = 0;
    fpsFrames = 0;
  }
}

renderer.setAnimationLoop(animate);

window.addEventListener('resize', () => {
  camera.aspect = window.innerWidth / window.innerHeight;
  camera.updateProjectionMatrix();
  renderer.setSize(window.innerWidth, window.innerHeight);
  renderer.setPixelRatio(Math.min(window.devicePixelRatio || 1, 1.8));
  applyResponsiveCamera();
});

// first light preset
applyLight('dusk');
applyResponsiveCamera();
