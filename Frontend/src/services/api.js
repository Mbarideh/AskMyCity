const API_BASE_URL = String(import.meta.env.VITE_API_BASE_URL || "http://127.0.0.1:8001").replace(/\/$/, "");


async function handleResponse(response) {
  let data;

  try {
    data = await response.json();
  } catch {
    data = null;
  }

  if (!response.ok) {
    throw new Error(
      data?.detail ||
      "The request could not be completed."
    );
  }

  return data;
}


function normalizeConversationMessages(
  messages = []
) {
  if (!Array.isArray(messages)) {
    return [];
  }

  return messages
    .filter((message) => {
      return (
        message &&
        (
          message.role === "user" ||
          message.role === "assistant"
        ) &&
        typeof message.content === "string" &&
        message.content.trim().length > 0
      );
    })
    .map((message) => {
      const resultIds = Array.isArray(message.results)
        ? message.results
            .map((result) => Number(result?.id))
            .filter((id) => Number.isInteger(id) && id > 0)
            .slice(0, 50)
        : Array.isArray(message.result_ids)
          ? message.result_ids
              .map((id) => Number(id))
              .filter((id) => Number.isInteger(id) && id > 0)
              .slice(0, 50)
          : [];

      return {
        role: message.role,
        content: message.content
          .trim()
          .slice(0, 2000),
        result_ids: resultIds,
      };
    })
    .slice(-20);
}


export async function getPlaces({
  search = "",
  city = "",
  category = "",
  minimumRating = "",
} = {}) {
  const parameters = new URLSearchParams();

  if (search.trim()) {
    parameters.set(
      "search",
      search.trim()
    );
  }

  if (city.trim()) {
    parameters.set(
      "city",
      city.trim()
    );
  }

  if (category.trim()) {
    parameters.set(
      "category",
      category.trim()
    );
  }

  if (minimumRating !== "") {
    parameters.set(
      "minimum_rating",
      String(minimumRating)
    );
  }

  const url =
    parameters.toString().length > 0
      ? `${API_BASE_URL}/places?${parameters}`
      : `${API_BASE_URL}/places`;

  const response = await fetch(url);

  return handleResponse(response);
}




export async function getExplorePlaces({
  search = "",
  city = "",
  category = "",
  limit = 60,
} = {}) {
  const parameters = new URLSearchParams();

  if (search.trim()) parameters.set("search", search.trim());
  if (city.trim()) parameters.set("city", city.trim());
  if (category.trim()) parameters.set("category", category.trim());
  parameters.set("limit", String(limit));

  const response = await fetch(
    `${API_BASE_URL}/places/explore?${parameters.toString()}`
  );

  return handleResponse(response);
}

export async function getPlace(placeId) {
  const response = await fetch(
    `${API_BASE_URL}/places/${placeId}`
  );

  return handleResponse(response);
}


/**
 * Send a conversational AI search request.
 *
 * query:
 * The user's newest message.
 *
 * location:
 * Optional browser GPS coordinates.
 *
 * messages:
 * Previous user and assistant messages.
 */
export async function searchWithAI(
  query,
  location = null,
  messages = [],
) {
  const normalizedQuery = String(
    query || ""
  ).trim();

  if (normalizedQuery.length < 3) {
    throw new Error(
      "Please enter a longer search request."
    );
  }

  const normalizedMessages =
    normalizeConversationMessages(
      messages
    );

  const body = {
    query: normalizedQuery,
    messages: normalizedMessages,
  };

  if (
    location &&
    typeof location.latitude === "number" &&
    Number.isFinite(
      location.latitude
    ) &&
    typeof location.longitude === "number" &&
    Number.isFinite(
      location.longitude
    )
  ) {
    body.latitude =
      location.latitude;

    body.longitude =
      location.longitude;
  }

  const response = await fetch(
    `${API_BASE_URL}/ai/search`,
    {
      method: "POST",
      headers: {
        "Content-Type":
          "application/json",
      },
      body: JSON.stringify(body),
    }
  );

  return handleResponse(response);
}


export async function registerUser(
  userData
) {
  const response = await fetch(
    `${API_BASE_URL}/auth/register`,
    {
      method: "POST",
      headers: {
        "Content-Type":
          "application/json",
      },
      body: JSON.stringify(
        userData
      ),
    }
  );

  return handleResponse(response);
}


export async function loginUser(
  credentials
) {
  const response = await fetch(
    `${API_BASE_URL}/auth/login`,
    {
      method: "POST",
      headers: {
        "Content-Type":
          "application/json",
      },
      body: JSON.stringify(
        credentials
      ),
    }
  );

  return handleResponse(response);
}
function authHeaders(token, includeJson = false) {
  const headers = {};
  if (token) headers.Authorization = `Bearer ${token}`;
  if (includeJson) headers["Content-Type"] = "application/json";
  return headers;
}

export async function getCurrentUser(token) {
  const response = await fetch(`${API_BASE_URL}/auth/me`, { headers: authHeaders(token) });
  return handleResponse(response);
}

export async function getBusinessStudioOverview(token) {
  const response = await fetch(`${API_BASE_URL}/dashboard/studio-overview`, { headers: authHeaders(token), cache: "no-store" });
  return handleResponse(response);
}

export async function getDashboardOverview(token) {
  const response = await fetch(`${API_BASE_URL}/dashboard/overview`, { headers: authHeaders(token) });
  return handleResponse(response);
}

