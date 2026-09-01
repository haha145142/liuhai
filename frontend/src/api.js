const API=import.meta.env.VITE_API_BASE||'http://localhost:8000/api/v1'
export async function getJSON(path){const r=await fetch(API+path);if(!r.ok)throw new Error(`HTTP ${r.status}`);return r.json()}
