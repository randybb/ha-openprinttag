// OpenPrintTag Spool card: the spool on a reader, from the integration's Spool sensor.
// Plain custom element, no build step; loaded by the integration (add_extra_js_url).

const fmt = (v, digits = 0) =>
  v === undefined || v === null || Number.isNaN(Number(v)) ? "–" : Number(v).toFixed(digits);
const range = (a, b) => (a === undefined && b === undefined ? null : `${fmt(a)}–${fmt(b)} °C`);
const esc = (s) =>
  String(s).replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" })[c]);

class OpenPrintTagCard extends HTMLElement {
  static getConfigForm() {
    return {
      schema: [
        { name: "entity", required: true, selector: { entity: { filter: { integration: "openprinttag" } } } },
        { name: "sticky", selector: { boolean: {} } },
      ],
    };
  }

  static getStubConfig(hass) {
    const entity = Object.keys(hass.entities || {}).find((id) => hass.entities[id].platform === "openprinttag");
    return { entity: entity || "" };
  }

  setConfig(config) {
    if (!config.entity) throw new Error("entity is required");
    this._config = config;
    this._key = null;
  }

  getCardSize() {
    return 4;
  }

  set hass(hass) {
    const state = hass.states[this._config.entity];
    // re-render only when the sensor changed
    const key = state ? state.last_updated : "missing";
    if (key === this._key) return;
    this._key = key;
    if (!this.shadowRoot) this.attachShadow({ mode: "open" });
    this.shadowRoot.innerHTML = `<style>${STYLE}</style><ha-card>${this._body(state)}</ha-card>`;
  }

  _body(state) {
    if (!state) return `<div class="empty">${esc(this._config.entity)} not found</div>`;
    const a = state.attributes;
    const removed = state.state === "unknown" || state.state === "unavailable";
    // sticky: the last spool stays, dimmed, until another one is read
    if (removed && !(this._config.sticky && a.uid)) {
      return `<div class="empty"><ha-icon icon="mdi:printer-3d-nozzle-off"></ha-icon>No spool on the reader</div>`;
    }
    const material = (a.database && a.database.material) || {};
    const full = a.actual_netto_full_weight ?? a.nominal_netto_full_weight;
    const length = a.actual_full_length ?? a.nominal_full_length;
    const left = full !== undefined ? Math.max(full - (a.consumed_weight || 0), 0) : undefined;
    const pct = full ? Math.round((left / full) * 100) : null;
    const color = a.primary_color || (material.primary_color || {}).color_rgba || "#888";

    const facts = [
      ["mdi:printer-3d-nozzle-heat", "Print", range(a.min_print_temperature, a.max_print_temperature)],
      ["mdi:radiator", "Bed", range(a.min_bed_temperature, a.max_bed_temperature)],
      ["mdi:cube-outline", "Chamber", a.chamber_temperature !== undefined ? `${fmt(a.chamber_temperature)} °C` : null],
      [
        "mdi:tumble-dryer",
        "Drying",
        a.drying_temperature !== undefined ? `${fmt(a.drying_temperature)} °C · ${fmt(a.drying_time)} min` : null,
      ],
      ["mdi:diameter-variant", "Diameter", a.filament_diameter !== undefined ? `${fmt(a.filament_diameter, 2)} mm` : null],
      ["mdi:calendar", "Made", a.manufactured_date ? new Date(a.manufactured_date).toLocaleDateString() : null],
    ].filter((f) => f[2]);

    const tags = [...(a.tags || []), ...(a.certifications || material.certifications || [])];

    return `
      ${removed ? `<div class="removed"><ha-icon icon="mdi:tray-remove"></ha-icon>Removed from the reader</div>` : ""}
      <div class="${removed ? "dim" : ""}">
      <div class="head">
        <div class="swatch" style="background:${esc(color)}"></div>
        <div class="title">
          <div class="name">${esc(a.material_name || state.state)}</div>
          <div class="sub">${esc([a.brand_name, a.material_type, color].filter(Boolean).join(" · "))}</div>
        </div>
        ${a.entity_picture ? `<img src="${esc(a.entity_picture)}" alt="">` : ""}
      </div>
      ${
        pct === null
          ? ""
          : `<div class="left">
              <div class="bar"><div style="width:${pct}%;background:${esc(color)}"></div></div>
              <div class="sub">${fmt(left)} g of ${fmt(full)} g${
                length ? ` · ~${fmt((length * left) / full / 1000)} m` : ""
              } · ${pct} %</div>
            </div>`
      }
      <div class="facts">
        ${facts
          .map(
            ([icon, label, value]) =>
              `<div class="fact"><ha-icon icon="${icon}"></ha-icon><span class="label">${label}</span>${esc(value)}</div>`,
          )
          .join("")}
      </div>
      ${tags.length ? `<div class="tags">${tags.map((t) => `<span>${esc(String(t).replace(/_/g, " "))}</span>`).join("")}</div>` : ""}
      </div>
    `;
  }
}

const STYLE = `
  ha-card { padding: 16px; }
  .empty { display: flex; align-items: center; gap: 8px; color: var(--secondary-text-color); }
  .head { display: flex; align-items: center; gap: 12px; }
  .swatch { flex: none; width: 40px; height: 40px; border-radius: 50%; border: 1px solid var(--divider-color); }
  .title { flex: 1; min-width: 0; }
  .name { font-size: 1.2em; font-weight: 500; color: var(--primary-text-color); }
  .sub { color: var(--secondary-text-color); font-size: 0.9em; }
  img { flex: none; width: 72px; height: 72px; object-fit: contain; }
  .left { margin-top: 12px; }
  .bar { height: 8px; border-radius: 4px; background: var(--divider-color); overflow: hidden; margin-bottom: 4px; }
  .bar div { height: 100%; }
  .facts { display: grid; grid-template-columns: repeat(auto-fill, minmax(150px, 1fr)); gap: 6px 12px; margin-top: 12px; }
  .fact { display: flex; align-items: center; gap: 6px; color: var(--primary-text-color); font-size: 0.9em; }
  .fact ha-icon { --mdc-icon-size: 18px; color: var(--secondary-text-color); }
  .label { color: var(--secondary-text-color); }
  .tags { display: flex; flex-wrap: wrap; gap: 6px; margin-top: 12px; }
  .removed { display: flex; align-items: center; gap: 6px; margin-bottom: 8px; color: var(--secondary-text-color); font-size: 0.9em; }
  .removed ha-icon { --mdc-icon-size: 18px; }
  .dim { opacity: 0.55; }
  .tags span { padding: 2px 8px; border-radius: 12px; background: var(--secondary-background-color); font-size: 0.8em; }
`;

customElements.define("openprinttag-card", OpenPrintTagCard);
window.customCards = window.customCards || [];
window.customCards.push({
  type: "openprinttag-card",
  name: "OpenPrintTag Spool",
  description: "The spool on an OpenPrintTag reader: color, remaining filament, temperatures",
  preview: true,
});