export async function getBusinessProfile(token) {
  const response = await fetch(`${API_BASE_URL}/dashboard/profile`, { headers: authHeaders(token) });
  return handleResponse(response);
}

export async function saveBusinessProfile(token, profile) {
  const response = await fetch(`${API_BASE_URL}/dashboard/profile`, {
    method: "PUT", headers: authHeaders(token, true), body: JSON.stringify(profile),
  });
  return handleResponse(response);
}

export async function getMenuItems(token) {
  const response = await fetch(`${API_BASE_URL}/dashboard/menu`, { headers: authHeaders(token) });
  return handleResponse(response);
}

export async function createMenuItem(token, item) {
  const response = await fetch(`${API_BASE_URL}/dashboard/menu`, {
    method: "POST", headers: authHeaders(token, true), body: JSON.stringify(item),
  });
  return handleResponse(response);
}

export async function deleteMenuItem(token, itemId) {
  const response = await fetch(`${API_BASE_URL}/dashboard/menu/${itemId}`, {
    method: "DELETE", headers: authHeaders(token),
  });
  if (!response.ok) return handleResponse(response);
  return null;
}

export async function getBusinessClaims(token) {
  const response = await fetch(`${API_BASE_URL}/dashboard/claims`, { headers: authHeaders(token) });
  return handleResponse(response);
}

export async function createBusinessClaim(token, claim) {
  const response = await fetch(`${API_BASE_URL}/dashboard/claims`, {
    method: "POST", headers: authHeaders(token, true), body: JSON.stringify(claim),
  });
  return handleResponse(response);
}

export async function getFavorites(token) {
  const response = await fetch(`${API_BASE_URL}/favorites`, {
    headers: authHeaders(token),
  });
  return handleResponse(response);
}

export async function addFavorite(token, placeId) {
  const response = await fetch(`${API_BASE_URL}/favorites/${placeId}`, {
    method: "POST",
    headers: authHeaders(token),
  });
  return handleResponse(response);
}

export async function removeFavorite(token, placeId) {
  const response = await fetch(`${API_BASE_URL}/favorites/${placeId}`, {
    method: "DELETE",
    headers: authHeaders(token),
  });

  if (!response.ok) {
    return handleResponse(response);
  }

  return null;
}

export async function getReviews(placeId) {
  const response = await fetch(`${API_BASE_URL}/places/${placeId}/reviews`);
  return handleResponse(response);
}

export async function submitReview(token, placeId, review) {
  const response = await fetch(`${API_BASE_URL}/places/${placeId}/reviews`, {
    method: "POST",
    headers: authHeaders(token, true),
    body: JSON.stringify(review),
  });
  return handleResponse(response);
}

export async function getPublicMenu(placeId) {
  const response = await fetch(`${API_BASE_URL}/places/${placeId}/menu`);
  return handleResponse(response);
}

export async function recordBusinessEvent(placeId, eventType) {
  const response = await fetch(`${API_BASE_URL}/places/${placeId}/events`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ event_type: eventType }),
  });
  return handleResponse(response);
}

export async function getBusinessReviews(token) {
  const response = await fetch(`${API_BASE_URL}/dashboard/reviews-data`, {
    headers: authHeaders(token),
  });
  return handleResponse(response);
}

export async function replyToBusinessReview(token, reviewId, ownerReply) {
  const response = await fetch(`${API_BASE_URL}/dashboard/reviews/${reviewId}/reply`, {
    method: "PATCH",
    headers: authHeaders(token, true),
    body: JSON.stringify({ owner_reply: ownerReply || null }),
  });
  return handleResponse(response);
}


export function absoluteMediaUrl(url) {
  if (!url) return "";
  if (/^https?:\/\//i.test(url) || url.startsWith("data:")) return url;
  return `${API_BASE_URL}${url.startsWith("/") ? "" : "/"}${url}`;
}

export async function getBusinessMedia(token) {
  const response = await fetch(`${API_BASE_URL}/dashboard/media`, { headers: authHeaders(token) });
  return handleResponse(response);
}

export async function uploadBusinessMedia(token, mediaType, file) {
  const formData = new FormData();
  formData.append("file", file);
  const response = await fetch(`${API_BASE_URL}/dashboard/media/${mediaType}`, {
    method: "POST", headers: authHeaders(token), body: formData,
  });
  return handleResponse(response);
}

export async function deleteBusinessMedia(token, mediaId) {
  const response = await fetch(`${API_BASE_URL}/dashboard/media/${mediaId}`, { method: "DELETE", headers: authHeaders(token) });
  if (!response.ok) return handleResponse(response);
  return null;
}

export async function getBusinessLocation(token) {
  const response = await fetch(`${API_BASE_URL}/dashboard/profile/location`, {
    headers: authHeaders(token),
    cache: "no-store",
  });
  return handleResponse(response);
}

export async function saveBusinessLocation(token, location) {
  const response = await fetch(`${API_BASE_URL}/dashboard/profile/location`, {
    method: "PUT",
    headers: authHeaders(token, true),
    body: JSON.stringify(location),
  });
  return handleResponse(response);
}

export async function searchBusinessAddress(token, query) {
  const parameters = new URLSearchParams({ q: String(query || "").trim() });
  const response = await fetch(`${API_BASE_URL}/dashboard/profile/geocode?${parameters.toString()}`, {
    headers: authHeaders(token),
    cache: "no-store",
  });
  return handleResponse(response);
}
