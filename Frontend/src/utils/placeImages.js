function addCandidate(target, value) {
  if (typeof value !== "string") return;
  let normalized = value.trim();
  if (normalized.startsWith("/media/")) normalized = `http://127.0.0.1:8001${normalized}`;
  if (!normalized || target.includes(normalized)) return;
  target.push(normalized);
}

function addJsonCandidates(target, value) {
  if (!value) return;

  if (Array.isArray(value)) {
    value.forEach((item) => {
      if (typeof item === "string") addCandidate(target, item);
      else if (item && typeof item === "object") {
        addCandidate(target, item.url);
        addCandidate(target, item.image_url);
        addCandidate(target, item.photo_url);
      }
    });
    return;
  }

  if (typeof value !== "string") return;
  const trimmed = value.trim();
  if (!trimmed) return;

  try {
    addJsonCandidates(target, JSON.parse(trimmed));
  } catch {
    trimmed
      .split(/[|,\n]/)
      .map((item) => item.trim())
      .filter(Boolean)
      .forEach((item) => addCandidate(target, item));
  }
}

function hashText(text = "") {
  let hash = 0;
  for (let index = 0; index < text.length; index += 1) {
    hash = (hash * 31 + text.charCodeAt(index)) >>> 0;
  }
  return hash;
}

function escapeXml(value = "") {
  return String(value)
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&apos;");
}

export function getPlaceFallbackImage(place = {}) {
  const name = place.name || "Local Business";
  const category = place.category || "AskMyCity";
  const seed = hashText(`${name}-${category}-${place.id || ""}`);
  const hueOne = seed % 360;
  const hueTwo = (hueOne + 45 + (seed % 80)) % 360;
  const initials = name
    .split(/\s+/)
    .filter(Boolean)
    .slice(0, 2)
    .map((part) => part[0]?.toUpperCase())
    .join("") || "AM";

  const svg = `
    <svg xmlns="http://www.w3.org/2000/svg" width="1200" height="760" viewBox="0 0 1200 760">
      <defs>
        <linearGradient id="background" x1="0" y1="0" x2="1" y2="1">
          <stop offset="0%" stop-color="hsl(${hueOne} 72% 48%)"/>
          <stop offset="100%" stop-color="hsl(${hueTwo} 68% 30%)"/>
        </linearGradient>
      </defs>
      <rect width="1200" height="760" fill="url(#background)"/>
      <circle cx="1040" cy="90" r="260" fill="white" opacity="0.08"/>
      <circle cx="120" cy="700" r="300" fill="white" opacity="0.06"/>
      <rect x="80" y="80" width="1040" height="600" rx="42" fill="white" opacity="0.08"/>
      <text x="600" y="330" text-anchor="middle" fill="white" font-family="Arial, sans-serif" font-size="170" font-weight="700">${escapeXml(initials)}</text>
      <text x="600" y="445" text-anchor="middle" fill="white" font-family="Arial, sans-serif" font-size="48" font-weight="700">${escapeXml(name.slice(0, 34))}</text>
      <text x="600" y="515" text-anchor="middle" fill="white" opacity="0.82" font-family="Arial, sans-serif" font-size="30">${escapeXml(category.slice(0, 42))}</text>
    </svg>`;

  return `data:image/svg+xml;charset=UTF-8,${encodeURIComponent(svg)}`;
}

export function getPlaceImages(place = {}) {
  const images = [];

  addCandidate(images, place.photo_url);
  addCandidate(images, place.image_url);
  addCandidate(images, place.google_photo_url);
  addCandidate(images, place.thumbnail_url);
  addCandidate(images, place.logo_url);
  addCandidate(images, place.street_view_url);

  addJsonCandidates(images, place.photos);
  addJsonCandidates(images, place.photos_json);
  addJsonCandidates(images, place.image_urls);
  addJsonCandidates(images, place.images);

  if (images.length === 0) images.push(getPlaceFallbackImage(place));
  return images;
}

export function getPrimaryPlaceImage(place = {}) {
  return getPlaceImages(place)[0];
}
