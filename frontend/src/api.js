export async function api(path, options = {}) {
    const headers = new Headers(options.headers ?? {});
    headers.set('Accept', 'application/json');

    const bodyIsForm = options.body instanceof FormData;
    if (options.body != null && !bodyIsForm && typeof options.body !== 'string') {
        headers.set('Content-Type', 'application/json');
        options = { ...options, body: JSON.stringify(options.body) };
    }

    let response;
    try {
        response = await fetch(path, {
            credentials: 'same-origin',
            ...options,
            signal: options.signal ?? AbortSignal.timeout(8000),
            headers,
        });
    } catch (error) {
        if (error.name === 'TimeoutError') {
            throw new Error('Server API tidak merespons. Pastikan FastAPI dan MySQL sedang berjalan.');
        }
        throw error;
    }
    const payload = await response.json().catch(() => ({}));

    if (!response.ok) {
        const error = new Error(payload.detail || payload.message || 'Permintaan gagal.');
        error.status = response.status;
        error.payload = payload;
        throw error;
    }

    return payload;
}