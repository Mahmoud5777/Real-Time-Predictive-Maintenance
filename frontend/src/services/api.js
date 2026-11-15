
const API_BASE_URL =
  import.meta.env.VITE_API_BASE_URL || "http://localhost:8000";

/**
 * Fonction centrale pour communiquer avec le backend FastAPI.
 */
export async function apiRequest(path, options = {}) {
  const url = `${API_BASE_URL}${path.startsWith("/") ? path : `/${path}`}`;

  const response = await fetch(url, {
    ...options,
    headers: {
      "Content-Type": "application/json",
      ...options.headers,
    },
  });

  // Une réponse HTTP 204 ne contient pas de données.
  let data = null;

  if (response.status !== 204) {
    const contentType = response.headers.get("content-type");

    if (contentType?.includes("application/json")) {
      data = await response.json();
    } else {
      data = await response.text();
    }
  }

  // Gestion des erreurs HTTP.
  if (!response.ok) {
    const message =
      typeof data === "object" && data !== null
        ? data.detail || data.message || "Erreur du serveur"
        : data || "Erreur du serveur";

    throw new Error(`Erreur API (${response.status}) : ${message}`);
  }

  return data;
}

// Méthodes HTTP disponibles.
export const api = {
  get: (path) => apiRequest(path),

  post: (path, body) =>
    apiRequest(path, {
      method: "POST",
      body: JSON.stringify(body),
    }),

  put: (path, body) =>
    apiRequest(path, {
      method: "PUT",
      body: JSON.stringify(body),
    }),

  delete: (path) =>
    apiRequest(path, {
      method: "DELETE",
    }),
};
