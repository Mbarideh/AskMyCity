import { useEffect, useMemo, useState } from "react";
import { useAuth } from "../../context/AuthContext";
import { createMenuItem, deleteMenuItem, getMenuItems } from "../../services/api";
import { inferMenuItemIcon, MENU_ICON_OPTIONS } from "../../utils/menuIcons";
import DashboardShell from "./DashboardShell";
import "./dashboard.css";

const blank = {
  name: "",
  category: "Main",
  description: "",
  price: "",
  photo_url: "",
  icon: "",
  is_available: true,
  is_featured: false,
};

export default function MenuPage() {
  const { token } = useAuth();
  const [items, setItems] = useState([]);
  const [form, setForm] = useState(blank);
  const [error, setError] = useState("");

  function load() {
    getMenuItems(token).then(setItems).catch((e) => setError(e.message));
  }

  useEffect(load, [token]);

  const set = (key) => (event) => {
    setForm((current) => ({
      ...current,
      [key]: event.target.type === "checkbox" ? event.target.checked : event.target.value,
    }));
  };

  const automaticIcon = useMemo(() => inferMenuItemIcon(form), [form]);
  const selectedIcon = form.icon || automaticIcon;

  async function add(event) {
    event.preventDefault();
    try {
      setError("");
      await createMenuItem(token, {
        ...form,
        icon: selectedIcon,
        price: form.price === "" ? null : Number(form.price),
      });
      setForm(blank);
      load();
    } catch (err) {
      setError(err.message);
    }
  }

  async function remove(id) {
    if (!window.confirm("Delete this item?")) return;
    await deleteMenuItem(token, id);
    load();
  }

  return (
    <DashboardShell>
      <div className="dashboard-heading">
        <div>
          <p className="dashboard-eyebrow">MENU / SERVICES</p>
          <h1>Show what you offer</h1>
          <p>Each item gets a matching icon automatically. You can override it before saving.</p>
        </div>
      </div>

      <div className="dashboard-columns menu-layout">
        <form className="dashboard-panel dashboard-form compact-form" onSubmit={add}>
          <h2>Add an item</h2>

          <div className="menu-icon-preview-row">
            <div className="menu-icon-preview" aria-hidden="true">{selectedIcon}</div>
            <div>
              <strong>{form.icon ? "Selected icon" : "Automatic icon"}</strong>
              <p>{form.name ? `Preview for ${form.name}` : "Type a menu item name to get the best icon."}</p>
            </div>
          </div>

          <label>
            Name
            <input value={form.name} onChange={set("name")} required />
          </label>

          <div className="field-grid">
            <label>
              Category
              <input value={form.category} onChange={set("category")} />
            </label>
            <label>
              Price
              <input type="number" min="0" step="0.01" value={form.price} onChange={set("price")} />
            </label>
          </div>

          <label>
            Description
            <textarea rows="4" value={form.description} onChange={set("description")} />
          </label>

          <fieldset className="menu-icon-picker">
            <legend>Icon</legend>
            <div className="menu-icon-picker-grid">
              <button
                type="button"
                className={!form.icon ? "active auto" : "auto"}
                onClick={() => setForm((current) => ({ ...current, icon: "" }))}
                title="Choose automatically"
              >
                <span>{automaticIcon}</span>
                <small>Auto</small>
              </button>
              {MENU_ICON_OPTIONS.map((icon) => (
                <button
                  type="button"
                  key={icon}
                  className={form.icon === icon ? "active" : ""}
                  onClick={() => setForm((current) => ({ ...current, icon }))}
                  aria-label={`Use ${icon} icon`}
                >
                  {icon}
                </button>
              ))}
            </div>
          </fieldset>

          <label className="publish-toggle">
            <input type="checkbox" checked={form.is_featured} onChange={set("is_featured")} />
            Featured item
          </label>

          <button className="dashboard-primary">Add item</button>
          {error && <div className="dashboard-alert error">{error}</div>}
        </form>

        <section className="dashboard-panel">
          <div className="panel-title">
            <h2>Your items</h2>
            <span>{items.length}</span>
          </div>

          {items.length === 0 ? (
            <p>No items yet.</p>
          ) : (
            <div className="menu-list">
              {items.map((item) => (
                <article key={item.id}>
                  <div className="studio-menu-item-main">
                    <div className="studio-menu-item-icon" aria-hidden="true">{inferMenuItemIcon(item)}</div>
                    <div>
                      <small>{item.category}</small>
                      <h3>{item.name}</h3>
                      <p>{item.description || "No description"}</p>
                    </div>
                  </div>
                  <div className="menu-price">
                    {item.price == null ? "—" : `$${Number(item.price).toFixed(2)}`}
                    <button type="button" onClick={() => remove(item.id)}>Delete</button>
                  </div>
                </article>
              ))}
            </div>
          )}
        </section>
      </div>
    </DashboardShell>
  );
}
