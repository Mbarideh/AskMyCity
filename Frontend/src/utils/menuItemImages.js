const IMAGE_BASE = "https://images.unsplash.com";

const EXACT_IMAGES = {
  "margherita pizza": `${IMAGE_BASE}/photo-1574071318508-1cdbab80d002?auto=format&fit=crop&w=320&q=80`,
  "pepperoni pizza": `${IMAGE_BASE}/photo-1628840042765-356cda07504e?auto=format&fit=crop&w=320&q=80`,
  "vegetarian pizza": `${IMAGE_BASE}/photo-1594007654729-407eedc4be65?auto=format&fit=crop&w=320&q=80`,
  "new york steak": `${IMAGE_BASE}/photo-1546964124-0cce460f38ef?auto=format&fit=crop&w=320&q=80`,
  "grilled salmon": `${IMAGE_BASE}/photo-1467003909585-2f8a72700288?auto=format&fit=crop&w=320&q=80`,
  "chicken parmesan": `${IMAGE_BASE}/photo-1604908176997-125f25cc6f3d?auto=format&fit=crop&w=320&q=80`,
  "lasagna": `${IMAGE_BASE}/photo-1574894709920-11b28e7367e3?auto=format&fit=crop&w=320&q=80`,
  "fettuccine alfredo": `${IMAGE_BASE}/photo-1473093295043-cdd812d0e601?auto=format&fit=crop&w=320&q=80`,
  "spaghetti marinara": `${IMAGE_BASE}/photo-1551892374-ecf8754cf8b0?auto=format&fit=crop&w=320&q=80`,
  "cheesecake": `${IMAGE_BASE}/photo-1565958011703-44f9829ba187?auto=format&fit=crop&w=320&q=80`,
  "tiramisu": `${IMAGE_BASE}/photo-1571877227200-a0d98ea607e9?auto=format&fit=crop&w=320&q=80`,
  "cappuccino": `${IMAGE_BASE}/photo-1572442388796-11668a67e53d?auto=format&fit=crop&w=320&q=80`,
  "espresso": `${IMAGE_BASE}/photo-1510707577719-ae7c14805e3a?auto=format&fit=crop&w=320&q=80`,
  "soda": `${IMAGE_BASE}/photo-1581636625402-29b2a704ef13?auto=format&fit=crop&w=320&q=80`,
  "caesar salad": `${IMAGE_BASE}/photo-1546793665-c74683f339c1?auto=format&fit=crop&w=320&q=80`,
  "greek salad": `${IMAGE_BASE}/photo-1540420773420-3366772f4999?auto=format&fit=crop&w=320&q=80`,
};

const KEYWORD_IMAGES = [
  ["pizza", `${IMAGE_BASE}/photo-1579751626657-72bc17010498?auto=format&fit=crop&w=320&q=80`],
  ["steak", `${IMAGE_BASE}/photo-1558030006-450675393462?auto=format&fit=crop&w=320&q=80`],
  ["salmon", `${IMAGE_BASE}/photo-1519708227418-c8fd9a32b7a2?auto=format&fit=crop&w=320&q=80`],
  ["chicken", `${IMAGE_BASE}/photo-1532550907401-a500c9a57435?auto=format&fit=crop&w=320&q=80`],
  ["pasta", `${IMAGE_BASE}/photo-1556761223-4c4282c73f77?auto=format&fit=crop&w=320&q=80`],
  ["spaghetti", `${IMAGE_BASE}/photo-1621996346565-e3dbc646d9a9?auto=format&fit=crop&w=320&q=80`],
  ["lasagna", `${IMAGE_BASE}/photo-1574894709920-11b28e7367e3?auto=format&fit=crop&w=320&q=80`],
  ["salad", `${IMAGE_BASE}/photo-1540420773420-3366772f4999?auto=format&fit=crop&w=320&q=80`],
  ["cake", `${IMAGE_BASE}/photo-1578985545062-69928b1d9587?auto=format&fit=crop&w=320&q=80`],
  ["tiramisu", `${IMAGE_BASE}/photo-1571877227200-a0d98ea607e9?auto=format&fit=crop&w=320&q=80`],
  ["coffee", `${IMAGE_BASE}/photo-1495474472287-4d71bcdd2085?auto=format&fit=crop&w=320&q=80`],
  ["cappuccino", `${IMAGE_BASE}/photo-1572442388796-11668a67e53d?auto=format&fit=crop&w=320&q=80`],
  ["espresso", `${IMAGE_BASE}/photo-1510707577719-ae7c14805e3a?auto=format&fit=crop&w=320&q=80`],
  ["soda", `${IMAGE_BASE}/photo-1581636625402-29b2a704ef13?auto=format&fit=crop&w=320&q=80`],
  ["drink", `${IMAGE_BASE}/photo-1544145945-f90425340c7e?auto=format&fit=crop&w=320&q=80`],
  ["burger", `${IMAGE_BASE}/photo-1568901346375-23c9450c58cd?auto=format&fit=crop&w=320&q=80`],
  ["sandwich", `${IMAGE_BASE}/photo-1528735602780-2552fd46c7af?auto=format&fit=crop&w=320&q=80`],
  ["soup", `${IMAGE_BASE}/photo-1547592166-23ac45744acd?auto=format&fit=crop&w=320&q=80`],
];

const CATEGORY_IMAGES = {
  salads: `${IMAGE_BASE}/photo-1540420773420-3366772f4999?auto=format&fit=crop&w=320&q=80`,
  desserts: `${IMAGE_BASE}/photo-1551024506-0bccd828d307?auto=format&fit=crop&w=320&q=80`,
  drinks: `${IMAGE_BASE}/photo-1544145945-f90425340c7e?auto=format&fit=crop&w=320&q=80`,
  food: `${IMAGE_BASE}/photo-1504674900247-0877df9cc836?auto=format&fit=crop&w=320&q=80`,
};

export function getAutomaticMenuItemImage(item, sectionKey = "food") {
  const normalizedName = String(item?.name || "").trim().toLowerCase();
  const normalizedDescription = String(item?.description || "").trim().toLowerCase();
  const searchableText = `${normalizedName} ${normalizedDescription}`;

  if (EXACT_IMAGES[normalizedName]) return EXACT_IMAGES[normalizedName];

  const keywordMatch = KEYWORD_IMAGES.find(([keyword]) => searchableText.includes(keyword));
  if (keywordMatch) return keywordMatch[1];

  return CATEGORY_IMAGES[sectionKey] || CATEGORY_IMAGES.food;
}
