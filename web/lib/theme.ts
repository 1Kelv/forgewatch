export const themeStorageKey = "forgewatch-theme";
// Static code only; no report or request data is interpolated into this script.
export const themeBootstrap = `(()=>{let t;try{t=localStorage.getItem("forgewatch-theme")}catch{}document.documentElement.dataset.theme=t==="dark"||t==="light"?t:matchMedia("(prefers-color-scheme: dark)").matches?"dark":"light"})()`;
